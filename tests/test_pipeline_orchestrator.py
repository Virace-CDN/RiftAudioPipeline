"""Pipeline orchestrator 测试。"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace

import pytest

import rift_audio_pipeline.pipeline.orchestrator as orchestrator
from rift_audio_pipeline.cloudflare.models import BaiduAccessGrant
from rift_audio_pipeline.cloudflare.models import CloudflareManifestPair
from rift_audio_pipeline.cloudflare.models import PipelineBootstrapResponse
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


def _build_remote_config(tmp_path: Path) -> PipelineRunConfig:
    """构造 remote 测试配置。"""

    return PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
    )


def test_handle_entity_artifacts_should_pack_audio_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应对实体输出目录逐个打包。"""

    calls: list[tuple[Path, Path, tuple[Path, ...]]] = []

    def _fake_pack_champion(
        champion_dir: Path,
        output_path: Path,
        *,
        archive_name: str | None = None,
        report_file: Path | None = None,
        password: str | None = None,
        encrypt_filenames: bool = True,
        extra_files: tuple[Path, ...] = tuple(),
        compression_level: int = 0,
        seven_zip_executable: str | None = None,
    ) -> Path:
        del (
            archive_name,
            report_file,
            password,
            encrypt_filenames,
            compression_level,
            seven_zip_executable,
        )
        calls.append((champion_dir, output_path, extra_files))
        return output_path / f"{champion_dir.name}.7z"

    monkeypatch.setattr(orchestrator, "pack_champion", _fake_pack_champion)

    audio_dir = tmp_path / "audios" / "annie"
    audio_dir.mkdir(parents=True, exist_ok=True)
    mapping_file = tmp_path / "hashes" / "annie.yml"
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text("meta", encoding="utf-8")

    archives = orchestrator.handle_entity_artifacts(
        config=_build_remote_config(tmp_path),
        artifact=EntityArtifacts(
            entity_type="champion",
            entity_id=1,
            audio_output_paths=(audio_dir,),
            mapping_output_path=mapping_file,
        ),
        version="16.5",
    )

    assert calls == [
        (
            audio_dir,
            tmp_path / "output" / "packages" / "16.5" / "champion",
            (mapping_file,),
        )
    ]
    assert archives == (tmp_path / "output" / "packages" / "16.5" / "champion" / "annie.7z",)


def test_build_processing_targets_should_prefer_explicit_ids(tmp_path: Path) -> None:
    """显式 ID 存在时应直接生成对应目标。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        champion_ids=(1, 103),
        map_ids=(11,),
    )

    targets = orchestrator.build_processing_targets(
        config=config,
        previous_version=None,
        current_pair=None,
    )

    assert [(target.entity_type, target.entity_id) for target in targets] == [
        ("champion", 1),
        ("champion", 103),
        ("map", 11),
    ]


def test_build_processing_targets_should_extract_entities_from_diff_paths(tmp_path: Path) -> None:
    """diff 路径应能回推出英雄 alias 与地图 ID。"""

    config = _build_remote_config(tmp_path)
    manifest_report = {
        "changed": [
            {"path": "DATA/FINAL/Champions/Ahri.wad.client"},
            {"path": "DATA/FINAL/Maps/Shipping/Map11/Map11.wad.client"},
        ]
    }
    pair = ManifestPairRef(
        version="16.5",
        lcu_manifest_url="https://lcu.example",
        game_manifest_url="https://game.example",
        match_mode="ignore_revision",
        match_reason="ok",
    )

    targets = orchestrator.build_processing_targets(
        config=config,
        previous_version="16.4",
        current_pair=pair,
        manifest_report=manifest_report,
    )

    assert [(target.entity_type, target.alias, target.entity_id, target.name) for target in targets] == [
        ("champion", "Ahri", None, None),
        ("map", None, 11, "Map11"),
    ]


def test_build_processing_targets_should_extract_common_map_id_zero(tmp_path: Path) -> None:
    """地图 Common 路径应稳定回推出 map_id=0。"""

    config = _build_remote_config(tmp_path)
    manifest_report = {
        "changed": [
            {"path": "DATA/FINAL/Maps/Shipping/Common/Common.wad.client"},
        ]
    }
    pair = ManifestPairRef(
        version="16.5",
        lcu_manifest_url="https://lcu.example",
        game_manifest_url="https://game.example",
        match_mode="ignore_revision",
        match_reason="ok",
    )

    targets = orchestrator.build_processing_targets(
        config=config,
        previous_version="16.4",
        current_pair=pair,
        manifest_report=manifest_report,
    )

    assert [(target.entity_type, target.entity_id, target.name) for target in targets] == [
        ("map", 0, "Common"),
    ]


def test_select_target_wad_paths_should_prefer_changed_then_unchanged() -> None:
    """应优先选择 changed WAD，必要时回退 unchanged。"""

    report = type(
        "ManifestReport",
        (),
        {
            "changed": [type("Entry", (), {"path": "DATA/FINAL/Champions/Ahri.wad.client"})()],
            "unchanged": [type("Entry", (), {"path": "DATA/FINAL/Champions/Zed.wad.client"})()],
        },
    )()
    selected = orchestrator.select_target_wad_paths(report)
    assert selected == ("DATA/FINAL/Champions/Ahri.wad.client",)

    empty_changed_report = type(
        "ManifestReport",
        (),
        {
            "changed": [],
            "unchanged": [type("Entry", (), {"path": "DATA/FINAL/Champions/Zed.wad.client"})()],
        },
    )()
    fallback_selected = orchestrator.select_target_wad_paths(empty_changed_report)
    assert fallback_selected == ("DATA/FINAL/Champions/Zed.wad.client",)


def test_apply_targets_to_config_should_only_override_known_ids(tmp_path: Path) -> None:
    """只有可解析 ID 的目标才应覆盖配置。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        champion_ids=(5,),
    )
    targets = (
        orchestrator.ProcessingTarget(entity_type="champion", entity_id=None, alias="Ahri"),
        orchestrator.ProcessingTarget(entity_type="map", entity_id=11, name="Map11"),
    )

    updated = orchestrator._apply_targets_to_config(config, targets)
    assert updated.champion_ids == (5,)
    assert updated.map_ids == (11,)


def test_resolve_remote_targets_should_infer_map_ids_from_previous_pair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """提供 previous pair 时，remote 目标应能从 diff 路径收敛到 map ID。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        previous_version="16.4",
        previous_lcu_manifest_url="https://lcu.example/16.4",
        previous_game_manifest_url="https://game.example/16.4",
    )
    current_pair = ManifestPairRef(
        version="16.5",
        lcu_manifest_url="https://lcu.example/16.5",
        game_manifest_url="https://game.example/16.5",
        match_mode="ignore_revision",
        match_reason="ok",
    )

    monkeypatch.setattr(
        orchestrator,
        "build_manifest_diff_report",
        lambda config, previous_pair, current_pair, include_unchanged=False: {
            "changed": [{"path": "DATA/FINAL/Maps/Shipping/Map30/Map30.wad.client"}]
        },
    )

    targets, effective_config, decision = orchestrator._resolve_remote_targets(
        config=config,
        run_id="run-1",
        current_pair=current_pair,
    )

    assert [(target.entity_type, target.entity_id, target.name) for target in targets] == [
        ("map", 30, "Map30"),
    ]
    assert effective_config.map_ids == (30,)
    assert decision.target_source == "manifest_diff_inferred"
    assert decision.previous_version == "16.4"


def test_bootstrap_control_plane_should_fill_runtime_config(tmp_path: Path) -> None:
    """控制面 bootstrap 应回填 previous pair 与百度凭据。"""

    class _FakeService:
        def get_pipeline_bootstrap(self, request) -> PipelineBootstrapResponse:
            assert request.game_region == "zh_CN"
            return PipelineBootstrapResponse(
                current_version="16.5",
                previous_version="16.4",
                current_pair=CloudflareManifestPair(
                    version="16.5",
                    lcu_manifest_url="https://lcu.example/16.5",
                    game_manifest_url="https://game.example/16.5",
                ),
                previous_pair=CloudflareManifestPair(
                    version="16.4",
                    lcu_manifest_url="https://lcu.example/16.4",
                    game_manifest_url="https://game.example/16.4",
                ),
                baidu_access_grant=BaiduAccessGrant(
                    app_key="app",
                    secret_key="secret",
                    refresh_token="refresh",
                ),
            )

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        control_plane_base_url="https://control.example.com",
    )

    original_builder = orchestrator._build_control_service
    orchestrator._build_control_service = lambda config: _FakeService()  # type: ignore[assignment]
    try:
        runtime_config, current_pair = orchestrator._bootstrap_control_plane(config)
    finally:
        orchestrator._build_control_service = original_builder  # type: ignore[assignment]

    assert current_pair is not None
    assert current_pair.version == "16.5"
    assert runtime_config.previous_version == "16.4"
    assert runtime_config.previous_game_manifest_url == "https://game.example/16.4"
    assert runtime_config.baidu_refresh_token == "refresh"


def test_run_pipeline_should_run_remote_and_upload_archives(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """remote happy path 应串起 remote、打包与上传。"""

    config = _build_remote_config(tmp_path)
    audio_dir = tmp_path / "audios" / "annie"
    audio_dir.mkdir(parents=True, exist_ok=True)
    archive_path = tmp_path / "output" / "packages" / "16.5" / "champion" / "annie.7z"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text("archive", encoding="utf-8")

    monkeypatch.setattr(
        orchestrator,
        "resolve_remote_manifest_pair",
        lambda config: ManifestPairRef(
            version="16.5",
            lcu_manifest_url="https://lcu.example",
            game_manifest_url="https://game.example",
            match_mode="ignore_revision",
            match_reason="ok",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_resolve_remote_targets",
        lambda config, run_id, current_pair: (
            (
                orchestrator.ProcessingTarget(
                    entity_type="champion", entity_id=1, decision_reason="unit_test"
                ),
            ),
            replace(config, champion_ids=(1,), include_champions=True, include_maps=False),
            orchestrator.PipelineDecisionSnapshot(
                run_id=run_id,
                target_source="unit_test",
                target_count=1,
                selected_champion_ids=(1,),
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "run_remote_pipeline",
        lambda config, pair, log_ctx: [
            EntityArtifacts(entity_type="champion", entity_id=1, audio_output_paths=(audio_dir,))
        ],
    )
    monkeypatch.setattr(
        orchestrator, "pack_champion", lambda champion_dir, output_path, **kwargs: archive_path
    )
    upload_calls: list[tuple[tuple[Path, ...], str]] = []
    monkeypatch.setattr(
        orchestrator,
        "_upload_archives_for_run",
        lambda config, archives, version: upload_calls.append((archives, version)),
    )

    summary = orchestrator.run_pipeline(config)
    artifacts_payload = json.loads(summary.log_dir.joinpath("artifacts.json").read_text(encoding="utf-8"))

    assert summary.status is PipelineRunStatus.SUCCESS
    assert summary.version == "16.5"
    assert summary.uploaded_archives == 1
    assert artifacts_payload["schema_version"] == 1
    assert artifacts_payload["archive_count"] == 1
    assert artifacts_payload["artifacts"][0]["entity_id"] == 1
    assert summary.processed_targets == 1
    assert upload_calls == [((archive_path,), "16.5")]
    run_payload = json.loads(summary.log_dir.joinpath("run.json").read_text(encoding="utf-8"))
    decision_payload = json.loads(
        summary.log_dir.joinpath("decision.json").read_text(encoding="utf-8")
    )
    assert run_payload["status"] == "success"
    assert decision_payload["target_source"] == "unit_test"


def test_run_pipeline_should_enqueue_log_retry_when_log_upload_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """日志上传失败时应写入待补偿队列。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        baidu_remote_root="/apps/test",
        baidu_app_key="app",
        baidu_secret_key="secret",
        baidu_refresh_token="refresh",
    )

    monkeypatch.setattr(
        orchestrator,
        "resolve_remote_manifest_pair",
        lambda config: ManifestPairRef(
            version="16.5",
            lcu_manifest_url="https://lcu.example",
            game_manifest_url="https://game.example",
            match_mode="ignore_revision",
            match_reason="ok",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_resolve_remote_targets",
        lambda config, run_id, current_pair: (
            (
                orchestrator.ProcessingTarget(
                    entity_type="champion", entity_id=1, decision_reason="unit_test"
                ),
            ),
            replace(config, champion_ids=(1,), include_champions=True, include_maps=False),
            orchestrator.PipelineDecisionSnapshot(
                run_id=run_id,
                target_source="unit_test",
                target_count=1,
                selected_champion_ids=(1,),
            ),
        ),
    )
    monkeypatch.setattr(orchestrator, "run_remote_pipeline", lambda config, pair, log_ctx: [])

    class _FakeClient:
        def close(self) -> None:
            return None

    monkeypatch.setattr(orchestrator, "_create_baidu_client", lambda config: _FakeClient())
    monkeypatch.setattr(
        orchestrator,
        "upload_run_logs",
        lambda log_ctx, config, client: (_ for _ in ()).throw(RuntimeError("upload failed")),
    )

    summary = orchestrator.run_pipeline(config)

    queue_file = tmp_path / "output" / "state" / "pending_log_upload_queue.json"
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert summary.pending_log_upload_entries == 1
    assert payload[0]["error_message"] == "upload failed"


def test_run_pipeline_should_skip_remote_execution_when_no_targets_resolved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """未解析到目标时应安全跳过 remote 执行，避免误跑全量。"""

    config = _build_remote_config(tmp_path)
    remote_calls: list[PipelineRunConfig] = []

    monkeypatch.setattr(
        orchestrator,
        "resolve_remote_manifest_pair",
        lambda config: ManifestPairRef(
            version="16.5",
            lcu_manifest_url="https://lcu.example",
            game_manifest_url="https://game.example",
            match_mode="ignore_revision",
            match_reason="ok",
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_resolve_remote_targets",
        lambda config, run_id, current_pair: (
            tuple(),
            replace(config, include_champions=False, include_maps=False),
            orchestrator.PipelineDecisionSnapshot(
                run_id=run_id,
                target_source="none",
                target_count=0,
                remote_execution_skipped=True,
            ),
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "run_remote_pipeline",
        lambda config, pair, log_ctx: remote_calls.append(config) or [],
    )

    summary = orchestrator.run_pipeline(config)

    decision_payload = json.loads(
        summary.log_dir.joinpath("decision.json").read_text(encoding="utf-8")
    )
    assert summary.status == "success"
    assert summary.processed_targets == 0
    assert remote_calls == []
    assert decision_payload["remote_execution_skipped"] is True
    assert decision_payload["schema_version"] == 1
