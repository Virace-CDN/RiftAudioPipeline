"""Cloudflare Worker 控制面高层服务。"""

from __future__ import annotations

from dataclasses import asdict

from rift_audio_pipeline.cloudflare.client import CloudflareWorkerClient
from rift_audio_pipeline.cloudflare.errors import CloudflareResponseValidationError
from rift_audio_pipeline.cloudflare.models import BaiduAccessGrant
from rift_audio_pipeline.cloudflare.models import CloudflareManifestPair
from rift_audio_pipeline.cloudflare.models import PipelineBootstrapRequest
from rift_audio_pipeline.cloudflare.models import PipelineBootstrapResponse
from rift_audio_pipeline.cloudflare.models import RunHeartbeatRequest
from rift_audio_pipeline.cloudflare.models import RunHeartbeatResponse
from rift_audio_pipeline.cloudflare.models import RunReportRequest
from rift_audio_pipeline.cloudflare.models import RunReportResponse


class CloudflareControlService:
    """面向 orchestrator 的 Cloudflare 控制面服务。"""

    def __init__(self, client: CloudflareWorkerClient) -> None:
        self._client = client

    def get_pipeline_bootstrap(
        self,
        request: PipelineBootstrapRequest,
    ) -> PipelineBootstrapResponse:
        """请求 Worker 返回 pipeline 启动参数。"""

        response_payload = self._client.request_json(
            "POST",
            "/api/pipeline/bootstrap",
            payload=_serialize_payload(asdict(request)),
        )
        current_version = _require_str(response_payload, "current_version")
        current_pair_payload = _require_dict(response_payload, "current_pair")
        previous_pair_payload = _optional_dict(response_payload, "previous_pair")
        baidu_access_payload = _optional_dict(response_payload, "baidu_access_grant")
        return PipelineBootstrapResponse(
            current_version=current_version,
            previous_version=_optional_str(response_payload, "previous_version"),
            current_pair=_parse_manifest_pair(current_pair_payload),
            previous_pair=(
                _parse_manifest_pair(previous_pair_payload)
                if previous_pair_payload is not None
                else None
            ),
            manifest_snapshot_url=_optional_str(response_payload, "manifest_snapshot_url"),
            manifest_snapshot_key=_optional_str(response_payload, "manifest_snapshot_key"),
            decision_source=_optional_str(response_payload, "decision_source"),
            baidu_access_grant=(
                _parse_baidu_access_grant(baidu_access_payload)
                if baidu_access_payload is not None
                else None
            ),
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
            raise CloudflareResponseValidationError(
                "Cloudflare Worker run report 响应缺少 accepted 布尔值。"
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
            raise CloudflareResponseValidationError(
                "Cloudflare Worker heartbeat 响应缺少 accepted 布尔值。"
            )
        return RunHeartbeatResponse(
            accepted=accepted,
            persisted_at=_optional_str(response_payload, "persisted_at"),
        )


def _parse_manifest_pair(payload: dict[str, object]) -> CloudflareManifestPair:
    """解析 manifest pair 响应。"""

    return CloudflareManifestPair(
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
        if isinstance(value, tuple):
            serialized[key] = list(value)
        elif isinstance(value, dict):
            serialized[key] = _serialize_payload(value)
        else:
            serialized[key] = value
    return serialized


def _require_str(payload: dict[str, object], key: str) -> str:
    """读取必填字符串字段。"""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CloudflareResponseValidationError(f"Cloudflare Worker 响应缺少有效字符串字段：{key}")
    return value


def _optional_str(payload: dict[str, object], key: str) -> str | None:
    """读取可选字符串字段。"""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CloudflareResponseValidationError(
            f"Cloudflare Worker 响应字段必须为字符串或 null：{key}"
        )
    return value


def _require_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    """读取必填对象字段。"""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise CloudflareResponseValidationError(f"Cloudflare Worker 响应缺少有效对象字段：{key}")
    return value


def _optional_dict(payload: dict[str, object], key: str) -> dict[str, object] | None:
    """读取可选对象字段。"""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise CloudflareResponseValidationError(
            f"Cloudflare Worker 响应字段必须为对象或 null：{key}"
        )
    return value
