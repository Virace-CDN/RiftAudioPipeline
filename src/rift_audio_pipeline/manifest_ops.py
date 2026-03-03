"""Manifest 获取与差异分析。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatestVersions:
    """最新版本信息。"""

    game_version: str
    game_manifest_url: str
    lcu_version: str
    lcu_manifest_url: str


@dataclass(frozen=True, slots=True)
class ChangedEntities:
    """变更实体集合。"""

    champion_aliases: tuple[str, ...]
    map_ids: tuple[str, ...]


def get_latest_versions() -> LatestVersions:
    """获取 GAME 和 LCU 最新版本信息。

    Returns:
        最新版本信息对象。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第二阶段实现。
    """

    raise NotImplementedError("待实现：接入 riotmanifest 获取 GAME/LCU 最新版本。")


def compare_major_minor(left_version: str, right_version: str) -> bool:
    """比较两个版本号的 `major.minor` 是否一致。

    Args:
        left_version: 左侧版本号，如 `16.4.7480682`。
        right_version: 右侧版本号，如 `16.4.7489999`。

    Returns:
        若 `major.minor` 相同返回 `True`，否则返回 `False`。
    """

    left_parts = left_version.split(".")
    right_parts = right_version.split(".")
    return left_parts[:2] == right_parts[:2]


def get_changed_entities(old_manifest_url: str, new_manifest_url: str, region: str) -> ChangedEntities:
    """获取 Manifest 差异中的变更实体。

    Args:
        old_manifest_url: 旧版本 manifest URL。
        new_manifest_url: 新版本 manifest URL。
        region: 语言区域，如 `zh_CN`。

    Returns:
        变更实体集合。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第二阶段实现。
    """

    raise NotImplementedError(
        "待实现：调用 diff_manifests 并解析英雄 alias 与地图 ID 变更。"
    )
