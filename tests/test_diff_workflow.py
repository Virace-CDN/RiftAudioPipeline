"""diff workflow 最小能力测试。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rift_audio_pipeline.workflows.diff_workflow import collect_diff_report
from rift_audio_pipeline.workflows.diff_workflow import format_path_hash_hex
import rift_audio_pipeline.workflows.diff_workflow as diff_workflow


@dataclass(frozen=True, slots=True)
class _FakeSectionDiff:
    """模拟 section diff 条目。"""

    path_hash: int
    status: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class _FakeWadFileDiff:
    """模拟 WAD diff 条目。"""

    wad_path: str
    status: str
    section_diffs: tuple[_FakeSectionDiff, ...]
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class _FakeResolvedReport:
    """模拟回填后的 WAD 报告。"""

    files: tuple[_FakeWadFileDiff, ...]


@dataclass(frozen=True, slots=True)
class _FakeManifestEntry:
    """模拟 manifest diff 条目。"""

    path: str


@dataclass(frozen=True, slots=True)
class _FakeManifestReport:
    """模拟 manifest diff 报告。"""

    added: tuple[_FakeManifestEntry, ...]
    changed: tuple[_FakeManifestEntry, ...]
    removed: tuple[_FakeManifestEntry, ...]


def test_collect_diff_report_should_use_real_path_or_fallback_path_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """路径回填后应优先 real_path，缺失时回退 path_hash。"""

    fake_manifest_report = _FakeManifestReport(
        added=tuple(),
        changed=(_FakeManifestEntry("DATA/FINAL/Champions/Ahri.zh_CN.wad.client"),),
        removed=tuple(),
    )
    fake_wad_report = object()
    fake_resolved_report = _FakeResolvedReport(
        files=(
            _FakeWadFileDiff(
                wad_path="DATA/FINAL/Champions/Ahri.zh_CN.wad.client",
                status="changed",
                section_diffs=(
                    _FakeSectionDiff(
                        path_hash=0xA1,
                        status="changed",
                        path="assets/sounds/vo/ahri/skin0_vo_audio.bnk",
                    ),
                    _FakeSectionDiff(
                        path_hash=0xB2,
                        status="added",
                        path=None,
                    ),
                ),
            ),
        )
    )

    def _fake_run_diff_manifests(*, old_manifest_url: str, new_manifest_url: str, region: str) -> Any:
        assert old_manifest_url == "https://example.test/old.manifest"
        assert new_manifest_url == "https://example.test/new.manifest"
        assert region == "zh_CN"
        return fake_manifest_report

    def _fake_run_diff_wad_headers(*, manifest_report: Any, target_wad_files: Any) -> Any:
        assert manifest_report is fake_manifest_report
        assert target_wad_files == ("DATA/FINAL/Champions/Ahri.zh_CN.wad.client",)
        return fake_wad_report

    def _fake_run_resolve_wad_diff_paths(
        *,
        wad_report: Any,
        include_section_statuses: set[str],
        max_skin_id: int,
        bin_data_source_mode: str,
    ) -> Any:
        assert wad_report is fake_wad_report
        assert include_section_statuses == {"added", "removed", "changed"}
        assert max_skin_id == 100
        assert bin_data_source_mode == "extractor"
        return fake_resolved_report

    monkeypatch.setattr(diff_workflow, "_run_diff_manifests", _fake_run_diff_manifests)
    monkeypatch.setattr(diff_workflow, "_run_diff_wad_headers", _fake_run_diff_wad_headers)
    monkeypatch.setattr(
        diff_workflow,
        "_run_resolve_wad_diff_paths",
        _fake_run_resolve_wad_diff_paths,
    )

    report = collect_diff_report(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
        from_game_version="16.5",
        to_game_version="16.6",
    )

    assert report.schema_version == 1
    assert report.from_game_version == "16.5"
    assert report.to_game_version == "16.6"
    assert report.has_changes is True
    assert report.stats.total_wad_count == 1
    assert report.stats.update_wad_count == 1
    assert report.stats.changed_section_count == 2
    assert report.stats.resolved_section_count == 1
    assert report.stats.unresolved_section_count == 1

    wad = report.wads[0]
    assert wad.wad_path == "DATA/FINAL/Champions/Ahri.zh_CN.wad.client"
    assert wad.status == "changed"
    assert wad.changed_count == 2

    first_change = wad.changes[0]
    assert first_change.real_path == "assets/sounds/vo/ahri/skin0_vo_audio.bnk"
    assert first_change.path == "assets/sounds/vo/ahri/skin0_vo_audio.bnk"
    assert first_change.path_hash == "0x00000000000000a1"

    second_change = wad.changes[1]
    assert second_change.real_path is None
    assert second_change.path == "0x00000000000000b2"
    assert second_change.path_hash == "0x00000000000000b2"


def test_collect_diff_report_should_filter_wad_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """应支持按 WAD 状态过滤输出。"""

    fake_resolved_report = _FakeResolvedReport(
        files=(
            _FakeWadFileDiff(
                wad_path="DATA/FINAL/Champions/Ahri.zh_CN.wad.client",
                status="changed",
                section_diffs=tuple(),
            ),
            _FakeWadFileDiff(
                wad_path="DATA/FINAL/Champions/Ahri.wad.client",
                status="unchanged",
                section_diffs=tuple(),
            ),
        )
    )

    monkeypatch.setattr(
        diff_workflow,
        "_run_diff_manifests",
        lambda **_: _FakeManifestReport(
            added=tuple(),
            changed=(_FakeManifestEntry("DATA/FINAL/Champions/Ahri.zh_CN.wad.client"),),
            removed=tuple(),
        ),
    )
    monkeypatch.setattr(diff_workflow, "_run_diff_wad_headers", lambda **_: object())
    monkeypatch.setattr(diff_workflow, "_run_resolve_wad_diff_paths", lambda **_: fake_resolved_report)

    report = collect_diff_report(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
        include_wad_statuses=("changed",),
    )

    assert len(report.wads) == 1
    assert report.wads[0].status == "changed"


def test_format_path_hash_hex_should_use_fixed_hex_width() -> None:
    """path_hash 应输出固定宽度十六进制。"""

    assert format_path_hash_hex(1) == "0x0000000000000001"


def test_collect_diff_report_should_return_empty_when_no_target_wads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无目标 WAD 时应直接返回空报告，不调用 WAD 头部比对。"""

    monkeypatch.setattr(
        diff_workflow,
        "_run_diff_manifests",
        lambda **_: _FakeManifestReport(added=tuple(), changed=tuple(), removed=tuple()),
    )

    def _raise_if_called(**_: Any) -> Any:
        raise AssertionError("不应调用 _run_diff_wad_headers")

    monkeypatch.setattr(diff_workflow, "_run_diff_wad_headers", _raise_if_called)

    report = collect_diff_report(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
    )

    assert report.has_changes is False
    assert report.wads == tuple()
    assert report.stats.total_wad_count == 0
