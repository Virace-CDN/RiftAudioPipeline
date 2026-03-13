"""job runner / runtime init / log worker 测试。"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from tests._control_plane_capture import ControlPlaneCaptureServer
from rift_audio_pipeline.control_plane.job_runner import _build_control_plane_config
from rift_audio_pipeline.control_plane.job_runner import _resolve_run_id
from rift_audio_pipeline.control_plane.job_runner import build_pipeline_command
from rift_audio_pipeline.control_plane.job_runner import build_parser
from rift_audio_pipeline.control_plane.job_runner import build_runtime_plan
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.runtime import process_output as process_output_module
from rift_audio_pipeline.control_plane.runtime.job_support import UploadQueueSnapshot
from rift_audio_pipeline.control_plane.runtime.job_support import _estimate_upload_wait_seconds
from rift_audio_pipeline.control_plane.runtime.job_support import _should_mirror_upload_worker_line
from rift_audio_pipeline.control_plane.runtime_init import initialize_runtime
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchBaiduInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchExecutionInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchGameInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchIdTargets
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchManifestInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchManifestsInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchMetadataInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchPayload
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchRequestInputs
from rift_audio_pipeline.control_plane.workflow_dispatch import DispatchTargetsInputs


def test_initialize_runtime_should_fetch_baidu_token_and_prepare_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """初始化脚本应向 plane 拉取百度凭据并准备本地 database 与 state.sqlite3。"""

    server = ControlPlaneCaptureServer(
        bootstrap_payload={},
        baidu_token_payload={
            "access_token": "plane-access-token",
        },
    )
    server.start()
    downloaded: list[tuple[str, Path]] = []

    def _fake_download(self, remote_path: str, local_path: Path) -> dict[str, object]:
        downloaded.append((remote_path, local_path))
        local_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "updated_at": "2026-03-14T00:00:00+08:00",
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
                                    "version": "16.5",
                                    "remote_path": "/apps/test-meta/database.json",
                                    "remote_name": "11·sr·召唤师峡谷-16.5-ALL.7z",
                                    "sha256": "db-hash",
                                    "packaged_at": "2026-03-14T00:00:00+08:00",
                                    "uploaded_at": "2026-03-14T00:00:00+08:00",
                                }
                            ],
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {}

    monkeypatch.setattr(
        "rift_audio_pipeline.control_plane.runtime_init.BaiduPanClient.download_file",
        _fake_download,
    )
    monkeypatch.setattr(
        "rift_audio_pipeline.control_plane.runtime_init.BaiduPanClient.ensure_directory",
        lambda self, dir_path: self.remote_dir if dir_path == "" else dir_path,
    )
    try:
        result = initialize_runtime(
            run_id="12345",
            runtime_dir=tmp_path / "runtime",
            archive_remote_root="/apps/test-data",
            meta_remote_root="/apps/test-meta",
            plane_config=ControlPlaneConfig(base_url=server.base_url),
        )
    finally:
        server.close()

    assert server.baidu_token_requests == [{}]
    assert downloaded == [("/apps/test-meta/database.json", result.database_file)]
    assert result.token_payload["access_token"] == "plane-access-token"
    assert (
        json.loads(result.database_file.read_text(encoding="utf-8"))["entries"]["11·sr·召唤师峡谷"]["artifacts"][0]["remote_path"]
        == "/apps/test-meta/database.json"
    )
    assert result.state_db_file.exists()
    with sqlite3.connect(result.state_db_file) as connection:
        imported_entries = connection.execute(
            "SELECT entry_key, remote_path FROM remote_database_entries WHERE run_id = ?",
            ("12345",),
        ).fetchall()
        run_control = connection.execute(
            "SELECT task_production_open, upload_phase_status FROM run_control WHERE run_id = ?",
            ("12345",),
        ).fetchone()
    assert len(imported_entries) == 1
    assert imported_entries[0][1] == "/apps/test-meta/database.json"
    assert run_control == (1, "open")


def test_initialize_runtime_should_prefer_dispatch_baidu_token_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """dispatch payload 若显式提供百度凭据，则不再请求 plane token 接口。"""

    server = ControlPlaneCaptureServer(
        bootstrap_payload={},
        baidu_token_payload={
            "access_token": "plane-access-token",
        },
    )
    server.start()
    downloaded: list[tuple[str, Path]] = []

    def _fake_download(self, remote_path: str, local_path: Path) -> dict[str, object]:
        downloaded.append((remote_path, local_path))
        local_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "updated_at": "2026-03-14T00:00:00+08:00",
                    "archive_remote_root": "/apps/test-data/",
                    "meta_remote_root": "/apps/test-meta/",
                    "entry_count": 0,
                    "entries": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {}

    monkeypatch.setattr(
        "rift_audio_pipeline.control_plane.runtime_init.BaiduPanClient.download_file",
        _fake_download,
    )
    monkeypatch.setattr(
        "rift_audio_pipeline.control_plane.runtime_init.BaiduPanClient.ensure_directory",
        lambda self, dir_path: self.remote_dir if dir_path == "" else dir_path,
    )
    try:
        result = initialize_runtime(
            run_id="manual-run",
            runtime_dir=tmp_path / "runtime",
            archive_remote_root="/apps/test-data",
            meta_remote_root="/apps/test-meta",
            plane_config=ControlPlaneConfig(base_url=server.base_url),
            provided_baidu_token_payload={
                "access_token": "manual-access-token",
            },
        )
    finally:
        server.close()

    assert server.baidu_token_requests == []
    assert downloaded == [("/apps/test-meta/database.json", result.database_file)]
    assert result.token_payload == {
        "access_token": "manual-access-token",
    }


def test_initialize_runtime_should_require_plane_or_dispatch_baidu_token(
    tmp_path: Path,
) -> None:
    """未提供百度凭据且没有 plane 配置时，应给出明确错误。"""

    with pytest.raises(ValueError, match="inputs.payload.baidu"):
        initialize_runtime(
            run_id="manual-run",
            runtime_dir=tmp_path / "runtime",
            archive_remote_root="/apps/test-data",
            meta_remote_root="/apps/test-meta",
            plane_config=None,
        )


def test_build_pipeline_command_should_exclude_control_plane_flags_and_use_env_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pipeline 主线命令应只保留业务入参与本地 run_id。"""

    monkeypatch.setenv("GITHUB_RUN_ID", "99887766")
    assert _resolve_run_id(None) == "99887766"

    command = build_pipeline_command(
        payload=DispatchPayload(
            ref="main",
            inputs=DispatchInputs(
                request=DispatchRequestInputs(mode="remote", stage="mapping"),
                game=DispatchGameInputs(region="zh_CN"),
                manifests=DispatchManifestsInputs(
                    current=DispatchManifestInputs(
                        version="16.5",
                        lcu_url="https://lcu.example/16.5",
                        game_url="https://game.example/16.5",
                    ),
                    previous=DispatchManifestInputs(version="16.4"),
                ),
                targets=DispatchTargetsInputs(
                    champions=DispatchIdTargets(ids=(1, 103)),
                    maps=DispatchIdTargets(ids=(11,)),
                ),
                baidu=DispatchBaiduInputs(
                    access_token="manual-access-token",
                ),
                execution=DispatchExecutionInputs(
                    force_update=False,
                    max_workers=8,
                    download_retry_attempts=5,
                    entity_retry_attempts=2,
                    log_level="DEBUG",
                    archive_password="zip-secret",
                ),
                metadata=DispatchMetadataInputs(requested_by="github-actions"),
            ),
        ),
        run_id="99887766",
        output_root=Path("output"),
        temp_root=Path("temp"),
        log_root=Path("output/logs"),
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        relay_socket_path=Path("/tmp/rift-audio-pipeline/99887766.sock"),
        state_db_path=Path("runtime/99887766/state.sqlite3"),
        default_mode="remote",
        default_game_region="zh_CN",
        default_log_level="INFO",
    )

    assert command[:3] == [sys.executable, "-m", "rift_audio_pipeline.pipeline.cli"]
    assert "--run-id" in command
    assert "99887766" in command
    assert "--relay-socket-path" in command
    assert "/tmp/rift-audio-pipeline/99887766.sock" in command
    assert "--state-db-path" in command
    assert "runtime/99887766/state.sqlite3" in command
    assert "--archive-remote-root" in command
    assert "/apps/test-data" in command
    assert "--meta-remote-root" in command
    assert "/apps/test-meta" in command
    assert "--control-plane-base-url" not in command
    assert "--control-plane-bearer-token" not in command
    assert "--champion-ids" in command
    assert "1,103" in command
    assert "--archive-password" in command
    assert "zip-secret" in command


def test_build_pipeline_command_should_omit_relay_socket_when_relay_disabled() -> None:
    """无 plane 场景下，pipeline 主线不应再收到 relay socket 参数。"""

    command = build_pipeline_command(
        payload=DispatchPayload(
            ref="main",
            inputs=DispatchInputs(
                request=DispatchRequestInputs(mode="remote", stage="extract"),
                game=DispatchGameInputs(region="zh_CN"),
            ),
        ),
        run_id="manual-smoke",
        output_root=Path("output"),
        temp_root=Path("temp"),
        log_root=Path("output/logs"),
        archive_remote_root="/apps/test-data",
        meta_remote_root="/apps/test-meta",
        relay_socket_path=None,
        state_db_path=Path("runtime/manual-smoke/state.sqlite3"),
        default_mode="remote",
        default_game_region="zh_CN",
        default_log_level="INFO",
    )

    assert "--relay-socket-path" not in command


def test_build_runtime_plan_should_derive_runtime_paths(tmp_path: Path) -> None:
    """runtime plan 应统一派生 runtime/log/relay 相关路径。"""

    args = build_parser().parse_args(
        [
            "--ref",
            "main",
            "--dispatch-inputs-file",
            str(tmp_path / "dispatch-inputs.json"),
            "--storage-root",
            str(tmp_path / "storage"),
            "--output-root",
            str(tmp_path / "output"),
            "--temp-root",
            str(tmp_path / "temp"),
            "--control-plane-base-url",
            "https://plane.example",
        ]
    )

    plan = build_runtime_plan(args=args, run_id="99887766")

    assert plan.run_id == "99887766"
    assert plan.runtime_root == tmp_path / "storage" / "runs" / "99887766"
    assert plan.log_root == tmp_path / "output" / "logs"
    assert plan.log_dir.parent.parent == tmp_path / "output" / "logs"
    assert plan.log_dir.name == "99887766"
    assert (
        plan.relay_config_file == tmp_path / "storage" / "runs" / "99887766" / "relay-config.json"
    )
    assert (
        plan.upload_stdout_file
        == tmp_path / "storage" / "runs" / "99887766" / "upload-worker.stdout.log"
    )


def test_build_parser_should_default_to_single_upload_worker() -> None:
    """上传默认并发应保守收口到 1。"""

    args = build_parser().parse_args(
        [
            "--ref",
            "main",
            "--dispatch-inputs-file",
            "dispatch.json",
        ]
    )

    assert args.upload_worker_count == 1


def test_pump_process_output_should_mirror_to_stdout_and_log_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """子进程日志应同时写入文件和父进程 stdout。"""

    source = io.StringIO("line-one\nline-two")
    log_file = tmp_path / "upload-worker-01.stdout.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file.open("w", encoding="utf-8")
    mirrored_stdout = io.StringIO()
    monkeypatch.setattr(process_output_module.sys, "stdout", mirrored_stdout)

    process_output_module._pump_process_output(
        source=source,
        log_handle=log_handle,
        stream_label="upload-worker-01",
    )
    log_handle.close()

    assert log_file.read_text(encoding="utf-8") == "line-one\nline-two\n"
    assert mirrored_stdout.getvalue() == (
        "[upload-worker-01] line-one\n"
        "[upload-worker-01] line-two\n"
    )


def test_pump_process_output_should_keep_verbose_lines_in_file_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """详细上传进度应只落文件，不实时镜像到 shell。"""

    source = io.StringIO(
        '{"event":"upload_task_progress","task_id":1}\n'
        '{"event":"upload_task_completed","task_id":1}\n'
    )
    log_file = tmp_path / "upload-worker-01.stdout.log"
    log_handle = log_file.open("w", encoding="utf-8")
    mirrored_stdout = io.StringIO()
    monkeypatch.setattr(process_output_module.sys, "stdout", mirrored_stdout)

    process_output_module._pump_process_output(
        source=source,
        log_handle=log_handle,
        stream_label="upload-worker-01",
        mirror_predicate=_should_mirror_upload_worker_line,
    )
    log_handle.close()

    assert '"upload_task_progress"' in log_file.read_text(encoding="utf-8")
    assert '"upload_task_completed"' in log_file.read_text(encoding="utf-8")
    assert '"upload_task_progress"' not in mirrored_stdout.getvalue()
    assert '"upload_task_completed"' in mirrored_stdout.getvalue()


def test_should_mirror_upload_worker_line_should_filter_progress_only() -> None:
    """upload worker 详细分片进度不应镜像到父进程 stdout。"""

    assert _should_mirror_upload_worker_line(
        '{"event":"upload_task_started","task_id":1}\n'
    )
    assert not _should_mirror_upload_worker_line(
        '{"event":"upload_task_progress","task_id":1}\n'
    )


def test_build_control_plane_config_should_return_none_for_blank_base_url() -> None:
    """空 control plane 地址应被视为关闭 relay。"""

    args = build_parser().parse_args(
        [
            "--ref",
            "main",
            "--dispatch-inputs-file",
            "dispatch.json",
        ]
    )

    assert _build_control_plane_config(args) is None


def test_estimate_upload_wait_seconds_should_scale_for_large_files() -> None:
    """1-2GB 级文件上传等待不应过于激进。"""

    timeout_seconds = _estimate_upload_wait_seconds(
        UploadQueueSnapshot(
            unfinished_count=2,
            queued_count=1,
            claimed_count=1,
            retry_wait_count=0,
            done_count=0,
            remaining_bytes=2 * 1024 * 1024 * 1024,
            signature=((1, "claimed", "a"), (2, "queued", "b")),
        )
    )

    assert timeout_seconds >= 1800
