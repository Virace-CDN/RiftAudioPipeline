"""本地 control plane 联调模拟支持。"""

from __future__ import annotations

from contextlib import ExitStack
from contextlib import AbstractContextManager
from contextlib import contextmanager
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
import json
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
        stack.enter_context(
            patch.object(
                orchestrator,
                "_upload_archives_for_run",
                _build_fake_archive_upload(artifact_paths.archive_upload_receipt),
            )
        )
        stack.enter_context(
            patch.object(
                orchestrator,
                "_retry_pending_manifest_sync_queue_if_possible",
                lambda config, queue_file: None,
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
            patch.object(
                orchestrator,
                "resolve_remote_manifest_pair",
                _build_fake_resolve_remote_manifest_pair(),
            )
        )
        stack.enter_context(
            patch.object(
                orchestrator,
                "_upload_archives_for_run",
                _build_fake_archive_upload(
                    artifact_paths.archive_upload_receipt,
                    failure_mode=failure_mode,
                ),
            )
        )
        stack.enter_context(
            patch.object(
                orchestrator,
                "_retry_pending_manifest_sync_queue_if_possible",
                lambda config, queue_file: None,
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
    """构造本地 fake remote 执行函数。"""

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
    """构造本地 fake 打包函数。"""

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
        archive_path = output_path / f"{archive_name or champion_dir.name}.7z"
        archive_path.write_text("mock archive payload", encoding="utf-8")
        return archive_path

    return _fake_pack_champion


def _build_fake_resolve_remote_manifest_pair():
    """构造本地 fake manifest pair 解析函数。"""

    def _fake_resolve_remote_manifest_pair(config: PipelineRunConfig):
        del config
        return orchestrator.ManifestPairRef(
            version="16.5",
            lcu_manifest_url="https://lcu.example/16.5",
            game_manifest_url="https://game.example/16.5",
            match_mode="simulation",
            match_reason="simulation_fixed_pair",
        )

    return _fake_resolve_remote_manifest_pair


def _build_fake_archive_upload(receipt_path: Path, *, failure_mode: str = "none"):
    """构造本地 fake archive 上传函数。"""

    def _fake_upload_archives_for_run(
        config: PipelineRunConfig,
        archives: tuple[Path, ...],
        version: str,
    ) -> None:
        if failure_mode in {"archive", "both"}:
            raise RuntimeError("本地联调模拟：archive upload failure")
        _write_json(
            receipt_path,
            {
                "recorded_at": _timestamp_now(),
                "remote_root": config.baidu_remote_root,
                "version": version,
                "archives": [str(path) for path in archives],
            },
        )

    return _fake_upload_archives_for_run


def _build_fake_log_upload(receipt_path: Path, *, failure_mode: str = "none"):
    """构造本地 fake 日志上传函数。"""

    def _fake_upload_run_logs(log_ctx: object, config: PipelineRunConfig, client: object) -> None:
        del client
        if failure_mode in {"log", "both"}:
            raise RuntimeError("本地联调模拟：log upload failure")
        log_dir = getattr(log_ctx, "log_dir")
        run_id = getattr(log_ctx, "run_id")
        run_date = getattr(log_ctx, "run_date")
        if not isinstance(log_dir, Path):
            raise ValueError("本地联调模拟缺少有效 log_dir。")
        _write_json(
            receipt_path,
            {
                "recorded_at": _timestamp_now(),
                "run_id": run_id,
                "remote_root": f"{config.baidu_remote_root.rstrip('/')}/logs/{run_date}/{run_id}",
                "files": sorted(
                    str(path.relative_to(log_dir))
                    for path in log_dir.rglob("*")
                    if path.is_file()
                ),
            },
        )

    return _fake_upload_run_logs


def _iter_simulated_targets(config: PipelineRunConfig) -> tuple[tuple[str, int], ...]:
    """把配置里的 champion/map IDs 归一化为模拟目标。"""

    targets: list[tuple[str, int]] = []
    targets.extend(("champion", champion_id) for champion_id in config.champion_ids or tuple())
    targets.extend(("map", map_id) for map_id in config.map_ids or tuple())
    if not targets:
        raise ValueError("本地联调模拟至少需要一个 champion_id 或 map_id。")
    return tuple(targets)


def _build_audio_output_dir(
    *,
    output_root: Path,
    version: str,
    entity_type: str,
    entity_id: int,
) -> Path:
    """为模拟产物构造音频输出目录。"""

    return output_root / "audios" / version / f"{entity_type}-{entity_id}-simulation"


def _timestamp_now() -> str:
    """返回 ISO8601 时间戳。"""

    return datetime.now().astimezone().isoformat()


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """写入 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _FakeBaiduClient:
    """最小 fake 百度客户端。"""

    def close(self) -> None:
        """模拟关闭客户端。"""
