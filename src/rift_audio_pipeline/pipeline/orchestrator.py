"""主流程编排模块。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from queue import Empty
from queue import Full
from queue import Queue
import shutil
import threading
import time

from loguru import logger

from rift_audio_pipeline.asset_downloader import download_game_content_metadata
from rift_audio_pipeline.asset_downloader import download_game_wads_by_runtime_paths
from rift_audio_pipeline.asset_downloader import download_lcu_data_wads
from rift_audio_pipeline.audio_processor import resolve_processing_targets
from rift_audio_pipeline.audio_processor import resolve_all_processing_targets
from rift_audio_pipeline.audio_processor import resolve_runtime_wad_paths
from rift_audio_pipeline.audio_processor import run_bin_updater
from rift_audio_pipeline.audio_processor import run_data_updater
from rift_audio_pipeline.audio_processor import run_unpack
from rift_audio_pipeline.baidu.sdk import ensure_official_sdk_path
from rift_audio_pipeline.baidu.oauth import resolve_token_store
from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.bin_extractor import create_local_bin_flag
from rift_audio_pipeline.bin_extractor import seed_bin_input_from_directory
from rift_audio_pipeline.config import PipelineConfig
from rift_audio_pipeline.game_dir_builder import build_simulated_dir
from rift_audio_pipeline.game_dir_builder import check_local_game_path
from rift_audio_pipeline.game_dir_builder import check_disk_space
from rift_audio_pipeline.game_dir_builder import cleanup_lcu_data_wads
from rift_audio_pipeline.game_dir_builder import cleanup_updater_inputs
from rift_audio_pipeline.game_dir_builder import write_content_metadata
from rift_audio_pipeline.manifest_ops import DECISION_REASON_FIRST_RUN
from rift_audio_pipeline.manifest_ops import DECISION_REASON_GAME_VERSION_UNCHANGED
from rift_audio_pipeline.manifest_ops import DECISION_REASON_NO_REGION_MANIFEST_CHANGES
from rift_audio_pipeline.manifest_ops import DEFAULT_LOCAL_STATE_FILE
from rift_audio_pipeline.manifest_ops import build_local_state
from rift_audio_pipeline.manifest_ops import evaluate_update_need
from rift_audio_pipeline.manifest_ops import extract_changed_entities_from_wad_paths
from rift_audio_pipeline.manifest_ops import filter_wad_changes_by_bin_voice_paths
from rift_audio_pipeline.manifest_ops import save_local_state
from rift_audio_pipeline.packer import pack_champion
from rift_audio_pipeline.pipeline.upload import PENDING_MANIFEST_SYNC_QUEUE_FILE_NAME
from rift_audio_pipeline.pipeline.upload import UPLOAD_MANIFEST_FILE_NAME
from rift_audio_pipeline.pipeline.upload import UPLOAD_MANIFEST_TEXT_FILE_NAME
from rift_audio_pipeline.pipeline.upload import _finalize_upload_manifest
from rift_audio_pipeline.pipeline.upload import _initialize_remote_upload_layout
from rift_audio_pipeline.pipeline.upload import _pack_unpacked_outputs
from rift_audio_pipeline.pipeline.upload import _preflight_remote_upload_index
from rift_audio_pipeline.pipeline.upload import _process_archives_upload
from rift_audio_pipeline.pipeline.upload import _resolve_default_upload_resource_type
from rift_audio_pipeline.pipeline.upload import _resolve_pack_archive_type
from rift_audio_pipeline.pipeline.upload import _resolve_pack_extra_files
from rift_audio_pipeline.pipeline.upload import _resolve_package_output_root
from rift_audio_pipeline.pipeline.upload import _resolve_upload_remote_index
from rift_audio_pipeline.pipeline.upload import _retry_pending_manifest_sync_queue
from rift_audio_pipeline.pipeline.upload import _upload_archives_and_manifest
from rift_audio_pipeline.pipeline.upload import _write_and_upload_update_log_files
from rift_audio_pipeline.pipeline.utils import _build_runtime_wad_paths_from_manifest_paths
from rift_audio_pipeline.pipeline.utils import _cleanup_simulated_runtime_files
from rift_audio_pipeline.pipeline.utils import _cleanup_version_audio_outputs
from rift_audio_pipeline.pipeline.utils import _current_utc_timestamp
from rift_audio_pipeline.pipeline.utils import _merge_runtime_wad_paths
from rift_audio_pipeline.pipeline.utils import _normalize_pipeline_game_version

STREAMING_UPLOAD_QUEUE_SIZE = 1
STREAMING_DISK_SPACE_MULTIPLIER = 3
STREAMING_MIN_REQUIRED_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _StreamingEntityTask:
    """低磁盘流式模式中的单实体任务。"""

    target: str
    entity_id: int
    champion_ids: tuple[int, ...]
    map_ids: tuple[int, ...]
    runtime_wad_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PackedEntityArtifact:
    """单实体打包结果。"""

    task: _StreamingEntityTask
    archive_path: Path


def run_pipeline(config: PipelineConfig) -> int:
    """执行流水线主入口。

    Args:
        config: 流水线配置对象。

    Returns:
        退出状态码，`0` 表示执行成功。
    """

    config.output_path.mkdir(parents=True, exist_ok=True)
    sdk_dir = ensure_official_sdk_path()
    logger.info("已加载百度官方 SDK 目录：{}", sdk_dir)

    try:
        decision = evaluate_update_need(
            region=config.game_region,
            state_file=DEFAULT_LOCAL_STATE_FILE,
        )
    except Exception as error:
        logger.error("更新判定失败，error={}", error)
        return 1
    latest = decision.latest_versions
    logger.info(
        "最新版本：GAME={} LCU={}（region={}）",
        latest.game_version,
        latest.lcu_version,
        config.game_region,
    )
    pipeline_game_version = _normalize_pipeline_game_version(latest.game_version)

    if not decision.should_update:
        saved_state = build_local_state(latest_versions=latest)
        saved_file = save_local_state(state=saved_state, state_file=DEFAULT_LOCAL_STATE_FILE)
        if decision.reason == DECISION_REASON_GAME_VERSION_UNCHANGED:
            logger.info("无需更新：GAME 版本未变化，已同步状态文件：{}", saved_file)
        elif decision.reason == DECISION_REASON_NO_REGION_MANIFEST_CHANGES:
            logger.info(
                "无需更新：版本变化但 {} 语音清单无变更，已同步状态文件：{}",
                config.game_region,
                saved_file,
            )
        else:
            logger.info("无需更新：reason={}，已同步状态文件：{}", decision.reason, saved_file)
        return 0

    secondary_filter_result = None
    secondary_unpack_paths: tuple[str, ...] | None = None
    secondary_filter_version_dir: Path | None = None
    target_manifest_paths_override: tuple[str, ...] | None = None
    if decision.reason == DECISION_REASON_FIRST_RUN:
        logger.info("检测到首次启动（无历史状态），将进入首次全量更新流程。")
    else:
        logger.info(
            "检测到 {} 语音变更：champion_count={}, map_count={}, added_wad={}, changed_wad={}, removed_wad={}, update_wad={}",
            config.game_region,
            len(decision.changed_entities.champion_aliases),
            len(decision.changed_entities.map_ids),
            len(decision.wad_changes.added_paths),
            len(decision.wad_changes.changed_paths),
            len(decision.wad_changes.removed_paths),
            len(decision.wad_changes.update_paths),
        )
        if decision.changed_entities.champion_aliases:
            logger.info("变更英雄：{}", ", ".join(decision.changed_entities.champion_aliases))
        if decision.changed_entities.map_ids:
            logger.info("变更地图：{}", ", ".join(decision.changed_entities.map_ids))

        if decision.previous_state is not None and decision.wad_changes.update_paths:
            update_wad_count = len(decision.wad_changes.update_paths)
            threshold = config.diff_bin_filter_threshold
            should_skip_secondary_filter = threshold > 0 and update_wad_count >= threshold
            if should_skip_secondary_filter:
                target_manifest_paths_override = tuple(decision.wad_changes.update_paths)
                logger.info(
                    "清单层 WAD 更新数达到阈值，跳过 WADExtractor 二次筛选：wad_count={}, threshold={}，改走 diff 列表完整下载解包",
                    update_wad_count,
                    threshold,
                )
            else:
                logger.info(
                    "开始 WAD 二次筛选：wad_count={}, threshold={}, unit_workers={}, extract_concurrency={}",
                    update_wad_count,
                    threshold,
                    config.diff_bin_filter_workers,
                    config.diff_bin_extract_concurrency,
                )
                try:
                    secondary_filter = filter_wad_changes_by_bin_voice_paths(
                        old_manifest_url=decision.previous_state.game_manifest_url,
                        new_manifest_url=latest.game_manifest_url,
                        region=config.game_region,
                        update_paths=decision.wad_changes.update_paths,
                        unit_max_workers=config.diff_bin_filter_workers,
                        extractor_prefetch_chunk_concurrency=config.diff_bin_extract_concurrency,
                        bin_output_dir=config.output_path
                        / "manifest"
                        / pipeline_game_version
                        / "bin_input",
                    )
                except Exception as error:  # noqa: BLE001
                    logger.error("WAD 二次筛选失败，error={}", error)
                    return 1

                logger.info(
                    "WAD 二次筛选结果：需解包={}, 可跳过={}",
                    len(secondary_filter.unpack_paths),
                    len(secondary_filter.skipped_paths),
                )
                if secondary_filter.unpack_paths:
                    logger.info("需解包 WAD：{}", ", ".join(secondary_filter.unpack_paths))
                    secondary_filter_result = secondary_filter
                    secondary_unpack_paths = secondary_filter.unpack_paths
                    target_manifest_paths_override = secondary_filter.unpack_paths
                    secondary_filter_version_dir = (
                        config.output_path / "manifest" / pipeline_game_version
                    )
                    create_local_bin_flag(version_dir=secondary_filter_version_dir)
                    matched_auto_bin_paths = {
                        path.strip().replace("\\", "/").casefold()
                        for decision_item in secondary_filter.decisions
                        if decision_item.should_unpack
                        for path in decision_item.matched_bin_paths
                        if isinstance(path, str) and path.strip()
                    }
                    logger.info(
                        "二次筛选 BIN 预写入完成：version_dir={}, matched_count={}",
                        secondary_filter_version_dir,
                        len(matched_auto_bin_paths),
                    )
                if secondary_filter.skipped_paths:
                    logger.info("可跳过 WAD：{}", ", ".join(secondary_filter.skipped_paths))

                if not secondary_filter.unpack_paths:
                    saved_state = build_local_state(latest_versions=latest)
                    saved_file = save_local_state(
                        state=saved_state, state_file=DEFAULT_LOCAL_STATE_FILE
                    )
                    logger.info(
                        "二次筛选后无需资源更新（仅 events 或无音频变化），已同步状态文件：{}",
                        saved_file,
                    )
                    return 0

    if config.dry_run:
        logger.info("dry-run 启用：仅做更新判定，不执行后续任务。")
        return 0
    if not config.enable_pack or not config.enable_upload:
        logger.error(
            "检测到版本更新，但当前流程要求必须启用打包与上传：--enable-pack --enable-upload"
        )
        return 1
    allow_missing_remote_index = decision.reason == DECISION_REASON_FIRST_RUN
    package_root = _resolve_package_output_root(
        config=config,
        game_version=pipeline_game_version,
    )
    pending_manifest_sync_queue_file = (
        config.output_path / "state" / PENDING_MANIFEST_SYNC_QUEUE_FILE_NAME
    )
    preloaded_remote_index: dict[str, dict[str, object]] = {}
    try:
        preloaded_remote_index = _preflight_remote_upload_index(
            config=config,
            package_root=package_root,
            allow_missing_remote_index=allow_missing_remote_index,
        )
        _retry_pending_manifest_sync_queue(
            config=config,
            queue_file=pending_manifest_sync_queue_file,
        )
    except Exception as error:  # noqa: BLE001
        logger.error("更新确认阶段远端索引预检失败，error={}", error)
        return 1

    runtime_game_path, runtime_is_simulated = _resolve_runtime_game_path(
        config=config,
        latest_game_version=latest.game_version,
    )
    if not check_local_game_path(runtime_game_path):
        logger.error("游戏目录不完整，无法执行后续流程：{}", runtime_game_path)
        return 1

    runtime_download_dir = _build_runtime_download_dir(
        runtime_game_path=runtime_game_path,
        game_version=pipeline_game_version,
        region=config.game_region,
        runtime_is_simulated=runtime_is_simulated,
    )
    game_download_dir, lcu_download_dir = _resolve_runtime_download_dirs(
        runtime_download_dir=runtime_download_dir,
        runtime_is_simulated=runtime_is_simulated,
    )
    if runtime_is_simulated:
        try:
            removed_stale_lcu_wads = cleanup_lcu_data_wads(
                game_path=runtime_game_path,
                region=config.game_region,
            )
            if removed_stale_lcu_wads > 0:
                logger.info("下载前已清理历史 LCU WAD：removed_count={}", removed_stale_lcu_wads)
            metadata_file = download_game_content_metadata(
                game_manifest_url=latest.game_manifest_url,
                download_dir=game_download_dir,
                game_path=runtime_game_path,
                concurrency_limit=config.download_concurrency,
            )
            lcu_wads = download_lcu_data_wads(
                lcu_manifest_url=latest.lcu_manifest_url,
                download_dir=lcu_download_dir,
                game_path=runtime_game_path,
                region=config.game_region,
                concurrency_limit=config.download_concurrency,
            )
        except Exception as error:  # noqa: BLE001
            logger.error("最小游戏目录基础资源下载失败，error={}", error)
            return 1
        logger.info(
            "最小游戏目录基础资源下载完成：metadata={}, lcu_wad_count={}",
            metadata_file,
            len(lcu_wads),
        )

    try:
        logger.debug(
            "开始执行 DataUpdater：game_path={}, output_path={}, region={}",
            runtime_game_path,
            config.output_path,
            config.game_region,
        )
        data_file_base = run_data_updater(
            game_path=runtime_game_path,
            output_path=config.output_path,
            region=config.game_region,
            force_update=False,
        )
    except Exception as error:  # noqa: BLE001
        logger.error("DataUpdater 执行失败，error={}", error)
        return 1
    data_version = data_file_base.parent.name.strip()
    if data_version:
        if data_version != pipeline_game_version:
            logger.info(
                "本地路径版本已按 DataUpdater 目录修正：expected={}, actual={}",
                pipeline_game_version,
                data_version,
            )
        pipeline_game_version = data_version
    if runtime_is_simulated:
        removed_lcu_data_wads = cleanup_lcu_data_wads(
            game_path=runtime_game_path,
            region=config.game_region,
        )
        logger.info("DataUpdater 后已清理 LCU 输入 WAD：removed_count={}", removed_lcu_data_wads)

    if secondary_filter_result is not None and secondary_filter_version_dir is not None:
        if data_file_base.parent != secondary_filter_version_dir:
            logger.error(
                "二次筛选 BIN 预写入版本目录与 DataUpdater 结果不一致：expected={}, actual={}",
                secondary_filter_version_dir,
                data_file_base.parent,
            )
            return 1

    if config.local_bin_dir is not None:
        try:
            written_bins = seed_bin_input_from_directory(
                version_dir=data_file_base.parent,
                source_dir=config.local_bin_dir,
                enable_local_bin=True,
            )
        except Exception as error:  # noqa: BLE001
            logger.error("本地 bin 注入失败，error={}", error)
            return 1
        logger.info(
            "本地 bin 注入完成：source={}, written_count={}",
            config.local_bin_dir,
            len(written_bins),
        )

    target_entities = (
        extract_changed_entities_from_wad_paths(target_manifest_paths_override)
        if target_manifest_paths_override is not None
        else decision.changed_entities
    )
    targets = resolve_processing_targets(
        data_file_base=data_file_base,
        champion_aliases=target_entities.champion_aliases,
        map_ids=target_entities.map_ids,
    )
    if config.low_disk_mode and not (targets.champion_ids or targets.map_ids):
        targets = resolve_all_processing_targets(data_file_base=data_file_base)

    runtime_wad_paths: tuple[str, ...] = tuple()
    if runtime_is_simulated:
        runtime_wad_targets = targets
        if not (runtime_wad_targets.champion_ids or runtime_wad_targets.map_ids):
            runtime_wad_targets = resolve_all_processing_targets(data_file_base=data_file_base)
        runtime_wad_paths = resolve_runtime_wad_paths(
            data_file_base=data_file_base,
            region=config.game_region,
            champion_ids=runtime_wad_targets.champion_ids,
            map_ids=runtime_wad_targets.map_ids,
            include_root_wad=secondary_filter_result is None,
        )
        if secondary_unpack_paths is not None:
            runtime_wad_paths = _merge_runtime_wad_paths(
                runtime_wad_paths,
                _build_runtime_wad_paths_from_manifest_paths(
                    manifest_paths=secondary_unpack_paths,
                    region=config.game_region,
                    include_root_wad=False,
                ),
            )
        if not runtime_wad_paths:
            logger.error("未解析到可下载的 GAME WAD 路径，无法继续模拟目录解包。")
            return 1
        removed_stale_runtime_wads = _cleanup_task_runtime_wads(
            runtime_game_path=runtime_game_path,
            runtime_wad_paths=runtime_wad_paths,
        )
        if removed_stale_runtime_wads > 0:
            logger.info("下载前已清理历史 GAME WAD：removed_count={}", removed_stale_runtime_wads)
        try:
            game_wads = download_game_wads_by_runtime_paths(
                game_manifest_url=latest.game_manifest_url,
                download_dir=game_download_dir,
                game_path=runtime_game_path,
                runtime_wad_paths=runtime_wad_paths,
                concurrency_limit=config.download_concurrency,
            )
        except Exception as error:  # noqa: BLE001
            logger.error("最小游戏目录 GAME WAD 下载失败，error={}", error)
            return 1
        logger.info(
            "最小游戏目录 GAME WAD 下载完成：target_count={}, staged_count={}",
            len(runtime_wad_paths),
            len(game_wads),
        )

    streaming_mode = _should_enable_streaming_mode(
        config=config,
        runtime_is_simulated=runtime_is_simulated,
        targets=targets,
    )
    upload_manifest: Path | None = None
    upload_run_records: list[dict[str, object]] = []
    effective_unpack_workers = _resolve_effective_unpack_workers(
        configured_workers=config.unpack_workers,
        runtime_is_simulated=runtime_is_simulated,
    )
    try:
        run_bin_updater(
            champion_ids=targets.champion_ids,
            map_ids=targets.map_ids,
            force_update=False,
            process_events=False,
        )
        if runtime_is_simulated:
            removed_lcu_wads, removed_bin_files = cleanup_updater_inputs(
                game_path=runtime_game_path,
                version_dir=data_file_base.parent,
            )
            logger.info(
                "已清理 Updater 输入数据：lcu_wad_count={}, bin_file_count={}",
                removed_lcu_wads,
                removed_bin_files,
            )

        if streaming_mode:
            upload_manifest = _run_streaming_unpack_pack_upload(
                config=config,
                game_version=pipeline_game_version,
                data_file_base=data_file_base,
                targets=targets,
                runtime_game_path=runtime_game_path,
                runtime_wad_paths=runtime_wad_paths,
                include_root_wad=secondary_filter_result is None,
                unpack_workers=effective_unpack_workers,
                allow_missing_remote_index=allow_missing_remote_index,
                run_record_collector=upload_run_records,
                preloaded_remote_index=preloaded_remote_index,
                pending_manifest_sync_queue_file=pending_manifest_sync_queue_file,
            )
        else:
            run_unpack(
                champion_ids=targets.champion_ids,
                map_ids=targets.map_ids,
                max_workers=effective_unpack_workers,
            )
        if runtime_is_simulated:
            removed_runtime_wads, removed_download_cache = _cleanup_simulated_runtime_files(
                runtime_game_path=runtime_game_path,
                runtime_download_dir=runtime_download_dir,
            )
            logger.info(
                "解包后已清理模拟目录临时文件：runtime_wad_count={}, download_cache_count={}",
                removed_runtime_wads,
                removed_download_cache,
            )
    except Exception as error:  # noqa: BLE001
        logger.error("解包阶段失败，error={}", error)
        return 1

    if streaming_mode:
        if upload_manifest is not None:
            logger.info("上传阶段执行完成：manifest_file={}", upload_manifest)
    else:
        try:
            archives = _pack_unpacked_outputs(config=config, game_version=pipeline_game_version)
        except Exception as error:  # noqa: BLE001
            logger.error("打包阶段失败，error={}", error)
            return 1
        logger.info("打包阶段执行完成：archive_count={}", len(archives))
        removed_audio_files = _cleanup_version_audio_outputs(
            version_audio_dir=config.output_path / "audios" / pipeline_game_version
        )
        logger.info("打包后已清理音频目录文件：removed_count={}", removed_audio_files)
        try:
            upload_manifest = _upload_archives_and_manifest(
                config=config,
                game_version=pipeline_game_version,
                archives=archives,
                allow_missing_remote_index=allow_missing_remote_index,
                run_record_collector=upload_run_records,
                preloaded_remote_index=preloaded_remote_index,
                pending_manifest_sync_queue_file=pending_manifest_sync_queue_file,
            )
        except Exception as error:  # noqa: BLE001
            logger.error("上传阶段失败，error={}", error)
            return 1
        if upload_manifest is not None:
            logger.info("上传阶段执行完成：manifest_file={}", upload_manifest)

    try:
        update_log_json, update_log_text = _write_and_upload_update_log_files(
            config=config,
            decision=decision,
            game_version=pipeline_game_version,
            target_entities=target_entities,
            targets=targets,
            secondary_filter_result=secondary_filter_result,
            upload_run_records=upload_run_records,
        )
        logger.info(
            "更新日志已生成并上传：json_file={}, text_file={}",
            update_log_json,
            update_log_text,
        )
    except Exception as error:  # noqa: BLE001
        logger.error("更新日志阶段失败，error={}", error)

    saved_state = build_local_state(latest_versions=latest)
    saved_file = save_local_state(state=saved_state, state_file=DEFAULT_LOCAL_STATE_FILE)
    logger.info("解包阶段执行完成，已同步状态文件：{}", saved_file)
    return 0


def _should_enable_streaming_mode(
    config: PipelineConfig,
    runtime_is_simulated: bool,
    targets: object,
) -> bool:
    """判定是否启用低磁盘流式模式。"""

    has_targets = bool(
        getattr(targets, "champion_ids", tuple()) or getattr(targets, "map_ids", tuple())
    )
    if not (config.low_disk_mode and has_targets):
        return False
    if runtime_is_simulated:
        return True
    logger.info("检测到真实游戏目录，跳过低磁盘流式模式并切换为批量处理。")
    return False


def _resolve_effective_unpack_workers(
    configured_workers: int,
    runtime_is_simulated: bool,
) -> int:
    """解析本次运行实际生效的解包并发数。"""

    if runtime_is_simulated:
        return configured_workers

    cpu_workers = max(1, os.cpu_count() or configured_workers)
    effective_workers = max(configured_workers, cpu_workers)
    if effective_workers != configured_workers:
        logger.info(
            "检测到真实游戏目录，解包并发自动提升：configured={}, effective={}",
            configured_workers,
            effective_workers,
        )
    return effective_workers


def _run_streaming_unpack_pack_upload(
    config: PipelineConfig,
    game_version: str,
    data_file_base: Path,
    targets: object,
    runtime_game_path: Path,
    runtime_wad_paths: tuple[str, ...],
    include_root_wad: bool,
    unpack_workers: int,
    allow_missing_remote_index: bool,
    run_record_collector: list[dict[str, object]],
    preloaded_remote_index: dict[str, dict[str, object]] | None = None,
    pending_manifest_sync_queue_file: Path | None = None,
) -> Path | None:
    """执行实体级流式流水线：解包 -> 打包 -> 上传 -> 清理。"""

    tasks = _build_streaming_entity_tasks(
        data_file_base=data_file_base,
        region=config.game_region,
        targets=targets,
        runtime_wad_paths=runtime_wad_paths,
        include_root_wad=include_root_wad,
    )
    if not tasks:
        logger.warning("低磁盘流式模式跳过：无可处理实体。")
        return None

    logger.info(
        "低磁盘流式模式启用：entity_count={}, upload_queue_size={}, unpack_workers={}",
        len(tasks),
        STREAMING_UPLOAD_QUEUE_SIZE,
        unpack_workers,
    )
    extra_files = _resolve_pack_extra_files(config=config)
    archive_audio_type = _resolve_pack_archive_type(config=config)
    if extra_files:
        logger.info("打包附加文件已启用：{}", ", ".join(str(item) for item in extra_files))
    if archive_audio_type is not None:
        logger.info("打包命名类型后缀：{}", archive_audio_type)

    upload_errors: list[Exception] = []
    upload_queue: Queue[_PackedEntityArtifact | None] = Queue(maxsize=STREAMING_UPLOAD_QUEUE_SIZE)
    upload_manifest_holder: list[Path | None] = [None]
    upload_thread = threading.Thread(
        name="streaming-upload-worker",
        target=_run_streaming_upload_worker,
        kwargs={
            "config": config,
            "game_version": game_version,
            "upload_queue": upload_queue,
            "upload_errors": upload_errors,
            "upload_manifest_holder": upload_manifest_holder,
            "allow_missing_remote_index": allow_missing_remote_index,
            "run_record_collector": run_record_collector,
            "preloaded_remote_index": preloaded_remote_index,
            "pending_manifest_sync_queue_file": pending_manifest_sync_queue_file,
        },
        daemon=True,
    )
    upload_thread.start()
    sentinel_enqueued = False

    try:
        for task in tasks:
            if upload_errors:
                raise RuntimeError("流式上传线程执行失败，已停止后续实体处理。") from upload_errors[
                    0
                ]

            _ensure_streaming_disk_space(
                config=config,
                game_version=game_version,
                runtime_game_path=runtime_game_path,
                task=task,
            )
            run_unpack(
                champion_ids=task.champion_ids,
                map_ids=task.map_ids,
                max_workers=unpack_workers,
            )
            artifact, entity_audio_dir, report_file = _pack_single_streaming_entity(
                config=config,
                game_version=game_version,
                task=task,
                extra_files=extra_files,
                archive_audio_type=archive_audio_type,
            )
            removed_wad_count = _cleanup_task_runtime_wads(
                runtime_game_path=runtime_game_path,
                runtime_wad_paths=task.runtime_wad_paths,
            )
            removed_audio_files = _cleanup_entity_audio_output(
                entity_audio_dir=entity_audio_dir,
                report_file=report_file,
            )
            # WAD 生命周期由 lol-audio-unpack 的实体解包流程判定；
            # 单实体解包完成后即可释放该任务关联资源，外层只负责回收。
            logger.info(
                "流式任务完成并入队上传：target={}, entity_id={}, removed_wad_count={}, removed_audio_count={}, archive={}",
                task.target,
                task.entity_id,
                removed_wad_count,
                removed_audio_files,
                artifact.archive_path,
            )
            _enqueue_streaming_upload_job(
                upload_queue=upload_queue,
                upload_errors=upload_errors,
                artifact=artifact,
            )

        _enqueue_streaming_upload_job(
            upload_queue=upload_queue,
            upload_errors=upload_errors,
            artifact=None,
        )
        sentinel_enqueued = True
        if not upload_errors:
            while upload_queue.unfinished_tasks > 0:
                logger.debug(
                    "等待流式上传队列完成：unfinished_tasks={}",
                    upload_queue.unfinished_tasks,
                )
                if upload_errors:
                    break
                if not upload_thread.is_alive():
                    raise RuntimeError(
                        "流式上传线程已退出但仍存在未完成任务："
                        f"unfinished_tasks={upload_queue.unfinished_tasks}"
                    )
                time.sleep(1)
        if upload_errors:
            raise RuntimeError("流式上传线程执行失败，流水线终止。") from upload_errors[0]
    finally:
        if upload_thread.is_alive() and (upload_errors or not sentinel_enqueued):
            _drain_streaming_upload_queue(upload_queue=upload_queue)
        upload_thread.join(timeout=5)
    return upload_manifest_holder[0]


def _build_streaming_entity_tasks(
    data_file_base: Path,
    region: str,
    targets: object,
    runtime_wad_paths: tuple[str, ...],
    include_root_wad: bool,
) -> tuple[_StreamingEntityTask, ...]:
    """构建流式模式所需的实体任务集合。"""

    runtime_wad_index = {item.casefold(): item for item in runtime_wad_paths}
    tasks: list[_StreamingEntityTask] = []
    champion_ids = tuple(int(item) for item in getattr(targets, "champion_ids", tuple()))
    map_ids = tuple(int(item) for item in getattr(targets, "map_ids", tuple()))

    for champion_id in champion_ids:
        task_runtime_paths = resolve_runtime_wad_paths(
            data_file_base=data_file_base,
            region=region,
            champion_ids=(champion_id,),
            map_ids=tuple(),
            include_root_wad=include_root_wad,
        )
        filtered_paths = tuple(
            runtime_wad_index.get(path.casefold(), path) for path in task_runtime_paths
        )
        tasks.append(
            _StreamingEntityTask(
                target="champions",
                entity_id=champion_id,
                champion_ids=(champion_id,),
                map_ids=tuple(),
                runtime_wad_paths=filtered_paths,
            )
        )
    for map_id in map_ids:
        task_runtime_paths = resolve_runtime_wad_paths(
            data_file_base=data_file_base,
            region=region,
            champion_ids=tuple(),
            map_ids=(map_id,),
            include_root_wad=include_root_wad,
        )
        filtered_paths = tuple(
            runtime_wad_index.get(path.casefold(), path) for path in task_runtime_paths
        )
        tasks.append(
            _StreamingEntityTask(
                target="maps",
                entity_id=map_id,
                champion_ids=tuple(),
                map_ids=(map_id,),
                runtime_wad_paths=filtered_paths,
            )
        )
    return tuple(tasks)


def _run_streaming_upload_worker(
    config: PipelineConfig,
    game_version: str,
    upload_queue: Queue[_PackedEntityArtifact | None],
    upload_errors: list[Exception],
    upload_manifest_holder: list[Path | None],
    allow_missing_remote_index: bool,
    run_record_collector: list[dict[str, object]],
    preloaded_remote_index: dict[str, dict[str, object]] | None = None,
    pending_manifest_sync_queue_file: Path | None = None,
) -> None:
    """消费流式打包产物并执行上传与压缩包清理。"""

    logger.debug("流式上传线程已启动：game_version={}", game_version)
    client: BaiduPanClient | None = None
    try:
        if not (
            config.baidu_pan_app_key and config.baidu_pan_secret_key and config.baidu_pan_refresh_token
        ):
            raise ValueError("上传阶段缺少百度凭据，请配置 app_key/secret_key/refresh_token")

        package_root = _resolve_package_output_root(config=config, game_version=game_version)
        manifest_file = package_root / UPLOAD_MANIFEST_FILE_NAME
        readable_manifest_file = package_root / UPLOAD_MANIFEST_TEXT_FILE_NAME
        credentials = BaiduCredentials(
            app_key=config.baidu_pan_app_key,
            secret_key=config.baidu_pan_secret_key,
            refresh_token=config.baidu_pan_refresh_token,
        )
        token_store = resolve_token_store()
        client = BaiduPanClient(
            credentials=credentials,
            remote_dir=config.baidu_pan_remote_dir,
            token_store=token_store,
        )
        _initialize_remote_upload_layout(client=client)
        remote_index = _resolve_upload_remote_index(
            client=client,
            package_root=package_root,
            allow_missing_remote_index=allow_missing_remote_index,
            preloaded_remote_index=preloaded_remote_index,
        )
        executed_at = _current_utc_timestamp()
        default_resource_type = _resolve_default_upload_resource_type(config=config)
        run_entries: list[dict[str, object]] = []
        has_index_changes = False

        while True:
            artifact = upload_queue.get()
            try:
                if artifact is None:
                    upload_manifest_holder[0] = _finalize_upload_manifest(
                        client=client,
                        manifest_file=manifest_file,
                        readable_manifest_file=readable_manifest_file,
                        game_version=game_version,
                        remote_dir=config.baidu_pan_remote_dir,
                        remote_index=remote_index,
                        run_entries=run_entries,
                        has_index_changes=has_index_changes,
                        executed_at=executed_at,
                        run_record_collector=run_record_collector,
                        refresh_remote_index_before_upload=preloaded_remote_index is not None,
                        pending_manifest_sync_queue_file=pending_manifest_sync_queue_file,
                    )
                    logger.debug("流式上传线程收到停止信号，已完成索引回传。")
                    return
                logger.debug(
                    "流式上传线程开始处理任务：target={}, entity_id={}, archive={}",
                    artifact.task.target,
                    artifact.task.entity_id,
                    artifact.archive_path,
                )
                current_entries, current_has_changes = _process_archives_upload(
                    client=client,
                    archives=(artifact.archive_path,),
                    remote_dir=config.baidu_pan_remote_dir,
                    game_version=game_version,
                    remote_index=remote_index,
                    executed_at=executed_at,
                    default_resource_type=default_resource_type,
                )
                if current_has_changes:
                    has_index_changes = True
                run_entries.extend(current_entries)
                _cleanup_uploaded_archive(artifact.archive_path)
                logger.info(
                    "流式上传完成并清理压缩包：target={}, entity_id={}, archive={}",
                    artifact.task.target,
                    artifact.task.entity_id,
                    artifact.archive_path,
                )
            finally:
                upload_queue.task_done()
    except Exception as error:  # noqa: BLE001
        logger.exception("流式上传线程异常：error={}", error)
        upload_errors.append(error)
    finally:
        if client is not None:
            client.close()


def _enqueue_streaming_upload_job(
    upload_queue: Queue[_PackedEntityArtifact | None],
    upload_errors: list[Exception],
    artifact: _PackedEntityArtifact | None,
) -> None:
    """将实体打包产物安全入队，避免上传线程异常导致阻塞。"""

    while True:
        if upload_errors:
            raise RuntimeError("流式上传线程异常，已停止入队。") from upload_errors[0]
        try:
            upload_queue.put(artifact, timeout=0.2)
            return
        except Full:
            continue


def _drain_streaming_upload_queue(upload_queue: Queue[_PackedEntityArtifact | None]) -> None:
    """在异常场景下尝试终止上传线程并释放队列阻塞。"""

    while True:
        try:
            upload_queue.put_nowait(None)
            return
        except Full:
            try:
                upload_queue.get_nowait()
                upload_queue.task_done()
            except Empty:
                continue


def _ensure_streaming_disk_space(
    config: PipelineConfig,
    game_version: str,
    runtime_game_path: Path,
    task: _StreamingEntityTask,
) -> None:
    """在流式任务启动前执行磁盘空间检查。"""

    required_bytes = _estimate_streaming_required_bytes(
        runtime_game_path=runtime_game_path,
        task=task,
    )
    package_root = _resolve_package_output_root(config=config, game_version=game_version)
    probe_dirs = tuple(
        {
            runtime_game_path.expanduser().resolve(),
            config.output_path.expanduser().resolve(),
            package_root.expanduser().resolve(),
        }
    )
    for probe in probe_dirs:
        probe.mkdir(parents=True, exist_ok=True)
        if check_disk_space(path=probe, required_bytes=required_bytes):
            continue
        raise RuntimeError(
            "流式任务磁盘空间不足："
            f"target={task.target}, entity_id={task.entity_id}, path={probe}, required_bytes={required_bytes}"
        )


def _estimate_streaming_required_bytes(
    runtime_game_path: Path,
    task: _StreamingEntityTask,
) -> int:
    """估算当前实体任务执行所需的最小可用磁盘空间。"""

    wad_total_bytes = 0
    for runtime_wad_path in task.runtime_wad_paths:
        wad_file = _resolve_runtime_wad_file(
            runtime_game_path=runtime_game_path,
            runtime_wad_path=runtime_wad_path,
        )
        if wad_file is None or not wad_file.is_file():
            continue
        wad_total_bytes += wad_file.stat().st_size
    estimated = wad_total_bytes * STREAMING_DISK_SPACE_MULTIPLIER
    return max(STREAMING_MIN_REQUIRED_BYTES, estimated)


def _resolve_runtime_wad_file(runtime_game_path: Path, runtime_wad_path: str) -> Path | None:
    """将运行时 WAD 路径转换为本地文件路径。"""

    normalized = runtime_wad_path.strip().replace("\\", "/")
    if not normalized:
        return None
    relative_path = normalized.removeprefix("Game/")
    if relative_path.startswith("/"):
        return None
    relative = Path(relative_path)
    if any(part == ".." for part in relative.parts):
        return None
    return runtime_game_path / relative


def _pack_single_streaming_entity(
    config: PipelineConfig,
    game_version: str,
    task: _StreamingEntityTask,
    extra_files: tuple[Path, ...],
    archive_audio_type: str | None,
) -> tuple[_PackedEntityArtifact, Path, Path | None]:
    """打包单实体输出并返回产物信息。"""

    entity_audio_dir = _resolve_entity_audio_directory(
        output_path=config.output_path,
        game_version=game_version,
        task=task,
    )
    report_file = (
        config.output_path
        / "reports"
        / game_version
        / task.target
        / f"_{task.entity_id}_metadata.yaml"
    )
    normalized_report_file = report_file if report_file.is_file() else None
    archive_name = _build_entity_archive_name(
        directory_name=entity_audio_dir.name,
        game_version=game_version,
        audio_type=archive_audio_type,
    )
    archive_path = pack_champion(
        champion_dir=entity_audio_dir,
        output_path=_resolve_package_output_root(config=config, game_version=game_version)
        / task.target,
        archive_name=archive_name,
        report_file=normalized_report_file,
        password=config.pack_password,
        encrypt_filenames=config.pack_encrypt_filenames,
        extra_files=extra_files,
    )
    return (
        _PackedEntityArtifact(task=task, archive_path=archive_path),
        entity_audio_dir,
        normalized_report_file,
    )


def _resolve_entity_audio_directory(
    output_path: Path,
    game_version: str,
    task: _StreamingEntityTask,
) -> Path:
    """定位当前实体对应的解包输出目录。"""

    target_root = output_path / "audios" / game_version / task.target
    if not target_root.is_dir():
        raise FileNotFoundError(f"流式打包失败：目录不存在：{target_root}")

    matched_dirs = tuple(
        item
        for item in target_root.iterdir()
        if item.is_dir() and _extract_entity_id_from_directory_name(item.name) == task.entity_id
    )
    if not matched_dirs:
        raise FileNotFoundError(
            "流式打包失败：未找到实体输出目录，"
            f"target={task.target}, entity_id={task.entity_id}, root={target_root}"
        )
    if len(matched_dirs) > 1:
        raise RuntimeError(
            "流式打包失败：实体输出目录冲突，"
            f"target={task.target}, entity_id={task.entity_id}, matched={matched_dirs}"
        )
    return matched_dirs[0]


def _extract_entity_id_from_directory_name(directory_name: str) -> int | None:
    """从目录名中解析实体 ID。"""

    prefix = directory_name.split("·", maxsplit=1)[0].strip()
    if prefix.isdigit():
        return int(prefix)
    return None


def _build_entity_archive_name(
    directory_name: str,
    game_version: str,
    audio_type: str | None,
) -> str:
    """构建单实体压缩包名称，规则与批量打包保持一致。"""

    parts = [directory_name]
    if game_version.strip():
        parts.append(game_version.strip())
    if isinstance(audio_type, str) and audio_type.strip():
        parts.append(audio_type.strip())
    return f"{'-'.join(parts)}.7z"


def _cleanup_task_runtime_wads(
    runtime_game_path: Path,
    runtime_wad_paths: tuple[str, ...],
) -> int:
    """清理单实体关联的运行时 WAD 文件。"""

    removed_count = 0
    for runtime_wad_path in runtime_wad_paths:
        wad_file = _resolve_runtime_wad_file(
            runtime_game_path=runtime_game_path,
            runtime_wad_path=runtime_wad_path,
        )
        if wad_file is None or not wad_file.is_file():
            continue
        wad_file.unlink()
        removed_count += 1
    return removed_count


def _cleanup_entity_audio_output(
    entity_audio_dir: Path,
    report_file: Path | None,
) -> int:
    """清理单实体解包目录与对应报告文件。"""

    removed_files = 0
    if entity_audio_dir.is_dir():
        for item in entity_audio_dir.rglob("*"):
            if item.is_file():
                removed_files += 1
        shutil.rmtree(entity_audio_dir, ignore_errors=True)
    if report_file is not None and report_file.is_file():
        report_file.unlink()
        removed_files += 1
    return removed_files


def _cleanup_uploaded_archive(archive_path: Path) -> None:
    """在上传成功后删除本地压缩包。"""

    archive_path.unlink(missing_ok=True)


def _resolve_runtime_game_path(
    config: PipelineConfig, latest_game_version: str
) -> tuple[Path, bool]:
    """解析本次运行使用的游戏目录。

    Returns:
        二元组 `(runtime_game_path, runtime_is_simulated)`。
    """

    if config.game_path is not None:
        return config.game_path, False

    simulated_base = (
        config.temp_dir
        if config.temp_dir is not None
        else (Path(__file__).resolve().parents[2] / "temp" / "mini_game")
    ).expanduser()
    simulated_dir = build_simulated_dir(simulated_base.resolve())
    write_content_metadata(game_path=simulated_dir, version=latest_game_version)
    logger.info("未提供本地游戏目录，已构建最小游戏目录：{}", simulated_dir)
    return simulated_dir, True


def _build_runtime_download_dir(
    runtime_game_path: Path,
    game_version: str,
    region: str,
    runtime_is_simulated: bool,
) -> Path:
    """构建运行时下载缓存目录。"""

    if runtime_is_simulated:
        return runtime_game_path
    return runtime_game_path.parent / "downloads" / game_version / region


def _resolve_runtime_download_dirs(
    runtime_download_dir: Path,
    runtime_is_simulated: bool,
) -> tuple[Path, Path]:
    """解析 GAME/LCU 下载目录。"""

    if runtime_is_simulated:
        return runtime_download_dir / "Game", runtime_download_dir / "LeagueClient"
    return runtime_download_dir / "game", runtime_download_dir / "lcu"
