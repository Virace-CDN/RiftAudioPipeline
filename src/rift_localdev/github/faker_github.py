"""本地伪 GitHub Actions workflow dispatch 服务。"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from threading import Thread
from typing import Any
from typing import Callable
from urllib.parse import urlparse

from rift_audio_pipeline.control_plane.workflow_dispatch import (
    DispatchPayload as CoreDispatchPayload,
)
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchBaiduInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchExecutionInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchGameInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchIdTargets
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchManifestInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchManifestsInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchMetadataInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchRequestInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchTargetsInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import WorkflowDispatchCommandConfig
from rift_audio_pipeline.control_plane.workflow_dispatch import _ALLOWED_PAYLOAD_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _BAIDU_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _EXECUTION_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _GAME_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _ID_TARGET_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _MANIFEST_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _MANIFESTS_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _METADATA_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _REQUEST_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import _REQUEST_STAGE_TO_FLAGS
from rift_audio_pipeline.control_plane.workflow_dispatch import _TARGETS_INPUT_FIELDS
from rift_audio_pipeline.control_plane.workflow_dispatch import build_job_runner_command
from rift_audio_pipeline.control_plane.workflow_dispatch import (
    parse_dispatch_payload as parse_core_dispatch_payload,
)
from rift_audio_pipeline.control_plane.workflow_dispatch import redact_raw_dispatch_payload
from rift_audio_pipeline.control_plane.workflow_dispatch import serialize_dispatch_inputs
from rift_audio_pipeline.pipeline.models import DEFAULT_ARCHIVE_REMOTE_ROOT
from rift_audio_pipeline.pipeline.models import DEFAULT_META_REMOTE_ROOT

_DISPATCH_PATH_PATTERN = re.compile(
    r"^/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)/actions/workflows/(?P<workflow_id>[^/]+)/dispatches$"
)
_HEALTH_PATH = "/healthz"

PipelineLauncher = Callable[[list[str], Path, Path], int]


@dataclass(frozen=True, slots=True)
class FakerGitHubConfig:
    """faker-github 服务配置。"""

    storage_root: Path
    host: str = "127.0.0.1"
    port: int = 9001
    github_token: str = "local-dev-token"
    github_token_source: str = "provided"
    control_plane_base_url: str = "http://localhost:5173"
    control_plane_bearer_token: str | None = None
    control_plane_access_client_id: str | None = None
    control_plane_access_client_secret: str | None = None
    default_mode: str = "remote"
    default_game_region: str = "zh_CN"
    default_requested_by: str = "github-actions"
    output_root: Path = Path("output")
    temp_root: Path = Path("temp")
    log_root: Path | None = None
    archive_remote_root: str = DEFAULT_ARCHIVE_REMOTE_ROOT
    meta_remote_root: str = DEFAULT_META_REMOTE_ROOT
    default_log_level: str = "INFO"
    control_plane_timeout_seconds: float = 30.0
    dry_run: bool = False
    log_http_exchange: bool = False
    working_directory: Path = Path.cwd()
    python_executable: Path = Path(sys.executable)


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    """一次 dispatch 触发的本地收据。"""

    dispatch_id: str
    received_at: str
    owner: str
    repo: str
    workflow_id: str
    ref: str
    inputs: dict[str, Any]
    command: tuple[str, ...]
    dry_run: bool
    pid: int | None
    log_path: str | None


def _timestamp_now() -> str:
    """返回当前带时区的 ISO 8601 字符串。"""

    return datetime.now().astimezone().isoformat()


def _slug_now() -> str:
    """生成适合文件名的 dispatch id。"""

    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S-%f")


def _mask_token(token: str) -> str:
    """返回适合日志展示的 token 摘要。"""

    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:6]}...{token[-4:]}"


def _emit_http_log(enabled: bool, event: str, payload: dict[str, Any]) -> None:
    """按需输出结构化 HTTP 调试日志。"""

    if not enabled:
        return
    print(
        json.dumps(
            {
                "event": event,
                "at": _timestamp_now(),
                **payload,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def _coerce_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    """校验对象为 JSON object。"""

    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} 必须是 object。")
    return dict(value)


def _coerce_integer(value: object, *, field_name: str) -> int:
    """校验对象为整数。"""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} 必须是整数。")
    return value


def _coerce_optional_string(value: object, *, field_name: str) -> str | None:
    """校验可空字符串字段。"""

    if value is None:
        return None
    return _coerce_string(value, field_name=field_name)


def _coerce_optional_integer(value: object, *, field_name: str) -> int | None:
    """校验可空整数。"""

    if value is None:
        return None
    return _coerce_integer(value, field_name=field_name)


def _coerce_json_string_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    """把 JSON 字符串解析为 object。"""

    raw_text = _coerce_string(value, field_name=field_name)
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise ValueError(f"{field_name} 必须是 JSON object 字符串。") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} 必须是 JSON object 字符串。")
    return dict(parsed)


def _coerce_string(value: object, *, field_name: str) -> str:
    """校验对象为非空字符串。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串。")
    return value.strip()


def _parse_bool_input(value: object, *, field_name: str) -> bool:
    """解析布尔 workflow input。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{field_name} 必须是布尔值。")


def _parse_int_list_input(value: object, *, field_name: str) -> tuple[int, ...] | None:
    """解析 ID 列表输入。"""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("["):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:  # noqa: PERF203
                raise ValueError(f"{field_name} JSON 解析失败。") from exc
        else:
            items = [part.strip() for part in stripped.split(",") if part.strip()]
            return tuple(int(item) for item in items)
    if isinstance(value, list):
        return tuple(int(item) for item in value)
    raise ValueError(f"{field_name} 必须是逗号分隔字符串或 number[]。")


def _validate_known_fields(
    raw_inputs: dict[str, Any], *, field_name: str, allowed_fields: frozenset[str]
) -> None:
    """拒绝 schema 外字段。"""

    unknown_fields = sorted(set(raw_inputs) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"{field_name} 包含未知字段: {', '.join(unknown_fields)}。")


def _parse_manifest_inputs(
    raw_inputs: dict[str, Any], *, field_name: str
) -> DispatchManifestInputs:
    """解析单个 manifest 结构。"""

    _validate_known_fields(raw_inputs, field_name=field_name, allowed_fields=_MANIFEST_INPUT_FIELDS)
    return DispatchManifestInputs(
        version=_coerce_optional_string(
            raw_inputs.get("version"), field_name=f"{field_name}.version"
        ),
        lcu_url=_coerce_optional_string(
            raw_inputs.get("lcu_url"), field_name=f"{field_name}.lcu_url"
        ),
        game_url=_coerce_optional_string(
            raw_inputs.get("game_url"), field_name=f"{field_name}.game_url"
        ),
    )


def _parse_id_targets(raw_inputs: dict[str, Any], *, field_name: str) -> DispatchIdTargets:
    """解析只含 ID 的目标集合。"""

    _validate_known_fields(
        raw_inputs, field_name=field_name, allowed_fields=_ID_TARGET_INPUT_FIELDS
    )
    return DispatchIdTargets(
        ids=_parse_int_list_input(raw_inputs.get("ids"), field_name=f"{field_name}.ids") or tuple()
    )


def _validate_dispatch_inputs(raw_inputs: dict[str, Any]) -> DispatchInputs:
    """校验结构化 workflow inputs schema。"""

    _validate_known_fields(
        raw_inputs, field_name="inputs.payload", allowed_fields=_ALLOWED_PAYLOAD_FIELDS
    )
    request_inputs = _coerce_mapping(raw_inputs.get("request"), field_name="inputs.payload.request")
    game_inputs = _coerce_mapping(raw_inputs.get("game"), field_name="inputs.payload.game")
    manifests_inputs = _coerce_mapping(
        raw_inputs.get("manifests"), field_name="inputs.payload.manifests"
    )
    targets_inputs = _coerce_mapping(raw_inputs.get("targets"), field_name="inputs.payload.targets")
    baidu_inputs = _coerce_mapping(raw_inputs.get("baidu"), field_name="inputs.payload.baidu")
    execution_inputs = _coerce_mapping(
        raw_inputs.get("execution"), field_name="inputs.payload.execution"
    )
    metadata_inputs = _coerce_mapping(
        raw_inputs.get("metadata"), field_name="inputs.payload.metadata"
    )

    _validate_known_fields(
        request_inputs, field_name="inputs.payload.request", allowed_fields=_REQUEST_INPUT_FIELDS
    )
    _validate_known_fields(
        game_inputs, field_name="inputs.payload.game", allowed_fields=_GAME_INPUT_FIELDS
    )
    _validate_known_fields(
        manifests_inputs,
        field_name="inputs.payload.manifests",
        allowed_fields=_MANIFESTS_INPUT_FIELDS,
    )
    _validate_known_fields(
        targets_inputs, field_name="inputs.payload.targets", allowed_fields=_TARGETS_INPUT_FIELDS
    )
    _validate_known_fields(
        baidu_inputs, field_name="inputs.payload.baidu", allowed_fields=_BAIDU_INPUT_FIELDS
    )
    _validate_known_fields(
        execution_inputs,
        field_name="inputs.payload.execution",
        allowed_fields=_EXECUTION_INPUT_FIELDS,
    )
    _validate_known_fields(
        metadata_inputs,
        field_name="inputs.payload.metadata",
        allowed_fields=_METADATA_INPUT_FIELDS,
    )

    return DispatchInputs(
        schema_version=_coerce_optional_string(
            raw_inputs.get("schema_version"), field_name="inputs.payload.schema_version"
        ),
        request=DispatchRequestInputs(
            mode=_coerce_optional_string(
                request_inputs.get("mode"), field_name="inputs.payload.request.mode"
            ),
            stage=_coerce_optional_string(
                request_inputs.get("stage"), field_name="inputs.payload.request.stage"
            ),
        ),
        game=DispatchGameInputs(
            region=_coerce_optional_string(
                game_inputs.get("region"), field_name="inputs.payload.game.region"
            )
        ),
        manifests=DispatchManifestsInputs(
            current=_parse_manifest_inputs(
                _coerce_mapping(
                    manifests_inputs.get("current"), field_name="inputs.payload.manifests.current"
                ),
                field_name="inputs.payload.manifests.current",
            ),
            previous=_parse_manifest_inputs(
                _coerce_mapping(
                    manifests_inputs.get("previous"),
                    field_name="inputs.payload.manifests.previous",
                ),
                field_name="inputs.payload.manifests.previous",
            ),
        ),
        targets=DispatchTargetsInputs(
            champions=_parse_id_targets(
                _coerce_mapping(
                    targets_inputs.get("champions"),
                    field_name="inputs.payload.targets.champions",
                ),
                field_name="inputs.payload.targets.champions",
            ),
            maps=_parse_id_targets(
                _coerce_mapping(
                    targets_inputs.get("maps"), field_name="inputs.payload.targets.maps"
                ),
                field_name="inputs.payload.targets.maps",
            ),
        ),
        baidu=DispatchBaiduInputs(
            app_key=_coerce_optional_string(
                baidu_inputs.get("app_key"),
                field_name="inputs.payload.baidu.app_key",
            ),
            secret_key=_coerce_optional_string(
                baidu_inputs.get("secret_key"),
                field_name="inputs.payload.baidu.secret_key",
            ),
            refresh_token=_coerce_optional_string(
                baidu_inputs.get("refresh_token"),
                field_name="inputs.payload.baidu.refresh_token",
            ),
        ),
        execution=DispatchExecutionInputs(
            force_update=(
                None
                if execution_inputs.get("force_update") is None
                else _parse_bool_input(
                    execution_inputs.get("force_update"),
                    field_name="inputs.payload.execution.force_update",
                )
            ),
            max_workers=_coerce_optional_integer(
                execution_inputs.get("max_workers"),
                field_name="inputs.payload.execution.max_workers",
            ),
            download_retry_attempts=_coerce_optional_integer(
                execution_inputs.get("download_retry_attempts"),
                field_name="inputs.payload.execution.download_retry_attempts",
            ),
            entity_retry_attempts=_coerce_optional_integer(
                execution_inputs.get("entity_retry_attempts"),
                field_name="inputs.payload.execution.entity_retry_attempts",
            ),
            log_level=_coerce_optional_string(
                execution_inputs.get("log_level"),
                field_name="inputs.payload.execution.log_level",
            ),
            archive_password=_coerce_optional_string(
                execution_inputs.get("archive_password"),
                field_name="inputs.payload.execution.archive_password",
            ),
        ),
        metadata=DispatchMetadataInputs(
            requested_by=_coerce_optional_string(
                metadata_inputs.get("requested_by"),
                field_name="inputs.payload.metadata.requested_by",
            )
        ),
    )


def _append_bool_flag(command: list[str], flag_name: str, value: bool) -> None:
    """为 BooleanOptionalAction 形式的参数追加显式值。"""

    command.append(f"--{flag_name}" if value else f"--no-{flag_name}")


def _append_stage_flags(command: list[str], *, stage: str | None) -> None:
    """把结构化 stage 翻译为 pipeline 执行开关。"""

    if stage is None:
        return
    normalized_stage = _coerce_string(stage, field_name="stage").casefold()
    flags = _REQUEST_STAGE_TO_FLAGS.get(normalized_stage)
    if flags is None:
        supported = ", ".join(sorted(_REQUEST_STAGE_TO_FLAGS))
        raise ValueError(f"stage 仅支持: {supported}。")
    run_update, run_extract, run_mapping = flags
    _append_bool_flag(command, "run-update", run_update)
    _append_bool_flag(command, "run-extract", run_extract)
    _append_bool_flag(command, "run-mapping", run_mapping)


def _extract_authorization_token(header_value: str | None) -> str | None:
    """从 Authorization 头中提取 token。"""

    if header_value is None:
        return None
    parts = header_value.strip().split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() not in {"bearer", "token"} or not token.strip():
        return None
    return token.strip()


def _launch_pipeline_subprocess(command: list[str], cwd: Path, log_path: Path) -> int:
    """异步拉起 pipeline 子进程。"""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(  # noqa: S603
            command,
            cwd=cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
    return process.pid


def _build_workflow_dispatch_command_config(
    config: FakerGitHubConfig,
) -> WorkflowDispatchCommandConfig:
    """把本地 fake GitHub 配置翻译成 job runner 命令配置。"""

    return WorkflowDispatchCommandConfig(
        storage_root=config.storage_root,
        control_plane_base_url=config.control_plane_base_url,
        control_plane_bearer_token=config.control_plane_bearer_token,
        control_plane_access_client_id=config.control_plane_access_client_id,
        control_plane_access_client_secret=config.control_plane_access_client_secret,
        default_mode=config.default_mode,
        default_game_region=config.default_game_region,
        default_requested_by=config.default_requested_by,
        output_root=config.output_root,
        temp_root=config.temp_root,
        log_root=config.log_root,
        archive_remote_root=config.archive_remote_root,
        meta_remote_root=config.meta_remote_root,
        default_log_level=config.default_log_level,
        control_plane_timeout_seconds=config.control_plane_timeout_seconds,
        python_executable=config.python_executable,
    )


class FakerGitHubState:
    """维护 dispatch 收据与进程拉起逻辑。"""

    def __init__(
        self,
        config: FakerGitHubConfig,
        launcher: PipelineLauncher | None = None,
    ) -> None:
        self.config = config
        self._launcher = launcher or _launch_pipeline_subprocess
        self._lock = Lock()
        self.storage_root = config.storage_root
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._latest_receipt: DispatchReceipt | None = None

    def latest_receipt(self) -> DispatchReceipt | None:
        """返回最近一次成功派发的收据。"""

        with self._lock:
            return self._latest_receipt

    def handle_dispatch(
        self,
        *,
        owner: str,
        repo: str,
        workflow_id: str,
        payload: CoreDispatchPayload,
    ) -> DispatchReceipt:
        """处理 workflow_dispatch 请求并拉起 pipeline。"""

        dispatch_id = _slug_now()
        dispatch_inputs_file = self.storage_root / "dispatch_inputs" / f"{dispatch_id}.json"
        dispatch_inputs_file.parent.mkdir(parents=True, exist_ok=True)
        dispatch_inputs_file.write_text(
            json.dumps(serialize_dispatch_inputs(payload.inputs), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        command = build_job_runner_command(
            config=_build_workflow_dispatch_command_config(self.config),
            payload=payload,
            dispatch_inputs_file=dispatch_inputs_file,
        )
        log_path: Path | None = None
        pid: int | None = None
        if not self.config.dry_run:
            log_path = self.storage_root / "logs" / f"{dispatch_id}.log"
            pid = self._launcher(command, self.config.working_directory, log_path)
        receipt = DispatchReceipt(
            dispatch_id=dispatch_id,
            received_at=_timestamp_now(),
            owner=owner,
            repo=repo,
            workflow_id=workflow_id,
            ref=payload.ref,
            inputs=serialize_dispatch_inputs(payload.inputs, redact_secrets=True),
            command=tuple(command),
            dry_run=self.config.dry_run,
            pid=pid,
            log_path=str(log_path) if log_path is not None else None,
        )
        receipt_path = self.storage_root / "dispatches" / f"{dispatch_id}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(asdict(receipt), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with self._lock:
            self._latest_receipt = receipt
        return receipt


class _FakerGitHubHttpServer(ThreadingHTTPServer):
    """携带共享状态的 HTTP server。"""

    def __init__(self, state: FakerGitHubState) -> None:
        self.state = state
        super().__init__(
            (state.config.host, state.config.port),
            _FakerGitHubRequestHandler,
        )


class _FakerGitHubRequestHandler(BaseHTTPRequestHandler):
    """处理 GitHub workflow dispatch 子集。"""

    server: _FakerGitHubHttpServer

    def do_GET(self) -> None:  # noqa: N802
        """处理健康检查请求。"""

        if urlparse(self.path).path != _HEALTH_PATH:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "not_found", "message": "Only /healthz is supported."},
            )
            return
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "base_url": self.server.state.config.control_plane_base_url,
                "dry_run": self.server.state.config.dry_run,
                "auth_required": True,
                "github_token_source": self.server.state.config.github_token_source,
                "github_token_preview": _mask_token(self.server.state.config.github_token),
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        """处理 workflow_dispatch。"""

        path = urlparse(self.path).path
        match = _DISPATCH_PATH_PATTERN.fullmatch(path)
        if match is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "not_found", "message": "Only workflow dispatch is supported."},
            )
            return
        if not self._check_authorization():
            return
        payload = self._read_json_object()
        if payload is None:
            return
        _emit_http_log(
            self.server.state.config.log_http_exchange,
            "dispatch_request",
            {
                "method": "POST",
                "path": path,
                "owner": match.group("owner"),
                "repo": match.group("repo"),
                "workflow_id": match.group("workflow_id"),
                "request_payload": redact_raw_dispatch_payload(payload),
            },
        )
        try:
            dispatch_payload = parse_core_dispatch_payload(payload)
            _emit_http_log(
                self.server.state.config.log_http_exchange,
                "workflow_inputs",
                {
                    "owner": match.group("owner"),
                    "repo": match.group("repo"),
                    "workflow_id": match.group("workflow_id"),
                    "ref": dispatch_payload.ref,
                    "inputs": serialize_dispatch_inputs(
                        dispatch_payload.inputs,
                        redact_secrets=True,
                    ),
                },
            )
            receipt = self.server.state.handle_dispatch(
                owner=match.group("owner"),
                repo=match.group("repo"),
                workflow_id=match.group("workflow_id"),
                payload=dispatch_payload,
            )
        except ValueError as exc:
            self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "validation_failed", "message": str(exc)},
            )
            return

        response_summary = {
            "dispatch_id": receipt.dispatch_id,
            "owner": receipt.owner,
            "repo": receipt.repo,
            "workflow_id": receipt.workflow_id,
            "ref": receipt.ref,
            "dry_run": receipt.dry_run,
            "pid": receipt.pid,
            "log_path": receipt.log_path,
            "command": list(receipt.command),
        }
        print(
            json.dumps(
                response_summary,
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        _emit_http_log(
            self.server.state.config.log_http_exchange,
            "dispatch_response",
            {
                "method": "POST",
                "path": path,
                "status": int(HTTPStatus.NO_CONTENT),
                "response_summary": response_summary,
            },
        )
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """静默默认访问日志。"""

    def _check_authorization(self) -> bool:
        """校验本地 fake GitHub token。"""

        token = _extract_authorization_token(self.headers.get("Authorization"))
        if token == self.server.state.config.github_token:
            return True
        self._send_json(
            HTTPStatus.UNAUTHORIZED,
            {
                "error": "unauthorized",
                "message": "Authorization header must carry the configured GitHub token.",
            },
            extra_headers={"WWW-Authenticate": 'Bearer realm="faker-github"'},
        )
        return False

    def _read_json_object(self) -> dict[str, Any] | None:
        """读取并解析 JSON object 请求体。"""

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_json(
                HTTPStatus.LENGTH_REQUIRED,
                {"error": "length_required", "message": "Content-Length is required."},
            )
            return None
        try:
            body = self.rfile.read(int(content_length))
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_json", "message": str(exc)},
            )
            return None
        if not isinstance(payload, dict):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_body", "message": "Request body must be an object."},
            )
            return None
        return payload

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        """发送 JSON 响应。"""

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        _emit_http_log(
            self.server.state.config.log_http_exchange,
            "http_response",
            {
                "method": self.command,
                "path": urlparse(self.path).path,
                "status": int(status),
                "response_payload": payload,
            },
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers is not None:
            for header_name, header_value in extra_headers.items():
                self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(body)


class FakerGitHubServer:
    """对外暴露 start/close 的 faker-github server 包装。"""

    def __init__(
        self,
        config: FakerGitHubConfig,
        launcher: PipelineLauncher | None = None,
    ) -> None:
        self._server = _FakerGitHubHttpServer(FakerGitHubState(config, launcher=launcher))
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        """返回监听地址。"""

        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        """后台启动 HTTP server。"""

        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        """关闭 HTTP server。"""

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


def build_parser() -> argparse.ArgumentParser:
    """构造 faker-github CLI 参数。"""

    parser = argparse.ArgumentParser(
        description="运行本地 faker-github server，模拟 GitHub workflow dispatch。"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument(
        "--github-token",
        help="本地 fake GitHub token；若不提供则启动时自动生成。",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path("temp/faker_github"),
        help="dispatch 收据与子进程日志落盘目录。",
    )
    parser.add_argument(
        "--control-plane-base-url",
        default="http://localhost:5173",
        help="启动 pipeline 时回调的 control plane 基础 URL。",
    )
    parser.add_argument("--control-plane-bearer-token")
    parser.add_argument("--control-plane-access-client-id")
    parser.add_argument("--control-plane-access-client-secret")
    parser.add_argument("--default-mode", default="remote")
    parser.add_argument("--default-game-region", default="zh_CN")
    parser.add_argument("--default-requested-by", default="github-actions")
    parser.add_argument("--output-root", type=Path, default=Path("output"))
    parser.add_argument("--temp-root", type=Path, default=Path("temp"))
    parser.add_argument("--log-root", type=Path)
    parser.add_argument("--archive-remote-root", default=DEFAULT_ARCHIVE_REMOTE_ROOT)
    parser.add_argument("--meta-remote-root", default=DEFAULT_META_REMOTE_ROOT)
    parser.add_argument("--default-log-level", default="INFO")
    parser.add_argument("--control-plane-timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--log-http-exchange",
        action="store_true",
        help="把 dispatch 请求入参与响应摘要输出到 stdout，便于联调观察。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出解析后的 pipeline CLI 命令，不真实启动子进程。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    args = build_parser().parse_args(argv)
    github_token = args.github_token or secrets.token_urlsafe(24)
    server = FakerGitHubServer(
        FakerGitHubConfig(
            storage_root=args.storage_root,
            host=args.host,
            port=args.port,
            github_token=github_token,
            github_token_source="provided" if args.github_token else "generated",
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
            archive_remote_root=args.archive_remote_root,
            meta_remote_root=args.meta_remote_root,
            default_log_level=args.default_log_level,
            control_plane_timeout_seconds=args.control_plane_timeout_seconds,
            dry_run=args.dry_run,
            log_http_exchange=args.log_http_exchange,
        )
    )
    print(
        json.dumps(
            {
                "base_url": server.base_url,
                "dispatch_route": (
                    f"{server.base_url}/repos/<owner>/<repo>/actions/workflows/"
                    "<workflow_id>/dispatches"
                ),
                "healthz": f"{server.base_url}{_HEALTH_PATH}",
                "storage_root": str(args.storage_root),
                "github_token": github_token,
                "github_token_source": "provided" if args.github_token else "generated",
                "github_token_preview": _mask_token(github_token),
                "control_plane_base_url": args.control_plane_base_url,
                "dry_run": args.dry_run,
                "log_http_exchange": args.log_http_exchange,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    server.start()
    try:
        if server._thread is not None:
            server._thread.join()
    except KeyboardInterrupt:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
