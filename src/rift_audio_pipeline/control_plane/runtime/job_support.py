"""job runner 编排辅助函数。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Callable

from rift_audio_pipeline.control_plane.runtime.relay_runtime import spawn_log_relay_process
from rift_audio_pipeline.control_plane.runtime.relay_runtime import write_log_relay_config
from rift_audio_pipeline.control_plane.runtime.process_output import ProcessOutputHandle
from rift_audio_pipeline.control_plane.runtime.process_output import start_streamed_process
from rift_audio_pipeline.control_plane.runtime_init import RuntimeInitializationResult
from rift_audio_pipeline.pipeline.logging import _LOG_RELAY_SOCKET_ROOT
from rift_audio_pipeline.pipeline.logging import LogSinkConfig

_DEFAULT_UPLOAD_WORKER_COUNT = 1
_MIN_UPLOAD_WAIT_SECONDS = 300.0
_SECONDS_PER_MIB = 1.0
_SECONDS_PER_TASK = 90.0
_MAX_UPLOAD_WAIT_SECONDS = 7200.0
_UPLOAD_POLL_INTERVAL_SECONDS = 2.0
_UPLOAD_DRAIN_GRACE_SECONDS = 30.0
_UPLOAD_WORKER_MIRRORED_EVENTS = frozenset(
    {
        "upload_worker_started",
        "upload_worker_drained",
        "upload_task_started",
        "upload_task_completed",
        "upload_task_rescheduled",
    }
)


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
    archive_remote_root: str
    meta_remote_root: str
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


@dataclass(frozen=True, slots=True)
class UploadQueueSnapshot:
    """上传队列的当前摘要。"""

    unfinished_count: int
    queued_count: int
    claimed_count: int
    retry_wait_count: int
    done_count: int
    remaining_bytes: int
    signature: tuple[tuple[int, str, str], ...]


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
        archive_remote_root=args.archive_remote_root,
        meta_remote_root=args.meta_remote_root,
        default_mode=args.default_mode,
        default_game_region=args.default_game_region,
        default_log_level=args.default_log_level,
    )


def prepare_relay(
    *,
    plan: RuntimePlan,
    control_plane_base_url: str | None,
    control_plane_bearer_token: str | None,
    control_plane_access_client_id: str | None,
    control_plane_access_client_secret: str | None,
    control_plane_timeout_seconds: float,
    ) -> tuple[subprocess.Popen[str] | None, ProcessOutputHandle | None]:
    """写入 relay 配置并启动独立 relay 进程。"""

    if not control_plane_base_url:
        return None, None
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


def _build_upload_worker_id(worker_index: int) -> str:
    """生成 upload worker 的稳定可读标识。"""

    return f"upload-worker-{worker_index:02d}"


def _build_upload_worker_stdout_file(*, runtime_root: Path, worker_id: str) -> Path:
    """为每个 upload worker 派生独立 stdout 日志文件。"""

    return runtime_root / f"{worker_id}.stdout.log"


def start_upload_worker(
    *,
    plan: RuntimePlan,
    init_result: RuntimeInitializationResult,
    worker_id: str,
) -> tuple[subprocess.Popen[str], ProcessOutputHandle]:
    """启动单个 upload worker 并返回进程句柄。"""

    upload_stdout_file = _build_upload_worker_stdout_file(
        runtime_root=plan.runtime_root,
        worker_id=worker_id,
    )
    return start_streamed_process(
        command=[
            sys.executable,
            "-u",
            "-m",
            "rift_audio_pipeline.control_plane.upload_worker",
            "--run-id",
            plan.run_id,
            "--state-db-path",
            str(init_result.state_db_file),
            "--baidu-token-file",
            str(init_result.baidu_token_file),
            "--archive-remote-root",
            plan.archive_remote_root,
            "--output-root",
            str(plan.output_root),
            "--worker-id",
            worker_id,
            "--delete-local-file-after-upload",
        ],
        log_file=upload_stdout_file,
        stream_label=worker_id,
        mirror_predicate=_should_mirror_upload_worker_line,
    )


def start_upload_workers(
    *,
    plan: RuntimePlan,
    init_result: RuntimeInitializationResult,
    worker_count: int = _DEFAULT_UPLOAD_WORKER_COUNT,
) -> tuple[list[subprocess.Popen[str]], list[ProcessOutputHandle]]:
    """启动多个 upload worker。"""

    processes: list[subprocess.Popen[str]] = []
    handles: list[ProcessOutputHandle] = []
    for worker_index in range(1, max(worker_count, 1) + 1):
        worker_id = _build_upload_worker_id(worker_index)
        process, handle = start_upload_worker(
            plan=plan,
            init_result=init_result,
            worker_id=worker_id,
        )
        processes.append(process)
        handles.append(handle)
    return processes, handles


def build_pipeline_environment(*, init_result: RuntimeInitializationResult) -> dict[str, str]:
    """构造 pipeline-main 启动所需环境变量。"""

    pipeline_env = dict(os.environ)
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


def wait_for_upload_workers(
    *,
    state_db_path: Path,
    run_id: str,
    upload_processes: list[subprocess.Popen[str]],
) -> int:
    """等待 upload worker 排空队列并退出。"""

    last_progress_at = time.monotonic()
    last_signature: tuple[tuple[int, str, str], ...] | None = None
    while True:
        snapshot = _read_upload_queue_snapshot(state_db_path=state_db_path, run_id=run_id)
        if snapshot.signature != last_signature:
            last_signature = snapshot.signature
            last_progress_at = time.monotonic()
        exit_codes = [process.poll() for process in upload_processes]
        failing_codes = [code for code in exit_codes if code not in (None, 0)]
        if failing_codes:
            return failing_codes[0]
        if snapshot.unfinished_count == 0 and all(code == 0 for code in exit_codes):
            return 0
        if snapshot.unfinished_count == 0 and all(code is not None for code in exit_codes):
            return 0
        if snapshot.unfinished_count == 0:
            if time.monotonic() - last_progress_at > _UPLOAD_DRAIN_GRACE_SECONDS:
                for process in upload_processes:
                    if process.poll() is None:
                        process.terminate()
                raise subprocess.TimeoutExpired(
                    cmd=[process.args for process in upload_processes],
                    timeout=_UPLOAD_DRAIN_GRACE_SECONDS,
                    output=(
                        f"upload drain 已完成但 worker 未在 {_UPLOAD_DRAIN_GRACE_SECONDS:.0f}s 内退出："
                        f"{snapshot}"
                    ),
                )
            time.sleep(_UPLOAD_POLL_INTERVAL_SECONDS)
            continue
        allowed_wait = _estimate_upload_wait_seconds(snapshot)
        if time.monotonic() - last_progress_at > allowed_wait:
            for process in upload_processes:
                if process.poll() is None:
                    process.terminate()
            raise subprocess.TimeoutExpired(
                cmd=[process.args for process in upload_processes],
                timeout=allowed_wait,
                output=(
                    "upload worker 长时间未见进度，当前摘要："
                    f"unfinished={snapshot.unfinished_count}, queued={snapshot.queued_count}, "
                    f"claimed={snapshot.claimed_count}, retry_wait={snapshot.retry_wait_count}, "
                    f"done={snapshot.done_count}, remaining_bytes={snapshot.remaining_bytes}"
                ),
            )
        time.sleep(_UPLOAD_POLL_INTERVAL_SECONDS)


def run_finalize_worker(
    *,
    plan: RuntimePlan,
    init_result: RuntimeInitializationResult,
    final_status: str,
    relay_enabled: bool,
) -> int:
    """在 upload drain 后同步执行 finalize worker。"""

    command = [
        sys.executable,
        "-m",
        "rift_audio_pipeline.control_plane.finalize_worker",
        "--run-id",
        plan.run_id,
        "--state-db-path",
        str(init_result.state_db_file),
        "--baidu-token-file",
        str(init_result.baidu_token_file),
        "--meta-remote-root",
        plan.meta_remote_root,
        "--database-file",
        str(init_result.database_file),
        "--log-root",
        str(plan.log_root),
        "--final-status",
        final_status,
    ]
    if relay_enabled:
        command.extend(
            [
                "--relay-state-file",
                str(plan.relay_state_file),
                "--relay-socket-path",
                str(plan.relay_socket_path),
            ]
        )
    finalize_completed = subprocess.run(command, check=False, text=True)
    return finalize_completed.returncode


def emit_run_result(result: JobRunnerResult) -> None:
    """输出 job runner 的统一 JSON 摘要。"""

    print(json.dumps(result.to_payload(), ensure_ascii=False, indent=2))


def _read_upload_queue_snapshot(*, state_db_path: Path, run_id: str) -> UploadQueueSnapshot:
    """读取当前上传队列摘要。"""

    with sqlite3.connect(state_db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, local_path, status, updated_at
            FROM upload_tasks
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()
    unfinished_statuses = {"queued", "claimed", "retry_wait"}
    unfinished_count = 0
    queued_count = 0
    claimed_count = 0
    retry_wait_count = 0
    done_count = 0
    remaining_bytes = 0
    signature: list[tuple[int, str, str]] = []
    for row in rows:
        task_id = int(row[0])
        local_path = Path(str(row[1]))
        status = str(row[2])
        updated_at = str(row[3]) if row[3] is not None else ""
        if status == "queued":
            queued_count += 1
        elif status == "claimed":
            claimed_count += 1
        elif status == "retry_wait":
            retry_wait_count += 1
        elif status == "done":
            done_count += 1
        if status in unfinished_statuses:
            unfinished_count += 1
            signature.append((task_id, status, updated_at))
            remaining_bytes += _measure_upload_task_bytes(local_path)
    return UploadQueueSnapshot(
        unfinished_count=unfinished_count,
        queued_count=queued_count,
        claimed_count=claimed_count,
        retry_wait_count=retry_wait_count,
        done_count=done_count,
        remaining_bytes=remaining_bytes,
        signature=tuple(signature),
    )


def _estimate_upload_wait_seconds(snapshot: UploadQueueSnapshot) -> float:
    """根据剩余文件大小和队列长度估算等待时长。"""

    remaining_mib = snapshot.remaining_bytes / (1024 * 1024)
    estimated = (
        _MIN_UPLOAD_WAIT_SECONDS
        + (remaining_mib * _SECONDS_PER_MIB)
        + (snapshot.unfinished_count * _SECONDS_PER_TASK)
    )
    return min(max(estimated, _MIN_UPLOAD_WAIT_SECONDS), _MAX_UPLOAD_WAIT_SECONDS)


def _measure_upload_task_bytes(local_path: Path) -> int:
    if local_path.is_file():
        return local_path.stat().st_size
    if local_path.is_dir():
        total_bytes = 0
        for child in local_path.rglob("*"):
            if child.is_file():
                total_bytes += child.stat().st_size
        return total_bytes
    return 0


def _should_mirror_upload_worker_line(line: str) -> bool:
    """只把 upload worker 的高层事件镜像到父进程 stdout。"""

    stripped = line.strip()
    if not stripped:
        return False
    try:
        payload = json.loads(stripped)
    except ValueError:
        return True
    if not isinstance(payload, dict):
        return True
    event_name = payload.get("event")
    return isinstance(event_name, str) and event_name in _UPLOAD_WORKER_MIRRORED_EVENTS
