"""Pipeline 总控编排入口。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import json
import re

from rift_audio_pipeline.baidu import BaiduCredentials
from rift_audio_pipeline.baidu import BaiduPanClient
from rift_audio_pipeline.baidu import resolve_token_store
from rift_audio_pipeline.cloudflare.client import CloudflareWorkerClient
from rift_audio_pipeline.cloudflare.models import CloudflareControlConfig
from rift_audio_pipeline.cloudflare.models import PipelineBootstrapRequest
from rift_audio_pipeline.cloudflare.models import RunHeartbeatRequest
from rift_audio_pipeline.cloudflare.models import RunReportRequest
from rift_audio_pipeline.cloudflare.service import CloudflareControlService
from rift_audio_pipeline.packer import pack_champion
from rift_audio_pipeline.pipeline.local import run_local_pipeline
from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.logging import enqueue_pending_log_upload
from rift_audio_pipeline.pipeline.logging import finalize_run_logging
from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.logging import record_error_snapshot
from rift_audio_pipeline.pipeline.logging import upload_run_logs
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineArtifactRecord
from rift_audio_pipeline.pipeline.models import PipelineArtifactsSnapshot
from rift_audio_pipeline.pipeline.models import PipelineDecisionSnapshot
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.models import PipelineStage
from rift_audio_pipeline.pipeline.models import ProcessingTarget
from rift_audio_pipeline.pipeline.remote import build_remote_app_context
from rift_audio_pipeline.pipeline.remote import run_remote_pipeline
import rift_audio_pipeline.upload as upload_module
from rift_audio_pipeline.upload import UploadConfig

CHAMPION_WAD_PATTERN = re.compile(r"/champions/(?P<alias>[^/]+)\.wad\.client$", re.IGNORECASE)
CHAMPION_BIN_PATTERN = re.compile(r"/characters/(?P<alias>[^/]+)/", re.IGNORECASE)
MAP_WAD_PATTERN = re.compile(r"/maps/shipping/(?P<map_name>map\d+|common)/", re.IGNORECASE)
MAP_BIN_PATTERN = re.compile(r"/data/maps/shipping/(?P<map_name>map\d+|common)/", re.IGNORECASE)


def run_pipeline(config: PipelineRunConfig) -> PipelineRunSummary:
    """运行 pipeline 总控主链。

    Args:
        config: Pipeline 运行配置。

    Returns:
        PipelineRunSummary: 本次运行摘要。
    """

    log_ctx = initialize_run_logging(config)
    runtime_config, bootstrapped_pair = _bootstrap_control_plane(config=config)
    resolved_version: str | None = None
    uploaded_archives = 0
    pending_log_upload_entries = 0
    manifest_queue_file = config.output_root / "state" / "pending_manifest_sync_queue.json"
    decision_payload: PipelineDecisionSnapshot | None = None
    active_stage = PipelineStage.INIT

    emit_event(
        log_ctx,
        PipelineEvent(
            run_id=log_ctx.run_id,
            stage=PipelineStage.INIT,
            event_type="run_started",
            message="pipeline 开始运行",
            payload={"mode": runtime_config.mode.value},
            created_at=datetime.now().astimezone().isoformat(),
        ),
    )
    _report_control_plane_heartbeat(
        config=runtime_config,
        run_id=log_ctx.run_id,
        status="running",
        stage=PipelineStage.INIT,
        summary=None,
    )

    try:
        active_stage = PipelineStage.LOAD_REMOTE_INDEX
        _retry_pending_manifest_sync_queue_if_possible(
            config=runtime_config, queue_file=manifest_queue_file
        )

        artifacts: list[EntityArtifacts]
        artifact_records: list[PipelineArtifactRecord] = []
        targets: tuple[ProcessingTarget, ...] = tuple()
        if runtime_config.mode is PipelineMode.REMOTE:
            active_stage = PipelineStage.RESOLVE_MANIFEST_PAIR
            pair = (
                _resolve_current_manifest_pair(runtime_config)
                or bootstrapped_pair
                or resolve_remote_manifest_pair(runtime_config)
            )
            resolved_version = pair.version
            active_stage = PipelineStage.BUILD_TARGETS
            targets, effective_config, decision_payload = _resolve_remote_targets(
                config=runtime_config,
                run_id=log_ctx.run_id,
                current_pair=pair,
            )
            emit_event(
                log_ctx,
                PipelineEvent(
                    run_id=log_ctx.run_id,
                    stage=PipelineStage.BUILD_TARGETS,
                    event_type="targets_built" if targets else "targets_skipped",
                    message="processing targets 已生成"
                    if targets
                    else "未解析到 processing targets，本轮跳过 remote 执行",
                    payload={
                        "targets": _serialize_targets(targets),
                        "decision": asdict(decision_payload),
                    },
                    created_at=datetime.now().astimezone().isoformat(),
                ),
            )
            active_stage = PipelineStage.EXTRACT if config.run_extract else PipelineStage.UPDATE
            artifacts = (
                run_remote_pipeline(config=effective_config, pair=pair, log_ctx=log_ctx)
                if targets
                else []
            )
        else:
            active_stage = PipelineStage.BUILD_TARGETS
            targets = build_processing_targets(
                config=runtime_config,
                previous_version=None,
                current_pair=None,
            )
            effective_config = _apply_targets_to_config(config=runtime_config, targets=targets)
            decision_payload = PipelineDecisionSnapshot(
                run_id=log_ctx.run_id,
                target_source="local_runtime_config",
                target_count=len(targets),
                selected_champion_ids=effective_config.champion_ids or tuple(),
                selected_map_ids=effective_config.map_ids or tuple(),
                resolved_targets=targets,
            )
            active_stage = PipelineStage.EXTRACT if config.run_extract else PipelineStage.UPDATE
            artifacts = run_local_pipeline(config=effective_config, log_ctx=log_ctx)
            resolved_version = _resolve_local_version(config=runtime_config)

        all_archives: list[Path] = []
        active_stage = PipelineStage.PACK
        for artifact in artifacts:
            archives = handle_entity_artifacts(
                config=runtime_config,
                artifact=artifact,
                version=resolved_version,
            )
            all_archives.extend(archives)
            artifact_records.append(
                PipelineArtifactRecord(
                    entity_type=artifact.entity_type,
                    entity_id=artifact.entity_id,
                    audio_output_paths=artifact.audio_output_paths,
                    mapping_output_path=artifact.mapping_output_path,
                    archive_paths=archives,
                )
            )

        if all_archives and resolved_version is not None:
            active_stage = PipelineStage.UPLOAD
            _upload_archives_for_run(
                config=runtime_config,
                archives=tuple(all_archives),
                version=resolved_version,
            )
            uploaded_archives = len(all_archives)

        summary = PipelineRunSummary(
            run_id=log_ctx.run_id,
            mode=runtime_config.mode,
            version=resolved_version,
            status=PipelineRunStatus.SUCCESS,
            processed_targets=len(targets) if targets else len(artifacts),
            succeeded_targets=len(artifacts),
            failed_targets=max((len(targets) if targets else len(artifacts)) - len(artifacts), 0),
            uploaded_archives=uploaded_archives,
            pending_manifest_sync_entries=_count_json_list_entries(manifest_queue_file),
            pending_log_upload_entries=0,
            log_dir=log_ctx.log_dir,
        )
        active_stage = PipelineStage.FINALIZE
        finalize_run_logging(
            log_ctx,
            summary,
            decision_payload=decision_payload,
            artifacts_payload=PipelineArtifactsSnapshot(
                run_id=log_ctx.run_id,
                version=resolved_version,
                artifact_count=len(artifacts),
                archive_count=len(all_archives),
                artifacts=tuple(artifact_records),
                archives=tuple(all_archives),
            ),
        )
        _report_control_plane_heartbeat(
            config=runtime_config,
            run_id=log_ctx.run_id,
            status="success",
            stage=PipelineStage.FINALIZE,
            summary=summary,
        )
    except Exception as error:  # noqa: BLE001
        record_error_snapshot(
            log_ctx,
            active_stage,
            error,
            payload={
                "resolved_version": resolved_version,
                "decision": asdict(decision_payload) if decision_payload is not None else None,
            },
        )
        summary = PipelineRunSummary(
            run_id=log_ctx.run_id,
            mode=runtime_config.mode,
            version=resolved_version,
            status=PipelineRunStatus.FAILED,
            processed_targets=0,
            succeeded_targets=0,
            failed_targets=1,
            uploaded_archives=uploaded_archives,
            pending_manifest_sync_entries=_count_json_list_entries(manifest_queue_file),
            pending_log_upload_entries=0,
            log_dir=log_ctx.log_dir,
        )
        finalize_run_logging(log_ctx, summary, decision_payload=decision_payload)
        _report_control_plane_heartbeat(
            config=runtime_config,
            run_id=log_ctx.run_id,
            status="failed",
            stage=active_stage,
            summary=summary,
        )

    if _has_baidu_credentials(runtime_config):
        try:
            client = _create_baidu_client(config=runtime_config)
            try:
                upload_run_logs(log_ctx, runtime_config, client)
            finally:
                client.close()
        except Exception as error:  # noqa: BLE001
            enqueue_pending_log_upload(runtime_config, log_ctx.log_dir, error_message=str(error))
            pending_log_upload_entries = _count_json_list_entries(
                runtime_config.output_root / "state" / "pending_log_upload_queue.json"
            )
            summary = PipelineRunSummary(
                run_id=summary.run_id,
                mode=summary.mode,
                version=summary.version,
                status=summary.status,
                processed_targets=summary.processed_targets,
                succeeded_targets=summary.succeeded_targets,
                failed_targets=summary.failed_targets,
                uploaded_archives=summary.uploaded_archives,
                pending_manifest_sync_entries=summary.pending_manifest_sync_entries,
                pending_log_upload_entries=pending_log_upload_entries,
                log_dir=summary.log_dir,
            )
            finalize_run_logging(log_ctx, summary)

    _report_control_plane_run_result(
        config=runtime_config,
        summary=summary,
        from_version=runtime_config.previous_version,
        to_version=summary.version,
        baidu_log_path=_build_baidu_log_remote_path(config=runtime_config, log_ctx=log_ctx),
    )
    return summary


def _resolve_remote_targets(
    config: PipelineRunConfig,
    *,
    run_id: str,
    current_pair: ManifestPairRef,
) -> tuple[tuple[ProcessingTarget, ...], PipelineRunConfig, PipelineDecisionSnapshot]:
    """为 remote 主流程解析本轮目标，并返回收敛后的运行配置。"""

    explicit_targets = _build_targets_from_explicit_ids(config)
    if explicit_targets:
        effective_config = _apply_targets_to_config(config=config, targets=explicit_targets)
        return (
            explicit_targets,
            effective_config,
            PipelineDecisionSnapshot(
                run_id=run_id,
                target_source="explicit_ids",
                current_version=current_pair.version,
                previous_version=None,
                target_count=len(explicit_targets),
                selected_champion_ids=effective_config.champion_ids or tuple(),
                selected_map_ids=effective_config.map_ids or tuple(),
                candidates=tuple(),
                resolved_targets=explicit_targets,
            ),
        )

    safe_config = replace(config, include_champions=False, include_maps=False)
    previous_pair = _resolve_previous_manifest_pair(config=config)
    if previous_pair is not None:
        manifest_report = build_manifest_diff_report(
            config,
            previous_pair=previous_pair,
            current_pair=current_pair,
            include_unchanged=False,
        )
        inferred_targets = build_processing_targets(
            config=config,
            previous_version=previous_pair.version,
            current_pair=current_pair,
            manifest_report=manifest_report,
        )
        resolved_targets = _resolve_remote_target_ids(
            config=config,
            current_pair=current_pair,
            targets=inferred_targets,
        )
        effective_config = _apply_targets_to_config(config=config, targets=resolved_targets)
        if effective_config.champion_ids or effective_config.map_ids:
            return (
                resolved_targets,
                effective_config,
                PipelineDecisionSnapshot(
                    run_id=run_id,
                    target_source="manifest_diff_inferred",
                    current_version=current_pair.version,
                    previous_version=previous_pair.version,
                    target_count=len(resolved_targets),
                    selected_champion_ids=effective_config.champion_ids or tuple(),
                    selected_map_ids=effective_config.map_ids or tuple(),
                    resolved_targets=resolved_targets,
                    candidates=tuple(_serialize_targets(inferred_targets)),
                ),
            )

    return (
        tuple(),
        safe_config,
        PipelineDecisionSnapshot(
            run_id=run_id,
            target_source="pending_runtime_diff_integration",
            current_version=current_pair.version,
            previous_version=previous_pair.version if previous_pair is not None else None,
            target_count=0,
            remote_execution_skipped=True,
            reason=(
                "当前 remote diff 决策未能收敛到可执行目标；"
                "若未提供 previous_pair，请先由 Worker 提供权威 previous-version 基线。"
            ),
        ),
    )


def handle_entity_artifacts(
    config: PipelineRunConfig,
    artifact: EntityArtifacts,
    version: str | None,
) -> tuple[Path, ...]:
    """将单实体产物打包为归档文件。

    Args:
        config: Pipeline 运行配置。
        artifact: 单实体产物。
        version: 本轮版本号。

    Returns:
        tuple[Path, ...]: 归档文件路径集合。
    """

    if version is None:
        return tuple()

    output_dir = config.output_root / "packages" / version / artifact.entity_type
    extra_files = (
        (artifact.mapping_output_path,)
        if artifact.mapping_output_path is not None and artifact.mapping_output_path.is_file()
        else tuple()
    )
    archives: list[Path] = []
    for audio_dir in artifact.audio_output_paths:
        if not audio_dir.is_dir():
            continue
        archives.append(
            pack_champion(
                champion_dir=audio_dir,
                output_path=output_dir,
                extra_files=extra_files,
            )
        )
    return tuple(archives)


def build_processing_targets(
    config: PipelineRunConfig,
    *,
    previous_version: str | None,
    current_pair: ManifestPairRef | None,
    manifest_report: object | None = None,
    wad_report: object | None = None,
    resolved_wad_report: object | None = None,
) -> tuple[ProcessingTarget, ...]:
    """构建本轮待处理实体。

    Args:
        config: Pipeline 运行配置。
        previous_version: 上一次成功版本；为空表示首跑。
        current_pair: 当前 remote manifest pair；local 模式可为空。
        manifest_report: 可选 manifest diff 结果。
        wad_report: 可选 wad header diff 结果。
        resolved_wad_report: 可选路径回填后的 wad 报告。

    Returns:
        tuple[ProcessingTarget, ...]: 待处理实体集合。
    """

    explicit_targets = _build_targets_from_explicit_ids(config)
    if explicit_targets:
        return explicit_targets
    if previous_version is None or current_pair is None:
        return tuple()

    changed_paths = _collect_changed_paths(
        manifest_report=manifest_report,
        wad_report=wad_report,
        resolved_wad_report=resolved_wad_report,
    )
    return _extract_targets_from_paths(changed_paths)


def build_manifest_diff_report(
    config: PipelineRunConfig,
    *,
    previous_pair: ManifestPairRef,
    current_pair: ManifestPairRef,
    include_unchanged: bool = False,
) -> object:
    """构建真实 manifest diff 报告。

    Args:
        config: Pipeline 运行配置。
        previous_pair: 上一版 manifest pair。
        current_pair: 当前 manifest pair。
        include_unchanged: 是否保留 unchanged 条目。

    Returns:
        object: `riotmanifest.diff_manifests` 返回的报告对象。
    """

    from riotmanifest import PatcherManifest
    from riotmanifest import diff_manifests

    manifest_cache_root = config.temp_root / "manifest_cache" / "diff"
    old_manifest = PatcherManifest(
        previous_pair.game_manifest_url, path=manifest_cache_root / "old"
    )
    new_manifest = PatcherManifest(current_pair.game_manifest_url, path=manifest_cache_root / "new")
    return diff_manifests(
        old_manifest,
        new_manifest,
        flags=config.game_region,
        pattern="wad.client",
        include_unflagged_when_flags=True,
        include_unchanged=include_unchanged,
        detect_moves=False,
    )


def select_target_wad_paths(
    manifest_report: object,
    *,
    fallback_to_unchanged: bool = True,
    limit: int | None = None,
) -> tuple[str, ...]:
    """从 manifest diff 报告中选择 WAD 路径。

    Args:
        manifest_report: manifest diff 报告对象。
        fallback_to_unchanged: 无 changed 条目时是否回退到 unchanged。
        limit: 可选上限。

    Returns:
        tuple[str, ...]: 选出的 WAD 路径。
    """

    selected_paths = _extract_paths_from_report(getattr(manifest_report, "changed", tuple()))
    if not selected_paths and fallback_to_unchanged:
        selected_paths = _extract_paths_from_report(getattr(manifest_report, "unchanged", tuple()))
    filtered_paths = [
        path
        for path in selected_paths
        if isinstance(path, str) and path.strip().lower().endswith(".wad.client")
    ]
    deduplicated_paths = tuple(dict.fromkeys(filtered_paths))
    if limit is None:
        return deduplicated_paths
    return deduplicated_paths[:limit]


def build_wad_diff_report(
    manifest_report: object,
    *,
    target_wad_files: tuple[str, ...],
    include_unchanged: bool = True,
    inner_paths: dict[str, tuple[str, ...]] | None = None,
) -> object:
    """构建真实 WAD header diff 报告。

    Args:
        manifest_report: manifest diff 报告。
        target_wad_files: 目标 WAD 路径。
        include_unchanged: 是否保留 unchanged section。
        inner_paths: 可选的聚焦内部路径映射。

    Returns:
        object: `riotmanifest.diff_wad_headers` 返回的报告对象。
    """

    from riotmanifest import diff_wad_headers

    return diff_wad_headers(
        manifest_report=manifest_report,
        target_wad_files=target_wad_files,
        include_unchanged=include_unchanged,
        inner_paths=inner_paths,
    )


def build_resolved_wad_diff_report(
    wad_report: object,
    *,
    focus_inner_paths: tuple[str, ...] = tuple(),
    max_skin_id: int = 0,
    include_champion_root_bins: bool = False,
    include_map_bins: bool = False,
    include_section_statuses: tuple[str, ...] = ("unchanged",),
) -> object:
    """执行真实 WAD 路径回填。

    Args:
        wad_report: WAD diff 报告。
        focus_inner_paths: 额外全局候选 BIN 路径。
        max_skin_id: 英雄皮肤 BIN 上限。
        include_champion_root_bins: 是否包含英雄根 BIN。
        include_map_bins: 是否包含地图通用 BIN。
        include_section_statuses: 需要回填的 section 状态。

    Returns:
        object: `riotmanifest.resolve_wad_diff_paths` 返回的新报告对象。
    """

    from riotmanifest import ManifestBinPathProvider
    from riotmanifest import resolve_wad_diff_paths

    with ManifestBinPathProvider(
        max_skin_id=max_skin_id,
        include_champion_root_bins=include_champion_root_bins,
        include_map_bins=include_map_bins,
        global_paths=focus_inner_paths,
    ) as provider:
        return resolve_wad_diff_paths(
            wad_report,
            path_provider=provider,
            include_section_statuses=include_section_statuses,
        )


def _build_control_service(config: PipelineRunConfig) -> CloudflareControlService | None:
    """按需构造控制面服务。"""

    if not config.control_plane_base_url:
        return None
    client = CloudflareWorkerClient(
        CloudflareControlConfig(
            base_url=config.control_plane_base_url,
            bearer_token=config.control_plane_bearer_token,
            access_client_id=config.control_plane_access_client_id,
            access_client_secret=config.control_plane_access_client_secret,
            timeout_seconds=config.control_plane_timeout_seconds,
        )
    )
    return CloudflareControlService(client)


def _bootstrap_control_plane(
    config: PipelineRunConfig,
) -> tuple[PipelineRunConfig, ManifestPairRef | None]:
    """从控制面 bootstrap 回填运行配置，并返回当前 pair。"""

    service = _build_control_service(config)
    if service is None:
        return config, None

    response = service.get_pipeline_bootstrap(
        PipelineBootstrapRequest(
            game_region=config.game_region,
            mode=config.mode,
            requested_by=config.control_plane_requested_by,
            champion_ids=config.champion_ids,
            map_ids=config.map_ids,
        )
    )
    previous_pair = response.previous_pair
    grant = response.baidu_access_grant
    runtime_config = replace(
        config,
        baidu_app_key=grant.app_key if grant and grant.app_key else config.baidu_app_key,
        baidu_secret_key=grant.secret_key if grant and grant.secret_key else config.baidu_secret_key,
        baidu_refresh_token=grant.refresh_token if grant and grant.refresh_token else config.baidu_refresh_token,
        previous_version=response.previous_version or config.previous_version,
        previous_lcu_manifest_url=(
            previous_pair.lcu_manifest_url if previous_pair is not None else config.previous_lcu_manifest_url
        ),
        previous_game_manifest_url=(
            previous_pair.game_manifest_url
            if previous_pair is not None
            else config.previous_game_manifest_url
        ),
        previous_match_mode=(
            previous_pair.match_mode if previous_pair is not None else config.previous_match_mode
        ),
        previous_match_reason=(
            previous_pair.match_reason if previous_pair is not None else config.previous_match_reason
        ),
    )
    current_pair = ManifestPairRef(
        version=response.current_pair.version,
        lcu_manifest_url=response.current_pair.lcu_manifest_url,
        game_manifest_url=response.current_pair.game_manifest_url,
        match_mode=response.current_pair.match_mode or "worker_bootstrap",
        match_reason=response.current_pair.match_reason or "worker_bootstrap",
    )
    return runtime_config, current_pair


def _report_control_plane_heartbeat(
    config: PipelineRunConfig,
    *,
    run_id: str,
    status: str,
    stage: PipelineStage,
    summary: PipelineRunSummary | None,
) -> None:
    """向控制面上报心跳；未配置控制面时静默跳过。"""

    service = _build_control_service(config)
    if service is None:
        return
    progress: dict[str, object] = {"stage": stage.value}
    if summary is not None:
        progress.update(
            {
                "uploaded_archives": summary.uploaded_archives,
                "processed_targets": summary.processed_targets,
                "succeeded_targets": summary.succeeded_targets,
                "failed_targets": summary.failed_targets,
            }
        )
    service.report_pipeline_run_heartbeat(
        RunHeartbeatRequest(
            run_id=run_id,
            status=status,
            last_log_at=datetime.now().astimezone().isoformat(),
            progress=progress,
        )
    )


def _report_control_plane_run_result(
    config: PipelineRunConfig,
    *,
    summary: PipelineRunSummary,
    from_version: str | None,
    to_version: str | None,
    baidu_log_path: str | None,
) -> None:
    """向控制面上报最终结果；未配置控制面时静默跳过。"""

    service = _build_control_service(config)
    if service is None or to_version is None:
        return
    service.report_pipeline_run_result(
        RunReportRequest(
            run_id=summary.run_id,
            from_version=from_version,
            to_version=to_version,
            status=summary.status,
            summary={
                "schema_version": summary.schema_version,
                "mode": summary.mode.value,
                "version": summary.version,
                "processed_targets": summary.processed_targets,
                "succeeded_targets": summary.succeeded_targets,
                "failed_targets": summary.failed_targets,
                "uploaded_archives": summary.uploaded_archives,
                "pending_manifest_sync_entries": summary.pending_manifest_sync_entries,
                "pending_log_upload_entries": summary.pending_log_upload_entries,
                "log_dir": str(summary.log_dir),
            },
            uploaded_archives=summary.uploaded_archives,
            baidu_log_path=baidu_log_path,
        )
    )


def _build_baidu_log_remote_path(
    config: PipelineRunConfig,
    log_ctx: object,
) -> str | None:
    """构造运行日志目录的百度远端根路径。"""

    if not _has_baidu_credentials(config):
        return None
    run_date = getattr(log_ctx, "run_date", None)
    run_id = getattr(log_ctx, "run_id", None)
    if not isinstance(run_date, str) or not isinstance(run_id, str):
        return None
    return f"{config.baidu_remote_root.rstrip('/')}/logs/{run_date}/{run_id}"


def resolve_remote_manifest_pair(config: PipelineRunConfig) -> ManifestPairRef:
    """薄封装 remote manifest pair 解析，便于测试 monkeypatch。"""

    from rift_audio_pipeline.pipeline.remote import resolve_remote_manifest_pair as _resolve

    return _resolve(config)


def _upload_archives_for_run(
    config: PipelineRunConfig,
    archives: tuple[Path, ...],
    version: str,
) -> Path | None:
    """调用现有上传模块完成资源包上传与索引同步。"""

    upload_config = UploadConfig(
        output_path=config.output_root,
        baidu_pan_remote_dir=config.baidu_remote_root,
        baidu_pan_app_key=config.baidu_app_key,
        baidu_pan_secret_key=config.baidu_secret_key,
        baidu_pan_refresh_token=config.baidu_refresh_token,
    )
    return upload_module._upload_archives_and_manifest(
        config=upload_config,
        game_version=version,
        archives=archives,
        pending_manifest_sync_queue_file=config.output_root
        / "state"
        / "pending_manifest_sync_queue.json",
    )


def _retry_pending_manifest_sync_queue_if_possible(
    config: PipelineRunConfig,
    queue_file: Path,
) -> None:
    """若百度凭据齐全，则优先重试 manifest 补偿队列。"""

    if not _has_baidu_credentials(config):
        return
    upload_config = UploadConfig(
        output_path=config.output_root,
        baidu_pan_remote_dir=config.baidu_remote_root,
        baidu_pan_app_key=config.baidu_app_key,
        baidu_pan_secret_key=config.baidu_secret_key,
        baidu_pan_refresh_token=config.baidu_refresh_token,
    )
    upload_module._retry_pending_manifest_sync_queue(
        config=upload_config,
        queue_file=queue_file,
    )


def _build_targets_from_explicit_ids(config: PipelineRunConfig) -> tuple[ProcessingTarget, ...]:
    """根据显式传入的 champion/map IDs 构建目标集合。"""

    targets: list[ProcessingTarget] = []
    for champion_id in config.champion_ids or tuple():
        targets.append(
            ProcessingTarget(
                entity_type="champion",
                entity_id=champion_id,
                decision_reason="explicit_champion_ids",
            )
        )
    for map_id in config.map_ids or tuple():
        targets.append(
            ProcessingTarget(
                entity_type="map",
                entity_id=map_id,
                decision_reason="explicit_map_ids",
            )
        )
    return tuple(targets)


def _collect_changed_paths(
    *,
    manifest_report: object | None,
    wad_report: object | None,
    resolved_wad_report: object | None,
) -> tuple[str, ...]:
    """从多层 diff 结果中尽量提取变更路径。"""

    candidates: list[str] = []
    for report in (resolved_wad_report, wad_report, manifest_report):
        if report is None:
            continue
        candidates.extend(_extract_paths_from_report(report))
    normalized_paths = {
        path.replace("\\", "/") for path in candidates if isinstance(path, str) and path.strip()
    }
    return tuple(sorted(normalized_paths))


def _extract_paths_from_report(report: object) -> list[str]:
    """递归提取 diff 报告中的路径字段。"""

    results: list[str] = []
    if isinstance(report, str):
        return [report]
    if isinstance(report, dict):
        for key, value in report.items():
            if key in {"path", "wad_path", "resolved_path", "file_path"} and isinstance(value, str):
                results.append(value)
            else:
                results.extend(_extract_paths_from_report(value))
        return results
    if isinstance(report, (list, tuple, set)):
        for item in report:
            results.extend(_extract_paths_from_report(item))
        return results
    for attr_name in (
        "path",
        "wad_path",
        "resolved_path",
        "file_path",
        "changed",
        "added",
        "removed",
        "unchanged",
        "moved",
        "entries",
        "files",
        "section_diffs",
    ):
        if hasattr(report, attr_name):
            results.extend(_extract_paths_from_report(getattr(report, attr_name)))
    return results


def _extract_targets_from_paths(paths: tuple[str, ...]) -> tuple[ProcessingTarget, ...]:
    """从变更路径中提取英雄 alias 与地图标识。"""

    targets: list[ProcessingTarget] = []
    seen_keys: set[tuple[str, str]] = set()
    for raw_path in paths:
        normalized_path = raw_path.replace("\\", "/")
        champion_alias = _extract_champion_alias(normalized_path)
        if champion_alias is not None:
            key = ("champion", champion_alias.casefold())
            if key not in seen_keys:
                seen_keys.add(key)
                targets.append(
                    ProcessingTarget(
                        entity_type="champion",
                        entity_id=None,
                        alias=champion_alias,
                        source_wads=(normalized_path,),
                        decision_reason="diff_path_inferred",
                    )
                )
            continue
        map_name = _extract_map_name(normalized_path)
        if map_name is not None:
            map_id = _extract_map_id(map_name)
            key = ("map", str(map_id) if map_id is not None else map_name.casefold())
            if key not in seen_keys:
                seen_keys.add(key)
                targets.append(
                    ProcessingTarget(
                        entity_type="map",
                        entity_id=map_id,
                        name=map_name,
                        source_wads=(normalized_path,),
                        decision_reason="diff_path_inferred",
                    )
                )
    return tuple(targets)


def _extract_champion_alias(path: str) -> str | None:
    """从路径中提取英雄 alias。"""

    for pattern in (CHAMPION_WAD_PATTERN, CHAMPION_BIN_PATTERN):
        match = pattern.search(path)
        if match is not None:
            return match.group("alias")
    return None


def _extract_map_name(path: str) -> str | None:
    """从路径中提取地图名。"""

    for pattern in (MAP_WAD_PATTERN, MAP_BIN_PATTERN):
        match = pattern.search(path)
        if match is not None:
            return match.group("map_name")
    return None


def _extract_map_id(map_name: str) -> int | None:
    """从地图名中提取稳定 map ID。

    约定：
    - `Common` -> `0`
    - `Map30` -> `30`
    - 其余无法命中 `Map<id>` 规则的值返回 `None`
    """

    normalized_name = map_name.strip()
    if normalized_name.casefold() == "common":
        return 0
    match = re.fullmatch(r"map(?P<map_id>\d+)", normalized_name, re.IGNORECASE)
    if match is None:
        return None
    return int(match.group("map_id"))


def _resolve_previous_manifest_pair(config: PipelineRunConfig) -> ManifestPairRef | None:
    """从运行配置中解析上一个 manifest pair。

    约束：
    - `previous_version`
    - `previous_lcu_manifest_url`
    - `previous_game_manifest_url`
      三者需同时提供，才视为存在可用 baseline。
    """

    if not (
        config.previous_version
        and config.previous_lcu_manifest_url
        and config.previous_game_manifest_url
    ):
        return None
    return ManifestPairRef(
        version=config.previous_version,
        lcu_manifest_url=config.previous_lcu_manifest_url,
        game_manifest_url=config.previous_game_manifest_url,
        match_mode=config.previous_match_mode or "external_previous_pair",
        match_reason=config.previous_match_reason or "provided_by_runtime_config",
    )


def _resolve_current_manifest_pair(config: PipelineRunConfig) -> ManifestPairRef | None:
    """从运行配置中解析当前 manifest pair。"""

    if not (
        config.current_version
        and config.current_lcu_manifest_url
        and config.current_game_manifest_url
    ):
        return None
    return ManifestPairRef(
        version=config.current_version,
        lcu_manifest_url=config.current_lcu_manifest_url,
        game_manifest_url=config.current_game_manifest_url,
        match_mode="external_current_pair",
        match_reason="provided_by_runtime_config",
    )


def _resolve_remote_target_ids(
    config: PipelineRunConfig,
    *,
    current_pair: ManifestPairRef,
    targets: tuple[ProcessingTarget, ...],
) -> tuple[ProcessingTarget, ...]:
    """把 remote diff 候选目标收敛为可执行 IDs。"""

    champion_aliases: list[str] = []
    for target in targets:
        if target.entity_type == "champion" and target.entity_id is None and target.alias:
            champion_aliases.append(target.alias)

    alias_to_id: dict[str, int] = {}
    if champion_aliases:
        from lol_audio_unpack import LolAudioUnpackApp

        app = LolAudioUnpackApp(build_remote_app_context(config=config, pair=current_pair))
        app.prepare_update_data(force_update=config.force_update)
        resolved_ids = app.resolve_champion_ids(champion_aliases) or tuple()
        alias_to_id = {
            alias.casefold(): champion_id for alias, champion_id in zip(champion_aliases, resolved_ids, strict=False)
        }

    resolved_targets: list[ProcessingTarget] = []
    for target in targets:
        if target.entity_type != "champion":
            resolved_targets.append(target)
            continue
        resolved_targets.append(
            replace(
                target,
                entity_id=alias_to_id.get(target.alias.casefold()) if target.alias is not None else target.entity_id,
            )
        )
    return tuple(resolved_targets)


def _apply_targets_to_config(
    config: PipelineRunConfig,
    targets: tuple[ProcessingTarget, ...],
) -> PipelineRunConfig:
    """将可解析的目标 ID 回写到运行配置。"""

    champion_ids = tuple(
        target.entity_id
        for target in targets
        if target.entity_type == "champion" and target.entity_id is not None
    )
    map_ids = tuple(
        target.entity_id
        for target in targets
        if target.entity_type == "map" and target.entity_id is not None
    )
    if not champion_ids and not map_ids:
        return config
    return replace(
        config,
        champion_ids=champion_ids or config.champion_ids,
        map_ids=map_ids or config.map_ids,
        include_champions=bool(champion_ids) if champion_ids else config.include_champions,
        include_maps=bool(map_ids) if map_ids else config.include_maps,
    )


def _serialize_targets(targets: tuple[ProcessingTarget, ...]) -> list[dict[str, object]]:
    """把目标列表转换为可 JSON 序列化结构。"""

    payload: list[dict[str, object]] = []
    for target in targets:
        payload.append(
            {
                "entity_type": target.entity_type,
                "entity_id": target.entity_id,
                "alias": target.alias,
                "name": target.name,
                "source_wads": list(target.source_wads),
                "decision_reason": target.decision_reason,
            }
        )
    return payload


def _resolve_local_version(config: PipelineRunConfig) -> str | None:
    """尽量从本地模式环境推断版本号。"""

    version_file = config.output_root / "manifest" / "version.txt"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip() or None
    return None


def _create_baidu_client(config: PipelineRunConfig) -> BaiduPanClient:
    """构造百度网盘客户端。"""

    if not _has_baidu_credentials(config):
        raise ValueError("缺少百度凭据，无法创建 BaiduPanClient。")
    return BaiduPanClient(
        credentials=BaiduCredentials(
            app_key=config.baidu_app_key,
            secret_key=config.baidu_secret_key,
            refresh_token=config.baidu_refresh_token,
        ),
        remote_dir=config.baidu_remote_root,
        token_store=resolve_token_store(),
    )


def _has_baidu_credentials(config: PipelineRunConfig) -> bool:
    """判断百度上传凭据是否完整。"""

    return bool(config.baidu_app_key and config.baidu_secret_key and config.baidu_refresh_token)


def _count_json_list_entries(file_path: Path) -> int:
    """统计 JSON 数组文件条目数。"""

    if not file_path.exists():
        return 0
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"JSON 队列格式非法：{file_path}")
    return len(payload)
