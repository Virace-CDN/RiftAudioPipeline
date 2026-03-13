"""finalize worker 测试。"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import threading
import time

from rift_audio_pipeline.control_plane.finalize_worker import move_archived_artifacts
from rift_audio_pipeline.control_plane.finalize_worker import build_database_payload
from rift_audio_pipeline.control_plane.finalize_worker import rotate_and_upload_database
from rift_audio_pipeline.control_plane.finalize_worker import wait_until_drained
from rift_audio_pipeline.control_plane.state_db import DatabaseArchiveMove
from rift_audio_pipeline.control_plane.state_db import build_database_export_plan
from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.control_plane.state_db import mark_upload_phase_drained
from rift_audio_pipeline.control_plane.state_db import record_new_file_fact


def test_build_database_payload_should_merge_remote_snapshot_and_new_file_facts(
    tmp_path: Path,
) -> None:
    """应从远端快照和新文件事实生成新的 database payload。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-1",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-10T08:00:00+08:00",
            "archive_remote_root": "/apps/test-data/",
            "meta_remote_root": "/apps/test-meta/",
            "entry_count": 1,
            "entries": {
                "11·sr·召唤师峡谷": {
                    "id": 11,
                    "alias": None,
                    "artifacts": [
                        {
                            "type": "ALL",
                            "version": "16.4",
                            "remote_path": "/apps/test-data/maps/11·sr·召唤师峡谷-16.4-ALL.7z",
                            "remote_name": "11·sr·召唤师峡谷-16.4-ALL.7z",
                            "sha256": "old-hash",
                            "packaged_at": "2026-03-10T07:58:00+08:00",
                            "uploaded_at": "2026-03-10T08:00:00+08:00",
                        }
                    ],
                }
            },
        },
    )
    record_new_file_fact(
        database_path=state_db_path,
        run_id="run-1",
        local_path="/tmp/new.7z",
        remote_path="/apps/test/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
        file_name="1·annie·黑暗之女·安妮-16.5-VO.7z",
        sha256="abc123",
        packaged_at="2026-03-11T12:00:00+08:00",
        uploaded_at="2026-03-11T12:01:00+08:00",
        metadata={
            "game_version": "16.5",
            "entity_key": "1·annie·黑暗之女·安妮",
            "target_group": "champions",
            "resource_type": "VO",
        },
    )

    export_plan = build_database_export_plan(database_path=state_db_path, run_id="run-1")
    payload = build_database_payload(
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        export_plan=export_plan,
    )

    assert payload["entry_count"] == 2
    entries = payload["entries"]
    assert payload["schema_version"] == 2
    assert payload["archive_remote_root"] == "/apps/test-data/"
    assert payload["meta_remote_root"] == "/apps/test-meta/"
    assert isinstance(entries, dict)
    assert entries["11·sr·召唤师峡谷"]["id"] == 11
    assert entries["11·sr·召唤师峡谷"]["alias"] is None
    assert entries["11·sr·召唤师峡谷"]["artifacts"][0]["remote_path"] == (
        "/apps/test-data/maps/11·sr·召唤师峡谷-16.4-ALL.7z"
    )
    assert entries["1·annie·黑暗之女·安妮"]["id"] == 1
    assert entries["1·annie·黑暗之女·安妮"]["alias"] == "annie"
    assert entries["1·annie·黑暗之女·安妮"]["artifacts"][0]["type"] == "VO"
    assert entries["1·annie·黑暗之女·安妮"]["artifacts"][0]["remote_path"] == (
        "/apps/test/champions/1·annie·黑暗之女·安妮-16.5-VO.7z"
    )


def test_rotate_and_upload_database_should_rotate_current_and_prune_history(tmp_path: Path) -> None:
    """应轮转远端 database.json，并只保留最近若干份历史。"""

    class _FakeClient:
        def __init__(self) -> None:
            self.renames: list[tuple[str, str]] = []
            self.uploads: list[tuple[Path, str]] = []
            self.deletes: list[list[str]] = []
            self.created_dirs: list[str] = []

        def ensure_directory(self, dir_path: str):
            self.created_dirs.append(dir_path)
            return dir_path

        def list_files(self, dir_path: str, limit: int = 1000, start: int = 0):
            assert dir_path == ""
            return {
                "list": [
                    {"path": "/apps/test/database.json"},
                    {"path": "/apps/test/database-20260311T100000.json"},
                    {"path": "/apps/test/database-20260310T100000.json"},
                    {"path": "/apps/test/database-20260309T100000.json"},
                ]
            }

        def rename_path(self, source_path: str, new_name: str, ondup: str = "newcopy"):
            self.renames.append((source_path, new_name))
            return {"errno": 0}

        def upload_file(self, local_path: Path, remote_path: str, rtype: int = 3):
            self.uploads.append((local_path, remote_path))
            return {"errno": 0}

        def delete_paths(self, paths):
            self.deletes.append(list(paths))
            return {"errno": 0}

    client = _FakeClient()
    database_file = tmp_path / "runtime" / "database.json"
    database_file.parent.mkdir(parents=True, exist_ok=True)
    database_file.write_text("{}", encoding="utf-8")

    rotate_and_upload_database(
        client=client,  # type: ignore[arg-type]
        remote_root="/apps/test",
        database_file=database_file,
        history_limit=2,
    )

    assert client.created_dirs == [""]
    assert client.renames
    assert client.renames[0][0] == "/apps/test/database.json"
    assert client.renames[0][1].startswith("database-")
    assert client.uploads == [(database_file, "database.json")]
    assert len(client.deletes) == 1
    assert len(client.deletes[0]) == 2


def test_rotate_and_upload_database_should_create_remote_root_when_missing(tmp_path: Path) -> None:
    """远端 meta 目录缺失时应先自动创建，再上传 database.json。"""

    class _FakeClient:
        def __init__(self) -> None:
            self.created_dirs: list[str] = []
            self.uploads: list[tuple[Path, str]] = []

        def ensure_directory(self, dir_path: str):
            self.created_dirs.append(dir_path)
            return dir_path

        def list_files(self, dir_path: str, limit: int = 1000, start: int = 0):
            assert dir_path == ""
            return {"list": []}

        def upload_file(self, local_path: Path, remote_path: str, rtype: int = 3):
            self.uploads.append((local_path, remote_path))
            return {"errno": 0}

        def delete_paths(self, paths):
            del paths
            return {"errno": 0}

        def rename_path(self, source_path: str, new_name: str, ondup: str = "newcopy"):
            del source_path, new_name, ondup
            return {"errno": 0}

    client = _FakeClient()
    database_file = tmp_path / "runtime" / "database.json"
    database_file.parent.mkdir(parents=True, exist_ok=True)
    database_file.write_text("{}", encoding="utf-8")

    rotate_and_upload_database(
        client=client,  # type: ignore[arg-type]
        remote_root="/apps/test-meta",
        database_file=database_file,
        history_limit=2,
    )

    assert client.created_dirs == [""]
    assert client.uploads == [(database_file, "database.json")]


def test_move_archived_artifacts_should_create_history_dir_before_move() -> None:
    """归档旧单类型前应先确保 `_old_versions/<group>` 目录存在。"""

    class _FakeClient:
        def __init__(self) -> None:
            self.created_dirs: list[str] = []
            self.moves: list[tuple[str, str, str | None]] = []

        def ensure_directory(self, dir_path: str):
            self.created_dirs.append(dir_path)
            return dir_path

        def move_path(self, source_path: str, destination_dir: str, new_name: str | None = None, ondup: str = "newcopy"):
            del ondup
            self.moves.append((source_path, destination_dir, new_name))
            return {"errno": 0}

    client = _FakeClient()

    move_archived_artifacts(
        client=client,  # type: ignore[arg-type]
        archive_remote_root="/apps/test-data",
        archive_moves=(
            DatabaseArchiveMove(
                entity_key="103·ahri·九尾妖狐·阿狸",
                artifact_type="VO",
                version="16.4",
                remote_path="/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.4-VO.7z",
                remote_name="103·ahri·九尾妖狐·阿狸-16.4-VO.7z",
                target_group="champions",
            ),
        ),
    )

    assert client.created_dirs == ["/apps/test-data/_old_versions/champions"]
    assert client.moves == [
        (
            "/apps/test-data/champions/103·ahri·九尾妖狐·阿狸-16.4-VO.7z",
            "/apps/test-data/_old_versions/champions",
            "103·ahri·九尾妖狐·阿狸-16.4-VO.7z",
        )
    ]


def test_wait_until_drained_should_return_after_upload_phase_drained(tmp_path: Path) -> None:
    """应等待直到 run_control.upload_phase_status 变为 drained。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-1",
        remote_database_payload={
            "schema_version": 2,
            "updated_at": "2026-03-14T00:00:00+08:00",
            "archive_remote_root": "/apps/test-data/",
            "meta_remote_root": "/apps/test-meta/",
            "entry_count": 0,
            "entries": {},
        },
    )

    def _mark_later() -> None:
        time.sleep(0.1)
        mark_upload_phase_drained(database_path=state_db_path, run_id="run-1")

    thread = threading.Thread(target=_mark_later, daemon=True)
    thread.start()
    wait_until_drained(state_db_path=state_db_path, run_id="run-1", poll_interval_ms=20)
    thread.join(timeout=1.0)

    with sqlite3.connect(state_db_path) as connection:
        status = connection.execute(
            "SELECT upload_phase_status FROM run_control WHERE run_id = ?",
            ("run-1",),
        ).fetchone()
    assert status == ("drained",)
