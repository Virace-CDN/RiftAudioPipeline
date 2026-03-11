"""GitHub Actions workflow 入口。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from rift_audio_pipeline.control_plane.faker_github import DispatchPayload
from rift_audio_pipeline.control_plane.faker_github import FakerGitHubConfig
from rift_audio_pipeline.control_plane.faker_github import _serialize_dispatch_inputs
from rift_audio_pipeline.control_plane.faker_github import build_pipeline_command
from rift_audio_pipeline.control_plane.faker_github import parse_dispatch_payload


def build_parser() -> argparse.ArgumentParser:
    """构造 GitHub Actions workflow 入口参数。"""

    parser = argparse.ArgumentParser(
        description="在 GitHub Actions 中解析结构化 dispatch inputs 并执行 pipeline。"
    )
    parser.add_argument("--ref", required=True, help="workflow_dispatch 使用的 Git ref。")
    parser.add_argument(
        "--dispatch-inputs-file",
        type=Path,
        required=True,
        help="结构化 dispatch inputs JSON 文件路径。",
    )
    parser.add_argument("--storage-root", type=Path, default=Path("temp/github_actions_dispatch"))
    parser.add_argument("--control-plane-base-url", default="")
    parser.add_argument("--control-plane-bearer-token")
    parser.add_argument("--control-plane-access-client-id")
    parser.add_argument("--control-plane-access-client-secret")
    parser.add_argument("--default-mode", default="remote")
    parser.add_argument("--default-game-region", default="zh_CN")
    parser.add_argument("--default-requested-by", default="github-actions")
    parser.add_argument("--output-root", type=Path, default=Path("output"))
    parser.add_argument("--temp-root", type=Path, default=Path("temp"))
    parser.add_argument("--log-root", type=Path)
    parser.add_argument("--baidu-remote-root", default="/apps/rift-audio-pipeline")
    parser.add_argument("--default-log-level", default="INFO")
    parser.add_argument("--control-plane-timeout-seconds", type=float, default=30.0)
    return parser


def load_dispatch_payload(*, ref: str, dispatch_inputs_file: Path) -> DispatchPayload:
    """从 JSON 文件加载结构化 dispatch payload。"""

    raw_payload = dispatch_inputs_file.read_text(encoding="utf-8")
    return parse_dispatch_payload({"ref": ref, "inputs": {"payload": raw_payload}})


def build_workflow_command(args: argparse.Namespace) -> tuple[DispatchPayload, list[str]]:
    """基于 workflow 参数构造 pipeline 命令。"""

    payload = load_dispatch_payload(ref=args.ref, dispatch_inputs_file=args.dispatch_inputs_file)
    config = FakerGitHubConfig(
        storage_root=args.storage_root,
        github_token="github-actions",
        github_token_source="workflow",
        control_plane_base_url=args.control_plane_base_url,
        control_plane_bearer_token=args.control_plane_bearer_token,
        control_plane_access_client_id=args.control_plane_access_client_id,
        control_plane_access_client_secret=args.control_plane_access_client_secret,
        default_mode=args.default_mode,
        default_game_region=args.default_game_region,
        default_requested_by=args.default_requested_by,
        output_root=args.output_root,
        temp_root=args.temp_root,
        log_root=args.log_root,
        baidu_remote_root=args.baidu_remote_root,
        default_log_level=args.default_log_level,
        control_plane_timeout_seconds=args.control_plane_timeout_seconds,
        working_directory=Path.cwd(),
        python_executable=Path(sys.executable),
    )
    return payload, build_pipeline_command(config=config, payload=payload)


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    args = build_parser().parse_args(argv)
    payload, command = build_workflow_command(args)
    print(
        json.dumps(
            {
                "ref": payload.ref,
                "inputs": _serialize_dispatch_inputs(payload.inputs),
                "command": command,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    completed = subprocess.run(command, check=False)  # noqa: S603
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
