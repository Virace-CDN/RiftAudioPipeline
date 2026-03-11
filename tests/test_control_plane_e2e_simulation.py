"""fake-github + mock control plane 端到端联调测试。"""

from __future__ import annotations

import json
from pathlib import Path

from rift_localdev.plane.e2e_simulation import ControlPlaneE2ESimulationConfig
from rift_localdev.plane.e2e_simulation import run_control_plane_e2e_simulation


def test_run_control_plane_e2e_simulation_should_complete_full_chain(tmp_path: Path) -> None:
    """应通过 fake-github dispatch 跑完整条本地联调链路。"""

    result = run_control_plane_e2e_simulation(
        ControlPlaneE2ESimulationConfig(
            fixture_dir=Path(__file__).parent / "fixtures" / "mock_control_plane",
            workspace_root=Path.cwd(),
            output_root=tmp_path / "output",
            temp_root=tmp_path / "temp",
            mock_plane_storage_root=tmp_path / "mock_plane",
            faker_storage_root=tmp_path / "faker_github",
            requested_by="pytest-e2e",
            champion_ids=(1,),
            map_ids=(11,),
            timeout_seconds=45.0,
        )
    )

    run_summary = _read_json(result.run_summary_path)
    terminal_summary = _read_json(result.terminal_summary_path)
    dispatch_receipt = _read_json(result.dispatch_receipt_path)
    log_relay_state = _read_json(result.log_relay_state_path)
    archive_receipt = _read_json(result.archive_upload_receipt)
    log_receipt = _read_json(result.log_upload_receipt)
    run_state = _read_json(result.mock_plane_run_dir / "run_state.json")

    assert run_summary["status"] == "success"
    assert run_summary["processed_targets"] == 2
    assert result.local_event_count == result.remote_log_count
    assert result.remote_log_count > 0
    assert terminal_summary["payload"]["summary"]["final_status"] == "success"
    assert terminal_summary["payload"]["summary"]["summary"]["status"] == "success"
    assert terminal_summary["payload"]["summary"]["processed_targets"] == 2
    assert dispatch_receipt["dry_run"] is False
    assert "--dispatch-inputs-file" in dispatch_receipt["command"]
    dispatch_inputs_path = Path(
        dispatch_receipt["command"][dispatch_receipt["command"].index("--dispatch-inputs-file") + 1]
    )
    dispatch_inputs = _read_json(dispatch_inputs_path)
    assert dispatch_inputs["targets"]["champions"]["ids"] == [1]
    assert dispatch_inputs["targets"]["maps"]["ids"] == [11]
    assert log_relay_state["terminal_sent"] is True
    assert log_relay_state["pending_spool_events"] == 0
    assert len(archive_receipt["archives"]) == 2
    assert "run.json" in log_receipt["files"]
    assert run_state["status"] == "success"
    assert run_state["relay_runtime"]["managed"] is True
    assert run_state["relay_runtime"]["start_signal_received"] is True
    assert run_state["relay_runtime"]["terminal_summary_received"] is True


def _read_json(path: Path) -> dict[str, object]:
    """读取 JSON 对象文件。"""

    return json.loads(path.read_text(encoding="utf-8"))
