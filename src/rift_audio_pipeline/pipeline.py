"""主流程编排模块。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
from queue import Empty
from queue import Full
from queue import Queue
import shutil
import threading

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
from rift_audio_pipeline.packer import pack_all
from rift_audio_pipeline.packer import pack_champion

DEFAULT_BUNDLED_PACK_EXTRA_DIR = Path(__file__).resolve().parent / "pack_extra"
DEFAULT_PACK_EXTRA_FILES = ("食用说明.txt", "license.txt")
UPLOAD_MANIFEST_FILE_NAME = "upload_manifest.json"
UPLOAD_MANIFEST_TEXT_FILE_NAME = "upload_manifest_readable.txt"
UPLOAD_MANIFEST_SCHEMA_VERSION = 2
RESOURCE_TYPE_BUCKETS = ("VO", "SFX", "MUSIC")
OLD_RESOURCE_BUCKET = "OLD"
RESOURCE_TARGET_GROUPS = ("champions", "maps")
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


@dataclass(frozen=True, slots=True)
class _ArchiveUploadLayout:
    """压缩包上传路由信息。"""

    remote_name: str
    remote_relative_path: str
    remote_path: str
    target_group: str
    resource_type: str
    entity_key: str


@dataclass(frozen=True, slots=True)
class _IndexedArchiveMetadata:
    """远端索引条目解析结果。"""

    remote_path: str
    remote_name: str
    game_version: str | None
    target_group: str | None
    resource_type: str | None
    entity_key: str | None
    is_old_bucket: bool


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
            try:
                secondary_filter = filter_wad_changes_by_bin_voice_paths(
                    old_manifest_url=decision.previous_state.game_manifest_url,
                    new_manifest_url=latest.game_manifest_url,
                    region=config.game_region,
                    update_paths=decision.wad_changes.update_paths,
                    bin_output_dir=config.output_path
                    / "manifest"
                    / latest.game_version
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
                secondary_filter_version_dir = config.output_path / "manifest" / latest.game_version
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

    runtime_game_path, runtime_is_simulated = _resolve_runtime_game_path(
        config=config,
        latest_game_version=latest.game_version,
    )
    if not check_local_game_path(runtime_game_path):
        logger.error("游戏目录不完整，无法执行后续流程：{}", runtime_game_path)
        return 1

    runtime_download_dir = _build_runtime_download_dir(
        runtime_game_path=runtime_game_path,
        game_version=latest.game_version,
        region=config.game_region,
    )
    if runtime_is_simulated:
        try:
            metadata_file = download_game_content_metadata(
                game_manifest_url=latest.game_manifest_url,
                download_dir=runtime_download_dir / "game",
                game_path=runtime_game_path,
            )
            lcu_wads = download_lcu_data_wads(
                lcu_manifest_url=latest.lcu_manifest_url,
                download_dir=runtime_download_dir / "lcu",
                game_path=runtime_game_path,
                region=config.game_region,
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
        data_file_base = run_data_updater(
            game_path=runtime_game_path,
            output_path=config.output_path,
            region=config.game_region,
            force_update=False,
        )
    except Exception as error:  # noqa: BLE001
        logger.error("DataUpdater 执行失败，error={}", error)
        return 1
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
        extract_changed_entities_from_wad_paths(secondary_unpack_paths)
        if secondary_unpack_paths is not None
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
        try:
            game_wads = download_game_wads_by_runtime_paths(
                game_manifest_url=latest.game_manifest_url,
                download_dir=runtime_download_dir / "game",
                game_path=runtime_game_path,
                runtime_wad_paths=runtime_wad_paths,
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
    allow_missing_remote_index = decision.reason == DECISION_REASON_FIRST_RUN
    upload_manifest: Path | None = None
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
                game_version=latest.game_version,
                data_file_base=data_file_base,
                targets=targets,
                runtime_game_path=runtime_game_path,
                runtime_wad_paths=runtime_wad_paths,
                include_root_wad=secondary_filter_result is None,
                unpack_workers=effective_unpack_workers,
                allow_missing_remote_index=allow_missing_remote_index,
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
            archives = _pack_unpacked_outputs(config=config, game_version=latest.game_version)
        except Exception as error:  # noqa: BLE001
            logger.error("打包阶段失败，error={}", error)
            return 1
        logger.info("打包阶段执行完成：archive_count={}", len(archives))
        removed_audio_files = _cleanup_version_audio_outputs(
            version_audio_dir=config.output_path / "audios" / latest.game_version
        )
        logger.info("打包后已清理音频目录文件：removed_count={}", removed_audio_files)
        try:
            upload_manifest = _upload_archives_and_manifest(
                config=config,
                game_version=latest.game_version,
                archives=archives,
                allow_missing_remote_index=allow_missing_remote_index,
            )
        except Exception as error:  # noqa: BLE001
            logger.error("上传阶段失败，error={}", error)
            return 1
        if upload_manifest is not None:
            logger.info("上传阶段执行完成：manifest_file={}", upload_manifest)

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
            upload_queue.join()
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
) -> None:
    """消费流式打包产物并执行上传与压缩包清理。"""

    while True:
        artifact = upload_queue.get()
        try:
            if artifact is None:
                return
            manifest_file = _upload_archives_and_manifest(
                config=config,
                game_version=game_version,
                archives=(artifact.archive_path,),
                allow_missing_remote_index=allow_missing_remote_index,
            )
            if manifest_file is not None:
                upload_manifest_holder[0] = manifest_file
            _cleanup_uploaded_archive(artifact.archive_path)
            logger.info(
                "流式上传完成并清理压缩包：target={}, entity_id={}, archive={}",
                artifact.task.target,
                artifact.task.entity_id,
                artifact.archive_path,
            )
        except Exception as error:  # noqa: BLE001
            upload_errors.append(error)
            return
        finally:
            upload_queue.task_done()


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
) -> Path:
    """构建运行时下载缓存目录。"""

    return runtime_game_path.parent / "downloads" / game_version / region


def _pack_unpacked_outputs(config: PipelineConfig, game_version: str) -> tuple[Path, ...]:
    """将当前版本解包产物按目录批量打包。"""

    version_audio_dir = config.output_path / "audios" / game_version
    if not version_audio_dir.is_dir():
        logger.warning("未找到可打包目录：{}", version_audio_dir)
        return tuple()

    if config.pack_output_dir is not None:
        pack_root = config.pack_output_dir
    else:
        pack_root = _resolve_package_output_root(config=config, game_version=game_version)

    archives: list[Path] = []
    extra_files = _resolve_pack_extra_files(config=config)
    archive_audio_type = _resolve_pack_archive_type(config=config)
    if extra_files:
        logger.info("打包附加文件已启用：{}", ", ".join(str(item) for item in extra_files))
    if archive_audio_type is not None:
        logger.info("打包命名类型后缀：{}", archive_audio_type)
    pack_targets = (
        (
            "champions",
            version_audio_dir / "champions",
            config.output_path / "reports" / game_version / "champions",
        ),
        (
            "maps",
            version_audio_dir / "maps",
            config.output_path / "reports" / game_version / "maps",
        ),
    )
    for target_name, target_dir, report_dir in pack_targets:
        if not target_dir.is_dir():
            continue
        target_output_dir = pack_root / target_name
        packed = pack_all(
            audio_dir=target_dir,
            output_dir=target_output_dir,
            version=game_version,
            audio_type=archive_audio_type,
            report_dir=report_dir,
            password=config.pack_password,
            encrypt_filenames=config.pack_encrypt_filenames,
            extra_files=extra_files,
        )
        archives.extend(packed)
        logger.info(
            "打包完成：target={}, source={}, archive_count={}",
            target_name,
            target_dir,
            len(packed),
        )

    return tuple(sorted(archives, key=lambda path: path.as_posix().casefold()))


def _upload_archives_and_manifest(
    config: PipelineConfig,
    game_version: str,
    archives: tuple[Path, ...],
    allow_missing_remote_index: bool = True,
) -> Path | None:
    """将打包产物上传到百度网盘，并同步本次上传清单。"""

    if not archives:
        logger.warning("上传阶段跳过：无可上传压缩包。")
        return None

    if not (
        config.baidu_pan_app_key and config.baidu_pan_secret_key and config.baidu_pan_refresh_token
    ):
        raise ValueError("上传阶段缺少百度凭据，请配置 app_key/secret_key/refresh_token")

    package_root = _resolve_package_output_root(config=config, game_version=game_version)
    manifest_file = package_root / UPLOAD_MANIFEST_FILE_NAME
    readable_manifest_file = package_root / UPLOAD_MANIFEST_TEXT_FILE_NAME
    run_entries: list[dict[str, object]] = []
    has_index_changes = False

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
    try:
        remote_index = _load_remote_upload_manifest_index(
            client=client,
            package_root=package_root,
            allow_missing_remote_index=allow_missing_remote_index,
        )
        executed_at = _current_utc_timestamp()
        _initialize_remote_upload_layout(client=client)
        default_resource_type = _resolve_default_upload_resource_type(config=config)
        for archive in archives:
            if not archive.is_file():
                raise FileNotFoundError(f"上传失败：压缩包不存在：{archive}")

            upload_layout = _build_archive_upload_layout(
                archive=archive,
                remote_dir=config.baidu_pan_remote_dir,
                default_resource_type=default_resource_type,
            )
            _ensure_remote_directory(
                client=client,
                relative_dir=f"{upload_layout.resource_type}/{upload_layout.target_group}",
            )
            archived_entries = _archive_remote_old_versions(
                client=client,
                remote_dir=config.baidu_pan_remote_dir,
                remote_index=remote_index,
                layout=upload_layout,
                expected_game_version=game_version,
                executed_at=executed_at,
            )
            if archived_entries:
                has_index_changes = True
                run_entries.extend(archived_entries)

            remote_name = upload_layout.remote_name
            remote_path = upload_layout.remote_path
            existing_entry = remote_index.get(remote_path.casefold())
            if existing_entry is not None:
                if _is_same_index_entry(
                    entry=existing_entry,
                    expected_remote_name=remote_name,
                    expected_game_version=game_version,
                ):
                    logger.info("远端索引命中同文件，跳过上传：{}", remote_path)
                    run_entries.append(
                        {
                            "local_path": str(archive),
                            "remote_path": remote_path,
                            "remote_name": remote_name,
                            "game_version": game_version,
                            "target_group": upload_layout.target_group,
                            "resource_type": upload_layout.resource_type,
                            "entity_key": upload_layout.entity_key,
                            "status": "skipped",
                        }
                    )
                    continue
                raise RuntimeError(
                    "上传阶段终止：远端索引存在同路径但版本不一致文件，"
                    f"remote_path={remote_path}, expected_game_version={game_version}"
                )

            if _remote_file_exists(client=client, remote_path=upload_layout.remote_relative_path):
                raise RuntimeError(
                    "上传阶段终止：检测到远端已存在同名文件但索引缺失，"
                    f"remote_path={remote_path}。请先修复远端索引后再重试。"
                )

            file_size = archive.stat().st_size
            file_sha256 = _calculate_sha256(archive)
            response = client.upload_file(
                local_path=archive, remote_path=upload_layout.remote_relative_path
            )
            has_index_changes = True
            remote_index[remote_path.casefold()] = {
                "remote_path": remote_path,
                "remote_name": remote_name,
                "bucket": upload_layout.resource_type,
                "game_version": game_version,
                "target_group": upload_layout.target_group,
                "resource_type": upload_layout.resource_type,
                "entity_key": upload_layout.entity_key,
                "size": file_size,
                "sha256": file_sha256,
                "uploaded_at": executed_at,
            }
            run_entries.append(
                {
                    "local_path": str(archive),
                    "remote_path": remote_path,
                    "remote_name": remote_name,
                    "size": file_size,
                    "sha256": file_sha256,
                    "target_group": upload_layout.target_group,
                    "resource_type": upload_layout.resource_type,
                    "entity_key": upload_layout.entity_key,
                    "status": "uploaded",
                    "response": response,
                }
            )

        manifest_payload = _build_upload_manifest_payload(
            game_version=game_version,
            index=remote_index,
            run_entries=run_entries,
            executed_at=executed_at,
        )
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        readable_manifest_file.write_text(
            _build_readable_upload_manifest_content(
                index=remote_index,
                game_version=game_version,
                executed_at=executed_at,
                remote_dir=config.baidu_pan_remote_dir,
            ),
            encoding="utf-8",
        )
        if has_index_changes:
            client.upload_file(local_path=manifest_file, remote_path=UPLOAD_MANIFEST_FILE_NAME)
            client.upload_file(
                local_path=readable_manifest_file,
                remote_path=UPLOAD_MANIFEST_TEXT_FILE_NAME,
            )
        else:
            logger.info("远端索引无变化，跳过索引文件回传。")
        return manifest_file
    finally:
        client.close()


def _resolve_package_output_root(config: PipelineConfig, game_version: str) -> Path:
    """解析当前版本打包产物根目录。"""

    if config.pack_output_dir is not None:
        return config.pack_output_dir
    return config.output_path / "packages" / game_version


def _resolve_pack_extra_files(config: PipelineConfig) -> tuple[Path, ...]:
    """解析打包附加文件列表。"""

    candidate_dirs: list[Path] = []
    if config.pack_extra_dir is not None:
        candidate_dirs.append(config.pack_extra_dir)
    else:
        candidate_dirs.append(DEFAULT_BUNDLED_PACK_EXTRA_DIR)

    for directory in candidate_dirs:
        resolved_dir = directory.expanduser().resolve()
        if not resolved_dir.is_dir():
            continue
        files: list[Path] = []
        for file_name in DEFAULT_PACK_EXTRA_FILES:
            file_path = resolved_dir / file_name
            if file_path.is_file():
                files.append(file_path)
        if files:
            return tuple(files)
    return tuple()


def _resolve_pack_archive_type(config: PipelineConfig) -> str | None:
    """解析压缩包命名的类型后缀。"""

    normalized_types = sorted(
        {
            item.strip().upper()
            for item in config.audio_types
            if isinstance(item, str) and item.strip()
        }
    )
    if len(normalized_types) == 1:
        return normalized_types[0]
    return None


def _resolve_default_upload_resource_type(config: PipelineConfig) -> str:
    """解析上传阶段默认资源类型目录。"""

    archive_type = _resolve_pack_archive_type(config=config)
    if archive_type in RESOURCE_TYPE_BUCKETS:
        return archive_type
    for item in config.audio_types:
        if not isinstance(item, str):
            continue
        normalized = item.strip().upper()
        if normalized in RESOURCE_TYPE_BUCKETS:
            return normalized
    return RESOURCE_TYPE_BUCKETS[0]


def _build_archive_upload_layout(
    archive: Path,
    remote_dir: str,
    default_resource_type: str,
) -> _ArchiveUploadLayout:
    """解析单个压缩包的远端目录路由。"""

    target_group = _resolve_archive_target_group(archive=archive)
    entity_key, _, archive_resource_type = _parse_archive_file_name(archive.name)
    resource_type = archive_resource_type or default_resource_type
    remote_relative_path = f"{resource_type}/{target_group}/{archive.name}"
    return _ArchiveUploadLayout(
        remote_name=archive.name,
        remote_relative_path=remote_relative_path,
        remote_path=_join_remote_file_path(remote_dir=remote_dir, remote_name=remote_relative_path),
        target_group=target_group,
        resource_type=resource_type,
        entity_key=entity_key,
    )


def _resolve_archive_target_group(archive: Path) -> str:
    """从本地路径解析上传目标分组（champions/maps）。"""

    for part in reversed(archive.parts[:-1]):
        lowered = part.casefold()
        if lowered in RESOURCE_TARGET_GROUPS:
            return lowered
    return "champions"


def _parse_archive_file_name(
    archive_name: str,
) -> tuple[str, str | None, str | None]:
    """解析压缩包文件名中的实体名、版本和资源类型。"""

    if archive_name.casefold().endswith(".7z"):
        stem = archive_name[:-3]
    else:
        stem = archive_name
    normalized_stem = stem.strip()
    if not normalized_stem:
        return archive_name, None, None
    parts = normalized_stem.rsplit("-", maxsplit=2)
    if len(parts) != 3:
        return normalized_stem, None, None
    entity_key = parts[0].strip()
    parsed_version = parts[1].strip() or None
    parsed_resource_type = parts[2].strip().upper()
    if not entity_key:
        return normalized_stem, None, None
    if parsed_resource_type not in RESOURCE_TYPE_BUCKETS:
        return normalized_stem, None, None
    return entity_key, parsed_version, parsed_resource_type


def _archive_remote_old_versions(
    client: BaiduPanClient,
    remote_dir: str,
    remote_index: dict[str, dict[str, object]],
    layout: _ArchiveUploadLayout,
    expected_game_version: str,
    executed_at: str,
) -> list[dict[str, object]]:
    """将同实体旧版本远端文件归档到 `OLD/<target_group>/`。"""

    archived_entries: list[dict[str, object]] = []
    old_relative_dir = f"{OLD_RESOURCE_BUCKET}/{layout.target_group}"
    for index_key, index_entry in tuple(remote_index.items()):
        metadata = _resolve_index_entry_metadata(entry=index_entry, remote_dir=remote_dir)
        if metadata.remote_path.casefold() == layout.remote_path.casefold():
            continue
        if metadata.is_old_bucket:
            continue
        if metadata.target_group != layout.target_group:
            continue
        if metadata.resource_type != layout.resource_type:
            continue
        if metadata.entity_key != layout.entity_key:
            continue
        if metadata.game_version is None or metadata.game_version == expected_game_version:
            continue

        _ensure_remote_directory(client=client, relative_dir=old_relative_dir)
        client.move_path(
            source_path=metadata.remote_path,
            destination_dir=old_relative_dir,
            new_name=metadata.remote_name,
        )
        archived_remote_relative = f"{old_relative_dir}/{metadata.remote_name}"
        archived_remote_path = _join_remote_file_path(
            remote_dir=remote_dir,
            remote_name=archived_remote_relative,
        )
        updated_entry = dict(index_entry)
        updated_entry.update(
            {
                "remote_path": archived_remote_path,
                "remote_name": metadata.remote_name,
                "game_version": metadata.game_version,
                "bucket": OLD_RESOURCE_BUCKET,
                "target_group": layout.target_group,
                "resource_type": layout.resource_type,
                "entity_key": layout.entity_key,
                "uploaded_at": executed_at,
            }
        )
        remote_index.pop(index_key, None)
        remote_index[archived_remote_path.casefold()] = updated_entry
        logger.info(
            "发现同实体旧版本，已归档到 OLD：source={}, destination={}",
            metadata.remote_path,
            archived_remote_path,
        )
        archived_entries.append(
            {
                "remote_path": archived_remote_path,
                "remote_name": metadata.remote_name,
                "game_version": metadata.game_version,
                "target_group": layout.target_group,
                "resource_type": layout.resource_type,
                "entity_key": layout.entity_key,
                "status": "archived_old",
            }
        )
    return archived_entries


def _resolve_index_entry_metadata(
    entry: dict[str, object],
    remote_dir: str,
) -> _IndexedArchiveMetadata:
    """解析远端索引条目的路由元数据。"""

    remote_path_value = entry.get("remote_path")
    if not (isinstance(remote_path_value, str) and remote_path_value.strip()):
        raise ValueError(f"远端索引条目缺少 remote_path：{entry}")
    remote_path = remote_path_value.strip().replace("\\", "/")
    remote_name = str(entry.get("remote_name") or Path(remote_path).name).strip()
    raw_relative = _build_relative_remote_path(remote_path=remote_path, remote_dir=remote_dir)
    path_parts = [item for item in raw_relative.split("/") if item]
    bucket = path_parts[0].upper() if path_parts else ""
    target_group = (
        path_parts[1].casefold()
        if len(path_parts) >= 2 and path_parts[1].casefold() in RESOURCE_TARGET_GROUPS
        else None
    )
    parsed_entity_key, parsed_version, parsed_resource_type = _parse_archive_file_name(remote_name)
    entry_game_version = entry.get("game_version")
    game_version = (
        entry_game_version.strip()
        if isinstance(entry_game_version, str) and entry_game_version.strip()
        else parsed_version
    )
    entry_resource_type = entry.get("resource_type")
    if isinstance(entry_resource_type, str) and entry_resource_type.strip():
        resource_type = entry_resource_type.strip().upper()
    elif bucket in RESOURCE_TYPE_BUCKETS:
        resource_type = bucket
    else:
        resource_type = parsed_resource_type
    entry_entity_key = entry.get("entity_key")
    if isinstance(entry_entity_key, str) and entry_entity_key.strip():
        entity_key = entry_entity_key.strip()
    else:
        entity_key = parsed_entity_key
    entry_target_group = entry.get("target_group")
    if isinstance(entry_target_group, str) and entry_target_group.strip():
        normalized_target = entry_target_group.strip().casefold()
        if normalized_target in RESOURCE_TARGET_GROUPS:
            target_group = normalized_target
    is_old_bucket = bucket == OLD_RESOURCE_BUCKET
    return _IndexedArchiveMetadata(
        remote_path=remote_path,
        remote_name=remote_name,
        game_version=game_version,
        target_group=target_group,
        resource_type=resource_type,
        entity_key=entity_key,
        is_old_bucket=is_old_bucket,
    )


def _build_relative_remote_path(remote_path: str, remote_dir: str) -> str:
    """将绝对远端路径转换为工作目录下相对路径。"""

    normalized_remote_path = remote_path.strip().replace("\\", "/")
    if not normalized_remote_path.startswith("/"):
        normalized_remote_path = f"/{normalized_remote_path.lstrip('/')}"
    normalized_dir = remote_dir.strip().replace("\\", "/").strip("/")
    normalized_work_dir = f"/{normalized_dir}" if normalized_dir else "/"
    if normalized_work_dir == "/":
        return normalized_remote_path.lstrip("/")
    if normalized_remote_path.casefold().startswith(f"{normalized_work_dir}/".casefold()):
        return normalized_remote_path[len(normalized_work_dir) + 1 :]
    if normalized_remote_path.casefold() == normalized_work_dir.casefold():
        return ""
    return normalized_remote_path.lstrip("/")


def _ensure_remote_directory(client: BaiduPanClient, relative_dir: str) -> None:
    """确保远端目录存在（按层创建）。"""

    normalized = relative_dir.strip().replace("\\", "/").strip("/")
    if not normalized:
        return

    current = ""
    for segment in normalized.split("/"):
        current = f"{current}/{segment}" if current else segment
        if _remote_file_exists(client=client, remote_path=current):
            continue
        client.create_directory(dir_path=current)


def _initialize_remote_upload_layout(client: BaiduPanClient) -> None:
    """初始化远端目录结构。"""

    for resource_type in RESOURCE_TYPE_BUCKETS:
        for target_group in RESOURCE_TARGET_GROUPS:
            _ensure_remote_directory(client=client, relative_dir=f"{resource_type}/{target_group}")
    for target_group in RESOURCE_TARGET_GROUPS:
        _ensure_remote_directory(
            client=client, relative_dir=f"{OLD_RESOURCE_BUCKET}/{target_group}"
        )


def _build_readable_upload_manifest_content(
    index: dict[str, dict[str, object]],
    game_version: str,
    executed_at: str,
    remote_dir: str,
) -> str:
    """构建给人类阅读和搜索的上传索引文本。"""

    active_lines: list[str] = []
    archived_lines: list[str] = []
    for entry in sorted(
        index.values(),
        key=lambda item: str(item.get("remote_path", "")).casefold(),
    ):
        metadata = _resolve_index_entry_metadata(entry=entry, remote_dir=remote_dir)
        bucket = (
            OLD_RESOURCE_BUCKET if metadata.is_old_bucket else (metadata.resource_type or "UNKNOWN")
        )
        group = metadata.target_group or "unknown"
        entity_key = metadata.entity_key or metadata.remote_name
        version = metadata.game_version or "unknown"
        line = (
            f"- {bucket}/{group} | {metadata.remote_name} | version={version} | "
            f"entity={entity_key} | path={metadata.remote_path}"
        )
        if metadata.is_old_bucket:
            archived_lines.append(line)
        else:
            active_lines.append(line)

    lines: list[str] = [
        "# RiftAudioPipeline 网盘索引（可读版）",
        "",
        f"更新时间(UTC): {executed_at}",
        f"当前运行版本: {game_version}",
        f"总条目数: {len(index)}",
        "",
        "## 在线资源",
    ]
    if active_lines:
        lines.extend(active_lines)
    else:
        lines.append("- （无）")
    lines.extend(
        (
            "",
            "## OLD 归档资源",
        )
    )
    if archived_lines:
        lines.extend(archived_lines)
    else:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)


def _calculate_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""

    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_remote_upload_manifest_index(
    client: BaiduPanClient,
    package_root: Path,
    allow_missing_remote_index: bool,
) -> dict[str, dict[str, object]]:
    """读取远端上传索引并构建内存查询表。

    Args:
        client: 百度网盘客户端。
        package_root: 当前版本打包根目录，用于临时落地远端索引文件。

    Returns:
        以 `remote_path.casefold()` 为键的索引字典。

    Raises:
        ValueError: 远端索引不是合法 JSON 或缺少 `entries` 列表。
        RuntimeError: 不允许缺失索引时，远端未找到索引文件。
    """

    temp_file = package_root / ".remote_upload_manifest.json"
    try:
        try:
            client.download_file(remote_path=UPLOAD_MANIFEST_FILE_NAME, local_path=temp_file)
        except FileNotFoundError:
            if not allow_missing_remote_index:
                raise RuntimeError(
                    "上传阶段终止：远端缺少上传索引 upload_manifest.json，"
                    "当前为差异更新流程，可能存在文件被手工移动或索引丢失，请先修复索引。"
                )
            logger.info("远端索引不存在，将创建新索引：{}", UPLOAD_MANIFEST_FILE_NAME)
            return {}

        try:
            payload = json.loads(temp_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"远端索引解析失败：{UPLOAD_MANIFEST_FILE_NAME} 不是合法 JSON。"
            ) from error

        if not isinstance(payload, dict):
            raise ValueError(f"远端索引格式错误：{UPLOAD_MANIFEST_FILE_NAME} 根对象必须为字典。")
        entries = payload.get("entries")
        return _build_upload_manifest_index(entries=entries)
    finally:
        temp_file.unlink(missing_ok=True)


def _build_upload_manifest_index(entries: object) -> dict[str, dict[str, object]]:
    """将远端索引条目转换为高效查询结构。"""

    if not isinstance(entries, list):
        raise ValueError("远端索引格式错误：`entries` 必须为列表。")

    index: dict[str, dict[str, object]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue

        remote_path_obj = raw_entry.get("remote_path")
        if not (isinstance(remote_path_obj, str) and remote_path_obj.strip()):
            continue

        remote_path = remote_path_obj.strip().replace("\\", "/")
        remote_name = str(raw_entry.get("remote_name") or Path(remote_path).name).strip()
        game_version = (
            str(raw_entry.get("game_version")).strip()
            if isinstance(raw_entry.get("game_version"), str)
            else ""
        )
        normalized_entry: dict[str, object] = {
            "remote_path": remote_path,
            "remote_name": remote_name,
            "game_version": game_version or None,
            "uploaded_at": raw_entry.get("uploaded_at"),
        }
        for field_name in ("bucket", "target_group", "resource_type", "entity_key"):
            field_value = raw_entry.get(field_name)
            if isinstance(field_value, str) and field_value.strip():
                normalized_entry[field_name] = field_value.strip()
        size_obj = _coerce_non_negative_int(raw_entry.get("size"))
        if size_obj is not None:
            normalized_entry["size"] = size_obj
        sha256_obj = raw_entry.get("sha256")
        if isinstance(sha256_obj, str) and sha256_obj.strip():
            normalized_entry["sha256"] = sha256_obj.strip().lower()
        index[remote_path.casefold()] = normalized_entry
    return index


def _build_upload_manifest_payload(
    game_version: str,
    index: dict[str, dict[str, object]],
    run_entries: list[dict[str, object]],
    executed_at: str,
) -> dict[str, object]:
    """构建上传索引快照。"""

    index_entries = tuple(
        sorted(
            index.values(),
            key=lambda entry: str(entry.get("remote_path", "")).casefold(),
        )
    )
    uploaded_count = sum(1 for entry in run_entries if entry.get("status") == "uploaded")
    skipped_count = sum(1 for entry in run_entries if entry.get("status") == "skipped")
    return {
        "schema_version": UPLOAD_MANIFEST_SCHEMA_VERSION,
        "updated_at": executed_at,
        "entry_count": len(index_entries),
        "entries": index_entries,
        "last_run": {
            "game_version": game_version,
            "executed_at": executed_at,
            "archive_count": len(run_entries),
            "uploaded_count": uploaded_count,
            "skipped_count": skipped_count,
            "entries": run_entries,
        },
    }


def _join_remote_file_path(remote_dir: str, remote_name: str) -> str:
    """拼接远端目录和文件名。"""

    normalized_name = remote_name.strip().replace("\\", "/").lstrip("/")
    if not normalized_name:
        raise ValueError("上传阶段失败：远端文件名不能为空。")

    normalized_dir = remote_dir.strip().replace("\\", "/").strip("/")
    if not normalized_dir:
        return f"/{normalized_name}"
    return f"/{normalized_dir}/{normalized_name}"


def _is_same_index_entry(
    entry: dict[str, object],
    expected_remote_name: str,
    expected_game_version: str,
) -> bool:
    """按文件名与版本号判断索引条目是否匹配。"""

    indexed_name = entry.get("remote_name")
    if isinstance(indexed_name, str) and indexed_name.strip():
        if indexed_name.strip() != expected_remote_name:
            return False

    indexed_version = entry.get("game_version")
    if indexed_version is None:
        return True
    if not isinstance(indexed_version, str):
        return False
    return indexed_version.strip() == expected_game_version


def _remote_file_exists(client: BaiduPanClient, remote_path: str) -> bool:
    """判断远端路径是否已存在。"""

    try:
        client.get_path_entry(remote_path=remote_path)
        return True
    except FileNotFoundError:
        return False


def _current_utc_timestamp() -> str:
    """返回 UTC ISO-8601 时间戳。"""

    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coerce_non_negative_int(value: object) -> int | None:
    """将对象转换为非负整数。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _cleanup_simulated_runtime_files(
    runtime_game_path: Path,
    runtime_download_dir: Path,
) -> tuple[int, int]:
    """清理模拟目录下临时 WAD 与下载缓存。"""

    runtime_wad_dirs = (
        runtime_game_path / "Game" / "DATA" / "FINAL" / "Champions",
        runtime_game_path / "Game" / "DATA" / "FINAL" / "Maps" / "Shipping",
    )
    removed_runtime_wads = 0
    for directory in runtime_wad_dirs:
        if not directory.is_dir():
            continue
        for item in directory.rglob("*"):
            if item.is_file() and item.name.casefold().endswith(".wad.client"):
                item.unlink()
                removed_runtime_wads += 1

    removed_download_cache = 0
    if runtime_download_dir.exists():
        for item in runtime_download_dir.rglob("*"):
            if item.is_file():
                removed_download_cache += 1
        shutil.rmtree(runtime_download_dir, ignore_errors=True)

    return removed_runtime_wads, removed_download_cache


def _merge_runtime_wad_paths(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """合并运行时 WAD 路径并去重排序。"""

    deduped: dict[str, str] = {}
    for group in groups:
        for path in group:
            normalized = path.strip().replace("\\", "/")
            if not normalized:
                continue
            deduped.setdefault(normalized.casefold(), normalized)
    return tuple(sorted(deduped.values(), key=str.casefold))


def _build_runtime_wad_paths_from_manifest_paths(
    manifest_paths: tuple[str, ...],
    region: str,
    include_root_wad: bool = True,
) -> tuple[str, ...]:
    """将 manifest WAD 路径转换为运行时根/区域路径集合。"""

    runtime_paths: dict[str, str] = {}
    region_suffix = f".{region}.wad.client"
    for raw_path in manifest_paths:
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith("Game/"):
            normalized = normalized.removeprefix("Game/")
        if not normalized.startswith("DATA/"):
            continue

        region_runtime_path = f"Game/{normalized}"
        runtime_paths.setdefault(region_runtime_path.casefold(), region_runtime_path)

        lowered = normalized.casefold()
        if include_root_wad and lowered.endswith(region_suffix.casefold()):
            root_manifest_path = f"{normalized[: len(normalized) - len(region_suffix)]}.wad.client"
            root_runtime_path = f"Game/{root_manifest_path}"
            runtime_paths.setdefault(root_runtime_path.casefold(), root_runtime_path)

    return tuple(sorted(runtime_paths.values(), key=str.casefold))


def _cleanup_version_audio_outputs(version_audio_dir: Path) -> int:
    """清理已打包版本的音频目录，降低上传阶段磁盘占用。"""

    if not version_audio_dir.is_dir():
        return 0

    removed_files = 0
    for item in version_audio_dir.rglob("*"):
        if item.is_file():
            removed_files += 1
    shutil.rmtree(version_audio_dir, ignore_errors=True)
    return removed_files
