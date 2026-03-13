"""Pipeline 总控编排入口。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import re
import shutil

from rift_audio_pipeline.baidu import BaiduCredentials
from rift_audio_pipeline.baidu import BaiduPanClient
from rift_audio_pipeline.baidu import resolve_token_store
from rift_audio_pipeline.control_plane.state_db import enqueue_upload_task
from rift_audio_pipeline.control_plane.state_db import mark_task_production_closed
from rift_audio_pipeline.packer import pack_champion
from rift_audio_pipeline.packer import _build_archive_name
from rift_audio_pipeline.pipeline.archive_publish import build_archive_publish_layout
from rift_audio_pipeline.pipeline.archive_publish import resolve_default_archive_resource_type
from rift_audio_pipeline.pipeline.local import run_local_pipeline
from rift_audio_pipeline.pipeline.logging import build_log_sink_config
from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.logging import finalize_log_relay_delivery
from rift_audio_pipeline.pipeline.logging import finalize_run_logging
from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.logging import load_error_snapshot
from rift_audio_pipeline.pipeline.logging import LogRelayClient
from rift_audio_pipeline.pipeline.logging import record_error_snapshot
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineArtifactRecord
from rift_audio_pipeline.pipeline.models import PipelineArtifactsSnapshot
from rift_audio_pipeline.pipeline.models import PipelineDecisionSnapshot
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineLogTerminalSummary
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.models import PipelineStage
from rift_audio_pipeline.pipeline.models import ProcessingTarget
from rift_audio_pipeline.pipeline.remote import build_remote_app_context
from rift_audio_pipeline.pipeline.remote import run_remote_pipeline

DEFAULT_ARCHIVE_PASSWORD = "x-item.com"

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
    runtime_config = config
    state_db_path = _require_state_database_path(runtime_config)
    resolved_version: str | None = None
    uploaded_archives = 0
    decision_payload: PipelineDecisionSnapshot | None = None
    active_stage = PipelineStage.INIT
    summary: PipelineRunSummary | None = None

    try:
        relay_client = _build_log_relay_client(runtime_config, log_ctx)
        if relay_client is not None:
            log_ctx.log_delivery_sink = relay_client
            relay_client.start()
        emit_event(
            log_ctx,
            PipelineEvent(
                run_id=log_ctx.run_id,
                stage=PipelineStage.INIT,
                event_type="run_started",
                message="pipeline 开始运行",
                payload={"mode": runtime_config.mode.value},
                created_at=datetime.now().astimezone().isoformat(),
                status_hint="running",
                operation="run_pipeline",
            ),
        )

        active_stage = PipelineStage.LOAD_REMOTE_INDEX

        artifacts: list[EntityArtifacts]
        artifact_records: list[PipelineArtifactRecord] = []
        targets: tuple[ProcessingTarget, ...] = tuple()
        if runtime_config.mode is PipelineMode.REMOTE:
            active_stage = PipelineStage.RESOLVE_MANIFEST_PAIR
            pair = (
                _resolve_current_manifest_pair(runtime_config)
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
                    status_hint="running",
                    operation="build_targets",
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
            _enqueue_archive_upload_tasks_for_run(
                config=runtime_config,
                state_db_path=state_db_path,
                run_id=log_ctx.run_id,
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
            pending_manifest_sync_entries=0,
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
    except Exception as error:  # noqa: BLE001
        record_error_snapshot(
            log_ctx,
            active_stage,
            error,
            payload={
                "resolved_version": resolved_version,
                "decision": asdict(decision_payload) if decision_payload is not None else None,
                "operation": "run_pipeline",
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
            pending_manifest_sync_entries=0,
            pending_log_upload_entries=0,
            log_dir=log_ctx.log_dir,
        )
        finalize_run_logging(log_ctx, summary, decision_payload=decision_payload)

    if summary is None:
        raise RuntimeError("pipeline 结束时未生成运行摘要。")
    _close_upload_task_production(state_db_path=state_db_path, summary=summary)
    finalize_log_relay_delivery(
        log_ctx,
        _build_terminal_log_summary(
            log_ctx=log_ctx,
            summary=summary,
            final_stage=PipelineStage.FINALIZE
            if summary.status is not PipelineRunStatus.FAILED
            else active_stage,
            error_brief=load_error_snapshot(log_ctx),
        ),
        shutdown=False,
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
    report_file = _resolve_report_file(config=config, artifact=artifact, version=version)
    extra_files = _resolve_pack_extra_items(artifact=artifact)
    archives: list[Path] = []
    for audio_dir in artifact.audio_output_paths:
        if not audio_dir.is_dir():
            continue
        archive_path = pack_champion(
            champion_dir=audio_dir,
            output_path=output_dir,
            archive_name=_build_archive_name(
                directory_name=audio_dir.name,
                version=version,
                audio_type=resolve_default_archive_resource_type(),
            ),
            report_file=report_file,
            password=config.archive_password or DEFAULT_ARCHIVE_PASSWORD,
            extra_files=extra_files,
        )
        archives.append(archive_path)
        shutil.rmtree(audio_dir)
    return tuple(archives)


def _resolve_report_file(
    *,
    config: PipelineRunConfig,
    artifact: EntityArtifacts,
    version: str,
) -> Path | None:
    """解析当前实体对应的 `_id_metadata.yaml`。"""

    entity_dir_name = f"{artifact.entity_type}s"
    candidate = config.output_root / "reports" / version / entity_dir_name / f"_{artifact.entity_id}_metadata.yaml"
    if candidate.is_file():
        return candidate
    return None


def _resolve_pack_extra_items(*, artifact: EntityArtifacts) -> tuple[Path, ...]:
    """汇总需要打进压缩包根目录的附加项。"""

    extras: list[Path] = []
    if artifact.mapping_output_path is not None and artifact.mapping_output_path.is_file():
        extras.append(artifact.mapping_output_path)
    pack_extra_dir = Path(__file__).resolve().parents[1] / "pack_extra"
    if pack_extra_dir.is_dir():
        extras.append(pack_extra_dir)
    return tuple(extras)


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


def resolve_remote_manifest_pair(config: PipelineRunConfig) -> ManifestPairRef:
    """薄封装 remote manifest pair 解析，便于测试 monkeypatch。"""

    from rift_audio_pipeline.pipeline.remote import resolve_remote_manifest_pair as _resolve

    return _resolve(config)


def _build_log_relay_client(
    config: PipelineRunConfig,
    log_ctx: object,
) -> LogRelayClient | None:
    """构造运行期 relay socket 客户端。"""

    required_fields = (
        "log_relay_state_file",
        "relay_socket_file",
    )
    if not all(hasattr(log_ctx, field_name) for field_name in required_fields):
        return None
    sink_config = build_log_sink_config(config, log_ctx)
    if not sink_config.enabled:
        return None
    run_id = getattr(log_ctx, "run_id", None)
    relay_state_file = getattr(log_ctx, "log_relay_state_file", None)
    relay_socket_file = getattr(log_ctx, "relay_socket_file", None)
    if not isinstance(run_id, str):
        return None
    if not isinstance(relay_state_file, Path) or not isinstance(relay_socket_file, Path):
        return None
    return LogRelayClient(
        run_id=run_id,
        relay_state_file=relay_state_file,
        relay_socket_file=relay_socket_file,
        config=sink_config,
        spawn_process=False,
    )


def _build_terminal_log_summary(
    *,
    log_ctx: object,
    summary: PipelineRunSummary,
    final_stage: PipelineStage,
    error_brief: dict[str, object] | None,
) -> PipelineLogTerminalSummary:
    """构造 relay 终态摘要。"""

    run_id = getattr(log_ctx, "run_id")
    last_seq = getattr(log_ctx, "last_event_seq", 0)
    log_dir = getattr(log_ctx, "log_dir")
    return PipelineLogTerminalSummary(
        run_id=run_id,
        finished_at=datetime.now().astimezone().isoformat(),
        final_status=summary.status.value,
        final_stage=final_stage.value,
        last_seq=last_seq if isinstance(last_seq, int) else 0,
        processed_targets=summary.processed_targets,
        succeeded_targets=summary.succeeded_targets,
        failed_targets=summary.failed_targets,
        uploaded_archives=summary.uploaded_archives,
        raw_log_bundle_ready=True,
        raw_log_local_dir=str(log_dir),
        raw_log_remote_path=None,
        summary={"status": summary.status.value},
        error_brief=error_brief,
    )


def _enqueue_archive_upload_tasks_for_run(
    config: PipelineRunConfig,
    *,
    state_db_path: Path,
    run_id: str,
    archives: tuple[Path, ...],
    version: str,
) -> None:
    """将 archive 上传任务写入本地状态库。"""

    default_resource_type = resolve_default_archive_resource_type()
    for archive in archives:
        layout = build_archive_publish_layout(
            archive=archive,
            remote_root=config.archive_remote_root,
            default_resource_type=default_resource_type,
        )
        enqueue_upload_task(
            database_path=state_db_path,
            run_id=run_id,
            local_path=str(archive),
            remote_path=layout.remote_path,
            task_type="archive",
            payload={
                "remote_relative_path": layout.remote_relative_path,
                "remote_name": layout.remote_name,
                "target_group": layout.target_group,
                "resource_type": layout.resource_type,
                "entity_key": layout.entity_key,
                "game_version": version,
            },
        )


def _close_upload_task_production(
    *,
    state_db_path: Path,
    summary: PipelineRunSummary,
) -> None:
    """标记本轮不会再新增上传任务。"""

    mark_task_production_closed(
        database_path=state_db_path,
        run_id=summary.run_id,
        pipeline_status=summary.status.value,
        final_summary_path=str(summary.log_dir / "run.json"),
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
        remote_dir=config.archive_remote_root,
        token_store=resolve_token_store(),
    )


def _has_baidu_credentials(config: PipelineRunConfig) -> bool:
    """判断百度上传凭据是否完整。"""

    return bool(config.baidu_app_key and config.baidu_secret_key and config.baidu_refresh_token)


def _require_state_database_path(config: PipelineRunConfig) -> Path:
    """要求当前运行必须显式提供状态库路径。"""

    if config.state_db_path is None:
        raise ValueError("当前 runtime worker 主路径要求显式提供 state_db_path。")
    return config.state_db_path
