"""游戏目录检测与模拟目录构建。"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Literal


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


def write_content_metadata(game_path: Path, version: str) -> Path:
    """写入最小游戏环境所需的 `content-metadata.json`。

    `lol_audio_unpack` 的 `DataUpdater/BinUpdater` 会从该文件读取版本号，
    因此在线模式最小游戏目录必须包含该文件。

    Args:
        game_path: 游戏根目录路径。
        version: 游戏完整版本号（例如 `16.4.7480682`）。

    Returns:
        已写入的 metadata 文件路径。
    """

    metadata_file = game_path / "Game" / "content-metadata.json"
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_text(
        json.dumps({"version": version}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata_file


def stage_wad_file(
    game_path: Path,
    relative_wad_path: str,
    source_wad_file: Path,
    strategy: Literal["hardlink", "copy"] = "hardlink",
) -> Path:
    """将 WAD 文件按相对路径落地到最小游戏目录。

    Args:
        game_path: 游戏根目录路径。
        relative_wad_path: 相对于游戏根目录的 WAD 路径。
        source_wad_file: 本地源 WAD 文件路径。
        strategy: 写入策略。`hardlink` 失败时会自动回退到复制。

    Returns:
        落地后的目标文件路径。

    Raises:
        FileNotFoundError: 源文件不存在时抛出。
        ValueError: 目标相对路径不合法时抛出。
    """

    return stage_runtime_file(
        game_path=game_path,
        relative_path=relative_wad_path,
        source_file=source_wad_file,
        strategy=strategy,
    )


def stage_runtime_file(
    game_path: Path,
    relative_path: str,
    source_file: Path,
    strategy: Literal["hardlink", "copy"] = "hardlink",
) -> Path:
    """将任意运行时文件按相对路径落地到游戏目录。

    Args:
        game_path: 游戏根目录路径。
        relative_path: 相对于游戏根目录的目标路径。
        source_file: 本地源文件路径。
        strategy: 写入策略。`hardlink` 失败时自动回退复制。

    Returns:
        落地后的目标文件路径。

    Raises:
        FileNotFoundError: 源文件不存在时抛出。
        ValueError: 目标相对路径不合法时抛出。
    """

    if not source_file.is_file():
        raise FileNotFoundError(f"源文件不存在：{source_file}")
    normalized_path = _normalize_relative_game_path(relative_path)
    target_file = game_path / normalized_path
    target_file.parent.mkdir(parents=True, exist_ok=True)

    if target_file.exists():
        target_file.unlink()

    if strategy == "hardlink":
        try:
            target_file.hardlink_to(source_file)
            return target_file
        except OSError:
            shutil.copy2(source_file, target_file)
            return target_file

    shutil.copy2(source_file, target_file)
    return target_file


def cleanup_updater_inputs(game_path: Path, version_dir: Path) -> tuple[int, int]:
    """清理 Updater 阶段使用的临时输入数据。

    会删除：
    - `LeagueClient/Plugins/rcp-be-lol-game-data/*.wad`
    - `manifest/<version>/bin_input/` 目录
    - `manifest/<version>/.use_local_bin` 标志

    Args:
        game_path: 运行时游戏目录。
        version_dir: 当前版本目录（通常为 `output/manifest/<version>`）。

    Returns:
        二元组 `(removed_lcu_wad_count, removed_bin_file_count)`。
    """

    removed_lcu_wad_count = 0
    lcu_dir = game_path / "LeagueClient" / "Plugins" / "rcp-be-lol-game-data"
    if lcu_dir.is_dir():
        for wad_file in lcu_dir.glob("*.wad"):
            if wad_file.is_file():
                wad_file.unlink()
                removed_lcu_wad_count += 1

    removed_bin_file_count = 0
    bin_input_dir = version_dir / "bin_input"
    if bin_input_dir.exists():
        for file_path in bin_input_dir.rglob("*"):
            if file_path.is_file():
                removed_bin_file_count += 1
        shutil.rmtree(bin_input_dir)

    local_bin_flag = version_dir / ".use_local_bin"
    if local_bin_flag.exists():
        local_bin_flag.unlink()

    return removed_lcu_wad_count, removed_bin_file_count


def cleanup_lcu_data_wads(game_path: Path, region: str) -> int:
    """清理 DataUpdater 所需的 LCU WAD 输入文件。

    清理范围：
    - `default-assets*.wad`
    - `{region}-assets.wad`

    Args:
        game_path: 运行时游戏目录。
        region: 语言区域（例如 `zh_CN`）。

    Returns:
        已删除文件数。
    """

    lcu_dir = game_path / "LeagueClient" / "Plugins" / "rcp-be-lol-game-data"
    if not lcu_dir.is_dir():
        return 0

    targets: dict[str, Path] = {}
    patterns = (f"{region}-assets.wad", "default-assets*.wad")
    for pattern in patterns:
        for file_path in lcu_dir.glob(pattern):
            if not file_path.is_file():
                continue
            targets[file_path.as_posix().casefold()] = file_path

    removed_count = 0
    for file_path in sorted(targets.values(), key=lambda item: item.as_posix().casefold()):
        file_path.unlink(missing_ok=True)
        removed_count += 1
    return removed_count


def _normalize_relative_game_path(relative_path: str) -> Path:
    """规范化并校验游戏目录内相对路径。"""

    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("relative_wad_path 不能为空")

    path = Path(raw)
    if path.is_absolute():
        raise ValueError(f"relative_wad_path 不允许绝对路径：{relative_path}")

    normalized = Path(*[part for part in path.parts if part not in {"", "."}])
    if not normalized.parts:
        raise ValueError(f"relative_wad_path 无有效路径段：{relative_path}")
    if any(part == ".." for part in normalized.parts):
        raise ValueError(f"relative_wad_path 存在越界路径段：{relative_path}")

    return normalized


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
