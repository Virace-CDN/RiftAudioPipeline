"""job runner 编排辅助函数。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable
from typing import TextIO

from rift_audio_pipeline.control_plane.runtime.relay_runtime import spawn_log_relay_process
from rift_audio_pipeline.control_plane.runtime.relay_runtime import write_log_relay_config
from rift_audio_pipeline.control_plane.runtime_init import RuntimeInitializationResult
from rift_audio_pipeline.pipeline.logging import _LOG_RELAY_SOCKET_ROOT
from rift_audio_pipeline.pipeline.logging import LogSinkConfig


@dataclass(frozen=True, slots=True)
class RuntimePlan:
    """描述单次 runtime worker 运行的本地布局。"""

    run_id: str
    runtime_root: Path
    output_root: Path
    temp_root: Path
    log_root: Path
    log_dir: Path
    relay_socket_path: Path
    relay_config_file: Path
    relay_state_file: Path
    relay_stdout_file: Path
    upload_stdout_file: Path
    baidu_remote_root: str
    default_mode: str
    default_game_region: str
    default_log_level: str


@dataclass(frozen=True, slots=True)
class JobRunnerResult:
    """归档 job runner 的最终执行结果。"""

    run_id: str
    runtime_dir: Path
    pipeline_command: tuple[str, ...]
    pipeline_returncode: int
    relay_returncode: int
    upload_returncode: int
    finalize_returncode: int
    database_file: Path
    state_db_file: Path
    imported_remote_entries: int
    baidu_token_file: Path
    relay_socket_path: Path

    def to_payload(self) -> dict[str, object]:
        """把结果序列化为可打印 JSON。"""

        return {
            "run_id": self.run_id,
            "runtime_dir": str(self.runtime_dir),
            "pipeline_command": list(self.pipeline_command),
            "pipeline_returncode": self.pipeline_returncode,
            "relay_returncode": self.relay_returncode,
            "upload_returncode": self.upload_returncode,
            "finalize_returncode": self.finalize_returncode,
            "database_file": str(self.database_file),
            "state_db_file": str(self.state_db_file),
            "imported_remote_entries": self.imported_remote_entries,
            "baidu_token_file": str(self.baidu_token_file),
            "relay_socket_path": str(self.relay_socket_path),
        }


def build_runtime_plan(
    *,
    args: argparse.Namespace,
    run_id: str,
    resolve_runtime_root: Callable[..., Path],
    resolve_log_dir: Callable[..., Path],
) -> RuntimePlan:
    """基于 CLI 参数组装本地 runtime 布局。"""

    runtime_root = resolve_runtime_root(
        storage_root=args.storage_root,
        output_root=args.output_root,
        run_id=run_id,
    )
    log_root = args.log_root or args.output_root / "logs"
    log_dir = resolve_log_dir(log_root=log_root, run_id=run_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    return RuntimePlan(
        run_id=run_id,
        runtime_root=runtime_root,
        output_root=args.output_root,
        temp_root=args.temp_root,
        log_root=log_root,
        log_dir=log_dir,
        relay_socket_path=_LOG_RELAY_SOCKET_ROOT / f"{run_id}.sock",
        relay_config_file=runtime_root / "relay-config.json",
        relay_state_file=log_dir / "log_relay_state.json",
        relay_stdout_file=runtime_root / "relay.stdout.log",
        upload_stdout_file=runtime_root / "upload-worker.stdout.log",
        baidu_remote_root=args.baidu_remote_root,
        default_mode=args.default_mode,
        default_game_region=args.default_game_region,
        default_log_level=args.default_log_level,
    )


def prepare_relay(
    *,
    plan: RuntimePlan,
    control_plane_base_url: str,
    control_plane_bearer_token: str | None,
    control_plane_access_client_id: str | None,
    control_plane_access_client_secret: str | None,
    control_plane_timeout_seconds: float,
) -> tuple[subprocess.Popen[str], TextIO]:
    """写入 relay 配置并启动独立 relay 进程。"""

    write_log_relay_config(
        relay_config_file=plan.relay_config_file,
        run_id=plan.run_id,
        relay_state_file=plan.relay_state_file,
        relay_socket_file=plan.relay_socket_path,
        config=LogSinkConfig(
            enabled=True,
            control_plane_base_url=control_plane_base_url,
            bearer_token=control_plane_bearer_token,
            access_client_id=control_plane_access_client_id,
            access_client_secret=control_plane_access_client_secret,
            timeout_seconds=control_plane_timeout_seconds,
            spool_dir=plan.log_dir / "spool",
        ),
    )
    return spawn_log_relay_process(
        relay_config_file=plan.relay_config_file,
        relay_stdout_file=plan.relay_stdout_file,
    )


def start_upload_worker(
    *,
    plan: RuntimePlan,
    init_result: RuntimeInitializationResult,
) -> tuple[subprocess.Popen[str], TextIO]:
    """启动独立 upload worker 并返回进程句柄。"""

    upload_stdout_handle = plan.upload_stdout_file.open("a", encoding="utf-8")
    upload_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "rift_audio_pipeline.control_plane.upload_worker",
            "--run-id",
            plan.run_id,
            "--state-db-path",
            str(init_result.state_db_file),
            "--baidu-token-file",
            str(init_result.baidu_token_file),
            "--baidu-remote-root",
            plan.baidu_remote_root,
            "--output-root",
            str(plan.output_root),
        ],
        stdout=upload_stdout_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return upload_process, upload_stdout_handle


def build_pipeline_environment(*, init_result: RuntimeInitializationResult) -> dict[str, str]:
    """构造 pipeline-main 启动所需环境变量。"""

    pipeline_env = dict(os.environ)
    pipeline_env["RIFT_BAIDU_APP_KEY"] = str(init_result.token_payload["app_key"])
    pipeline_env["RIFT_BAIDU_SECRET_KEY"] = str(init_result.token_payload["secret_key"])
    pipeline_env["RIFT_BAIDU_REFRESH_TOKEN"] = str(init_result.token_payload["refresh_token"])
    pipeline_env["RIFT_BAIDU_DATABASE_FILE"] = str(init_result.database_file)
    return pipeline_env


def run_pipeline_main(
    *,
    pipeline_command: list[str],
    pipeline_env: dict[str, str],
) -> int:
    """启动 pipeline-main 并等待其结束。"""

    pipeline_process = subprocess.Popen(  # noqa: S603
        pipeline_command,
        env=pipeline_env,
        text=True,
    )
    return pipeline_process.wait()


def run_finalize_worker(
    *,
    plan: RuntimePlan,
    init_result: RuntimeInitializationResult,
    final_status: str,
) -> int:
    """在 upload drain 后同步执行 finalize worker。"""

    finalize_completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "rift_audio_pipeline.control_plane.finalize_worker",
            "--run-id",
            plan.run_id,
            "--state-db-path",
            str(init_result.state_db_file),
            "--baidu-token-file",
            str(init_result.baidu_token_file),
            "--baidu-remote-root",
            plan.baidu_remote_root,
            "--database-file",
            str(init_result.database_file),
            "--log-root",
            str(plan.log_root),
            "--relay-state-file",
            str(plan.relay_state_file),
            "--relay-socket-path",
            str(plan.relay_socket_path),
            "--final-status",
            final_status,
        ],
        check=False,
        text=True,
    )
    return finalize_completed.returncode


def emit_run_result(result: JobRunnerResult) -> None:
    """输出 job runner 的统一 JSON 摘要。"""

    print(json.dumps(result.to_payload(), ensure_ascii=False, indent=2))
