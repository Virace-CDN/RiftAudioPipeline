"""本地联调模拟支持。"""

from __future__ import annotations

from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import rift_audio_pipeline.pipeline.orchestrator as orchestrator
from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineStage

SIMULATION_ENV_VAR = "RIFT_CONTROL_PLANE_LOCAL_SIMULATION"
MOCK_BAIDU_ENV_VAR = "RIFT_CONTROL_PLANE_MOCK_BAIDU"
BAIDU_FAILURE_MODE_ENV_VAR = "RIFT_CONTROL_PLANE_BAIDU_FAILURE_MODE"


@dataclass(frozen=True, slots=True)
class SimulationArtifactPaths:
    """本地联调模拟产物路径。"""

    receipt_dir: Path
    archive_upload_receipt: Path
    log_upload_receipt: Path


@contextmanager
def patch_pipeline_for_simulation(
    config: PipelineRunConfig,
    *,
    receipt_dir: Path | None = None,
) -> Iterator[SimulationArtifactPaths]:
    """给 orchestrator 注入本地联调 fake 实现。"""

    artifact_paths = build_simulation_artifact_paths(config.output_root, receipt_dir=receipt_dir)
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {SIMULATION_ENV_VAR: "1"}, clear=False))
        stack.enter_context(
            patch.object(
                orchestrator,
                "run_remote_pipeline",
                _build_fake_run_remote_pipeline(),
            )
        )
        stack.enter_context(
            patch.object(
                orchestrator,
                "resolve_remote_manifest_pair",
                _build_fake_resolve_remote_manifest_pair(),
            )
        )
        stack.enter_context(
            patch.object(
                orchestrator,
                "pack_champion",
                _build_fake_pack_champion(),
            )
        )
        yield artifact_paths


def maybe_patch_pipeline_for_simulation(
    config: PipelineRunConfig,
) -> AbstractContextManager[SimulationArtifactPaths | None]:
    """按环境变量决定是否启用联调模拟。"""

    if os.getenv(SIMULATION_ENV_VAR) == "1":
        return patch_pipeline_for_simulation(config)
    if os.getenv(MOCK_BAIDU_ENV_VAR) == "1":
        return patch_pipeline_for_baidu_mock(
            config,
            failure_mode=os.getenv(BAIDU_FAILURE_MODE_ENV_VAR, "none"),
        )
    return nullcontext(None)


@contextmanager
def patch_pipeline_for_baidu_mock(
    config: PipelineRunConfig,
    *,
    receipt_dir: Path | None = None,
    failure_mode: str = "none",
) -> Iterator[SimulationArtifactPaths]:
    """只 mock 百度上传层，保留真实 remote 解包主线。"""

    artifact_paths = build_simulation_artifact_paths(config.output_root, receipt_dir=receipt_dir)
    with ExitStack() as stack:
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    MOCK_BAIDU_ENV_VAR: "1",
                    BAIDU_FAILURE_MODE_ENV_VAR: failure_mode,
                },
                clear=False,
            )
        )
        yield artifact_paths


def build_simulation_artifact_paths(
    output_root: Path,
    *,
    receipt_dir: Path | None = None,
) -> SimulationArtifactPaths:
    """构造本地联调产物路径集合。"""

    target_dir = receipt_dir or output_root / "simulation"
    target_dir.mkdir(parents=True, exist_ok=True)
    return SimulationArtifactPaths(
        receipt_dir=target_dir,
        archive_upload_receipt=target_dir / "archive_upload.json",
        log_upload_receipt=target_dir / "log_upload.json",
    )


def _build_fake_run_remote_pipeline():
    def _fake_run_remote_pipeline(
        config: PipelineRunConfig,
        pair: object,
        log_ctx: object,
    ) -> list[EntityArtifacts]:
        version = getattr(pair, "version")
        run_id = getattr(log_ctx, "run_id", None)
        if not isinstance(version, str):
            raise ValueError("本地联调模拟缺少有效 version。")
        if not isinstance(run_id, str):
            raise ValueError("本地联调模拟缺少有效 run_id。")
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=run_id,
                stage=PipelineStage.EXTRACT,
                event_type="simulation_remote_started",
                message="本地联调模拟 remote 执行开始",
                payload={
                    "version": version,
                    "champion_ids": list(config.champion_ids or tuple()),
                    "map_ids": list(config.map_ids or tuple()),
                },
                created_at=_timestamp_now(),
                status_hint="running",
                operation="simulation_remote_pipeline",
            ),
        )

        artifacts: list[EntityArtifacts] = []
        for entity_type, entity_id in _iter_simulated_targets(config):
            audio_dir = _build_audio_output_dir(
                output_root=config.output_root,
                version=version,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            audio_dir.mkdir(parents=True, exist_ok=True)
            (audio_dir / "sample.txt").write_text(
                f"mock {entity_type} payload {entity_id}",
                encoding="utf-8",
            )
            emit_event(
                log_ctx,
                PipelineEvent(
                    run_id=run_id,
                    stage=PipelineStage.EXTRACT,
                    event_type="simulation_entity_complete",
                    message=f"本地联调模拟实体完成：{entity_type}#{entity_id}",
                    payload={
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "audio_output_path": str(audio_dir),
                    },
                    created_at=_timestamp_now(),
                    status_hint="running",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    operation="simulation_entity_complete",
                ),
            )
            artifacts.append(
                EntityArtifacts(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    audio_output_paths=(audio_dir,),
                )
            )
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=run_id,
                stage=PipelineStage.EXTRACT,
                event_type="simulation_remote_finished",
                message="本地联调模拟 remote 执行完成",
                payload={"artifact_count": len(artifacts)},
                created_at=_timestamp_now(),
                status_hint="running",
                operation="simulation_remote_pipeline",
            ),
        )
        return artifacts

    return _fake_run_remote_pipeline


def _build_fake_pack_champion():
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
            report_file,
            password,
            encrypt_filenames,
            extra_files,
            compression_level,
            seven_zip_executable,
        )
        output_path.mkdir(parents=True, exist_ok=True)
        archive_path = output_path / (archive_name or f"{champion_dir.name}.zip")
        archive_path.write_text("mock archive", encoding="utf-8")
        return archive_path

    return _fake_pack_champion


def _build_fake_resolve_remote_manifest_pair():
    def _fake_resolve_remote_manifest_pair(config: PipelineRunConfig) -> object:
        version = config.current_version or "simulation-version"
        return type("SimulationManifestPair", (), {"version": version})()

    return _fake_resolve_remote_manifest_pair


def _iter_simulated_targets(config: PipelineRunConfig) -> Iterator[tuple[str, int]]:
    for champion_id in config.champion_ids or tuple():
        yield "champion", champion_id
    for map_id in config.map_ids or tuple():
        yield "map", map_id


def _build_audio_output_dir(
    *,
    output_root: Path,
    version: str,
    entity_type: str,
    entity_id: int,
) -> Path:
    return output_root / version / entity_type / str(entity_id)


def _timestamp_now() -> str:
    return datetime.now().astimezone().isoformat()
