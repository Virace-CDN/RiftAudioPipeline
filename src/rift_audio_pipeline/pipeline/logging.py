"""Pipeline 日志落地与补偿上传。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import is_dataclass
from datetime import datetime
from pathlib import Path
import json
import uuid

from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineErrorSnapshot
from rift_audio_pipeline.pipeline.models import PendingLogUploadEntry
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.models import PipelineStage


@dataclass(frozen=True, slots=True)
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
    log_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

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
    )
    _append_log_line(context.text_log_file, f"{now.isoformat()} [init] run_id={run_id}")
    return context


def emit_event(ctx: PipelineLogContext, event: PipelineEvent) -> None:
    """写入结构化事件与文本日志。

    Args:
        ctx: 日志上下文。
        event: 事件对象。
    """

    serialized_event = _to_json_compatible(event)
    with ctx.events_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(serialized_event, ensure_ascii=False))
        handle.write("\n")
    _append_log_line(
        ctx.text_log_file,
        f"{event.created_at} [{event.stage.value}] {event.event_type}: {event.message}",
    )


def record_error_snapshot(
    ctx: PipelineLogContext,
    stage: PipelineStage,
    error: BaseException,
    payload: dict[str, object] | None = None,
) -> None:
    """记录失败快照。

    Args:
        ctx: 日志上下文。
        stage: 失败阶段。
        error: 原始异常。
        payload: 附加上下文。
    """

    content = PipelineErrorSnapshot(
        run_id=ctx.run_id,
        stage=stage,
        error_type=type(error).__name__,
        error_message=str(error),
        payload=payload or {},
        created_at=datetime.now().astimezone().isoformat(),
    )
    _write_json(ctx.error_file, content)
    _append_log_line(
        ctx.text_log_file,
        (
            f"{content.created_at} [error] stage={stage.value} "
            f"error={type(error).__name__}: {error}"
        ),
    )


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
