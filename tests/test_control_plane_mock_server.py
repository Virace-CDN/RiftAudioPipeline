"""Mock control plane server 联调测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_localdev.plane.mock_server import MockControlPlaneConfig
from rift_localdev.plane.mock_server import MockControlPlaneServer
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.models import RunBootstrapRequest
from rift_audio_pipeline.control_plane.models import RunHeartbeatRequest
from rift_audio_pipeline.control_plane.models import RunLogEventRequest
from rift_audio_pipeline.control_plane.models import RunLogFinalizeRequest
from rift_audio_pipeline.control_plane.models import RunReportRequest
from rift_audio_pipeline.control_plane.service import ControlPlaneService
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


def test_mock_control_plane_server_should_round_trip_http(tmp_path: Path) -> None:
    """mock server 应能通过真实 HTTP 完成 bootstrap 启动通知、heartbeat、logs 与 report。"""

    fixture_dir = Path(__file__).parent / "fixtures" / "mock_control_plane"
    storage_root = tmp_path / "received"
    server = MockControlPlaneServer(
        MockControlPlaneConfig(
            fixture_dir=fixture_dir,
            storage_root=storage_root,
            host="127.0.0.1",
            port=0,
        )
    )
    server.start()
    try:
        service = ControlPlaneService(
            ControlPlaneClient(
                ControlPlaneConfig(
                    base_url=server.base_url,
                    bearer_token="mock-worker-token",
                    access_client_id="mock-client-id",
                    access_client_secret="mock-client-secret",
                )
            )
        )

        bootstrap = service.notify_pipeline_run_started(
            RunBootstrapRequest(
                run_id="run-mock-1",
                started_at="2026-03-09T09:59:59+08:00",
            )
        )
        heartbeat = service.report_pipeline_run_heartbeat(
            RunHeartbeatRequest(
                run_id="run-mock-1",
                status="running",
                last_log_at="2026-03-09T10:00:00+08:00",
                progress={"stage": "extract", "processed_targets": 2},
            )
        )
        log_event = service.report_pipeline_run_log_event(
            RunLogEventRequest(
                run_id="run-mock-1",
                event={
                    "seq": 1,
                    "stage": "init",
                    "event_type": "run_started",
                    "message": "pipeline 开始运行",
                },
            )
        )
        log_finalize = service.finalize_pipeline_run_logs(
            RunLogFinalizeRequest(
                run_id="run-mock-1",
                summary={
                    "final_status": "success",
                    "final_stage": "finalize",
                    "last_seq": 1,
                },
            )
        )
        report = service.report_pipeline_run_result(
            RunReportRequest(
                run_id="run-mock-1",
                status=PipelineRunStatus.SUCCESS,
                changes=(
                    {
                        "remote_path": "/apps/rift-audio-pipeline/VO/champions/demo.7z",
                        "file_name": "demo.7z",
                    },
                ),
                finished_at="2026-03-09T10:20:00+08:00",
            )
        )
    finally:
        server.close()

    assert bootstrap is None
    assert heartbeat is None
    assert log_event is None
    assert log_finalize is None
    assert report is None

    bootstrap_payload = _read_json(storage_root / "bootstrap_requests" / "0001.json")
    heartbeat_payload = _read_json(storage_root / "runs" / "run-mock-1" / "heartbeats" / "0001.json")
    log_payload = _read_json(storage_root / "runs" / "run-mock-1" / "logs" / "0001.json")
    log_finalize_payload = _read_json(storage_root / "runs" / "run-mock-1" / "logs_finalize.json")
    report_payload = _read_json(storage_root / "runs" / "run-mock-1" / "report.json")
    run_state_payload = _read_json(storage_root / "runs" / "run-mock-1" / "run_state.json")

    assert bootstrap_payload["payload"]["run_id"] == "run-mock-1"
    assert heartbeat_payload["payload"]["progress"]["stage"] == "extract"
    assert log_payload["payload"]["event"]["seq"] == 1
    assert log_finalize_payload["payload"]["summary"]["final_status"] == "success"
    assert report_payload["payload"]["status"] == "success"
    assert report_payload["payload"]["changes"][0]["file_name"] == "demo.7z"
    assert run_state_payload["status"] == "success"
    assert run_state_payload["source"] == "report"


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))
