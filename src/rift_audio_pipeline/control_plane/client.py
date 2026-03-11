"""control plane API 客户端。"""

from __future__ import annotations

import json
from typing import Any

import urllib3

from rift_audio_pipeline.control_plane.errors import ControlPlaneApiError
from rift_audio_pipeline.control_plane.errors import ControlPlaneAuthenticationError
from rift_audio_pipeline.control_plane.errors import ControlPlaneConfigurationError
from rift_audio_pipeline.control_plane.errors import ControlPlaneUnavailableError
from rift_audio_pipeline.control_plane.errors import ControlPlaneResponseValidationError
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig


class ControlPlaneClient:
    """面向本仓的 Worker API HTTP 客户端。"""

    def __init__(
        self,
        config: ControlPlaneConfig,
        *,
        http_client: urllib3.PoolManager | Any | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client or urllib3.PoolManager()

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """发送 JSON 请求并解析 JSON 响应。

        Args:
            method: HTTP 方法。
            path: 相对路径或完整 URL。
            payload: 可选 JSON 请求体。

        Returns:
            dict[str, object]: 响应 JSON 对象。

        Raises:
            ControlPlaneConfigurationError: 配置非法。
            ControlPlaneAuthenticationError: 鉴权失败。
            ControlPlaneApiError: 返回非成功状态码。
            ControlPlaneUnavailableError: 网络失败或响应不可达。
            ControlPlaneResponseValidationError: 响应不是合法 JSON 对象。
        """

        url = self._build_url(path)
        headers = self._build_headers()
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"

        timeout = urllib3.Timeout(total=self._config.timeout_seconds)
        try:
            response = self._http_client.request(
                method=method.upper(),
                url=url,
                body=body,
                headers=headers,
                timeout=timeout,
            )
        except Exception as error:  # noqa: BLE001
            raise ControlPlaneUnavailableError(
                f"control plane API 请求失败：{url}"
            ) from error

        response_payload = self._decode_json_object(response.data)
        if response.status in {401, 403}:
            raise ControlPlaneAuthenticationError(
                status_code=response.status,
                message=f"control plane API 鉴权失败：HTTP {response.status}",
                response_body=response_payload,
            )
        if response.status >= 400:
            raise ControlPlaneApiError(
                status_code=response.status,
                message=f"control plane API 调用失败：HTTP {response.status}",
                response_body=response_payload,
            )
        return response_payload

    def _build_url(self, path: str) -> str:
        """将路径转换为完整 URL。"""

        normalized_path = path.strip()
        if not normalized_path:
            raise ControlPlaneConfigurationError("control plane API path 不能为空。")
        if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
            return normalized_path
        if not normalized_path.startswith("/"):
            normalized_path = f"/{normalized_path}"
        return f"{self._config.base_url}{normalized_path}"

    def _build_headers(self) -> dict[str, str]:
        """构造请求头。"""

        headers = {
            "Accept": "application/json",
            "User-Agent": self._config.user_agent,
        }
        if self._config.bearer_token:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"
        if self._config.access_client_id and self._config.access_client_secret:
            headers["CF-Access-Client-Id"] = self._config.access_client_id
            headers["CF-Access-Client-Secret"] = self._config.access_client_secret
        return headers

    def _decode_json_object(self, payload: bytes | str | None) -> dict[str, object]:
        """解码 JSON 响应对象。"""

        if payload in (None, b"", ""):
            return {}
        if isinstance(payload, bytes):
            text = payload.decode("utf-8")
        else:
            text = payload
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as error:
            raise ControlPlaneResponseValidationError(
                "control plane API 返回了非 JSON 响应。"
            ) from error
        if not isinstance(decoded, dict):
            raise ControlPlaneResponseValidationError(
                "control plane API 返回的 JSON 根对象必须为字典。"
            )
        return decoded
