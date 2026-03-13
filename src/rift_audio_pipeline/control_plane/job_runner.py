"""GitHub Actions / fake-github 启动总控。"""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import uuid

from rift_audio_pipeline.control_plane.github_actions_workflow import load_dispatch_payload
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.runtime.job_support import JobRunnerResult
from rift_audio_pipeline.control_plane.runtime.job_support import RuntimePlan
from rift_audio_pipeline.control_plane.runtime.job_support import build_pipeline_environment
from rift_audio_pipeline.control_plane.runtime.job_support import (
    build_runtime_plan as build_runtime_plan_impl,
)
from rift_audio_pipeline.control_plane.runtime.job_support import emit_run_result
from rift_audio_pipeline.control_plane.runtime.job_support import prepare_relay
from rift_audio_pipeline.control_plane.runtime.job_support import run_finalize_worker
from rift_audio_pipeline.control_plane.runtime.job_support import run_pipeline_main
from rift_audio_pipeline.control_plane.runtime.job_support import start_upload_workers
from rift_audio_pipeline.control_plane.runtime.job_support import wait_for_upload_workers
from rift_audio_pipeline.control_plane.runtime_init import initialize_runtime
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchPayload
from rift_audio_pipeline.pipeline.models import DEFAULT_ARCHIVE_REMOTE_ROOT
from rift_audio_pipeline.pipeline.models import DEFAULT_META_REMOTE_ROOT

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
    parser.add_argument("--control-plane-base-url", default="")
    parser.add_argument("--control-plane-bearer-token")
    parser.add_argument("--control-plane-access-client-id")
    parser.add_argument("--control-plane-access-client-secret")
    parser.add_argument("--control-plane-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--default-mode", default="remote")
    parser.add_argument("--default-game-region", default="zh_CN")
    parser.add_argument("--default-requested-by", default="github-actions")
    parser.add_argument("--default-log-level", default="INFO")
    parser.add_argument("--archive-remote-root", default=DEFAULT_ARCHIVE_REMOTE_ROOT)
    parser.add_argument("--meta-remote-root", default=DEFAULT_META_REMOTE_ROOT)
    parser.add_argument("--upload-worker-count", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    """按固定顺序调度 runtime worker 主路径。"""

    args = build_parser().parse_args(argv)
    payload = load_dispatch_payload(ref=args.ref, dispatch_inputs_file=args.dispatch_inputs_file)
    plan = build_runtime_plan(args=args, run_id=_resolve_run_id(args.run_id))
    control_plane_config = _build_control_plane_config(args)
    init_result = initialize_runtime(
        run_id=plan.run_id,
        runtime_dir=plan.runtime_root,
        archive_remote_root=plan.archive_remote_root,
        meta_remote_root=plan.meta_remote_root,
        plane_config=control_plane_config,
        provided_baidu_token_payload=_build_baidu_token_payload(payload),
    )
    relay_enabled = control_plane_config is not None
    pipeline_command = build_pipeline_command(
        payload=payload,
        run_id=plan.run_id,
        output_root=plan.output_root,
        temp_root=plan.temp_root,
        log_root=plan.log_root,
        archive_remote_root=plan.archive_remote_root,
        meta_remote_root=plan.meta_remote_root,
        relay_socket_path=plan.relay_socket_path if relay_enabled else None,
        state_db_path=init_result.state_db_file,
        default_mode=plan.default_mode,
        default_game_region=plan.default_game_region,
        default_log_level=plan.default_log_level,
    )
    relay_process, relay_output_handle = prepare_relay(
        plan=plan,
        control_plane_base_url=control_plane_config.base_url if control_plane_config else None,
        control_plane_bearer_token=args.control_plane_bearer_token,
        control_plane_access_client_id=args.control_plane_access_client_id,
        control_plane_access_client_secret=args.control_plane_access_client_secret,
        control_plane_timeout_seconds=args.control_plane_timeout_seconds,
    )
    upload_processes, upload_output_handles = start_upload_workers(
        plan=plan,
        init_result=init_result,
        worker_count=args.upload_worker_count,
    )
    result = JobRunnerResult(
        run_id=plan.run_id,
        runtime_dir=plan.runtime_root,
        pipeline_command=tuple(pipeline_command),
        pipeline_returncode=1,
        relay_returncode=1,
        upload_returncode=1,
        finalize_returncode=1,
        database_file=init_result.database_file,
        state_db_file=init_result.state_db_file,
        imported_remote_entries=init_result.imported_remote_entries,
        baidu_token_file=init_result.baidu_token_file,
        relay_socket_path=plan.relay_socket_path,
    )
    try:
        pipeline_returncode = run_pipeline_main(
            pipeline_command=pipeline_command,
            pipeline_env=build_pipeline_environment(init_result=init_result),
        )
        upload_returncode = wait_for_upload_workers(
            state_db_path=init_result.state_db_file,
            run_id=plan.run_id,
            upload_processes=upload_processes,
        )
        finalize_returncode = run_finalize_worker(
            plan=plan,
            init_result=init_result,
            final_status="success" if pipeline_returncode == 0 else "failed",
            relay_enabled=relay_enabled,
        )
        relay_returncode = relay_process.wait(timeout=30.0) if relay_process is not None else 0
        result = JobRunnerResult(
            run_id=result.run_id,
            runtime_dir=result.runtime_dir,
            pipeline_command=result.pipeline_command,
            pipeline_returncode=pipeline_returncode,
            relay_returncode=relay_returncode,
            upload_returncode=upload_returncode,
            finalize_returncode=finalize_returncode,
            database_file=result.database_file,
            state_db_file=result.state_db_file,
            imported_remote_entries=result.imported_remote_entries,
            baidu_token_file=result.baidu_token_file,
            relay_socket_path=result.relay_socket_path,
        )
    finally:
        for process in upload_processes:
            if process.poll() is None:
                process.terminate()
        if relay_process is not None and relay_process.poll() is None:
            relay_process.terminate()
        if relay_process is not None:
            try:
                relay_process.wait(timeout=5.0)
            except Exception:  # noqa: BLE001
                pass
        for process in upload_processes:
            try:
                process.wait(timeout=5.0)
            except Exception:  # noqa: BLE001
                pass
        if relay_output_handle is not None:
            relay_output_handle.close()
        for handle in upload_output_handles:
            handle.close()
        init_result.baidu_token_file.unlink(missing_ok=True)
    emit_run_result(result)
    return result.pipeline_returncode


def build_runtime_plan(*, args: argparse.Namespace, run_id: str) -> RuntimePlan:
    """兼容导出：基于 CLI 参数组装本地 runtime 布局。"""

    return build_runtime_plan_impl(
        args=args,
        run_id=run_id,
        resolve_runtime_root=_resolve_runtime_root,
        resolve_log_dir=_resolve_log_dir,
    )


def _build_control_plane_config(args: argparse.Namespace) -> ControlPlaneConfig | None:
    """根据 CLI 参数构造可选 plane 配置。"""

    normalized_base_url = args.control_plane_base_url.strip()
    if not normalized_base_url:
        return None
    return ControlPlaneConfig(
        base_url=normalized_base_url,
        bearer_token=args.control_plane_bearer_token,
        access_client_id=args.control_plane_access_client_id,
        access_client_secret=args.control_plane_access_client_secret,
        timeout_seconds=args.control_plane_timeout_seconds,
    )


def _build_baidu_token_payload(payload: DispatchPayload) -> dict[str, object] | None:
    """从 dispatch payload 中提取可选的百度凭据覆盖值。"""

    baidu_inputs = payload.inputs.baidu
    token_payload = {
        "access_token": baidu_inputs.access_token,
    }
    return {key: value for key, value in token_payload.items() if value is not None} or None


def build_pipeline_command(
    *,
    payload: DispatchPayload,
    run_id: str,
    output_root: Path,
    temp_root: Path,
    log_root: Path,
    archive_remote_root: str,
    meta_remote_root: str,
    relay_socket_path: Path | None,
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
        "--state-db-path",
        str(state_db_path),
        "--archive-remote-root",
        archive_remote_root,
        "--meta-remote-root",
        meta_remote_root,
        "--log-level",
        inputs.execution.log_level or default_log_level,
    ]
    if relay_socket_path is not None:
        command.extend(["--relay-socket-path", str(relay_socket_path)])
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
    if inputs.execution.archive_password:
        command.extend(["--archive-password", inputs.execution.archive_password])
    if inputs.execution.force_update is not None:
        command.append("--force-update" if inputs.execution.force_update else "--no-force-update")
    if inputs.targets.champions.ids:
        command.extend(
            ["--champion-ids", ",".join(str(item) for item in inputs.targets.champions.ids)]
        )
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
