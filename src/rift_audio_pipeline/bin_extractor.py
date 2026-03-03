"""bin 提取与本地标志管理。"""

from __future__ import annotations

from pathlib import Path

LOCAL_BIN_FLAG_FILE = ".use_local_bin"


def write_to_bin_input(version_dir: Path, relative_path: str, content: bytes) -> Path:
    """将 bin 原始数据写入 `bin_input` 目录。

    Args:
        version_dir: 版本目录路径。
        relative_path: bin 文件相对路径。
        content: 二进制内容。

    Returns:
        写入后的文件路径。
    """

    target_file = version_dir / "bin_input" / relative_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(content)
    return target_file


def create_local_bin_flag(version_dir: Path) -> Path:
    """创建 local_bin 标志文件。

    Args:
        version_dir: 版本目录路径。

    Returns:
        标志文件路径。
    """

    flag_file = version_dir / LOCAL_BIN_FLAG_FILE
    flag_file.touch(exist_ok=True)
    return flag_file


def extract_champion_bins(alias: str, manifest_url: str) -> None:
    """预留：按英雄 alias 在线提取 bin。

    Args:
        alias: 英雄别名。
        manifest_url: 当前版本 manifest URL。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第三阶段实现。
    """

    raise NotImplementedError(f"待实现：英雄 {alias} 的在线 bin 提取。")


def extract_map_bins(map_id: str, manifest_url: str) -> None:
    """预留：按地图 ID 在线提取 bin。

    Args:
        map_id: 地图 ID。
        manifest_url: 当前版本 manifest URL。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第三阶段实现。
    """

    raise NotImplementedError(f"待实现：地图 {map_id} 的在线 bin 提取。")
