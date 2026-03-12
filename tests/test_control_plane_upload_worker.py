"""upload worker 与状态机测试。"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.control_plane.state_db import enqueue_upload_task
from rift_audio_pipeline.control_plane.state_db import mark_task_production_closed
from rift_audio_pipeline.control_plane.upload_worker import UploadWorker
from rift_audio_pipeline.control_plane.upload_worker import UploadWorkerConfig


def test_upload_worker_should_drain_queue_and_record_file_fact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """upload worker 应消费上传任务，记录文件事实，并在封口后排空退出。"""

    state_db_path = tmp_path / "runtime" / "state.sqlite3"
    bootstrap_state_database(
        database_path=state_db_path,
        run_id="run-1",
        remote_database_payload={},
    )
    archive_path = tmp_path / "output" / "packages" / "16.5" / "champions" / "1·annie·黑暗之女·安妮-16.5-VO.7z"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text("archive-bytes", encoding="utf-8")
    enqueue_upload_task(
        database_path=state_db_path,
        run_id="run-1",
        local_path=str(archive_path),
        remote_path="/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
        payload={
            "remote_relative_path": "VO/champions/1·annie·黑暗之女·安妮-16.5-VO.7z",
            "game_version": "16.5",
        },
    )
    mark_task_production_closed(
        database_path=state_db_path,
        run_id="run-1",
        pipeline_status="success",
        final_summary_path=str(tmp_path / "output" / "logs" / "run-1" / "run.json"),
    )
    baidu_token_file = tmp_path / "runtime" / "baidu-token.json"
    baidu_token_file.parent.mkdir(parents=True, exist_ok=True)
    baidu_token_file.write_text(
        json.dumps(
            {
                "access_token": "access-token",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    upload_calls: list[tuple[Path, str]] = []

    def _fake_upload_file(
        self,
        local_path: Path,
        remote_path: str,
        rtype: int = 3,
        progress_callback=None,
    ):
        upload_calls.append((local_path, remote_path))
        if progress_callback is not None:
            progress_callback({"phase": "precreate", "status": "started"})
            progress_callback({"phase": "create", "status": "completed"})
        return {"path": remote_path, "rtype": rtype}

    monkeypatch.setattr(
        "rift_audio_pipeline.control_plane.upload_worker.BaiduPanClient.upload_file",
        _fake_upload_file,
    )

    worker = UploadWorker(
        UploadWorkerConfig(
            run_id="run-1",
            state_db_path=state_db_path,
            baidu_token_file=baidu_token_file,
            baidu_remote_root="/apps/test",
            worker_id="worker-1",
            delete_local_file_after_upload=True,
            poll_interval_ms=10,
        )
    )
    worker.serve()

    with sqlite3.connect(state_db_path) as connection:
        task_row = connection.execute(
            "SELECT status FROM upload_tasks WHERE run_id = ?",
            ("run-1",),
        ).fetchone()
        fact_row = connection.execute(
            "SELECT remote_path, file_name, sha256 FROM new_file_facts WHERE run_id = ?",
            ("run-1",),
        ).fetchone()
        run_control = connection.execute(
            "SELECT upload_phase_status FROM run_control WHERE run_id = ?",
            ("run-1",),
        ).fetchone()

    assert upload_calls == [
        (archive_path, "VO/champions/1·annie·黑暗之女·安妮-16.5-VO.7z")
    ]
    assert task_row == ("done",)
    assert fact_row is not None
    assert fact_row[0] == "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.5-VO.7z"
    assert fact_row[1] == archive_path.name
    assert isinstance(fact_row[2], str) and fact_row[2]
    assert run_control == ("drained",)
    assert not archive_path.exists()
