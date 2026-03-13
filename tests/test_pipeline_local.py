"""Pipeline local 适配层测试。"""

from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

from rift_audio_pipeline.pipeline.local import build_local_app_context
from rift_audio_pipeline.pipeline.local import run_local_pipeline
from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig


def _build_local_config(tmp_path: Path) -> PipelineRunConfig:
    """构造 local 测试配置。"""

    return PipelineRunConfig(
        mode=PipelineMode.LOCAL,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        game_path=tmp_path / "League of Legends",
        champion_ids=(1,),
        map_ids=(11,),
        run_mapping=True,
    )


def test_build_local_app_context_should_require_game_path(tmp_path: Path) -> None:
    """未提供 game_path 时应拒绝构造 local 上下文。"""

    config = PipelineRunConfig(
        mode=PipelineMode.LOCAL,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        game_path=None,
    )

    with pytest.raises(ValueError, match="game_path"):
        build_local_app_context(config)


def test_run_local_pipeline_should_collect_scanned_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """local 流程应在执行后回填本地产物。"""

    config = _build_local_config(tmp_path)
    config.game_path.mkdir(parents=True, exist_ok=True)
    output_root = config.output_root

    class _FakeApp:
        def __init__(self, ctx: object) -> None:
            self.ctx = ctx

        def update(self, opts: object, target: str = "all") -> None:
            del opts, target
            (output_root / "manifest").mkdir(parents=True, exist_ok=True)
            (output_root / "manifest" / "version.txt").write_text("16.5", encoding="utf-8")

        def extract(self, opts: object, *, include_champions: bool, include_maps: bool) -> None:
            del opts, include_champions, include_maps
            champion_dir = output_root / "audios" / "16.5" / "1·annie" / "vo"
            champion_dir.mkdir(parents=True, exist_ok=True)
            (champion_dir / "line.wem").write_text("voice", encoding="utf-8")

            map_dir = output_root / "audios" / "16.5" / "sfx" / "11·map11"
            map_dir.mkdir(parents=True, exist_ok=True)
            (map_dir / "ambient.wem").write_text("map", encoding="utf-8")

        def mapping(self, opts: object, *, include_champions: bool, include_maps: bool) -> None:
            del opts, include_champions, include_maps
            champion_file = output_root / "hashes" / "16.5" / "champions" / "1.json"
            champion_file.parent.mkdir(parents=True, exist_ok=True)
            champion_file.write_text("{}", encoding="utf-8")

            map_file = output_root / "hashes" / "16.5" / "maps" / "11.json"
            map_file.parent.mkdir(parents=True, exist_ok=True)
            map_file.write_text("{}", encoding="utf-8")

    fake_module = types.SimpleNamespace(
        setup_app=lambda **kwargs: types.SimpleNamespace(config=types.SimpleNamespace(**kwargs)),
        LolAudioUnpackApp=_FakeApp,
        OperationOptions=lambda **kwargs: types.SimpleNamespace(**kwargs),
    )
    monkeypatch.setitem(sys.modules, "lol_audio_unpack", fake_module)

    log_ctx = initialize_run_logging(config)
    artifacts = run_local_pipeline(config, log_ctx)

    assert [(artifact.entity_type, artifact.entity_id) for artifact in artifacts] == [
        ("champion", 1),
        ("map", 11),
    ]
    assert artifacts[0].audio_output_paths == (output_root / "audios" / "16.5" / "1·annie",)
    assert (
        artifacts[0].mapping_output_path == output_root / "hashes" / "16.5" / "champions" / "1.json"
    )
    assert artifacts[1].audio_output_paths == (
        output_root / "audios" / "16.5" / "sfx" / "11·map11",
    )
    assert artifacts[1].mapping_output_path == output_root / "hashes" / "16.5" / "maps" / "11.json"
