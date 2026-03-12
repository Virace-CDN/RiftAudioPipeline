"""子进程 stdout 双写到文件与父进程流的辅助工具。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import threading
from typing import Callable
from typing import IO
from typing import Mapping
from typing import TextIO


@dataclass(frozen=True, slots=True)
class ProcessOutputHandle:
    """描述单个子进程的 stdout 镜像输出状态。"""

    log_file: Path
    log_handle: TextIO
    reader_thread: threading.Thread
    stream_label: str

    def close(self) -> None:
        """等待 reader 线程结束后关闭日志文件。"""

        self.reader_thread.join(timeout=5.0)
        if not self.log_handle.closed:
            self.log_handle.close()


def start_streamed_process(
    *,
    command: list[str],
    log_file: Path,
    stream_label: str,
    env: Mapping[str, str] | None = None,
    close_fds: bool = True,
    start_new_session: bool = False,
    mirror_predicate: Callable[[str], bool] | None = None,
) -> tuple[subprocess.Popen[str], ProcessOutputHandle]:
    """启动子进程，并把 stdout 同步写入文件与父进程 stdout。"""

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file.open("a", encoding="utf-8")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=dict(env) if env is not None else None,
        close_fds=close_fds,
        start_new_session=start_new_session,
    )
    if process.stdout is None:
        raise RuntimeError(f"启动 {stream_label} 失败：stdout pipe 不可用。")
    reader_thread = threading.Thread(
        target=_pump_process_output,
        args=(process.stdout, log_handle, stream_label, mirror_predicate),
        daemon=True,
        name=f"{stream_label}-stdout-pump",
    )
    reader_thread.start()
    return process, ProcessOutputHandle(
        log_file=log_file,
        log_handle=log_handle,
        reader_thread=reader_thread,
        stream_label=stream_label,
    )


def _pump_process_output(
    source: IO[str],
    log_handle: TextIO,
    stream_label: str,
    mirror_predicate: Callable[[str], bool] | None = None,
) -> None:
    """持续消费子进程 stdout，并镜像到文件与父进程 stdout。"""

    try:
        for raw_line in source:
            normalized_line = raw_line if raw_line.endswith("\n") else f"{raw_line}\n"
            log_handle.write(normalized_line)
            log_handle.flush()
            if mirror_predicate is not None and not mirror_predicate(normalized_line):
                continue
            sys.stdout.write(_format_stream_line(stream_label=stream_label, line=normalized_line))
            sys.stdout.flush()
    finally:
        source.close()


def _format_stream_line(*, stream_label: str, line: str) -> str:
    """给镜像到父进程的日志行补上来源前缀。"""

    return f"[{stream_label}] {line}"
