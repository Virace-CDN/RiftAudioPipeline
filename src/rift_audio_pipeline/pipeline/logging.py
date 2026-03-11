"""Pipeline 日志落地与补偿上传。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from dataclasses import is_dataclass
from datetime import datetime
import inspect
import json
import os
from pathlib import Path
from queue import Empty
from queue import Full
from queue import Queue
import socket
import subprocess
import sys
import threading
import time
import traceback
from typing import Callable
from typing import Protocol
import uuid

from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineErrorSnapshot
from rift_audio_pipeline.pipeline.models import PendingLogUploadEntry
from rift_audio_pipeline.pipeline.models import PipelineLogTerminalSummary
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.models import PipelineStage

_EVENT_WRITE_LOCK = threading.Lock()
_LOG_RELAY_SOCKET_ROOT = Path("/tmp/rift_audio_pipeline_log_relay")


@dataclass(frozen=True, slots=True)
class LogSinkConfig:
    """实时日志下沉配置。"""

    enabled: bool = False
    control_plane_base_url: str | None = None
    bearer_token: str | None = None
    access_client_id: str | None = None
    access_client_secret: str | None = None
    timeout_seconds: float = 5.0
    max_queue_size: int = 2000
    flush_interval_ms: int = 250
    retry_backoff_ms: tuple[int, ...] = (200, 1000, 5000)
    spool_dir: Path | None = None
    monitor_interval_ms: int = 500
    heartbeat_interval_ms: int = 5000


@dataclass(slots=True)
class PipelineLogContext:
    """一次 pipeline 运行的日志上下文。"""

    run_id: str
    run_date: str
    log_dir: Path
    state_dir: Path
    run_file: Path
    events_file: Path
    text_log_file: Path
    error_file: Path
    decision_file: Path
    artifacts_file: Path
    spool_dir: Path
    log_relay_state_file: Path
    relay_config_file: Path
    relay_stdout_file: Path
    relay_socket_file: Path
    next_event_seq: int = 1
    last_event_seq: int = 0
    log_delivery_sink: LogDeliverySink | None = field(default=None, repr=False)


class LogDeliverySink(Protocol):
    """运行期实时日志下沉接口。"""

    def start(self) -> None:
        """启动日志下沉端。"""

    def enqueue_event(self, payload: dict[str, object]) -> None:
        """投递单条结构化事件。"""

    def set_terminal_summary(self, summary: PipelineLogTerminalSummary) -> None:
        """登记终态摘要。"""

    def close(self, *, timeout_seconds: float = 10.0) -> None:
        """等待下沉端完成收尾。"""


class RelaySpoolPump:
    """relay 进程内的本地 spool + 重试发送引擎。"""

    def __init__(
        self,
        *,
        run_id: str,
        state_file: Path,
        config: LogSinkConfig,
        send_event: Callable[[dict[str, object]], None],
        send_terminal_summary: Callable[[dict[str, object]], None],
    ) -> None:
        self._run_id = run_id
        self._state_file = state_file
        self._config = config
        self._send_event = send_event
        self._send_terminal_summary = send_terminal_summary
        self._spool_dir = config.spool_dir or state_file.parent / "spool"
        self._event_spool_dir = self._spool_dir / "events"
        self._terminal_summary_file = self._spool_dir / "terminal_summary.json"
        self._queue: Queue[dict[str, object]] = Queue(maxsize=config.max_queue_size)
        self._terminal_summary: dict[str, object] | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._queued_event_seqs: set[int] = set()
        self._state = "created"
        self._dropped_events = 0
        self._last_sent_seq: int | None = None
        self._last_send_error: str | None = None
        self._terminal_sent = False
        self._event_spool_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """启动后台发送线程。"""

        if not self._config.enabled or self._thread is not None:
            return
        self._enqueue_pending_spool_events()
        self._load_terminal_summary_from_spool()
        self._state = "running"
        self._persist_state()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"RelaySpoolPump-{self._run_id}",
            daemon=True,
        )
        self._thread.start()

    def enqueue_event(self, payload: dict[str, object]) -> None:
        """把单条事件放入待发送队列。"""

        if not self._config.enabled:
            return
        event_seq = _require_event_seq(payload)
        self._write_json_file(self._event_spool_file(event_seq), payload)
        try:
            self._queue.put_nowait(dict(payload))
            with self._lock:
                self._queued_event_seqs.add(event_seq)
        except Full:
            with self._lock:
                self._dropped_events += 1
                self._last_send_error = "log queue full"
                self._persist_state()

    def set_terminal_summary(self, summary: PipelineLogTerminalSummary) -> None:
        """登记终态摘要，待队列 drain 后发送。"""

        self._terminal_summary = _to_json_compatible(summary)
        self._write_json_file(self._terminal_summary_file, self._terminal_summary)
        self._persist_state()

    def close(self, *, timeout_seconds: float = 10.0) -> None:
        """等待队列 drain，并尝试发送终态摘要。"""

        if not self._config.enabled:
            return
        self._enqueue_pending_spool_events()
        self._load_terminal_summary_from_spool()
        self._stop_event.set()
        self._state = "draining"
        self._persist_state()
        if self._thread is not None:
            self._thread.join(timeout=timeout_seconds)
        self._state = "closed"
        self._persist_state()

    def _run_loop(self) -> None:
        """后台发送循环。"""

        while True:
            if self._stop_event.is_set() and self._queue.empty():
                break
            try:
                payload = self._queue.get(timeout=self._config.flush_interval_ms / 1000)
            except Empty:
                continue
            try:
                self._send_with_retry(payload, self._send_event)
            finally:
                self._queue.task_done()
                with self._lock:
                    if isinstance(payload.get("seq"), int):
                        self._queued_event_seqs.discard(payload["seq"])
                self._enqueue_pending_spool_events()

        if self._terminal_summary is not None and not self._terminal_sent:
            self._send_with_retry(self._terminal_summary, self._send_terminal_summary)
            with self._lock:
                self._terminal_sent = True
                self._state = "flushed"
                if self._terminal_summary_file.exists():
                    self._terminal_summary_file.unlink()
                self._persist_state()

    def _send_with_retry(
        self,
        payload: dict[str, object],
        sender: Callable[[dict[str, object]], None],
    ) -> None:
        """按退避策略尝试发送。"""

        attempt_index = 0
        backoffs = (0, *self._config.retry_backoff_ms)
        while attempt_index < len(backoffs):
            if attempt_index > 0:
                time.sleep(backoffs[attempt_index] / 1000)
            try:
                sender(payload)
            except Exception as error:  # noqa: BLE001
                with self._lock:
                    self._last_send_error = str(error)
                    self._persist_state()
                attempt_index += 1
                continue

            with self._lock:
                if isinstance(payload.get("seq"), int):
                    self._last_sent_seq = payload["seq"]
                    event_spool_file = self._event_spool_file(payload["seq"])
                    if event_spool_file.exists():
                        event_spool_file.unlink()
                self._last_send_error = None
                self._persist_state()
            return

        with self._lock:
            self._dropped_events += 1
            self._persist_state()

    def _persist_state(self) -> None:
        """把当前发送状态落到 `log_relay_state.json`。"""

        payload = {
            "run_id": self._run_id,
            "state": self._state,
            "queue_size": self._queue.qsize(),
            "dropped_events": self._dropped_events,
            "last_sent_seq": self._last_sent_seq,
            "last_send_error": self._last_send_error,
            "terminal_sent": self._terminal_sent,
            "pending_spool_events": len(list(self._event_spool_dir.glob("*.json"))),
            "terminal_summary_pending": self._terminal_summary_file.exists(),
            "updated_at": datetime.now().astimezone().isoformat(),
        }
        self._state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _enqueue_pending_spool_events(self) -> None:
        """把仍未入队的 spool 事件补回发送队列。"""

        for file_path in self._list_spooled_event_files():
            if not file_path.exists():
                continue
            try:
                payload = self._read_json_file(file_path)
            except FileNotFoundError:
                continue
            event_seq = _require_event_seq(payload)
            with self._lock:
                if event_seq in self._queued_event_seqs or (
                    self._last_sent_seq is not None and event_seq <= self._last_sent_seq
                ):
                    continue
            try:
                self._queue.put_nowait(payload)
            except Full:
                return
            with self._lock:
                self._queued_event_seqs.add(event_seq)

    def _load_terminal_summary_from_spool(self) -> None:
        """从 spool 恢复终态摘要。"""

        if self._terminal_summary is not None or not self._terminal_summary_file.exists():
            return
        self._terminal_summary = self._read_json_file(self._terminal_summary_file)

    def _list_spooled_event_files(self) -> list[Path]:
        """列出当前 spool 目录中的事件文件。"""

        return sorted(self._event_spool_dir.glob("*.json"))

    def _event_spool_file(self, seq: int) -> Path:
        """返回某条事件的 spool 文件路径。"""

        return self._event_spool_dir / f"{seq:08d}.json"

    def _write_json_file(self, path: Path, payload: dict[str, object]) -> None:
        """把 JSON 对象写入磁盘。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json_file(self, path: Path) -> dict[str, object]:
        """读取 JSON 对象文件。"""

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"RelaySpoolPump spool 文件必须是 JSON 对象：{path}")
        return payload


class LogRelayClient:
    """把结构化事件交给独立 relay 进程。"""

    def __init__(
        self,
        *,
        run_id: str,
        relay_state_file: Path,
        relay_config_file: Path,
        relay_stdout_file: Path,
        relay_socket_file: Path,
        config: LogSinkConfig,
    ) -> None:
        self._run_id = run_id
        self._state_file = relay_state_file
        self._relay_config_file = relay_config_file
        self._relay_stdout_file = relay_stdout_file
        self._relay_socket_file = relay_socket_file
        self._config = config
        self._process: subprocess.Popen[str] | None = None
        self._stdout_handle: object | None = None
        self._terminal_summary: dict[str, object] | None = None
        self._started = False
        self._dropped_events = 0
        self._last_send_error: str | None = None

    def start(self) -> None:
        """启动 relay 子进程并等待本地 socket 就绪。"""

        if not self._config.enabled or self._started:
            return
        try:
            self._write_relay_config()
            self._spawn_process()
            self._wait_for_ready()
        except Exception as error:  # noqa: BLE001
            self._last_send_error = str(error)
            self._persist_state(state="relay_start_failed")
            self._cleanup_process()
            return
        self._started = True
        try:
            self._send_envelope(
                envelope_type="start",
                payload={
                    "main_pid": os.getpid(),
                    "started_at": datetime.now().astimezone().isoformat(),
                },
            )
        except RuntimeError as error:
            self._last_send_error = str(error)
            self._persist_state(state="start_signal_failed")

    def enqueue_event(self, payload: dict[str, object]) -> None:
        """把事件 envelope 发给 relay 进程。"""

        if not self._config.enabled:
            return
        self._send_envelope(
            envelope_type="event",
            payload=payload,
            count_drop_on_failure=True,
        )

    def set_terminal_summary(self, summary: PipelineLogTerminalSummary) -> None:
        """缓存终态摘要，等待 close 时发送给 relay。"""

        self._terminal_summary = _to_json_compatible(summary)

    def close(self, *, timeout_seconds: float = 10.0) -> None:
        """要求 relay drain 队列并退出。"""

        if not self._config.enabled:
            return
        if self._terminal_summary is not None:
            self._send_envelope(
                envelope_type="terminal_summary",
                payload=self._terminal_summary,
                count_drop_on_failure=False,
            )
        self._send_envelope(envelope_type="shutdown", payload={"run_id": self._run_id})
        if self._process is not None:
            try:
                self._process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                self._last_send_error = "relay shutdown timed out"
                self._persist_state(state="shutdown_timeout", terminal_sent=False)
        self._cleanup_process()

    def _spawn_process(self) -> None:
        """启动 relay 子进程。"""

        self._relay_stdout_file.parent.mkdir(parents=True, exist_ok=True)
        self._stdout_handle = self._relay_stdout_file.open("a", encoding="utf-8")
        src_root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{src_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(src_root)
        )
        self._persist_state(state="starting")
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "rift_audio_pipeline.control_plane.log_relay",
                "--config",
                str(self._relay_config_file),
            ],
            stdout=self._stdout_handle,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
            start_new_session=True,
            text=True,
        )

    def _write_relay_config(self) -> None:
        """把 relay 运行配置写到磁盘，供子进程读取。"""

        self._relay_config_file.parent.mkdir(parents=True, exist_ok=True)
        self._relay_socket_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self._run_id,
            "state_file": str(self._state_file),
            "spool_dir": str(self._config.spool_dir or self._state_file.parent / "spool"),
            "socket_path": str(self._relay_socket_file),
            "control_plane_base_url": self._config.control_plane_base_url,
            "bearer_token": self._config.bearer_token,
            "access_client_id": self._config.access_client_id,
            "access_client_secret": self._config.access_client_secret,
            "timeout_seconds": self._config.timeout_seconds,
            "max_queue_size": self._config.max_queue_size,
            "flush_interval_ms": self._config.flush_interval_ms,
            "retry_backoff_ms": list(self._config.retry_backoff_ms),
            "monitor_interval_ms": self._config.monitor_interval_ms,
            "heartbeat_interval_ms": self._config.heartbeat_interval_ms,
        }
        self._relay_config_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _wait_for_ready(self, *, timeout_seconds: float = 5.0) -> None:
        """等待 relay socket 可连接。"""

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(f"relay process exited with code {self._process.returncode}")
            try:
                self._send_envelope(
                    envelope_type="ping",
                    payload={"run_id": self._run_id},
                    await_response=True,
                )
            except RuntimeError:
                time.sleep(0.05)
                continue
            return
        raise TimeoutError(f"等待 relay socket 就绪超时：{self._relay_socket_file}")

    def _send_envelope(
        self,
        *,
        envelope_type: str,
        payload: dict[str, object],
        count_drop_on_failure: bool = False,
        await_response: bool = False,
    ) -> None:
        """通过本地 Unix socket 把 envelope 发给 relay。"""

        if not self._started and envelope_type != "ping":
            self._last_send_error = "relay is not ready"
            if count_drop_on_failure:
                self._dropped_events += 1
            self._persist_state(state="relay_unavailable")
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(min(self._config.timeout_seconds, 1.0))
                client.connect(str(self._relay_socket_file))
                client.sendall(
                    (
                        json.dumps(
                            {
                                "type": envelope_type,
                                "run_id": self._run_id,
                                "payload": payload,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    ).encode("utf-8")
                )
                client.shutdown(socket.SHUT_WR)
                response_raw = client.recv(4096) if await_response else b""
        except OSError as error:
            self._last_send_error = str(error)
            if count_drop_on_failure:
                self._dropped_events += 1
                self._persist_state(state="send_failed")
                return
            raise RuntimeError(f"relay envelope 发送失败：{self._relay_socket_file}") from error

        if not response_raw:
            return
        response = json.loads(response_raw.decode("utf-8"))
        if not isinstance(response, dict) or response.get("accepted") is not True:
            error_message = response.get("error", "relay rejected request")
            self._last_send_error = str(error_message)
            if count_drop_on_failure:
                self._dropped_events += 1
                self._persist_state(state="send_rejected")
                return
            raise RuntimeError(str(error_message))
        self._last_send_error = None

    def _persist_state(
        self,
        *,
        state: str,
        terminal_sent: bool | None = None,
    ) -> None:
        """把客户端本地状态写入状态文件。"""

        payload = {
            "run_id": self._run_id,
            "state": state,
            "dropped_events": self._dropped_events,
            "last_send_error": self._last_send_error,
            "terminal_sent": terminal_sent if terminal_sent is not None else False,
            "relay_pid": self._process.pid if self._process is not None else None,
            "socket_path": str(self._relay_socket_file),
            "updated_at": datetime.now().astimezone().isoformat(),
        }
        self._state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _cleanup_process(self) -> None:
        """关闭本地文件句柄。"""

        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=1.0)
        self._process = None
        if self._stdout_handle is not None:
            self._stdout_handle.close()
            self._stdout_handle = None


def initialize_run_logging(config: PipelineRunConfig) -> PipelineLogContext:
    """初始化一次运行的日志目录与上下文。

    Args:
        config: Pipeline 运行配置。

    Returns:
        PipelineLogContext: 已创建目录与文件路径的日志上下文。
    """

    now = datetime.now().astimezone()
    run_date = now.strftime("%Y-%m-%d")
    run_id = f"{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    log_dir = config.log_root / run_date / run_id
    state_dir = config.output_root / "state"
    spool_dir = log_dir / "spool"
    relay_socket_file = _LOG_RELAY_SOCKET_ROOT / f"{run_id}.sock"
    log_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    spool_dir.mkdir(parents=True, exist_ok=True)
    relay_socket_file.parent.mkdir(parents=True, exist_ok=True)

    context = PipelineLogContext(
        run_id=run_id,
        run_date=run_date,
        log_dir=log_dir,
        state_dir=state_dir,
        run_file=log_dir / "run.json",
        events_file=log_dir / "events.jsonl",
        text_log_file=log_dir / "pipeline.log",
        error_file=log_dir / "error.json",
        decision_file=log_dir / "decision.json",
        artifacts_file=log_dir / "artifacts.json",
        spool_dir=spool_dir,
        log_relay_state_file=log_dir / "log_relay_state.json",
        relay_config_file=log_dir / "log_relay_config.json",
        relay_stdout_file=log_dir / "log_relay_stdout.log",
        relay_socket_file=relay_socket_file,
    )
    _append_log_line(context.text_log_file, f"{now.isoformat()} [init] run_id={run_id}")
    return context


def emit_event(ctx: PipelineLogContext, event: PipelineEvent) -> None:
    """写入结构化事件与文本日志。

    Args:
        ctx: 日志上下文。
        event: 事件对象。
    """

    caller_file, caller_function, caller_line = _resolve_callsite(stacklevel=2)
    with _EVENT_WRITE_LOCK:
        seq = _reserve_event_seq(ctx, requested_seq=event.seq)
        serialized_event = {
            "schema_version": event.schema_version,
            "run_id": event.run_id,
            "seq": seq,
            "created_at": event.created_at,
            "source": event.source,
            "level": event.level,
            "stage": event.stage,
            "event_type": event.event_type,
            "message": event.message,
            "status_hint": event.status_hint,
            "thread_name": event.thread_name or threading.current_thread().name,
            "process_id": event.process_id or os.getpid(),
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "entity_alias": event.entity_alias,
            "attempt": event.attempt,
            "operation": event.operation,
            "code_file": event.code_file or caller_file,
            "code_function": event.code_function or caller_function,
            "code_line": event.code_line or caller_line,
            "error_type": event.error_type,
            "error_message": event.error_message,
            "exception_module": event.exception_module,
            "traceback": event.traceback,
            "cause_chain": event.cause_chain,
            "payload": event.payload,
        }
        with ctx.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_to_json_compatible(serialized_event), ensure_ascii=False))
            handle.write("\n")
    if ctx.log_delivery_sink is not None:
        ctx.log_delivery_sink.enqueue_event(_to_json_compatible(serialized_event))
    _append_log_line(
        ctx.text_log_file,
        (
            f"{event.created_at} [{event.stage.value}] "
            f"seq={seq} level={event.level} {event.event_type}: {event.message}"
        ),
    )


def record_error_snapshot(
    ctx: PipelineLogContext,
    stage: PipelineStage,
    error: BaseException,
    payload: dict[str, object] | None = None,
) -> PipelineErrorSnapshot:
    """记录失败快照。

    Args:
        ctx: 日志上下文。
        stage: 失败阶段。
        error: 原始异常。
        payload: 附加上下文。
    """

    error_payload = dict(payload or {})
    code_file, code_function, code_line = _extract_exception_location(error)
    content = PipelineErrorSnapshot(
        run_id=ctx.run_id,
        stage=stage,
        error_type=type(error).__name__,
        error_message=str(error),
        payload=error_payload,
        created_at=datetime.now().astimezone().isoformat(),
        thread_name=threading.current_thread().name,
        process_id=os.getpid(),
        entity_type=_extract_str_value(error_payload, "entity_type"),
        entity_id=_extract_int_value(error_payload, "entity_id"),
        entity_alias=_extract_str_value(error_payload, "entity_alias"),
        attempt=_extract_int_value(error_payload, "attempt"),
        operation=_extract_str_value(error_payload, "operation"),
        code_file=code_file,
        code_function=code_function,
        code_line=code_line,
        exception_module=type(error).__module__,
        traceback=_format_exception_traceback(error),
        cause_chain=_build_exception_cause_chain(error),
    )
    _write_json(ctx.error_file, content)
    location_fragment = (
        f" file={content.code_file}:{content.code_line}"
        if content.code_file is not None and content.code_line is not None
        else ""
    )
    _append_log_line(
        ctx.text_log_file,
        (
            f"{content.created_at} [error] stage={stage.value} "
            f"error={type(error).__name__}: {error}{location_fragment}"
        ),
    )
    if content.traceback:
        _append_log_line(ctx.text_log_file, content.traceback.rstrip())
    return content


def finalize_run_logging(
    ctx: PipelineLogContext,
    summary: PipelineRunSummary,
    *,
    decision_payload: object | None = None,
    artifacts_payload: object | None = None,
) -> None:
    """写入本轮运行的最终摘要文件。

    Args:
        ctx: 日志上下文。
        summary: 运行摘要。
        decision_payload: 决策摘要。
        artifacts_payload: 产物摘要。
    """

    _write_json(ctx.run_file, summary)
    if decision_payload is not None:
        _write_json(ctx.decision_file, decision_payload)
    if artifacts_payload is not None:
        _write_json(ctx.artifacts_file, artifacts_payload)
    _append_log_line(
        ctx.text_log_file,
        (
            f"{datetime.now().astimezone().isoformat()} [finalize] "
            f"status={summary.status} uploaded={summary.uploaded_archives}"
        ),
    )


def build_log_sink_config(config: PipelineRunConfig, ctx: PipelineLogContext) -> LogSinkConfig:
    """从运行配置派生实时日志下沉配置。"""

    relay_enabled = should_enable_log_relay(config)
    return LogSinkConfig(
        enabled=relay_enabled,
        control_plane_base_url=config.control_plane_base_url,
        bearer_token=config.control_plane_bearer_token,
        access_client_id=config.control_plane_access_client_id,
        access_client_secret=config.control_plane_access_client_secret,
        timeout_seconds=config.control_plane_timeout_seconds,
        spool_dir=ctx.spool_dir,
    )


def should_enable_log_relay(config: PipelineRunConfig) -> bool:
    """判断当前运行是否应启用独立 relay。"""

    return (
        bool(config.control_plane_base_url)
        and config.mode is not PipelineMode.LOCAL
        and sys.platform.startswith("linux")
    )


def finalize_log_relay_delivery(
    ctx: PipelineLogContext,
    terminal_summary: PipelineLogTerminalSummary,
) -> None:
    """把终态摘要交给日志下沉端，并等待 drain。"""

    if ctx.log_delivery_sink is None:
        return
    ctx.log_delivery_sink.set_terminal_summary(terminal_summary)
    ctx.log_delivery_sink.close()


def load_error_snapshot(ctx: PipelineLogContext) -> dict[str, object] | None:
    """读取当前运行的 `error.json`。"""

    if not ctx.error_file.exists():
        return None
    payload = json.loads(ctx.error_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"error.json 必须是 JSON 对象：{ctx.error_file}")
    return payload


def upload_run_logs(
    ctx: PipelineLogContext,
    config: PipelineRunConfig,
    baidu_client: BaiduPanClient,
) -> None:
    """上传本次运行日志目录。

    Args:
        ctx: 日志上下文。
        config: Pipeline 运行配置。
        baidu_client: 百度网盘客户端。
    """

    remote_base = f"{config.baidu_remote_root.rstrip('/')}/logs/{ctx.run_date}/{ctx.run_id}"
    _ensure_remote_directory(baidu_client=baidu_client, remote_dir=remote_base)
    for file_path in sorted(path for path in ctx.log_dir.rglob("*") if path.is_file()):
        relative_path = file_path.relative_to(ctx.log_dir).as_posix()
        remote_path = f"{remote_base}/{relative_path}"
        parent_remote_dir = remote_path.rsplit("/", 1)[0]
        _ensure_remote_directory(baidu_client=baidu_client, remote_dir=parent_remote_dir)
        baidu_client.upload_file(local_path=file_path, remote_path=remote_path)


def enqueue_pending_log_upload(
    config: PipelineRunConfig,
    log_dir: Path,
    *,
    error_message: str,
) -> None:
    """将日志补传任务写入待补偿队列。

    Args:
        config: Pipeline 运行配置。
        log_dir: 本地日志目录。
        error_message: 本次上传失败原因。
    """

    state_dir = config.output_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    queue_file = state_dir / "pending_log_upload_queue.json"
    existing_entries = _load_json_list(queue_file)
    existing_entries.append(
        _to_json_compatible(
            PendingLogUploadEntry(
                log_dir=str(log_dir.resolve()),
                remote_root=config.baidu_remote_root,
                error_message=error_message,
                enqueued_at=datetime.now().astimezone().isoformat(),
                run_id=log_dir.name,
            )
        )
    )
    _write_json(queue_file, existing_entries)


def _ensure_remote_directory(baidu_client: BaiduPanClient, remote_dir: str) -> None:
    """确保远端目录存在。

    Args:
        baidu_client: 百度网盘客户端。
        remote_dir: 远端目录路径。
    """

    parts = [part for part in remote_dir.strip("/").split("/") if part]
    if not parts:
        return
    current = ""
    for part in parts:
        current = f"{current}/{part}" if current else f"/{part}"
        try:
            baidu_client.get_path_entry(current)
        except FileNotFoundError:
            baidu_client.create_directory(current)


def _load_json_list(file_path: Path) -> list[dict[str, object]]:
    """读取 JSON 数组文件，不存在时返回空列表。"""

    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"待补偿队列格式非法，期望 list，实际为：{type(payload)!r}")
    normalized_payload: list[dict[str, object]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError(f"待补偿队列项格式非法，期望 dict，实际为：{type(entry)!r}")
        normalized_payload.append(entry)
    return normalized_payload


def _append_log_line(file_path: Path, message: str) -> None:
    """向文本日志追加一行。"""

    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(message)
        handle.write("\n")


def _reserve_event_seq(ctx: PipelineLogContext, requested_seq: int | None) -> int:
    """为当前运行分配或确认事件序号。"""

    seq = requested_seq if requested_seq is not None else ctx.next_event_seq
    ctx.last_event_seq = max(ctx.last_event_seq, seq)
    ctx.next_event_seq = max(ctx.next_event_seq, seq + 1)
    return seq


def _resolve_callsite(stacklevel: int) -> tuple[str | None, str | None, int | None]:
    """解析调用方代码位置。"""

    frame = inspect.currentframe()
    try:
        for _ in range(stacklevel):
            if frame is None:
                return None, None, None
            frame = frame.f_back
        if frame is None:
            return None, None, None
        return (
            _normalize_code_file(frame.f_code.co_filename),
            frame.f_code.co_name,
            frame.f_lineno,
        )
    finally:
        del frame


def _normalize_code_file(file_name: str) -> str:
    """尽量返回对当前仓库友好的代码路径。"""

    resolved_path = Path(file_name).resolve()
    try:
        return resolved_path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _extract_exception_location(
    error: BaseException,
) -> tuple[str | None, str | None, int | None]:
    """提取异常 traceback 的最后有效 frame。"""

    if error.__traceback__ is None:
        return None, None, None
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return None, None, None
    last_frame = frames[-1]
    return (
        _normalize_code_file(last_frame.filename),
        last_frame.name,
        last_frame.lineno,
    )


def _format_exception_traceback(error: BaseException) -> str | None:
    """格式化完整 traceback 文本。"""

    if error.__traceback__ is None:
        return None
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


def _build_exception_cause_chain(error: BaseException) -> tuple[dict[str, str], ...]:
    """构造 `__cause__` / `__context__` 摘要链。"""

    chain: list[dict[str, str]] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if current.__cause__ is not None:
            current = current.__cause__
            relation = "cause"
        elif current.__context__ is not None and not current.__suppress_context__:
            current = current.__context__
            relation = "context"
        else:
            break
        chain.append(
            {
                "relation": relation,
                "error_type": type(current).__name__,
                "error_message": str(current),
                "exception_module": type(current).__module__,
            }
        )
    return tuple(chain)


def _extract_str_value(payload: dict[str, object], key: str) -> str | None:
    """从 payload 中提取字符串值。"""

    value = payload.get(key)
    return value if isinstance(value, str) else None


def _extract_int_value(payload: dict[str, object], key: str) -> int | None:
    """从 payload 中提取整数值。"""

    value = payload.get(key)
    return value if isinstance(value, int) else None


def _require_event_seq(payload: dict[str, object]) -> int:
    """读取事件中的必填序号。"""

    value = payload.get("seq")
    if not isinstance(value, int):
        raise ValueError("日志 relay 事件 payload 缺少有效的整数 seq。")
    return value


def _write_json(file_path: Path, payload: object) -> None:
    """写入 UTF-8 JSON 文件。"""

    file_path.write_text(
        json.dumps(_to_json_compatible(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _to_json_compatible(value: object) -> object:
    """递归转换为 JSON 可序列化结构。"""

    if is_dataclass(value):
        return _to_json_compatible(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value") and type(value).__module__ == "enum":
        return getattr(value, "value")
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_compatible(item) for item in value]
    return value
