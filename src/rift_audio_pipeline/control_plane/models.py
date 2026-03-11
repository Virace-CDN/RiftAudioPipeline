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
class PipelineBootstrapRequest:
    """请求 Worker 返回 pipeline 启动参数。"""

    game_region: str
    mode: PipelineMode
    requested_by: str | None = None
    champion_ids: tuple[int, ...] | None = None
    map_ids: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class PipelineBootstrapResponse:
    """Worker 返回的 pipeline 启动参数。"""

    current_version: str
    previous_version: str | None
    current_pair: ControlPlaneManifestPair
    previous_pair: ControlPlaneManifestPair | None = None
    manifest_snapshot_url: str | None = None
    manifest_snapshot_key: str | None = None
    decision_source: str | None = None
    baidu_access_grant: BaiduAccessGrant | None = None


@dataclass(frozen=True, slots=True)
class RunReportRequest:
    """执行端向 Worker 回报运行结果。"""

    run_id: str
    from_version: str | None
    to_version: str
    status: PipelineRunStatus
    summary: dict[str, object]
    uploaded_archives: int = 0
    diff_artifacts_key: str | None = None
    r2_summary_key: str | None = None
    baidu_log_path: str | None = None


@dataclass(frozen=True, slots=True)
class RunHeartbeatRequest:
    """执行端向 Worker 回报运行中心跳。"""

    run_id: str
    status: str
    last_log_at: str
    progress: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class RunReportResponse:
    """Worker 对运行回报的确认结果。"""

    accepted: bool
    persisted_at: str | None = None
    next_head_version: str | None = None


@dataclass(frozen=True, slots=True)
class RunHeartbeatResponse:
    """Worker 对心跳上报的确认结果。"""

    accepted: bool
    persisted_at: str | None = None


@dataclass(frozen=True, slots=True)
class RunLogEventRequest:
    """执行端向 Worker 发送单条实时日志事件。"""

    run_id: str
    event: dict[str, object]


@dataclass(frozen=True, slots=True)
class RunLogEventResponse:
    """Worker 对实时日志事件的确认结果。"""

    accepted: bool
    persisted_at: str | None = None
    next_expected_seq: int | None = None


@dataclass(frozen=True, slots=True)
class RunLogFinalizeRequest:
    """执行端向 Worker 发送终态日志摘要。"""

    run_id: str
    summary: dict[str, object]


@dataclass(frozen=True, slots=True)
class RunLogFinalizeResponse:
    """Worker 对终态日志摘要的确认结果。"""

    accepted: bool
    persisted_at: str | None = None
    worker_status: str | None = None
