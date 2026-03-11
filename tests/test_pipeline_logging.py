"""Pipeline 日志模块测试。"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

import rift_audio_pipeline.pipeline.logging as pipeline_logging
from tests._control_plane_capture import ControlPlaneCaptureServer
from rift_audio_pipeline.pipeline.logging import build_log_sink_config
from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.logging import enqueue_pending_log_upload
from rift_audio_pipeline.pipeline.logging import finalize_log_relay_delivery
from rift_audio_pipeline.pipeline.logging import finalize_run_logging
from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.logging import LogRelayClient
from rift_audio_pipeline.pipeline.logging import RelaySpoolPump
from rift_audio_pipeline.pipeline.logging import LogSinkConfig
from rift_audio_pipeline.pipeline.logging import record_error_snapshot
from rift_audio_pipeline.pipeline.logging import upload_run_logs
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineLogTerminalSummary
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
    try:
        raise RuntimeError("上传失败")
    except RuntimeError as error:
        record_error_snapshot(log_ctx, PipelineStage.UPLOAD, error, payload={"operation": "upload"})
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
    event_payload = json.loads(log_ctx.events_file.read_text(encoding="utf-8").splitlines()[0])
    assert run_payload["status"] == "partial_success"
    assert run_payload["schema_version"] == 1
    assert json.loads(log_ctx.decision_file.read_text(encoding="utf-8")) == {"targets": 2}
    assert event_payload["event_type"] == "run_started"
    assert event_payload["seq"] == 1
    assert event_payload["thread_name"] == "MainThread"
    assert event_payload["process_id"] > 0
    assert event_payload["code_file"].endswith("tests/test_pipeline_logging.py")
    assert (
        event_payload["code_function"]
        == "test_initialize_and_finalize_run_logging_should_write_summary_files"
    )
    error_payload = json.loads(log_ctx.error_file.read_text(encoding="utf-8"))
    assert error_payload["schema_version"] == 1
    assert error_payload["stage"] == "upload"
    assert error_payload["operation"] == "upload"
    assert error_payload["traceback"] is not None
    assert "RuntimeError: 上传失败" in error_payload["traceback"]
    assert error_payload["code_file"].endswith("tests/test_pipeline_logging.py")
    assert (
        error_payload["code_function"]
        == "test_initialize_and_finalize_run_logging_should_write_summary_files"
    )


def test_emit_event_should_assign_monotonic_sequence(tmp_path: Path) -> None:
    """应为同一 run 的事件分配单调递增序号。"""

    config = _build_config(tmp_path)
    log_ctx = initialize_run_logging(config)

    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.INIT,
            event_type="first",
            message="第一条事件",
            payload={},
            created_at="2026-03-08T12:00:00+08:00",
        ),
    )
    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.EXTRACT,
            event_type="second",
            message="第二条事件",
            payload={},
            created_at="2026-03-08T12:00:01+08:00",
            level="WARNING",
            entity_type="champion",
            entity_id=266,
        ),
    )

    payload = [
        json.loads(line)
        for line in log_ctx.events_file.read_text(encoding="utf-8").splitlines()
    ]
    assert [item["seq"] for item in payload] == [1, 2]
    assert payload[1]["level"] == "WARNING"
    assert payload[1]["entity_type"] == "champion"
    assert payload[1]["entity_id"] == 266
    assert log_ctx.last_event_seq == 2
    assert log_ctx.next_event_seq == 3


def test_relay_spool_pump_should_forward_events_and_terminal_summary(tmp_path: Path) -> None:
    """RelaySpoolPump 应在 drain 后把事件与终态摘要发给控制面。"""

    config = _build_config(tmp_path)
    log_ctx = initialize_run_logging(config)
    sent_events: list[dict[str, object]] = []
    sent_terminal_summaries: list[dict[str, object]] = []
    pump = RelaySpoolPump(
        run_id=log_ctx.run_id,
        state_file=log_ctx.log_relay_state_file,
        config=LogSinkConfig(
            enabled=True,
            control_plane_base_url="http://127.0.0.1:8788",
            spool_dir=log_ctx.spool_dir,
            flush_interval_ms=10,
            retry_backoff_ms=(10,),
        ),
        send_event=lambda payload: sent_events.append(dict(payload)),
        send_terminal_summary=lambda payload: sent_terminal_summaries.append(dict(payload)),
    )
    log_ctx.log_delivery_sink = pump
    pump.start()

    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.INIT,
            event_type="run_started",
            message="开始运行",
            payload={},
            created_at="2026-03-08T12:00:00+08:00",
        ),
    )
    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.EXTRACT,
            event_type="entity_complete",
            message="单实体完成",
            payload={},
            created_at="2026-03-08T12:00:01+08:00",
        ),
    )
    finalize_log_relay_delivery(
        log_ctx,
        PipelineLogTerminalSummary(
            run_id=log_ctx.run_id,
            finished_at="2026-03-08T12:00:02+08:00",
            final_status="success",
            final_stage="finalize",
            last_seq=log_ctx.last_event_seq,
            processed_targets=1,
            succeeded_targets=1,
            failed_targets=0,
            uploaded_archives=0,
            raw_log_bundle_ready=True,
            raw_log_local_dir=str(log_ctx.log_dir),
            raw_log_remote_path=None,
            summary={"status": "success"},
        ),
    )

    state_payload = json.loads(log_ctx.log_relay_state_file.read_text(encoding="utf-8"))
    assert [payload["seq"] for payload in sent_events] == [1, 2]
    assert sent_terminal_summaries[0]["last_seq"] == 2
    assert state_payload["terminal_sent"] is True
    assert state_payload["last_sent_seq"] == 2


def test_relay_spool_pump_should_replay_spooled_events_on_start(tmp_path: Path) -> None:
    """RelaySpoolPump 重启后应从 spool 目录恢复未发送事件。"""

    config = _build_config(tmp_path)
    log_ctx = initialize_run_logging(config)
    sent_events: list[dict[str, object]] = []
    pump = RelaySpoolPump(
        run_id=log_ctx.run_id,
        state_file=log_ctx.log_relay_state_file,
        config=LogSinkConfig(
            enabled=True,
            control_plane_base_url="http://127.0.0.1:8788",
            spool_dir=log_ctx.spool_dir,
            flush_interval_ms=10,
            retry_backoff_ms=(10,),
        ),
        send_event=lambda payload: sent_events.append(dict(payload)),
        send_terminal_summary=lambda payload: None,
    )
    event_spool_file = log_ctx.spool_dir / "events" / "00000001.json"
    event_spool_file.parent.mkdir(parents=True, exist_ok=True)
    event_spool_file.write_text(
        json.dumps(
            {
                "run_id": log_ctx.run_id,
                "seq": 1,
                "stage": "init",
                "event_type": "spooled",
                "message": "来自 spool 的事件",
                "created_at": "2026-03-08T12:00:00+08:00",
                "payload": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    pump.start()
    pump.close()

    state_payload = json.loads(log_ctx.log_relay_state_file.read_text(encoding="utf-8"))
    assert [payload["seq"] for payload in sent_events] == [1]
    assert state_payload["pending_spool_events"] == 0
    assert not event_spool_file.exists()


def test_log_relay_client_should_forward_events_and_terminal_summary(tmp_path: Path) -> None:
    """LogRelayClient 应通过独立 relay 进程把事件和终态摘要送到控制面。"""

    server = ControlPlaneCaptureServer(
        bootstrap_payload={
            "current_version": "16.5",
            "current_pair": {
                "version": "16.5",
                "lcu_manifest_url": "https://lcu.example/16.5",
                "game_manifest_url": "https://game.example/16.5",
            },
        }
    )
    server.start()
    try:
        config = _build_config(tmp_path)
        log_ctx = initialize_run_logging(config)
        relay = LogRelayClient(
            run_id=log_ctx.run_id,
            relay_state_file=log_ctx.log_relay_state_file,
            relay_config_file=log_ctx.relay_config_file,
            relay_stdout_file=log_ctx.relay_stdout_file,
            relay_socket_file=log_ctx.relay_socket_file,
            config=LogSinkConfig(
                enabled=True,
                control_plane_base_url=server.base_url,
                spool_dir=log_ctx.spool_dir,
                flush_interval_ms=10,
                retry_backoff_ms=(10,),
                timeout_seconds=1.0,
            ),
        )
        log_ctx.log_delivery_sink = relay
        relay.start()

        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.INIT,
                event_type="run_started",
                message="开始运行",
                payload={},
                created_at="2026-03-08T12:00:00+08:00",
            ),
        )
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.EXTRACT,
                event_type="entity_complete",
                message="单实体完成",
                payload={},
                created_at="2026-03-08T12:00:01+08:00",
            ),
        )
        finalize_log_relay_delivery(
            log_ctx,
            PipelineLogTerminalSummary(
                run_id=log_ctx.run_id,
                finished_at="2026-03-08T12:00:02+08:00",
                final_status="success",
                final_stage="finalize",
                last_seq=log_ctx.last_event_seq,
                processed_targets=1,
                succeeded_targets=1,
                failed_targets=0,
                uploaded_archives=0,
                raw_log_bundle_ready=True,
                raw_log_local_dir=str(log_ctx.log_dir),
                raw_log_remote_path=None,
                summary={"status": "success"},
            ),
        )

        state_payload = json.loads(log_ctx.log_relay_state_file.read_text(encoding="utf-8"))
        assert [payload["event"]["seq"] for payload in server.events] == [1, 2]
        assert server.terminal_summaries[0]["summary"]["last_seq"] == 2
        assert state_payload["terminal_sent"] is True
        assert state_payload["last_sent_seq"] == 2
    finally:
        server.close()


def test_build_log_sink_config_should_disable_relay_for_local_mode(tmp_path: Path) -> None:
    """LOCAL 模式即使给了 control plane URL，也不应启用 relay。"""

    config = PipelineRunConfig(
        mode=PipelineMode.LOCAL,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        control_plane_base_url="http://127.0.0.1:8788",
    )
    log_ctx = initialize_run_logging(config)

    sink_config = build_log_sink_config(config, log_ctx)

    assert sink_config.enabled is False


def test_build_log_sink_config_should_disable_relay_on_windows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows 直接执行时应完全依赖本地 RAW，不启用 relay。"""

    config = replace(_build_config(tmp_path), control_plane_base_url="http://127.0.0.1:8788")
    log_ctx = initialize_run_logging(config)
    monkeypatch.setattr(pipeline_logging.sys, "platform", "win32")

    sink_config = build_log_sink_config(config, log_ctx)

    assert sink_config.enabled is False


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
