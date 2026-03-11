"""relay 进程配置与拉起辅助函数。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Protocol
from typing import TextIO


class RelayProcessConfig(Protocol):
    """描述 relay 子进程所需的最小配置字段。"""

    control_plane_base_url: str | None
    bearer_token: str | None
    access_client_id: str | None
    access_client_secret: str | None
    timeout_seconds: float
    max_queue_size: int
    flush_interval_ms: int
    retry_backoff_ms: tuple[int, ...]
    monitor_interval_ms: int
    heartbeat_interval_ms: int
    spool_dir: Path | None


def build_log_relay_config_payload(
    *,
    run_id: str,
    relay_state_file: Path,
    relay_socket_file: Path,
    config: RelayProcessConfig,
) -> dict[str, object]:
    """构造 relay 外部进程配置。"""

    return {
        "run_id": run_id,
        "state_file": str(relay_state_file),
        "spool_dir": str(config.spool_dir or relay_state_file.parent / "spool"),
        "socket_path": str(relay_socket_file),
        "control_plane_base_url": config.control_plane_base_url,
        "bearer_token": config.bearer_token,
        "access_client_id": config.access_client_id,
        "access_client_secret": config.access_client_secret,
        "timeout_seconds": config.timeout_seconds,
        "max_queue_size": config.max_queue_size,
        "flush_interval_ms": config.flush_interval_ms,
        "retry_backoff_ms": list(config.retry_backoff_ms),
        "monitor_interval_ms": config.monitor_interval_ms,
        "heartbeat_interval_ms": config.heartbeat_interval_ms,
    }


def write_log_relay_config(
    *,
    relay_config_file: Path,
    run_id: str,
    relay_state_file: Path,
    relay_socket_file: Path,
    config: RelayProcessConfig,
) -> None:
    """写 relay 进程配置文件。"""

    relay_config_file.parent.mkdir(parents=True, exist_ok=True)
    relay_socket_file.parent.mkdir(parents=True, exist_ok=True)
    relay_config_file.write_text(
        json.dumps(
            build_log_relay_config_payload(
                run_id=run_id,
                relay_state_file=relay_state_file,
                relay_socket_file=relay_socket_file,
                config=config,
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def spawn_log_relay_process(
    *,
    relay_config_file: Path,
    relay_stdout_file: Path,
) -> tuple[subprocess.Popen[str], TextIO]:
    """外部启动 relay 进程。"""

    relay_stdout_file.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = relay_stdout_file.open("a", encoding="utf-8")
    src_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{src_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(src_root)
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "rift_audio_pipeline.control_plane.log_relay",
            "--config",
            str(relay_config_file),
        ],
        stdout=stdout_handle,
        stderr=subprocess.STDOUT,
        env=env,
        close_fds=True,
        start_new_session=True,
        text=True,
    )
    return process, stdout_handle
