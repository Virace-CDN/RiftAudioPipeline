"""GitHub Actions 运行前初始化。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path

from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.baidu.oauth import resolve_token_store
from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.simulation import MOCK_BAIDU_ENV_VAR
from rift_audio_pipeline.simulation import SIMULATION_ENV_VAR


@dataclass(frozen=True, slots=True)
class RuntimeInitializationResult:
    """运行前初始化产物。"""

    run_id: str
    runtime_dir: Path
    baidu_token_file: Path
    database_file: Path
    state_db_file: Path
    token_payload: dict[str, object]
    imported_remote_entries: int


def initialize_runtime(
    *,
    run_id: str,
    runtime_dir: Path,
    baidu_remote_root: str,
    plane_config: ControlPlaneConfig,
    provided_baidu_token_payload: dict[str, object] | None = None,
) -> RuntimeInitializationResult:
    """准备百度凭据、本地 database 与 state.sqlite3。

    Args:
        run_id: 当前运行 ID。
        runtime_dir: 当前运行的本地工作目录。
        baidu_remote_root: 百度远端根目录。
        plane_config: control plane 访问配置。
        provided_baidu_token_payload: dispatch payload 中显式提供的百度凭据。

    Returns:
        RuntimeInitializationResult: 初始化阶段产物。

    Raises:
        ValueError: 当百度凭据缺少必需字段或 database 非 JSON object 时抛出。
    """

    runtime_dir.mkdir(parents=True, exist_ok=True)
    token_payload, token_source = _resolve_baidu_token_payload(
        plane_config=plane_config,
        provided_baidu_token_payload=provided_baidu_token_payload,
    )
    _validate_baidu_token_payload(token_payload, source_label=token_source)
    baidu_token_file = runtime_dir / "baidu-token.json"
    baidu_token_file.write_text(
        json.dumps(token_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    database_file = runtime_dir / "database.json"
    _download_or_initialize_database(
        token_payload=token_payload,
        baidu_remote_root=baidu_remote_root,
        database_file=database_file,
    )
    database_payload = json.loads(database_file.read_text(encoding="utf-8"))
    if not isinstance(database_payload, dict):
        raise ValueError(f"database.json 顶层必须是 JSON object：{database_file}")
    state_db_result = bootstrap_state_database(
        database_path=runtime_dir / "state.sqlite3",
        run_id=run_id,
        remote_database_payload=database_payload,
    )
    return RuntimeInitializationResult(
        run_id=run_id,
        runtime_dir=runtime_dir,
        baidu_token_file=baidu_token_file,
        database_file=database_file,
        state_db_file=state_db_result.database_path,
        token_payload=token_payload,
        imported_remote_entries=state_db_result.imported_remote_entries,
    )


def build_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数。"""

    parser = argparse.ArgumentParser(description="初始化 GitHub Actions 运行前上下文。")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--baidu-remote-root", required=True)
    parser.add_argument("--plane-base-url", required=True)
    parser.add_argument("--plane-bearer-token")
    parser.add_argument("--plane-access-client-id")
    parser.add_argument("--plane-access-client-secret")
    parser.add_argument("--plane-timeout-seconds", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""

    args = build_parser().parse_args(argv)
    result = initialize_runtime(
        run_id=args.run_id,
        runtime_dir=args.runtime_dir,
        baidu_remote_root=args.baidu_remote_root,
        plane_config=ControlPlaneConfig(
            base_url=args.plane_base_url,
            bearer_token=args.plane_bearer_token,
            access_client_id=args.plane_access_client_id,
            access_client_secret=args.plane_access_client_secret,
            timeout_seconds=args.plane_timeout_seconds,
        ),
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "runtime_dir": str(result.runtime_dir),
                "baidu_token_file": str(result.baidu_token_file),
                "database_file": str(result.database_file),
                "state_db_file": str(result.state_db_file),
                "imported_remote_entries": result.imported_remote_entries,
                "token_fields": sorted(result.token_payload.keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _fetch_baidu_token_payload(*, plane_config: ControlPlaneConfig) -> dict[str, object]:
    client = ControlPlaneClient(plane_config)
    return client.request_json("GET", "/api/baidu/token")


def _resolve_baidu_token_payload(
    *,
    plane_config: ControlPlaneConfig,
    provided_baidu_token_payload: dict[str, object] | None,
) -> tuple[dict[str, object], str]:
    """决定当前运行应使用的百度凭据来源。"""

    if provided_baidu_token_payload is not None:
        return dict(provided_baidu_token_payload), "inputs.payload.baidu"
    return _fetch_baidu_token_payload(plane_config=plane_config), "plane /api/baidu/token"


def _validate_baidu_token_payload(payload: dict[str, object], *, source_label: str) -> None:
    """校验百度凭据负载。"""

    required_fields = ("app_key", "secret_key", "refresh_token")
    missing = [
        field_name
        for field_name in required_fields
        if not isinstance(payload.get(field_name), str) or not str(payload[field_name]).strip()
    ]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{source_label} 缺少必需字段：{joined}")


def _download_or_initialize_database(
    *,
    token_payload: dict[str, object],
    baidu_remote_root: str,
    database_file: Path,
) -> None:
    if os.getenv(SIMULATION_ENV_VAR) == "1" or os.getenv(MOCK_BAIDU_ENV_VAR) == "1":
        database_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "updated_at": datetime.now().astimezone().isoformat(),
                    "entries": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return
    token_store = resolve_token_store(database_file.parent / "baidu-oauth-token.json")
    client = BaiduPanClient(
        credentials=BaiduCredentials(
            app_key=str(token_payload["app_key"]),
            secret_key=str(token_payload["secret_key"]),
            refresh_token=str(token_payload["refresh_token"]),
        ),
        remote_dir=baidu_remote_root,
        token_store=token_store,
    )
    remote_database_path = f"{baidu_remote_root.rstrip('/')}/database.json"
    try:
        client.download_file(remote_database_path, database_file)
    except FileNotFoundError:
        database_file.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "updated_at": datetime.now().astimezone().isoformat(),
                    "entries": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
