"""Remote 模式上游适配层。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable
from typing import cast
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
    from lol_audio_unpack.remote_preparer import RemoteSnapshotPreparer

    ctx = build_remote_app_context(config=config, pair=pair)
    app = LolAudioUnpackApp(ctx)
    collected_artifacts: list[EntityArtifacts] = []
    restore_hooks = _install_remote_progress_hooks(
        app=app,
        remote_preparer_cls=RemoteSnapshotPreparer,
        log_ctx=log_ctx,
        pair=pair,
        config=config,
    )

    try:
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.RESOLVE_MANIFEST_PAIR,
                event_type="remote_manifest_pair_ready",
                message="remote manifest pair 已就绪",
                payload=asdict(pair),
                created_at=datetime.now().astimezone().isoformat(),
                status_hint="running",
                operation="resolve_remote_manifest_pair",
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

        runtime_config = config
        update_options = (
            build_remote_operation_options(
                config=runtime_config,
                champion_ids=runtime_config.champion_ids,
                map_ids=runtime_config.map_ids,
            )
            if runtime_config.run_update
            else None
        )
        extract_options = (
            build_remote_operation_options(
                config=runtime_config,
                champion_ids=runtime_config.champion_ids,
                map_ids=runtime_config.map_ids,
                integrate_data=False,
            )
            if runtime_config.run_extract
            else None
        )
        mapping_options = (
            build_remote_operation_options(
                config=runtime_config,
                champion_ids=runtime_config.champion_ids,
                map_ids=runtime_config.map_ids,
                integrate_data=runtime_config.integrate_data,
            )
            if runtime_config.run_mapping
            else None
        )
        if _should_prepare_full_fallback(runtime_config):
            if update_options is not None:
                app.update(update_options, target="all")
                update_options = None
            post_update_work_item_count = _preview_remote_work_item_count(
                app=app,
                extract_options=extract_options,
                mapping_options=mapping_options,
                config=runtime_config,
            )
            if post_update_work_item_count in {None, 0}:
                runtime_config = _materialize_remote_target_config(
                    app=app,
                    config=runtime_config,
                )
                if not _has_explicit_remote_targets(runtime_config):
                    raise RuntimeError(
                        "remote 全量模式在 update 后仍未生成任何实体工作项，无法继续按实体下载 WAD 并执行解包。"
                    )
                extract_options = (
                    build_remote_operation_options(
                        config=runtime_config,
                        champion_ids=runtime_config.champion_ids,
                        map_ids=runtime_config.map_ids,
                        integrate_data=False,
                    )
                    if runtime_config.run_extract
                    else None
                )
                mapping_options = (
                    build_remote_operation_options(
                        config=runtime_config,
                        champion_ids=runtime_config.champion_ids,
                        map_ids=runtime_config.map_ids,
                        integrate_data=runtime_config.integrate_data,
                    )
                    if runtime_config.run_mapping
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
                    status_hint="running",
                    entity_type=artifacts.entity_type,
                    entity_id=artifacts.entity_id,
                    operation="remote_entity_complete",
                ),
            )
            if on_entity_complete is not None:
                on_entity_complete(artifacts)

        work_item_count = _preview_remote_work_item_count(
            app=app,
            extract_options=extract_options,
            mapping_options=mapping_options,
            config=runtime_config,
        )
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.EXTRACT,
                event_type="remote_entity_loop_started",
                message="remote 单位循环开始",
                payload={
                    "work_item_count": work_item_count,
                    "run_extract": runtime_config.run_extract,
                    "run_mapping": runtime_config.run_mapping,
                },
                created_at=datetime.now().astimezone().isoformat(),
                status_hint="running",
                operation="remote_entity_loop",
            ),
        )
        app.run_remote_entity_workflow(
            update_options=update_options,
            update_target="all",
            extract_options=extract_options,
            mapping_options=mapping_options,
            extract_include_champions=runtime_config.include_champions,
            extract_include_maps=runtime_config.include_maps,
            mapping_include_champions=runtime_config.include_champions,
            mapping_include_maps=runtime_config.include_maps,
            on_entity_complete=_on_entity_complete,
            download_retry_attempts=runtime_config.download_retry_attempts,
            entity_retry_attempts=runtime_config.entity_retry_attempts,
        )
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.EXTRACT,
                event_type="remote_entity_loop_finished",
                message="remote 单位循环完成",
                payload={
                    "work_item_count": work_item_count,
                    "collected_artifact_count": len(collected_artifacts),
                },
                created_at=datetime.now().astimezone().isoformat(),
                status_hint="running",
                operation="remote_entity_loop",
            ),
        )
        return collected_artifacts
    finally:
        restore_hooks()


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


def _install_remote_progress_hooks(
    *,
    app: object,
    remote_preparer_cls: type[object],
    log_ctx: PipelineLogContext,
    pair: ManifestPairRef,
    config: PipelineRunConfig,
) -> Callable[[], None]:
    """给上游 remote 主线安装阶段化结构化事件。"""

    original_prepare_lcu_game_data = getattr(remote_preparer_cls, "prepare_lcu_game_data", None)
    original_prepare_bin_inputs = getattr(remote_preparer_cls, "prepare_bin_inputs", None)
    original_update = getattr(app, "update", None)

    if not callable(original_prepare_lcu_game_data) or not callable(original_prepare_bin_inputs):
        return lambda: None

    def _wrapped_prepare_lcu_game_data(preparer_self: object) -> object:
        started_at = datetime.now().astimezone()
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.LOAD_REMOTE_INDEX,
            event_type="remote_manifest_download_started",
            message="开始下载 remote manifest",
            payload={
                "lcu_manifest_url": pair.lcu_manifest_url,
                "game_manifest_url": pair.game_manifest_url,
                "version": pair.version,
            },
            operation="remote_manifest_download",
        )
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.UPDATE,
            event_type="remote_min_environment_prepare_started",
            message="开始准备最小化运行环境",
            payload={"version": pair.version},
            operation="remote_min_environment",
        )
        result = original_prepare_lcu_game_data(preparer_self)
        duration_ms = int((datetime.now().astimezone() - started_at).total_seconds() * 1000)
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.LOAD_REMOTE_INDEX,
            event_type="remote_manifest_download_finished",
            message="remote manifest 下载完成",
            payload={
                "manifest_cache_path": str(getattr(result, "manifest_cache_path", "")),
                "duration_ms": duration_ms,
            },
            operation="remote_manifest_download",
        )
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.UPDATE,
            event_type="remote_min_environment_prepare_finished",
            message="最小化运行环境准备完成",
            payload={
                "prepared_lcu_root": str(getattr(result, "prepared_lcu_root", "")),
                "bundle_count": len(getattr(result, "bundle_cache_paths", tuple())),
                "description_cache_path": str(getattr(result, "description_cache_path", "")),
                "duration_ms": duration_ms,
            },
            operation="remote_min_environment",
        )
        return result

    def _wrapped_prepare_bin_inputs(preparer_self: object, **kwargs: object) -> object:
        started_at = datetime.now().astimezone()
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.UPDATE,
            event_type="remote_bin_prepare_started",
            message="开始处理 BIN 输入",
            payload={
                "target": kwargs.get("target"),
                "champion_ids": kwargs.get("champion_ids"),
                "map_ids": kwargs.get("map_ids"),
            },
            operation="remote_bin_prepare",
        )
        result = original_prepare_bin_inputs(preparer_self, **kwargs)
        duration_ms = int((datetime.now().astimezone() - started_at).total_seconds() * 1000)
        extracted_file_count = getattr(result, "extracted_file_count", 0) if result is not None else 0
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.UPDATE,
            event_type="remote_bin_prepare_finished",
            message="BIN 输入处理完成",
            payload={
                "target": kwargs.get("target"),
                "champion_ids": kwargs.get("champion_ids"),
                "map_ids": kwargs.get("map_ids"),
                "extracted_file_count": extracted_file_count,
                "duration_ms": duration_ms,
            },
            operation="remote_bin_prepare",
        )
        return result

    def _wrapped_update(opts: object, *, target: str = "all") -> None:
        started_at = datetime.now().astimezone()
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.UPDATE,
            event_type="remote_update_started",
            message="开始执行 remote update 主线",
            payload={
                "target": target,
                "champion_ids": getattr(opts, "champion_ids", None),
                "map_ids": getattr(opts, "map_ids", None),
            },
            operation="remote_update",
        )
        original_update(opts, target=target)
        duration_ms = int((datetime.now().astimezone() - started_at).total_seconds() * 1000)
        _emit_remote_phase_event(
            log_ctx=log_ctx,
            stage=PipelineStage.UPDATE,
            event_type="remote_update_finished",
            message="remote update 主线完成",
            payload={
                "target": target,
                "champion_ids": getattr(opts, "champion_ids", None),
                "map_ids": getattr(opts, "map_ids", None),
                "duration_ms": duration_ms,
            },
            operation="remote_update",
        )

    setattr(remote_preparer_cls, "prepare_lcu_game_data", _wrapped_prepare_lcu_game_data)
    setattr(remote_preparer_cls, "prepare_bin_inputs", _wrapped_prepare_bin_inputs)
    if callable(original_update):
        setattr(app, "update", _wrapped_update)

    def _restore() -> None:
        setattr(remote_preparer_cls, "prepare_lcu_game_data", original_prepare_lcu_game_data)
        setattr(remote_preparer_cls, "prepare_bin_inputs", original_prepare_bin_inputs)
        if callable(original_update):
            setattr(app, "update", original_update)

    return _restore


def _preview_remote_work_item_count(
    *,
    app: object,
    extract_options: object | None,
    mapping_options: object | None,
    config: PipelineRunConfig,
) -> int | None:
    """预估 remote 单位循环待处理项数量。"""

    explicit_target_count = len(config.champion_ids or tuple()) + len(config.map_ids or tuple())
    if explicit_target_count > 0:
        return explicit_target_count
    build_items = getattr(app, "build_remote_entity_work_items", None)
    if not callable(build_items):
        return None
    try:
        work_items = build_items(
            extract_options=extract_options,
            mapping_options=mapping_options,
            extract_include_champions=config.include_champions,
            extract_include_maps=config.include_maps,
            mapping_include_champions=config.include_champions,
            mapping_include_maps=config.include_maps,
        )
    except Exception:  # noqa: BLE001
        return None
    return len(cast(list[object], work_items))


def _should_prepare_full_fallback(config: PipelineRunConfig) -> bool:
    """判断当前 remote 配置是否处于“无显式 IDs 的全量 fallback”场景。"""

    if _has_explicit_remote_targets(config):
        return False
    return config.include_champions or config.include_maps


def _has_explicit_remote_targets(config: PipelineRunConfig) -> bool:
    """判断当前配置是否已携带显式实体 ID。"""

    return bool(config.champion_ids) or bool(config.map_ids)


def _materialize_remote_target_config(
    *,
    app: object,
    config: PipelineRunConfig,
) -> PipelineRunConfig:
    """基于当前 `data.msgpack` 物化 remote 全量模式的显式实体 ID。"""

    create_reader = getattr(app, "_create_reader", None)
    if not callable(create_reader):
        return config
    reader = create_reader()
    champion_ids = config.champion_ids
    map_ids = config.map_ids
    if champion_ids is None and config.include_champions:
        champion_ids = _collect_reader_entity_ids(getattr(reader, "get_champions", None))
    if map_ids is None and config.include_maps:
        map_ids = _collect_reader_entity_ids(getattr(reader, "get_maps", None))
    if not champion_ids and not map_ids:
        return config
    return replace(
        config,
        champion_ids=champion_ids or None,
        map_ids=map_ids or None,
    )


def _collect_reader_entity_ids(get_entities: object) -> tuple[int, ...]:
    """从 `DataReader` 的实体迭代结果提取稳定 ID 列表。"""

    if not callable(get_entities):
        return tuple()
    entity_ids: list[int] = []
    for entity in get_entities():
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("id")
        if entity_id is None:
            continue
        entity_ids.append(int(entity_id))
    return tuple(entity_ids)


def _emit_remote_phase_event(
    *,
    log_ctx: PipelineLogContext,
    stage: PipelineStage,
    event_type: str,
    message: str,
    payload: dict[str, object],
    operation: str,
) -> None:
    """发出 remote 主线阶段事件。"""

    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=stage,
            event_type=event_type,
            message=message,
            payload=payload,
            created_at=datetime.now().astimezone().isoformat(),
            status_hint="running",
            operation=operation,
        ),
    )
