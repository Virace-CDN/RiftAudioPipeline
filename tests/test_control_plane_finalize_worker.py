"""finalize worker 测试。"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
import time

from rift_audio_pipeline.control_plane.finalize_worker import build_database_payload
from rift_audio_pipeline.control_plane.finalize_worker import rotate_and_upload_database
from rift_audio_pipeline.control_plane.finalize_worker import wait_until_drained
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
            "entries": [
                {
                    "remote_path": "/apps/test/VO/champions/old.7z",
                    "remote_name": "old.7z",
                }
            ]
        },
    )
    record_new_file_fact(
        database_path=state_db_path,
        run_id="run-1",
        local_path="/tmp/new.7z",
        remote_path="/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
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

    payload = build_database_payload(state_db_path=state_db_path, run_id="run-1")

    assert payload["entry_count"] == 2
    entries = payload["entries"]
    assert isinstance(entries, list)
    remote_paths = [entry["remote_path"] for entry in entries]
    assert "/apps/test/VO/champions/old.7z" in remote_paths
    assert "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.5-VO.7z" in remote_paths


def test_rotate_and_upload_database_should_rotate_current_and_prune_history(tmp_path: Path) -> None:
    """应轮转远端 database.json，并只保留最近若干份历史。"""

    class _FakeClient:
        def __init__(self) -> None:
            self.renames: list[tuple[str, str]] = []
            self.uploads: list[tuple[Path, str]] = []
            self.deletes: list[list[str]] = []

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

    assert client.renames
    assert client.renames[0][0] == "/apps/test/database.json"
    assert client.renames[0][1].startswith("database-")
    assert client.uploads == [(database_file, "database.json")]
    assert len(client.deletes) == 1
    assert len(client.deletes[0]) == 2


def test_wait_until_drained_should_return_after_upload_phase_drained(tmp_path: Path) -> None:
    """应等待直到 run_control.upload_phase_status 变为 drained。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-1",
        remote_database_payload={},
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
