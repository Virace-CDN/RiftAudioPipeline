"""独立 log relay 进程测试。"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from tests._control_plane_capture import ControlPlaneCaptureServer


def test_log_relay_should_infer_failed_when_main_process_exits_without_finalize(
    tmp_path: Path,
) -> None:
    """主进程消失且未发送终态时，relay 应自动判定失败。"""

    server = ControlPlaneCaptureServer(
        bootstrap_payload={
            "current_version": "16.5",
            "current_pair": {
                "version": "16.5",
                "lcu_manifest_url": "https://lcu.example/16.5",
                "game_manifest_url": "https://game.example/16.5",
            },
        }
    )
    server.start()
    main_process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.2)"])
    relay = _start_relay_process(tmp_path=tmp_path, base_url=server.base_url)
    try:
        _send_envelope(
            relay.socket_path,
            {
                "type": "start",
                "run_id": relay.run_id,
                "payload": {
                    "main_pid": main_process.pid,
                    "started_at": _timestamp(),
                },
            },
            await_response=False,
        )
        _send_envelope(
            relay.socket_path,
            {
                "type": "event",
                "run_id": relay.run_id,
                "payload": {
                    "schema_version": 1,
                    "run_id": relay.run_id,
                    "seq": 1,
                    "created_at": _timestamp(),
                    "source": "pipeline",
                    "level": "INFO",
                    "stage": "init",
                    "event_type": "run_started",
                    "message": "pipeline 开始运行",
                    "status_hint": "running",
                    "thread_name": "MainThread",
                    "process_id": main_process.pid,
                    "payload": {},
                },
            },
            await_response=False,
        )
        main_process.wait(timeout=3.0)
        relay.process.wait(timeout=5.0)

        assert server.terminal_summaries
        assert server.terminal_summaries[0]["summary"]["final_status"] == "failed"
        relay_runtime = server.terminal_summaries[0]["summary"]["summary"]["relay_runtime"]
        assert relay_runtime["status_reason"] == "main_process_exited_without_finalize"
        assert relay_runtime["start_signal_received"] is True
        assert relay_runtime["terminal_summary_received"] is True
        assert server.heartbeats
        assert server.heartbeats[-1]["status"] == "failed"
        assert server.heartbeats[-1]["progress"]["relay_runtime"]["status"] == "failed"
    finally:
        if relay.process.poll() is None:
            relay.process.kill()
            relay.process.wait(timeout=3.0)
        if main_process.poll() is None:
            main_process.kill()
            main_process.wait(timeout=3.0)
        server.close()


def test_log_relay_should_mark_partial_success_when_warning_seen(tmp_path: Path) -> None:
    """收到 warning 级事件且最终正常结束时，应标记为 partial_success。"""

    server = ControlPlaneCaptureServer(
        bootstrap_payload={
            "current_version": "16.5",
            "current_pair": {
                "version": "16.5",
                "lcu_manifest_url": "https://lcu.example/16.5",
                "game_manifest_url": "https://game.example/16.5",
            },
        }
    )
    server.start()
    relay = _start_relay_process(tmp_path=tmp_path, base_url=server.base_url)
    try:
        _send_envelope(
            relay.socket_path,
            {
                "type": "start",
                "run_id": relay.run_id,
                "payload": {
                    "main_pid": os.getpid(),
                    "started_at": _timestamp(),
                },
            },
            await_response=False,
        )
        _send_envelope(
            relay.socket_path,
            {
                "type": "event",
                "run_id": relay.run_id,
                "payload": {
                    "schema_version": 1,
                    "run_id": relay.run_id,
                    "seq": 1,
                    "created_at": _timestamp(),
                    "source": "pipeline",
                    "level": "INFO",
                    "stage": "init",
                    "event_type": "run_started",
                    "message": "pipeline 开始运行",
                    "status_hint": "running",
                    "thread_name": "MainThread",
                    "process_id": os.getpid(),
                    "payload": {},
                },
            },
            await_response=False,
        )
        _send_envelope(
            relay.socket_path,
            {
                "type": "event",
                "run_id": relay.run_id,
                "payload": {
                    "schema_version": 1,
                    "run_id": relay.run_id,
                    "seq": 2,
                    "created_at": _timestamp(),
                    "source": "pipeline",
                    "level": "WARNING",
                    "stage": "extract",
                    "event_type": "warning_detected",
                    "message": "出现需要关注的 warning",
                    "status_hint": "running",
                    "thread_name": "MainThread",
                    "process_id": os.getpid(),
                    "payload": {},
                },
            },
            await_response=False,
        )
        _send_envelope(
            relay.socket_path,
            {
                "type": "terminal_summary",
                "run_id": relay.run_id,
                "payload": {
                    "run_id": relay.run_id,
                    "finished_at": _timestamp(),
                    "final_status": "success",
                    "final_stage": "finalize",
                    "last_seq": 2,
                    "processed_targets": 1,
                    "succeeded_targets": 1,
                    "failed_targets": 0,
                    "uploaded_archives": 0,
                    "raw_log_bundle_ready": True,
                    "raw_log_local_dir": str(tmp_path),
                    "raw_log_remote_path": None,
                    "summary": {"status": "success"},
                    "schema_version": 1,
                },
            },
            await_response=False,
        )
        _send_envelope(
            relay.socket_path,
            {"type": "shutdown", "run_id": relay.run_id, "payload": {"run_id": relay.run_id}},
            await_response=False,
        )
        relay.process.wait(timeout=5.0)

        assert server.events
        assert "thread_name" not in server.events[0]["event"]
        assert "traceback" not in server.events[0]["event"]
        assert "cause_chain" not in server.events[0]["event"]
        assert server.terminal_summaries
        assert server.terminal_summaries[0]["summary"]["final_status"] == "partial_success"
        relay_runtime = server.terminal_summaries[0]["summary"]["summary"]["relay_runtime"]
        assert relay_runtime["attention_detected"] is True
        assert server.terminal_summaries[0]["summary"]["summary"]["status"] == "partial_success"
    finally:
        if relay.process.poll() is None:
            relay.process.kill()
            relay.process.wait(timeout=3.0)
        server.close()


class _RelayProcessHandle:
    """测试中持有 relay 进程及其路径。"""

    def __init__(self, *, process: subprocess.Popen[str], socket_path: Path, run_id: str) -> None:
        self.process = process
        self.socket_path = socket_path
        self.run_id = run_id


def _start_relay_process(*, tmp_path: Path, base_url: str) -> _RelayProcessHandle:
    """启动测试用 relay 进程。"""

    run_id = f"relay-test-{int(time.time() * 1000)}"
    log_dir = tmp_path / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    config_path = log_dir / "relay-config.json"
    socket_path = log_dir / "relay.sock"
    state_file = log_dir / "log_relay_state.json"
    stdout_file = log_dir / "relay_stdout.log"
    config_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "state_file": str(state_file),
                "spool_dir": str(log_dir / "spool"),
                "socket_path": str(socket_path),
                "control_plane_base_url": base_url,
                "timeout_seconds": 1.0,
                "max_queue_size": 100,
                "flush_interval_ms": 20,
                "retry_backoff_ms": [20],
                "monitor_interval_ms": 50,
                "heartbeat_interval_ms": 50,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    env = dict(os.environ)
    src_root = Path(__file__).resolve().parents[1] / "src"
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{src_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(src_root)
    )
    stdout_handle = stdout_file.open("a", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "rift_audio_pipeline.control_plane.log_relay",
            "--config",
            str(config_path),
        ],
        stdout=stdout_handle,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"relay process exited early: {stdout_file.read_text(encoding='utf-8')}")
        if socket_path.exists():
            _send_envelope(
                socket_path,
                {"type": "ping", "run_id": run_id, "payload": {"run_id": run_id}},
                await_response=True,
            )
            stdout_handle.close()
            return _RelayProcessHandle(process=process, socket_path=socket_path, run_id=run_id)
        time.sleep(0.05)
    stdout_handle.close()
    process.kill()
    process.wait(timeout=3.0)
    raise TimeoutError(f"relay socket 未就绪：{socket_path}")


def _send_envelope(socket_path: Path, envelope: dict[str, object], *, await_response: bool) -> dict[str, object] | None:
    """通过 Unix socket 向 relay 发送原始 envelope。"""

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1.0)
        client.connect(str(socket_path))
        client.sendall((json.dumps(envelope, ensure_ascii=False) + "\n").encode("utf-8"))
        client.shutdown(socket.SHUT_WR)
        if not await_response:
            return None
        response = json.loads(client.recv(4096).decode("utf-8"))
        if not isinstance(response, dict) or response.get("accepted") is not True:
            raise RuntimeError(f"relay ping failed: {response}")
        return response


def _timestamp() -> str:
    """返回测试用当前时间。"""

    return datetime.now().astimezone().isoformat()
