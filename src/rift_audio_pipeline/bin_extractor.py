"""bin 提取与本地标志管理。"""

from __future__ import annotations

from collections.abc import Mapping
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

    Raises:
        ValueError: 当 `relative_path` 为空、为绝对路径或存在越界段时抛出。
    """

    normalized_path = _normalize_relative_bin_path(relative_path)
    target_file = version_dir / "bin_input" / normalized_path
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


def write_many_to_bin_input(
    version_dir: Path,
    bin_payloads: Mapping[str, bytes],
    enable_local_bin: bool = True,
) -> tuple[Path, ...]:
    """批量写入 bin 数据到 `bin_input` 目录。

    Args:
        version_dir: 版本目录路径。
        bin_payloads: 以相对路径为 key、二进制内容为 value 的映射。
        enable_local_bin: 是否在写入后创建 `.use_local_bin` 标志。

    Returns:
        已写入文件路径集合（按路径排序）。
    """

    written_files = [
        write_to_bin_input(version_dir=version_dir, relative_path=path, content=content)
        for path, content in sorted(bin_payloads.items(), key=lambda item: item[0].casefold())
    ]
    if enable_local_bin and written_files:
        create_local_bin_flag(version_dir=version_dir)
    return tuple(written_files)


def seed_bin_input_from_directory(
    version_dir: Path,
    source_dir: Path,
    enable_local_bin: bool = True,
) -> tuple[Path, ...]:
    """从本地目录导入 bin 文件到 `bin_input`。

    目录相对结构会原样保留。例如 `source_dir/data/maps/map11/map11.bin`
    会落地到 `version_dir/bin_input/data/maps/map11/map11.bin`。

    Args:
        version_dir: 版本目录路径。
        source_dir: 本地 bin 根目录。
        enable_local_bin: 是否在导入后创建 `.use_local_bin` 标志。

    Returns:
        已写入文件路径集合（按路径排序）。

    Raises:
        FileNotFoundError: `source_dir` 不存在或不是目录时抛出。
    """

    if not source_dir.is_dir():
        raise FileNotFoundError(f"本地 bin 目录不存在或不可读：{source_dir}")

    payloads: dict[str, bytes] = {}
    for item in sorted(source_dir.rglob("*"), key=lambda path: path.as_posix().casefold()):
        if not item.is_file():
            continue
        if item.suffix.casefold() != ".bin":
            continue
        relative_path = item.relative_to(source_dir).as_posix()
        payloads[relative_path] = item.read_bytes()

    return write_many_to_bin_input(
        version_dir=version_dir,
        bin_payloads=payloads,
        enable_local_bin=enable_local_bin,
    )


def _normalize_relative_bin_path(relative_path: str) -> Path:
    """规范化相对路径并阻止越界。

    Args:
        relative_path: 输入相对路径。

    Returns:
        规范化后的相对路径对象。

    Raises:
        ValueError: 输入为空、为绝对路径或存在越界段时抛出。
    """

    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("relative_path 不能为空")

    path = Path(raw)
    if path.is_absolute():
        raise ValueError(f"relative_path 不允许绝对路径：{relative_path}")

    normalized = Path(*[part for part in path.parts if part not in {"", "."}])
    if not normalized.parts:
        raise ValueError(f"relative_path 无有效路径段：{relative_path}")
    if any(part == ".." for part in normalized.parts):
        raise ValueError(f"relative_path 存在越界路径段：{relative_path}")
    return normalized


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
