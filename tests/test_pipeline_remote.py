"""Pipeline remote 适配层测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.remote import build_remote_app_context
from rift_audio_pipeline.pipeline.remote import build_remote_operation_options
from rift_audio_pipeline.pipeline.remote import convert_remote_payload
from rift_audio_pipeline.pipeline.remote import resolve_remote_manifest_pair
from rift_audio_pipeline.pipeline.remote import run_remote_pipeline


def _build_config(tmp_path: Path) -> PipelineRunConfig:
    """构造测试用 pipeline 配置。"""

    return PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        remote_live_region="EUW",
        champion_ids=(1, 103),
        include_maps=False,
        wwiser_path=tmp_path / "wwiser.pyz",
        run_mapping=True,
        integrate_data=True,
    )


def test_resolve_remote_manifest_pair_should_use_live_region(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应使用 live 区服解析 manifest pair。"""

    class _FakeResolver:
        def resolve_manifest_pair(self, region: str) -> object:
            assert region == "EUW"
            return SimpleNamespace(
                version="16.5",
                lcu=SimpleNamespace(url="https://lcu.example"),
                game=SimpleNamespace(url="https://game.example"),
                match_mode=SimpleNamespace(value="ignore_revision"),
                match_reason="latest live pair",
            )

    monkeypatch.setitem(
        sys.modules,
        "riotmanifest",
        SimpleNamespace(LeagueManifestResolver=_FakeResolver),
    )

    pair = resolve_remote_manifest_pair(_build_config(tmp_path))
    assert pair.version == "16.5"
    assert pair.lcu_manifest_url == "https://lcu.example"
    assert pair.match_mode == "ignore_revision"


def test_build_remote_app_context_should_pass_cli_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应把 manifest trio 与基础参数写入 `cli_overrides`。"""

    calls: dict[str, object] = {}

    def _fake_setup_app(*, dev_mode: bool, log_level: str, cli_overrides: dict[str, object]) -> object:
        calls["dev_mode"] = dev_mode
        calls["log_level"] = log_level
        calls["cli_overrides"] = cli_overrides
        return object()

    monkeypatch.setitem(sys.modules, "lol_audio_unpack", SimpleNamespace(setup_app=_fake_setup_app))

    pair = ManifestPairRef(
        version="16.5",
        lcu_manifest_url="https://lcu.example",
        game_manifest_url="https://game.example",
        match_mode="ignore_revision",
        match_reason="ok",
    )
    build_remote_app_context(_build_config(tmp_path), pair)

    overrides = calls["cli_overrides"]
    assert isinstance(overrides, dict)
    assert overrides["SOURCE_MODE"] == "remote_snapshot"
    assert overrides["REMOTE_VERSION"] == "16.5"
    assert overrides["REMOTE_LCU_MANIFEST_URL"] == "https://lcu.example"
    assert overrides["WWISER_PATH"] == str((tmp_path / "wwiser.pyz"))


def test_build_remote_operation_options_should_forward_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应把本仓配置映射为上游 `OperationOptions`。"""

    class _FakeOperationOptions:
        def __init__(
            self,
            *,
            max_workers: int,
            force_update: bool,
            process_events: bool,
            integrate_data: bool,
            champion_ids: tuple[int, ...] | None,
            map_ids: tuple[int, ...] | None,
        ) -> None:
            self.max_workers = max_workers
            self.force_update = force_update
            self.process_events = process_events
            self.integrate_data = integrate_data
            self.champion_ids = champion_ids
            self.map_ids = map_ids

    monkeypatch.setitem(
        sys.modules,
        "lol_audio_unpack",
        SimpleNamespace(OperationOptions=_FakeOperationOptions),
    )

    options = build_remote_operation_options(
        _build_config(tmp_path),
        champion_ids=(1,),
        map_ids=None,
    )
    assert options.max_workers == 4
    assert options.integrate_data is True
    assert options.champion_ids == (1,)


def test_convert_remote_payload_should_normalize_paths(tmp_path: Path) -> None:
    """应把上游回调路径转成 `Path`。"""

    payload = SimpleNamespace(
        entity_type="champion",
        entity_id=1,
        audio_output_paths=(str(tmp_path / "audios" / "annie"),),
        mapping_output_path=str(tmp_path / "hashes" / "annie.yml"),
    )

    artifacts = convert_remote_payload(payload)
    assert artifacts.entity_type == "champion"
    assert artifacts.audio_output_paths == (tmp_path / "audios" / "annie",)
    assert artifacts.mapping_output_path == (tmp_path / "hashes" / "annie.yml")


def test_run_remote_pipeline_should_collect_callback_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应通过上游回调收集实体产物。"""

    class _FakeOperationOptions:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    def _fake_setup_app(*, dev_mode: bool, log_level: str, cli_overrides: dict[str, object]) -> object:
        del dev_mode, log_level, cli_overrides
        return object()

    class _FakeApp:
        def __init__(self, ctx: object) -> None:
            self.ctx = ctx

        def run_remote_entity_workflow(self, **kwargs) -> None:
            callback = kwargs["on_entity_complete"]
            callback(
                SimpleNamespace(
                    entity_type="champion",
                    entity_id=1,
                    audio_output_paths=(tmp_path / "audios" / "annie",),
                    mapping_output_path=tmp_path / "hashes" / "annie.yml",
                )
            )

    monkeypatch.setitem(
        sys.modules,
        "lol_audio_unpack",
        SimpleNamespace(
            setup_app=_fake_setup_app,
            OperationOptions=_FakeOperationOptions,
            LolAudioUnpackApp=_FakeApp,
        ),
    )

    config = _build_config(tmp_path)
    pair = ManifestPairRef(
        version="16.5",
        lcu_manifest_url="https://lcu.example",
        game_manifest_url="https://game.example",
        match_mode="ignore_revision",
        match_reason="ok",
    )
    log_ctx = initialize_run_logging(config)

    artifacts = run_remote_pipeline(config, pair, log_ctx)

    assert len(artifacts) == 1
    assert artifacts[0].entity_id == 1
    assert artifacts[0].mapping_output_path == (tmp_path / "hashes" / "annie.yml")
