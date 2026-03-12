"""archive 发布路由测试。"""

from __future__ import annotations

from pathlib import Path

from rift_audio_pipeline.pipeline.archive_publish import build_archive_publish_layout
from rift_audio_pipeline.pipeline.archive_publish import resolve_default_archive_resource_type


def test_resolve_default_archive_resource_type_should_choose_first_supported_type() -> None:
    """应从 audio_types 中选择首个受支持的资源类型。"""

    assert resolve_default_archive_resource_type(("music", "vo")) == "MUSIC"
    assert resolve_default_archive_resource_type(("unknown", "sfx")) == "SFX"
    assert resolve_default_archive_resource_type(("unknown",)) == "VO"


def test_build_archive_publish_layout_should_route_archive_by_group_and_type() -> None:
    """应根据文件名和目录推导 archive 发布路由。"""

    archive = Path("/tmp/output/packages/16.5/maps/11-map11-16.5-SFX.7z")

    layout = build_archive_publish_layout(
        archive,
        remote_root="/apps/test",
        default_resource_type="VO",
    )

    assert layout.remote_name == "11-map11-16.5-SFX.7z"
    assert layout.remote_relative_path == "SFX/maps/11-map11-16.5-SFX.7z"
    assert layout.remote_path == "/apps/test/SFX/maps/11-map11-16.5-SFX.7z"
    assert layout.target_group == "maps"
    assert layout.resource_type == "SFX"
    assert layout.entity_key == "11-map11"


def test_build_archive_publish_layout_should_accept_singular_directory_name() -> None:
    """单数目录名 map/champion 也应映射到正确远端分组。"""

    archive = Path("/tmp/output/packages/16.5/map/11·sr·召唤师峡谷.7z")

    layout = build_archive_publish_layout(
        archive,
        remote_root="/apps/test",
        default_resource_type="VO",
    )

    assert layout.remote_relative_path == "VO/maps/11·sr·召唤师峡谷.7z"
    assert layout.target_group == "maps"
