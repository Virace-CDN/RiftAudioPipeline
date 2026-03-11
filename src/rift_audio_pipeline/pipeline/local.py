"""Local 模式上游适配层。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import re
from typing import TYPE_CHECKING

from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineStage

if TYPE_CHECKING:
    from rift_audio_pipeline.pipeline.logging import PipelineLogContext

ENTITY_ID_PATTERN = re.compile(r"^(?P<entity_id>\d+)(?:[·._ -].*)?$")


def build_local_app_context(config: PipelineRunConfig) -> object:
    """构造 local 模式的上游 `AppContext`。

    Args:
        config: Pipeline 运行配置。

    Returns:
        object: `lol_audio_unpack` 返回的 `AppContext`。

    Raises:
        ValueError: 未提供 `game_path` 时抛出。
    """

    from lol_audio_unpack import setup_app

    if config.game_path is None:
        raise ValueError("local 模式缺少 game_path，无法构造 AppContext。")

    cli_overrides: dict[str, object] = {
        "SOURCE_MODE": "local_path",
        "GAME_PATH": str(config.game_path),
        "OUTPUT_PATH": str(config.output_root),
        "GAME_REGION": config.game_region,
    }
    if config.wwiser_path is not None:
        cli_overrides["WWISER_PATH"] = str(config.wwiser_path)

    return setup_app(
        dev_mode=config.dev_mode,
        log_level=config.log_level,
        cli_overrides=cli_overrides,
    )


def run_local_pipeline(
    config: PipelineRunConfig,
    log_ctx: PipelineLogContext,
) -> list[EntityArtifacts]:
    """运行 local 模式流程并扫描本地产物。

    Args:
        config: Pipeline 运行配置。
        log_ctx: 日志上下文。

    Returns:
        list[EntityArtifacts]: 本轮扫描到的本地产物集合。
    """

    from lol_audio_unpack import LolAudioUnpackApp
    from lol_audio_unpack import OperationOptions

    ctx = build_local_app_context(config)
    app = LolAudioUnpackApp(ctx)
    opts = OperationOptions(
        max_workers=config.max_workers,
        force_update=config.force_update,
        process_events=True,
        integrate_data=config.integrate_data,
        champion_ids=config.champion_ids,
        map_ids=config.map_ids,
    )

    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.INIT,
            event_type="local_context_ready",
            message="local AppContext 已就绪",
            payload={
                "mode": config.mode.value,
                "game_path": str(config.game_path) if config.game_path is not None else None,
                "config": asdict(config),
            },
            created_at=datetime.now().astimezone().isoformat(),
            status_hint="running",
            operation="build_local_context",
        ),
    )

    if config.run_update:
        app.update(opts, target="all")
    if config.run_extract:
        app.extract(
            opts,
            include_champions=config.include_champions,
            include_maps=config.include_maps,
        )
    if config.run_mapping:
        app.mapping(
            opts,
            include_champions=config.include_champions,
            include_maps=config.include_maps,
        )

    artifacts = _collect_local_artifacts(config)
    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.EXTRACT,
            event_type="local_artifacts_scanned",
            message="local 本地产物扫描完成",
            payload={
                "artifact_count": len(artifacts),
                "entity_ids": [artifact.entity_id for artifact in artifacts],
            },
            created_at=datetime.now().astimezone().isoformat(),
            status_hint="running",
            operation="scan_local_artifacts",
        ),
    )
    return artifacts


def _collect_local_artifacts(config: PipelineRunConfig) -> list[EntityArtifacts]:
    """扫描 local 输出目录并回填统一产物对象。"""

    version = _resolve_local_output_version(config.output_root)
    if version is None:
        return []

    audio_paths_by_id = _collect_audio_output_paths(config.output_root / "audios" / version)
    mapping_paths_by_type = _collect_mapping_output_paths(
        config.output_root / "hashes" / version,
        prefer_integrated=config.integrate_data,
    )
    selected_ids = _resolve_selected_entity_ids(
        config=config,
        audio_ids=set(audio_paths_by_id),
        mapping_paths_by_type=mapping_paths_by_type,
    )

    artifacts: list[EntityArtifacts] = []
    for entity_type, entity_ids in selected_ids.items():
        mapping_lookup = mapping_paths_by_type[entity_type]
        for entity_id in entity_ids:
            audio_output_paths = audio_paths_by_id.get(entity_id, tuple())
            if not audio_output_paths:
                continue
            artifacts.append(
                EntityArtifacts(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    audio_output_paths=audio_output_paths,
                    mapping_output_path=mapping_lookup.get(entity_id),
                )
            )
    return artifacts


def _resolve_local_output_version(output_root: Path) -> str | None:
    """从 local 输出目录推断当前版本号。"""

    version_file = output_root / "manifest" / "version.txt"
    if version_file.is_file():
        version = version_file.read_text(encoding="utf-8").strip()
        if version:
            return version

    candidate_versions: set[str] = set()
    for relative_path in ("audios", "hashes", "reports"):
        base_dir = output_root / relative_path
        if not base_dir.is_dir():
            continue
        for child in base_dir.iterdir():
            if child.is_dir():
                candidate_versions.add(child.name)
    if not candidate_versions:
        return None
    return sorted(candidate_versions, key=_version_sort_key)[-1]


def _collect_audio_output_paths(audio_root: Path) -> dict[int, tuple[Path, ...]]:
    """收集 `audios/<version>` 下的实体输出目录。"""

    collected: dict[int, list[Path]] = {}
    if not audio_root.is_dir():
        return {}

    for child in sorted(audio_root.iterdir(), key=lambda item: item.name.casefold()):
        if not child.is_dir():
            continue
        entity_id = _parse_entity_id(child.name)
        if entity_id is not None:
            collected.setdefault(entity_id, []).append(child)
            continue
        for grandchild in sorted(child.iterdir(), key=lambda item: item.name.casefold()):
            if not grandchild.is_dir():
                continue
            entity_id = _parse_entity_id(grandchild.name)
            if entity_id is None:
                continue
            collected.setdefault(entity_id, []).append(grandchild)
    return {entity_id: _sorted_unique_paths(paths) for entity_id, paths in collected.items()}


def _collect_mapping_output_paths(
    hashes_root: Path,
    *,
    prefer_integrated: bool,
) -> dict[str, dict[int, Path]]:
    """收集 `hashes/<version>` 下的实体映射文件。"""

    results: dict[str, dict[int, Path]] = {"champion": {}, "map": {}}
    root_candidates = (
        (
            ("champion", hashes_root / "integrated" / "champions"),
            ("map", hashes_root / "integrated" / "maps"),
            ("champion", hashes_root / "champions"),
            ("map", hashes_root / "maps"),
        )
        if prefer_integrated
        else (
            ("champion", hashes_root / "champions"),
            ("map", hashes_root / "maps"),
            ("champion", hashes_root / "integrated" / "champions"),
            ("map", hashes_root / "integrated" / "maps"),
        )
    )
    for entity_type, root_dir in root_candidates:
        if not root_dir.is_dir():
            continue
        for file_path in sorted(root_dir.iterdir(), key=lambda item: item.name.casefold()):
            if not file_path.is_file():
                continue
            entity_id = _parse_entity_id(file_path.stem)
            if entity_id is None:
                continue
            results[entity_type].setdefault(entity_id, file_path)
    return results


def _resolve_selected_entity_ids(
    *,
    config: PipelineRunConfig,
    audio_ids: set[int],
    mapping_paths_by_type: dict[str, dict[int, Path]],
) -> dict[str, tuple[int, ...]]:
    """根据配置、音频目录和映射产物推断应回填的实体集合。"""

    champion_ids = set(config.champion_ids or tuple()) if config.include_champions else set()
    map_ids = set(config.map_ids or tuple()) if config.include_maps else set()

    if config.include_champions and not champion_ids:
        champion_ids.update(mapping_paths_by_type["champion"])
    if config.include_maps and not map_ids:
        map_ids.update(mapping_paths_by_type["map"])

    unresolved_audio_ids = audio_ids - champion_ids - map_ids
    if unresolved_audio_ids:
        if config.include_champions and not config.include_maps:
            champion_ids.update(unresolved_audio_ids)
        elif config.include_maps and not config.include_champions:
            map_ids.update(unresolved_audio_ids)

    return {
        "champion": tuple(sorted(champion_ids)),
        "map": tuple(sorted(map_ids)),
    }


def _parse_entity_id(raw_name: str) -> int | None:
    """从实体目录名或文件名中提取整数 ID。"""

    match = ENTITY_ID_PATTERN.match(raw_name)
    if match is None:
        return None
    return int(match.group("entity_id"))


def _sorted_unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    """按路径稳定去重。"""

    unique_paths: dict[str, Path] = {}
    for path in paths:
        unique_paths.setdefault(str(path), path)
    return tuple(
        unique_paths[key] for key in sorted(unique_paths, key=lambda item: item.casefold())
    )


def _version_sort_key(version: str) -> tuple[int, ...]:
    """将版本字符串转换为可排序元组。"""

    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return (0,)
