"""control plane服务测试。"""

from __future__ import annotations

from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.control_plane.models import RunBootstrapRequest
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
                "accepted": True,
                "persisted_at": "2026-03-08T12:00:00+08:00",
            }
        return {
            "accepted": True,
            "persisted_at": "2026-03-08T12:00:00+08:00",
        }


def test_notify_pipeline_run_started_should_parse_response() -> None:
    """应把 bootstrap 启动通知响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.notify_pipeline_run_started(
        RunBootstrapRequest(
            run_id="run-1",
            started_at="2026-03-08T12:00:00+08:00",
        )
    )

    assert response.accepted is True
    assert response.persisted_at == "2026-03-08T12:00:00+08:00"


def test_report_pipeline_run_result_should_parse_response() -> None:
    """应把 run report 响应解析为强类型对象。"""

    service = ControlPlaneService(_FakeClient())

    response = service.report_pipeline_run_result(
        RunReportRequest(
            run_id="run-1",
            status=PipelineRunStatus.SUCCESS,
            changes=(
                {
                    "remote_path": "/apps/test/VO/champions/demo.7z",
                    "file_name": "demo.7z",
                },
            ),
            finished_at="2026-03-08T12:10:00+08:00",
        )
    )

    assert response.accepted is True
    assert response.persisted_at == "2026-03-08T12:00:00+08:00"


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
