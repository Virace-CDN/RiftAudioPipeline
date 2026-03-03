"""游戏目录检测与模拟目录构建。"""

from __future__ import annotations

from pathlib import Path
import shutil


def check_local_game_path(game_path: Path) -> bool:
    """检查本地游戏目录是否满足最低资源条件。

    Args:
        game_path: 游戏根目录路径，通常包含 `Game` 与 `LeagueClient` 子目录。

    Returns:
        若关键目录存在返回 `True`，否则返回 `False`。
    """

    required_dirs = (
        game_path / "Game" / "DATA" / "FINAL",
        game_path / "LeagueClient" / "Plugins" / "rcp-be-lol-game-data",
    )
    return all(path.exists() for path in required_dirs)


def build_simulated_dir(base_dir: Path) -> Path:
    """构建在线模式所需的最小游戏目录结构。

    Args:
        base_dir: 模拟目录根路径。

    Returns:
        已创建完成的模拟目录路径。
    """

    champions_dir = base_dir / "Game" / "DATA" / "FINAL" / "Champions"
    maps_dir = base_dir / "Game" / "DATA" / "FINAL" / "Maps" / "Shipping"
    lcu_dir = base_dir / "LeagueClient" / "Plugins" / "rcp-be-lol-game-data"
    for directory in (champions_dir, maps_dir, lcu_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return base_dir


def check_disk_space(path: Path, required_bytes: int) -> bool:
    """检测磁盘可用空间是否足够。

    Args:
        path: 目标目录路径。
        required_bytes: 预估所需空间（字节）。

    Returns:
        可用空间充足返回 `True`，否则返回 `False`。
    """

    usage = shutil.disk_usage(path)
    return usage.free >= required_bytes
