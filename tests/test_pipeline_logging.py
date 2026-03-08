"""Pipeline 日志模块测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.logging import enqueue_pending_log_upload
from rift_audio_pipeline.pipeline.logging import finalize_run_logging
from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.logging import record_error_snapshot
from rift_audio_pipeline.pipeline.logging import upload_run_logs
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.models import PipelineStage


def _build_config(tmp_path: Path) -> PipelineRunConfig:
    """构造测试用运行配置。"""

    return PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
    )


def test_initialize_and_finalize_run_logging_should_write_summary_files(tmp_path: Path) -> None:
    """应创建日志目录并写入摘要文件。"""

    config = _build_config(tmp_path)
    log_ctx = initialize_run_logging(config)
    event = PipelineEvent(
        run_id=log_ctx.run_id,
        stage=PipelineStage.INIT,
        event_type="run_started",
        message="开始运行",
        payload={"mode": "remote"},
        created_at="2026-03-08T12:00:00+08:00",
    )

    emit_event(log_ctx, event)
    record_error_snapshot(log_ctx, PipelineStage.UPLOAD, RuntimeError("上传失败"))
    summary = PipelineRunSummary(
        run_id=log_ctx.run_id,
        mode=PipelineMode.REMOTE,
        version="16.5",
        status=PipelineRunStatus.PARTIAL_SUCCESS,
        processed_targets=2,
        succeeded_targets=1,
        failed_targets=1,
        uploaded_archives=1,
        pending_manifest_sync_entries=1,
        pending_log_upload_entries=0,
        log_dir=log_ctx.log_dir,
    )
    finalize_run_logging(
        log_ctx,
        summary,
        decision_payload={"targets": 2},
        artifacts_payload={"archives": ["annie.7z"]},
    )

    assert log_ctx.events_file.exists()
    assert log_ctx.error_file.exists()
    assert log_ctx.run_file.exists()
    run_payload = json.loads(log_ctx.run_file.read_text(encoding="utf-8"))
    assert run_payload["status"] == "partial_success"
    assert run_payload["schema_version"] == 1
    assert json.loads(log_ctx.decision_file.read_text(encoding="utf-8")) == {"targets": 2}
    assert "run_started" in log_ctx.events_file.read_text(encoding="utf-8")
    error_payload = json.loads(log_ctx.error_file.read_text(encoding="utf-8"))
    assert error_payload["schema_version"] == 1
    assert error_payload["stage"] == "upload"


def test_enqueue_pending_log_upload_should_append_queue_entry(tmp_path: Path) -> None:
    """日志上传失败时应追加待补偿任务。"""

    config = _build_config(tmp_path)
    log_dir = tmp_path / "output" / "logs" / "2026-03-08" / "run-1"
    log_dir.mkdir(parents=True, exist_ok=True)

    enqueue_pending_log_upload(config, log_dir, error_message="network timeout")
    enqueue_pending_log_upload(config, log_dir, error_message="network timeout again")

    queue_file = tmp_path / "output" / "state" / "pending_log_upload_queue.json"
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(payload) == 2
    assert payload[0]["error_message"] == "network timeout"
    assert payload[1]["log_dir"] == str(log_dir.resolve())
    assert payload[0]["schema_version"] == 1


def test_upload_run_logs_should_create_remote_dirs_and_upload_files(tmp_path: Path) -> None:
    """上传日志时应逐文件创建目录并调用客户端上传。"""

    class _FakeClient:
        def __init__(self) -> None:
            self.remote_dirs: set[str] = set()
            self.upload_calls: list[tuple[Path, str]] = []

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            if remote_path in self.remote_dirs:
                return {"path": remote_path, "isdir": 1}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            self.remote_dirs.add(dir_path)
            return {"path": dir_path, "isdir": 1}

        def upload_file(self, local_path: Path, remote_path: str) -> dict[str, object]:
            self.upload_calls.append((local_path, remote_path))
            return {"path": remote_path, "errno": 0}

    config = _build_config(tmp_path)
    log_ctx = initialize_run_logging(config)
    (log_ctx.log_dir / "nested").mkdir(parents=True, exist_ok=True)
    (log_ctx.log_dir / "pipeline.log").write_text("hello", encoding="utf-8")
    (log_ctx.log_dir / "nested" / "events.jsonl").write_text("{}", encoding="utf-8")
    fake_client = _FakeClient()

    upload_run_logs(log_ctx, config, fake_client)  # type: ignore[arg-type]

    remote_paths = [item[1] for item in fake_client.upload_calls]
    assert any(path.endswith("/pipeline.log") for path in remote_paths)
    assert any(path.endswith("/nested/events.jsonl") for path in remote_paths)
