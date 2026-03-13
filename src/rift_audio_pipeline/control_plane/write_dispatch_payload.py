"""把 GitHub Actions event 中的 dispatch payload 落盘为运行时文件。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rift_audio_pipeline.control_plane.workflow_dispatch import redact_raw_dispatch_payload


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数。"""

    parser = argparse.ArgumentParser(description="写出 dispatch payload 与脱敏副本。")
    parser.add_argument("--github-event-path", type=Path, required=True)
    parser.add_argument("--dispatch-inputs-file", type=Path, required=True)
    parser.add_argument("--redacted-output-file", type=Path, required=True)
    parser.add_argument("--ref", required=True)
    return parser


def write_dispatch_payload(
    *,
    github_event_path: Path,
    dispatch_inputs_file: Path,
    redacted_output_file: Path,
    ref: str,
) -> dict[str, object]:
    """从 GitHub event 中提取 payload 并写出原文与脱敏副本。

    Args:
        github_event_path: GitHub Actions 事件 JSON 文件路径。
        dispatch_inputs_file: 原始 payload 输出路径。
        redacted_output_file: 脱敏后的 payload 输出路径。
        ref: 本次 workflow_dispatch 对应的 Git ref 名称。

    Returns:
        dict[str, object]: 适合打印的执行摘要。

    Raises:
        ValueError: 当事件文件顶层、`inputs` 或 `inputs.payload` 结构不合法时抛出。
    """

    event_payload = json.loads(github_event_path.read_text(encoding="utf-8"))
    if not isinstance(event_payload, dict):
        raise ValueError(f"github event 顶层必须是 JSON object：{github_event_path}")
    inputs = event_payload.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError(f"github event 缺少 inputs object：{github_event_path}")
    dispatch_payload_json = inputs.get("payload")
    if not isinstance(dispatch_payload_json, str) or not dispatch_payload_json.strip():
        raise ValueError(f"github event 缺少非空 inputs.payload：{github_event_path}")

    dispatch_inputs_file.parent.mkdir(parents=True, exist_ok=True)
    dispatch_inputs_file.write_text(dispatch_payload_json, encoding="utf-8")
    redacted_output_file.parent.mkdir(parents=True, exist_ok=True)
    redacted_output_file.write_text(
        json.dumps(
            redact_raw_dispatch_payload(
                {
                    "ref": ref,
                    "inputs": {"payload": dispatch_payload_json},
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "ref": ref,
        "github_event_path": str(github_event_path),
        "dispatch_inputs_file": str(dispatch_inputs_file),
        "redacted_output_file": str(redacted_output_file),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""

    args = build_parser().parse_args(argv)
    summary = write_dispatch_payload(
        github_event_path=args.github_event_path,
        dispatch_inputs_file=args.dispatch_inputs_file,
        redacted_output_file=args.redacted_output_file,
        ref=args.ref,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
