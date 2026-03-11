"""GitHub Actions / fake-github 启动总控。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from rift_audio_pipeline.control_plane.faker_github import DispatchPayload
from rift_audio_pipeline.control_plane.github_actions_workflow import load_dispatch_payload
from rift_audio_pipeline.control_plane.runtime_init import initialize_runtime
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.pipeline.logging import _LOG_RELAY_SOCKET_ROOT
from rift_audio_pipeline.pipeline.logging import LogSinkConfig
from rift_audio_pipeline.pipeline.logging import spawn_log_relay_process
from rift_audio_pipeline.pipeline.logging import write_log_relay_config

_REQUEST_STAGE_TO_FLAGS = {
    None: (True, True, False),
    "update": (True, False, False),
    "extract": (True, True, False),
    "mapping": (True, True, True),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按 dispatch payload 启动完整运行时链路。")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--dispatch-inputs-file", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=Path("output"))
    parser.add_argument("--temp-root", type=Path, default=Path("temp"))
    parser.add_argument("--log-root", type=Path, default=None)
    parser.add_argument("--run-id")
    parser.add_argument("--control-plane-base-url", required=True)
    parser.add_argument("--control-plane-bearer-token")
    parser.add_argument("--control-plane-access-client-id")
    parser.add_argument("--control-plane-access-client-secret")
    parser.add_argument("--control-plane-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--default-mode", default="remote")
    parser.add_argument("--default-game-region", default="zh_CN")
    parser.add_argument("--default-requested-by", default="github-actions")
    parser.add_argument("--default-log-level", default="INFO")
    parser.add_argument("--baidu-remote-root", default="/apps/rift-audio-pipeline")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = load_dispatch_payload(ref=args.ref, dispatch_inputs_file=args.dispatch_inputs_file)
    run_id = _resolve_run_id(args.run_id)
    runtime_root = _resolve_runtime_root(storage_root=args.storage_root, output_root=args.output_root, run_id=run_id)
    init_result = initialize_runtime(
        run_id=run_id,
        runtime_dir=runtime_root,
        baidu_remote_root=args.baidu_remote_root,
        plane_config=ControlPlaneConfig(
            base_url=args.control_plane_base_url,
            bearer_token=args.control_plane_bearer_token,
            access_client_id=args.control_plane_access_client_id,
            access_client_secret=args.control_plane_access_client_secret,
            timeout_seconds=args.control_plane_timeout_seconds,
        ),
    )
    log_root = args.log_root or args.output_root / "logs"
    log_dir = _resolve_log_dir(log_root=log_root, run_id=run_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    relay_socket_path = _LOG_RELAY_SOCKET_ROOT / f"{run_id}.sock"
    relay_config_file = runtime_root / "relay-config.json"
    relay_stdout_file = runtime_root / "relay.stdout.log"
    write_log_relay_config(
        relay_config_file=relay_config_file,
        run_id=run_id,
        relay_state_file=log_dir / "log_relay_state.json",
        relay_socket_file=relay_socket_path,
        config=LogSinkConfig(
            enabled=True,
            control_plane_base_url=args.control_plane_base_url,
            bearer_token=args.control_plane_bearer_token,
            access_client_id=args.control_plane_access_client_id,
            access_client_secret=args.control_plane_access_client_secret,
            timeout_seconds=args.control_plane_timeout_seconds,
            spool_dir=log_dir / "spool",
        ),
    )
    relay_process, relay_stdout_handle = spawn_log_relay_process(
        relay_config_file=relay_config_file,
        relay_stdout_file=relay_stdout_file,
    )
    upload_stdout_file = runtime_root / "upload-worker.stdout.log"
    upload_stdout_handle = upload_stdout_file.open("a", encoding="utf-8")
    upload_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "rift_audio_pipeline.control_plane.upload_worker",
            "--run-id",
            run_id,
            "--state-db-path",
            str(init_result.state_db_file),
            "--baidu-token-file",
            str(init_result.baidu_token_file),
            "--baidu-remote-root",
            args.baidu_remote_root,
            "--output-root",
            str(args.output_root),
        ],
        stdout=upload_stdout_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    pipeline_returncode = 1
    relay_returncode = 1
    upload_returncode = 1
    finalize_returncode = 1
    try:
        pipeline_env = dict(os.environ)
        pipeline_env["RIFT_BAIDU_APP_KEY"] = str(init_result.token_payload["app_key"])
        pipeline_env["RIFT_BAIDU_SECRET_KEY"] = str(init_result.token_payload["secret_key"])
        pipeline_env["RIFT_BAIDU_REFRESH_TOKEN"] = str(init_result.token_payload["refresh_token"])
        pipeline_env["RIFT_BAIDU_DATABASE_FILE"] = str(init_result.database_file)
        pipeline_command = build_pipeline_command(
            payload=payload,
            run_id=run_id,
            output_root=args.output_root,
            temp_root=args.temp_root,
            log_root=log_root,
            baidu_remote_root=args.baidu_remote_root,
            relay_socket_path=relay_socket_path,
            state_db_path=init_result.state_db_file,
            default_mode=args.default_mode,
            default_game_region=args.default_game_region,
            default_log_level=args.default_log_level,
        )
        pipeline_process = subprocess.Popen(  # noqa: S603
            pipeline_command,
            env=pipeline_env,
            text=True,
        )
        pipeline_returncode = pipeline_process.wait()
        upload_returncode = upload_process.wait(timeout=60.0)
        finalize_completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "rift_audio_pipeline.control_plane.finalize_worker",
                "--run-id",
                run_id,
                "--state-db-path",
                str(init_result.state_db_file),
                "--baidu-token-file",
                str(init_result.baidu_token_file),
                "--baidu-remote-root",
                args.baidu_remote_root,
                "--database-file",
                str(init_result.database_file),
                "--log-root",
                str(log_root),
                "--relay-state-file",
                str(log_dir / "log_relay_state.json"),
                "--relay-socket-path",
                str(relay_socket_path),
                "--final-status",
                "success" if pipeline_returncode == 0 else "failed",
            ],
            check=False,
            text=True,
        )
        finalize_returncode = finalize_completed.returncode
        relay_returncode = relay_process.wait(timeout=30.0)
    finally:
        relay_stdout_handle.close()
        upload_stdout_handle.close()
    print(
        json.dumps(
            {
                "run_id": run_id,
                "runtime_dir": str(runtime_root),
                "pipeline_command": pipeline_command,
                "pipeline_returncode": pipeline_returncode,
                "relay_returncode": relay_returncode,
                "upload_returncode": upload_returncode,
                "finalize_returncode": finalize_returncode,
                "database_file": str(init_result.database_file),
                "state_db_file": str(init_result.state_db_file),
                "imported_remote_entries": init_result.imported_remote_entries,
                "baidu_token_file": str(init_result.baidu_token_file),
                "relay_socket_path": str(relay_socket_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return pipeline_returncode


def build_pipeline_command(
    *,
    payload: DispatchPayload,
    run_id: str,
    output_root: Path,
    temp_root: Path,
    log_root: Path,
    baidu_remote_root: str,
    relay_socket_path: Path,
    state_db_path: Path,
    default_mode: str,
    default_game_region: str,
    default_log_level: str,
) -> list[str]:
    inputs = payload.inputs
    mode = inputs.request.mode or default_mode
    game_region = inputs.game.region or default_game_region
    command = [
        sys.executable,
        "-m",
        "rift_audio_pipeline.pipeline.cli",
        "--mode",
        mode,
        "--game-region",
        game_region,
        "--output-root",
        str(output_root),
        "--temp-root",
        str(temp_root),
        "--log-root",
        str(log_root),
        "--run-id",
        run_id,
        "--relay-socket-path",
        str(relay_socket_path),
        "--state-db-path",
        str(state_db_path),
        "--baidu-remote-root",
        baidu_remote_root,
        "--log-level",
        inputs.execution.log_level or default_log_level,
    ]
    _append_stage_flags(command, stage=inputs.request.stage)
    for value, flag in (
        (inputs.manifests.current.version, "--current-version"),
        (inputs.manifests.current.lcu_url, "--current-lcu-manifest-url"),
        (inputs.manifests.current.game_url, "--current-game-manifest-url"),
        (inputs.manifests.previous.version, "--previous-version"),
        (inputs.manifests.previous.lcu_url, "--previous-lcu-manifest-url"),
        (inputs.manifests.previous.game_url, "--previous-game-manifest-url"),
    ):
        if value:
            command.extend([flag, value])
    for value, flag in (
        (inputs.execution.max_workers, "--max-workers"),
        (inputs.execution.download_retry_attempts, "--download-retry-attempts"),
        (inputs.execution.entity_retry_attempts, "--entity-retry-attempts"),
    ):
        if value is not None:
            command.extend([flag, str(value)])
    if inputs.execution.force_update is not None:
        command.append("--force-update" if inputs.execution.force_update else "--no-force-update")
    if inputs.targets.champions.ids:
        command.extend(["--champion-ids", ",".join(str(item) for item in inputs.targets.champions.ids)])
    if inputs.targets.maps.ids:
        command.extend(["--map-ids", ",".join(str(item) for item in inputs.targets.maps.ids)])
    return command


def _append_stage_flags(command: list[str], *, stage: str | None) -> None:
    if stage not in _REQUEST_STAGE_TO_FLAGS:
        supported = ", ".join(sorted(key for key in _REQUEST_STAGE_TO_FLAGS if key is not None))
        raise ValueError(f"stage 仅支持: {supported}。")
    run_update, run_extract, run_mapping = _REQUEST_STAGE_TO_FLAGS[stage]
    command.append("--run-update" if run_update else "--no-run-update")
    command.append("--run-extract" if run_extract else "--no-run-extract")
    command.append("--run-mapping" if run_mapping else "--no-run-mapping")


def _resolve_run_id(override: str | None) -> str:
    if override:
        return override
    github_run_id = os.getenv("GITHUB_RUN_ID")
    if github_run_id:
        return github_run_id
    return f"local-{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _resolve_runtime_root(*, storage_root: Path | None, output_root: Path, run_id: str) -> Path:
    if storage_root is not None:
        return storage_root / "runs" / run_id
    return output_root / "runtime" / run_id


def _resolve_log_dir(*, log_root: Path, run_id: str) -> Path:
    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    return log_root / run_date / run_id
if __name__ == "__main__":
    raise SystemExit(main())
