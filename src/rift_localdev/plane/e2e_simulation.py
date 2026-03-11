"""本地 fake-github + mock control plane 端到端联调脚本。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import TextIO
from urllib import request

from rift_localdev.simulation import BAIDU_FAILURE_MODE_ENV_VAR
from rift_localdev.simulation import MOCK_BAIDU_ENV_VAR
from rift_localdev.simulation import SIMULATION_ENV_VAR


@dataclass(frozen=True, slots=True)
class ControlPlaneE2ESimulationConfig:
    """本地端到端联调配置。"""

    fixture_dir: Path
    workspace_root: Path
    output_root: Path
    temp_root: Path
    mock_plane_storage_root: Path
    faker_storage_root: Path
    requested_by: str = "control-plane-e2e"
    game_region: str = "zh_CN"
    owner: str = "octo"
    repo: str = "test"
    workflow_id: str = "pipeline.yml"
    stage: str = "extract"
    champion_ids: tuple[int, ...] = (1,)
    map_ids: tuple[int, ...] = tuple()
    host: str = "127.0.0.1"
    timeout_seconds: float = 30.0
    poll_interval_seconds: float = 0.2
    github_token: str = "local-dev-token"
    simulation_mode: str = "full"
    baidu_failure_mode: str = "none"


@dataclass(frozen=True, slots=True)
class ControlPlaneE2ESimulationResult:
    """本地端到端联调结果。"""

    mock_plane_base_url: str
    fake_github_base_url: str
    run_id: str
    dispatch_receipt_path: Path
    fake_github_log_path: Path
    log_dir: Path
    mock_plane_run_dir: Path
    archive_upload_receipt: Path
    log_upload_receipt: Path
    local_event_count: int
    remote_log_count: int
    terminal_summary_path: Path
    run_summary_path: Path
    log_relay_state_path: Path


def run_control_plane_e2e_simulation(
    config: ControlPlaneE2ESimulationConfig,
) -> ControlPlaneE2ESimulationResult:
    """启动 mock plane/fake-github，并跑完整条本地联调链路。"""

    _validate_target_count(config)
    config.output_root.mkdir(parents=True, exist_ok=True)
    config.temp_root.mkdir(parents=True, exist_ok=True)
    config.mock_plane_storage_root.mkdir(parents=True, exist_ok=True)
    config.faker_storage_root.mkdir(parents=True, exist_ok=True)

    base_env = os.environ.copy()
    base_env["PYTHONUNBUFFERED"] = "1"

    mock_plane_proc = _start_server_process(
        command=[
            sys.executable,
            "-m",
            "rift_localdev.plane.mock_server",
            "--fixture-dir",
            str(config.fixture_dir),
            "--storage-root",
            str(config.mock_plane_storage_root),
            "--host",
            config.host,
            "--port",
            "0",
        ],
        cwd=config.workspace_root,
        env=base_env,
        process_name="mock-control-plane",
    )

    faker_env = dict(base_env)
    if config.simulation_mode == "full":
        faker_env[SIMULATION_ENV_VAR] = "1"
    elif config.simulation_mode == "baidu-only":
        faker_env[MOCK_BAIDU_ENV_VAR] = "1"
        faker_env[BAIDU_FAILURE_MODE_ENV_VAR] = config.baidu_failure_mode
    else:
        raise ValueError(f"不支持的 simulation_mode: {config.simulation_mode}")
    fake_github_proc = _start_server_process(
        command=[
            sys.executable,
            "-m",
            "rift_localdev.github.faker_github",
            "--host",
            config.host,
            "--port",
            "0",
            "--github-token",
            config.github_token,
            "--storage-root",
            str(config.faker_storage_root),
            "--control-plane-base-url",
            mock_plane_proc.startup_payload["base_url"],
            "--default-requested-by",
            config.requested_by,
            "--output-root",
            str(config.output_root),
            "--temp-root",
            str(config.temp_root),
            "--log-root",
            str(config.output_root / "logs"),
        ],
        cwd=config.workspace_root,
        env=faker_env,
        process_name="fake-github",
    )

    try:
        _wait_for_healthz(
            f"{mock_plane_proc.startup_payload['base_url']}/healthz",
            timeout_seconds=config.timeout_seconds,
        )
        _wait_for_healthz(
            fake_github_proc.startup_payload["healthz"],
            timeout_seconds=config.timeout_seconds,
        )
        _dispatch_workflow(config, fake_github_proc.startup_payload["base_url"])
        receipt_path = _wait_for_single_file(
            config.faker_storage_root / "dispatches",
            "*.json",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        receipt_payload = _read_json(receipt_path)
        fake_github_log_path = Path(_require_str(receipt_payload, "log_path"))
        run_summary_path = _wait_for_run_summary(
            config.output_root / "logs",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        run_summary_payload = _read_json(run_summary_path)
        run_id = _require_str(run_summary_payload, "run_id")
        log_dir = run_summary_path.parent
        mock_plane_run_dir = config.mock_plane_storage_root / "runs" / run_id
        terminal_summary_path = _wait_for_path(
            mock_plane_run_dir / "logs_finalize.json",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        _wait_for_path(
            mock_plane_run_dir / "heartbeats" / "0001.json",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        log_relay_state_path = _wait_for_path(
            log_dir / "log_relay_state.json",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        archive_upload_receipt = _wait_for_path(
            config.output_root / "simulation" / "archive_upload.json",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )
        log_upload_receipt = _wait_for_path(
            config.output_root / "simulation" / "log_upload.json",
            timeout_seconds=config.timeout_seconds,
            poll_interval_seconds=config.poll_interval_seconds,
        )

        local_events = _read_json_lines(log_dir / "events.jsonl")
        remote_log_files = sorted((mock_plane_run_dir / "logs").glob("*.json"))
        if not remote_log_files:
            raise RuntimeError("mock control plane 未收到任何 runtime log。")
        local_event_count = len(local_events)
        remote_log_count = len(remote_log_files)
        terminal_payload = _read_json(terminal_summary_path)
        log_relay_state = _read_json(log_relay_state_path)
        fake_github_log_content = fake_github_log_path.read_text(encoding="utf-8")

        if local_event_count != remote_log_count:
            raise RuntimeError(
                f"runtime log 条数不一致：local={local_event_count}, remote={remote_log_count}"
            )
        if _require_str(run_summary_payload, "status") != "success":
            raise RuntimeError(f"pipeline 未成功结束：{run_summary_payload}")
        terminal_summary_payload = terminal_payload["payload"]["summary"]  # type: ignore[index]
        if not isinstance(terminal_summary_payload, dict):
            raise ValueError(f"mock plane 终态摘要 payload 结构非法：{terminal_payload}")
        nested_summary = terminal_summary_payload.get("summary")
        if not isinstance(nested_summary, dict):
            raise ValueError(f"mock plane 终态摘要缺少 summary：{terminal_payload}")
        if _require_str(nested_summary, "status") != "success":
            raise RuntimeError(f"终态日志摘要不是 success：{terminal_payload}")
        if not _bool_value(log_relay_state, "terminal_sent"):
            raise RuntimeError(f"log relay 未成功发送终态摘要：{log_relay_state}")
        if _int_value(log_relay_state, "pending_spool_events") != 0:
            raise RuntimeError(f"log relay 仍残留未发送 spool 事件：{log_relay_state}")
        if '"status": "success"' not in fake_github_log_content:
            raise RuntimeError("fake-github 子进程日志里未看到成功摘要。")

        return ControlPlaneE2ESimulationResult(
            mock_plane_base_url=mock_plane_proc.startup_payload["base_url"],
            fake_github_base_url=fake_github_proc.startup_payload["base_url"],
            run_id=run_id,
            dispatch_receipt_path=receipt_path,
            fake_github_log_path=fake_github_log_path,
            log_dir=log_dir,
            mock_plane_run_dir=mock_plane_run_dir,
            archive_upload_receipt=archive_upload_receipt,
            log_upload_receipt=log_upload_receipt,
            local_event_count=local_event_count,
            remote_log_count=remote_log_count,
            terminal_summary_path=terminal_summary_path,
            run_summary_path=run_summary_path,
            log_relay_state_path=log_relay_state_path,
        )
    finally:
        _stop_server_process(fake_github_proc.process)
        _stop_server_process(mock_plane_proc.process)


def build_parser() -> argparse.ArgumentParser:
    """构造联调脚本 CLI 参数。"""

    parser = argparse.ArgumentParser(description="运行 fake-github + mock control plane 端到端联调。")
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/mock_control_plane"),
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("temp/control_plane_e2e") / _slug_now(),
    )
    parser.add_argument("--requested-by", default="control-plane-e2e")
    parser.add_argument("--game-region", default="zh_CN")
    parser.add_argument("--owner", default="octo")
    parser.add_argument("--repo", default="test")
    parser.add_argument("--workflow-id", default="pipeline.yml")
    parser.add_argument("--stage", choices=("update", "extract", "mapping"), default="extract")
    parser.add_argument("--champion-ids", default="1")
    parser.add_argument("--map-ids", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--simulation-mode", choices=("full", "baidu-only"), default="full")
    parser.add_argument(
        "--baidu-failure-mode",
        choices=("none", "archive", "log", "both"),
        default="none",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    args = build_parser().parse_args(argv)
    base_dir = args.base_dir
    result = run_control_plane_e2e_simulation(
        ControlPlaneE2ESimulationConfig(
            fixture_dir=args.fixture_dir,
            workspace_root=args.workspace_root,
            output_root=base_dir / "output",
            temp_root=base_dir / "temp",
            mock_plane_storage_root=base_dir / "mock_plane_received",
            faker_storage_root=base_dir / "faker_github",
            requested_by=args.requested_by,
            game_region=args.game_region,
            owner=args.owner,
            repo=args.repo,
            workflow_id=args.workflow_id,
            stage=args.stage,
            champion_ids=_parse_id_list(args.champion_ids),
            map_ids=_parse_id_list(args.map_ids),
            host=args.host,
            timeout_seconds=args.timeout_seconds,
            simulation_mode=args.simulation_mode,
            baidu_failure_mode=args.baidu_failure_mode,
        )
    )
    print(json.dumps(_result_to_json(result), ensure_ascii=False, indent=2))
    return 0


@dataclass(frozen=True, slots=True)
class _ServerProcess:
    """本地 server 子进程与启动信息。"""

    process: subprocess.Popen[str]
    startup_payload: dict[str, str]


def _start_server_process(
    *,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    process_name: str,
) -> _ServerProcess:
    """启动本地 server 子进程并读取启动 JSON。"""

    process = subprocess.Popen(  # noqa: S603
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError(f"{process_name} stdout 不可用。")
    startup_payload = _read_startup_json(process.stdout, process_name=process_name)
    return _ServerProcess(process=process, startup_payload=startup_payload)


def _read_startup_json(stream: TextIO, *, process_name: str) -> dict[str, str]:
    """读取 server 启动阶段输出的 JSON。"""

    lines: list[str] = []
    brace_depth = 0
    started = False
    while True:
        line = stream.readline()
        if not line:
            raise RuntimeError(f"{process_name} 未输出启动 JSON 就退出。")
        if not started and "{" not in line:
            continue
        started = True
        brace_depth += line.count("{")
        brace_depth -= line.count("}")
        lines.append(line)
        if brace_depth == 0:
            payload = json.loads("".join(lines))
            if not isinstance(payload, dict):
                raise ValueError(f"{process_name} 启动输出必须是 JSON 对象。")
            return {str(key): str(value) for key, value in payload.items()}


def _wait_for_healthz(url: str, *, timeout_seconds: float) -> None:
    """等待 server 健康检查成功。"""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    raise TimeoutError(f"等待健康检查超时：{url}")


def _dispatch_workflow(
    config: ControlPlaneE2ESimulationConfig,
    fake_github_base_url: str,
) -> None:
    """向 fake-github 发送一次 workflow dispatch。"""

    payload = {
        "ref": "main",
        "inputs": {
            "payload": json.dumps(
                {
                    "schema_version": "2026-03-11",
                    "request": {"stage": config.stage},
                    "game": {"region": config.game_region},
                    "targets": {
                        "champions": {
                            "ids": ",".join(str(item) for item in config.champion_ids)
                        }
                        if config.champion_ids
                        else {},
                        "maps": {
                            "ids": ",".join(str(item) for item in config.map_ids)
                        }
                        if config.map_ids
                        else {},
                    },
                    "metadata": {"requested_by": config.requested_by},
                },
                ensure_ascii=False,
            )
        },
    }
    dispatch_request = request.Request(
        url=(
            f"{fake_github_base_url}/repos/{config.owner}/{config.repo}/actions/workflows/"
            f"{config.workflow_id}/dispatches"
        ),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.github_token}",
        },
    )
    with request.urlopen(dispatch_request, timeout=10) as response:
        if response.status != 204:
            raise RuntimeError(f"dispatch 返回异常状态码：{response.status}")


def _wait_for_single_file(
    directory: Path,
    pattern: str,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> Path:
    """等待目录下出现唯一匹配文件。"""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        files = sorted(directory.glob(pattern))
        if len(files) == 1:
            return files[0]
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"等待文件超时：{directory}/{pattern}")


def _wait_for_run_summary(
    log_root: Path,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> Path:
    """等待本地 `run.json` 生成。"""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        candidates = sorted(log_root.glob("*/*/run.json"))
        if len(candidates) == 1:
            return candidates[0]
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"等待 run.json 超时：{log_root}")


def _wait_for_path(
    path: Path,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> Path:
    """等待某个路径出现。"""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return path
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"等待路径超时：{path}")


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON 对象文件。"""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 文件必须是对象：{path}")
    return payload


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    """读取 JSONL 文件。"""

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    payloads: list[dict[str, object]] = []
    for line in lines:
        decoded = json.loads(line)
        if not isinstance(decoded, dict):
            raise ValueError(f"JSONL 行必须是对象：{path}")
        payloads.append(decoded)
    return payloads


def _require_str(payload: dict[str, object], key: str) -> str:
    """读取必填字符串字段。"""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"缺少有效字符串字段：{key}")
    return value


def _bool_value(payload: dict[str, object], key: str) -> bool:
    """读取布尔字段。"""

    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"缺少有效布尔字段：{key}")
    return value


def _int_value(payload: dict[str, object], key: str) -> int:
    """读取整数字段。"""

    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"缺少有效整数字段：{key}")
    return value


def _stop_server_process(process: subprocess.Popen[str]) -> None:
    """停止本地 server 子进程。"""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _parse_id_list(raw_value: str) -> tuple[int, ...]:
    """解析逗号分隔 ID 列表。"""

    normalized = [item.strip() for item in raw_value.split(",") if item.strip()]
    return tuple(int(item) for item in normalized)


def _validate_target_count(config: ControlPlaneE2ESimulationConfig) -> None:
    """限制本地联调目标数量。"""

    total_targets = len(config.champion_ids) + len(config.map_ids)
    if total_targets == 0:
        raise ValueError("端到端联调至少需要一个 champion_id 或 map_id。")
    if total_targets > 3:
        raise ValueError("端到端联调最多只支持 3 个 champion/map 目标。")


def _slug_now() -> str:
    """返回适合目录名的时间戳。"""

    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")


def _result_to_json(result: ControlPlaneE2ESimulationResult) -> dict[str, object]:
    """把结果对象转换为 JSON 友好结构。"""

    payload = asdict(result)
    for key, value in list(payload.items()):
        if isinstance(value, Path):
            payload[key] = str(value)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
