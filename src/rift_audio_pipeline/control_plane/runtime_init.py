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
from rift_audio_pipeline.baidu.pan import DOWNLOAD_CONNECT_TIMEOUT
from rift_audio_pipeline.baidu.pan import DOWNLOAD_MAX_ATTEMPTS
from rift_audio_pipeline.baidu.pan import DOWNLOAD_READ_TIMEOUT
from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.simulation import MOCK_BAIDU_ENV_VAR
from rift_audio_pipeline.simulation import SIMULATION_ENV_VAR

DOWNLOAD_CONNECT_TIMEOUT_ENV_VAR = "RIFT_BAIDU_DOWNLOAD_CONNECT_TIMEOUT_SECONDS"
DOWNLOAD_READ_TIMEOUT_ENV_VAR = "RIFT_BAIDU_DOWNLOAD_READ_TIMEOUT_SECONDS"
DOWNLOAD_MAX_ATTEMPTS_ENV_VAR = "RIFT_BAIDU_DOWNLOAD_MAX_ATTEMPTS"


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
    archive_remote_root: str,
    meta_remote_root: str,
    plane_config: ControlPlaneConfig | None,
    provided_baidu_token_payload: dict[str, object] | None = None,
) -> RuntimeInitializationResult:
    """准备百度凭据、本地 database 与 state.sqlite3。

    Args:
        run_id: 当前运行 ID。
        runtime_dir: 当前运行的本地工作目录。
        archive_remote_root: 百度远端产物根目录。
        meta_remote_root: 百度远端数据库与日志根目录。
        plane_config: control plane 访问配置；仅在需要向 plane 拉百度凭据时使用。
        provided_baidu_token_payload: dispatch payload 中显式提供的百度 access token。

    Returns:
        RuntimeInitializationResult: 初始化阶段产物。

    Raises:
        ValueError: 当百度凭据缺少必需字段或 database 非 JSON object 时抛出。
    """

    runtime_dir.mkdir(parents=True, exist_ok=True)
    _emit_runtime_log(f"run_id={run_id} runtime_dir={runtime_dir}")
    token_payload, token_source = _resolve_baidu_token_payload(
        plane_config=plane_config,
        provided_baidu_token_payload=provided_baidu_token_payload,
    )
    _validate_baidu_token_payload(token_payload, source_label=token_source)
    _emit_runtime_log(
        f"run_id={run_id} baidu_token_source={token_source} token_fields={','.join(sorted(token_payload.keys()))}"
    )
    baidu_token_file = runtime_dir / "baidu-token.json"
    baidu_token_file.write_text(
        json.dumps(token_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _emit_runtime_log(f"run_id={run_id} baidu_token_file={baidu_token_file}")
    database_file = runtime_dir / "database.json"
    _emit_runtime_log(f"run_id={run_id} database_file={database_file}")
    _download_or_initialize_database(
        token_payload=token_payload,
        archive_remote_root=archive_remote_root,
        meta_remote_root=meta_remote_root,
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
    _emit_runtime_log(
        f"run_id={run_id} state_db_file={state_db_result.database_path} imported_remote_entries={state_db_result.imported_remote_entries}"
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
    parser.add_argument("--archive-remote-root", required=True)
    parser.add_argument("--meta-remote-root", required=True)
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
        archive_remote_root=args.archive_remote_root,
        meta_remote_root=args.meta_remote_root,
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
    plane_config: ControlPlaneConfig | None,
    provided_baidu_token_payload: dict[str, object] | None,
) -> tuple[dict[str, object], str]:
    """决定当前运行应使用的百度凭据来源。"""

    if provided_baidu_token_payload is not None:
        return dict(provided_baidu_token_payload), "inputs.payload.baidu"
    if plane_config is None:
        raise ValueError(
            "未提供 inputs.payload.baidu，且 control plane base_url 为空，无法获取百度凭据。"
        )
    return _fetch_baidu_token_payload(plane_config=plane_config), "plane /api/baidu/token"


def _validate_baidu_token_payload(payload: dict[str, object], *, source_label: str) -> None:
    """校验百度凭据负载。"""

    required_fields = ("access_token",)
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
    archive_remote_root: str,
    meta_remote_root: str,
    database_file: Path,
) -> None:
    if os.getenv(SIMULATION_ENV_VAR) == "1" or os.getenv(MOCK_BAIDU_ENV_VAR) == "1":
        _emit_runtime_log("simulation_mode=1 database.json will be initialized locally")
        database_file.write_text(
            json.dumps(
                _build_empty_database_payload(
                    archive_remote_root=archive_remote_root,
                    meta_remote_root=meta_remote_root,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return
    download_connect_timeout = _read_positive_float_env(
        DOWNLOAD_CONNECT_TIMEOUT_ENV_VAR,
        default=DOWNLOAD_CONNECT_TIMEOUT,
    )
    download_read_timeout = _read_positive_float_env(
        DOWNLOAD_READ_TIMEOUT_ENV_VAR,
        default=DOWNLOAD_READ_TIMEOUT,
    )
    download_max_attempts = _read_positive_int_env(
        DOWNLOAD_MAX_ATTEMPTS_ENV_VAR,
        default=DOWNLOAD_MAX_ATTEMPTS,
    )
    client = BaiduPanClient(
        credentials=BaiduCredentials(
            access_token=str(token_payload["access_token"]),
        ),
        remote_dir=meta_remote_root,
        token_store=None,
        allow_token_refresh=False,
        download_connect_timeout=download_connect_timeout,
        download_read_timeout=download_read_timeout,
        download_max_attempts=download_max_attempts,
        download_log=_emit_runtime_log,
    )
    remote_database_path = f"{meta_remote_root.rstrip('/')}/database.json"
    _emit_runtime_log(
        "download_database "
        f"remote_path={remote_database_path} "
        f"connect_timeout={download_connect_timeout}s "
        f"max_read_timeout={download_read_timeout}s "
        f"max_attempts={download_max_attempts}"
    )
    try:
        client.ensure_directory("")
        client.download_file(remote_database_path, database_file)
        _emit_runtime_log(f"database_download_success remote_path={remote_database_path}")
    except FileNotFoundError:
        _emit_runtime_log(
            f"database_missing remote_path={remote_database_path}; initialize empty database.json"
        )
        database_file.write_text(
            json.dumps(
                _build_empty_database_payload(
                    archive_remote_root=archive_remote_root,
                    meta_remote_root=meta_remote_root,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        client.close()


def _emit_runtime_log(message: str) -> None:
    """把 runtime_init 关键阶段直接输出到 stdout。"""

    print(f"[runtime_init] {message}", flush=True)


def _read_positive_float_env(name: str, *, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return float(default)
    value = float(raw_value)
    if value <= 0:
        raise ValueError(f"{name} 必须大于 0，当前值：{raw_value}")
    return value


def _read_positive_int_env(name: str, *, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return int(default)
    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{name} 必须大于 0，当前值：{raw_value}")
    return value


def _build_empty_database_payload(
    *,
    archive_remote_root: str,
    meta_remote_root: str,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "updated_at": datetime.now().astimezone().isoformat(),
        "archive_remote_root": _normalize_remote_root(archive_remote_root),
        "meta_remote_root": _normalize_remote_root(meta_remote_root),
        "entry_count": 0,
        "entries": {},
    }


def _normalize_remote_root(remote_root: str) -> str:
    stripped = remote_root.rstrip("/")
    if not stripped:
        return "/"
    return f"{stripped}/"


if __name__ == "__main__":
    raise SystemExit(main())
