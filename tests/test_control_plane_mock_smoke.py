"""本地 mock smoke runner 测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_localdev.plane.mock_smoke import MockSmokeConfig
from rift_localdev.plane.mock_smoke import run_mock_control_plane_smoke
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


def test_run_mock_control_plane_smoke_should_complete_pipeline_flow(tmp_path: Path) -> None:
    """legacy smoke runner 应至少跑通本地主线与假 archive 上传。"""

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

    archive_receipt = _read_json(result.archive_upload_receipt)
    run_summary = _read_json(result.summary.log_dir / "run.json")

    assert archive_receipt["version"] == "16.5"
    assert len(archive_receipt["archives"]) == 2
    assert run_summary["status"] == "success"


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))
