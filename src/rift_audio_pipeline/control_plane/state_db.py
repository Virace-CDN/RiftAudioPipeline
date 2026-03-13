"""本地运行时状态库。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

_VERSION_PATTERN = re.compile(r"-(?P<version>\d+\.\d+)-")
_ARCHIVE_NAME_PATTERN = re.compile(
    r"^(?P<entity_key>.+)-(?P<version>\d+\.\d+)-(?P<artifact_type>ALL|VO|SFX|MUSIC)\.7z$",
    re.IGNORECASE,
)
_ARTIFACT_TYPE_ORDER = {
    "ALL": 0,
    "VO": 1,
    "SFX": 2,
    "MUSIC": 3,
}


@dataclass(frozen=True, slots=True)
class StateDatabaseBootstrapResult:
    """状态库初始化结果。"""

    database_path: Path
    run_id: str
    imported_remote_entries: int


@dataclass(frozen=True, slots=True)
class UploadTaskRecord:
    """上传任务记录。"""

    id: int
    run_id: str
    local_path: str
    remote_path: str
    task_type: str
    payload_json: str | None
    attempt_count: int


@dataclass(frozen=True, slots=True)
class NewFileFactRecord:
    """新文件事实记录。"""

    remote_path: str
    file_name: str
    sha256: str | None
    packaged_at: str | None
    uploaded_at: str | None
    metadata_json: str | None


@dataclass(frozen=True, slots=True)
class UploadQueuePressure:
    """上传队列背压摘要。"""

    unfinished_count: int
    pending_bytes: int


@dataclass(frozen=True, slots=True)
class DatabaseArchiveMove:
    """需要迁移到历史目录的远端 active 产物。"""

    entity_key: str
    artifact_type: str
    version: str
    remote_path: str
    remote_name: str
    target_group: str


@dataclass(frozen=True, slots=True)
class DatabaseExportPlan:
    """database v2 导出计划。"""

    entries: dict[str, dict[str, object]]
    archive_moves: tuple[DatabaseArchiveMove, ...]


def bootstrap_state_database(
    *,
    database_path: Path,
    run_id: str,
    remote_database_payload: dict[str, object],
) -> StateDatabaseBootstrapResult:
    """初始化状态库并导入远端 database 快照。"""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        _initialize_connection(connection)
        _create_schema(connection)
        _upsert_runtime_meta(
            connection,
            key="schema_version",
            value="1",
        )
        _upsert_runtime_meta(
            connection,
            key="last_bootstrap_run_id",
            value=run_id,
        )
        _upsert_run_control(connection, run_id=run_id)
        imported_remote_entries = _replace_remote_database_entries(
            connection,
            run_id=run_id,
            remote_database_payload=remote_database_payload,
        )
        connection.commit()
    return StateDatabaseBootstrapResult(
        database_path=database_path,
        run_id=run_id,
        imported_remote_entries=imported_remote_entries,
    )


def enqueue_upload_task(
    *,
    database_path: Path,
    run_id: str,
    local_path: str,
    remote_path: str,
    task_type: str = "archive",
    payload: dict[str, object] | None = None,
) -> None:
    """追加上传任务。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            INSERT INTO upload_tasks(
                run_id,
                local_path,
                remote_path,
                task_type,
                payload_json,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)
            """,
            (
                run_id,
                local_path,
                remote_path,
                task_type,
                json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload is not None else None,
                now,
                now,
            ),
        )
        connection.commit()


def mark_task_production_closed(
    *,
    database_path: Path,
    run_id: str,
    pipeline_status: str,
    final_summary_path: str,
) -> None:
    """标记某个 run 不会再新增上传任务。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            UPDATE run_control
            SET task_production_open = 0,
                pipeline_status = ?,
                final_summary_path = ?,
                producer_finished_at = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (pipeline_status, final_summary_path, now, now, run_id),
        )
        connection.commit()


def claim_next_upload_task(
    *,
    database_path: Path,
    run_id: str,
    worker_id: str,
) -> UploadTaskRecord | None:
    """claim 下一条可执行上传任务。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT *
            FROM upload_tasks
            WHERE run_id = ?
              AND (
                status = 'queued'
                OR (status = 'retry_wait' AND (next_retry_at IS NULL OR next_retry_at <= ?))
              )
            ORDER BY id ASC
            LIMIT 1
            """,
            (run_id, now),
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            """
            UPDATE upload_tasks
            SET status = 'claimed',
                claimed_by = ?,
                claimed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (worker_id, now, now, row["id"]),
        )
        connection.commit()
        return UploadTaskRecord(
            id=int(row["id"]),
            run_id=str(row["run_id"]),
            local_path=str(row["local_path"]),
            remote_path=str(row["remote_path"]),
            task_type=str(row["task_type"]),
            payload_json=str(row["payload_json"]) if row["payload_json"] is not None else None,
            attempt_count=int(row["attempt_count"]),
        )


def complete_upload_task(
    *,
    database_path: Path,
    task_id: int,
) -> None:
    """标记上传任务完成。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            UPDATE upload_tasks
            SET status = 'done',
                updated_at = ?
            WHERE id = ?
            """,
            (now, task_id),
        )
        connection.commit()


def reschedule_upload_task(
    *,
    database_path: Path,
    task_id: int,
    last_error: str,
    next_retry_at: str,
) -> None:
    """标记上传任务重试等待。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            UPDATE upload_tasks
            SET status = 'retry_wait',
                attempt_count = attempt_count + 1,
                next_retry_at = ?,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (next_retry_at, last_error, now, task_id),
        )
        connection.commit()


def record_new_file_fact(
    *,
    database_path: Path,
    run_id: str,
    local_path: str,
    remote_path: str,
    file_name: str,
    sha256: str,
    packaged_at: str,
    uploaded_at: str,
    metadata: dict[str, object] | None = None,
) -> None:
    """记录上传成功后的文件事实。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            INSERT INTO new_file_facts(
                run_id,
                local_path,
                remote_path,
                file_name,
                sha256,
                packaged_at,
                uploaded_at,
                metadata_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, remote_path) DO UPDATE SET
                local_path = excluded.local_path,
                file_name = excluded.file_name,
                sha256 = excluded.sha256,
                packaged_at = excluded.packaged_at,
                uploaded_at = excluded.uploaded_at,
                metadata_json = excluded.metadata_json
            """,
            (
                run_id,
                local_path,
                remote_path,
                file_name,
                sha256,
                packaged_at,
                uploaded_at,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True) if metadata is not None else None,
                now,
            ),
        )
        connection.commit()


def get_run_drain_state(
    *,
    database_path: Path,
    run_id: str,
) -> tuple[bool, int]:
    """返回是否已封口以及未完成任务数。"""

    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        row = connection.execute(
            """
            SELECT task_production_open
            FROM run_control
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        open_flag = bool(row[0]) if row is not None else True
        unfinished_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM upload_tasks
            WHERE run_id = ?
              AND status IN ('queued', 'claimed', 'retry_wait')
            """,
            (run_id,),
        ).fetchone()[0]
    return (not open_flag, int(unfinished_count))


def mark_upload_phase_drained(
    *,
    database_path: Path,
    run_id: str,
) -> None:
    """标记上传阶段已排空。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            UPDATE run_control
            SET upload_phase_status = 'drained',
                drained_at = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (now, now, run_id),
        )
        connection.commit()


def get_upload_phase_status(
    *,
    database_path: Path,
    run_id: str,
) -> str | None:
    """读取上传阶段状态。"""

    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        row = connection.execute(
            "SELECT upload_phase_status FROM run_control WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row[0])


def mark_upload_phase_finalized(
    *,
    database_path: Path,
    run_id: str,
) -> None:
    """标记上传与索引重建都已完成。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            UPDATE run_control
            SET upload_phase_status = 'finalized',
                finalized_at = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (now, now, run_id),
        )
        connection.commit()


def update_upload_task_local_path(
    *,
    database_path: Path,
    task_id: int,
    local_path: str,
) -> None:
    """更新上传任务当前占用的本地路径。"""

    now = _now()
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.execute(
            """
            UPDATE upload_tasks
            SET local_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (local_path, now, task_id),
        )
        connection.commit()


def get_upload_queue_pressure(
    *,
    database_path: Path,
    run_id: str,
) -> UploadQueuePressure:
    """返回未完成任务数与其本地占用字节数。"""

    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        rows = connection.execute(
            """
            SELECT local_path
            FROM upload_tasks
            WHERE run_id = ?
              AND status IN ('queued', 'claimed', 'retry_wait')
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()
    pending_bytes = 0
    for (raw_local_path,) in rows:
        if not isinstance(raw_local_path, str) or not raw_local_path.strip():
            continue
        pending_bytes += _measure_local_path_bytes(Path(raw_local_path))
    return UploadQueuePressure(
        unfinished_count=len(rows),
        pending_bytes=pending_bytes,
    )


def build_database_entries_for_export(
    *,
    database_path: Path,
    run_id: str,
) -> list[dict[str, object]]:
    """从远端快照和本轮新增文件事实生成新的 database entries。"""

    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.row_factory = sqlite3.Row
        remote_rows = connection.execute(
            """
            SELECT remote_path, remote_name, latest_game_version, entity_key, target_group, resource_type
            FROM remote_database_entries
            WHERE run_id = ?
            ORDER BY remote_path ASC
            """,
            (run_id,),
        ).fetchall()
        fact_rows = connection.execute(
            """
            SELECT remote_path, file_name, sha256, packaged_at, uploaded_at, metadata_json
            FROM new_file_facts
            WHERE run_id = ?
            ORDER BY remote_path ASC
            """,
            (run_id,),
        ).fetchall()

    merged: dict[str, dict[str, object]] = {}
    for row in remote_rows:
        remote_path = row["remote_path"]
        if not isinstance(remote_path, str) or not remote_path:
            continue
        merged[remote_path] = {
            "remote_path": remote_path,
            "remote_name": row["remote_name"],
            "latest_game_version": row["latest_game_version"],
            "entity_key": row["entity_key"],
            "target_group": row["target_group"],
            "resource_type": row["resource_type"],
        }
    for row in fact_rows:
        metadata_json = row["metadata_json"]
        metadata: dict[str, object] = {}
        if isinstance(metadata_json, str) and metadata_json.strip():
            decoded = json.loads(metadata_json)
            if isinstance(decoded, dict):
                metadata = decoded
        remote_path = str(row["remote_path"])
        merged[remote_path] = {
            "remote_path": remote_path,
            "remote_name": row["file_name"],
            "latest_game_version": metadata.get("game_version") or _extract_version_from_name(str(row["file_name"])),
            "entity_key": metadata.get("entity_key"),
            "target_group": metadata.get("target_group"),
            "resource_type": metadata.get("resource_type"),
            "sha256": row["sha256"],
            "packaged_at": row["packaged_at"],
            "uploaded_at": row["uploaded_at"],
        }
    return [merged[key] for key in sorted(merged.keys(), key=str.casefold)]


def build_database_records_for_export(
    *,
    database_path: Path,
    run_id: str,
) -> dict[str, dict[str, object]]:
    """按 database v2 结构导出 active entity records。"""

    return build_database_export_plan(database_path=database_path, run_id=run_id).entries


def build_database_export_plan(
    *,
    database_path: Path,
    run_id: str,
) -> DatabaseExportPlan:
    """构造 database v2 active entries 与历史迁移计划。"""

    records = _load_database_record_states(database_path=database_path, run_id=run_id)
    archive_moves = tuple(_collect_archive_moves(records))
    excluded_remote_paths = {item.remote_path for item in archive_moves}
    entries = _finalize_database_records(records, excluded_remote_paths=excluded_remote_paths)
    return DatabaseExportPlan(entries=entries, archive_moves=archive_moves)


def build_report_changes(
    *,
    database_path: Path,
    run_id: str,
) -> list[dict[str, object]]:
    """构造最终 report 所需的本轮变动集。"""

    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT remote_path, file_name, sha256, packaged_at, uploaded_at, metadata_json
            FROM new_file_facts
            WHERE run_id = ?
            ORDER BY remote_path ASC
            """,
            (run_id,),
        ).fetchall()
    results: list[dict[str, object]] = []
    for row in rows:
        metadata_json = row["metadata_json"]
        metadata: dict[str, object] = {}
        if isinstance(metadata_json, str) and metadata_json.strip():
            decoded = json.loads(metadata_json)
            if isinstance(decoded, dict):
                metadata = decoded
        results.append(
            {
                "remote_path": row["remote_path"],
                "file_name": row["file_name"],
                "sha256": row["sha256"],
                "packaged_at": row["packaged_at"],
                "uploaded_at": row["uploaded_at"],
                "game_version": metadata.get("game_version"),
                "entity_key": metadata.get("entity_key"),
                "target_group": metadata.get("target_group"),
                "resource_type": metadata.get("resource_type"),
            }
        )
    return results


def _load_database_record_states(
    *,
    database_path: Path,
    run_id: str,
) -> dict[str, dict[str, object]]:
    with sqlite3.connect(database_path) as connection:
        _initialize_connection(connection)
        connection.row_factory = sqlite3.Row
        remote_rows = connection.execute(
            """
            SELECT
                entry_key,
                remote_path,
                remote_name,
                latest_game_version,
                entity_key,
                target_group,
                resource_type,
                raw_entry_json
            FROM remote_database_entries
            WHERE run_id = ?
            ORDER BY entry_key ASC
            """,
            (run_id,),
        ).fetchall()
        fact_rows = connection.execute(
            """
            SELECT remote_path, file_name, sha256, packaged_at, uploaded_at, metadata_json
            FROM new_file_facts
            WHERE run_id = ?
            ORDER BY remote_path ASC
            """,
            (run_id,),
        ).fetchall()

    records: dict[str, dict[str, object]] = {}
    for row in remote_rows:
        for candidate in _build_remote_artifact_candidates(row):
            _merge_database_record(records, candidate=candidate, source_rank=0)
    for row in fact_rows:
        candidate = _build_new_file_artifact_candidate(row)
        if candidate is not None:
            _merge_database_record(records, candidate=candidate, source_rank=1)
    return records


def _build_remote_artifact_candidates(row: sqlite3.Row) -> list[dict[str, object]]:
    raw_entry = _load_json_object(row["raw_entry_json"])
    row_context = {
        "entry_key": _optional_str(row["entry_key"]),
        "remote_path": _optional_str(row["remote_path"]),
        "remote_name": _optional_str(row["remote_name"]),
        "version": _optional_str(row["latest_game_version"]),
        "entity_key": _optional_str(row["entity_key"]),
        "target_group": _optional_str(row["target_group"]),
        "resource_type": _optional_str(row["resource_type"]),
    }
    candidates: list[dict[str, object]] = []
    artifact_payload = raw_entry.get("artifact")
    if isinstance(artifact_payload, dict):
        candidate = _build_artifact_candidate(
            artifact_payload=artifact_payload,
            base_payload=raw_entry,
            row_context=row_context,
        )
        if candidate is not None:
            return [candidate]

    versions_obj = raw_entry.get("versions")
    if isinstance(versions_obj, list) and versions_obj:
        active_versions = [
            item
            for item in versions_obj
            if isinstance(item, dict) and not bool(item.get("is_archived"))
        ]
        if not active_versions:
            active_versions = [item for item in versions_obj if isinstance(item, dict)]
        for item in active_versions:
            candidate = _build_artifact_candidate(
                artifact_payload=item,
                base_payload=raw_entry,
                row_context=row_context,
            )
            if candidate is not None:
                candidates.append(candidate)
        if candidates:
            return candidates

    if raw_entry:
        candidate = _build_artifact_candidate(
            artifact_payload=raw_entry,
            base_payload=raw_entry,
            row_context=row_context,
        )
        if candidate is not None:
            return [candidate]

    candidate = _build_artifact_candidate(
        artifact_payload={},
        base_payload=raw_entry,
        row_context=row_context,
    )
    return [candidate] if candidate is not None else []


def _build_new_file_artifact_candidate(row: sqlite3.Row) -> dict[str, object] | None:
    metadata = _load_json_object(row["metadata_json"])
    row_context = {
        "remote_path": _optional_str(row["remote_path"]),
        "remote_name": _optional_str(row["file_name"]),
        "version": None,
        "entity_key": None,
        "target_group": None,
        "resource_type": None,
        "sha256": _optional_str(row["sha256"]),
        "packaged_at": _optional_str(row["packaged_at"]),
        "uploaded_at": _optional_str(row["uploaded_at"]),
    }
    return _build_artifact_candidate(
        artifact_payload=metadata,
        base_payload=metadata,
        row_context=row_context,
    )


def _build_artifact_candidate(
    *,
    artifact_payload: dict[str, object],
    base_payload: dict[str, object],
    row_context: dict[str, str | None],
) -> dict[str, object] | None:
    remote_path = _coalesce_optional_str(
        _optional_str(artifact_payload.get("remote_path")),
        row_context.get("remote_path"),
    )
    remote_name = _coalesce_optional_str(
        _optional_str(artifact_payload.get("remote_name")),
        row_context.get("remote_name"),
    )
    if remote_name is None and remote_path is not None:
        remote_name = Path(remote_path).name

    parsed_name = _parse_archive_name(remote_name)
    target_group = _coalesce_optional_str(
        _optional_str(artifact_payload.get("target_group")),
        _optional_str(base_payload.get("target_group")),
        row_context.get("target_group"),
        _infer_target_group_from_remote_path(remote_path),
    )
    entity_key = _coalesce_optional_str(
        _optional_str(artifact_payload.get("entity_key")),
        _optional_str(base_payload.get("entity_key")),
        parsed_name.get("entity_key"),
        row_context.get("entity_key"),
    )
    artifact_type = _coalesce_optional_str(
        _normalize_artifact_type(artifact_payload.get("type")),
        _normalize_artifact_type(artifact_payload.get("artifact_type")),
        _normalize_artifact_type(artifact_payload.get("resource_type")),
        _normalize_artifact_type(base_payload.get("resource_type")),
        _normalize_artifact_type(row_context.get("resource_type")),
        parsed_name.get("artifact_type"),
    )
    version = _coalesce_optional_str(
        _optional_str(artifact_payload.get("version")),
        _optional_str(artifact_payload.get("game_version")),
        _optional_str(base_payload.get("latest_game_version")),
        row_context.get("version"),
        parsed_name.get("version"),
    )
    sha256 = _coalesce_optional_str(
        _optional_str(artifact_payload.get("sha256")),
        _optional_str(base_payload.get("sha256")),
        row_context.get("sha256"),
    )
    packaged_at = _coalesce_optional_str(
        _optional_str(artifact_payload.get("packaged_at")),
        _optional_str(base_payload.get("packaged_at")),
        row_context.get("packaged_at"),
    )
    uploaded_at = _coalesce_optional_str(
        _optional_str(artifact_payload.get("uploaded_at")),
        _optional_str(base_payload.get("uploaded_at")),
        row_context.get("uploaded_at"),
    )
    if (
        entity_key is None
        or remote_path is None
        or remote_name is None
        or artifact_type is None
        or version is None
        or sha256 is None
        or packaged_at is None
        or uploaded_at is None
    ):
        return None

    entity_id = _coerce_int(artifact_payload.get("id"))
    if entity_id is None:
        entity_id = _coerce_int(artifact_payload.get("entity_id"))
    if entity_id is None:
        entity_id = _coerce_int(base_payload.get("id"))
    if entity_id is None:
        entity_id = _coerce_int(base_payload.get("entity_id"))
    if entity_id is None:
        entity_id = _parse_entity_id(entity_key)
    if entity_id is None:
        return None

    alias = _coalesce_optional_str(
        _optional_str(artifact_payload.get("alias")),
        _optional_str(artifact_payload.get("entity_alias")),
        _optional_str(base_payload.get("alias")),
        _optional_str(base_payload.get("entity_alias")),
        _infer_entity_alias(entity_key, target_group),
    )
    return {
        "entity_key": entity_key,
        "entity_id": entity_id,
        "alias": alias,
        "artifact": {
            "type": artifact_type,
            "version": version,
            "remote_path": remote_path,
            "remote_name": remote_name,
            "sha256": sha256,
            "packaged_at": packaged_at,
            "uploaded_at": uploaded_at,
        },
    }


def _merge_database_record(
    records: dict[str, dict[str, object]],
    *,
    candidate: dict[str, object],
    source_rank: int,
) -> None:
    entity_key = str(candidate["entity_key"])
    entity_id = candidate["entity_id"]
    alias = candidate["alias"]
    artifact = candidate["artifact"]
    if not isinstance(entity_id, int) or not isinstance(artifact, dict):
        return
    record = records.setdefault(
        entity_key,
        {
            "id": entity_id,
            "alias": alias if isinstance(alias, str) else None,
            "_artifacts": {},
        },
    )
    if record.get("id") is None:
        record["id"] = entity_id
    if record.get("alias") is None and isinstance(alias, str):
        record["alias"] = alias
    artifacts = record["_artifacts"]
    if not isinstance(artifacts, dict):
        artifacts = {}
        record["_artifacts"] = artifacts
    artifact_key = (artifact["type"], artifact["version"])
    existing = artifacts.get(artifact_key)
    candidate_rank = _artifact_rank(artifact, source_rank=source_rank)
    if existing is None or candidate_rank >= existing["rank"]:
        artifacts[artifact_key] = {
            "artifact": artifact,
            "rank": candidate_rank,
            "source_rank": source_rank,
        }


def _finalize_database_records(
    records: dict[str, dict[str, object]],
    *,
    excluded_remote_paths: set[str] | None = None,
) -> dict[str, dict[str, object]]:
    finalized: dict[str, dict[str, object]] = {}
    excluded = excluded_remote_paths or set()
    for entity_key in sorted(records.keys(), key=str.casefold):
        record = records[entity_key]
        entity_id = record.get("id")
        artifacts_state = record.get("_artifacts")
        if not isinstance(entity_id, int) or not isinstance(artifacts_state, dict):
            continue
        artifacts = [
            item["artifact"]
            for item in artifacts_state.values()
            if isinstance(item, dict)
            and isinstance(item.get("artifact"), dict)
            and str(item["artifact"].get("remote_path") or "") not in excluded
        ]
        artifacts = _filter_superseded_artifacts(artifacts)
        if not artifacts:
            continue
        finalized[entity_key] = {
            "id": entity_id,
            "alias": record.get("alias") if isinstance(record.get("alias"), str) else None,
            "artifacts": artifacts,
        }
    return finalized


def _collect_archive_moves(
    records: dict[str, dict[str, object]],
) -> list[DatabaseArchiveMove]:
    moves: list[DatabaseArchiveMove] = []
    seen_paths: set[str] = set()
    for entity_key, record in records.items():
        artifacts_state = record.get("_artifacts")
        if not isinstance(artifacts_state, dict):
            continue
        new_all_versions = [
            _version_sort_key(str(item["artifact"].get("version")))
            for item in artifacts_state.values()
            if isinstance(item, dict)
            and item.get("source_rank") == 1
            and isinstance(item.get("artifact"), dict)
            and item["artifact"].get("type") == "ALL"
            and isinstance(item["artifact"].get("version"), str)
        ]
        if not new_all_versions:
            continue
        newest_all_version = max(new_all_versions)
        for item in artifacts_state.values():
            if not isinstance(item, dict) or item.get("source_rank") != 0:
                continue
            artifact = item.get("artifact")
            if not isinstance(artifact, dict):
                continue
            artifact_type = str(artifact.get("type") or "")
            if artifact_type not in {"VO", "SFX", "MUSIC"}:
                continue
            version = artifact.get("version")
            remote_path = artifact.get("remote_path")
            remote_name = artifact.get("remote_name")
            if (
                not isinstance(version, str)
                or not isinstance(remote_path, str)
                or not isinstance(remote_name, str)
                or remote_path in seen_paths
            ):
                continue
            if _version_sort_key(version) >= newest_all_version:
                continue
            target_group = _infer_target_group_from_remote_path(remote_path)
            if target_group is None:
                continue
            seen_paths.add(remote_path)
            moves.append(
                DatabaseArchiveMove(
                    entity_key=entity_key,
                    artifact_type=artifact_type,
                    version=version,
                    remote_path=remote_path,
                    remote_name=remote_name,
                    target_group=target_group,
                )
            )
    return sorted(moves, key=lambda item: (item.target_group, item.entity_key, item.remote_path))


def _filter_superseded_artifacts(artifacts: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(artifacts, key=_artifact_sort_key)


def _artifact_rank(artifact: dict[str, object], *, source_rank: int) -> tuple[int, str, str, str]:
    return (
        source_rank,
        str(artifact.get("uploaded_at") or ""),
        str(artifact.get("packaged_at") or ""),
        str(artifact.get("remote_path") or ""),
    )


def _artifact_sort_key(artifact: dict[str, object]) -> tuple[tuple[int, ...], int, str]:
    version = artifact.get("version")
    artifact_type = artifact.get("type")
    remote_name = artifact.get("remote_name")
    return (
        _version_sort_key(version if isinstance(version, str) else ""),
        _ARTIFACT_TYPE_ORDER.get(str(artifact_type), 99),
        str(remote_name or ""),
    )


def _version_sort_key(version: str) -> tuple[int, ...]:
    parts = version.split(".")
    normalized: list[int] = []
    for part in parts:
        try:
            normalized.append(int(part))
        except ValueError:
            normalized.append(0)
    return tuple(normalized)


def _parse_archive_name(remote_name: str | None) -> dict[str, str | None]:
    if remote_name is None:
        return {"entity_key": None, "version": None, "artifact_type": None}
    match = _ARCHIVE_NAME_PATTERN.match(remote_name)
    if match is None:
        return {"entity_key": None, "version": None, "artifact_type": None}
    return {
        "entity_key": match.group("entity_key"),
        "version": match.group("version"),
        "artifact_type": match.group("artifact_type").upper(),
    }


def _normalize_artifact_type(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if normalized in _ARTIFACT_TYPE_ORDER:
        return normalized
    return None


def _infer_target_group_from_remote_path(remote_path: str | None) -> str | None:
    if remote_path is None:
        return None
    parent_name = Path(remote_path).parent.name.strip()
    return parent_name or None


def _parse_entity_id(entity_key: str) -> int | None:
    head, *_ = entity_key.split("·", 1)
    try:
        return int(head)
    except ValueError:
        return None


def _infer_entity_alias(entity_key: str, target_group: str | None) -> str | None:
    if target_group != "champions":
        return None
    parts = [part.strip() for part in entity_key.split("·")]
    if len(parts) < 2 or not parts[1]:
        return None
    return parts[1]


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _coalesce_optional_str(*values: object) -> str | None:
    for value in values:
        normalized = _optional_str(value)
        if normalized is not None:
            return normalized
    return None


def _load_json_object(raw_value: object) -> dict[str, object]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return {}
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return decoded
    return {}


def _initialize_connection(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS runtime_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_control (
            run_id TEXT PRIMARY KEY,
            task_production_open INTEGER NOT NULL DEFAULT 1,
            pipeline_status TEXT,
            final_summary_path TEXT,
            upload_phase_status TEXT NOT NULL DEFAULT 'open',
            producer_finished_at TEXT,
            drained_at TEXT,
            finalized_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS upload_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            local_path TEXT NOT NULL,
            remote_path TEXT NOT NULL,
            task_type TEXT NOT NULL DEFAULT 'archive',
            status TEXT NOT NULL DEFAULT 'queued',
            payload_json TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_retry_at TEXT,
            claimed_by TEXT,
            claimed_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_upload_tasks_run_status
        ON upload_tasks(run_id, status);

        CREATE TABLE IF NOT EXISTS new_file_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            local_path TEXT NOT NULL,
            remote_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            sha256 TEXT,
            packaged_at TEXT,
            uploaded_at TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_new_file_facts_run_remote
        ON new_file_facts(run_id, remote_path);

        CREATE TABLE IF NOT EXISTS sync_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            available_at TEXT NOT NULL,
            claimed_by TEXT,
            claimed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sync_outbox_run_status
        ON sync_outbox(run_id, status, available_at);

        CREATE TABLE IF NOT EXISTS remote_database_entries (
            run_id TEXT NOT NULL,
            entry_key TEXT NOT NULL,
            remote_path TEXT,
            remote_name TEXT,
            latest_game_version TEXT,
            entity_key TEXT,
            target_group TEXT,
            resource_type TEXT,
            raw_entry_json TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            PRIMARY KEY (run_id, entry_key)
        );

        CREATE INDEX IF NOT EXISTS idx_remote_database_entries_run_version
        ON remote_database_entries(run_id, latest_game_version);
        """
    )


def _upsert_runtime_meta(connection: sqlite3.Connection, *, key: str, value: str) -> None:
    now = _now()
    connection.execute(
        """
        INSERT INTO runtime_meta(key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        (key, value, now),
    )


def _upsert_run_control(connection: sqlite3.Connection, *, run_id: str) -> None:
    now = _now()
    connection.execute(
        """
        INSERT INTO run_control(
            run_id,
            task_production_open,
            upload_phase_status,
            created_at,
            updated_at
        )
        VALUES (?, 1, 'open', ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            updated_at = excluded.updated_at
        """,
        (run_id, now, now),
    )


def _replace_remote_database_entries(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    remote_database_payload: dict[str, object],
) -> int:
    connection.execute("DELETE FROM remote_database_entries WHERE run_id = ?", (run_id,))
    rows = _normalize_remote_database_entries(remote_database_payload)
    if not rows:
        return 0
    now = _now()
    connection.executemany(
        """
        INSERT INTO remote_database_entries(
            run_id,
            entry_key,
            remote_path,
            remote_name,
            latest_game_version,
            entity_key,
            target_group,
            resource_type,
            raw_entry_json,
            imported_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                run_id,
                row["entry_key"],
                row["remote_path"],
                row["remote_name"],
                row["latest_game_version"],
                row["entity_key"],
                row["target_group"],
                row["resource_type"],
                json.dumps(row["raw_entry"], ensure_ascii=False, sort_keys=True),
                now,
            )
            for row in rows
        ],
    )
    return len(rows)


def _normalize_remote_database_entries(
    payload: dict[str, object],
) -> list[dict[str, Any]]:
    if payload.get("schema_version") != 2:
        raise ValueError("database.json 仅支持 schema_version=2。")
    entries_obj = payload.get("entries")
    if not isinstance(entries_obj, dict):
        raise ValueError("database.json entries 必须是 object。")
    normalized = []
    for entity_key, raw_entity in entries_obj.items():
        if not isinstance(raw_entity, dict):
            continue
        raw_artifacts = raw_entity.get("artifacts")
        if not isinstance(raw_artifacts, list):
            continue
        entity_alias = _optional_str(raw_entity.get("alias"))
        entity_id = _coerce_int(raw_entity.get("id"))
        for index, raw_artifact in enumerate(raw_artifacts):
            if not isinstance(raw_artifact, dict):
                continue
            remote_path = _optional_str(raw_artifact.get("remote_path"))
            remote_name = _optional_str(raw_artifact.get("remote_name"))
            if remote_name is None and remote_path is not None:
                remote_name = Path(remote_path).name
            artifact_type = _coalesce_optional_str(
                _normalize_artifact_type(raw_artifact.get("type")),
                _normalize_artifact_type(raw_artifact.get("resource_type")),
                _parse_archive_name(remote_name).get("artifact_type"),
            )
            version = _coalesce_optional_str(
                _optional_str(raw_artifact.get("version")),
                _optional_str(raw_artifact.get("game_version")),
                _extract_version_from_name(remote_name),
            )
            target_group = _infer_target_group_from_remote_path(remote_path)
            normalized.append(
                {
                    "entry_key": f"{entity_key}|{artifact_type or 'artifact'}|{version or index}",
                    "remote_path": remote_path,
                    "remote_name": remote_name,
                    "latest_game_version": version,
                    "entity_key": str(entity_key),
                    "target_group": target_group,
                    "resource_type": artifact_type,
                    "raw_entry": {
                        "entity_key": str(entity_key),
                        "id": entity_id,
                        "alias": entity_alias,
                        "target_group": target_group,
                        "artifact": raw_artifact,
                    },
                }
            )
    return normalized


def _resolve_latest_remote_path(versions_obj: list[object]) -> str | None:
    latest_remote_path = None
    for item in versions_obj:
        if not isinstance(item, dict):
            continue
        if bool(item.get("is_archived")):
            continue
        latest_remote_path = _optional_str(item.get("remote_path")) or latest_remote_path
    if latest_remote_path is not None:
        return latest_remote_path
    for item in reversed(versions_obj):
        if isinstance(item, dict):
            latest_remote_path = _optional_str(item.get("remote_path"))
            if latest_remote_path is not None:
                return latest_remote_path
    return None


def _extract_version_from_name(remote_name: str | None) -> str | None:
    if remote_name is None:
        return None
    match = _VERSION_PATTERN.search(remote_name)
    if match is None:
        return None
    return match.group("version")


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _measure_local_path_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        total_bytes = 0
        for child in path.rglob("*"):
            if child.is_file():
                total_bytes += child.stat().st_size
        return total_bytes
    return 0


def _now() -> str:
    return datetime.now().astimezone().isoformat()
