"""测试用 control plane HTTP capture server。"""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
import json
import threading
from typing import Any


@dataclass
class ControlPlaneCaptureServer:
    """记录 control plane 请求的本地 HTTP server。"""

    bootstrap_payload: dict[str, object]
    baidu_token_payload: dict[str, object] | None = None

    def __post_init__(self) -> None:
        self.bootstrap_requests: list[dict[str, object]] = []
        self.baidu_token_requests: list[dict[str, object]] = []
        self.heartbeats: list[dict[str, object]] = []
        self.reports: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.terminal_summaries: list[dict[str, object]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._build_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """返回本地 server 基础地址。"""

        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> None:
        """启动 server。"""

        self._thread.start()

    def close(self) -> None:
        """关闭 server。"""

        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        """构造绑定当前实例的 request handler。"""

        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/api/baidu/token":
                    outer.baidu_token_requests.append({})
                    _write_json_response(
                        self,
                        outer.baidu_token_payload
                        or {
                            "app_key": "mock-app-key",
                            "secret_key": "mock-secret-key",
                            "refresh_token": "mock-refresh-token",
                        },
                    )
                    return
                _write_json_response(self, {"error": f"unexpected path: {self.path}"}, status=404)

            def do_POST(self) -> None:  # noqa: N802
                payload = _read_request_json(self)
                if self.path == "/api/pipeline/bootstrap":
                    outer.bootstrap_requests.append(payload)
                    _write_json_response(self, {})
                    return
                if self.path.endswith("/heartbeat"):
                    outer.heartbeats.append(payload)
                    _write_json_response(self, {})
                    return
                if self.path.endswith("/report"):
                    outer.reports.append(payload)
                    _write_json_response(self, {})
                    return
                if self.path.endswith("/logs/finalize"):
                    outer.terminal_summaries.append(payload)
                    _write_json_response(self, {})
                    return
                if self.path.endswith("/logs"):
                    outer.events.append(payload)
                    _write_json_response(self, {})
                    return
                _write_json_response(self, {"error": f"unexpected path: {self.path}"}, status=404)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

        return _Handler


def _read_request_json(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    """读取请求体 JSON。"""

    content_length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(content_length)
    if not raw:
        return {}
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("capture server 仅支持 JSON object 请求体。")
    return payload


def _write_json_response(
    handler: BaseHTTPRequestHandler,
    payload: dict[str, object],
    *,
    status: int = 200,
) -> None:
    """写回 JSON 响应。"""

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)
