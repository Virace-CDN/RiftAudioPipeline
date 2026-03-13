"""dispatch payload 写盘脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_audio_pipeline.control_plane.write_dispatch_payload import write_dispatch_payload


def test_write_dispatch_payload_should_write_raw_and_redacted_files(tmp_path: Path) -> None:
    """应写出原始 payload 文件与脱敏副本。"""

    github_event_path = tmp_path / "event.json"
    dispatch_inputs_file = tmp_path / "dispatch-payload.json"
    redacted_output_file = tmp_path / "dispatch-payload.redacted.json"
    github_event_path.write_text(
        json.dumps(
            {
                "inputs": {
                    "payload": json.dumps(
                        {
                            "schema_version": "2026-03-14",
                            "baidu": {
                                "access_token": "secret-token",
                                "app_key": "secret-app-key",
                            },
                            "execution": {
                                "archive_remote_root": "/apps/custom-data",
                                "meta_remote_root": "/apps/custom-meta",
                            },
                        },
                        ensure_ascii=False,
                    )
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = write_dispatch_payload(
        github_event_path=github_event_path,
        dispatch_inputs_file=dispatch_inputs_file,
        redacted_output_file=redacted_output_file,
        ref="test",
    )

    assert summary["ref"] == "test"
    assert json.loads(dispatch_inputs_file.read_text(encoding="utf-8"))["execution"] == {
        "archive_remote_root": "/apps/custom-data",
        "meta_remote_root": "/apps/custom-meta",
    }
    redacted_payload = json.loads(redacted_output_file.read_text(encoding="utf-8"))
    assert redacted_payload["inputs"]["payload"]
    decoded_redacted = json.loads(redacted_payload["inputs"]["payload"])
    assert decoded_redacted["baidu"]["access_token"] == "***REDACTED***"
    assert decoded_redacted["baidu"]["app_key"] == "***REDACTED***"
