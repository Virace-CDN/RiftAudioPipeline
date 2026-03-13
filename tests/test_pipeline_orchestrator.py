"""Pipeline orchestrator 测试。"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

import rift_audio_pipeline.pipeline.artifact_tasks as artifact_tasks
import rift_audio_pipeline.pipeline.orchestrator as orchestrator
from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import DEFAULT_ARCHIVE_PASSWORD
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


def _build_remote_config(tmp_path: Path) -> PipelineRunConfig:
    """构造 remote 测试配置。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        run_id="run-test",
        state_db_path=state_db_path,
    )
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-test",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-14T00:00:00+08:00",
            "archive_remote_root": "/apps/test-data/",
            "meta_remote_root": "/apps/test-meta/",
            "entry_count": 0,
            "entries": {},
        },
    )
    return config


def test_build_artifact_task_plans_should_derive_archive_and_remote_paths(
    tmp_path: Path,
) -> None:
    """应从单实体产物导出打包计划与远端路径。"""

    audio_dir = tmp_path / "audios" / "annie"
    audio_dir.mkdir(parents=True, exist_ok=True)
    mapping_file = tmp_path / "hashes" / "annie.yml"
    mapping_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.write_text("meta", encoding="utf-8")
    report_file = tmp_path / "output" / "reports" / "16.5" / "champions" / "_1_metadata.yaml"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("meta: 1", encoding="utf-8")
    config = _build_remote_config(tmp_path)
    plans = artifact_tasks.build_artifact_task_plans(
        output_root=config.output_root,
        archive_remote_root=config.archive_remote_root,
        artifact=EntityArtifacts(
            entity_type="champion",
            entity_id=1,
            audio_output_paths=(audio_dir,),
            mapping_output_path=mapping_file,
        ),
        version="16.5",
    )

    assert len(plans) == 1
    assert plans[0].source_dir == audio_dir
    assert plans[0].archive_output_dir == tmp_path / "output" / "packages" / "16.5" / "champion"
    assert plans[0].archive_name == "annie-16.5-VO.7z"
    assert plans[0].report_file == report_file
    assert plans[0].extra_files == (
        mapping_file,
        (Path(orchestrator.__file__).resolve().parents[1] / "pack_extra"),
    )
    assert plans[0].remote_relative_path == "champions/annie-16.5-VO.7z"
    assert plans[0].remote_path == "/apps/test-data/champions/annie-16.5-VO.7z"


def test_artifact_task_plan_should_round_trip_and_pack_with_default_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """artifact task 计划应能序列化回写，并在 worker 侧复用默认密码打包。"""

    calls: list[dict[str, object]] = []

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
        del report_file, encrypt_filenames, extra_files, compression_level, seven_zip_executable
        calls.append(
            {
                "champion_dir": champion_dir,
                "output_path": output_path,
                "archive_name": archive_name,
                "password": password,
            }
        )
        output_path.mkdir(parents=True, exist_ok=True)
        archive_path = output_path / f"{champion_dir.name}.7z"
        archive_path.write_text("archive", encoding="utf-8")
        return archive_path

    monkeypatch.setattr(artifact_tasks, "pack_champion", _fake_pack_champion)

    audio_dir = tmp_path / "audios" / "annie"
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "sample.txt").write_text("voice", encoding="utf-8")
    config = _build_remote_config(tmp_path)
    plan = artifact_tasks.build_artifact_task_plans(
        output_root=config.output_root,
        archive_remote_root=config.archive_remote_root,
        artifact=EntityArtifacts(
            entity_type="champion",
            entity_id=1,
            audio_output_paths=(audio_dir,),
        ),
        version="16.5",
    )[0]
    payload = artifact_tasks.serialize_artifact_task_plan(plan)
    parsed_plan = artifact_tasks.parse_artifact_task_plan(payload, remote_path=plan.remote_path)
    archive_path = artifact_tasks.pack_artifact_task(
        parsed_plan,
        archive_password=DEFAULT_ARCHIVE_PASSWORD,
    )

    assert calls[0]["password"] == DEFAULT_ARCHIVE_PASSWORD
    assert calls[0]["archive_name"] == "annie-16.5-VO.7z"
    assert archive_path == tmp_path / "output" / "packages" / "16.5" / "champion" / "annie.7z"


def test_build_processing_targets_should_prefer_explicit_ids(tmp_path: Path) -> None:
    """显式 ID 存在时应直接生成对应目标。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
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
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
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
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
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


def test_resolve_current_manifest_pair_should_prefer_explicit_runtime_config(tmp_path: Path) -> None:
    """显式 current pair 存在时应直接采用运行配置。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        current_version="16.5",
        current_lcu_manifest_url="https://lcu.example/16.5",
        current_game_manifest_url="https://game.example/16.5",
    )

    current_pair = orchestrator._resolve_current_manifest_pair(config)

    assert current_pair is not None
    assert current_pair.version == "16.5"
    assert current_pair.match_mode == "external_current_pair"
    assert current_pair.match_reason == "provided_by_runtime_config"


def test_run_pipeline_should_run_remote_and_upload_archives(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """remote happy path 应把 archive 写入 SQLite 上传队列并封口。"""

    config = _build_remote_config(tmp_path)
    audio_dir = tmp_path / "audios" / "annie"
    audio_dir.mkdir(parents=True, exist_ok=True)

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
        lambda config, pair, log_ctx, on_entity_complete=None: (
            on_entity_complete(
                EntityArtifacts(entity_type="champion", entity_id=1, audio_output_paths=(audio_dir,))
            )
            if on_entity_complete is not None
            else None
        )
        or [EntityArtifacts(entity_type="champion", entity_id=1, audio_output_paths=(audio_dir,))],
    )
    summary = orchestrator.run_pipeline(config)
    artifacts_payload = json.loads(summary.log_dir.joinpath("artifacts.json").read_text(encoding="utf-8"))
    with sqlite3.connect(config.state_db_path) as connection:
        upload_tasks = connection.execute(
            """
            SELECT local_path, remote_path, task_type, status
            FROM upload_tasks
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            ("run-test",),
        ).fetchall()
        run_control = connection.execute(
            """
            SELECT task_production_open, pipeline_status, final_summary_path
            FROM run_control
            WHERE run_id = ?
            """,
            ("run-test",),
        ).fetchone()

    assert summary.status is PipelineRunStatus.SUCCESS
    assert summary.version == "16.5"
    assert summary.uploaded_archives == 1
    assert artifacts_payload["schema_version"] == 1
    assert artifacts_payload["archive_count"] == 1
    assert artifacts_payload["artifacts"][0]["entity_id"] == 1
    assert summary.processed_targets == 1
    assert upload_tasks == [
        (
            str(audio_dir),
            "/apps/test-data/champions/annie-16.5-VO.7z",
            "artifact",
            "queued",
        )
    ]
    assert run_control is not None
    assert run_control[0] == 0
    assert run_control[1] == "success"
    assert run_control[2].endswith("run.json")
    run_payload = json.loads(summary.log_dir.joinpath("run.json").read_text(encoding="utf-8"))
    decision_payload = json.loads(
        summary.log_dir.joinpath("decision.json").read_text(encoding="utf-8")
    )
    assert run_payload["status"] == "success"
    assert decision_payload["target_source"] == "unit_test"


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
    with sqlite3.connect(config.state_db_path) as connection:
        upload_task_count = connection.execute(
            "SELECT COUNT(*) FROM upload_tasks WHERE run_id = ?",
            ("run-test",),
        ).fetchone()
        run_control = connection.execute(
            "SELECT task_production_open, pipeline_status FROM run_control WHERE run_id = ?",
            ("run-test",),
        ).fetchone()

    decision_payload = json.loads(
        summary.log_dir.joinpath("decision.json").read_text(encoding="utf-8")
    )
    assert summary.status == "success"
    assert summary.processed_targets == 0
    assert remote_calls == []
    assert upload_task_count == (0,)
    assert run_control == (0, "success")
    assert decision_payload["remote_execution_skipped"] is True
    assert decision_payload["schema_version"] == 1


def test_run_pipeline_should_require_state_db_path(tmp_path: Path) -> None:
    """当前主路径缺少状态库时应直接失败，而不是回退旧上传实现。"""

    config = PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=tmp_path / "output",
        temp_root=tmp_path / "temp",
        log_root=tmp_path / "output" / "logs",
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
    )

    with pytest.raises(ValueError, match="state_db_path"):
        orchestrator.run_pipeline(config)
