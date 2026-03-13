"""上传阶段排空后的统一收尾 worker。"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time

from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.simulation import BAIDU_FAILURE_MODE_ENV_VAR
from rift_audio_pipeline.simulation import MOCK_BAIDU_ENV_VAR
from rift_audio_pipeline.simulation import SIMULATION_ENV_VAR
from rift_audio_pipeline.control_plane.state_db import DatabaseArchiveMove
from rift_audio_pipeline.control_plane.state_db import DatabaseExportPlan
from rift_audio_pipeline.control_plane.state_db import build_database_export_plan
from rift_audio_pipeline.control_plane.state_db import build_report_changes
from rift_audio_pipeline.control_plane.state_db import get_upload_phase_status
from rift_audio_pipeline.control_plane.state_db import mark_upload_phase_finalized
from rift_audio_pipeline.pipeline.logging import LogRelayClient
from rift_audio_pipeline.pipeline.logging import LogSinkConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="database.json 收尾与远端轮转。")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--state-db-path", type=Path, required=True)
    parser.add_argument("--baidu-token-file", type=Path, required=True)
    parser.add_argument("--archive-remote-root", required=True)
    parser.add_argument("--meta-remote-root", required=True)
    parser.add_argument("--database-file", type=Path, required=True)
    parser.add_argument("--log-root", type=Path)
    parser.add_argument("--relay-state-file", type=Path)
    parser.add_argument("--relay-socket-path", type=Path)
    parser.add_argument("--final-status", required=True)
    parser.add_argument("--poll-interval-ms", type=int, default=500)
    parser.add_argument("--history-limit", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    wait_until_drained(
        state_db_path=args.state_db_path,
        run_id=args.run_id,
        poll_interval_ms=args.poll_interval_ms,
    )
    token_payload = json.loads(args.baidu_token_file.read_text(encoding="utf-8"))
    if not isinstance(token_payload, dict):
        raise ValueError(f"baidu token 文件顶层必须是对象：{args.baidu_token_file}")
    archive_client = BaiduPanClient(
        credentials=BaiduCredentials(
            access_token=_require_str(token_payload, "access_token"),
        ),
        remote_dir=args.archive_remote_root,
        token_store=None,
        allow_token_refresh=False,
    )
    meta_client = BaiduPanClient(
        credentials=BaiduCredentials(
            access_token=_require_str(token_payload, "access_token"),
        ),
        remote_dir=args.meta_remote_root,
        token_store=None,
        allow_token_refresh=False,
    )
    try:
        export_plan = build_database_export_plan(
            database_path=args.state_db_path,
            run_id=args.run_id,
        )
        if os.getenv(SIMULATION_ENV_VAR) != "1" and os.getenv(MOCK_BAIDU_ENV_VAR) != "1":
            move_archived_artifacts(
                client=archive_client,
                archive_remote_root=args.archive_remote_root,
                archive_moves=export_plan.archive_moves,
            )
        payload = build_database_payload(
            archive_remote_root=args.archive_remote_root,
            meta_remote_root=args.meta_remote_root,
            export_plan=export_plan,
        )
        args.database_file.parent.mkdir(parents=True, exist_ok=True)
        args.database_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if os.getenv(SIMULATION_ENV_VAR) == "1" or os.getenv(MOCK_BAIDU_ENV_VAR) == "1":
            failure_mode = os.getenv(BAIDU_FAILURE_MODE_ENV_VAR, "none")
            if failure_mode in {"log", "both"}:
                raise RuntimeError("本地联调模拟：log upload failure")
            if args.log_root is not None:
                log_receipt = args.log_root.parent / "simulation" / "log_upload.json"
                run_log_dir = _find_run_log_dir(args.log_root, args.run_id)
                log_receipt.parent.mkdir(parents=True, exist_ok=True)
                log_receipt.write_text(
                    json.dumps(
                        {
                            "recorded_at": datetime.now().astimezone().isoformat(),
                            "run_id": args.run_id,
                            "remote_root": f"{args.meta_remote_root.rstrip('/')}/logs/{run_log_dir.parent.name}/{args.run_id}",
                            "files": sorted(
                                str(path.relative_to(run_log_dir))
                                for path in run_log_dir.rglob("*")
                                if path.is_file()
                            ),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        else:
            rotate_and_upload_database(
                client=meta_client,
                remote_root=args.meta_remote_root,
                database_file=args.database_file,
                history_limit=args.history_limit,
            )
    finally:
        archive_client.close()
        meta_client.close()
    if args.relay_state_file is not None and args.relay_socket_path is not None:
        relay_client = LogRelayClient(
            run_id=args.run_id,
            relay_state_file=args.relay_state_file,
            relay_socket_file=args.relay_socket_path,
            config=LogSinkConfig(enabled=True),
            spawn_process=False,
        )
        relay_client.attach()
        relay_client.report_run_result(
            build_report_payload(
                state_db_path=args.state_db_path,
                run_id=args.run_id,
                status=args.final_status,
            )
        )
        relay_client.shutdown()
    mark_upload_phase_finalized(
        database_path=args.state_db_path,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "run_id": args.run_id,
                "database_file": str(args.database_file),
                "history_limit": args.history_limit,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def wait_until_drained(
    *,
    state_db_path: Path,
    run_id: str,
    poll_interval_ms: int,
) -> None:
    while True:
        phase_status = get_upload_phase_status(database_path=state_db_path, run_id=run_id)
        if phase_status == "drained":
            return
        time.sleep(poll_interval_ms / 1000)


def build_database_payload(
    *,
    archive_remote_root: str,
    meta_remote_root: str,
    export_plan: DatabaseExportPlan,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "updated_at": datetime.now().astimezone().isoformat(),
        "archive_remote_root": _normalize_remote_root(archive_remote_root),
        "meta_remote_root": _normalize_remote_root(meta_remote_root),
        "entry_count": len(export_plan.entries),
        "entries": export_plan.entries,
    }


def build_report_payload(
    *,
    state_db_path: Path,
    run_id: str,
    status: str,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "status": status,
        "finished_at": datetime.now().astimezone().isoformat(),
        "changes": build_report_changes(database_path=state_db_path, run_id=run_id),
    }


def rotate_and_upload_database(
    *,
    client: BaiduPanClient,
    remote_root: str,
    database_file: Path,
    history_limit: int,
) -> None:
    listing = _list_database_directory(client)
    remote_entries = listing.get("list")
    if not isinstance(remote_entries, list):
        remote_entries = []
    current_database_path = f"{remote_root.rstrip('/')}/database.json"
    timestamp_prefix = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    current_exists = False
    history_paths: list[str] = []
    for item in remote_entries:
        if not isinstance(item, dict):
            continue
        path_value = item.get("path")
        if not isinstance(path_value, str):
            continue
        if path_value == current_database_path:
            current_exists = True
        if path_value.startswith(f"{remote_root.rstrip('/')}/database-") and path_value.endswith(
            ".json"
        ):
            history_paths.append(path_value)
    if current_exists:
        client.rename_path(current_database_path, f"database-{timestamp_prefix}.json")
        history_paths.append(f"{remote_root.rstrip('/')}/database-{timestamp_prefix}.json")
    client.upload_file(local_path=database_file, remote_path="database.json")
    history_paths = sorted(set(history_paths), reverse=True)
    if len(history_paths) > history_limit:
        client.delete_paths(history_paths[history_limit:])


def move_archived_artifacts(
    *,
    client: BaiduPanClient,
    archive_remote_root: str,
    archive_moves: tuple[DatabaseArchiveMove, ...],
) -> None:
    archive_root = archive_remote_root.rstrip("/")
    for item in archive_moves:
        destination_dir = f"{archive_root}/_old_versions/{item.target_group}"
        client.ensure_directory(destination_dir)
        client.move_path(
            source_path=item.remote_path,
            destination_dir=destination_dir,
            new_name=item.remote_name,
        )


def _list_database_directory(client: BaiduPanClient) -> dict[str, object]:
    client.ensure_directory("")
    return client.list_files("")


def _require_str(payload: dict[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} 必须是非空字符串。")
    return value


def _find_run_log_dir(log_root: Path, run_id: str) -> Path:
    candidates = sorted(log_root.glob(f"*/{run_id}"))
    if not candidates:
        raise FileNotFoundError(f"未找到 run_id 对应日志目录：{run_id}")
    return candidates[0]


def _normalize_remote_root(remote_root: str) -> str:
    stripped = remote_root.rstrip("/")
    if not stripped:
        return "/"
    return f"{stripped}/"


if __name__ == "__main__":
    raise SystemExit(main())
