"""Pipeline 纯工具函数集合。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import hashlib
from pathlib import Path
import shutil


def _parse_game_version_sort_key(game_version: str, fallback: str) -> tuple[int, ...]:
    """将版本号解析为可排序键。"""

    normalized = game_version.strip()
    if not normalized:
        return (-1, -1, -1, -1)
    parts = normalized.split(".")
    parsed: list[int] = []
    for part in parts[:4]:
        if part.isdigit():
            parsed.append(int(part))
        else:
            parsed.append(-1)
    while len(parsed) < 4:
        parsed.append(-1)
    if all(value == -1 for value in parsed):
        stable_tail = sum(ord(char) for char in fallback.casefold()) % 1_000_000
        return (-1, -1, -1, stable_tail)
    return tuple(parsed)


def _build_update_log_text(payload: dict[str, object]) -> str:
    """将结构化更新日志渲染为人类可读文本。"""

    changed_entities_obj = payload.get("changed_entities")
    changed_entities = changed_entities_obj if isinstance(changed_entities_obj, dict) else {}
    wad_changes_obj = payload.get("wad_changes")
    wad_changes = wad_changes_obj if isinstance(wad_changes_obj, dict) else {}
    upload_summary_obj = payload.get("upload_summary")
    upload_summary = upload_summary_obj if isinstance(upload_summary_obj, dict) else {}
    lines = [
        "# RiftAudioPipeline 差异更新日志",
        "",
        f"执行时间(UTC): {payload.get('executed_at')}",
        f"决策原因: {payload.get('decision_reason')}",
        f"版本区间: {payload.get('from_game_version')} -> {payload.get('to_game_version')}",
        "",
        "## 变更实体",
        f"- champions(alias): {', '.join(changed_entities.get('champion_aliases', [])) or '无'}",
        f"- maps(id): {', '.join(changed_entities.get('map_ids', [])) or '无'}",
        "",
        "## WAD 变更",
        f"- added: {len(wad_changes.get('added_paths', []))}",
        f"- changed: {len(wad_changes.get('changed_paths', []))}",
        f"- removed: {len(wad_changes.get('removed_paths', []))}",
        f"- update_paths: {len(wad_changes.get('update_paths', []))}",
    ]
    secondary_filter_obj = payload.get("secondary_filter")
    if isinstance(secondary_filter_obj, dict):
        lines.extend(
            (
                "",
                "## 二次筛选",
                f"- 需解包 WAD: {len(secondary_filter_obj.get('unpack_paths', []))}",
                f"- 可跳过 WAD: {len(secondary_filter_obj.get('skipped_paths', []))}",
            )
        )
        decisions_obj = secondary_filter_obj.get("decisions", [])
        if isinstance(decisions_obj, list):
            for item in decisions_obj:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "- WAD: "
                    f"{item.get('region_wad_path')} | should_unpack={item.get('should_unpack')} | "
                    f"skip_reason={item.get('skip_reason')}"
                )
                lines.append(
                    f"  changed_audio={len(item.get('changed_audio_paths', []))}, "
                    f"changed_event={len(item.get('changed_event_paths', []))}"
                )
    lines.extend(
        (
            "",
            "## 上传结果",
            f"- run_entry_count: {upload_summary.get('run_entry_count', 0)}",
            f"- uploaded_count: {upload_summary.get('uploaded_count', 0)}",
            f"- skipped_count: {upload_summary.get('skipped_count', 0)}",
            f"- archived_count: {upload_summary.get('archived_count', 0)}",
        )
    )
    entries_obj = upload_summary.get("entries")
    if isinstance(entries_obj, list):
        for item in entries_obj:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"{item.get('status')} | {item.get('remote_name') or item.get('remote_path')} | "
                f"reason={item.get('reason')}"
            )
    lines.append("")
    return "\n".join(lines)


def _calculate_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""

    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_upload_manifest_index(entries: object) -> dict[str, dict[str, object]]:
    """将远端索引条目转换为高效查询结构。"""

    if not isinstance(entries, list):
        raise ValueError("远端索引格式错误：`entries` 必须为列表。")

    index: dict[str, dict[str, object]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            continue

        remote_path_obj = raw_entry.get("remote_path")
        if not (isinstance(remote_path_obj, str) and remote_path_obj.strip()):
            continue

        remote_path = remote_path_obj.strip().replace("\\", "/")
        remote_name = str(raw_entry.get("remote_name") or Path(remote_path).name).strip()
        game_version = (
            str(raw_entry.get("game_version")).strip()
            if isinstance(raw_entry.get("game_version"), str)
            else ""
        )
        normalized_entry: dict[str, object] = {
            "remote_path": remote_path,
            "remote_name": remote_name,
            "game_version": game_version or None,
            "uploaded_at": raw_entry.get("uploaded_at"),
        }
        for field_name in ("bucket", "target_group", "resource_type", "entity_key"):
            field_value = raw_entry.get(field_name)
            if isinstance(field_value, str) and field_value.strip():
                normalized_entry[field_name] = field_value.strip()
        size_obj = _coerce_non_negative_int(raw_entry.get("size"))
        if size_obj is not None:
            normalized_entry["size"] = size_obj
        sha256_obj = raw_entry.get("sha256")
        if isinstance(sha256_obj, str) and sha256_obj.strip():
            normalized_entry["sha256"] = sha256_obj.strip().lower()
        index[remote_path.casefold()] = normalized_entry
    return index


def _join_remote_file_path(remote_dir: str, remote_name: str) -> str:
    """拼接远端目录和文件名。"""

    normalized_name = remote_name.strip().replace("\\", "/").lstrip("/")
    if not normalized_name:
        raise ValueError("上传阶段失败：远端文件名不能为空。")

    normalized_dir = remote_dir.strip().replace("\\", "/").strip("/")
    if not normalized_dir:
        return f"/{normalized_name}"
    return f"/{normalized_dir}/{normalized_name}"


def _is_same_index_entry(
    entry: dict[str, object],
    expected_remote_name: str,
    expected_game_version: str,
) -> bool:
    """按文件名与版本号判断索引条目是否匹配。"""

    indexed_name = entry.get("remote_name")
    if isinstance(indexed_name, str) and indexed_name.strip():
        if indexed_name.strip() != expected_remote_name:
            return False

    indexed_version = entry.get("game_version")
    if indexed_version is None:
        return True
    if not isinstance(indexed_version, str):
        return False
    return indexed_version.strip() == expected_game_version


def _current_utc_timestamp() -> str:
    """返回 UTC ISO-8601 时间戳。"""

    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _coerce_non_negative_int(value: object) -> int | None:
    """将对象转换为非负整数。"""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def _cleanup_simulated_runtime_files(
    runtime_game_path: Path,
    runtime_download_dir: Path,
) -> tuple[int, int]:
    """清理模拟目录下临时 WAD 与下载缓存。"""

    runtime_wad_dirs = (
        runtime_game_path / "Game" / "DATA" / "FINAL" / "Champions",
        runtime_game_path / "Game" / "DATA" / "FINAL" / "Maps" / "Shipping",
    )
    removed_runtime_wads = 0
    for directory in runtime_wad_dirs:
        if not directory.is_dir():
            continue
        for item in directory.rglob("*"):
            if item.is_file() and item.name.casefold().endswith(".wad.client"):
                item.unlink()
                removed_runtime_wads += 1

    removed_download_cache = 0
    if runtime_download_dir.expanduser().resolve() == runtime_game_path.expanduser().resolve():
        return removed_runtime_wads, removed_download_cache
    if runtime_download_dir.exists():
        for item in runtime_download_dir.rglob("*"):
            if item.is_file():
                removed_download_cache += 1
        shutil.rmtree(runtime_download_dir, ignore_errors=True)

    return removed_runtime_wads, removed_download_cache


def _merge_runtime_wad_paths(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """合并运行时 WAD 路径并去重排序。"""

    deduped: dict[str, str] = {}
    for group in groups:
        for path in group:
            normalized = path.strip().replace("\\", "/")
            if not normalized:
                continue
            deduped.setdefault(normalized.casefold(), normalized)
    return tuple(sorted(deduped.values(), key=str.casefold))


def _normalize_pipeline_game_version(game_version: str) -> str:
    """将版本号标准化为 `major.minor`，用于本地路径与打包命名。"""

    normalized = game_version.strip()
    if not normalized:
        return normalized
    parts = normalized.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{parts[1]}"
    return normalized


def _build_runtime_wad_paths_from_manifest_paths(
    manifest_paths: tuple[str, ...],
    region: str,
    include_root_wad: bool = True,
) -> tuple[str, ...]:
    """将 manifest WAD 路径转换为运行时根/区域路径集合。"""

    runtime_paths: dict[str, str] = {}
    region_suffix = f".{region}.wad.client"
    for raw_path in manifest_paths:
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith("Game/"):
            normalized = normalized.removeprefix("Game/")
        if not normalized.startswith("DATA/"):
            continue

        region_runtime_path = f"Game/{normalized}"
        runtime_paths.setdefault(region_runtime_path.casefold(), region_runtime_path)

        lowered = normalized.casefold()
        if include_root_wad and lowered.endswith(region_suffix.casefold()):
            root_manifest_path = f"{normalized[: len(normalized) - len(region_suffix)]}.wad.client"
            root_runtime_path = f"Game/{root_manifest_path}"
            runtime_paths.setdefault(root_runtime_path.casefold(), root_runtime_path)

    return tuple(sorted(runtime_paths.values(), key=str.casefold))


def _cleanup_version_audio_outputs(version_audio_dir: Path) -> int:
    """清理已打包版本的音频目录，降低上传阶段磁盘占用。"""

    if not version_audio_dir.is_dir():
        return 0

    removed_files = 0
    for item in version_audio_dir.rglob("*"):
        if item.is_file():
            removed_files += 1
    shutil.rmtree(version_audio_dir, ignore_errors=True)
    return removed_files
