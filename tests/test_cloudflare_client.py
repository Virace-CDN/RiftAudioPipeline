"""Cloudflare Worker API 客户端测试。"""

from __future__ import annotations

import json

import pytest

from rift_audio_pipeline.cloudflare.client import CloudflareWorkerClient
from rift_audio_pipeline.cloudflare.errors import CloudflareApiError
from rift_audio_pipeline.cloudflare.errors import CloudflareAuthenticationError
from rift_audio_pipeline.cloudflare.models import CloudflareControlConfig


class _FakeResponse:
    def __init__(self, *, status: int, payload: object) -> None:
        self.status = status
        self.data = json.dumps(payload).encode("utf-8")


class _FakeHttpClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs: object) -> _FakeResponse:
        self.calls.append(kwargs)
        return self.response


def test_request_json_should_send_bearer_and_access_headers() -> None:
    """请求头应包含 Bearer 与 Access service token。"""

    response = _FakeResponse(status=200, payload={"ok": True})
    http_client = _FakeHttpClient(response)
    client = CloudflareWorkerClient(
        CloudflareControlConfig(
            base_url="https://control.example.com",
            bearer_token="worker-token",
            access_client_id="client-id",
            access_client_secret="client-secret",
        ),
        http_client=http_client,
    )

    payload = client.request_json("POST", "/api/pipeline/bootstrap", payload={"mode": "remote"})

    assert payload == {"ok": True}
    headers = http_client.calls[0]["headers"]
    assert headers["Authorization"] == "Bearer worker-token"
    assert headers["CF-Access-Client-Id"] == "client-id"
    assert headers["CF-Access-Client-Secret"] == "client-secret"


def test_request_json_should_raise_auth_error_on_403() -> None:
    """403 应映射为鉴权失败。"""

    client = CloudflareWorkerClient(
        CloudflareControlConfig(base_url="https://control.example.com"),
        http_client=_FakeHttpClient(_FakeResponse(status=403, payload={"error": "forbidden"})),
    )

    with pytest.raises(CloudflareAuthenticationError):
        client.request_json("GET", "/api/pipeline/bootstrap")


def test_request_json_should_raise_api_error_on_500() -> None:
    """5xx 应映射为通用 API 失败。"""

    client = CloudflareWorkerClient(
        CloudflareControlConfig(base_url="https://control.example.com"),
        http_client=_FakeHttpClient(_FakeResponse(status=500, payload={"error": "boom"})),
    )

    with pytest.raises(CloudflareApiError):
        client.request_json("GET", "/api/pipeline/bootstrap")
