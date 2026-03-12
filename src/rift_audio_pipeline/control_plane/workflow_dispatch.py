"""workflow_dispatch 结构、校验与 job runner 命令构造。"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

_ALLOWED_INPUT_WRAPPER_FIELDS = frozenset({"payload"})
_ALLOWED_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "request",
        "game",
        "manifests",
        "targets",
        "baidu",
        "execution",
        "metadata",
    }
)
_REQUEST_INPUT_FIELDS = frozenset({"mode", "stage"})
_GAME_INPUT_FIELDS = frozenset({"region"})
_MANIFESTS_INPUT_FIELDS = frozenset({"current", "previous"})
_MANIFEST_INPUT_FIELDS = frozenset({"version", "lcu_url", "game_url"})
_TARGETS_INPUT_FIELDS = frozenset({"champions", "maps"})
_ID_TARGET_INPUT_FIELDS = frozenset({"ids"})
_BAIDU_INPUT_FIELDS = frozenset({"access_token", "app_key", "secret_key", "refresh_token"})
_EXECUTION_INPUT_FIELDS = frozenset(
    {
        "force_update",
        "max_workers",
        "download_retry_attempts",
        "entity_retry_attempts",
        "log_level",
        "archive_password",
    }
)
_METADATA_INPUT_FIELDS = frozenset({"requested_by"})
_SENSITIVE_BAIDU_FIELDS = frozenset({"access_token", "app_key", "secret_key", "refresh_token"})
_REDACTED_SECRET = "***REDACTED***"
_REQUEST_STAGE_TO_FLAGS = {
    None: (True, True, False),
    "update": (True, False, False),
    "extract": (True, True, False),
    "mapping": (True, True, True),
}


@dataclass(frozen=True, slots=True)
class WorkflowDispatchCommandConfig:
    """构造 job runner 命令所需的固定运行配置。"""

    storage_root: Path
    control_plane_base_url: str
    control_plane_bearer_token: str | None = None
    control_plane_access_client_id: str | None = None
    control_plane_access_client_secret: str | None = None
    default_mode: str = "remote"
    default_game_region: str = "zh_CN"
    default_requested_by: str = "github-actions"
    output_root: Path = Path("output")
    temp_root: Path = Path("temp")
    log_root: Path | None = None
    baidu_remote_root: str = "/apps/rift-audio-pipeline"
    default_log_level: str = "INFO"
    control_plane_timeout_seconds: float = 30.0
    python_executable: Path = Path(sys.executable)


@dataclass(frozen=True, slots=True)
class DispatchPayload:
    """workflow_dispatch 请求负载。"""

    ref: str
    inputs: "DispatchInputs"


@dataclass(frozen=True, slots=True)
class DispatchRequestInputs:
    """一次 dispatch 的请求维度参数。"""

    mode: str | None = None
    stage: str | None = None


@dataclass(frozen=True, slots=True)
class DispatchGameInputs:
    """一次 dispatch 的游戏上下文。"""

    region: str | None = None


@dataclass(frozen=True, slots=True)
class DispatchManifestInputs:
    """单个 manifest 对。"""

    version: str | None = None
    lcu_url: str | None = None
    game_url: str | None = None


@dataclass(frozen=True, slots=True)
class DispatchManifestsInputs:
    """当前版与上一版 manifest 信息。"""

    current: DispatchManifestInputs = field(default_factory=DispatchManifestInputs)
    previous: DispatchManifestInputs = field(default_factory=DispatchManifestInputs)


@dataclass(frozen=True, slots=True)
class DispatchIdTargets:
    """单类实体的 ID 目标集合。"""

    ids: tuple[int, ...] = tuple()


@dataclass(frozen=True, slots=True)
class DispatchTargetsInputs:
    """实体目标集合。"""

    champions: DispatchIdTargets = field(default_factory=DispatchIdTargets)
    maps: DispatchIdTargets = field(default_factory=DispatchIdTargets)


@dataclass(frozen=True, slots=True)
class DispatchBaiduInputs:
    """手动 workflow dispatch 使用的百度凭据。"""

    access_token: str | None = None
    app_key: str | None = None
    secret_key: str | None = None
    refresh_token: str | None = None


@dataclass(frozen=True, slots=True)
class DispatchExecutionInputs:
    """运行策略参数。"""

    force_update: bool | None = None
    max_workers: int | None = None
    download_retry_attempts: int | None = None
    entity_retry_attempts: int | None = None
    log_level: str | None = None
    archive_password: str | None = None


@dataclass(frozen=True, slots=True)
class DispatchMetadataInputs:
    """请求来源等元信息。"""

    requested_by: str | None = None


@dataclass(frozen=True, slots=True)
class DispatchInputs:
    """结构化 workflow inputs。"""

    schema_version: str | None = None
    request: DispatchRequestInputs = field(default_factory=DispatchRequestInputs)
    game: DispatchGameInputs = field(default_factory=DispatchGameInputs)
    manifests: DispatchManifestsInputs = field(default_factory=DispatchManifestsInputs)
    targets: DispatchTargetsInputs = field(default_factory=DispatchTargetsInputs)
    baidu: DispatchBaiduInputs = field(default_factory=DispatchBaiduInputs)
    execution: DispatchExecutionInputs = field(default_factory=DispatchExecutionInputs)
    metadata: DispatchMetadataInputs = field(default_factory=DispatchMetadataInputs)


def _coerce_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} 必须是 object。")
    return dict(value)


def _coerce_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} 必须是整数。")
    return value


def _coerce_optional_integer(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    return _coerce_integer(value, field_name=field_name)


def _coerce_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _coerce_string(value, field_name=field_name)


def _coerce_json_string_mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} 必须是 JSON object 字符串。")
    try:
        decoded = json.loads(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} 不是合法 JSON：{exc}") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{field_name} 必须是 JSON object。")
    return dict(decoded)


def _coerce_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串。")
    return value.strip()


def _parse_bool_input(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"{field_name} 必须是布尔值。")


def _parse_int_list_input(value: object, *, field_name: str) -> tuple[int, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        if not value.strip():
            return tuple()
        values = [item.strip() for item in value.split(",")]
        return tuple(_coerce_integer(int(item), field_name=field_name) for item in values if item)
    if isinstance(value, list):
        return tuple(_coerce_integer(item, field_name=field_name) for item in value)
    raise ValueError(f"{field_name} 必须是整数数组或逗号分隔字符串。")


def _validate_known_fields(
    raw_inputs: dict[str, Any], *, field_name: str, allowed_fields: frozenset[str]
) -> None:
    unknown_fields = sorted(key for key in raw_inputs if key not in allowed_fields)
    if unknown_fields:
        joined = ", ".join(unknown_fields)
        raise ValueError(f"{field_name} 包含未知字段：{joined}")


def _parse_manifest_inputs(
    raw_inputs: dict[str, Any], *, field_name: str
) -> DispatchManifestInputs:
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
    _validate_known_fields(
        raw_inputs, field_name=field_name, allowed_fields=_ID_TARGET_INPUT_FIELDS
    )
    return DispatchIdTargets(
        ids=_parse_int_list_input(raw_inputs.get("ids"), field_name=f"{field_name}.ids") or tuple()
    )


def _validate_dispatch_inputs(raw_inputs: dict[str, Any]) -> DispatchInputs:
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
            access_token=_coerce_optional_string(
                baidu_inputs.get("access_token"),
                field_name="inputs.payload.baidu.access_token",
            ),
            app_key=_coerce_optional_string(
                baidu_inputs.get("app_key"), field_name="inputs.payload.baidu.app_key"
            ),
            secret_key=_coerce_optional_string(
                baidu_inputs.get("secret_key"), field_name="inputs.payload.baidu.secret_key"
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


_OMIT = object()


def _prune_empty(value: Any) -> Any:
    if value is None:
        return _OMIT
    if isinstance(value, dict):
        pruned: dict[str, Any] = {}
        for key, item in value.items():
            pruned_item = _prune_empty(item)
            if pruned_item is _OMIT:
                continue
            pruned[key] = pruned_item
        return pruned if pruned else _OMIT
    if isinstance(value, tuple):
        if not value:
            return _OMIT
        return [item for item in value]
    if isinstance(value, list):
        if not value:
            return _OMIT
        return value
    return value


def serialize_dispatch_inputs(
    inputs: DispatchInputs,
    *,
    redact_secrets: bool = False,
) -> dict[str, Any]:
    """把结构化 inputs 转成适合日志/收据的 JSON object。"""

    serialized = _prune_empty(asdict(inputs))
    result = serialized if isinstance(serialized, dict) else {}
    return _redact_dispatch_inputs_mapping(result) if redact_secrets else result


def redact_raw_dispatch_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    """把 workflow_dispatch 原始请求中的敏感字段脱敏。"""

    sanitized = json.loads(json.dumps(raw_payload, ensure_ascii=False))
    inputs = sanitized.get("inputs")
    if not isinstance(inputs, dict):
        return sanitized if isinstance(sanitized, dict) else {}
    wrapped_payload = inputs.get("payload")
    if not isinstance(wrapped_payload, str):
        return sanitized if isinstance(sanitized, dict) else {}
    try:
        decoded_payload = json.loads(wrapped_payload)
    except ValueError:
        return sanitized if isinstance(sanitized, dict) else {}
    if not isinstance(decoded_payload, dict):
        return sanitized if isinstance(sanitized, dict) else {}
    inputs["payload"] = json.dumps(
        _redact_dispatch_inputs_mapping(decoded_payload),
        ensure_ascii=False,
    )
    return sanitized if isinstance(sanitized, dict) else {}


def _redact_dispatch_inputs_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """递归脱敏 dispatch payload 中的百度敏感字段。"""

    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "baidu" and isinstance(value, dict):
            redacted[key] = {
                item_key: (_REDACTED_SECRET if item_key in _SENSITIVE_BAIDU_FIELDS else item_value)
                for item_key, item_value in value.items()
            }
            continue
        if isinstance(value, dict):
            redacted[key] = _redact_dispatch_inputs_mapping(value)
            continue
        if isinstance(value, list):
            redacted[key] = [
                _redact_dispatch_inputs_mapping(item) if isinstance(item, dict) else item
                for item in value
            ]
            continue
        redacted[key] = value
    return redacted


def parse_dispatch_payload(raw_payload: dict[str, Any]) -> DispatchPayload:
    """把 GitHub workflow dispatch 请求解析为强类型对象。"""

    raw_inputs = _coerce_mapping(raw_payload.get("inputs"), field_name="inputs")
    _validate_known_fields(
        raw_inputs, field_name="inputs", allowed_fields=_ALLOWED_INPUT_WRAPPER_FIELDS
    )
    return DispatchPayload(
        ref=_coerce_string(raw_payload.get("ref"), field_name="ref"),
        inputs=_validate_dispatch_inputs(
            _coerce_json_string_mapping(raw_inputs.get("payload"), field_name="inputs.payload")
        ),
    )


def build_job_runner_command(
    *,
    config: WorkflowDispatchCommandConfig,
    payload: DispatchPayload,
    dispatch_inputs_file: Path,
) -> list[str]:
    """把 workflow dispatch 参数翻译成 job runner 命令。"""

    _validate_stage(payload.inputs.request.stage)
    inputs = payload.inputs
    command = [
        str(config.python_executable),
        "-m",
        "rift_audio_pipeline.control_plane.job_runner",
        "--ref",
        payload.ref,
        "--dispatch-inputs-file",
        str(dispatch_inputs_file),
        "--storage-root",
        str(config.storage_root),
        "--output-root",
        str(config.output_root),
        "--temp-root",
        str(config.temp_root),
        "--baidu-remote-root",
        config.baidu_remote_root,
        "--default-mode",
        _coerce_string(inputs.request.mode or config.default_mode, field_name="mode"),
        "--default-game-region",
        _coerce_string(inputs.game.region or config.default_game_region, field_name="game_region"),
        "--control-plane-base-url",
        config.control_plane_base_url,
        "--default-requested-by",
        _coerce_string(
            inputs.metadata.requested_by or config.default_requested_by,
            field_name="requested_by",
        ),
        "--control-plane-timeout-seconds",
        str(config.control_plane_timeout_seconds),
        "--default-log-level",
        _coerce_string(
            inputs.execution.log_level or config.default_log_level,
            field_name="log_level",
        ),
    ]
    if config.log_root is not None:
        command.extend(["--log-root", str(config.log_root)])
    if config.control_plane_bearer_token:
        command.extend(["--control-plane-bearer-token", config.control_plane_bearer_token])
    if config.control_plane_access_client_id:
        command.extend(["--control-plane-access-client-id", config.control_plane_access_client_id])
    if config.control_plane_access_client_secret:
        command.extend(
            [
                "--control-plane-access-client-secret",
                config.control_plane_access_client_secret,
            ]
        )
    return command


def _validate_stage(stage: str | None) -> None:
    if stage not in _REQUEST_STAGE_TO_FLAGS:
        supported = ", ".join(sorted(key for key in _REQUEST_STAGE_TO_FLAGS if key is not None))
        raise ValueError(f"stage 仅支持: {supported}。")
