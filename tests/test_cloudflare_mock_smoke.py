"""本地 mock smoke runner 测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_audio_pipeline.cloudflare.mock_smoke import MockSmokeConfig
from rift_audio_pipeline.cloudflare.mock_smoke import run_mock_control_plane_smoke
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


def test_run_mock_control_plane_smoke_should_complete_pipeline_flow(tmp_path: Path) -> None:
    """smoke runner 应跑通 bootstrap、heartbeat、report 与本地假上传。"""

    fixture_dir = Path(__file__).parent / "fixtures" / "mock_control_plane"
    result = run_mock_control_plane_smoke(
        MockSmokeConfig(
            fixture_dir=fixture_dir,
            output_root=tmp_path / "output",
            temp_root=tmp_path / "temp",
            storage_root=tmp_path / "received",
            requested_by="pytest-smoke",
            champion_ids=(1, 103),
        )
    )

    assert result.summary.status is PipelineRunStatus.SUCCESS
    assert result.summary.uploaded_archives == 2
    assert result.summary.processed_targets == 2

    bootstrap_payload = _read_json(result.received_root / "bootstrap_requests" / "0001.json")
    heartbeat_1 = _read_json(result.received_root / "runs" / result.summary.run_id / "heartbeats" / "0001.json")
    heartbeat_2 = _read_json(result.received_root / "runs" / result.summary.run_id / "heartbeats" / "0002.json")
    report_payload = _read_json(result.received_root / "runs" / result.summary.run_id / "report.json")
    archive_receipt = _read_json(result.archive_upload_receipt)
    log_receipt = _read_json(result.log_upload_receipt)
    run_summary = _read_json(result.summary.log_dir / "run.json")

    assert bootstrap_payload["payload"]["requested_by"] == "pytest-smoke"
    assert bootstrap_payload["payload"]["champion_ids"] == [1, 103]
    assert heartbeat_1["payload"]["progress"]["stage"] == "init"
    assert heartbeat_2["payload"]["progress"]["stage"] == "finalize"
    assert report_payload["payload"]["status"] == "success"
    assert report_payload["payload"]["uploaded_archives"] == 2
    assert archive_receipt["version"] == "16.5"
    assert len(archive_receipt["archives"]) == 2
    assert log_receipt["run_id"] == result.summary.run_id
    assert "run.json" in log_receipt["files"]
    assert run_summary["status"] == "success"


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))
