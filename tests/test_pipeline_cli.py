"""Pipeline CLI 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from rift_audio_pipeline.pipeline import cli
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunSummary


def test_build_run_config_should_parse_cli_args(tmp_path: Path) -> None:
    """CLI 参数应被正确转换为运行配置。"""

    args = cli.build_parser().parse_args(
        [
            "--mode",
            "remote",
            "--output-root",
            str(tmp_path / "output"),
            "--temp-root",
            str(tmp_path / "temp"),
            "--baidu-remote-root",
            "/apps/demo",
            "--remote-live-region",
            "NA1",
            "--current-version",
            "16.5",
            "--current-lcu-manifest-url",
            "https://lcu.example/16.5",
            "--current-game-manifest-url",
            "https://game.example/16.5",
            "--champion-ids",
            "1,103",
            "--map-ids",
            "11",
            "--run-mapping",
            "--integrate-data",
            "--max-workers",
            "8",
            "--archive-password",
            "zip-secret",
        ]
    )

    config = cli.build_run_config(args)

    assert config.mode is PipelineMode.REMOTE
    assert config.output_root == tmp_path / "output"
    assert config.temp_root == tmp_path / "temp"
    assert config.log_root == tmp_path / "output" / "logs"
    assert config.remote_live_region == "NA1"
    assert config.current_version == "16.5"
    assert config.current_lcu_manifest_url == "https://lcu.example/16.5"
    assert config.current_game_manifest_url == "https://game.example/16.5"
    assert config.champion_ids == (1, 103)
    assert config.map_ids == (11,)
    assert config.run_mapping is True
    assert config.integrate_data is True
    assert config.max_workers == 8
    assert config.archive_password == "zip-secret"


def test_main_should_run_pipeline_and_print_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """CLI 主入口应调用 orchestrator 并输出摘要 JSON。"""

    captured_config: list[object] = []
    monkeypatch.setattr(
        cli,
        "run_pipeline",
        lambda config: (
            captured_config.append(config)
            or PipelineRunSummary(
                run_id="run-1",
                mode=config.mode,
                version="16.5",
                status=PipelineRunStatus.SUCCESS,
                processed_targets=1,
                succeeded_targets=1,
                failed_targets=0,
                uploaded_archives=1,
                pending_manifest_sync_entries=0,
                pending_log_upload_entries=0,
                log_dir=tmp_path / "output" / "logs" / "run-1",
            )
        ),
    )

    exit_code = cli.main(
        [
            "--mode",
            "remote",
            "--output-root",
            str(tmp_path / "output"),
            "--temp-root",
            str(tmp_path / "temp"),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0
    assert len(captured_config) == 1
    assert '"status": "success"' in stdout
