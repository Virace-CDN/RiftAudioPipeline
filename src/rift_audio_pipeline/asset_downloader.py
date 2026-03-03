"""基于 RiotManifest 的最小游戏环境下载组件。"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from collections.abc import Sequence
from pathlib import Path
import re
from typing import Any

from riotmanifest import PatcherManifest

from rift_audio_pipeline.game_dir_builder import stage_runtime_file

DEFAULT_DOWNLOAD_CONCURRENCY = 4
LCU_DEFAULT_ASSETS_PATTERN = r"^Plugins/rcp-be-lol-game-data/default-assets\d*\.wad$"


def download_game_content_metadata(
    game_manifest_url: str,
    download_dir: Path,
    game_path: Path,
) -> Path:
    """下载并落地 `content-metadata.json`。

    Args:
        game_manifest_url: GAME manifest URL。
        download_dir: 下载缓存目录。
        game_path: 运行时最小游戏目录。

    Returns:
        落地后的目标文件路径。
    """

    downloaded = download_manifest_exact_paths(
        manifest_url=game_manifest_url,
        download_dir=download_dir,
        exact_paths=("content-metadata.json",),
    )
    return stage_runtime_file(
        game_path=game_path,
        relative_path="Game/content-metadata.json",
        source_file=downloaded[0],
    )


def download_lcu_data_wads(
    lcu_manifest_url: str,
    download_dir: Path,
    game_path: Path,
    region: str,
) -> tuple[Path, ...]:
    """下载 DataUpdater 所需 LCU WAD 并落地到最小游戏目录。

    Args:
        lcu_manifest_url: LCU manifest URL。
        download_dir: 下载缓存目录。
        game_path: 运行时最小游戏目录。
        region: 语言区域，例如 `zh_CN`。

    Returns:
        落地后的 WAD 路径集合。
    """

    region_pattern = rf"^Plugins/rcp-be-lol-game-data/{re.escape(region)}-assets\.wad$"
    downloaded = download_manifest_patterns(
        manifest_url=lcu_manifest_url,
        download_dir=download_dir,
        patterns=(LCU_DEFAULT_ASSETS_PATTERN, region_pattern),
    )

    staged: list[Path] = []
    for source in downloaded:
        manifest_relative = source.relative_to(download_dir).as_posix()
        target_relative = _to_runtime_relative_path(manifest_relative)
        staged.append(
            stage_runtime_file(
                game_path=game_path,
                relative_path=target_relative,
                source_file=source,
            )
        )
    return tuple(staged)


def download_game_wads_by_runtime_paths(
    game_manifest_url: str,
    download_dir: Path,
    game_path: Path,
    runtime_wad_paths: Sequence[str],
) -> tuple[Path, ...]:
    """按运行时路径下载 GAME WAD 并落地到最小游戏目录。

    运行时路径通常来自 `data.msgpack` 的 `wad.root` / `wad.<region>` 字段，
    例如 `Game/DATA/FINAL/Champions/Annie.zh_CN.wad.client`。

    Args:
        game_manifest_url: GAME manifest URL。
        download_dir: 下载缓存目录。
        game_path: 运行时最小游戏目录。
        runtime_wad_paths: 运行时 WAD 路径集合。

    Returns:
        落地后的 WAD 路径集合。
    """

    manifest_paths = tuple(_to_game_manifest_path(path) for path in runtime_wad_paths)
    downloaded = download_manifest_exact_paths(
        manifest_url=game_manifest_url,
        download_dir=download_dir,
        exact_paths=manifest_paths,
    )

    staged: list[Path] = []
    for source in downloaded:
        manifest_relative = source.relative_to(download_dir).as_posix()
        staged.append(
            stage_runtime_file(
                game_path=game_path,
                relative_path=f"Game/{manifest_relative}",
                source_file=source,
            )
        )
    return tuple(staged)


def download_manifest_patterns(
    manifest_url: str,
    download_dir: Path,
    patterns: Sequence[str],
    concurrency_limit: int = DEFAULT_DOWNLOAD_CONCURRENCY,
) -> tuple[Path, ...]:
    """按正则模式批量下载 manifest 文件。

    Args:
        manifest_url: manifest URL。
        download_dir: 下载目录。
        patterns: 正则模式集合。
        concurrency_limit: 并发下载数。

    Returns:
        已下载文件路径集合（按路径排序）。
    """

    manifest = PatcherManifest(file=manifest_url, path=str(download_dir))
    files: list[Any] = []
    for pattern in patterns:
        files.extend(manifest.filter_files(pattern=pattern))
    deduped = _dedupe_manifest_files(files)
    return _download_selected_files(
        manifest=manifest,
        files=deduped,
        download_dir=download_dir,
        concurrency_limit=concurrency_limit,
    )


def download_manifest_exact_paths(
    manifest_url: str,
    download_dir: Path,
    exact_paths: Sequence[str],
    concurrency_limit: int = DEFAULT_DOWNLOAD_CONCURRENCY,
) -> tuple[Path, ...]:
    """按精确路径批量下载 manifest 文件。

    Args:
        manifest_url: manifest URL。
        download_dir: 下载目录。
        exact_paths: 清单内精确路径集合。
        concurrency_limit: 并发下载数。

    Returns:
        已下载文件路径集合（按路径排序）。

    Raises:
        FileNotFoundError: 指定路径不在清单中时抛出。
    """

    manifest = PatcherManifest(file=manifest_url, path=str(download_dir))
    index = {
        str(file_obj.name).replace("\\", "/").casefold(): file_obj
        for file_obj in manifest.files.values()
    }
    selected: list[Any] = []
    missing: list[str] = []
    for raw_path in exact_paths:
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        matched = index.get(normalized.casefold())
        if matched is None:
            missing.append(normalized)
            continue
        selected.append(matched)

    if missing:
        raise FileNotFoundError(f"以下路径不在 manifest 中：{missing}")

    deduped = _dedupe_manifest_files(selected)
    return _download_selected_files(
        manifest=manifest,
        files=deduped,
        download_dir=download_dir,
        concurrency_limit=concurrency_limit,
    )


def _download_selected_files(
    manifest: PatcherManifest,
    files: Sequence[Any],
    download_dir: Path,
    concurrency_limit: int,
) -> tuple[Path, ...]:
    """下载选定文件并返回本地路径。"""

    if not files:
        return tuple()
    download_dir.mkdir(parents=True, exist_ok=True)
    results = asyncio.run(
        manifest.download_files_concurrently(
            files=list(files),
            concurrency_limit=concurrency_limit,
            raise_on_error=False,
        )
    )
    failed = [
        str(file_obj.name) for file_obj, success in zip(files, results, strict=False) if not success
    ]
    if failed:
        raise RuntimeError(f"下载失败：{failed}")
    return tuple(
        sorted(
            (download_dir / str(file_obj.name).replace("\\", "/") for file_obj in files),
            key=lambda path: path.as_posix().casefold(),
        )
    )


def _dedupe_manifest_files(files: Iterable[Any]) -> tuple[Any, ...]:
    """按文件名去重并保持稳定顺序。"""

    seen: set[str] = set()
    deduped: list[Any] = []
    for file_obj in files:
        name = str(getattr(file_obj, "name", "")).replace("\\", "/")
        if not name:
            continue
        lowered = name.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(file_obj)
    return tuple(deduped)


def _to_game_manifest_path(runtime_path: str) -> str:
    """将运行时路径转换为 GAME manifest 路径。"""

    normalized = runtime_path.strip().replace("\\", "/")
    if normalized.startswith("Game/"):
        normalized = normalized.removeprefix("Game/")
    if normalized.startswith("DATA/"):
        return normalized
    raise ValueError(f"无法映射到 GAME manifest 路径：{runtime_path}")


def _to_runtime_relative_path(manifest_path: str) -> str:
    """将 manifest 路径映射为最小游戏目录相对路径。"""

    normalized = manifest_path.strip().replace("\\", "/")
    if normalized == "content-metadata.json":
        return "Game/content-metadata.json"
    if normalized.startswith("DATA/"):
        return f"Game/{normalized}"
    if normalized.startswith("Plugins/"):
        return f"LeagueClient/{normalized}"
    raise ValueError(f"无法映射到运行时目录路径：{manifest_path}")
