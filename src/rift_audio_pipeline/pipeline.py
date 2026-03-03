"""主流程编排模块。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import hashlib
import json
from pathlib import Path
import shutil

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
from rift_audio_pipeline.audio_processor import run_unpack_by_entity
from rift_audio_pipeline.baidu.sdk import ensure_official_sdk_path
from rift_audio_pipeline.baidu.oauth import resolve_token_store
from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.bin_extractor import seed_bin_input_from_directory
from rift_audio_pipeline.bin_extractor import write_many_to_bin_input
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
from rift_audio_pipeline.manifest_ops import extract_bin_payloads_from_filter_decisions
from rift_audio_pipeline.manifest_ops import extract_changed_entities_from_wad_paths
from rift_audio_pipeline.manifest_ops import filter_wad_changes_by_bin_voice_paths
from rift_audio_pipeline.manifest_ops import save_local_state
from rift_audio_pipeline.packer import pack_all

DEFAULT_BUNDLED_PACK_EXTRA_DIR = Path(__file__).resolve().parent / "pack_extra"
DEFAULT_PACK_EXTRA_FILES = ("食用说明.txt", "license.txt")


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
                secondary_filter_result = secondary_filter
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

    if secondary_filter_result is not None:
        try:
            auto_bin_payloads = extract_bin_payloads_from_filter_decisions(
                manifest_url=latest.game_manifest_url,
                decisions=secondary_filter_result.decisions,
            )
            written_auto_bins = write_many_to_bin_input(
                version_dir=data_file_base.parent,
                bin_payloads=auto_bin_payloads,
                enable_local_bin=True,
            )
        except Exception as error:  # noqa: BLE001
            logger.error("二次筛选 BIN 自动复用写入失败，error={}", error)
            return 1
        logger.info(
            "二次筛选 BIN 自动复用完成：matched_count={}, written_count={}",
            len(auto_bin_payloads),
            len(written_auto_bins),
        )

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

    if runtime_is_simulated:
        runtime_wad_targets = targets
        if not (runtime_wad_targets.champion_ids or runtime_wad_targets.map_ids):
            runtime_wad_targets = resolve_all_processing_targets(data_file_base=data_file_base)
        runtime_wad_paths = resolve_runtime_wad_paths(
            data_file_base=data_file_base,
            region=config.game_region,
            champion_ids=runtime_wad_targets.champion_ids,
            map_ids=runtime_wad_targets.map_ids,
        )
        if secondary_unpack_paths is not None:
            runtime_wad_paths = _merge_runtime_wad_paths(
                runtime_wad_paths,
                _build_runtime_wad_paths_from_manifest_paths(
                    manifest_paths=secondary_unpack_paths,
                    region=config.game_region,
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

    if config.enable_pack:
        try:
            archives = _pack_unpacked_outputs(config=config, game_version=latest.game_version)
        except Exception as error:  # noqa: BLE001
            logger.error("打包阶段失败，error={}", error)
            return 1
        logger.info("打包阶段执行完成：archive_count={}", len(archives))
        if config.enable_upload:
            try:
                upload_manifest = _upload_archives_and_manifest(
                    config=config,
                    game_version=latest.game_version,
                    archives=archives,
                )
            except Exception as error:  # noqa: BLE001
                logger.error("上传阶段失败，error={}", error)
                return 1
            if upload_manifest is not None:
                logger.info("上传阶段执行完成：manifest_file={}", upload_manifest)
                if runtime_is_simulated:
                    removed_runtime_wads, removed_download_cache = _cleanup_simulated_runtime_files(
                        runtime_game_path=runtime_game_path,
                        runtime_download_dir=runtime_download_dir,
                    )
                    logger.info(
                        "模拟目录临时文件清理完成：runtime_wad_count={}, download_cache_count={}",
                        removed_runtime_wads,
                        removed_download_cache,
                    )

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
    manifest_file = package_root / "upload_manifest.json"
    uploaded_entries: list[dict[str, object]] = []

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
        for archive in archives:
            if not archive.is_file():
                raise FileNotFoundError(f"上传失败：压缩包不存在：{archive}")
            remote_name = _build_remote_archive_name(
                game_version=game_version,
                archive_name=archive.name,
            )
            response = client.upload_file(local_path=archive, remote_path=remote_name)
            uploaded_entries.append(
                {
                    "local_path": str(archive),
                    "remote_path": f"{config.baidu_pan_remote_dir.rstrip('/')}/{remote_name}",
                    "size": archive.stat().st_size,
                    "sha256": _calculate_sha256(archive),
                    "response": response,
                }
            )

        manifest_payload = {
            "schema_version": 1,
            "game_version": game_version,
            "created_at": datetime.now(tz=timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "archive_count": len(uploaded_entries),
            "entries": uploaded_entries,
        }
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        remote_manifest_name = f"upload_manifest_{game_version}.json"
        client.upload_file(local_path=manifest_file, remote_path=remote_manifest_name)
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


def _build_remote_archive_name(game_version: str, archive_name: str) -> str:
    """生成远端压缩包文件名。"""

    return f"package_{game_version}_{archive_name}"


def _calculate_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""

    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        if lowered.endswith(region_suffix.casefold()):
            root_manifest_path = f"{normalized[: len(normalized) - len(region_suffix)]}.wad.client"
            root_runtime_path = f"Game/{root_manifest_path}"
            runtime_paths.setdefault(root_runtime_path.casefold(), root_runtime_path)

    return tuple(sorted(runtime_paths.values(), key=str.casefold))
