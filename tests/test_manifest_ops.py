"""Manifest 版本与更新判定测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from rift_audio_pipeline.manifest_ops import ChangedEntities
from rift_audio_pipeline.manifest_ops import DECISION_REASON_FIRST_RUN
from rift_audio_pipeline.manifest_ops import DECISION_REASON_GAME_VERSION_UNCHANGED
from rift_audio_pipeline.manifest_ops import DECISION_REASON_NO_REGION_MANIFEST_CHANGES
from rift_audio_pipeline.manifest_ops import DECISION_REASON_REGION_MANIFEST_CHANGED
from rift_audio_pipeline.manifest_ops import LatestVersions
from rift_audio_pipeline.manifest_ops import LocalRunState
from rift_audio_pipeline.manifest_ops import ManifestVoiceFilterResult
from rift_audio_pipeline.manifest_ops import ManifestWadChanges
from rift_audio_pipeline.manifest_ops import VoicePathStatus
from rift_audio_pipeline.manifest_ops import WadVoiceFilterDecision
from rift_audio_pipeline.manifest_ops import build_local_state
from rift_audio_pipeline.manifest_ops import compare_major_minor
from rift_audio_pipeline.manifest_ops import evaluate_update_need
from rift_audio_pipeline.manifest_ops import extract_changed_entities_from_wad_paths
from rift_audio_pipeline.manifest_ops import filter_wad_changes_by_bin_voice_paths
from rift_audio_pipeline.manifest_ops import get_changed_entities
from rift_audio_pipeline.manifest_ops import get_manifest_wad_changes
from rift_audio_pipeline.manifest_ops import load_local_state
from rift_audio_pipeline.manifest_ops import save_local_state
import rift_audio_pipeline.manifest_ops as manifest_ops


class _FakeDiffEntry:
    """模拟 diff 条目。"""

    def __init__(self, path: str) -> None:
        self.path = path


class _FakeDiffReport:
    """模拟 diff 报告对象。"""

    def __init__(
        self,
        added: tuple[Any, ...],
        changed: tuple[Any, ...],
        removed: tuple[Any, ...],
    ) -> None:
        self.added = added
        self.changed = changed
        self.removed = removed


def _make_latest_versions(
    game_version: str = "16.4.7480682",
    game_manifest_url: str = "https://example.test/game-new.manifest",
    lcu_version: str = "16.4",
    lcu_manifest_url: str = "https://example.test/lcu-new.manifest",
) -> LatestVersions:
    """构造测试用最新版本对象。"""

    return LatestVersions(
        game_version=game_version,
        game_manifest_url=game_manifest_url,
        lcu_version=lcu_version,
        lcu_manifest_url=lcu_manifest_url,
    )


def _make_state(
    game_version: str = "16.3.7457600",
    game_manifest_url: str = "https://example.test/game-old.manifest",
) -> LocalRunState:
    """构造测试用本地状态对象。"""

    return LocalRunState(
        schema_version=1,
        game_version=game_version,
        game_manifest_url=game_manifest_url,
        lcu_version="16.3",
        lcu_manifest_url="https://example.test/lcu-old.manifest",
        checked_at="2026-03-03T00:00:00Z",
    )


def test_compare_major_minor_should_compare_first_two_segments() -> None:
    """版本比较应只比较 major.minor。"""

    assert compare_major_minor("16.4.7480682", "16.4.7489999") is True
    assert compare_major_minor("16.4.7480682", "16.5.7489999") is False


def test_state_round_trip_should_preserve_values(tmp_path: Path) -> None:
    """本地状态读写应可往返。"""

    state_file = tmp_path / "state" / "run_history.json"
    latest = _make_latest_versions()
    state = build_local_state(latest_versions=latest)

    saved_file = save_local_state(state=state, state_file=state_file)
    loaded = load_local_state(state_file=saved_file)

    assert loaded is not None
    assert loaded.game_version == latest.game_version
    assert loaded.game_manifest_url == latest.game_manifest_url
    assert loaded.lcu_version == latest.lcu_version


def test_get_manifest_wad_changes_should_split_added_changed_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WAD 路径差异应正确拆分 added/changed/removed。"""

    def _fake_diff_manifests(
        old_manifest: str,
        new_manifest: str,
        *,
        flags: str,
        pattern: str,
        include_unchanged: bool,
    ) -> _FakeDiffReport:
        assert old_manifest == "https://example.test/old.manifest"
        assert new_manifest == "https://example.test/new.manifest"
        assert flags == "zh_CN"
        assert pattern == r"wad\.client$"
        assert include_unchanged is False
        return _FakeDiffReport(
            added=(_FakeDiffEntry("DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client"),),
            changed=(_FakeDiffEntry("DATA/FINAL/Champions/Renata.zh_CN.wad.client"),),
            removed=(_FakeDiffEntry("DATA/FINAL/Maps/Shipping/Map30/Map30.zh_CN.wad.client"),),
        )

    monkeypatch.setattr(manifest_ops, "diff_manifests", _fake_diff_manifests)

    changes = get_manifest_wad_changes(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
    )

    assert changes.added_paths == ("DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",)
    assert changes.changed_paths == ("DATA/FINAL/Champions/Renata.zh_CN.wad.client",)
    assert changes.removed_paths == ("DATA/FINAL/Maps/Shipping/Map30/Map30.zh_CN.wad.client",)
    assert changes.update_paths == (
        "DATA/FINAL/Champions/Renata.zh_CN.wad.client",
        "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",
    )


def test_get_manifest_wad_changes_should_support_dict_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """diff 条目为字典时也应正确读取 path。"""

    def _fake_diff_manifests(*_: Any, **__: Any) -> _FakeDiffReport:
        return _FakeDiffReport(
            added=({"path": "DATA/FINAL/Champions/Ahri.zh_CN.wad.client"},),
            changed=tuple(),
            removed=tuple(),
        )

    monkeypatch.setattr(manifest_ops, "diff_manifests", _fake_diff_manifests)

    changes = get_manifest_wad_changes(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
    )

    assert changes.added_paths == ("DATA/FINAL/Champions/Ahri.zh_CN.wad.client",)
    assert changes.changed_paths == tuple()
    assert changes.removed_paths == tuple()


def test_get_changed_entities_should_extract_champions_and_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """应从 diff 结果提取英雄别名与地图 ID。"""

    monkeypatch.setattr(
        manifest_ops,
        "get_manifest_wad_changes",
        lambda **_: ManifestWadChanges(
            added_paths=(
                "DATA/FINAL/Champions/Renata.zh_CN.wad.client",
                "DATA/FINAL/Maps/Shipping/Map22/Map22.zh_CN.wad.client",
            ),
            changed_paths=("DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",),
            removed_paths=("DATA/FINAL/Maps/Shipping/Map30/Map30.zh_CN.wad.client",),
        ),
    )

    entities = get_changed_entities(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
    )

    assert entities.champion_aliases == ("Renata",)
    assert entities.map_ids == ("11", "22", "30")


def test_extract_changed_entities_from_wad_paths_should_normalize_and_extract() -> None:
    """应从给定路径集合中提取实体并忽略非法空值。"""

    entities = extract_changed_entities_from_wad_paths(
        paths=(
            "DATA\\FINAL\\Champions\\Ahri.zh_CN.wad.client",
            "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",
            "   ",
        ),
    )

    assert entities.champion_aliases == ("Ahri",)
    assert entities.map_ids == ("11",)


def test_evaluate_update_need_should_require_update_on_first_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """首次运行（无状态文件）应判定需要更新。"""

    monkeypatch.setattr(manifest_ops, "get_latest_versions", lambda **_: _make_latest_versions())
    monkeypatch.setattr(manifest_ops, "load_local_state", lambda **_: None)

    decision = evaluate_update_need(region="zh_CN", state_file=tmp_path / "missing.json")

    assert decision.should_update is True
    assert decision.reason == DECISION_REASON_FIRST_RUN
    assert decision.changed_entities == ChangedEntities(champion_aliases=tuple(), map_ids=tuple())
    assert decision.wad_changes == ManifestWadChanges(
        added_paths=tuple(),
        changed_paths=tuple(),
        removed_paths=tuple(),
    )


def test_evaluate_update_need_should_skip_when_game_version_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """GAME 版本未变化时应直接跳过。"""

    latest = _make_latest_versions(game_version="16.4.7480682")
    previous = _make_state(game_version="16.4.7480682")
    monkeypatch.setattr(manifest_ops, "get_latest_versions", lambda **_: latest)
    monkeypatch.setattr(manifest_ops, "load_local_state", lambda **_: previous)

    decision = evaluate_update_need(region="zh_CN", state_file=tmp_path / "run_history.json")

    assert decision.should_update is False
    assert decision.reason == DECISION_REASON_GAME_VERSION_UNCHANGED
    assert decision.wad_changes.update_paths == tuple()


def test_evaluate_update_need_should_skip_when_no_region_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """版本变化但目标区域无变更时应跳过。"""

    latest = _make_latest_versions(game_version="16.5.7496037")
    previous = _make_state(game_version="16.4.7480682")
    monkeypatch.setattr(manifest_ops, "get_latest_versions", lambda **_: latest)
    monkeypatch.setattr(manifest_ops, "load_local_state", lambda **_: previous)
    monkeypatch.setattr(
        manifest_ops,
        "get_manifest_wad_changes",
        lambda **_: ManifestWadChanges(
            added_paths=tuple(),
            changed_paths=tuple(),
            removed_paths=tuple(),
        ),
    )

    decision = evaluate_update_need(region="zh_CN", state_file=tmp_path / "run_history.json")

    assert decision.should_update is False
    assert decision.reason == DECISION_REASON_NO_REGION_MANIFEST_CHANGES


def test_evaluate_update_need_should_require_update_when_region_changed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """版本变化且目标区域有实体变更时应更新。"""

    latest = _make_latest_versions(game_version="16.5.7496037")
    previous = _make_state(game_version="16.4.7480682")
    monkeypatch.setattr(manifest_ops, "get_latest_versions", lambda **_: latest)
    monkeypatch.setattr(manifest_ops, "load_local_state", lambda **_: previous)
    monkeypatch.setattr(
        manifest_ops,
        "get_manifest_wad_changes",
        lambda **_: ManifestWadChanges(
            added_paths=("DATA/FINAL/Champions/Annie.zh_CN.wad.client",),
            changed_paths=("DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",),
            removed_paths=tuple(),
        ),
    )

    decision = evaluate_update_need(region="zh_CN", state_file=tmp_path / "run_history.json")

    assert decision.should_update is True
    assert decision.reason == DECISION_REASON_REGION_MANIFEST_CHANGED
    assert decision.changed_entities.champion_aliases == ("Annie",)
    assert decision.changed_entities.map_ids == ("11",)
    assert decision.wad_changes.update_paths == (
        "DATA/FINAL/Champions/Annie.zh_CN.wad.client",
        "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",
    )


def test_load_local_state_should_raise_on_invalid_json_object(
    tmp_path: Path,
) -> None:
    """状态文件为非 JSON 对象时应抛出异常。"""

    state_file = tmp_path / "state" / "run_history.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="本地状态格式错误"):
        load_local_state(state_file=state_file)


def test_evaluate_update_need_should_fallback_to_first_run_on_invalid_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """状态文件不兼容时应按首次运行处理。"""

    state_file = tmp_path / "state" / "run_history.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(manifest_ops, "get_latest_versions", lambda **_: _make_latest_versions())

    decision = evaluate_update_need(region="zh_CN", state_file=state_file)

    assert decision.should_update is True
    assert decision.reason == DECISION_REASON_FIRST_RUN


def test_resolve_root_wad_path_should_strip_region_suffix() -> None:
    """区域 WAD 路径应正确映射到根 WAD。"""

    root = manifest_ops._resolve_root_wad_path(
        "DATA/FINAL/Champions/Zac.zh_CN.wad.client",
        region="zh_CN",
    )
    assert root == "DATA/FINAL/Champions/Zac.wad.client"


def test_classify_voice_bank_paths_should_use_suffix_rules() -> None:
    """语音路径分类应仅识别 VO audio/events。"""

    audio_paths, event_paths = manifest_ops._classify_voice_bank_paths(
        [
            "ASSETS/Sounds/Wwise2016/VO/en_US/Characters/Zac/Skins/Base/Zac_Base_VO_audio.bnk",
            "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_audio.wpk",
            "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_events.bnk",
            "assets/sounds/wwise2016/sfx/characters/zac/skins/base/zac_base_sfx_audio.bnk",
        ]
    )
    assert audio_paths == (
        "ASSETS/Sounds/Wwise2016/VO/en_US/Characters/Zac/Skins/Base/Zac_Base_VO_audio.bnk",
        "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_audio.wpk",
    )
    assert event_paths == (
        "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_events.bnk",
    )


def test_build_wad_voice_filter_decision_should_skip_localized() -> None:
    """Localized 路径应被直接跳过。"""

    decision = manifest_ops._build_wad_voice_filter_decision(
        old_extractor=object(),  # type: ignore[arg-type]
        new_extractor=object(),  # type: ignore[arg-type]
        old_file_index={},
        new_file_index={},
        region="zh_CN",
        wad_path="DATA/FINAL/Localized/Global.zh_CN.wad.client",
        max_champion_skin_bin_index=260,
    )
    assert decision.should_unpack is False
    assert decision.skip_reason == "Localized 目录不在处理范围"


def test_filter_wad_changes_by_bin_voice_paths_should_aggregate_unpack_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """二次筛选汇总应按 should_unpack 输出路径集合。"""

    class _FakeManifest:
        def __init__(self, file: str, path: str) -> None:
            self.file = file
            self.path = path
            self.files: dict[str, Any] = {}

    class _FakeExtractor:
        def __init__(self, manifest: _FakeManifest, **_: Any) -> None:
            self.manifest = manifest

        def __enter__(self) -> _FakeExtractor:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any | None,
        ) -> None:
            return None

    def _fake_decision(**kwargs: Any) -> WadVoiceFilterDecision:
        wad_path = str(kwargs["wad_path"])
        if "Annie" in wad_path:
            return WadVoiceFilterDecision(
                region_wad_path=wad_path,
                root_wad_path="DATA/FINAL/Champions/Annie.wad.client",
                entity_type="champion",
                matched_bin_paths=("data/characters/annie/skins/skin0.bin",),
                audio_paths=(
                    "assets/sounds/wwise2016/vo/en_us/characters/annie/skins/base/annie_base_vo_audio.wpk",
                ),
                event_paths=tuple(),
                path_statuses=(
                    VoicePathStatus(
                        path="assets/sounds/wwise2016/vo/en_us/characters/annie/skins/base/annie_base_vo_audio.wpk",
                        status="changed",
                        path_type="audio",
                    ),
                ),
                changed_audio_paths=(
                    "assets/sounds/wwise2016/vo/en_us/characters/annie/skins/base/annie_base_vo_audio.wpk",
                ),
                changed_event_paths=tuple(),
                should_unpack=True,
                skip_reason=None,
            )
        return WadVoiceFilterDecision(
            region_wad_path=wad_path,
            root_wad_path="DATA/FINAL/Champions/Zac.wad.client",
            entity_type="champion",
            matched_bin_paths=("data/characters/zac/skins/skin0.bin",),
            audio_paths=(
                "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_audio.wpk",
            ),
            event_paths=(
                "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_events.bnk",
            ),
            path_statuses=(
                VoicePathStatus(
                    path="assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_audio.wpk",
                    status="unchanged",
                    path_type="audio",
                ),
                VoicePathStatus(
                    path="assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_events.bnk",
                    status="changed",
                    path_type="event",
                ),
            ),
            changed_audio_paths=tuple(),
            changed_event_paths=(
                "assets/sounds/wwise2016/vo/en_us/characters/zac/skins/base/zac_base_vo_events.bnk",
            ),
            should_unpack=False,
            skip_reason="仅 vo_events 变更，按规则跳过资源解包",
        )

    monkeypatch.setattr(manifest_ops, "PatcherManifest", _FakeManifest)
    monkeypatch.setattr(manifest_ops, "WADExtractor", _FakeExtractor)
    monkeypatch.setattr(manifest_ops, "_build_wad_voice_filter_decision", _fake_decision)

    result = filter_wad_changes_by_bin_voice_paths(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
        update_paths=(
            "DATA/FINAL/Champions/Annie.zh_CN.wad.client",
            " DATA/FINAL/Champions/Zac.zh_CN.wad.client ",
            "DATA/FINAL/Champions/Annie.zh_CN.wad.client",
        ),
    )

    assert isinstance(result, ManifestVoiceFilterResult)
    assert result.unpack_paths == ("DATA/FINAL/Champions/Annie.zh_CN.wad.client",)
    assert result.skipped_paths == ("DATA/FINAL/Champions/Zac.zh_CN.wad.client",)
    assert len(result.decisions) == 2


def test_filter_wad_changes_by_bin_voice_paths_should_write_bin_output_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """启用 BIN 输出目录时，应在筛选阶段直接写入本地 BIN 文件。"""

    class _FakeManifest:
        def __init__(self, file: str, path: str) -> None:
            self.file = file
            self.path = path
            self.files: dict[str, Any] = {}

    class _FakeExtractor:
        def __init__(self, manifest: _FakeManifest, **_: Any) -> None:
            self.manifest = manifest

        def __enter__(self) -> _FakeExtractor:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any | None,
        ) -> None:
            return None

    def _fake_decision(**kwargs: Any) -> WadVoiceFilterDecision:
        decision = WadVoiceFilterDecision(
            region_wad_path="DATA/FINAL/Champions/Annie.zh_CN.wad.client",
            root_wad_path="DATA/FINAL/Champions/Annie.wad.client",
            entity_type="champion",
            matched_bin_paths=("data/characters/annie/skins/skin0.bin",),
            audio_paths=tuple(),
            event_paths=tuple(),
            path_statuses=tuple(),
            changed_audio_paths=(
                "assets/sounds/wwise2016/vo/en_us/characters/annie/skins/base/annie_base_vo_audio.wpk",
            ),
            changed_event_paths=tuple(),
            should_unpack=True,
            skip_reason=None,
        )
        callback = kwargs.get("on_bin_payloads")
        if callable(callback):
            callback(
                decision,
                {
                    "data/characters/annie/skins/skin0.bin": b"annie-bin",
                    "data/maps/shipping/map11/map11.bin": b"map-bin",
                },
            )
        return decision

    monkeypatch.setattr(manifest_ops, "PatcherManifest", _FakeManifest)
    monkeypatch.setattr(manifest_ops, "WADExtractor", _FakeExtractor)
    monkeypatch.setattr(manifest_ops, "_build_wad_voice_filter_decision", _fake_decision)

    bin_output_dir = tmp_path / "manifest" / "16.4" / "bin_input"
    result = filter_wad_changes_by_bin_voice_paths(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
        update_paths=("DATA/FINAL/Champions/Annie.zh_CN.wad.client",),
        bin_output_dir=bin_output_dir,
    )

    assert result.unpack_paths == ("DATA/FINAL/Champions/Annie.zh_CN.wad.client",)
    assert (bin_output_dir / "data" / "characters" / "annie" / "skins" / "skin0.bin").read_bytes() == b"annie-bin"
    assert (bin_output_dir / "data" / "maps" / "shipping" / "map11" / "map11.bin").read_bytes() == b"map-bin"


def test_filter_wad_changes_by_bin_voice_paths_should_reject_invalid_unit_workers() -> None:
    """并发数小于 1 时应直接拒绝。"""

    with pytest.raises(ValueError, match="unit_max_workers"):
        filter_wad_changes_by_bin_voice_paths(
            old_manifest_url="https://example.test/old.manifest",
            new_manifest_url="https://example.test/new.manifest",
            region="zh_CN",
            update_paths=("DATA/FINAL/Champions/Annie.zh_CN.wad.client",),
            unit_max_workers=0,
        )


def test_filter_wad_changes_by_bin_voice_paths_should_reject_invalid_extract_concurrency() -> None:
    """WADExtractor 内部下载并发小于 1 时应直接拒绝。"""

    with pytest.raises(ValueError, match="extractor_prefetch_chunk_concurrency"):
        filter_wad_changes_by_bin_voice_paths(
            old_manifest_url="https://example.test/old.manifest",
            new_manifest_url="https://example.test/new.manifest",
            region="zh_CN",
            update_paths=("DATA/FINAL/Champions/Annie.zh_CN.wad.client",),
            extractor_prefetch_chunk_concurrency=0,
        )
