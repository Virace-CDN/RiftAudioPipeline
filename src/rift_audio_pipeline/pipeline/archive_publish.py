"""archive 发布路由辅助函数。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rift_audio_pipeline.artifact_utils import join_remote_file_path

DEFAULT_ARCHIVE_AUDIO_TYPES: tuple[str, ...] = ("VO",)
RESOURCE_TYPE_BUCKETS = ("VO", "SFX", "MUSIC")
RESOURCE_TARGET_GROUPS = ("champions", "maps")


@dataclass(frozen=True, slots=True)
class ArchivePublishLayout:
    """描述单个 archive 的远端发布路由。"""

    remote_name: str
    remote_relative_path: str
    remote_path: str
    target_group: str
    resource_type: str
    entity_key: str


def resolve_default_archive_resource_type(
    audio_types: tuple[str, ...] = DEFAULT_ARCHIVE_AUDIO_TYPES,
) -> str:
    """解析 archive 发布的默认资源类型目录。"""

    for item in audio_types:
        if not isinstance(item, str):
            continue
        normalized = item.strip().upper()
        if normalized in RESOURCE_TYPE_BUCKETS:
            return normalized
    return RESOURCE_TYPE_BUCKETS[0]


def build_archive_publish_layout(
    archive: Path,
    *,
    remote_root: str,
    default_resource_type: str,
) -> ArchivePublishLayout:
    """解析单个压缩包的远端发布路由。"""

    target_group = _resolve_archive_target_group(archive=archive)
    entity_key, _, archive_resource_type = _parse_archive_file_name(archive.name)
    resource_type = archive_resource_type or default_resource_type
    remote_relative_path = f"{resource_type}/{target_group}/{archive.name}"
    return ArchivePublishLayout(
        remote_name=archive.name,
        remote_relative_path=remote_relative_path,
        remote_path=join_remote_file_path(
            remote_dir=remote_root,
            remote_name=remote_relative_path,
        ),
        target_group=target_group,
        resource_type=resource_type,
        entity_key=entity_key,
    )


def _resolve_archive_target_group(archive: Path) -> str:
    """从本地路径解析发布目标分组。"""

    for part in reversed(archive.parts[:-1]):
        lowered = part.casefold()
        if lowered in RESOURCE_TARGET_GROUPS:
            return lowered
    return "champions"


def _parse_archive_file_name(
    archive_name: str,
) -> tuple[str, str | None, str | None]:
    """解析压缩包文件名中的实体名、版本和资源类型。"""

    stem = archive_name[:-3] if archive_name.casefold().endswith(".7z") else archive_name
    normalized_stem = stem.strip()
    if not normalized_stem:
        return archive_name, None, None
    parts = normalized_stem.rsplit("-", maxsplit=2)
    if len(parts) != 3:
        return normalized_stem, None, None
    entity_key = parts[0].strip()
    parsed_version = parts[1].strip() or None
    parsed_resource_type = parts[2].strip().upper()
    if not entity_key:
        return normalized_stem, None, None
    if parsed_resource_type not in RESOURCE_TYPE_BUCKETS:
        return normalized_stem, None, None
    return entity_key, parsed_version, parsed_resource_type
