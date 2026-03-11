"""control plane服务测试。"""

from __future__ import annotations

from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.control_plane.models import PipelineBootstrapRequest
from rift_audio_pipeline.control_plane.models import RunHeartbeatRequest
from rift_audio_pipeline.control_plane.models import RunLogEventRequest
from rift_audio_pipeline.control_plane.models import RunLogFinalizeRequest
from rift_audio_pipeline.control_plane.models import RunReportRequest
from rift_audio_pipeline.control_plane.service import ControlPlaneService


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append((method, path, payload))
        if path == "/api/pipeline/bootstrap":
            return {
                "current_version": "16.4",
                "previous_version": "16.3",
                "current_pair": {
                    "version": "16.4",
                    "lcu_manifest_url": "https://lcu.example/16.4",
                    "game_manifest_url": "https://game.example/16.4",
                },
                "previous_pair": {
                    "version": "16.3",
                    "lcu_manifest_url": "https://lcu.example/16.3",
                    "game_manifest_url": "https://game.example/16.3",
                },
                "decision_source": "worker_latest_version",
                "manifest_snapshot_url": "https://r2.example/manifests/16.4/pair.json",
            }
        return {
            "accepted": True,
            "persisted_at": "2026-03-08T12:00:00+08:00",
            "next_head_version": "16.4",
        }


def test_get_pipeline_bootstrap_should_parse_response() -> None:
    """应把 bootstrap 响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.get_pipeline_bootstrap(
        PipelineBootstrapRequest(
            game_region="zh_CN",
            mode=PipelineMode.REMOTE,
            requested_by="github-actions",
        )
    )

    assert response.current_version == "16.4"
    assert response.previous_version == "16.3"
    assert response.current_pair.version == "16.4"
    assert response.previous_pair is not None
    assert response.previous_pair.version == "16.3"


def test_report_pipeline_run_result_should_parse_response() -> None:
    """应把 run report 响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.report_pipeline_run_result(
        RunReportRequest(
            run_id="run-1",
            from_version="16.3",
            to_version="16.4",
            status=PipelineRunStatus.SUCCESS,
            summary={"uploaded_archives": 1},
        )
    )

    assert response.accepted is True
    assert response.next_head_version == "16.4"


def test_report_pipeline_run_heartbeat_should_parse_response() -> None:
    """应把 heartbeat 响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.report_pipeline_run_heartbeat(
        RunHeartbeatRequest(
            run_id="run-1",
            status="running",
            last_log_at="2026-03-08T12:00:00+08:00",
            progress={"stage": "extract"},
        )
    )

    assert response.accepted is True
    assert response.persisted_at == "2026-03-08T12:00:00+08:00"


def test_report_pipeline_run_log_event_should_parse_response() -> None:
    """应把实时日志响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.report_pipeline_run_log_event(
        RunLogEventRequest(
            run_id="run-1",
            event={"seq": 1, "event_type": "run_started", "message": "started"},
        )
    )

    assert response.accepted is True
    assert response.persisted_at == "2026-03-08T12:00:00+08:00"
    assert response.next_expected_seq is None


def test_finalize_pipeline_run_logs_should_parse_response() -> None:
    """应把终态日志摘要响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.finalize_pipeline_run_logs(
        RunLogFinalizeRequest(
            run_id="run-1",
            summary={"final_status": "success", "last_seq": 3},
        )
    )

    assert response.accepted is True
    assert response.persisted_at == "2026-03-08T12:00:00+08:00"
