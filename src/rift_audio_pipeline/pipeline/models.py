"""Pipeline 编排层共享数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Mapping

PIPELINE_EVENT_SCHEMA_VERSION = 1
PIPELINE_SUMMARY_SCHEMA_VERSION = 1
PIPELINE_DECISION_SCHEMA_VERSION = 1
PIPELINE_ARTIFACTS_SCHEMA_VERSION = 1
PIPELINE_ERROR_SCHEMA_VERSION = 1
PIPELINE_PENDING_LOG_UPLOAD_SCHEMA_VERSION = 1


class PipelineMode(str, Enum):
    """Pipeline 运行模式。"""

    LOCAL = "local"
    REMOTE = "remote"


class PipelineStage(str, Enum):
    """Pipeline 阶段枚举。"""

    INIT = "init"
    LOAD_REMOTE_INDEX = "load_remote_index"
    RESOLVE_MANIFEST_PAIR = "resolve_manifest_pair"
    DIFF = "diff"
    BUILD_TARGETS = "build_targets"
    UPDATE = "update"
    EXTRACT = "extract"
    MAPPING = "mapping"
    PACK = "pack"
    UPLOAD = "upload"
    FINALIZE = "finalize"


class PipelineRunStatus(str, Enum):
    """Pipeline 运行状态枚举。"""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PipelineRunConfig:
    """Pipeline 运行配置。

    Args:
        mode: 运行模式。
        game_region: 目标语言/游戏区服标识，如 `zh_CN`。
        output_root: 主输出根目录。
        temp_root: 临时目录根。
        log_root: 日志目录根。
        run_id: 本轮运行 ID；为空时按当前时间自动生成。
        baidu_remote_root: 百度网盘远端根目录。
        remote_live_region: remote live 区服，如 `EUW`。
        baidu_app_key: 百度 app key。
        baidu_secret_key: 百度 secret key。
        baidu_refresh_token: 百度 refresh token。
        current_version: 当前目标版本。
        current_lcu_manifest_url: 当前版 LCU manifest URL。
        current_game_manifest_url: 当前版 GAME manifest URL。
        previous_version: 上一次成功版本。
        previous_lcu_manifest_url: 上一版 LCU manifest URL。
        previous_game_manifest_url: 上一版 GAME manifest URL。
        previous_match_mode: 上一版 manifest pair 匹配模式。
        previous_match_reason: 上一版 manifest pair 匹配原因。
        relay_socket_path: relay socket 路径。
        state_db_path: 本地状态库路径。
        control_plane_base_url: 控制面基础 URL。
        control_plane_bearer_token: 控制面 Bearer token。
        control_plane_access_client_id: Access service token client id。
        control_plane_access_client_secret: Access service token client secret。
        control_plane_timeout_seconds: 控制面超时秒数。
        control_plane_requested_by: 启动请求来源。
        game_path: 本地模式游戏目录。
        wwiser_path: 映射阶段 WWISER 路径。
        force_update: 是否强制更新。
        include_champions: 是否包含英雄。
        include_maps: 是否包含地图。
        champion_ids: 指定英雄 ID。
        map_ids: 指定地图 ID。
        run_update: 是否执行 update。
        run_extract: 是否执行 extract。
        run_mapping: 是否执行 mapping。
        integrate_data: 是否输出 integrated mapping 数据。
        cleanup_remote: 是否清理远端中间产物。
        dev_mode: 是否启用开发模式。
        max_workers: 最大工作线程数。
        download_retry_attempts: 下载类错误重试次数。
        entity_retry_attempts: 单实体完整流程重试次数。
        log_level: 上游 app 日志级别。
    """

    mode: PipelineMode
    game_region: str
    output_root: Path
    temp_root: Path
    log_root: Path
    baidu_remote_root: str
    run_id: str | None = None
    remote_live_region: str | None = None
    baidu_app_key: str | None = None
    baidu_secret_key: str | None = None
    baidu_refresh_token: str | None = None
    current_version: str | None = None
    current_lcu_manifest_url: str | None = None
    current_game_manifest_url: str | None = None
    previous_version: str | None = None
    previous_lcu_manifest_url: str | None = None
    previous_game_manifest_url: str | None = None
    previous_match_mode: str | None = None
    previous_match_reason: str | None = None
    relay_socket_path: Path | None = None
    state_db_path: Path | None = None
    control_plane_base_url: str | None = None
    control_plane_bearer_token: str | None = None
    control_plane_access_client_id: str | None = None
    control_plane_access_client_secret: str | None = None
    control_plane_timeout_seconds: float = 30.0
    control_plane_requested_by: str | None = None
    game_path: Path | None = None
    wwiser_path: Path | None = None
    force_update: bool = False
    include_champions: bool = True
    include_maps: bool = True
    champion_ids: tuple[int, ...] | None = None
    map_ids: tuple[int, ...] | None = None
    run_update: bool = True
    run_extract: bool = True
    run_mapping: bool = False
    integrate_data: bool = False
    cleanup_remote: bool = True
    dev_mode: bool = False
    max_workers: int = 4
    download_retry_attempts: int = 3
    entity_retry_attempts: int = 3
    log_level: str = "INFO"


@dataclass(frozen=True, slots=True)
class ManifestPairRef:
    """面向 orchestrator 的最小 manifest pair 引用。"""

    version: str
    lcu_manifest_url: str
    game_manifest_url: str
    match_mode: str
    match_reason: str


@dataclass(frozen=True, slots=True)
class ProcessingTarget:
    """待处理实体描述。"""

    entity_type: str
    entity_id: int | None = None
    alias: str | None = None
    name: str | None = None
    source_wads: tuple[str, ...] = tuple()
    decision_reason: str = ""


@dataclass(frozen=True, slots=True)
class EntityArtifacts:
    """单实体产物集合。"""

    entity_type: str
    entity_id: int
    audio_output_paths: tuple[Path, ...] = tuple()
    mapping_output_path: Path | None = None
    archive_paths: tuple[Path, ...] = tuple()


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """结构化阶段事件。"""

    run_id: str
    stage: PipelineStage
    event_type: str
    message: str
    payload: Mapping[str, Any]
    created_at: str
    seq: int | None = None
    source: str = "pipeline"
    level: str = "INFO"
    status_hint: str | None = None
    thread_name: str | None = None
    process_id: int | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    entity_alias: str | None = None
    attempt: int | None = None
    operation: str | None = None
    code_file: str | None = None
    code_function: str | None = None
    code_line: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    exception_module: str | None = None
    traceback: str | None = None
    cause_chain: tuple[Mapping[str, str], ...] = tuple()
    schema_version: int = PIPELINE_EVENT_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PipelineLogTerminalSummary:
    """运行结束时发给控制面的终态摘要。"""

    run_id: str
    finished_at: str
    final_status: str
    final_stage: str
    last_seq: int
    processed_targets: int
    succeeded_targets: int
    failed_targets: int
    uploaded_archives: int
    raw_log_bundle_ready: bool
    raw_log_local_dir: str
    raw_log_remote_path: str | None
    summary: Mapping[str, Any]
    error_brief: Mapping[str, Any] | None = None
    schema_version: int = PIPELINE_SUMMARY_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PipelineRunSummary:
    """Pipeline 运行摘要。"""

    run_id: str
    mode: PipelineMode
    version: str | None
    status: PipelineRunStatus
    processed_targets: int
    succeeded_targets: int
    failed_targets: int
    uploaded_archives: int
    pending_manifest_sync_entries: int
    pending_log_upload_entries: int
    log_dir: Path
    schema_version: int = PIPELINE_SUMMARY_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PipelineDecisionSnapshot:
    """`decision.json` 稳定落盘结构。"""

    run_id: str
    target_source: str
    target_count: int
    current_version: str | None = None
    previous_version: str | None = None
    selected_champion_ids: tuple[int, ...] = tuple()
    selected_map_ids: tuple[int, ...] = tuple()
    candidates: tuple[Mapping[str, Any], ...] = tuple()
    resolved_targets: tuple[ProcessingTarget, ...] = tuple()
    remote_execution_skipped: bool = False
    reason: str | None = None
    schema_version: int = PIPELINE_DECISION_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PipelineArtifactRecord:
    """单实体落盘产物记录。"""

    entity_type: str
    entity_id: int
    audio_output_paths: tuple[Path, ...] = tuple()
    mapping_output_path: Path | None = None
    archive_paths: tuple[Path, ...] = tuple()


@dataclass(frozen=True, slots=True)
class PipelineArtifactsSnapshot:
    """`artifacts.json` 稳定落盘结构。"""

    run_id: str
    version: str | None
    artifact_count: int
    archive_count: int
    artifacts: tuple[PipelineArtifactRecord, ...] = tuple()
    archives: tuple[Path, ...] = tuple()
    schema_version: int = PIPELINE_ARTIFACTS_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PipelineErrorSnapshot:
    """`error.json` 稳定落盘结构。"""

    run_id: str
    stage: PipelineStage
    error_type: str
    error_message: str
    payload: Mapping[str, Any]
    created_at: str
    thread_name: str | None = None
    process_id: int | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    entity_alias: str | None = None
    attempt: int | None = None
    operation: str | None = None
    code_file: str | None = None
    code_function: str | None = None
    code_line: int | None = None
    exception_module: str | None = None
    traceback: str | None = None
    cause_chain: tuple[Mapping[str, str], ...] = tuple()
    schema_version: int = PIPELINE_ERROR_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class PendingLogUploadEntry:
    """日志补传队列条目。"""

    log_dir: str
    remote_root: str
    error_message: str
    enqueued_at: str
    run_id: str | None = None
    schema_version: int = PIPELINE_PENDING_LOG_UPLOAD_SCHEMA_VERSION
