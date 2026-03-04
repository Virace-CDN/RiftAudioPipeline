"""Manifest 获取、版本状态判断与差异分析。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any
from typing import Literal
from typing import TypeAlias

from league_tools.formats import BIN
from riotmanifest import PatcherManifest
from riotmanifest import RiotGameData
from riotmanifest import WADExtractor
from riotmanifest import diff_manifests

DEFAULT_GAME_RELEASE_REGION = "EUW1"
DEFAULT_LCU_RELEASE_REGION = "EUW"
DEFAULT_LOCAL_STATE_FILE = Path(__file__).resolve().parents[2] / "state" / "run_history.json"
LOCAL_STATE_SCHEMA_VERSION = 1
WAD_CLIENT_FILE_PATTERN = r"wad\.client$"
LOCALIZED_WAD_SEGMENT = "/localized/"
DEFAULT_MAX_CHAMPION_SKIN_BIN_INDEX = 260
BIN_PROBE_BATCH_SIZE = 80
DEFAULT_VOICE_FILTER_UNIT_MAX_WORKERS = 4
DEFAULT_VOICE_FILTER_EXTRACTOR_PREFETCH_CONCURRENCY = 6

VOICE_AUDIO_SUFFIXES = ("_vo_audio.bnk", "_vo_audio.wpk")
VOICE_EVENTS_SUFFIX = "_vo_events.bnk"

CHAMPION_WAD_PATH_PATTERN = re.compile(
    r"^DATA/FINAL/Champions/(?:[^/]+/)?(?P<alias>[^/.]+)\.[^.]+\.wad\.client$",
    re.IGNORECASE,
)
CHAMPION_ROOT_WAD_PATH_PATTERN = re.compile(
    r"^DATA/FINAL/Champions/(?:[^/]+/)?(?P<alias>[^/.]+)\.wad\.client$",
    re.IGNORECASE,
)
MAP_WAD_PATH_PATTERN = re.compile(
    r"^DATA/FINAL/Maps/Shipping/(?:Map(?P<map_id_dir>\d+)/)?Map(?P<map_id_file>\d+)\.[^.]+\.wad\.client$",
    re.IGNORECASE,
)
MAP_ROOT_WAD_PATH_PATTERN = re.compile(
    r"^DATA/FINAL/Maps/Shipping/(?:Map(?P<map_id_dir>\d+)/)?Map(?P<map_id_file>\d+)\.wad\.client$",
    re.IGNORECASE,
)
MAP_COMMON_ROOT_WAD_PATH_PATTERN = re.compile(
    r"^DATA/FINAL/Maps/Shipping/(?:Common/)?Common\.wad\.client$",
    re.IGNORECASE,
)

DECISION_REASON_FIRST_RUN = "first_run"
DECISION_REASON_GAME_VERSION_UNCHANGED = "game_version_unchanged"
DECISION_REASON_NO_REGION_MANIFEST_CHANGES = "no_region_manifest_changes"
DECISION_REASON_REGION_MANIFEST_CHANGED = "region_manifest_changed"

VoicePathDiffStatus: TypeAlias = Literal["added", "removed", "changed", "unchanged", "missing"]
SectionSignature: TypeAlias = tuple[int, int, int, int, bool, int | None]


@dataclass(frozen=True, slots=True)
class LatestVersions:
    """最新版本信息。"""

    game_version: str
    game_manifest_url: str
    lcu_version: str
    lcu_manifest_url: str


@dataclass(frozen=True, slots=True)
class LocalRunState:
    """本地历史状态。"""

    schema_version: int
    game_version: str
    game_manifest_url: str
    lcu_version: str
    lcu_manifest_url: str
    checked_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocalRunState:
        """从字典反序列化状态对象。

        Args:
            data: JSON 字典。

        Returns:
            状态对象。

        Raises:
            ValueError: 字段缺失或类型不合法时抛出。
        """

        required_fields = (
            "schema_version",
            "game_version",
            "game_manifest_url",
            "lcu_version",
            "lcu_manifest_url",
            "checked_at",
        )
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise ValueError(f"本地状态缺少字段：{missing}")
        return cls(
            schema_version=int(data["schema_version"]),
            game_version=str(data["game_version"]),
            game_manifest_url=str(data["game_manifest_url"]),
            lcu_version=str(data["lcu_version"]),
            lcu_manifest_url=str(data["lcu_manifest_url"]),
            checked_at=str(data["checked_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化状态对象。"""

        return dict(asdict(self))


@dataclass(frozen=True, slots=True)
class ChangedEntities:
    """变更实体集合。"""

    champion_aliases: tuple[str, ...]
    map_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManifestWadChanges:
    """Manifest WAD 路径差异结果。"""

    added_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    removed_paths: tuple[str, ...]

    @property
    def update_paths(self) -> tuple[str, ...]:
        """返回需要更新下载的路径集合（added + changed）。"""

        return tuple(sorted(set(self.added_paths + self.changed_paths)))


@dataclass(frozen=True, slots=True)
class UpdateDecision:
    """更新判定结果。"""

    should_update: bool
    reason: str
    latest_versions: LatestVersions
    previous_state: LocalRunState | None
    changed_entities: ChangedEntities
    wad_changes: ManifestWadChanges


@dataclass(frozen=True, slots=True)
class VoicePathStatus:
    """单个语音资源路径的旧新版本差异状态。"""

    path: str
    status: VoicePathDiffStatus
    path_type: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VoicePathStatus:
        """从字典反序列化路径状态。"""

        return cls(
            path=str(data.get("path", "")),
            status=str(data.get("status", "missing")),  # type: ignore[arg-type]
            path_type=str(data.get("path_type", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""

        return dict(asdict(self))


@dataclass(frozen=True, slots=True)
class WadVoiceFilterDecision:
    """单个 WAD 的二次筛选判定结果。"""

    region_wad_path: str
    root_wad_path: str | None
    entity_type: str
    matched_bin_paths: tuple[str, ...]
    audio_paths: tuple[str, ...]
    event_paths: tuple[str, ...]
    path_statuses: tuple[VoicePathStatus, ...]
    changed_audio_paths: tuple[str, ...]
    changed_event_paths: tuple[str, ...]
    should_unpack: bool
    skip_reason: str | None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WadVoiceFilterDecision:
        """从字典反序列化单个 WAD 判定结果。"""

        path_statuses_raw = data.get("path_statuses", tuple())
        path_statuses = tuple(
            VoicePathStatus.from_dict(item)
            for item in path_statuses_raw
            if isinstance(item, Mapping)
        )
        return cls(
            region_wad_path=str(data.get("region_wad_path", "")),
            root_wad_path=(
                str(data.get("root_wad_path")) if data.get("root_wad_path") is not None else None
            ),
            entity_type=str(data.get("entity_type", "")),
            matched_bin_paths=tuple(str(item) for item in data.get("matched_bin_paths", tuple())),
            audio_paths=tuple(str(item) for item in data.get("audio_paths", tuple())),
            event_paths=tuple(str(item) for item in data.get("event_paths", tuple())),
            path_statuses=path_statuses,
            changed_audio_paths=tuple(
                str(item) for item in data.get("changed_audio_paths", tuple())
            ),
            changed_event_paths=tuple(
                str(item) for item in data.get("changed_event_paths", tuple())
            ),
            should_unpack=bool(data.get("should_unpack", False)),
            skip_reason=(
                str(data.get("skip_reason")) if data.get("skip_reason") is not None else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""

        return {
            "region_wad_path": self.region_wad_path,
            "root_wad_path": self.root_wad_path,
            "entity_type": self.entity_type,
            "matched_bin_paths": list(self.matched_bin_paths),
            "audio_paths": list(self.audio_paths),
            "event_paths": list(self.event_paths),
            "path_statuses": [item.to_dict() for item in self.path_statuses],
            "changed_audio_paths": list(self.changed_audio_paths),
            "changed_event_paths": list(self.changed_event_paths),
            "should_unpack": self.should_unpack,
            "skip_reason": self.skip_reason,
        }


@dataclass(frozen=True, slots=True)
class ManifestVoiceFilterResult:
    """WAD 二次筛选汇总结果。"""

    unpack_paths: tuple[str, ...]
    skipped_paths: tuple[str, ...]
    decisions: tuple[WadVoiceFilterDecision, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ManifestVoiceFilterResult:
        """从字典反序列化二次筛选汇总结果。"""

        decisions_raw = data.get("decisions", tuple())
        decisions = tuple(
            WadVoiceFilterDecision.from_dict(item)
            for item in decisions_raw
            if isinstance(item, Mapping)
        )
        return cls(
            unpack_paths=tuple(str(item) for item in data.get("unpack_paths", tuple())),
            skipped_paths=tuple(str(item) for item in data.get("skipped_paths", tuple())),
            decisions=decisions,
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""

        return {
            "unpack_paths": list(self.unpack_paths),
            "skipped_paths": list(self.skipped_paths),
            "decisions": [item.to_dict() for item in self.decisions],
        }


def get_latest_versions(
    game_release_region: str = DEFAULT_GAME_RELEASE_REGION,
    lcu_release_region: str = DEFAULT_LCU_RELEASE_REGION,
) -> LatestVersions:
    """获取 GAME 和 LCU 最新版本信息。

    Args:
        game_release_region: GAME 版本来源区域。
        lcu_release_region: LCU 版本来源区域。

    Returns:
        最新版本信息对象。

    Raises:
        RuntimeError: 指定区域无可用版本数据。
    """

    game_data = RiotGameData()
    game_data.load_lcu_data()
    game_data.load_game_data(regions=[game_release_region])

    latest_game = game_data.latest_game(game_release_region)
    latest_lcu = game_data.latest_lcu(lcu_release_region)
    if latest_game is None:
        raise RuntimeError(f"无法获取 GAME 最新版本，区域={game_release_region}")
    if latest_lcu is None:
        raise RuntimeError(f"无法获取 LCU 最新版本，区域={lcu_release_region}")

    return LatestVersions(
        game_version=latest_game["version"],
        game_manifest_url=latest_game["url"],
        lcu_version=latest_lcu["version"],
        lcu_manifest_url=latest_lcu["url"],
    )


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


def get_manifest_wad_changes(
    old_manifest_url: str,
    new_manifest_url: str,
    region: str,
) -> ManifestWadChanges:
    """获取指定区域 WAD 的路径差异。

    Args:
        old_manifest_url: 旧版本 manifest URL。
        new_manifest_url: 新版本 manifest URL。
        region: 语言区域，如 `zh_CN`。

    Returns:
        路径差异结果（added/changed/removed）。
    """
    report = diff_manifests(
        old_manifest_url,
        new_manifest_url,
        flags=region,
        pattern=WAD_CLIENT_FILE_PATTERN,
        include_unchanged=False,
    )
    added_paths = {
        str(_extract_diff_entry_path(entry)) for entry in getattr(report, "added", tuple())
    }
    changed_paths = {
        str(_extract_diff_entry_path(entry)) for entry in getattr(report, "changed", tuple())
    }
    removed_paths = {
        str(_extract_diff_entry_path(entry)) for entry in getattr(report, "removed", tuple())
    }

    return ManifestWadChanges(
        added_paths=tuple(sorted(added_paths, key=str.casefold)),
        changed_paths=tuple(sorted(changed_paths, key=str.casefold)),
        removed_paths=tuple(sorted(removed_paths, key=str.casefold)),
    )


def get_changed_entities(
    old_manifest_url: str, new_manifest_url: str, region: str
) -> ChangedEntities:
    """获取 Manifest 差异中的变更实体。

    Args:
        old_manifest_url: 旧版本 manifest URL。
        new_manifest_url: 新版本 manifest URL。
        region: 语言区域，如 `zh_CN`。

    Returns:
        变更实体集合。
    """

    wad_changes = get_manifest_wad_changes(
        old_manifest_url=old_manifest_url,
        new_manifest_url=new_manifest_url,
        region=region,
    )
    return _extract_changed_entities_from_paths(
        paths=set(wad_changes.added_paths + wad_changes.changed_paths + wad_changes.removed_paths),
    )


def extract_changed_entities_from_wad_paths(paths: Sequence[str]) -> ChangedEntities:
    """从区域 WAD 路径集合提取英雄 alias 与地图 ID。

    Args:
        paths: 区域 WAD 路径集合。

    Returns:
        变更实体集合。
    """

    normalized_paths = {
        _normalize_manifest_path(path) for path in paths if isinstance(path, str) and path.strip()
    }
    return _extract_changed_entities_from_paths(paths=normalized_paths)


def filter_wad_changes_by_bin_voice_paths(
    old_manifest_url: str,
    new_manifest_url: str,
    region: str,
    update_paths: Sequence[str],
    max_champion_skin_bin_index: int = DEFAULT_MAX_CHAMPION_SKIN_BIN_INDEX,
    unit_max_workers: int = DEFAULT_VOICE_FILTER_UNIT_MAX_WORKERS,
    extractor_prefetch_chunk_concurrency: int = (
        DEFAULT_VOICE_FILTER_EXTRACTOR_PREFETCH_CONCURRENCY
    ),
    bin_output_dir: Path | None = None,
) -> ManifestVoiceFilterResult:
    """基于根 WAD 的 BIN 解析结果筛选真正需要解包的区域 WAD。

    规则：
    - 跳过 `Localized` 路径。
    - 不做路径字符串拼接推导，语音资源路径一律来自 BIN 解析。
    - 仅当 `*_vo_audio.bnk` 或 `*_vo_audio.wpk` 发生变化时判定为“需要解包”。
    - 仅 `*_vo_events.bnk` 变化时标记为“可跳过资源解包”。

    Args:
        old_manifest_url: 旧版本 manifest URL。
        new_manifest_url: 新版本 manifest URL。
        region: 语言区域（例如 `zh_CN`）。
        update_paths: 来自 manifest diff 的区域 WAD 变化路径（通常为 `added + changed`）。
        max_champion_skin_bin_index: 英雄 BIN 探测上限（包含该值）。
        unit_max_workers: 以英雄/地图为单位并发筛选时的最大并发数。
        extractor_prefetch_chunk_concurrency: WADExtractor 内部预取下载并发
            （映射 `prefetch_chunk_concurrency`）。
        bin_output_dir: 可选 BIN 落地目录；传入后会在筛选阶段直接写入 BIN 文件。

    Returns:
        二次筛选结果，包含“需解包路径”、“可跳过路径”与每个 WAD 的明细判定。

    Raises:
        ValueError: 参数不合法时抛出。
        RuntimeError: BIN 解析失败时抛出。
    """

    if max_champion_skin_bin_index < 0:
        raise ValueError(
            f"max_champion_skin_bin_index 必须为非负整数，当前值={max_champion_skin_bin_index}"
        )
    if unit_max_workers < 1:
        raise ValueError(f"unit_max_workers 必须 >= 1，当前值={unit_max_workers}")
    if extractor_prefetch_chunk_concurrency < 1:
        raise ValueError(
            "extractor_prefetch_chunk_concurrency 必须 >= 1，"
            f"当前值={extractor_prefetch_chunk_concurrency}"
        )

    normalized_paths = _normalize_update_paths(update_paths)
    if not normalized_paths:
        return ManifestVoiceFilterResult(
            unpack_paths=tuple(),
            skipped_paths=tuple(),
            decisions=tuple(),
        )

    old_manifest = PatcherManifest(file=old_manifest_url, path="")
    new_manifest = PatcherManifest(file=new_manifest_url, path="")
    old_file_index = _build_manifest_file_index(old_manifest)
    new_file_index = _build_manifest_file_index(new_manifest)

    decisions: list[WadVoiceFilterDecision] = []
    on_bin_payloads: Callable[[WadVoiceFilterDecision, Mapping[str, bytes]], None] | None = None
    if bin_output_dir is not None:
        _prepare_voice_filter_bin_output_dir(bin_output_dir=bin_output_dir)
        written_bin_keys: set[str] = set()

        def _on_bin_payloads(
            decision: WadVoiceFilterDecision,
            bin_payloads: Mapping[str, bytes],
        ) -> None:
            del decision
            for raw_path, content in sorted(bin_payloads.items(), key=lambda item: item[0].casefold()):
                normalized_path = _normalize_manifest_path(raw_path)
                lowered = normalized_path.casefold()
                if lowered in written_bin_keys:
                    continue
                _write_voice_filter_bin_output_file(
                    bin_output_dir=bin_output_dir,
                    relative_path=normalized_path,
                    content=content,
                )
                written_bin_keys.add(lowered)

        on_bin_payloads = _on_bin_payloads

    grouped_wad_paths = _group_update_paths_by_root_wad(update_paths=normalized_paths, region=region)
    effective_workers = min(unit_max_workers, len(grouped_wad_paths))
    collected_bin_payloads: list[tuple[WadVoiceFilterDecision, dict[str, bytes]]] = []
    if effective_workers <= 1:
        for wad_paths in grouped_wad_paths:
            group_decisions, group_payloads = _build_wad_voice_filter_decisions_for_group(
                old_manifest=old_manifest,
                new_manifest=new_manifest,
                old_file_index=old_file_index,
                new_file_index=new_file_index,
                region=region,
                wad_paths=wad_paths,
                max_champion_skin_bin_index=max_champion_skin_bin_index,
                extractor_prefetch_chunk_concurrency=extractor_prefetch_chunk_concurrency,
                collect_bin_payloads=on_bin_payloads is not None,
            )
            decisions.extend(group_decisions)
            collected_bin_payloads.extend(group_payloads)
    else:
        grouped_results: dict[
            int,
            tuple[
                tuple[WadVoiceFilterDecision, ...],
                tuple[tuple[WadVoiceFilterDecision, dict[str, bytes]], ...],
            ],
        ] = {}
        with ThreadPoolExecutor(
            max_workers=effective_workers,
            thread_name_prefix="wad-bin-filter",
        ) as executor:
            future_to_index = {
                executor.submit(
                    _build_wad_voice_filter_decisions_for_group,
                    old_manifest=old_manifest,
                    new_manifest=new_manifest,
                    old_file_index=old_file_index,
                    new_file_index=new_file_index,
                    region=region,
                    wad_paths=wad_paths,
                    max_champion_skin_bin_index=max_champion_skin_bin_index,
                    extractor_prefetch_chunk_concurrency=extractor_prefetch_chunk_concurrency,
                    collect_bin_payloads=on_bin_payloads is not None,
                ): index
                for index, wad_paths in enumerate(grouped_wad_paths)
            }
            for future in as_completed(future_to_index):
                grouped_results[future_to_index[future]] = future.result()
        for group_index in sorted(grouped_results):
            group_decisions, group_payloads = grouped_results[group_index]
            decisions.extend(group_decisions)
            collected_bin_payloads.extend(group_payloads)

    if on_bin_payloads is not None:
        for decision_item, bin_payloads in collected_bin_payloads:
            on_bin_payloads(decision_item, bin_payloads)

    unpack_paths = tuple(
        sorted(
            {item.region_wad_path for item in decisions if item.should_unpack},
            key=str.casefold,
        )
    )
    skipped_paths = tuple(
        sorted(
            {item.region_wad_path for item in decisions if not item.should_unpack},
            key=str.casefold,
        )
    )
    result = ManifestVoiceFilterResult(
        unpack_paths=unpack_paths,
        skipped_paths=skipped_paths,
        decisions=tuple(sorted(decisions, key=lambda item: item.region_wad_path.casefold())),
    )
    return result


def _prepare_voice_filter_bin_output_dir(bin_output_dir: Path) -> None:
    """准备 BIN 输出目录。

    Args:
        bin_output_dir: BIN 输出目录。
    """

    if bin_output_dir.exists():
        shutil.rmtree(bin_output_dir, ignore_errors=True)
    bin_output_dir.mkdir(parents=True, exist_ok=True)


def _write_voice_filter_bin_output_file(
    bin_output_dir: Path,
    relative_path: str,
    content: bytes,
) -> Path:
    """写入单个 BIN 原始数据到输出目录。

    Args:
        bin_output_dir: BIN 输出目录。
        relative_path: BIN 相对路径。
        content: BIN 原始字节。

    Returns:
        已写入的目标文件路径。
    """

    normalized_path = _normalize_relative_bin_output_path(relative_path)
    target_file = bin_output_dir / normalized_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_bytes(content)
    return target_file


def _normalize_relative_bin_output_path(relative_path: str) -> Path:
    """规范化 BIN 输出相对路径并阻止越界。

    Args:
        relative_path: 原始相对路径。

    Returns:
        规范化后的相对路径对象。

    Raises:
        ValueError: 输入为空、绝对路径或包含越界段时抛出。
    """

    raw = _normalize_manifest_path(relative_path)
    if not raw:
        raise ValueError("BIN 输出路径不能为空")
    path = Path(raw)
    if path.is_absolute():
        raise ValueError(f"BIN 输出路径不允许绝对路径：{relative_path}")
    normalized = Path(*[part for part in path.parts if part not in {"", "."}])
    if not normalized.parts:
        raise ValueError(f"BIN 输出路径无有效路径段：{relative_path}")
    if any(part == ".." for part in normalized.parts):
        raise ValueError(f"BIN 输出路径存在越界路径段：{relative_path}")
    return normalized


def _build_wad_voice_filter_decision(
    old_extractor: WADExtractor,
    new_extractor: WADExtractor,
    old_file_index: Mapping[str, Any],
    new_file_index: Mapping[str, Any],
    region: str,
    wad_path: str,
    max_champion_skin_bin_index: int,
    on_bin_payloads: Callable[[WadVoiceFilterDecision, Mapping[str, bytes]], None] | None = None,
) -> WadVoiceFilterDecision:
    """构建单个区域 WAD 的二次筛选判定。

    Args:
        old_extractor: 旧版本 WAD 提取器。
        new_extractor: 新版本 WAD 提取器。
        old_file_index: 旧版本 manifest 文件索引。
        new_file_index: 新版本 manifest 文件索引。
        region: 语言区域。
        wad_path: 目标区域 WAD 路径。
        max_champion_skin_bin_index: 英雄 BIN 探测上限。
        on_bin_payloads: 可选回调；当判定需解包时回传该 WAD 命中的 BIN 原始数据。

    Returns:
        单个 WAD 的筛选判定结果。
    """

    normalized_wad_path = _normalize_manifest_path(wad_path)
    if LOCALIZED_WAD_SEGMENT in normalized_wad_path.casefold():
        return WadVoiceFilterDecision(
            region_wad_path=normalized_wad_path,
            root_wad_path=None,
            entity_type="localized",
            matched_bin_paths=tuple(),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=tuple(),
            changed_event_paths=tuple(),
            should_unpack=False,
            skip_reason="Localized 目录不在处理范围",
        )

    root_wad_path = _resolve_root_wad_path(normalized_wad_path, region=region)
    if root_wad_path is None:
        return WadVoiceFilterDecision(
            region_wad_path=normalized_wad_path,
            root_wad_path=None,
            entity_type="unknown",
            matched_bin_paths=tuple(),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=tuple(),
            changed_event_paths=tuple(),
            should_unpack=False,
            skip_reason=f"无法根据 region={region} 推导根 WAD 路径",
        )

    entity_type, candidate_bin_paths = _build_candidate_bin_paths(
        root_wad_path=root_wad_path,
        max_champion_skin_bin_index=max_champion_skin_bin_index,
    )
    if not candidate_bin_paths:
        return WadVoiceFilterDecision(
            region_wad_path=normalized_wad_path,
            root_wad_path=root_wad_path,
            entity_type=entity_type,
            matched_bin_paths=tuple(),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=tuple(),
            changed_event_paths=tuple(),
            should_unpack=False,
            skip_reason="未识别出可探测的 BIN 路径",
        )

    if root_wad_path.casefold() not in new_file_index:
        return WadVoiceFilterDecision(
            region_wad_path=normalized_wad_path,
            root_wad_path=root_wad_path,
            entity_type=entity_type,
            matched_bin_paths=tuple(),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=tuple(),
            changed_event_paths=tuple(),
            should_unpack=False,
            skip_reason="新版本 manifest 中不存在对应根 WAD",
        )

    bin_raws = _extract_existing_bin_raws(
        extractor=new_extractor,
        root_wad_path=root_wad_path,
        candidate_bin_paths=candidate_bin_paths,
    )
    if not bin_raws:
        return WadVoiceFilterDecision(
            region_wad_path=normalized_wad_path,
            root_wad_path=root_wad_path,
            entity_type=entity_type,
            matched_bin_paths=tuple(),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=tuple(),
            changed_event_paths=tuple(),
            should_unpack=False,
            skip_reason="根 WAD 中未命中任何可解析 BIN",
        )

    audio_paths, event_paths = _collect_voice_paths_from_bin_raws(
        root_wad_path=root_wad_path,
        bin_raws=bin_raws,
    )
    if not audio_paths and not event_paths:
        return WadVoiceFilterDecision(
            region_wad_path=normalized_wad_path,
            root_wad_path=root_wad_path,
            entity_type=entity_type,
            matched_bin_paths=tuple(sorted(bin_raws.keys(), key=str.casefold)),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=tuple(),
            changed_event_paths=tuple(),
            should_unpack=False,
            skip_reason="BIN 未解析到 VO 资源路径",
        )

    path_statuses = _collect_voice_path_statuses(
        old_extractor=old_extractor,
        new_extractor=new_extractor,
        old_file_index=old_file_index,
        new_file_index=new_file_index,
        region_wad_path=normalized_wad_path,
        audio_paths=audio_paths,
        event_paths=event_paths,
    )
    changed_audio_paths = tuple(
        sorted(
            {
                item.path
                for item in path_statuses
                if item.path_type == "audio" and item.status in {"added", "removed", "changed"}
            },
            key=str.casefold,
        )
    )
    changed_event_paths = tuple(
        sorted(
            {
                item.path
                for item in path_statuses
                if item.path_type == "event" and item.status in {"added", "removed", "changed"}
            },
            key=str.casefold,
        )
    )
    should_unpack = bool(changed_audio_paths)
    if should_unpack:
        skip_reason = None
    elif changed_event_paths:
        skip_reason = "仅 vo_events 变更，按规则跳过资源解包"
    else:
        skip_reason = "VO 音频资源未发生变化"

    decision = WadVoiceFilterDecision(
        region_wad_path=normalized_wad_path,
        root_wad_path=root_wad_path,
        entity_type=entity_type,
        matched_bin_paths=tuple(sorted(bin_raws.keys(), key=str.casefold)),
        audio_paths=audio_paths,
        event_paths=event_paths,
        path_statuses=path_statuses,
        changed_audio_paths=changed_audio_paths,
        changed_event_paths=changed_event_paths,
        should_unpack=should_unpack,
        skip_reason=skip_reason,
    )
    if should_unpack and on_bin_payloads is not None:
        on_bin_payloads(decision, bin_raws)
    return decision


def _collect_voice_path_statuses(
    old_extractor: WADExtractor,
    new_extractor: WADExtractor,
    old_file_index: Mapping[str, Any],
    new_file_index: Mapping[str, Any],
    region_wad_path: str,
    audio_paths: tuple[str, ...],
    event_paths: tuple[str, ...],
) -> tuple[VoicePathStatus, ...]:
    """收集语音路径状态（added/removed/changed/unchanged/missing）。"""

    old_header = _load_wad_header(
        extractor=old_extractor,
        file_index=old_file_index,
        wad_path=region_wad_path,
    )
    new_header = _load_wad_header(
        extractor=new_extractor,
        file_index=new_file_index,
        wad_path=region_wad_path,
    )
    old_sections = _build_wad_section_index(old_header) if old_header is not None else {}
    new_sections = _build_wad_section_index(new_header) if new_header is not None else {}

    statuses: list[VoicePathStatus] = []
    for path in audio_paths:
        statuses.append(
            VoicePathStatus(
                path=path,
                status=_diff_inner_path_status(
                    path=path,
                    old_header=old_header,
                    new_header=new_header,
                    old_sections=old_sections,
                    new_sections=new_sections,
                ),
                path_type="audio",
            )
        )
    for path in event_paths:
        statuses.append(
            VoicePathStatus(
                path=path,
                status=_diff_inner_path_status(
                    path=path,
                    old_header=old_header,
                    new_header=new_header,
                    old_sections=old_sections,
                    new_sections=new_sections,
                ),
                path_type="event",
            )
        )
    return tuple(sorted(statuses, key=lambda item: (item.path_type, item.path.casefold())))


def _load_wad_header(
    extractor: WADExtractor,
    file_index: Mapping[str, Any],
    wad_path: str,
) -> Any | None:
    """按路径加载 WAD 头；文件不存在时返回 `None`。"""

    file_obj = file_index.get(wad_path.casefold())
    if file_obj is None:
        return None
    return extractor.get_wad_header(file_obj)


def _build_manifest_file_index(manifest: PatcherManifest) -> dict[str, Any]:
    """构建 manifest 文件索引（key 为小写路径）。"""

    return {str(file.name).casefold(): file for file in manifest.files.values()}


def _extract_existing_bin_raws(
    extractor: WADExtractor,
    root_wad_path: str,
    candidate_bin_paths: Sequence[str],
) -> dict[str, bytes]:
    """从根 WAD 中提取存在的 BIN 原始数据。"""

    existing: dict[str, bytes] = {}
    for start in range(0, len(candidate_bin_paths), BIN_PROBE_BATCH_SIZE):
        chunk = list(candidate_bin_paths[start : start + BIN_PROBE_BATCH_SIZE])
        if not chunk:
            continue
        result = extractor.extract_files({root_wad_path: chunk})
        wad_result = result.get(root_wad_path, {})
        if not isinstance(wad_result, Mapping):
            continue
        for bin_path, raw in wad_result.items():
            if isinstance(raw, (bytes, bytearray)) and raw:
                existing[str(bin_path)] = bytes(raw)
    return existing


def _collect_voice_paths_from_bin_raws(
    root_wad_path: str,
    bin_raws: Mapping[str, bytes],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """从 BIN 数据提取并分类语音资源路径。"""

    bank_paths: list[str] = []
    for bin_path, raw in bin_raws.items():
        try:
            bin_file = BIN(raw)
        except Exception as error:  # noqa: BLE001
            raise RuntimeError(
                f"解析 BIN 失败，root_wad={root_wad_path}, bin={bin_path}"
            ) from error
        for group in getattr(bin_file, "data", tuple()):
            for bank_unit in getattr(group, "bank_units", tuple()):
                values = getattr(bank_unit, "bank_path", None)
                if not values:
                    continue
                for value in values:
                    if isinstance(value, str) and value.strip():
                        bank_paths.append(value.strip())
    return _classify_voice_bank_paths(bank_paths)


def _classify_voice_bank_paths(paths: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """按规则将路径分类为 audio 与 event。"""

    audio: dict[str, str] = {}
    events: dict[str, str] = {}
    for path in paths:
        normalized = _normalize_manifest_path(path)
        lowered = normalized.casefold()
        if "_vo_" not in lowered:
            continue
        if lowered.endswith(VOICE_AUDIO_SUFFIXES):
            audio.setdefault(lowered, normalized)
            continue
        if lowered.endswith(VOICE_EVENTS_SUFFIX):
            events.setdefault(lowered, normalized)
    return (
        tuple(sorted(audio.values(), key=str.casefold)),
        tuple(sorted(events.values(), key=str.casefold)),
    )


def _build_wad_section_index(header: Any) -> dict[int, tuple[SectionSignature, ...]]:
    """为 WAD 头构建按 `path_hash` 索引的 section 签名集合。"""

    index: dict[int, list[SectionSignature]] = {}
    for section in getattr(header, "files", tuple()):
        signature: SectionSignature = (
            int(section.size),
            int(section.compressed_size),
            int(section.type),
            int(getattr(section, "subchunk_count", 0)),
            bool(getattr(section, "duplicate", False)),
            _as_optional_int(getattr(section, "sha256", None)),
        )
        path_hash = int(section.path_hash)
        index.setdefault(path_hash, []).append(signature)
    return {path_hash: tuple(sorted(values)) for path_hash, values in index.items()}


def _diff_inner_path_status(
    path: str,
    old_header: Any | None,
    new_header: Any | None,
    old_sections: Mapping[int, tuple[SectionSignature, ...]],
    new_sections: Mapping[int, tuple[SectionSignature, ...]],
) -> VoicePathDiffStatus:
    """比较单一路径在旧新 WAD 中的 section 状态。"""

    candidate_hashes: set[int] = set()
    if old_header is not None:
        candidate_hashes.add(_resolve_wad_path_hash(old_header, path))
    if new_header is not None:
        candidate_hashes.add(_resolve_wad_path_hash(new_header, path))
    if not candidate_hashes:
        return "missing"

    old_values = _collect_sections_by_hashes(old_sections, candidate_hashes)
    new_values = _collect_sections_by_hashes(new_sections, candidate_hashes)
    if not old_values and not new_values:
        return "missing"
    if not old_values:
        return "added"
    if not new_values:
        return "removed"
    if old_values == new_values:
        return "unchanged"
    return "changed"


def _collect_sections_by_hashes(
    section_index: Mapping[int, tuple[SectionSignature, ...]],
    path_hashes: set[int],
) -> tuple[SectionSignature, ...]:
    """按哈希集合聚合 section 签名。"""

    values: list[SectionSignature] = []
    for path_hash in sorted(path_hashes):
        values.extend(section_index.get(path_hash, tuple()))
    return tuple(sorted(values))


def _resolve_wad_path_hash(header: Any, path: str) -> int:
    """按 WAD 版本算法计算路径哈希。"""

    hash_func = getattr(header, "_get_hash_for_path", None)
    if callable(hash_func):
        return int(hash_func(path))
    fallback = getattr(type(header), "get_hash", None)
    if callable(fallback):
        return int(fallback(path))
    raise ValueError(f"当前 WAD 头对象不支持路径哈希计算: {type(header)!r}")


def _build_candidate_bin_paths(
    root_wad_path: str,
    max_champion_skin_bin_index: int,
) -> tuple[str, tuple[str, ...]]:
    """按根 WAD 类型构造 BIN 探测路径。"""

    champion_match = CHAMPION_ROOT_WAD_PATH_PATTERN.match(root_wad_path)
    if champion_match is not None:
        alias = champion_match.group("alias").casefold()
        candidates = tuple(
            f"data/characters/{alias}/skins/skin{index}.bin"
            for index in range(max_champion_skin_bin_index + 1)
        )
        return "champion", candidates

    map_match = MAP_ROOT_WAD_PATH_PATTERN.match(root_wad_path)
    if map_match is not None:
        map_id = map_match.group("map_id_file") or map_match.group("map_id_dir")
        if map_id is not None:
            map_name = f"map{map_id}"
            return "map", (f"data/maps/shipping/{map_name}/{map_name}.bin",)

    if MAP_COMMON_ROOT_WAD_PATH_PATTERN.match(root_wad_path) is not None:
        return "map", ("data/maps/shipping/common/common.bin",)

    return "unknown", tuple()


def _resolve_root_wad_path(region_wad_path: str, region: str) -> str | None:
    """将 `xx.<region>.wad.client` 映射到根 WAD 路径 `xx.wad.client`。"""

    normalized = _normalize_manifest_path(region_wad_path)
    region_suffix = f".{region}.wad.client"
    lowered = normalized.casefold()
    if not lowered.endswith(region_suffix.casefold()):
        return None
    return f"{normalized[: len(normalized) - len(region_suffix)]}.wad.client"


def _normalize_update_paths(update_paths: Sequence[str]) -> tuple[str, ...]:
    """标准化并去重 WAD 路径列表。"""

    return tuple(
        sorted(
            {
                _normalize_manifest_path(path)
                for path in update_paths
                if isinstance(path, str) and path.strip()
            },
            key=str.casefold,
        )
    )


def _group_update_paths_by_root_wad(
    update_paths: Sequence[str],
    region: str,
) -> tuple[tuple[str, ...], ...]:
    """按根 WAD（英雄/地图单位）对区域 WAD 路径分组。"""

    grouped: dict[str, list[str]] = {}
    for raw_path in update_paths:
        normalized_path = _normalize_manifest_path(raw_path)
        root_wad_path = _resolve_root_wad_path(region_wad_path=normalized_path, region=region)
        if root_wad_path is None:
            group_key = f"path::{normalized_path.casefold()}"
        else:
            group_key = f"root::{_normalize_manifest_path(root_wad_path).casefold()}"
        grouped.setdefault(group_key, []).append(normalized_path)
    return tuple(
        tuple(sorted(set(paths), key=str.casefold))
        for _, paths in sorted(grouped.items(), key=lambda item: item[0].casefold())
    )


def _build_wad_voice_filter_decisions_for_group(
    old_manifest: PatcherManifest,
    new_manifest: PatcherManifest,
    old_file_index: Mapping[str, Any],
    new_file_index: Mapping[str, Any],
    region: str,
    wad_paths: Sequence[str],
    max_champion_skin_bin_index: int,
    extractor_prefetch_chunk_concurrency: int,
    collect_bin_payloads: bool,
) -> tuple[
    tuple[WadVoiceFilterDecision, ...],
    tuple[tuple[WadVoiceFilterDecision, dict[str, bytes]], ...],
]:
    """按单个单位分组执行 WAD 二次筛选。"""

    decisions: list[WadVoiceFilterDecision] = []
    captured_payloads: list[tuple[WadVoiceFilterDecision, dict[str, bytes]]] = []

    def _capture_bin_payloads(
        decision: WadVoiceFilterDecision,
        bin_payloads: Mapping[str, bytes],
    ) -> None:
        normalized_payloads = {
            str(path): bytes(content)
            for path, content in bin_payloads.items()
            if isinstance(path, str) and isinstance(content, (bytes, bytearray)) and content
        }
        if normalized_payloads:
            captured_payloads.append((decision, normalized_payloads))

    with WADExtractor(
        new_manifest,
        prefetch_chunk_concurrency=extractor_prefetch_chunk_concurrency,
    ) as new_extractor, WADExtractor(
        old_manifest,
        prefetch_chunk_concurrency=extractor_prefetch_chunk_concurrency,
    ) as old_extractor:
        for wad_path in wad_paths:
            decision = _build_wad_voice_filter_decision(
                old_extractor=old_extractor,
                new_extractor=new_extractor,
                old_file_index=old_file_index,
                new_file_index=new_file_index,
                region=region,
                wad_path=wad_path,
                max_champion_skin_bin_index=max_champion_skin_bin_index,
                on_bin_payloads=_capture_bin_payloads if collect_bin_payloads else None,
            )
            decisions.append(decision)
    return tuple(decisions), tuple(captured_payloads)


def _normalize_manifest_path(path: str) -> str:
    """统一清洗 manifest 路径分隔符与首尾空白。"""

    return path.strip().replace("\\", "/")


def _as_optional_int(value: Any) -> int | None:
    """将可选整数值转为 `int | None`。"""

    if value is None:
        return None
    return int(value)


def _extract_diff_entry_path(entry: Any) -> str:
    """提取 diff 条目中的路径字段。"""

    if isinstance(entry, dict):
        value = entry.get("path")
    else:
        value = getattr(entry, "path", None)
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError(f"diff 条目缺少合法 path 字段：{entry!r}")


def load_local_state(state_file: Path = DEFAULT_LOCAL_STATE_FILE) -> LocalRunState | None:
    """读取本地历史状态。

    Args:
        state_file: 本地状态文件路径。

    Returns:
        读取到的状态对象；文件不存在时返回 `None`。

    Raises:
        ValueError: 状态文件 JSON 格式非法时抛出。
    """

    resolved_file = state_file.expanduser().resolve()
    if not resolved_file.exists():
        return None

    payload = json.loads(resolved_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"本地状态格式错误，期望 JSON 对象：{resolved_file}")
    return LocalRunState.from_dict(payload)


def save_local_state(
    state: LocalRunState,
    state_file: Path = DEFAULT_LOCAL_STATE_FILE,
) -> Path:
    """写入本地历史状态。

    Args:
        state: 状态对象。
        state_file: 写入目标路径。

    Returns:
        已写入文件路径。
    """

    resolved_file = state_file.expanduser().resolve()
    resolved_file.parent.mkdir(parents=True, exist_ok=True)
    resolved_file.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resolved_file


def build_local_state(latest_versions: LatestVersions) -> LocalRunState:
    """根据最新版本构造状态对象。

    Args:
        latest_versions: 最新版本信息。

    Returns:
        本地状态对象。
    """

    checked_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return LocalRunState(
        schema_version=LOCAL_STATE_SCHEMA_VERSION,
        game_version=latest_versions.game_version,
        game_manifest_url=latest_versions.game_manifest_url,
        lcu_version=latest_versions.lcu_version,
        lcu_manifest_url=latest_versions.lcu_manifest_url,
        checked_at=checked_at,
    )


def evaluate_update_need(
    region: str,
    state_file: Path = DEFAULT_LOCAL_STATE_FILE,
    game_release_region: str = DEFAULT_GAME_RELEASE_REGION,
    lcu_release_region: str = DEFAULT_LCU_RELEASE_REGION,
) -> UpdateDecision:
    """评估是否需要进入后续更新流程。

    Args:
        region: 语言区域标识（例如 `zh_CN`）。
        state_file: 本地状态文件路径。
        game_release_region: GAME 版本来源区域。
        lcu_release_region: LCU 版本来源区域。

    Returns:
        更新判定结果。
    """

    latest_versions = get_latest_versions(
        game_release_region=game_release_region,
        lcu_release_region=lcu_release_region,
    )
    try:
        previous_state = load_local_state(state_file=state_file)
    except ValueError:
        previous_state = None
    return evaluate_update_need_with_latest(
        region=region,
        latest_versions=latest_versions,
        previous_state=previous_state,
    )


def evaluate_update_need_with_latest(
    region: str,
    latest_versions: LatestVersions,
    previous_state: LocalRunState | None,
) -> UpdateDecision:
    """基于给定最新版本与历史状态评估更新需求。

    Args:
        region: 语言区域标识（例如 `zh_CN`）。
        latest_versions: 最新版本信息。
        previous_state: 历史状态，首次执行可为 `None`。

    Returns:
        更新判定结果。
    """

    empty_changes = ChangedEntities(champion_aliases=tuple(), map_ids=tuple())
    empty_wad_changes = ManifestWadChanges(
        added_paths=tuple(),
        changed_paths=tuple(),
        removed_paths=tuple(),
    )

    if previous_state is None:
        return UpdateDecision(
            should_update=True,
            reason=DECISION_REASON_FIRST_RUN,
            latest_versions=latest_versions,
            previous_state=None,
            changed_entities=empty_changes,
            wad_changes=empty_wad_changes,
        )

    if previous_state.game_version == latest_versions.game_version:
        return UpdateDecision(
            should_update=False,
            reason=DECISION_REASON_GAME_VERSION_UNCHANGED,
            latest_versions=latest_versions,
            previous_state=previous_state,
            changed_entities=empty_changes,
            wad_changes=empty_wad_changes,
        )

    wad_changes = get_manifest_wad_changes(
        old_manifest_url=previous_state.game_manifest_url,
        new_manifest_url=latest_versions.game_manifest_url,
        region=region,
    )
    changed_entities = _extract_changed_entities_from_paths(
        paths=set(wad_changes.added_paths + wad_changes.changed_paths + wad_changes.removed_paths),
    )
    has_region_changes = bool(
        wad_changes.added_paths or wad_changes.changed_paths or wad_changes.removed_paths
    )
    return UpdateDecision(
        should_update=has_region_changes,
        reason=(
            DECISION_REASON_REGION_MANIFEST_CHANGED
            if has_region_changes
            else DECISION_REASON_NO_REGION_MANIFEST_CHANGES
        ),
        latest_versions=latest_versions,
        previous_state=previous_state,
        changed_entities=changed_entities,
        wad_changes=wad_changes,
    )


def _extract_changed_entities_from_paths(paths: set[str]) -> ChangedEntities:
    """从路径集合中提取英雄 alias 与地图 ID。"""

    champion_aliases: set[str] = set()
    map_ids: set[str] = set()
    for path in paths:
        normalized = path.replace("\\", "/")
        champion_match = CHAMPION_WAD_PATH_PATTERN.match(normalized)
        if champion_match is not None:
            champion_aliases.add(champion_match.group("alias"))
            continue
        map_match = MAP_WAD_PATH_PATTERN.match(normalized)
        if map_match is not None:
            map_id = map_match.group("map_id_file") or map_match.group("map_id_dir")
            if map_id is not None:
                map_ids.add(map_id)
    return ChangedEntities(
        champion_aliases=tuple(sorted(champion_aliases, key=str.casefold)),
        map_ids=tuple(sorted(map_ids, key=lambda item: int(item))),
    )
