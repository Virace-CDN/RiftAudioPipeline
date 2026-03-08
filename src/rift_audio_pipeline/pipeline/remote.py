"""Remote 模式上游适配层。"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable
from typing import TYPE_CHECKING

from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineStage

if TYPE_CHECKING:
    from rift_audio_pipeline.pipeline.logging import PipelineLogContext

DEFAULT_REMOTE_LIVE_REGION = "EUW"


def resolve_remote_manifest_pair(config: PipelineRunConfig) -> ManifestPairRef:
    """解析 remote 模式使用的 manifest pair。

    Args:
        config: Pipeline 运行配置。

    Returns:
        ManifestPairRef: 面向本仓的最小 manifest pair 结构。
    """

    from riotmanifest import LeagueManifestResolver

    resolver = LeagueManifestResolver()
    pair = resolver.resolve_manifest_pair(config.remote_live_region or DEFAULT_REMOTE_LIVE_REGION)
    match_mode = getattr(pair.match_mode, "value", str(pair.match_mode))
    return ManifestPairRef(
        version=str(pair.version),
        lcu_manifest_url=pair.lcu.url,
        game_manifest_url=pair.game.url,
        match_mode=str(match_mode),
        match_reason=str(pair.match_reason),
    )


def build_remote_app_context(config: PipelineRunConfig, pair: ManifestPairRef) -> object:
    """构造 remote 模式的上游 `AppContext`。

    Args:
        config: Pipeline 运行配置。
        pair: 已解析的 manifest pair。

    Returns:
        object: `lol_audio_unpack` 返回的 `AppContext`。
    """

    from lol_audio_unpack import setup_app

    cli_overrides = _build_remote_cli_overrides(config=config, pair=pair)
    return setup_app(
        dev_mode=config.dev_mode,
        log_level=config.log_level,
        cli_overrides=cli_overrides,
    )


def build_remote_operation_options(
    config: PipelineRunConfig,
    *,
    champion_ids: tuple[int, ...] | None,
    map_ids: tuple[int, ...] | None,
    integrate_data: bool | None = None,
) -> object:
    """把本仓配置转换为上游 `OperationOptions`。

    Args:
        config: Pipeline 运行配置。
        champion_ids: 指定英雄 ID。
        map_ids: 指定地图 ID。
        integrate_data: 是否覆盖 `integrate_data`。

    Returns:
        object: 上游 `OperationOptions` 对象。
    """

    from lol_audio_unpack import OperationOptions

    return OperationOptions(
        max_workers=config.max_workers,
        force_update=config.force_update,
        process_events=True,
        integrate_data=config.integrate_data if integrate_data is None else integrate_data,
        champion_ids=champion_ids,
        map_ids=map_ids,
    )


def convert_remote_payload(payload: object) -> EntityArtifacts:
    """将上游 remote 回调载荷转换为本仓实体产物。

    Args:
        payload: `RemoteEntityCallbackPayload` 实例。

    Returns:
        EntityArtifacts: 本仓统一产物对象。
    """

    audio_output_paths = tuple(
        Path(path) for path in getattr(payload, "audio_output_paths", tuple())
    )
    mapping_output_path = getattr(payload, "mapping_output_path", None)
    normalized_mapping_path = Path(mapping_output_path) if mapping_output_path is not None else None
    return EntityArtifacts(
        entity_type=str(getattr(payload, "entity_type")),
        entity_id=int(getattr(payload, "entity_id")),
        audio_output_paths=audio_output_paths,
        mapping_output_path=normalized_mapping_path,
    )


def run_remote_pipeline(
    config: PipelineRunConfig,
    pair: ManifestPairRef,
    log_ctx: PipelineLogContext,
    on_entity_complete: Callable[[EntityArtifacts], None] | None = None,
) -> list[EntityArtifacts]:
    """运行 remote 模式骨架流程。

    Args:
        config: Pipeline 运行配置。
        pair: 已解析的 manifest pair。
        log_ctx: 日志上下文。
        on_entity_complete: 单实体完成回调。

    Returns:
        list[EntityArtifacts]: 本次 remote 流程收集到的实体产物。
    """

    from lol_audio_unpack import LolAudioUnpackApp

    ctx = build_remote_app_context(config=config, pair=pair)
    app = LolAudioUnpackApp(ctx)
    collected_artifacts: list[EntityArtifacts] = []

    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.RESOLVE_MANIFEST_PAIR,
            event_type="remote_manifest_pair_ready",
            message="remote manifest pair 已就绪",
            payload=asdict(pair),
            created_at=datetime.now().astimezone().isoformat(),
        ),
    )

    if not config.run_extract and not config.run_mapping:
        if config.run_update:
            app.update(
                build_remote_operation_options(
                    config=config,
                    champion_ids=config.champion_ids,
                    map_ids=config.map_ids,
                ),
                target="all",
            )
        return collected_artifacts

    update_options = (
        build_remote_operation_options(
            config=config,
            champion_ids=config.champion_ids,
            map_ids=config.map_ids,
        )
        if config.run_update
        else None
    )
    extract_options = (
        build_remote_operation_options(
            config=config,
            champion_ids=config.champion_ids,
            map_ids=config.map_ids,
            integrate_data=False,
        )
        if config.run_extract
        else None
    )
    mapping_options = (
        build_remote_operation_options(
            config=config,
            champion_ids=config.champion_ids,
            map_ids=config.map_ids,
            integrate_data=config.integrate_data,
        )
        if config.run_mapping
        else None
    )

    def _on_entity_complete(raw_payload: object) -> None:
        artifacts = convert_remote_payload(raw_payload)
        collected_artifacts.append(artifacts)
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.EXTRACT,
                event_type="remote_entity_complete",
                message=f"remote 实体处理完成：{artifacts.entity_type}#{artifacts.entity_id}",
                payload={
                    "entity_type": artifacts.entity_type,
                    "entity_id": artifacts.entity_id,
                    "audio_output_paths": tuple(str(path) for path in artifacts.audio_output_paths),
                    "mapping_output_path": (
                        str(artifacts.mapping_output_path)
                        if artifacts.mapping_output_path is not None
                        else None
                    ),
                },
                created_at=datetime.now().astimezone().isoformat(),
            ),
        )
        if on_entity_complete is not None:
            on_entity_complete(artifacts)

    app.run_remote_entity_workflow(
        update_options=update_options,
        update_target="all",
        extract_options=extract_options,
        mapping_options=mapping_options,
        extract_include_champions=config.include_champions,
        extract_include_maps=config.include_maps,
        mapping_include_champions=config.include_champions,
        mapping_include_maps=config.include_maps,
        on_entity_complete=_on_entity_complete,
        download_retry_attempts=config.download_retry_attempts,
        entity_retry_attempts=config.entity_retry_attempts,
    )
    return collected_artifacts


def _build_remote_cli_overrides(
    config: PipelineRunConfig, pair: ManifestPairRef
) -> dict[str, object]:
    """构造传给上游的 `cli_overrides`。"""

    overrides: dict[str, object] = {
        "SOURCE_MODE": "remote_snapshot",
        "OUTPUT_PATH": str(config.output_root),
        "GAME_REGION": config.game_region,
        "REMOTE_LIVE_REGION": config.remote_live_region or DEFAULT_REMOTE_LIVE_REGION,
        "REMOTE_VERSION": pair.version,
        "REMOTE_LCU_MANIFEST_URL": pair.lcu_manifest_url,
        "REMOTE_GAME_MANIFEST_URL": pair.game_manifest_url,
        "CLEANUP_REMOTE": config.cleanup_remote,
    }
    if config.game_path is not None:
        overrides["GAME_PATH"] = str(config.game_path)
    if config.wwiser_path is not None:
        overrides["WWISER_PATH"] = str(config.wwiser_path)
    return overrides
