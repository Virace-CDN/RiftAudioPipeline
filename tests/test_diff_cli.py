"""diff CLI 入口测试。"""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from typing import Any

import pytest

from rift_audio_pipeline.workflows.diff_cli import build_parser
from rift_audio_pipeline.workflows.diff_cli import main
from rift_audio_pipeline.workflows.diff_cli import run_from_namespace
import rift_audio_pipeline.workflows.diff_cli as diff_cli


@dataclass(frozen=True, slots=True)
class _FakeStats:
    """模拟报告统计对象。"""

    update_wad_count: int
    changed_section_count: int


@dataclass(frozen=True, slots=True)
class _FakeReport:
    """模拟 diff 报告对象。"""

    has_changes: bool
    stats: _FakeStats

    def dump_pretty_json(self, output_path: str) -> str:
        """模拟报告写入行为。"""

        return output_path


def test_build_parser_should_use_expected_defaults() -> None:
    """应正确解析默认参数。"""

    parser = build_parser()
    args = parser.parse_args(
        [
            "--old-manifest-url",
            "https://example.test/old.manifest",
            "--new-manifest-url",
            "https://example.test/new.manifest",
        ]
    )

    assert args.region == "zh_CN"
    assert args.max_skin_id == 100
    assert args.bin_data_source_mode == "extractor"
    assert args.output_path == "output/diff_report.json"


def test_run_from_namespace_should_call_collect_diff_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """命令执行应调用 workflow 并输出摘要。"""

    captured_kwargs: dict[str, Any] = {}

    def _fake_collect_diff_report(**kwargs: Any) -> _FakeReport:
        captured_kwargs.update(kwargs)
        return _FakeReport(
            has_changes=True,
            stats=_FakeStats(update_wad_count=2, changed_section_count=5),
        )

    monkeypatch.setattr(diff_cli, "collect_diff_report", _fake_collect_diff_report)

    args = Namespace(
        old_manifest_url="https://example.test/old.manifest",
        new_manifest_url="https://example.test/new.manifest",
        region="zh_CN",
        from_game_version="16.5",
        to_game_version="16.6",
        target_wad_files=["A.wad.client", " ", "B.wad.client"],
        include_wad_statuses=["changed", "added"],
        include_section_statuses=["changed", "added"],
        max_skin_id=120,
        bin_data_source_mode="extractor",
        output_path="output/custom_diff_report.json",
    )
    exit_code = run_from_namespace(args)

    assert exit_code == 0
    assert captured_kwargs["target_wad_files"] == ("A.wad.client", "B.wad.client")
    assert captured_kwargs["include_wad_statuses"] == ("changed", "added")
    assert captured_kwargs["include_section_statuses"] == ("changed", "added")
    assert captured_kwargs["max_skin_id"] == 120

    stdout = capsys.readouterr().out
    assert "diff_report 已输出: output/custom_diff_report.json" in stdout
    assert "has_changes=True" in stdout


def test_main_should_parse_argv_and_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主入口应支持直接传入 argv。"""

    monkeypatch.setattr(diff_cli, "collect_diff_report", lambda **_: _FakeReport(False, _FakeStats(0, 0)))
    exit_code = main(
        [
            "--old-manifest-url",
            "https://example.test/old.manifest",
            "--new-manifest-url",
            "https://example.test/new.manifest",
            "--output-path",
            "output/diff_report.json",
        ]
    )

    assert exit_code == 0
