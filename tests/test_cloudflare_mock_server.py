"""Mock control plane server 联调测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_audio_pipeline.cloudflare.client import CloudflareWorkerClient
from rift_audio_pipeline.cloudflare.mock_server import MockControlPlaneConfig
from rift_audio_pipeline.cloudflare.mock_server import MockControlPlaneServer
from rift_audio_pipeline.cloudflare.models import CloudflareControlConfig
from rift_audio_pipeline.cloudflare.models import PipelineBootstrapRequest
from rift_audio_pipeline.cloudflare.models import RunHeartbeatRequest
from rift_audio_pipeline.cloudflare.models import RunReportRequest
from rift_audio_pipeline.cloudflare.service import CloudflareControlService
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


def test_mock_control_plane_server_should_round_trip_http(tmp_path: Path) -> None:
    """mock server 应能通过真实 HTTP 完成 bootstrap、heartbeat 与 report。"""

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
        service = CloudflareControlService(
            CloudflareWorkerClient(
                CloudflareControlConfig(
                    base_url=server.base_url,
                    bearer_token="mock-worker-token",
                    access_client_id="mock-client-id",
                    access_client_secret="mock-client-secret",
                )
            )
        )

        bootstrap = service.get_pipeline_bootstrap(
            PipelineBootstrapRequest(
                game_region="zh_CN",
                mode=PipelineMode.REMOTE,
                requested_by="pytest",
                champion_ids=(1, 103),
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
        report = service.report_pipeline_run_result(
            RunReportRequest(
                run_id="run-mock-1",
                from_version="16.4",
                to_version="16.5",
                status=PipelineRunStatus.SUCCESS,
                summary={"uploaded_archives": 2, "failed_targets": 0},
                uploaded_archives=2,
                baidu_log_path="/apps/rift-audio-pipeline/logs/2026-03-09/run-mock-1",
            )
        )
    finally:
        server.close()

    assert bootstrap.current_version == "16.5"
    assert bootstrap.previous_pair is not None
    assert bootstrap.previous_pair.version == "16.4"
    assert bootstrap.baidu_access_grant is not None
    assert bootstrap.baidu_access_grant.refresh_token == "mock-baidu-refresh-token"
    assert heartbeat.accepted is True
    assert report.accepted is True
    assert report.next_head_version == "16.5"

    bootstrap_payload = _read_json(storage_root / "bootstrap_requests" / "0001.json")
    heartbeat_payload = _read_json(storage_root / "runs" / "run-mock-1" / "heartbeats" / "0001.json")
    report_payload = _read_json(storage_root / "runs" / "run-mock-1" / "report.json")

    assert bootstrap_payload["payload"]["requested_by"] == "pytest"
    assert bootstrap_payload["payload"]["champion_ids"] == [1, 103]
    assert heartbeat_payload["payload"]["progress"]["stage"] == "extract"
    assert report_payload["payload"]["status"] == "success"
    assert report_payload["response"]["next_head_version"] == "16.5"


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))
