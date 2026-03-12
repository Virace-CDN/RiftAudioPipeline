"""faker-github 服务测试。"""

from __future__ import annotations

import json
from pathlib import Path
from urllib import error
from urllib import request

import pytest

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
from rift_audio_pipeline.control_plane.workflow_dispatch import WorkflowDispatchCommandConfig
from rift_audio_pipeline.control_plane.workflow_dispatch import build_job_runner_command
from rift_audio_pipeline.control_plane.workflow_dispatch import parse_dispatch_payload
from rift_localdev.github.faker_github import FakerGitHubConfig
from rift_localdev.github.faker_github import FakerGitHubServer
from rift_localdev.github.faker_github import _extract_authorization_token


def test_build_pipeline_command_should_map_dispatch_inputs() -> None:
    """应把 workflow inputs 正确翻译为独立 job runner 参数。"""

    config = FakerGitHubConfig(
        storage_root=Path("temp/test-faker-github"),
        control_plane_base_url="http://localhost:5173",
        default_mode="remote",
        default_game_region="zh_CN",
    )
    command = build_job_runner_command(
        config=WorkflowDispatchCommandConfig(
            storage_root=config.storage_root,
            control_plane_base_url=config.control_plane_base_url,
            default_mode=config.default_mode,
            default_game_region=config.default_game_region,
            default_requested_by=config.default_requested_by,
            output_root=config.output_root,
            temp_root=config.temp_root,
            log_root=config.log_root,
            baidu_remote_root=config.baidu_remote_root,
            default_log_level=config.default_log_level,
            control_plane_timeout_seconds=config.control_plane_timeout_seconds,
            python_executable=config.python_executable,
        ),
        payload=DispatchPayload(
            ref="main",
            inputs=DispatchInputs(
                schema_version="2026-03-11",
                request=DispatchRequestInputs(mode="remote", stage="mapping"),
                game=DispatchGameInputs(region="euw"),
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
                    maps=DispatchIdTargets(ids=(11, 12)),
                ),
                baidu=DispatchBaiduInputs(
                    app_key="manual-app-key",
                    secret_key="manual-secret-key",
                    refresh_token="manual-refresh-token",
                ),
                execution=DispatchExecutionInputs(
                    force_update=True,
                    max_workers=8,
                    download_retry_attempts=5,
                    entity_retry_attempts=2,
                    log_level="DEBUG",
                    archive_password="zip-secret",
                ),
                metadata=DispatchMetadataInputs(requested_by="plane-scheduler"),
            ),
        ),
        dispatch_inputs_file=Path("temp/test-faker-github/dispatch-payload.json"),
    )

    assert command[:3] == [
        str(config.python_executable),
        "-m",
        "rift_audio_pipeline.control_plane.job_runner",
    ]
    assert "--dispatch-inputs-file" in command
    assert "temp/test-faker-github/dispatch-payload.json" in command
    assert "--default-game-region" in command
    assert "euw" in command
    assert "--control-plane-base-url" in command
    assert "http://localhost:5173" in command
    assert "--default-mode" in command
    assert "remote" in command
    assert "--default-requested-by" in command
    assert "plane-scheduler" in command
    assert "--default-log-level" in command
    assert "DEBUG" in command


def test_faker_github_server_should_accept_dispatch_and_record_receipt(tmp_path: Path) -> None:
    """收到 dispatch 请求后应拉起 launcher 并落盘收据。"""

    launched: dict[str, object] = {}

    def _fake_launcher(command: list[str], cwd: Path, log_path: Path) -> int:
        launched["command"] = command
        launched["cwd"] = cwd
        launched["log_path"] = log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("fake pipeline log\n", encoding="utf-8")
        return 4321

    server = FakerGitHubServer(
        FakerGitHubConfig(
            storage_root=tmp_path / "faker-github",
            host="127.0.0.1",
            port=0,
            github_token="test-token",
            control_plane_base_url="http://localhost:5173",
        ),
        launcher=_fake_launcher,
    )
    server.start()
    try:
        payload = json.dumps(
            {
                "ref": "main",
                "inputs": {
                    "payload": json.dumps(
                        {
                            "schema_version": "2026-03-11",
                            "request": {"stage": "extract"},
                            "game": {"region": "euw"},
                            "manifests": {
                                "current": {
                                    "version": "16.5",
                                    "lcu_url": "https://lcu.example/16.5",
                                    "game_url": "https://game.example/16.5",
                                }
                            },
                            "targets": {"champions": {"ids": "266,103"}},
                            "baidu": {
                                "app_key": "manual-app-key",
                                "secret_key": "manual-secret-key",
                                "refresh_token": "manual-refresh-token",
                            },
                            "execution": {"archive_password": "zip-secret"},
                            "metadata": {"requested_by": "plane-test"},
                        }
                    ),
                },
            }
        ).encode("utf-8")
        req = request.Request(
            url=(f"{server.base_url}/repos/octo/test/actions/workflows/pipeline.yml/dispatches"),
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-token",
            },
        )
        with request.urlopen(req) as response:
            assert response.status == 204

        dispatch_dir = tmp_path / "faker-github" / "dispatches"
        receipts = list(dispatch_dir.glob("*.json"))
        assert len(receipts) == 1
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        assert receipt["owner"] == "octo"
        assert receipt["repo"] == "test"
        assert receipt["workflow_id"] == "pipeline.yml"
        assert receipt["dry_run"] is False
        assert receipt["pid"] == 4321
        assert launched["log_path"] == Path(receipt["log_path"])
        launched_command = launched["command"]
        assert isinstance(launched_command, list)
        assert launched_command[:3] == [
            launched_command[0],
            "-m",
            "rift_audio_pipeline.control_plane.job_runner",
        ]
        assert "--dispatch-inputs-file" in launched_command
        dispatch_inputs_path = Path(
            launched_command[launched_command.index("--dispatch-inputs-file") + 1]
        )
        assert dispatch_inputs_path.exists()
        dispatch_inputs_payload = json.loads(dispatch_inputs_path.read_text(encoding="utf-8"))
        assert dispatch_inputs_payload["targets"]["champions"]["ids"] == [266, 103]
        assert dispatch_inputs_payload["manifests"]["current"]["version"] == "16.5"
        assert dispatch_inputs_payload["baidu"]["refresh_token"] == "manual-refresh-token"
        assert dispatch_inputs_payload["execution"]["archive_password"] == "zip-secret"
    finally:
        server.close()


def test_faker_github_server_dry_run_should_not_launch_process(tmp_path: Path) -> None:
    """dry-run 模式应只记录命令，不真实启动进程。"""

    def _unexpected_launcher(command: list[str], cwd: Path, log_path: Path) -> int:
        raise AssertionError("launcher should not be called in dry-run mode")

    server = FakerGitHubServer(
        FakerGitHubConfig(
            storage_root=tmp_path / "faker-github",
            host="127.0.0.1",
            port=0,
            github_token="dry-run-token",
            dry_run=True,
        ),
        launcher=_unexpected_launcher,
    )
    server.start()
    try:
        payload = json.dumps(
            {
                "ref": "main",
                "inputs": {
                    "payload": json.dumps(
                        {
                            "request": {"mode": "remote"},
                            "game": {"region": "euw"},
                            "execution": {"force_update": False},
                        }
                    ),
                },
            }
        ).encode("utf-8")
        req = request.Request(
            url=f"{server.base_url}/repos/octo/test/actions/workflows/pipeline.yml/dispatches",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "token dry-run-token",
            },
        )
        with request.urlopen(req) as response:
            assert response.status == 204

        receipts = list((tmp_path / "faker-github" / "dispatches").glob("*.json"))
        assert len(receipts) == 1
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        assert receipt["dry_run"] is True
        assert receipt["pid"] is None
        assert receipt["log_path"] is None
        dispatch_inputs_path = Path(
            receipt["command"][receipt["command"].index("--dispatch-inputs-file") + 1]
        )
        dispatch_inputs_payload = json.loads(dispatch_inputs_path.read_text(encoding="utf-8"))
        assert dispatch_inputs_payload["execution"]["force_update"] is False
    finally:
        server.close()


def test_faker_github_server_should_log_request_and_response_when_enabled(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """开启 HTTP exchange 日志时应输出请求与响应摘要。"""

    server = FakerGitHubServer(
        FakerGitHubConfig(
            storage_root=tmp_path / "faker-github",
            host="127.0.0.1",
            port=0,
            github_token="log-token",
            dry_run=True,
            log_http_exchange=True,
        )
    )
    server.start()
    try:
        payload = json.dumps(
            {
                "ref": "main",
                "inputs": {
                    "payload": json.dumps(
                        {
                            "game": {"region": "euw"},
                            "metadata": {"requested_by": "frontend-test"},
                        }
                    ),
                },
            }
        ).encode("utf-8")
        req = request.Request(
            url=f"{server.base_url}/repos/octo/test/actions/workflows/pipeline.yml/dispatches",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer log-token",
            },
        )
        with request.urlopen(req) as response:
            assert response.status == 204

        events = [
            json.loads(line) for line in capsys.readouterr().out.splitlines() if '"event":' in line
        ]
        assert [event["event"] for event in events] == [
            "dispatch_request",
            "workflow_inputs",
            "dispatch_response",
        ]
        assert (
            json.loads(events[0]["request_payload"]["inputs"]["payload"])["metadata"][
                "requested_by"
            ]
            == "frontend-test"
        )
        assert events[1]["inputs"]["metadata"]["requested_by"] == "frontend-test"
        assert events[2]["status"] == 204
        assert events[2]["response_summary"]["dispatch_id"]
        assert events[2]["response_summary"]["dry_run"] is True
    finally:
        server.close()


def test_faker_github_server_should_validate_payload(tmp_path: Path) -> None:
    """非法 payload 应返回 422。"""

    server = FakerGitHubServer(
        FakerGitHubConfig(
            storage_root=tmp_path / "faker-github",
            host="127.0.0.1",
            port=0,
            github_token="validation-token",
        )
    )
    server.start()
    try:
        payload = json.dumps({"inputs": {}}).encode("utf-8")
        req = request.Request(
            url=f"{server.base_url}/repos/octo/test/actions/workflows/pipeline.yml/dispatches",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer validation-token",
            },
        )
        try:
            request.urlopen(req)
        except error.HTTPError as exc:
            assert exc.code == 422
            body = json.loads(exc.read().decode("utf-8"))
            assert body["error"] == "validation_failed"
        else:  # pragma: no cover
            raise AssertionError("expected HTTPError")
    finally:
        server.close()


def test_parse_dispatch_payload_should_reject_runtime_secret_fields() -> None:
    """worker 运行时机密不应混入 workflow inputs。"""

    with pytest.raises(ValueError, match="worker_token"):
        parse_dispatch_payload(
            {
                "ref": "main",
                "inputs": {
                    "payload": json.dumps(
                        {
                            "request": {"mode": "remote"},
                            "worker_token": "secret",
                        }
                    ),
                },
            }
        )


def test_parse_dispatch_payload_should_accept_baidu_inputs() -> None:
    """手动 workflow dispatch 可显式携带百度凭据。"""

    payload = parse_dispatch_payload(
        {
            "ref": "main",
            "inputs": {
                "payload": json.dumps(
                    {
                        "request": {"mode": "remote"},
                        "baidu": {
                            "app_key": "manual-app-key",
                            "secret_key": "manual-secret-key",
                            "refresh_token": "manual-refresh-token",
                        },
                    }
                ),
            },
        }
    )

    assert payload.inputs.baidu.app_key == "manual-app-key"
    assert payload.inputs.baidu.secret_key == "manual-secret-key"
    assert payload.inputs.baidu.refresh_token == "manual-refresh-token"


def test_parse_dispatch_payload_should_require_nested_inputs() -> None:
    """结构化 inputs 不再接受扁平字段。"""

    with pytest.raises(ValueError, match="mode"):
        parse_dispatch_payload(
            {
                "ref": "main",
                "inputs": {
                    "mode": "remote",
                },
            }
        )


def test_build_pipeline_command_should_reject_unsupported_stage() -> None:
    """只接受可映射到 pipeline 的 stage。"""

    with pytest.raises(ValueError, match="stage"):
        build_job_runner_command(
            config=WorkflowDispatchCommandConfig(
                storage_root=Path("temp/test-faker-github"),
                control_plane_base_url="http://localhost:5173",
            ),
            payload=DispatchPayload(
                ref="main",
                inputs=DispatchInputs(
                    request=DispatchRequestInputs(mode="remote", stage="upload"),
                ),
            ),
            dispatch_inputs_file=Path("temp/test-faker-github/dispatch-payload.json"),
        )


def test_faker_github_server_should_require_authorization(tmp_path: Path) -> None:
    """缺失或错误 token 时应返回 401。"""

    server = FakerGitHubServer(
        FakerGitHubConfig(
            storage_root=tmp_path / "faker-github",
            host="127.0.0.1",
            port=0,
            github_token="secret-token",
        )
    )
    server.start()
    try:
        payload = json.dumps({"ref": "main"}).encode("utf-8")
        req = request.Request(
            url=f"{server.base_url}/repos/octo/test/actions/workflows/pipeline.yml/dispatches",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            request.urlopen(req)
        except error.HTTPError as exc:
            assert exc.code == 401
            body = json.loads(exc.read().decode("utf-8"))
            assert body["error"] == "unauthorized"
        else:  # pragma: no cover
            raise AssertionError("expected HTTPError")
    finally:
        server.close()


def test_extract_authorization_token_should_support_bearer_and_token() -> None:
    """应支持 Bearer 和 token 两种本地测试写法。"""

    assert _extract_authorization_token("Bearer abc") == "abc"
    assert _extract_authorization_token("token xyz") == "xyz"
    assert _extract_authorization_token("Basic no") is None
