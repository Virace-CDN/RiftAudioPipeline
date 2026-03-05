"""独立 diff_collect 命令行入口。"""

from __future__ import annotations

import argparse
from argparse import Namespace
from pathlib import Path
from typing import Sequence

from rift_audio_pipeline.workflows.diff_workflow import collect_diff_report

DEFAULT_DIFF_OUTPUT_PATH = Path("output") / "diff_report.json"
DEFAULT_WAD_STATUSES: tuple[str, ...] = ("added", "removed", "changed", "error")
DEFAULT_SECTION_STATUSES: tuple[str, ...] = ("added", "removed", "changed")


def build_parser() -> argparse.ArgumentParser:
    """构建 diff_collect 命令行解析器。

    Returns:
        配置完成的参数解析器。
    """

    parser = argparse.ArgumentParser(description="独立执行 manifest/wad diff 并输出 diff_report.json")
    parser.add_argument("--old-manifest-url", required=True, help="旧版 manifest URL")
    parser.add_argument("--new-manifest-url", required=True, help="新版 manifest URL")
    parser.add_argument("--region", default="zh_CN", help="语言区域，例如 zh_CN")
    parser.add_argument("--from-game-version", default=None, help="可选旧版本号")
    parser.add_argument("--to-game-version", default=None, help="可选新版本号")
    parser.add_argument(
        "--target-wad-files",
        nargs="+",
        default=None,
        help="可选，仅分析指定 WAD 路径集合",
    )
    parser.add_argument(
        "--include-wad-statuses",
        nargs="+",
        default=list(DEFAULT_WAD_STATUSES),
        choices=["added", "removed", "changed", "unchanged", "error"],
        help="纳入报告的 WAD 状态",
    )
    parser.add_argument(
        "--include-section-statuses",
        nargs="+",
        default=list(DEFAULT_SECTION_STATUSES),
        choices=["added", "removed", "changed", "unchanged"],
        help="纳入报告的 section 状态",
    )
    parser.add_argument("--max-skin-id", type=int, default=100, help="BIN 路径扫描皮肤上限")
    parser.add_argument(
        "--bin-data-source-mode",
        default="extractor",
        choices=["extractor", "download_root_wad"],
        help="BIN 数据来源模式",
    )
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_DIFF_OUTPUT_PATH),
        help="输出 JSON 文件路径，默认 output/diff_report.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行 diff_collect 命令。

    Args:
        argv: 可选参数列表；不传时读取命令行实参。

    Returns:
        退出状态码，`0` 表示执行成功。
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    return run_from_namespace(args)


def run_from_namespace(args: Namespace) -> int:
    """从解析后的参数对象执行 diff_collect。

    Args:
        args: 命令行参数命名空间。

    Returns:
        退出状态码，`0` 表示执行成功。
    """

    target_wad_files = _normalize_optional_paths(args.target_wad_files)
    report = collect_diff_report(
        old_manifest_url=args.old_manifest_url,
        new_manifest_url=args.new_manifest_url,
        region=args.region,
        from_game_version=args.from_game_version,
        to_game_version=args.to_game_version,
        target_wad_files=target_wad_files,
        include_wad_statuses=tuple(args.include_wad_statuses),
        include_section_statuses=tuple(args.include_section_statuses),
        max_skin_id=int(args.max_skin_id),
        bin_data_source_mode=args.bin_data_source_mode,
    )
    output_path = report.dump_pretty_json(args.output_path)
    print(f"diff_report 已输出: {output_path}")
    print(
        "summary: "
        f"has_changes={report.has_changes}, "
        f"update_wad_count={report.stats.update_wad_count}, "
        f"changed_section_count={report.stats.changed_section_count}"
    )
    return 0


def _normalize_optional_paths(raw_values: Sequence[str] | None) -> tuple[str, ...] | None:
    """规范化可选路径列表。

    Args:
        raw_values: 原始路径序列。

    Returns:
        非空时返回去空白后的元组；否则返回 `None`。
    """

    if raw_values is None:
        return None
    normalized = tuple(item.strip() for item in raw_values if isinstance(item, str) and item.strip())
    return normalized or None
