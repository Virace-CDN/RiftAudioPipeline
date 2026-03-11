"""control plane 控制面高层服务。"""

from __future__ import annotations

from dataclasses import asdict

from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_audio_pipeline.control_plane.errors import ControlPlaneResponseValidationError
from rift_audio_pipeline.control_plane.models import BaiduAccessGrant
from rift_audio_pipeline.control_plane.models import ControlPlaneManifestPair
from rift_audio_pipeline.control_plane.models import RunBootstrapRequest
from rift_audio_pipeline.control_plane.models import RunBootstrapResponse
from rift_audio_pipeline.control_plane.models import RunHeartbeatRequest
from rift_audio_pipeline.control_plane.models import RunHeartbeatResponse
from rift_audio_pipeline.control_plane.models import RunLogEventRequest
from rift_audio_pipeline.control_plane.models import RunLogEventResponse
from rift_audio_pipeline.control_plane.models import RunLogFinalizeRequest
from rift_audio_pipeline.control_plane.models import RunLogFinalizeResponse
from rift_audio_pipeline.control_plane.models import RunReportRequest
from rift_audio_pipeline.control_plane.models import RunReportResponse


class ControlPlaneService:
    """面向 orchestrator 的 control plane 服务。"""

    def __init__(self, client: ControlPlaneClient) -> None:
        self._client = client

    def notify_pipeline_run_started(
        self,
        request: RunBootstrapRequest,
    ) -> RunBootstrapResponse:
        """向 Worker 发送任务启动通知。"""

        response_payload = self._client.request_json(
            "POST",
            "/api/pipeline/bootstrap",
            payload=_serialize_payload(asdict(request)),
        )
        accepted = response_payload.get("accepted")
        if not isinstance(accepted, bool):
            raise ControlPlaneResponseValidationError(
                "control plane bootstrap 响应缺少 accepted 布尔值。"
            )
        return RunBootstrapResponse(
            accepted=accepted,
            persisted_at=_optional_str(response_payload, "persisted_at"),
        )

    def report_pipeline_run_result(self, request: RunReportRequest) -> RunReportResponse:
        """向 Worker 回报执行端运行结果。"""

        response_payload = self._client.request_json(
            "POST",
            f"/api/pipeline/runs/{request.run_id}/report",
            payload=_serialize_payload(asdict(request)),
        )
        accepted = response_payload.get("accepted")
        if not isinstance(accepted, bool):
            raise ControlPlaneResponseValidationError(
                "control plane run report 响应缺少 accepted 布尔值。"
            )
        return RunReportResponse(
            accepted=accepted,
            persisted_at=_optional_str(response_payload, "persisted_at"),
            next_head_version=_optional_str(response_payload, "next_head_version"),
        )

    def report_pipeline_run_heartbeat(self, request: RunHeartbeatRequest) -> RunHeartbeatResponse:
        """向 Worker 回报执行端运行中心跳。"""

        response_payload = self._client.request_json(
            "POST",
            f"/api/pipeline/runs/{request.run_id}/heartbeat",
            payload=_serialize_payload(asdict(request)),
        )
        accepted = response_payload.get("accepted")
        if not isinstance(accepted, bool):
            raise ControlPlaneResponseValidationError(
                "control plane heartbeat 响应缺少 accepted 布尔值。"
            )
        return RunHeartbeatResponse(
            accepted=accepted,
            persisted_at=_optional_str(response_payload, "persisted_at"),
        )

    def report_pipeline_run_log_event(self, request: RunLogEventRequest) -> RunLogEventResponse:
        """向 Worker 发送单条实时运行日志。"""

        response_payload = self._client.request_json(
            "POST",
            f"/api/pipeline/runs/{request.run_id}/logs",
            payload=_serialize_payload(asdict(request)),
        )
        accepted = response_payload.get("accepted")
        if not isinstance(accepted, bool):
            raise ControlPlaneResponseValidationError(
                "control plane log event 响应缺少 accepted 布尔值。"
            )
        return RunLogEventResponse(
            accepted=accepted,
            persisted_at=_optional_str(response_payload, "persisted_at"),
            next_expected_seq=_optional_int(response_payload, "next_expected_seq"),
        )

    def finalize_pipeline_run_logs(
        self,
        request: RunLogFinalizeRequest,
    ) -> RunLogFinalizeResponse:
        """向 Worker 发送运行终态日志摘要。"""

        response_payload = self._client.request_json(
            "POST",
            f"/api/pipeline/runs/{request.run_id}/logs/finalize",
            payload=_serialize_payload(asdict(request)),
        )
        accepted = response_payload.get("accepted")
        if not isinstance(accepted, bool):
            raise ControlPlaneResponseValidationError(
                "control plane log finalize 响应缺少 accepted 布尔值。"
            )
        return RunLogFinalizeResponse(
            accepted=accepted,
            persisted_at=_optional_str(response_payload, "persisted_at"),
            worker_status=_optional_str(response_payload, "worker_status"),
        )


def _parse_manifest_pair(payload: dict[str, object]) -> ControlPlaneManifestPair:
    """解析 manifest pair 响应。"""

    return ControlPlaneManifestPair(
        version=_require_str(payload, "version"),
        lcu_manifest_url=_require_str(payload, "lcu_manifest_url"),
        game_manifest_url=_require_str(payload, "game_manifest_url"),
        match_mode=_optional_str(payload, "match_mode"),
        match_reason=_optional_str(payload, "match_reason"),
    )


def _parse_baidu_access_grant(payload: dict[str, object]) -> BaiduAccessGrant:
    """解析百度访问授权响应。"""

    return BaiduAccessGrant(
        app_key=_optional_str(payload, "app_key"),
        secret_key=_optional_str(payload, "secret_key"),
        refresh_token=_optional_str(payload, "refresh_token"),
        access_token=_optional_str(payload, "access_token"),
        expires_at=_optional_str(payload, "expires_at"),
        token_source=_optional_str(payload, "token_source"),
    )


def _serialize_payload(payload: dict[str, object]) -> dict[str, object]:
    """移除 `None` 并把 tuple 转为 list。"""

    serialized: dict[str, object] = {}
    for key, value in payload.items():
        if value is None:
            continue
        serialized[key] = _serialize_value(value)
    return serialized


def _serialize_value(value: object) -> object:
    """递归序列化嵌套 tuple/list/dict。"""

    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serialize_value(item)
            for key, item in value.items()
            if item is not None
        }
    return value


def _require_str(payload: dict[str, object], key: str) -> str:
    """读取必填字符串字段。"""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneResponseValidationError(f"control plane 响应缺少有效字符串字段：{key}")
    return value


def _optional_str(payload: dict[str, object], key: str) -> str | None:
    """读取可选字符串字段。"""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ControlPlaneResponseValidationError(
            f"control plane 响应字段必须为字符串或 null：{key}"
        )
    return value


def _optional_int(payload: dict[str, object], key: str) -> int | None:
    """读取可选整数值字段。"""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ControlPlaneResponseValidationError(f"control plane 响应字段必须为整数或 null：{key}")
    return value


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    """读取必填对象字段。"""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise ControlPlaneResponseValidationError(f"control plane 响应缺少有效对象字段：{key}")
    return value


def _optional_dict(payload: dict[str, object], key: str) -> dict[str, object] | None:
    """读取可选对象字段。"""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ControlPlaneResponseValidationError(
            f"control plane 响应字段必须为对象或 null：{key}"
        )
    return value
