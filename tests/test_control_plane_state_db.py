"""state.sqlite3 状态库测试。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from rift_audio_pipeline.control_plane.state_db import build_database_export_plan
from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.control_plane.state_db import record_new_file_fact


def test_bootstrap_state_database_should_import_database_v2_entries(
    tmp_path: Path,
) -> None:
    """应创建最小状态库并导入 database v2 快照。"""

    result = bootstrap_state_database(
        database_path=tmp_path / "runtime" / "state.sqlite3",
        run_id="run-123",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-10T08:00:00+08:00",
            "archive_remote_root": "/apps/test-data/",
            "meta_remote_root": "/apps/test-meta/",
            "entry_count": 1,
            "entries": {
                "1·annie·黑暗之女·安妮": {
                    "id": 1,
                    "alias": "annie",
                    "artifacts": [
                        {
                            "type": "VO",
                            "version": "16.5",
                            "remote_path": "/apps/test/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
                            "remote_name": "1·annie·黑暗之女·安妮-16.5-VO.7z",
                            "sha256": "annie-vo-hash",
                            "packaged_at": "2026-03-10T07:58:31+00:00",
                            "uploaded_at": "2026-03-10T08:00:00+00:00",
                        }
                    ],
                }
            },
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
        "1·annie·黑暗之女·安妮|VO|16.5",
        "/apps/test/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
        "1·annie·黑暗之女·安妮-16.5-VO.7z",
        "16.5",
        "1·annie·黑暗之女·安妮",
    )
    assert runtime_meta == ("run-123",)


def test_bootstrap_state_database_should_support_database_v2_entries_object(
    tmp_path: Path,
) -> None:
    """应兼容新版 database v2 的 entries object。"""

    result = bootstrap_state_database(
        database_path=tmp_path / "runtime" / "state.sqlite3",
        run_id="run-789",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-14T01:05:00+08:00",
            "archive_remote_root": "/apps/rift-audio-pipeline-data/",
            "meta_remote_root": "/apps/rift-audio-pipeline-meta/",
            "entry_count": 1,
            "entries": {
                "103·ahri·九尾妖狐·阿狸": {
                    "id": 103,
                    "alias": "ahri",
                    "artifacts": [
                        {
                            "type": "ALL",
                            "version": "16.5",
                            "remote_path": "/apps/rift-audio-pipeline-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
                            "remote_name": "103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
                            "sha256": "hash-all",
                            "packaged_at": "2026-03-10T07:58:31+00:00",
                            "uploaded_at": "2026-03-10T08:00:00+00:00",
                        },
                        {
                            "type": "VO",
                            "version": "16.6",
                            "remote_path": "/apps/rift-audio-pipeline-data/champions/103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
                            "remote_name": "103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
                            "sha256": "hash-vo",
                            "packaged_at": "2026-03-14T00:53:31+00:00",
                            "uploaded_at": "2026-03-14T00:54:12+00:00",
                        },
                    ],
                }
            },
        },
    )

    assert result.imported_remote_entries == 2
    with sqlite3.connect(result.database_path) as connection:
        remote_entries = connection.execute(
            """
            SELECT entry_key, remote_path, remote_name, latest_game_version, entity_key, resource_type
            FROM remote_database_entries
            WHERE run_id = ?
            ORDER BY entry_key ASC
            """,
            ("run-789",),
        ).fetchall()

    assert remote_entries == [
        (
            "103·ahri·九尾妖狐·阿狸|ALL|16.5",
            "/apps/rift-audio-pipeline-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
            "103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
            "16.5",
            "103·ahri·九尾妖狐·阿狸",
            "ALL",
        ),
        (
            "103·ahri·九尾妖狐·阿狸|VO|16.6",
            "/apps/rift-audio-pipeline-data/champions/103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
            "103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
            "16.6",
            "103·ahri·九尾妖狐·阿狸",
            "VO",
        ),
    ]


def test_bootstrap_state_database_should_reject_non_v2_payload(tmp_path: Path) -> None:
    """默认不兼容旧 schema，bootstrap 应直接拒绝。"""

    with pytest.raises(ValueError, match="schema_version=2"):
        bootstrap_state_database(
            database_path=tmp_path / "runtime" / "state.sqlite3",
            run_id="run-legacy",
            remote_database_payload={"entries": []},
        )


def test_build_database_export_plan_should_archive_older_single_type_when_new_all_uploaded(
    tmp_path: Path,
) -> None:
    """新 ALL 上传后，应把更老的单类型产物列入 `_old_versions` 迁移计划。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-archive",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-14T00:00:00+08:00",
            "archive_remote_root": "/apps/test-data/",
            "meta_remote_root": "/apps/test-meta/",
            "entry_count": 1,
            "entries": {
                "103·ahri·九尾妖狐·阿狸": {
                    "id": 103,
                    "alias": "ahri",
                    "artifacts": [
                        {
                            "type": "VO",
                            "version": "16.3",
                            "remote_path": "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.3-VO.7z",
                            "remote_name": "103·ahri·九尾妖狐·阿狸-16.3-VO.7z",
                            "sha256": "old-vo",
                            "packaged_at": "2026-03-10T00:00:00+08:00",
                            "uploaded_at": "2026-03-10T00:10:00+08:00",
                        },
                        {
                            "type": "SFX",
                            "version": "16.4",
                            "remote_path": "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.4-SFX.7z",
                            "remote_name": "103·ahri·九尾妖狐·阿狸-16.4-SFX.7z",
                            "sha256": "old-sfx",
                            "packaged_at": "2026-03-11T00:00:00+08:00",
                            "uploaded_at": "2026-03-11T00:10:00+08:00",
                        },
                    ],
                }
            },
        },
    )
    record_new_file_fact(
        database_path=state_db_path,
        run_id="run-archive",
        local_path="/tmp/new-all.7z",
        remote_path="/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
        file_name="103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
        sha256="new-all",
        packaged_at="2026-03-14T00:00:00+08:00",
        uploaded_at="2026-03-14T00:05:00+08:00",
        metadata={
            "entity_id": 103,
            "entity_key": "103·ahri·九尾妖狐·阿狸",
            "target_group": "champions",
            "resource_type": "ALL",
            "game_version": "16.5",
        },
    )

    plan = build_database_export_plan(database_path=state_db_path, run_id="run-archive")

    assert [item.remote_path for item in plan.archive_moves] == [
        "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.3-VO.7z",
        "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.4-SFX.7z",
    ]
    assert plan.entries["103·ahri·九尾妖狐·阿狸"]["artifacts"] == [
        {
            "type": "ALL",
            "version": "16.5",
            "remote_path": "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
            "remote_name": "103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
            "sha256": "new-all",
            "packaged_at": "2026-03-14T00:00:00+08:00",
            "uploaded_at": "2026-03-14T00:05:00+08:00",
        }
    ]


def test_build_database_export_plan_should_keep_newer_single_type_after_older_all(
    tmp_path: Path,
) -> None:
    """旧 ALL 后面来了更高版本单类型时，两者都应保持 active。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-keep",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-14T00:00:00+08:00",
            "archive_remote_root": "/apps/test-data/",
            "meta_remote_root": "/apps/test-meta/",
            "entry_count": 1,
            "entries": {
                "103·ahri·九尾妖狐·阿狸": {
                    "id": 103,
                    "alias": "ahri",
                    "artifacts": [
                        {
                            "type": "ALL",
                            "version": "16.5",
                            "remote_path": "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
                            "remote_name": "103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
                            "sha256": "all-165",
                            "packaged_at": "2026-03-10T00:00:00+08:00",
                            "uploaded_at": "2026-03-10T00:10:00+08:00",
                        }
                    ],
                }
            },
        },
    )
    record_new_file_fact(
        database_path=state_db_path,
        run_id="run-keep",
        local_path="/tmp/new-vo.7z",
        remote_path="/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
        file_name="103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
        sha256="new-vo",
        packaged_at="2026-03-14T00:00:00+08:00",
        uploaded_at="2026-03-14T00:05:00+08:00",
        metadata={
            "entity_id": 103,
            "entity_key": "103·ahri·九尾妖狐·阿狸",
            "target_group": "champions",
            "resource_type": "VO",
            "game_version": "16.6",
        },
    )

    plan = build_database_export_plan(database_path=state_db_path, run_id="run-keep")

    assert plan.archive_moves == ()
    assert plan.entries["103·ahri·九尾妖狐·阿狸"]["artifacts"] == [
        {
            "type": "ALL",
            "version": "16.5",
            "remote_path": "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
            "remote_name": "103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
            "sha256": "all-165",
            "packaged_at": "2026-03-10T00:00:00+08:00",
            "uploaded_at": "2026-03-10T00:10:00+08:00",
        },
        {
            "type": "VO",
            "version": "16.6",
            "remote_path": "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
            "remote_name": "103·ahri·九尾妖狐·阿狸-16.6-VO.7z",
            "sha256": "new-vo",
            "packaged_at": "2026-03-14T00:00:00+08:00",
            "uploaded_at": "2026-03-14T00:05:00+08:00",
        },
    ]
