"""主流程编排模块。"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from rift_audio_pipeline.audio_processor import resolve_processing_targets
from rift_audio_pipeline.audio_processor import resolve_all_processing_targets
from rift_audio_pipeline.audio_processor import run_bin_updater
from rift_audio_pipeline.audio_processor import run_data_updater
from rift_audio_pipeline.audio_processor import run_unpack
from rift_audio_pipeline.audio_processor import run_unpack_by_entity
from rift_audio_pipeline.baidu.sdk import ensure_official_sdk_path
from rift_audio_pipeline.bin_extractor import seed_bin_input_from_directory
from rift_audio_pipeline.config import PipelineConfig
from rift_audio_pipeline.game_dir_builder import build_simulated_dir
from rift_audio_pipeline.game_dir_builder import check_local_game_path
from rift_audio_pipeline.game_dir_builder import cleanup_updater_inputs
from rift_audio_pipeline.game_dir_builder import write_content_metadata
from rift_audio_pipeline.manifest_ops import DECISION_REASON_FIRST_RUN
from rift_audio_pipeline.manifest_ops import DECISION_REASON_GAME_VERSION_UNCHANGED
from rift_audio_pipeline.manifest_ops import DECISION_REASON_NO_REGION_MANIFEST_CHANGES
from rift_audio_pipeline.manifest_ops import DEFAULT_LOCAL_STATE_FILE
from rift_audio_pipeline.manifest_ops import build_voice_filter_result_cache_path
from rift_audio_pipeline.manifest_ops import build_local_state
from rift_audio_pipeline.manifest_ops import evaluate_update_need
from rift_audio_pipeline.manifest_ops import extract_changed_entities_from_wad_paths
from rift_audio_pipeline.manifest_ops import filter_wad_changes_by_bin_voice_paths
from rift_audio_pipeline.manifest_ops import save_local_state


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

    secondary_unpack_paths: tuple[str, ...] | None = None
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
                )
                filter_cache_file = build_voice_filter_result_cache_path(
                    old_manifest_url=decision.previous_state.game_manifest_url,
                    new_manifest_url=latest.game_manifest_url,
                    region=config.game_region,
                    update_paths=decision.wad_changes.update_paths,
                )
            except Exception as error:  # noqa: BLE001
                logger.error("WAD 二次筛选失败，error={}", error)
                return 1

            logger.info(
                "WAD 二次筛选结果：需解包={}, 可跳过={}",
                len(secondary_filter.unpack_paths),
                len(secondary_filter.skipped_paths),
            )
            logger.info("WAD 二次筛选缓存文件：{}", filter_cache_file)
            if secondary_filter.unpack_paths:
                logger.info("需解包 WAD：{}", ", ".join(secondary_filter.unpack_paths))
                secondary_unpack_paths = secondary_filter.unpack_paths
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

    runtime_game_path, runtime_is_simulated = _resolve_runtime_game_path(
        config=config,
        latest_game_version=latest.game_version,
    )
    if not check_local_game_path(runtime_game_path):
        logger.error("游戏目录不完整，无法执行后续流程：{}", runtime_game_path)
        return 1

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

        if config.low_disk_mode and (targets.champion_ids or targets.map_ids):
            logger.info(
                "低磁盘模式启用：按实体顺序解包（champions={}, maps={}, workers={}）",
                len(targets.champion_ids),
                len(targets.map_ids),
                config.unpack_workers,
            )
            run_unpack_by_entity(
                champion_ids=targets.champion_ids,
                map_ids=targets.map_ids,
                max_workers=config.unpack_workers,
            )
        else:
            run_unpack(
                champion_ids=targets.champion_ids,
                map_ids=targets.map_ids,
                max_workers=config.unpack_workers,
            )
    except Exception as error:  # noqa: BLE001
        logger.error("解包阶段失败，error={}", error)
        return 1

    saved_state = build_local_state(latest_versions=latest)
    saved_file = save_local_state(state=saved_state, state_file=DEFAULT_LOCAL_STATE_FILE)
    logger.info("解包阶段执行完成，已同步状态文件：{}", saved_file)
    return 0


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
