"""独立日志 worker，负责读取本地日志并回放到 plane。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import time

from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.models import RunHeartbeatRequest
from rift_audio_pipeline.control_plane.models import RunLogEventRequest
from rift_audio_pipeline.control_plane.models import RunLogFinalizeRequest
from rift_audio_pipeline.control_plane.service import ControlPlaneService
from rift_audio_pipeline.pipeline.logging import LogSinkConfig
from rift_audio_pipeline.pipeline.logging import RelaySpoolPump


@dataclass(frozen=True, slots=True)
class LogWorkerConfig:
    """独立日志 worker 配置。"""

    run_id: str
    log_dir: Path
    state_file: Path
    spool_dir: Path
    pipeline_pid_file: Path
    control_plane_base_url: str
    bearer_token: str | None = None
    access_client_id: str | None = None
    access_client_secret: str | None = None
    timeout_seconds: float = 5.0
    poll_interval_ms: int = 200
    heartbeat_interval_ms: int = 5000
    retry_backoff_ms: tuple[int, ...] = (200, 1000, 5000)
    flush_interval_ms: int = 200
    max_queue_size: int = 2000
    raw_log_remote_path: str | None = None


class LogWorker:
    """文件观察型日志 worker。"""

    def __init__(self, config: LogWorkerConfig) -> None:
        self._config = config
        self._events_file = config.log_dir / "events.jsonl"
        self._run_file = config.log_dir / "run.json"
        self._error_file = config.log_dir / "error.json"
        self._service = ControlPlaneService(
            ControlPlaneClient(
                ControlPlaneConfig(
                    base_url=config.control_plane_base_url,
                    bearer_token=config.bearer_token,
                    access_client_id=config.access_client_id,
                    access_client_secret=config.access_client_secret,
                    timeout_seconds=config.timeout_seconds,
                )
            )
        )
        self._pump = RelaySpoolPump(
            run_id=config.run_id,
            state_file=config.state_file,
            config=LogSinkConfig(
                enabled=True,
                control_plane_base_url=config.control_plane_base_url,
                bearer_token=config.bearer_token,
                access_client_id=config.access_client_id,
                access_client_secret=config.access_client_secret,
                timeout_seconds=config.timeout_seconds,
                max_queue_size=config.max_queue_size,
                flush_interval_ms=config.flush_interval_ms,
                retry_backoff_ms=config.retry_backoff_ms,
                spool_dir=config.spool_dir,
            ),
            send_event=self._send_event,
            send_terminal_summary=self._send_terminal_summary,
        )
        self._pipeline_pid: int | None = None
        self._main_started = False
        self._attention_detected = False
        self._last_seq = 0
        self._last_stage = "init"
        self._last_log_at = datetime.now().astimezone().isoformat()
        self._terminal_sent = False
        self._events_offset = 0

    def serve(self) -> None:
        """启动 worker，直到发送终态。"""

        self._pump.start()
        next_heartbeat_at = time.monotonic() + self._config.heartbeat_interval_ms / 1000
        try:
            while not self._terminal_sent:
                self._maybe_load_pipeline_pid()
                self._drain_events_file()
                if self._maybe_finalize_from_run_file():
                    break
                if time.monotonic() >= next_heartbeat_at and self._main_started:
                    self._send_heartbeat(status="running")
                    next_heartbeat_at = (
                        time.monotonic() + self._config.heartbeat_interval_ms / 1000
                    )
                if self._maybe_infer_failed():
                    break
                time.sleep(self._config.poll_interval_ms / 1000)
        finally:
            if not self._terminal_sent:
                self._pump.close()

    def _maybe_load_pipeline_pid(self) -> None:
        if self._pipeline_pid is not None or not self._config.pipeline_pid_file.exists():
            return
        raw_pid = self._config.pipeline_pid_file.read_text(encoding="utf-8").strip()
        if not raw_pid:
            return
        self._pipeline_pid = int(raw_pid)
        self._main_started = True

    def _drain_events_file(self) -> None:
        if not self._events_file.exists():
            return
        with self._events_file.open("r", encoding="utf-8") as handle:
            handle.seek(self._events_offset)
            while True:
                line = handle.readline()
                if not line:
                    break
                self._events_offset = handle.tell()
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                self._main_started = True
                self._last_seq = _int_value(payload.get("seq"), default=self._last_seq)
                self._last_stage = _str_value(payload.get("stage"), default=self._last_stage)
                self._last_log_at = _str_value(
                    payload.get("created_at"),
                    default=self._last_log_at,
                )
                level = _str_value(payload.get("level"), default="INFO")
                if level.upper() in {"WARNING", "ERROR", "CRITICAL"}:
                    self._attention_detected = True
                self._pump.enqueue_event(_build_plane_event(run_id=self._config.run_id, payload=payload))

    def _maybe_finalize_from_run_file(self) -> bool:
        if not self._run_file.exists():
            return False
        run_summary = json.loads(self._run_file.read_text(encoding="utf-8"))
        if not isinstance(run_summary, dict):
            raise ValueError(f"run.json 结构非法：{self._run_file}")
        final_status = _str_value(run_summary.get("status"), default="failed")
        terminal_summary = {
            "run_id": self._config.run_id,
            "finished_at": datetime.now().astimezone().isoformat(),
            "final_status": final_status,
            "final_stage": _resolve_final_stage(run_summary, self._error_file),
            "last_seq": self._last_seq,
            "processed_targets": _int_value(run_summary.get("processed_targets")),
            "succeeded_targets": _int_value(run_summary.get("succeeded_targets")),
            "failed_targets": _int_value(run_summary.get("failed_targets")),
            "uploaded_archives": _int_value(run_summary.get("uploaded_archives")),
            "raw_log_bundle_ready": True,
            "raw_log_local_dir": str(self._config.log_dir),
            "raw_log_remote_path": self._config.raw_log_remote_path,
            "summary": {
                "status": final_status,
                "relay_runtime": self._build_runtime_snapshot(status=final_status),
            },
            "error_brief": _load_error_brief(self._error_file),
            "schema_version": 1,
        }
        self._pump.set_terminal_summary(terminal_summary)
        self._send_heartbeat(status=final_status)
        self._pump.close()
        self._terminal_sent = True
        return True

    def _maybe_infer_failed(self) -> bool:
        if self._terminal_sent or self._pipeline_pid is None or self._run_file.exists():
            return False
        if _is_process_alive(self._pipeline_pid):
            return False
        terminal_summary = {
            "run_id": self._config.run_id,
            "finished_at": datetime.now().astimezone().isoformat(),
            "final_status": "failed",
            "final_stage": self._last_stage,
            "last_seq": self._last_seq,
            "processed_targets": 0,
            "succeeded_targets": 0,
            "failed_targets": 1,
            "uploaded_archives": 0,
            "raw_log_bundle_ready": False,
            "raw_log_local_dir": str(self._config.log_dir),
            "raw_log_remote_path": self._config.raw_log_remote_path,
            "summary": {
                "status": "failed",
                "relay_runtime": self._build_runtime_snapshot(status="failed"),
            },
            "error_brief": {
                "error_type": "ProcessExitedWithoutRunSummary",
                "error_message": "pipeline 主进程退出，但未写出 run.json。",
            },
            "schema_version": 1,
        }
        self._pump.set_terminal_summary(terminal_summary)
        self._send_heartbeat(status="failed")
        self._pump.close()
        self._terminal_sent = True
        return True

    def _send_event(self, payload: dict[str, object]) -> None:
        self._service.report_pipeline_run_log_event(
            RunLogEventRequest(run_id=self._config.run_id, event=payload)
        )

    def _send_terminal_summary(self, payload: dict[str, object]) -> None:
        self._service.finalize_pipeline_run_logs(
            RunLogFinalizeRequest(run_id=self._config.run_id, summary=payload)
        )

    def _send_heartbeat(self, *, status: str) -> None:
        self._service.report_pipeline_run_heartbeat(
            RunHeartbeatRequest(
                run_id=self._config.run_id,
                status=status,
                last_log_at=self._last_log_at,
                progress={
                    "stage": self._last_stage,
                    "last_seq": self._last_seq,
                    "relay_runtime": self._build_runtime_snapshot(status=status),
                },
            )
        )

    def _build_runtime_snapshot(self, *, status: str) -> dict[str, object]:
        return {
            "managed": True,
            "status": status,
            "status_reason": None if status != "failed" else "process_exited_without_run_summary",
            "start_signal_received": self._main_started,
            "terminal_summary_received": self._terminal_sent,
            "attention_detected": self._attention_detected,
            "main_pid": self._pipeline_pid,
            "last_stage": self._last_stage,
            "last_seq": self._last_seq,
            "last_log_at": self._last_log_at,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="独立日志 worker。")
    parser.add_argument("--config", type=Path, required=True)
    return parser


def load_config(config_path: Path) -> LogWorkerConfig:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"log worker config 非法：{config_path}")
    return LogWorkerConfig(
        run_id=_require_str(payload, "run_id"),
        log_dir=Path(_require_str(payload, "log_dir")),
        state_file=Path(_require_str(payload, "state_file")),
        spool_dir=Path(_require_str(payload, "spool_dir")),
        pipeline_pid_file=Path(_require_str(payload, "pipeline_pid_file")),
        control_plane_base_url=_require_str(payload, "control_plane_base_url"),
        bearer_token=_optional_str(payload, "bearer_token"),
        access_client_id=_optional_str(payload, "access_client_id"),
        access_client_secret=_optional_str(payload, "access_client_secret"),
        timeout_seconds=_float_value(payload.get("timeout_seconds"), default=5.0),
        poll_interval_ms=_int_value(payload.get("poll_interval_ms"), default=200),
        heartbeat_interval_ms=_int_value(payload.get("heartbeat_interval_ms"), default=5000),
        retry_backoff_ms=tuple(_int_tuple(payload.get("retry_backoff_ms"))),
        flush_interval_ms=_int_value(payload.get("flush_interval_ms"), default=200),
        max_queue_size=_int_value(payload.get("max_queue_size"), default=2000),
        raw_log_remote_path=_optional_str(payload, "raw_log_remote_path"),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    worker = LogWorker(load_config(args.config))
    worker.serve()
    return 0


def _build_plane_event(*, run_id: str, payload: dict[str, object]) -> dict[str, object]:
    event = {
        "schema_version": _int_value(payload.get("schema_version"), default=1),
        "run_id": run_id,
        "seq": _int_value(payload.get("seq")),
        "created_at": _str_value(payload.get("created_at"), default=datetime.now().astimezone().isoformat()),
        "source": _str_value(payload.get("source"), default="pipeline"),
        "level": _str_value(payload.get("level"), default="INFO"),
        "stage": _str_value(payload.get("stage"), default="init"),
        "event_type": _str_value(payload.get("event_type"), default="unknown"),
        "message": _str_value(payload.get("message"), default=""),
        "status_hint": payload.get("status_hint"),
        "entity_type": payload.get("entity_type"),
        "entity_id": payload.get("entity_id"),
        "entity_alias": payload.get("entity_alias"),
        "attempt": payload.get("attempt"),
        "operation": payload.get("operation"),
    }
    extra_payload = payload.get("payload")
    if isinstance(extra_payload, dict) and extra_payload:
        event["payload"] = extra_payload
    if isinstance(payload.get("error_type"), str) or isinstance(payload.get("error_message"), str):
        event["error_type"] = payload.get("error_type")
        event["error_message"] = payload.get("error_message")
        event["code_file"] = payload.get("code_file")
        event["code_function"] = payload.get("code_function")
        event["code_line"] = payload.get("code_line")
        event["exception_module"] = payload.get("exception_module")
    return event


def _resolve_final_stage(run_summary: dict[str, object], error_file: Path) -> str:
    if error_file.exists():
        payload = json.loads(error_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return _str_value(payload.get("stage"), default="finalize")
    return _str_value(run_summary.get("status"), default="finalize") if False else "finalize"


def _load_error_brief(error_file: Path) -> dict[str, object] | None:
    if not error_file.exists():
        return None
    payload = json.loads(error_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return {
        "error_type": _optional_str(payload, "error_type"),
        "error_message": _optional_str(payload, "error_message"),
    }


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _require_str(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串。")
    return value


def _optional_str(payload: dict[str, object], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是字符串。")
    return value


def _str_value(value: object, *, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _int_value(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _float_value(value: object, *, default: float) -> float:
    return value if isinstance(value, (int, float)) else default


def _int_tuple(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        return (200, 1000, 5000)
    return tuple(item for item in value if isinstance(item, int))


if __name__ == "__main__":
    raise SystemExit(main())
