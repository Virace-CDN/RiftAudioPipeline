"""本地 mock control plane server。"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Lock
from threading import Thread
from urllib.parse import urlparse


_RUN_ENDPOINT_PATTERN = re.compile(r"^/api/pipeline/runs/(?P<run_id>[^/]+)/(?P<kind>heartbeat|report|logs)$")
_RUN_LOG_FINALIZE_ENDPOINT_PATTERN = re.compile(
    r"^/api/pipeline/runs/(?P<run_id>[^/]+)/logs/finalize$"
)


@dataclass(frozen=True, slots=True)
class MockControlPlaneConfig:
    """本地 mock control plane 配置。"""

    fixture_dir: Path
    storage_root: Path
    host: str = "127.0.0.1"
    port: int = 8788


class MockControlPlaneState:
    """保存 mock control plane 的响应 fixture 与收到的请求。"""

    def __init__(
        self,
        *,
        fixture_dir: Path,
        storage_root: Path,
    ) -> None:
        self._fixture_dir = fixture_dir
        self._storage_root = storage_root
        self._lock = Lock()
        self._bootstrap_sequence = 0
        self._heartbeat_sequences: dict[str, int] = defaultdict(int)
        self._log_event_sequences: dict[str, int] = defaultdict(int)
        self._bootstrap_response = self._load_fixture("bootstrap.json")
        self._heartbeat_response = self._load_optional_fixture(
            "heartbeat_response.json",
            default_payload={"accepted": True},
        )
        self._report_response = self._load_optional_fixture(
            "report_response.json",
            default_payload={"accepted": True},
        )
        self._log_event_response = self._load_optional_fixture(
            "log_event_response.json",
            default_payload={"accepted": True},
        )
        self._log_finalize_response = self._load_optional_fixture(
            "log_finalize_response.json",
            default_payload={"accepted": True},
        )
        self._baidu_token_response = self._load_optional_fixture(
            "baidu_token.json",
            default_payload={
                "app_key": "mock-baidu-app-key",
                "secret_key": "mock-baidu-secret-key",
                "refresh_token": "mock-baidu-refresh-token",
            },
        )

    def bootstrap_response(self) -> dict[str, object]:
        """返回 bootstrap 启动通知响应。"""

        return {"accepted": True, "persisted_at": _current_timestamp()}

    def baidu_token_response(self) -> dict[str, object]:
        """返回百度 token fixture。"""

        return dict(self._baidu_token_response)

    def heartbeat_response(self, run_id: str, payload: dict[str, object]) -> dict[str, object]:
        """返回 heartbeat 响应。"""

        response = dict(self._heartbeat_response)
        response.setdefault("accepted", True)
        response.setdefault("persisted_at", _current_timestamp())
        self._record_request(
            category="heartbeats",
            run_id=run_id,
            payload=payload,
            response=response,
        )
        self._write_run_state(
            run_id=run_id,
            source="heartbeat",
            payload={
                "status": payload.get("status"),
                "stage": _extract_stage(payload),
                "relay_runtime": _extract_relay_runtime(payload),
            },
        )
        return response

    def report_response(self, run_id: str, payload: dict[str, object]) -> dict[str, object]:
        """返回 report 响应。"""

        response = dict(self._report_response)
        response.setdefault("accepted", True)
        response.setdefault("persisted_at", _current_timestamp())
        self._record_request(
            category="report",
            run_id=run_id,
            payload=payload,
            response=response,
        )
        self._write_run_state(
            run_id=run_id,
            source="report",
            payload={
                "report_status": payload.get("status"),
                "finished_at": payload.get("finished_at"),
                "changes": payload.get("changes"),
            },
        )
        return response

    def log_event_response(self, run_id: str, payload: dict[str, object]) -> dict[str, object]:
        """返回实时日志事件响应。"""

        response = dict(self._log_event_response)
        response.setdefault("accepted", True)
        response.setdefault("persisted_at", _current_timestamp())
        event = payload.get("event")
        if isinstance(event, dict) and isinstance(event.get("seq"), int):
            response.setdefault("next_expected_seq", event["seq"] + 1)
        self._record_request(
            category="logs",
            run_id=run_id,
            payload=payload,
            response=response,
        )
        return response

    def log_finalize_response(self, run_id: str, payload: dict[str, object]) -> dict[str, object]:
        """返回日志终态摘要响应。"""

        response = dict(self._log_finalize_response)
        response.setdefault("accepted", True)
        response.setdefault("persisted_at", _current_timestamp())
        summary = payload.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("final_status"), str):
            response.setdefault("worker_status", summary["final_status"])
        self._record_request(
            category="logs_finalize",
            run_id=run_id,
            payload=payload,
            response=response,
        )
        self._write_run_state(
            run_id=run_id,
            source="logs_finalize",
            payload={
                "status": summary.get("final_status") if isinstance(summary, dict) else None,
                "stage": summary.get("final_stage") if isinstance(summary, dict) else None,
                "relay_runtime": _extract_relay_runtime_from_summary(summary),
                "terminal_summary": summary,
            },
        )
        return response

    def record_bootstrap_request(self, payload: dict[str, object]) -> None:
        """落盘 bootstrap 启动通知。"""

        self._record_request(
            category="bootstrap_requests",
            run_id=None,
            payload=payload,
            response=self.bootstrap_response(),
        )
        run_id = payload.get("run_id")
        if isinstance(run_id, str):
            self._write_run_state(
                run_id=run_id,
                source="bootstrap",
                payload={
                    "status": "started",
                    "started_at": payload.get("started_at"),
                },
            )

    def _record_request(
        self,
        *,
        category: str,
        run_id: str | None,
        payload: dict[str, object],
        response: dict[str, object],
    ) -> None:
        """把请求与响应统一落到存储目录。"""

        received_at = _current_timestamp()
        envelope = {
            "received_at": received_at,
            "payload": payload,
            "response": response,
        }
        if run_id is None:
            target_dir = self._storage_root / category
            with self._lock:
                self._bootstrap_sequence += 1
                sequence = self._bootstrap_sequence
            target_path = target_dir / f"{sequence:04d}.json"
        elif category == "heartbeats":
            target_dir = self._storage_root / "runs" / run_id / category
            with self._lock:
                self._heartbeat_sequences[run_id] += 1
                sequence = self._heartbeat_sequences[run_id]
            target_path = target_dir / f"{sequence:04d}.json"
        elif category == "logs":
            target_dir = self._storage_root / "runs" / run_id / category
            with self._lock:
                self._log_event_sequences[run_id] += 1
                sequence = self._log_event_sequences[run_id]
            target_path = target_dir / f"{sequence:04d}.json"
        else:
            target_dir = self._storage_root / "runs" / run_id
            target_path = target_dir / f"{category}.json"

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_run_state(
        self,
        *,
        run_id: str,
        source: str,
        payload: dict[str, object],
    ) -> None:
        """把当前 run 的聚合状态写到固定文件。"""

        target_path = self._storage_root / "runs" / run_id / "run_state.json"
        existing_payload: dict[str, object] = {}
        if target_path.exists():
            existing_payload = dict(self._load_json_object(target_path))
        existing_payload.update(
            {
                "run_id": run_id,
                "updated_at": _current_timestamp(),
                "source": source,
            }
        )
        for key, value in payload.items():
            if value is not None:
                existing_payload[key] = value
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(existing_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_fixture(self, filename: str) -> dict[str, object]:
        """读取必需 fixture。"""

        path = self._fixture_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少 mock control plane fixture: {path}")
        return self._load_json_object(path)

    def _load_optional_fixture(
        self,
        filename: str,
        *,
        default_payload: dict[str, object],
    ) -> dict[str, object]:
        """读取可选 fixture；不存在时回退默认值。"""

        path = self._fixture_dir / filename
        if not path.exists():
            return default_payload
        return self._load_json_object(path)

    def _load_json_object(self, path: Path) -> dict[str, object]:
        """读取并校验 JSON 对象 fixture。"""

        decoded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(f"mock control plane fixture 必须为 JSON 对象: {path}")
        return decoded


class _MockControlPlaneHttpServer(ThreadingHTTPServer):
    """携带 state 的 HTTP server。"""

    def __init__(
        self,
        server_address: tuple[str, int],
        state: MockControlPlaneState,
    ) -> None:
        self.state = state
        super().__init__(server_address, _MockControlPlaneRequestHandler)


class _MockControlPlaneRequestHandler(BaseHTTPRequestHandler):
    """处理 mock control plane 请求。"""

    server: _MockControlPlaneHttpServer

    def do_GET(self) -> None:  # noqa: N802
        """处理健康检查。"""

        path = urlparse(self.path).path
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/api/baidu/token":
            self._send_json(HTTPStatus.OK, self.server.state.baidu_token_response())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        """处理 control plane API。"""

        payload = self._read_json_object()
        if payload is None:
            return
        path = urlparse(self.path).path
        if path == "/api/pipeline/bootstrap":
            self.server.state.record_bootstrap_request(payload)
            self._send_json(HTTPStatus.OK, self.server.state.bootstrap_response())
            return

        finalize_match = _RUN_LOG_FINALIZE_ENDPOINT_PATTERN.fullmatch(path)
        if finalize_match is not None:
            run_id = finalize_match.group("run_id")
            response = self.server.state.log_finalize_response(run_id, payload)
            self._send_json(HTTPStatus.OK, response)
            return

        match = _RUN_ENDPOINT_PATTERN.fullmatch(path)
        if match is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        run_id = match.group("run_id")
        kind = match.group("kind")
        if kind == "heartbeat":
            response = self.server.state.heartbeat_response(run_id, payload)
            self._send_json(HTTPStatus.OK, response)
            return
        if kind == "logs":
            response = self.server.state.log_event_response(run_id, payload)
            self._send_json(HTTPStatus.OK, response)
            return

        response = self.server.state.report_response(run_id, payload)
        self._send_json(HTTPStatus.OK, response)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        """禁用默认访问日志输出。"""

        del format, args

    def _read_json_object(self) -> dict[str, object] | None:
        """读取请求体并确保它是 JSON 对象。"""

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            decoded = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return None
        if not isinstance(decoded, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "json_object_required"})
            return None
        return decoded

    def _send_json(self, status: HTTPStatus, payload: Mapping[str, object]) -> None:
        """返回 JSON 响应。"""

        encoded = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class MockControlPlaneServer:
    """以后台线程形式运行的本地 mock control plane server。"""

    def __init__(self, config: MockControlPlaneConfig) -> None:
        self._config = config
        self._state = MockControlPlaneState(
            fixture_dir=config.fixture_dir,
            storage_root=config.storage_root,
        )
        self._http_server = _MockControlPlaneHttpServer((config.host, config.port), self._state)
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        """返回 server base URL。"""

        host, port = self._http_server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        """启动后台线程。"""

        if self._thread is not None:
            return
        self._thread = Thread(target=self._http_server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        """关闭 server。"""

        self._http_server.shutdown()
        self._http_server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def build_parser() -> argparse.ArgumentParser:
    """构造 mock server CLI 参数。"""

    parser = argparse.ArgumentParser(description="运行本地 mock control plane server。")
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/mock_control_plane"),
        help="响应 fixture 所在目录。",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path("temp/mock_control_plane"),
        help="接收到的请求落盘目录。",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    args = build_parser().parse_args(argv)
    server = MockControlPlaneServer(
        MockControlPlaneConfig(
            fixture_dir=args.fixture_dir,
            storage_root=args.storage_root,
            host=args.host,
            port=args.port,
        )
    )
    print(
        json.dumps(
            {
                "base_url": server.base_url,
                "fixture_dir": str(args.fixture_dir),
                "storage_root": str(args.storage_root),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    server.start()
    try:
        server._thread.join()  # type: ignore[union-attr]
    except KeyboardInterrupt:
        server.close()
    return 0


def _current_timestamp() -> str:
    """返回当前 ISO 8601 时间。"""

    return datetime.now().astimezone().isoformat()


def _extract_stage(payload: dict[str, object]) -> str | None:
    """从 heartbeat 负载提取当前阶段。"""

    progress = payload.get("progress")
    if not isinstance(progress, Mapping):
        return None
    stage = progress.get("stage")
    return stage if isinstance(stage, str) else None


def _extract_relay_runtime(payload: dict[str, object]) -> dict[str, object] | None:
    """从 heartbeat 负载提取 relay 运行态快照。"""

    progress = payload.get("progress")
    if not isinstance(progress, Mapping):
        return None
    relay_runtime = progress.get("relay_runtime")
    return dict(relay_runtime) if isinstance(relay_runtime, Mapping) else None


def _extract_relay_runtime_from_summary(summary: object) -> dict[str, object] | None:
    """从 terminal summary 中提取 relay 运行态快照。"""

    if not isinstance(summary, Mapping):
        return None
    nested_summary = summary.get("summary")
    if not isinstance(nested_summary, Mapping):
        return None
    relay_runtime = nested_summary.get("relay_runtime")
    return dict(relay_runtime) if isinstance(relay_runtime, Mapping) else None


if __name__ == "__main__":
    raise SystemExit(main())
