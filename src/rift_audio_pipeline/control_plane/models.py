"""control plane 对接层数据模型。"""

from __future__ import annotations

from dataclasses import dataclass

from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunStatus


@dataclass(frozen=True, slots=True)
class ControlPlaneConfig:
    """control plane 控制面访问配置。

    Args:
        base_url: Worker 基础地址。
        bearer_token: 可选 Bearer token。
        access_client_id: 可选 Access service token client id。
        access_client_secret: 可选 Access service token client secret。
        timeout_seconds: 请求超时秒数。
        user_agent: 自定义 User-Agent。
    """

    base_url: str
    bearer_token: str | None = None
    access_client_id: str | None = None
    access_client_secret: str | None = None
    timeout_seconds: float = 30.0
    user_agent: str = "rift-audio-pipeline/control-plane"

    def __post_init__(self) -> None:
        normalized_url = self.base_url.rstrip("/")
        if not normalized_url:
            raise ValueError("control plane base_url 不能为空。")
        if bool(self.access_client_id) != bool(self.access_client_secret):
            raise ValueError(
                "Access 鉴权必须同时提供 access_client_id 与 access_client_secret。"
            )
        if self.timeout_seconds <= 0:
            raise ValueError("control plane timeout_seconds 必须大于 0。")
        object.__setattr__(self, "base_url", normalized_url)


@dataclass(frozen=True, slots=True)
class ControlPlaneManifestPair:
    """Worker 返回的 manifest pair。"""

    version: str
    lcu_manifest_url: str
    game_manifest_url: str
    match_mode: str | None = None
    match_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BaiduAccessGrant:
    """Worker 下发的百度访问授权。"""

    app_key: str | None = None
    secret_key: str | None = None
    refresh_token: str | None = None
    access_token: str | None = None
    expires_at: str | None = None
    token_source: str | None = None


@dataclass(frozen=True, slots=True)
class RunBootstrapRequest:
    """执行端向 Worker 发送任务启动通知。"""

    run_id: str
    started_at: str


@dataclass(frozen=True, slots=True)
class RunReportRequest:
    """执行端向 Worker 回报运行结果。"""

    run_id: str
    status: PipelineRunStatus
    changes: tuple[dict[str, object], ...] = tuple()
    finished_at: str | None = None


@dataclass(frozen=True, slots=True)
class RunHeartbeatRequest:
    """执行端向 Worker 回报运行中心跳。"""

    run_id: str
    status: str
    last_log_at: str
    progress: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class RunLogEventRequest:
    """执行端向 Worker 发送单条实时日志事件。"""

    run_id: str
    event: dict[str, object]


@dataclass(frozen=True, slots=True)
class RunLogFinalizeRequest:
    """执行端向 Worker 发送终态日志摘要。"""

    run_id: str
    summary: dict[str, object]

