"""独立差异采集 workflow（第一阶段）。"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Literal

import riotmanifest

from rift_audio_pipeline.workflows.contracts import DIFF_REPORT_SCHEMA_VERSION
from rift_audio_pipeline.workflows.contracts import DiffReport
from rift_audio_pipeline.workflows.contracts import DiffReportStats
from rift_audio_pipeline.workflows.contracts import DiffSectionChange
from rift_audio_pipeline.workflows.contracts import DiffSectionStatus
from rift_audio_pipeline.workflows.contracts import DiffWadEntry
from rift_audio_pipeline.workflows.contracts import DiffWadStatus

WAD_CLIENT_PATTERN = r"wad\.client$"
DEFAULT_SECTION_STATUSES: tuple[DiffSectionStatus, ...] = ("added", "removed", "changed")
DEFAULT_WAD_STATUSES: tuple[DiffWadStatus, ...] = ("added", "removed", "changed", "error")
UPDATE_WAD_STATUSES: set[DiffWadStatus] = {"added", "removed", "changed"}
BinDataSourceMode = Literal["extractor", "download_root_wad"]


@dataclass(frozen=True, slots=True)
class _CollectCounters:
    """差异采集过程中的聚合计数器。"""

    changed_section_count: int
    resolved_section_count: int
    unresolved_section_count: int


def collect_diff_report(
    *,
    old_manifest_url: str,
    new_manifest_url: str,
    region: str,
    from_game_version: str | None = None,
    to_game_version: str | None = None,
    target_wad_files: Sequence[str] | None = None,
    include_wad_statuses: Iterable[DiffWadStatus] | None = None,
    include_section_statuses: Iterable[DiffSectionStatus] | None = None,
    max_skin_id: int = 100,
    bin_data_source_mode: BinDataSourceMode = "extractor",
) -> DiffReport:
    """执行 Manifest/WAD diff 并输出结构化差异报告。

    Args:
        old_manifest_url: 旧版 manifest URL。
        new_manifest_url: 新版 manifest URL。
        region: 区域标记（例如 `zh_CN`）。
        from_game_version: 可选旧版本号。
        to_game_version: 可选新版本号。
        target_wad_files: 可选，仅分析指定 WAD。
        include_wad_statuses: 需要纳入报告的 WAD 状态集合。
        include_section_statuses: 需要纳入报告的 section 状态集合。
        max_skin_id: BIN 路径提供器扫描皮肤上限。
        bin_data_source_mode: BIN 数据来源模式，默认 `extractor`。

    Returns:
        `DiffReport`：包含更新 WAD 与 WAD 内部文件变化信息。

    Raises:
        RuntimeError: 当前 `riotmanifest` 版本缺少必要 API 时抛出。
    """

    normalized_wad_statuses = _normalize_wad_statuses(include_wad_statuses)
    normalized_section_statuses = _normalize_section_statuses(include_section_statuses)

    manifest_report = _run_diff_manifests(
        old_manifest_url=old_manifest_url,
        new_manifest_url=new_manifest_url,
        region=region,
    )
    effective_target_wad_files = (
        tuple(target_wad_files)
        if target_wad_files is not None
        else _derive_target_wad_files_from_manifest_report(manifest_report)
    )
    if not effective_target_wad_files:
        return _build_empty_diff_report(
            region=region,
            old_manifest_url=old_manifest_url,
            new_manifest_url=new_manifest_url,
            from_game_version=from_game_version,
            to_game_version=to_game_version,
        )

    wad_report = _run_diff_wad_headers(
        manifest_report=manifest_report,
        target_wad_files=effective_target_wad_files,
    )
    resolved_report = _run_resolve_wad_diff_paths(
        wad_report=wad_report,
        include_section_statuses=normalized_section_statuses,
        max_skin_id=max_skin_id,
        bin_data_source_mode=bin_data_source_mode,
    )

    wad_entries, counters = _build_wad_entries(
        resolved_report=resolved_report,
        include_wad_statuses=normalized_wad_statuses,
        include_section_statuses=normalized_section_statuses,
    )
    update_wad_count = sum(1 for item in wad_entries if item.status in UPDATE_WAD_STATUSES)

    stats = DiffReportStats(
        total_wad_count=len(wad_entries),
        update_wad_count=update_wad_count,
        changed_section_count=counters.changed_section_count,
        resolved_section_count=counters.resolved_section_count,
        unresolved_section_count=counters.unresolved_section_count,
    )
    has_changes = update_wad_count > 0
    return DiffReport(
        schema_version=DIFF_REPORT_SCHEMA_VERSION,
        region=region,
        from_manifest_url=old_manifest_url,
        to_manifest_url=new_manifest_url,
        from_game_version=from_game_version,
        to_game_version=to_game_version,
        has_changes=has_changes,
        wads=wad_entries,
        stats=stats,
    )


def _run_diff_manifests(
    *,
    old_manifest_url: str,
    new_manifest_url: str,
    region: str,
) -> Any:
    """执行 `diff_manifests`。"""

    diff_manifests_func = getattr(riotmanifest, "diff_manifests", None)
    if not callable(diff_manifests_func):
        raise RuntimeError("当前 riotmanifest 版本缺少 diff_manifests，请先升级依赖。")
    return diff_manifests_func(
        old_manifest_url,
        new_manifest_url,
        flags=region,
        pattern=WAD_CLIENT_PATTERN,
        include_unchanged=False,
        detect_moves=False,
    )


def _run_diff_wad_headers(
    *,
    manifest_report: Any,
    target_wad_files: Sequence[str] | None,
) -> Any:
    """执行 `diff_wad_headers`。"""

    diff_wad_headers_func = getattr(riotmanifest, "diff_wad_headers", None)
    if not callable(diff_wad_headers_func):
        raise RuntimeError("当前 riotmanifest 版本缺少 diff_wad_headers，请先升级依赖。")
    return diff_wad_headers_func(
        manifest_report=manifest_report,
        target_wad_files=target_wad_files,
        include_unchanged=False,
    )


def _derive_target_wad_files_from_manifest_report(manifest_report: Any) -> tuple[str, ...]:
    """从 Manifest diff 结果提取待比对 WAD 路径列表。"""

    paths: dict[str, str] = {}
    for section_name in ("added", "changed", "removed"):
        for entry in getattr(manifest_report, section_name, tuple()):
            path = _extract_entry_path(entry)
            if path is None:
                continue
            key = path.casefold()
            paths.setdefault(key, path)
    return tuple(sorted(paths.values(), key=str.casefold))


def _extract_entry_path(entry: Any) -> str | None:
    """从 diff 条目对象或字典读取 `path` 字段。"""

    if isinstance(entry, dict):
        path = entry.get("path")
    else:
        path = getattr(entry, "path", None)
    if not isinstance(path, str):
        return None
    normalized = path.strip()
    if not normalized:
        return None
    return normalized


def _run_resolve_wad_diff_paths(
    *,
    wad_report: Any,
    include_section_statuses: set[DiffSectionStatus],
    max_skin_id: int,
    bin_data_source_mode: BinDataSourceMode,
) -> Any:
    """执行 `resolve_wad_diff_paths` 并回填真实路径。"""

    provider_cls = getattr(riotmanifest, "ManifestBinPathProvider", None)
    if not callable(provider_cls):
        raise RuntimeError(
            "当前 riotmanifest 版本缺少 ManifestBinPathProvider，"
            "请升级到包含 resolve_wad_diff_paths 的版本。"
        )
    resolve_func = getattr(riotmanifest, "resolve_wad_diff_paths", None)
    if not callable(resolve_func):
        raise RuntimeError("当前 riotmanifest 版本缺少 resolve_wad_diff_paths，请先升级依赖。")

    with provider_cls(max_skin_id=max_skin_id) as provider:
        return resolve_func(
            wad_report,
            path_provider=provider,
            include_section_statuses=tuple(sorted(include_section_statuses)),
            bin_data_source_mode=bin_data_source_mode,
        )


def _build_wad_entries(
    *,
    resolved_report: Any,
    include_wad_statuses: set[DiffWadStatus],
    include_section_statuses: set[DiffSectionStatus],
) -> tuple[tuple[DiffWadEntry, ...], _CollectCounters]:
    """从回填后的报告提取项目内部契约结构。"""

    entries: list[DiffWadEntry] = []
    changed_section_count = 0
    resolved_section_count = 0
    unresolved_section_count = 0

    for file_entry in getattr(resolved_report, "files", tuple()):
        wad_status = _normalize_status(getattr(file_entry, "status", "error"), default="error")
        if wad_status not in include_wad_statuses:
            continue

        changes: list[DiffSectionChange] = []
        for section_diff in getattr(file_entry, "section_diffs", tuple()):
            section_status = _normalize_status(
                getattr(section_diff, "status", "changed"),
                default="changed",
            )
            if section_status not in include_section_statuses:
                continue

            path_hash = getattr(section_diff, "path_hash", None)
            if not isinstance(path_hash, int):
                continue

            real_path_raw = getattr(section_diff, "path", None)
            real_path = real_path_raw if isinstance(real_path_raw, str) and real_path_raw else None
            path_hash_hex = format_path_hash_hex(path_hash)
            final_path = real_path or path_hash_hex
            changed_section_count += 1
            if real_path is None:
                unresolved_section_count += 1
            else:
                resolved_section_count += 1

            changes.append(
                DiffSectionChange(
                    status=section_status,
                    path=final_path,
                    real_path=real_path,
                    path_hash=path_hash_hex,
                )
            )

        warning_raw = getattr(file_entry, "warning", None)
        warning = warning_raw if isinstance(warning_raw, str) and warning_raw else None
        wad_path_raw = getattr(file_entry, "wad_path", "")
        wad_path = str(wad_path_raw)
        entries.append(
            DiffWadEntry(
                wad_path=wad_path,
                status=wad_status,
                changed_count=len(changes),
                changes=tuple(changes),
                warning=warning,
            )
        )

    counters = _CollectCounters(
        changed_section_count=changed_section_count,
        resolved_section_count=resolved_section_count,
        unresolved_section_count=unresolved_section_count,
    )
    return tuple(entries), counters


def _normalize_wad_statuses(
    statuses: Iterable[DiffWadStatus] | None,
) -> set[DiffWadStatus]:
    """规范化 WAD 状态过滤集合。"""

    allowed: set[DiffWadStatus] = {"added", "removed", "changed", "unchanged", "error"}
    if statuses is None:
        return set(DEFAULT_WAD_STATUSES)
    normalized = {item for item in statuses if item in allowed}
    return normalized or set(DEFAULT_WAD_STATUSES)


def _normalize_section_statuses(
    statuses: Iterable[DiffSectionStatus] | None,
) -> set[DiffSectionStatus]:
    """规范化 section 状态过滤集合。"""

    allowed: set[DiffSectionStatus] = {"added", "removed", "changed", "unchanged"}
    if statuses is None:
        return set(DEFAULT_SECTION_STATUSES)
    normalized = {item for item in statuses if item in allowed}
    return normalized or set(DEFAULT_SECTION_STATUSES)


def _normalize_status(value: Any, *, default: str) -> Any:
    """将外部状态值规范化为内部字符串。"""

    if isinstance(value, str) and value:
        return value
    return default


def _build_empty_diff_report(
    *,
    region: str,
    old_manifest_url: str,
    new_manifest_url: str,
    from_game_version: str | None,
    to_game_version: str | None,
) -> DiffReport:
    """构建无目标 WAD 时的空差异报告。"""

    return DiffReport(
        schema_version=DIFF_REPORT_SCHEMA_VERSION,
        region=region,
        from_manifest_url=old_manifest_url,
        to_manifest_url=new_manifest_url,
        from_game_version=from_game_version,
        to_game_version=to_game_version,
        has_changes=False,
        wads=tuple(),
        stats=DiffReportStats(
            total_wad_count=0,
            update_wad_count=0,
            changed_section_count=0,
            resolved_section_count=0,
            unresolved_section_count=0,
        ),
    )


def format_path_hash_hex(path_hash: int) -> str:
    """格式化 `path_hash` 字段为十六进制字符串。"""

    return f"0x{path_hash:016x}"
