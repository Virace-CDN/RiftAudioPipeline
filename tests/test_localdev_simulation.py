"""本地 simulation 补丁测试。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import rift_audio_pipeline.pipeline.orchestrator as orchestrator
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_localdev.simulation import BAIDU_FAILURE_MODE_ENV_VAR
from rift_localdev.simulation import MOCK_BAIDU_ENV_VAR
from rift_localdev.simulation import patch_pipeline_for_baidu_mock


def test_patch_pipeline_for_baidu_mock_should_preserve_manifest_pair_resolution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """百度 mock 模式不应覆盖真实 manifest pair 解析。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/rift-audio-pipeline-data",
        meta_remote_root="/apps/rift-audio-pipeline-meta",
    )
    expected_pair = ManifestPairRef(
        version="16.5",
        lcu_manifest_url="https://real.example/lcu.manifest",
        game_manifest_url="https://real.example/game.manifest",
        match_mode="external_current_pair",
        match_reason="pytest",
    )

    monkeypatch.setattr(
        orchestrator,
        "resolve_remote_manifest_pair",
        lambda current_config: expected_pair if current_config is config else None,
    )

    with patch_pipeline_for_baidu_mock(config, failure_mode="none"):
        assert orchestrator.resolve_remote_manifest_pair(config) == expected_pair
        assert os.environ[MOCK_BAIDU_ENV_VAR] == "1"
        assert os.environ[BAIDU_FAILURE_MODE_ENV_VAR] == "none"
