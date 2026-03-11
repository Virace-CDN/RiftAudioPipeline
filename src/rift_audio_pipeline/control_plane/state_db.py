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
    database_obj = payload.get("database")
    if isinstance(database_obj, dict):
        normalized: list[dict[str, Any]] = []
        for entry_key, raw_entry in database_obj.items():
            if not isinstance(raw_entry, dict):
                continue
            latest_remote_name = _optional_str(raw_entry.get("latest_remote_name"))
            latest_version = _optional_str(raw_entry.get("latest_game_version")) or _extract_version_from_name(
                latest_remote_name
            )
            versions_obj = raw_entry.get("versions")
            latest_remote_path = None
            if isinstance(versions_obj, list) and versions_obj:
                latest_remote_path = _resolve_latest_remote_path(versions_obj)
            normalized.append(
                {
                    "entry_key": str(entry_key),
                    "remote_path": latest_remote_path,
                    "remote_name": latest_remote_name,
                    "latest_game_version": latest_version,
                    "entity_key": _optional_str(raw_entry.get("entity_key")),
                    "target_group": _optional_str(raw_entry.get("target_group")),
                    "resource_type": _optional_str(raw_entry.get("resource_type")),
                    "raw_entry": raw_entry,
                }
            )
        return normalized

    entries_obj = payload.get("entries")
    if isinstance(entries_obj, list):
        normalized = []
        for index, raw_entry in enumerate(entries_obj):
            if not isinstance(raw_entry, dict):
                continue
            remote_path = _optional_str(raw_entry.get("remote_path"))
            remote_name = _optional_str(raw_entry.get("remote_name"))
            if remote_name is None and remote_path is not None:
                remote_name = Path(remote_path).name
            normalized.append(
                {
                    "entry_key": remote_path or remote_name or f"entry-{index}",
                    "remote_path": remote_path,
                    "remote_name": remote_name,
                    "latest_game_version": _extract_version_from_name(remote_name),
                    "entity_key": _optional_str(raw_entry.get("entity_key")),
                    "target_group": _optional_str(raw_entry.get("target_group")),
                    "resource_type": _optional_str(raw_entry.get("resource_type")),
                    "raw_entry": raw_entry,
                }
            )
        return normalized

    return []


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


def _now() -> str:
    return datetime.now().astimezone().isoformat()
