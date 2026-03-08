"""Cloudflare 对接层异常定义。"""

from __future__ import annotations


class CloudflareError(RuntimeError):
    """Cloudflare 对接层基类异常。"""


class CloudflareConfigurationError(CloudflareError):
    """Cloudflare 对接层配置非法。"""


class CloudflareApiError(CloudflareError):
    """Worker API 返回非成功状态码。"""

    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        response_body: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class CloudflareAuthenticationError(CloudflareApiError):
    """Worker API 鉴权失败。"""


class CloudflareResponseValidationError(CloudflareError):
    """Worker API 响应结构非法。"""


class CloudflareControlPlaneUnavailableError(CloudflareError):
    """Worker 控制面暂不可用。"""
