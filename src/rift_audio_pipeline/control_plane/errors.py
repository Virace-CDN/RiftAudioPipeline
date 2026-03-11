"""control plane 对接层异常定义。"""

from __future__ import annotations


class ControlPlaneError(RuntimeError):
    """control plane 对接层基类异常。"""


class ControlPlaneConfigurationError(ControlPlaneError):
    """control plane 对接层配置非法。"""


class ControlPlaneApiError(ControlPlaneError):
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


class ControlPlaneAuthenticationError(ControlPlaneApiError):
    """Worker API 鉴权失败。"""


class ControlPlaneResponseValidationError(ControlPlaneError):
    """Worker API 响应结构非法。"""


class ControlPlaneUnavailableError(ControlPlaneError):
    """Worker 控制面暂不可用。"""
