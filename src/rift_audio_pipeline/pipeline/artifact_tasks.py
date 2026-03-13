"""单实体压缩包任务规划与打包辅助。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rift_audio_pipeline.packer import _build_archive_name
from rift_audio_pipeline.packer import pack_champion
from rift_audio_pipeline.pipeline.archive_publish import build_archive_publish_layout
from rift_audio_pipeline.pipeline.archive_publish import resolve_default_archive_resource_type
from rift_audio_pipeline.pipeline.models import EntityArtifacts


@dataclass(frozen=True, slots=True)
class ArtifactTaskPlan:
    """描述单个本地实体目录的打包与上传计划。"""

    entity_type: str
    entity_id: int
    source_dir: Path
    archive_output_dir: Path
    archive_name: str
    report_file: Path | None
    extra_files: tuple[Path, ...]
    game_version: str
    remote_relative_path: str
    remote_path: str
    remote_name: str
    target_group: str
    resource_type: str
    entity_key: str


def build_artifact_task_plans(
    *,
    output_root: Path,
    archive_remote_root: str,
    artifact: EntityArtifacts,
    version: str,
) -> tuple[ArtifactTaskPlan, ...]:
    """基于单实体产物生成一个或多个压缩上传任务计划。"""

    output_dir = output_root / "packages" / version / artifact.entity_type
    report_file = _resolve_report_file(
        output_root=output_root,
        artifact=artifact,
        version=version,
    )
    extra_files = _resolve_pack_extra_items(artifact=artifact)
    default_resource_type = resolve_default_archive_resource_type()
    plans: list[ArtifactTaskPlan] = []
    for audio_dir in artifact.audio_output_paths:
        if not audio_dir.is_dir():
            continue
        archive_name = _build_archive_name(
            directory_name=audio_dir.name,
            version=version,
            audio_type=default_resource_type,
        )
        archive_path = output_dir / archive_name
        layout = build_archive_publish_layout(
            archive=archive_path,
            remote_root=archive_remote_root,
            default_resource_type=default_resource_type,
        )
        plans.append(
            ArtifactTaskPlan(
                entity_type=artifact.entity_type,
                entity_id=artifact.entity_id,
                source_dir=audio_dir,
                archive_output_dir=output_dir,
                archive_name=archive_name,
                report_file=report_file,
                extra_files=extra_files,
                game_version=version,
                remote_relative_path=layout.remote_relative_path,
                remote_path=layout.remote_path,
                remote_name=layout.remote_name,
                target_group=layout.target_group,
                resource_type=layout.resource_type,
                entity_key=layout.entity_key,
            )
        )
    return tuple(plans)


def serialize_artifact_task_plan(plan: ArtifactTaskPlan) -> dict[str, object]:
    """把打包任务计划序列化为可写入 SQLite 的 JSON payload。"""

    return {
        "entity_type": plan.entity_type,
        "entity_id": plan.entity_id,
        "source_dir": str(plan.source_dir),
        "archive_output_dir": str(plan.archive_output_dir),
        "archive_name": plan.archive_name,
        "report_file": str(plan.report_file) if plan.report_file is not None else None,
        "extra_files": [str(path) for path in plan.extra_files],
        "game_version": plan.game_version,
        "remote_relative_path": plan.remote_relative_path,
        "remote_name": plan.remote_name,
        "target_group": plan.target_group,
        "resource_type": plan.resource_type,
        "entity_key": plan.entity_key,
    }


def parse_artifact_task_plan(payload: dict[str, object], *, remote_path: str) -> ArtifactTaskPlan:
    """从 SQLite payload 反序列化打包任务计划。"""

    extra_files_raw = payload.get("extra_files")
    if extra_files_raw is None:
        extra_files: tuple[Path, ...] = tuple()
    elif isinstance(extra_files_raw, list) and all(isinstance(item, str) for item in extra_files_raw):
        extra_files = tuple(Path(item) for item in extra_files_raw)
    else:
        raise ValueError("artifact task payload.extra_files 必须是字符串数组。")
    report_file_raw = payload.get("report_file")
    if report_file_raw is not None and not isinstance(report_file_raw, str):
        raise ValueError("artifact task payload.report_file 必须是字符串或 null。")
    return ArtifactTaskPlan(
        entity_type=_require_str(payload, "entity_type"),
        entity_id=_require_int(payload, "entity_id"),
        source_dir=Path(_require_str(payload, "source_dir")),
        archive_output_dir=Path(_require_str(payload, "archive_output_dir")),
        archive_name=_require_str(payload, "archive_name"),
        report_file=Path(report_file_raw) if isinstance(report_file_raw, str) else None,
        extra_files=extra_files,
        game_version=_require_str(payload, "game_version"),
        remote_relative_path=_require_str(payload, "remote_relative_path"),
        remote_path=remote_path,
        remote_name=_require_str(payload, "remote_name"),
        target_group=_require_str(payload, "target_group"),
        resource_type=_require_str(payload, "resource_type"),
        entity_key=_require_str(payload, "entity_key"),
    )


def pack_artifact_task(
    plan: ArtifactTaskPlan,
    *,
    archive_password: str,
) -> Path:
    """按任务计划生成本地压缩包文件。"""

    archive_output_dir = plan.archive_output_dir.expanduser().resolve()
    archive_output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_output_dir / plan.archive_name
    archive_path.unlink(missing_ok=True)
    return pack_champion(
        champion_dir=plan.source_dir,
        output_path=archive_output_dir,
        archive_name=plan.archive_name,
        report_file=plan.report_file,
        password=archive_password,
        extra_files=plan.extra_files,
    )


def _resolve_report_file(
    *,
    output_root: Path,
    artifact: EntityArtifacts,
    version: str,
) -> Path | None:
    """解析当前实体对应的 `_id_metadata.yaml`。"""

    entity_dir_name = f"{artifact.entity_type}s"
    candidate = output_root / "reports" / version / entity_dir_name / f"_{artifact.entity_id}_metadata.yaml"
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


def _require_int(payload: dict[str, object], field_name: str) -> int:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"artifact task payload.{field_name} 必须是整数。")
    return value


def _require_str(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"artifact task payload.{field_name} 必须是非空字符串。")
    return value
