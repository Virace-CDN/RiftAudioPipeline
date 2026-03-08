"""Pipeline 编排层公开入口。"""

from rift_audio_pipeline.pipeline.cli import build_parser
from rift_audio_pipeline.pipeline.cli import build_run_config
from rift_audio_pipeline.pipeline.cli import main
from rift_audio_pipeline.pipeline.logging import PipelineLogContext
from rift_audio_pipeline.pipeline.logging import emit_event
from rift_audio_pipeline.pipeline.logging import enqueue_pending_log_upload
from rift_audio_pipeline.pipeline.logging import finalize_run_logging
from rift_audio_pipeline.pipeline.logging import initialize_run_logging
from rift_audio_pipeline.pipeline.logging import record_error_snapshot
from rift_audio_pipeline.pipeline.logging import upload_run_logs
from rift_audio_pipeline.pipeline.local import build_local_app_context
from rift_audio_pipeline.pipeline.local import run_local_pipeline
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineEvent
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.models import PipelineStage
from rift_audio_pipeline.pipeline.models import ProcessingTarget
from rift_audio_pipeline.pipeline.orchestrator import handle_entity_artifacts
from rift_audio_pipeline.pipeline.orchestrator import build_processing_targets
from rift_audio_pipeline.pipeline.orchestrator import build_manifest_diff_report
from rift_audio_pipeline.pipeline.orchestrator import build_resolved_wad_diff_report
from rift_audio_pipeline.pipeline.orchestrator import build_wad_diff_report
from rift_audio_pipeline.pipeline.orchestrator import run_pipeline
from rift_audio_pipeline.pipeline.orchestrator import select_target_wad_paths
from rift_audio_pipeline.pipeline.remote import build_remote_app_context
from rift_audio_pipeline.pipeline.remote import build_remote_operation_options
from rift_audio_pipeline.pipeline.remote import convert_remote_payload
from rift_audio_pipeline.pipeline.remote import resolve_remote_manifest_pair
from rift_audio_pipeline.pipeline.remote import run_remote_pipeline

__all__ = [
    "EntityArtifacts",
    "ManifestPairRef",
    "PipelineEvent",
    "PipelineLogContext",
    "PipelineMode",
    "PipelineRunConfig",
    "PipelineRunSummary",
    "PipelineStage",
    "ProcessingTarget",
    "build_parser",
    "build_processing_targets",
    "build_run_config",
    "build_manifest_diff_report",
    "build_resolved_wad_diff_report",
    "build_wad_diff_report",
    "build_local_app_context",
    "build_remote_app_context",
    "build_remote_operation_options",
    "convert_remote_payload",
    "emit_event",
    "enqueue_pending_log_upload",
    "finalize_run_logging",
    "handle_entity_artifacts",
    "initialize_run_logging",
    "main",
    "record_error_snapshot",
    "resolve_remote_manifest_pair",
    "run_local_pipeline",
    "run_pipeline",
    "run_remote_pipeline",
    "select_target_wad_paths",
    "upload_run_logs",
]
