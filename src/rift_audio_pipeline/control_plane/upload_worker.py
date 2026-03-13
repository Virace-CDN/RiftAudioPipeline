"""独立百度上传 worker。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
import json
import os
from pathlib import Path
import time
import uuid

from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.artifact_utils import calculate_sha256
from rift_audio_pipeline.simulation import BAIDU_FAILURE_MODE_ENV_VAR
from rift_audio_pipeline.simulation import MOCK_BAIDU_ENV_VAR
from rift_audio_pipeline.simulation import SIMULATION_ENV_VAR
from rift_audio_pipeline.control_plane.state_db import claim_next_upload_task
from rift_audio_pipeline.control_plane.state_db import complete_upload_task
from rift_audio_pipeline.control_plane.state_db import get_run_drain_state
from rift_audio_pipeline.control_plane.state_db import mark_upload_phase_drained
from rift_audio_pipeline.control_plane.state_db import record_new_file_fact
from rift_audio_pipeline.control_plane.state_db import reschedule_upload_task


@dataclass(frozen=True, slots=True)
class UploadWorkerConfig:
    """独立上传 worker 配置。"""

    run_id: str
    state_db_path: Path
    baidu_token_file: Path
    archive_remote_root: str
    worker_id: str
    output_root: Path | None = None
    delete_local_file_after_upload: bool = False
    poll_interval_ms: int = 500
    retry_backoff_seconds: tuple[int, ...] = (2, 5, 15, 30)


class UploadWorker:
    """消费本地 SQLite 上传队列。"""

    def __init__(self, config: UploadWorkerConfig) -> None:
        self._config = config
        token_payload = json.loads(config.baidu_token_file.read_text(encoding="utf-8"))
        if not isinstance(token_payload, dict):
            raise ValueError(f"baidu token 文件顶层必须是对象：{config.baidu_token_file}")
        self._client = BaiduPanClient(
            credentials=BaiduCredentials(
                access_token=_require_str(token_payload, "access_token"),
            ),
            remote_dir=config.archive_remote_root,
            token_store=None,
            allow_token_refresh=False,
        )

    def serve(self) -> None:
        """持续消费上传队列，直到 drain。"""

        print(
            json.dumps(
                {
                    "event": "upload_worker_started",
                    "run_id": self._config.run_id,
                    "worker_id": self._config.worker_id,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        try:
            while True:
                task = claim_next_upload_task(
                    database_path=self._config.state_db_path,
                    run_id=self._config.run_id,
                    worker_id=self._config.worker_id,
                )
                if task is None:
                    production_closed, unfinished_count = get_run_drain_state(
                        database_path=self._config.state_db_path,
                        run_id=self._config.run_id,
                    )
                    if production_closed and unfinished_count == 0:
                        mark_upload_phase_drained(
                            database_path=self._config.state_db_path,
                            run_id=self._config.run_id,
                        )
                        print(
                            json.dumps(
                                {
                                    "event": "upload_worker_drained",
                                    "run_id": self._config.run_id,
                                    "worker_id": self._config.worker_id,
                                },
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                        return
                    time.sleep(self._config.poll_interval_ms / 1000)
                    continue
                self._process_task(task)
        finally:
            self._client.close()

    def _process_task(self, task: object) -> None:
        payload = json.loads(task.payload_json) if getattr(task, "payload_json", None) else {}
        if not isinstance(payload, dict):
            payload = {}
        local_path = Path(task.local_path)
        remote_relative_path = payload.get("remote_relative_path")
        if not isinstance(remote_relative_path, str) or not remote_relative_path.strip():
            raise ValueError(f"上传任务缺少 remote_relative_path：task_id={task.id}")
        try:
            print(
                json.dumps(
                    {
                        "event": "upload_task_started",
                        "run_id": self._config.run_id,
                        "worker_id": self._config.worker_id,
                        "task_id": task.id,
                        "local_path": str(local_path),
                        "remote_relative_path": remote_relative_path,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            self._upload_file(
                local_path=local_path,
                remote_relative_path=remote_relative_path,
                metadata=payload,
                task_id=task.id,
            )
            uploaded_at = _now()
            packaged_at = (
                datetime.fromtimestamp(local_path.stat().st_ctime).astimezone().isoformat()
            )
            record_new_file_fact(
                database_path=self._config.state_db_path,
                run_id=self._config.run_id,
                local_path=str(local_path),
                remote_path=task.remote_path,
                file_name=local_path.name,
                sha256=calculate_sha256(local_path),
                packaged_at=packaged_at,
                uploaded_at=uploaded_at,
                metadata={
                    "task_type": task.task_type,
                    "remote_relative_path": remote_relative_path,
                    **payload,
                },
            )
            if self._config.delete_local_file_after_upload:
                local_path.unlink()
            complete_upload_task(
                database_path=self._config.state_db_path,
                task_id=task.id,
            )
            print(
                json.dumps(
                    {
                        "event": "upload_task_completed",
                        "run_id": self._config.run_id,
                        "worker_id": self._config.worker_id,
                        "task_id": task.id,
                        "remote_path": task.remote_path,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        except Exception as error:  # noqa: BLE001
            next_retry_at = _next_retry_at(
                base_time=datetime.now().astimezone(),
                attempt_count=task.attempt_count + 1,
                backoff_seconds=self._config.retry_backoff_seconds,
            )
            reschedule_upload_task(
                database_path=self._config.state_db_path,
                task_id=task.id,
                last_error=str(error),
                next_retry_at=next_retry_at,
            )
            print(
                json.dumps(
                    {
                        "event": "upload_task_rescheduled",
                        "run_id": self._config.run_id,
                        "worker_id": self._config.worker_id,
                        "task_id": task.id,
                        "error": str(error),
                        "next_retry_at": next_retry_at,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    def _upload_file(
        self,
        *,
        local_path: Path,
        remote_relative_path: str,
        metadata: dict[str, object],
        task_id: int,
    ) -> None:
        if os.getenv(SIMULATION_ENV_VAR) == "1" or os.getenv(MOCK_BAIDU_ENV_VAR) == "1":
            failure_mode = os.getenv(BAIDU_FAILURE_MODE_ENV_VAR, "none")
            if failure_mode in {"archive", "both"}:
                raise RuntimeError("本地联调模拟：archive upload failure")
            if self._config.output_root is not None:
                receipt_path = self._config.output_root / "simulation" / "archive_upload.json"
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "recorded_at": _now(),
                    "remote_root": self._config.archive_remote_root,
                    "archives": [],
                }
                if receipt_path.exists():
                    decoded = json.loads(receipt_path.read_text(encoding="utf-8"))
                    if isinstance(decoded, dict):
                        payload.update(decoded)
                archives_obj = payload.get("archives")
                archives = archives_obj if isinstance(archives_obj, list) else []
                if str(local_path) not in archives:
                    archives.append(str(local_path))
                payload["archives"] = archives
                game_version = metadata.get("game_version")
                if isinstance(game_version, str) and game_version.strip():
                    payload["version"] = game_version
                receipt_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            return
        self._client.upload_file(
            local_path=local_path,
            remote_path=remote_relative_path,
            progress_callback=lambda event: self._emit_upload_progress(
                task_id=task_id,
                local_path=local_path,
                remote_relative_path=remote_relative_path,
                event=event,
            ),
        )

    def _emit_upload_progress(
        self,
        *,
        task_id: int,
        local_path: Path,
        remote_relative_path: str,
        event: dict[str, object],
    ) -> None:
        """输出上传阶段级调试日志。"""

        payload = {
            "event": "upload_task_progress",
            "run_id": self._config.run_id,
            "worker_id": self._config.worker_id,
            "task_id": task_id,
            "local_path": str(local_path),
            "remote_relative_path": remote_relative_path,
            **event,
        }
        print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="独立百度上传 worker。")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--state-db-path", type=Path, required=True)
    parser.add_argument("--baidu-token-file", type=Path, required=True)
    parser.add_argument("--archive-remote-root", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--worker-id")
    parser.add_argument(
        "--delete-local-file-after-upload",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    worker = UploadWorker(
        UploadWorkerConfig(
            run_id=args.run_id,
            state_db_path=args.state_db_path,
            baidu_token_file=args.baidu_token_file,
            archive_remote_root=args.archive_remote_root,
            worker_id=args.worker_id or f"upload-worker-{uuid.uuid4().hex[:8]}",
            output_root=args.output_root,
            delete_local_file_after_upload=args.delete_local_file_after_upload,
        )
    )
    worker.serve()
    return 0


def _next_retry_at(
    *,
    base_time: datetime,
    attempt_count: int,
    backoff_seconds: tuple[int, ...],
) -> str:
    index = min(max(attempt_count - 1, 0), len(backoff_seconds) - 1)
    return (base_time + timedelta(seconds=backoff_seconds[index])).isoformat()


def _require_str(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串。")
    return value


def _now() -> str:
    return datetime.now().astimezone().isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
