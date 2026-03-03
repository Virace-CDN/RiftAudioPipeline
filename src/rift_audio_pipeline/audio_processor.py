"""语音解包编排模块。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

DEFAULT_UNPACK_MAX_WORKERS = 4


@dataclass(frozen=True, slots=True)
class AudioProcessingTargets:
    """需要处理的目标实体集合。"""

    champion_ids: tuple[int, ...]
    map_ids: tuple[int, ...]


def run_data_updater(
    game_path: Path,
    output_path: Path,
    region: str,
    force_update: bool = False,
) -> Path:
    """执行 DataUpdater，生成/更新 `data` 文件。

    Args:
        game_path: 游戏目录。
        output_path: 输出目录。
        region: 语言区域。
        force_update: 是否忽略版本检查强制更新。

    Returns:
        `data` 文件基础路径（不带后缀）。
    """

    _initialize_unpack_config(game_path=game_path, output_path=output_path, region=region)
    from lol_audio_unpack.manager import DataUpdater

    updater = DataUpdater(languages=[region], force_update=force_update)
    data_file_base = updater.check_and_update()
    logger.info("DataUpdater 执行完成：{}", data_file_base)
    return data_file_base


def resolve_processing_targets(
    data_file_base: Path,
    champion_aliases: Sequence[str],
    map_ids: Sequence[str],
) -> AudioProcessingTargets:
    """将 manifest 维度目标转换为 `BinUpdater/解包` 所需 ID。

    Args:
        data_file_base: `data` 文件基础路径（不带后缀）。
        champion_aliases: 英雄别名集合。
        map_ids: 地图 ID 集合（字符串）。

    Returns:
        规范化后的目标 ID 集合；当为空时表示执行全量处理。
    """

    from lol_audio_unpack.manager.utils import read_data

    payload = read_data(data_file_base)
    champions_raw = payload.get("champions", {})
    alias_set = {item.casefold() for item in champion_aliases}

    champion_ids: set[int] = set()
    for champion_id, champion_data in champions_raw.items():
        if not isinstance(champion_data, dict):
            continue
        alias = str(champion_data.get("alias", "")).casefold()
        if alias and alias in alias_set:
            try:
                champion_ids.add(int(champion_id))
            except ValueError:
                logger.warning("跳过无法解析为 int 的英雄 ID：{}", champion_id)

    normalized_map_ids: set[int] = set()
    for map_id in map_ids:
        try:
            normalized_map_ids.add(int(map_id))
        except ValueError:
            logger.warning("跳过无法解析为 int 的地图 ID：{}", map_id)

    return AudioProcessingTargets(
        champion_ids=tuple(sorted(champion_ids)),
        map_ids=tuple(sorted(normalized_map_ids)),
    )


def resolve_all_processing_targets(data_file_base: Path) -> AudioProcessingTargets:
    """从 `data` 文件提取全量英雄/地图 ID。

    Args:
        data_file_base: `data` 文件基础路径（不带后缀）。

    Returns:
        全量目标 ID 集合。
    """

    from lol_audio_unpack.manager.utils import read_data

    payload = read_data(data_file_base)
    champions_raw = payload.get("champions", {})
    maps_raw = payload.get("maps", {})

    champion_ids = sorted(
        (int(champion_id) for champion_id in champions_raw if str(champion_id).isdigit())
    )
    map_ids = sorted((int(map_id) for map_id in maps_raw if str(map_id).isdigit()))
    return AudioProcessingTargets(
        champion_ids=tuple(champion_ids),
        map_ids=tuple(map_ids),
    )


def run_bin_updater(
    champion_ids: tuple[int, ...],
    map_ids: tuple[int, ...],
    force_update: bool = False,
    process_events: bool = False,
) -> None:
    """执行 BinUpdater。

    Args:
        champion_ids: 英雄 ID 列表；为空时表示全量。
        map_ids: 地图 ID 列表；为空时表示全量。
        force_update: 是否忽略版本检查强制更新。
        process_events: 是否处理 events 数据。语音资源场景默认关闭以降低耗时。
    """

    from lol_audio_unpack.manager import BinUpdater

    updater = BinUpdater(force_update=force_update, process_events=process_events)
    if champion_ids or map_ids:
        updater.update(
            champion_ids=[str(item) for item in champion_ids] if champion_ids else None,
            map_ids=[str(item) for item in map_ids] if map_ids else None,
        )
        logger.info(
            "BinUpdater 执行完成（增量）：champion_ids={}, map_ids={}, process_events={}",
            list(champion_ids),
            list(map_ids),
            process_events,
        )
        return

    updater.update(target="all")
    logger.info("BinUpdater 执行完成（全量）：process_events={}", process_events)


def run_unpack(
    champion_ids: tuple[int, ...],
    map_ids: tuple[int, ...],
    max_workers: int = DEFAULT_UNPACK_MAX_WORKERS,
) -> None:
    """执行语音解包。

    Args:
        champion_ids: 英雄 ID 列表；为空时表示全量。
        map_ids: 地图 ID 列表；为空时表示全量。
        max_workers: 并发线程数。
    """

    from lol_audio_unpack.manager.data_reader import DataReader
    from lol_audio_unpack.unpack import unpack_audio_all
    from lol_audio_unpack.unpack import unpack_champions
    from lol_audio_unpack.unpack import unpack_maps

    _reset_singleton_instance(DataReader)
    reader = DataReader()
    if champion_ids or map_ids:
        if champion_ids:
            unpack_champions(
                reader=reader, champion_ids=list(champion_ids), max_workers=max_workers
            )
        if map_ids:
            unpack_maps(reader=reader, map_ids=list(map_ids), max_workers=max_workers)
        logger.info(
            "解包执行完成（增量）：champion_ids={}, map_ids={}, max_workers={}",
            list(champion_ids),
            list(map_ids),
            max_workers,
        )
    else:
        unpack_audio_all(
            reader=reader,
            max_workers=max_workers,
            include_champions=True,
            include_maps=True,
        )
        logger.info("解包执行完成（全量）：max_workers={}", max_workers)
    reader.write_unknown_categories_to_file()


def run_unpack_by_entity(
    champion_ids: tuple[int, ...],
    map_ids: tuple[int, ...],
    max_workers: int = DEFAULT_UNPACK_MAX_WORKERS,
) -> None:
    """按实体顺序执行解包，降低峰值磁盘占用。

    Args:
        champion_ids: 英雄 ID 列表。
        map_ids: 地图 ID 列表。
        max_workers: 每次实体解包的并发线程数。
    """

    for champion_id in champion_ids:
        run_unpack(
            champion_ids=(champion_id,),
            map_ids=tuple(),
            max_workers=max_workers,
        )
    for map_id in map_ids:
        run_unpack(
            champion_ids=tuple(),
            map_ids=(map_id,),
            max_workers=max_workers,
        )


def _initialize_unpack_config(game_path: Path, output_path: Path, region: str) -> None:
    """初始化 `lol_audio_unpack` 配置。"""

    from lol_audio_unpack.utils.config import config as unpack_config

    unpack_config.initialize(
        env_path=output_path,
        force_reload=True,
        cli_overrides={
            "GAME_PATH": game_path,
            "OUTPUT_PATH": output_path,
            "GAME_REGION": region,
        },
    )


def _reset_singleton_instance(target_cls: type[object]) -> None:
    """重置下游库单例对象，避免同进程多次运行时复用旧状态。"""

    from lol_audio_unpack.utils.common import Singleton

    Singleton._instances.pop(target_cls, None)
