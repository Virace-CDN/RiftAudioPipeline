"""独立 relay 进程：接收本地 envelope，并复用现有 relay spool 引擎对接 control plane。"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import socketserver
import time

from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.models import RunBootstrapRequest
from rift_audio_pipeline.control_plane.models import RunReportRequest
from rift_audio_pipeline.control_plane.models import RunHeartbeatRequest
from rift_audio_pipeline.control_plane.models import RunLogEventRequest
from rift_audio_pipeline.control_plane.models import RunLogFinalizeRequest
from rift_audio_pipeline.control_plane.service import ControlPlaneService
from rift_audio_pipeline.pipeline.logging import RelaySpoolPump
from rift_audio_pipeline.pipeline.logging import LogSinkConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus

ATTENTION_LEVELS = frozenset({"WARNING", "ERROR", "CRITICAL"})
RELAY_STATUS_REASON_MISSING_START_SIGNAL = "missing_start_signal"
RELAY_STATUS_REASON_WARNING_OR_ERROR_DETECTED = "warning_or_error_detected"
RELAY_STATUS_REASON_MAIN_PROCESS_EXITED_WITHOUT_FINALIZE = "main_process_exited_without_finalize"
RELAY_STATUS_REASON_MAIN_SHUTDOWN_WITHOUT_TERMINAL_SUMMARY = "main_shutdown_without_terminal_summary"
RELAY_STATUS_REASON_RELAY_SHUTDOWN_WITHOUT_TERMINAL_SUMMARY = "relay_shutdown_without_terminal_summary"
RELAY_STATUS_REASON_RELAY_RUNTIME_ERROR = "relay_runtime_error"


class _LogRelayRuntime:
    """relay 进程的运行时控制器。"""

    def __init__(self, config_path: Path) -> None:
        payload = _read_json_object(config_path)
        self._run_id = _require_str(payload, "run_id")
        self._socket_path = Path(_require_str(payload, "socket_path"))
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()
        control_plane_config = ControlPlaneConfig(
            base_url=_require_str(payload, "control_plane_base_url"),
            bearer_token=_optional_str(payload, "bearer_token"),
            access_client_id=_optional_str(payload, "access_client_id"),
            access_client_secret=_optional_str(payload, "access_client_secret"),
            timeout_seconds=_require_float(payload, "timeout_seconds"),
        )
        self._service = ControlPlaneService(ControlPlaneClient(control_plane_config))
        self._state_file = Path(_require_str(payload, "state_file"))
        self._log_dir = self._state_file.parent
        self._pump = RelaySpoolPump(
            run_id=self._run_id,
            state_file=self._state_file,
            config=LogSinkConfig(
                enabled=True,
                control_plane_base_url=control_plane_config.base_url,
                bearer_token=control_plane_config.bearer_token,
                access_client_id=control_plane_config.access_client_id,
                access_client_secret=control_plane_config.access_client_secret,
                timeout_seconds=control_plane_config.timeout_seconds,
                max_queue_size=_require_int(payload, "max_queue_size"),
                flush_interval_ms=_require_int(payload, "flush_interval_ms"),
                retry_backoff_ms=tuple(_require_int_list(payload, "retry_backoff_ms")),
                spool_dir=Path(_require_str(payload, "spool_dir")),
                monitor_interval_ms=_optional_int(payload, "monitor_interval_ms", default=500),
                heartbeat_interval_ms=_optional_int(payload, "heartbeat_interval_ms", default=5000),
            ),
            send_event=lambda event: self._service.report_pipeline_run_log_event(
                RunLogEventRequest(run_id=self._run_id, event=event)
            ),
            send_terminal_summary=lambda summary: self._service.finalize_pipeline_run_logs(
                RunLogFinalizeRequest(run_id=self._run_id, summary=summary)
            ),
        )
        self._shutdown_requested = False
        self._main_pid: int | None = None
        self._main_started = False
        self._terminal_summary_received = False
        self._attention_detected = False
        self._status_reason: str | None = None
        self._last_seq = 0
        self._last_stage = "init"
        self._last_log_at = _current_timestamp()
        self._monitor_interval_seconds = self._pump._config.monitor_interval_ms / 1000
        self._heartbeat_interval_seconds = self._pump._config.heartbeat_interval_ms / 1000

    def serve(self) -> None:
        """启动 socket server，直到收到 shutdown。"""

        fatal_error: Exception | None = None
        self._pump.start()
        next_heartbeat_at = time.monotonic() + self._heartbeat_interval_seconds
        next_monitor_at = time.monotonic() + self._monitor_interval_seconds
        try:
            with _LogRelayServer(self._socket_path, self) as server:
                server.timeout = min(
                    self._heartbeat_interval_seconds,
                    self._monitor_interval_seconds,
                    0.2,
                )
                while not self._shutdown_requested:
                    server.handle_request()
                    now = time.monotonic()
                    if (
                        self._main_started
                        and not self._terminal_summary_received
                        and now >= next_heartbeat_at
                    ):
                        self._send_heartbeat(status="running")
                        next_heartbeat_at = now + self._heartbeat_interval_seconds
                    if (
                        self._main_started
                        and not self._terminal_summary_received
                        and self._main_pid is not None
                        and now >= next_monitor_at
                    ):
                        if not _is_process_alive(self._main_pid):
                            self._finalize_if_missing(
                                reason=RELAY_STATUS_REASON_MAIN_PROCESS_EXITED_WITHOUT_FINALIZE
                            )
                            self._shutdown_requested = True
                        next_monitor_at = now + self._monitor_interval_seconds
        except Exception as error:  # noqa: BLE001
            fatal_error = error
            self._report_runtime_failure(error)
        finally:
            if fatal_error is None:
                self._finalize_if_missing(
                    reason=RELAY_STATUS_REASON_RELAY_SHUTDOWN_WITHOUT_TERMINAL_SUMMARY
                )
            try:
                self._pump.close()
            except Exception as pump_error:  # noqa: BLE001
                if fatal_error is None:
                    self._report_runtime_failure(pump_error)
            if self._socket_path.exists():
                self._socket_path.unlink()
        if fatal_error is not None:
            raise fatal_error

    def handle_message(self, message: dict[str, object]) -> dict[str, object]:
        """处理来自主进程的 envelope。"""

        envelope_type = _require_str(message, "type")
        if envelope_type == "ping":
            return {"accepted": True, "type": envelope_type}
        payload = _require_dict(message, "payload")
        if envelope_type == "start":
            self._main_pid = _require_int(payload, "main_pid")
            self._main_started = True
            self._status_reason = None
            self._last_log_at = _optional_str(payload, "started_at") or _current_timestamp()
            try:
                self._service.notify_pipeline_run_started(
                    RunBootstrapRequest(
                        run_id=self._run_id,
                        started_at=self._last_log_at,
                    )
                )
            except Exception:
                return {"accepted": True, "type": envelope_type}
            self._send_heartbeat(status="running")
            return {"accepted": True, "type": envelope_type}
        if envelope_type == "event":
            self._register_event(payload)
            self._pump.enqueue_event(self._build_plane_event(payload))
            return {"accepted": True, "type": envelope_type}
        if envelope_type == "terminal_summary":
            self._terminal_summary_received = True
            normalized_summary = self._normalize_terminal_summary(payload)
            final_stage = normalized_summary.get("final_stage")
            if isinstance(final_stage, str) and final_stage:
                self._last_stage = final_stage
            self._pump.set_terminal_summary(normalized_summary)
            self._send_heartbeat(status=str(normalized_summary["final_status"]))
            return {"accepted": True, "type": envelope_type}
        if envelope_type == "report":
            self._service.report_pipeline_run_result(
                RunReportRequest(
                    run_id=self._run_id,
                    status=PipelineRunStatus(_require_str(payload, "status")),
                    changes=tuple(_require_list_of_dicts(payload, "changes")),
                    finished_at=_optional_str(payload, "finished_at"),
                )
            )
            return {"accepted": True, "type": envelope_type}
        if envelope_type == "shutdown":
            self._finalize_if_missing(
                reason=RELAY_STATUS_REASON_MAIN_SHUTDOWN_WITHOUT_TERMINAL_SUMMARY
            )
            self._shutdown_requested = True
            return {"accepted": True, "type": envelope_type}
        raise ValueError(f"未知 relay envelope type: {envelope_type}")

    def _register_event(self, payload: dict[str, object]) -> None:
        """登记主进程发来的运行事件。"""

        event_seq = payload.get("seq")
        if isinstance(event_seq, int):
            self._last_seq = max(self._last_seq, event_seq)
        stage = payload.get("stage")
        if isinstance(stage, str) and stage:
            self._last_stage = stage
        created_at = payload.get("created_at")
        if isinstance(created_at, str) and created_at:
            self._last_log_at = created_at
        level = payload.get("level")
        if isinstance(level, str) and level.upper() in ATTENTION_LEVELS:
            self._attention_detected = True
        if isinstance(payload.get("error_type"), str) or isinstance(payload.get("error_message"), str):
            self._attention_detected = True

    def _build_plane_event(self, payload: dict[str, object]) -> dict[str, object]:
        """为 worker 构造精简后的结构化事件。"""

        event = {
            "schema_version": payload.get("schema_version", 1),
            "run_id": self._run_id,
            "seq": payload.get("seq", self._last_seq),
            "created_at": payload.get("created_at", self._last_log_at),
            "source": payload.get("source", "pipeline"),
            "level": payload.get("level", "INFO"),
            "stage": payload.get("stage", self._last_stage),
            "event_type": payload.get("event_type", "unknown"),
            "message": payload.get("message", ""),
            "status_hint": payload.get("status_hint"),
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "entity_alias": payload.get("entity_alias"),
            "attempt": payload.get("attempt"),
            "operation": payload.get("operation"),
        }
        if isinstance(payload.get("payload"), dict) and payload["payload"]:
            event["payload"] = payload["payload"]
        if isinstance(payload.get("error_type"), str) or isinstance(payload.get("error_message"), str):
            event["error_type"] = payload.get("error_type")
            event["error_message"] = payload.get("error_message")
            event["code_file"] = payload.get("code_file")
            event["code_function"] = payload.get("code_function")
            event["code_line"] = payload.get("code_line")
            event["exception_module"] = payload.get("exception_module")
        return event

    def _normalize_terminal_summary(self, payload: dict[str, object]) -> dict[str, object]:
        """按 relay 规则标准化终态摘要。"""

        summary = dict(payload)
        final_status = summary.get("final_status")
        if not isinstance(final_status, str):
            raise ValueError("terminal summary 缺少 final_status。")
        relay_metadata = _require_dict(summary, "summary") if isinstance(summary.get("summary"), dict) else {}
        if final_status == PipelineRunStatus.SUCCESS.value and not self._main_started:
            final_status = PipelineRunStatus.FAILED.value
            self._status_reason = RELAY_STATUS_REASON_MISSING_START_SIGNAL
        elif final_status == PipelineRunStatus.SUCCESS.value and self._attention_detected:
            final_status = PipelineRunStatus.PARTIAL_SUCCESS.value
            self._status_reason = RELAY_STATUS_REASON_WARNING_OR_ERROR_DETECTED
        relay_metadata["status"] = final_status
        relay_metadata["relay_runtime"] = self._build_runtime_snapshot(status=final_status)
        summary["summary"] = relay_metadata
        summary["final_status"] = final_status
        return summary

    def _finalize_if_missing(self, *, reason: str) -> None:
        """若主进程未显式发送终态，则由 relay 推断失败。"""

        if self._terminal_summary_received or not self._main_started:
            return
        self._terminal_summary_received = True
        self._status_reason = reason
        self._pump.enqueue_event(
            {
                "schema_version": 1,
                "run_id": self._run_id,
                "seq": self._next_relay_seq(),
                "created_at": _current_timestamp(),
                "source": "relay",
                "level": "ERROR",
                "stage": self._last_stage,
                "event_type": "relay_inferred_failed",
                "message": "主进程已结束但未发送终态摘要，relay 推断本次运行失败。",
                "status_hint": PipelineRunStatus.FAILED.value,
                "thread_name": "LogRelayMonitor",
                "process_id": os.getpid(),
                "entity_type": None,
                "entity_id": None,
                "entity_alias": None,
                "attempt": None,
                "operation": "log_relay.monitor",
                "code_file": __file__,
                "code_function": "_finalize_if_missing",
                "code_line": None,
                "error_type": "ProcessExitedWithoutFinalize",
                "error_message": reason,
                "exception_module": None,
                "traceback": None,
                "cause_chain": (),
                "payload": {
                    "relay_status_reason": reason,
                    "main_pid": self._main_pid,
                    "relay_runtime": self._build_runtime_snapshot(
                        status=PipelineRunStatus.FAILED.value
                    ),
                },
            }
        )
        summary = {
            "run_id": self._run_id,
            "finished_at": _current_timestamp(),
            "final_status": PipelineRunStatus.FAILED.value,
            "final_stage": self._last_stage,
            "last_seq": self._last_seq,
            "processed_targets": 0,
            "succeeded_targets": 0,
            "failed_targets": 1,
            "uploaded_archives": 0,
            "raw_log_bundle_ready": False,
            "raw_log_local_dir": str(self._log_dir),
            "raw_log_remote_path": None,
            "summary": {
                "status": PipelineRunStatus.FAILED.value,
                "relay_runtime": self._build_runtime_snapshot(
                    status=PipelineRunStatus.FAILED.value
                ),
            },
            "error_brief": {
                "error_type": "ProcessExitedWithoutFinalize",
                "error_message": "主进程已退出但未发送结束通知。",
            },
            "schema_version": 1,
        }
        self._pump.set_terminal_summary(summary)
        self._send_heartbeat(status=PipelineRunStatus.FAILED.value)

    def _send_heartbeat(self, *, status: str) -> None:
        """把 relay 当前观察到的运行状态回报给控制面。"""

        try:
            self._service.report_pipeline_run_heartbeat(
                RunHeartbeatRequest(
                    run_id=self._run_id,
                    status=status,
                    last_log_at=self._last_log_at,
                    progress={
                        "stage": self._last_stage,
                        "last_seq": self._last_seq,
                        "relay_runtime": self._build_runtime_snapshot(status=status),
                    },
                )
            )
        except Exception:  # noqa: BLE001
            return

    def _next_relay_seq(self) -> int:
        """为 relay 自生成事件分配顺序号。"""

        self._last_seq += 1
        return self._last_seq

    def _build_runtime_snapshot(self, *, status: str) -> dict[str, object]:
        """构造稳定的 relay 运行态快照。"""

        return {
            "managed": True,
            "status": status,
            "status_reason": self._status_reason,
            "start_signal_received": self._main_started,
            "terminal_summary_received": self._terminal_summary_received,
            "attention_detected": self._attention_detected,
            "main_pid": self._main_pid,
            "last_stage": self._last_stage,
            "last_seq": self._last_seq,
            "last_log_at": self._last_log_at,
        }

    def _report_runtime_failure(self, error: Exception) -> None:
        """relay 自身异常时，直接向 worker 回报失败终态。"""

        self._terminal_summary_received = True
        self._status_reason = RELAY_STATUS_REASON_RELAY_RUNTIME_ERROR
        relay_runtime = self._build_runtime_snapshot(status=PipelineRunStatus.FAILED.value)
        terminal_summary = {
            "run_id": self._run_id,
            "finished_at": _current_timestamp(),
            "final_status": PipelineRunStatus.FAILED.value,
            "final_stage": self._last_stage,
            "last_seq": self._last_seq,
            "processed_targets": 0,
            "succeeded_targets": 0,
            "failed_targets": 1,
            "uploaded_archives": 0,
            "raw_log_bundle_ready": False,
            "raw_log_local_dir": str(self._log_dir),
            "raw_log_remote_path": None,
            "summary": {
                "status": PipelineRunStatus.FAILED.value,
                "relay_runtime": relay_runtime,
            },
            "error_brief": {
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            "schema_version": 1,
        }
        self._write_runtime_failure_state(error=error, relay_runtime=relay_runtime)
        try:
            self._service.finalize_pipeline_run_logs(
                RunLogFinalizeRequest(run_id=self._run_id, summary=terminal_summary)
            )
        except Exception:  # noqa: BLE001
            return
        self._send_heartbeat(status=PipelineRunStatus.FAILED.value)

    def _write_runtime_failure_state(
        self,
        *,
        error: Exception,
        relay_runtime: dict[str, object],
    ) -> None:
        """在本地状态文件留下 relay fatal 线索。"""

        self._state_file.write_text(
            json.dumps(
                {
                    "run_id": self._run_id,
                    "state": "relay_runtime_error",
                    "last_seq": self._last_seq,
                    "last_stage": self._last_stage,
                    "last_log_at": self._last_log_at,
                    "relay_runtime": relay_runtime,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "updated_at": _current_timestamp(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


class _LogRelayServer(socketserver.UnixStreamServer):
    """把 controller 暴露给 request handler。"""

    allow_reuse_address = True

    def __init__(self, socket_path: Path, runtime: _LogRelayRuntime) -> None:
        self.runtime = runtime
        super().__init__(str(socket_path), _LogRelayRequestHandler)


class _LogRelayRequestHandler(socketserver.StreamRequestHandler):
    """处理单个 relay socket 请求。"""

    def handle(self) -> None:
        try:
            raw = self.rfile.readline()
            if not raw:
                return
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("relay envelope 必须是 JSON 对象。")
            response = self.server.runtime.handle_message(decoded)  # type: ignore[attr-defined]
        except Exception as error:  # noqa: BLE001
            response = {"accepted": False, "error": str(error)}
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    """relay 进程 CLI 入口。"""

    parser = argparse.ArgumentParser(description="RiftAudioPipeline log relay process")
    parser.add_argument("--config", required=True, help="Relay 运行配置 JSON 文件路径")
    args = parser.parse_args(argv)
    runtime = _LogRelayRuntime(Path(args.config))
    runtime.serve()
    return 0


def _read_json_object(path: Path) -> dict[str, object]:
    """读取 JSON 对象文件。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"relay config 必须是 JSON 对象：{path}")
    return payload


def _require_str(payload: dict[str, object], key: str) -> str:
    """读取必填字符串。"""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"relay config 缺少非空字符串字段：{key}")
    return value


def _optional_str(payload: dict[str, object], key: str) -> str | None:
    """读取可选字符串。"""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"relay config 字段必须是字符串或 null：{key}")
    return value


def _require_int(payload: dict[str, object], key: str) -> int:
    """读取必填整数。"""

    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"relay config 字段必须是整数：{key}")
    return value


def _require_float(payload: dict[str, object], key: str) -> float:
    """读取必填浮点数。"""

    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"relay config 字段必须是数字：{key}")
    return float(value)


def _require_int_list(payload: dict[str, object], key: str) -> list[int]:
    """读取整数列表。"""

    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ValueError(f"relay config 字段必须是整数列表：{key}")
    return list(value)


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    """读取必填对象。"""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"relay envelope 字段必须是对象：{key}")
    return value


def _require_list_of_dicts(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} 必须是对象数组。")
    results: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{key} 必须是对象数组。")
        results.append(item)
    return results


def _optional_int(payload: dict[str, object], key: str, *, default: int) -> int:
    """读取可选整数。"""

    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, int):
        raise ValueError(f"relay config 字段必须是整数：{key}")
    return value


def _current_timestamp() -> str:
    """返回当前带时区时间。"""

    return datetime.now().astimezone().isoformat()


def _is_process_alive(pid: int) -> bool:
    """检查目标 PID 是否仍存在。"""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


if __name__ == "__main__":
    raise SystemExit(main())
