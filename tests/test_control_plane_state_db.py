"""state.sqlite3 状态库测试。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database


def test_bootstrap_state_database_should_create_minimal_schema_and_import_entries(
    tmp_path: Path,
) -> None:
    """应创建最小状态库并导入远端 database 快照。"""

    result = bootstrap_state_database(
        database_path=tmp_path / "runtime" / "state.sqlite3",
        run_id="run-123",
        remote_database_payload={
            "database": {
                "champions|vo|annie": {
                    "entity_key": "annie",
                    "target_group": "champions",
                    "resource_type": "VO",
                    "latest_game_version": "16.5",
                    "latest_remote_name": "1·annie·黑暗之女·安妮-16.5-VO.7z",
                    "versions": [
                        {
                            "remote_path": "/apps/test/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
                            "remote_name": "1·annie·黑暗之女·安妮-16.5-VO.7z",
                            "game_version": "16.5",
                            "is_archived": False,
                        }
                    ],
                }
            }
        },
    )

    assert result.database_path.exists()
    assert result.imported_remote_entries == 1

    with sqlite3.connect(result.database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        remote_entry = connection.execute(
            """
            SELECT entry_key, remote_path, remote_name, latest_game_version, entity_key
            FROM remote_database_entries
            WHERE run_id = ?
            """,
            ("run-123",),
        ).fetchone()
        runtime_meta = connection.execute(
            "SELECT value FROM runtime_meta WHERE key = 'last_bootstrap_run_id'"
        ).fetchone()

    assert {
        "runtime_meta",
        "run_control",
        "upload_tasks",
        "new_file_facts",
        "sync_outbox",
        "remote_database_entries",
    }.issubset(tables)
    assert remote_entry == (
        "champions|vo|annie",
        "/apps/test/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
        "1·annie·黑暗之女·安妮-16.5-VO.7z",
        "16.5",
        "annie",
    )
    assert runtime_meta == ("run-123",)


def test_bootstrap_state_database_should_support_flat_entries_payload(tmp_path: Path) -> None:
    """应兼容较简单的 entries 列表快照。"""

    result = bootstrap_state_database(
        database_path=tmp_path / "runtime" / "state.sqlite3",
        run_id="run-456",
        remote_database_payload={
            "entries": [
                {
                    "remote_path": "/apps/test/maps/11·map11·召唤师峡谷-16.4-VO.7z",
                    "remote_name": "11·map11·召唤师峡谷-16.4-VO.7z",
                }
            ]
        },
    )

    with sqlite3.connect(result.database_path) as connection:
        remote_entry = connection.execute(
            """
            SELECT remote_path, remote_name, latest_game_version
            FROM remote_database_entries
            WHERE run_id = ?
            """,
            ("run-456",),
        ).fetchone()

    assert remote_entry == (
        "/apps/test/maps/11·map11·召唤师峡谷-16.4-VO.7z",
        "11·map11·召唤师峡谷-16.4-VO.7z",
        "16.4",
    )
