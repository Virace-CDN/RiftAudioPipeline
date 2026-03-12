"""GitHub Actions workflow 入口测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rift_audio_pipeline.control_plane import github_actions_workflow


def test_build_workflow_command_should_map_structured_dispatch_inputs(tmp_path: Path) -> None:
    """workflow 入口应把结构化 JSON 转成 job runner 调用。"""

    dispatch_payload_file = tmp_path / "dispatch-payload.json"
    dispatch_payload_file.write_text(
        json.dumps(
            {
                "schema_version": "2026-03-11",
                "request": {"mode": "remote", "stage": "update"},
                "game": {"region": "oc1"},
                "manifests": {
                    "current": {
                        "version": "16.5",
                        "lcu_url": "https://lcu.example/16.5",
                        "game_url": "https://game.example/16.5",
                    }
                },
                "metadata": {"requested_by": "actions-test"},
            }
        ),
        encoding="utf-8",
    )
    args = github_actions_workflow.build_parser().parse_args(
        [
            "--ref",
            "main",
            "--dispatch-inputs-file",
            str(dispatch_payload_file),
            "--control-plane-base-url",
            "https://control.example.com",
        ]
    )

    payload, command = github_actions_workflow.build_workflow_command(args)

    assert payload.ref == "main"
    assert command[:3] == [
        github_actions_workflow.sys.executable,
        "-m",
        "rift_audio_pipeline.control_plane.job_runner",
    ]
    assert "--dispatch-inputs-file" in command
    assert str(dispatch_payload_file) in command
    assert "--default-game-region" in command
    assert "oc1" in command
    assert "--default-requested-by" in command
    assert "actions-test" in command
    assert "--control-plane-base-url" in command
    assert "https://control.example.com" in command


def test_load_dispatch_payload_should_require_json_object(tmp_path: Path) -> None:
    """workflow 输入文件必须是 JSON object。"""

    dispatch_payload_file = tmp_path / "dispatch-payload.json"
    dispatch_payload_file.write_text('"bad"', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        github_actions_workflow.load_dispatch_payload(
            ref="main",
            dispatch_inputs_file=dispatch_payload_file,
        )
