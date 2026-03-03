"""语音解包编排模块。"""

from __future__ import annotations

from pathlib import Path


def run_data_updater(game_path: Path, output_path: Path, region: str) -> None:
    """执行数据更新。

    Args:
        game_path: 游戏目录。
        output_path: 输出目录。
        region: 语言区域。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第四阶段实现。
    """

    raise NotImplementedError(
        f"待实现：DataUpdater，game_path={game_path}, output_path={output_path}, region={region}"
    )


def run_bin_updater(champion_ids: tuple[int, ...], map_ids: tuple[int, ...]) -> None:
    """执行 BinUpdater。

    Args:
        champion_ids: 英雄 ID 列表。
        map_ids: 地图 ID 列表。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第四阶段实现。
    """

    raise NotImplementedError(
        f"待实现：BinUpdater，champion_ids={champion_ids}, map_ids={map_ids}"
    )


def run_unpack(champion_ids: tuple[int, ...], map_ids: tuple[int, ...]) -> None:
    """执行语音解包。

    Args:
        champion_ids: 英雄 ID 列表。
        map_ids: 地图 ID 列表。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第四阶段实现。
    """

    raise NotImplementedError(
        f"待实现：音频解包，champion_ids={champion_ids}, map_ids={map_ids}"
    )
