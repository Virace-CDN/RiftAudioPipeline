"""本地 mock control plane smoke runner。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import uuid

from rift_audio_pipeline.control_plane.client import ControlPlaneClient
from rift_audio_pipeline.control_plane.models import ControlPlaneConfig
from rift_audio_pipeline.control_plane.state_db import bootstrap_state_database
from rift_audio_pipeline.control_plane.upload_worker import UploadWorker
from rift_audio_pipeline.control_plane.upload_worker import UploadWorkerConfig
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.orchestrator import run_pipeline
from rift_localdev.plane.mock_server import MockControlPlaneConfig
from rift_localdev.plane.mock_server import MockControlPlaneServer
from rift_localdev.simulation import patch_pipeline_for_simulation


@dataclass(frozen=True, slots=True)
class MockSmokeConfig:
    """本地 smoke runner 配置。"""

    fixture_dir: Path
    output_root: Path
    temp_root: Path
    storage_root: Path
    host: str = "127.0.0.1"
    port: int = 0
    game_region: str = "zh_CN"
    baidu_remote_root: str = "/apps/rift-audio-pipeline"
    requested_by: str = "mock-smoke"
    champion_ids: tuple[int, ...] = (1,)


@dataclass(frozen=True, slots=True)
class MockSmokeResult:
    """本地 smoke runner 结果摘要。"""

    base_url: str
    summary: PipelineRunSummary
    received_root: Path
    archive_upload_receipt: Path


def run_mock_control_plane_smoke(config: MockSmokeConfig) -> MockSmokeResult:
    """启动 mock server 并执行一轮本地 smoke。"""

    server = MockControlPlaneServer(
        MockControlPlaneConfig(
            fixture_dir=config.fixture_dir,
            storage_root=config.storage_root,
            host=config.host,
            port=config.port,
        )
    )
    server.start()
    try:
        run_id = f"mock-smoke-{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        runtime_root = config.output_root / "runtime" / run_id
        runtime_root.mkdir(parents=True, exist_ok=True)
        token_payload = ControlPlaneClient(
            ControlPlaneConfig(base_url=server.base_url)
        ).request_json("GET", "/api/baidu/token")
        baidu_token_file = runtime_root / "baidu-token.json"
        baidu_token_file.write_text(
            json.dumps(token_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (runtime_root / "database.json").write_text(
            json.dumps({"schema_version": 1, "entry_count": 0, "entries": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        state_db_result = bootstrap_state_database(
            database_path=runtime_root / "state.sqlite3",
            run_id=run_id,
            remote_database_payload={"schema_version": 1, "entry_count": 0, "entries": []},
        )
        runtime_config = PipelineRunConfig(
            mode=PipelineMode.REMOTE,
            game_region=config.game_region,
            output_root=config.output_root,
            temp_root=config.temp_root,
            log_root=config.output_root / "logs",
            baidu_remote_root=config.baidu_remote_root,
            run_id=run_id,
            state_db_path=state_db_result.database_path,
            control_plane_base_url=server.base_url,
            control_plane_requested_by=config.requested_by,
            champion_ids=config.champion_ids,
            include_maps=False,
            baidu_app_key=str(token_payload["app_key"]),
            baidu_secret_key=str(token_payload["secret_key"]),
            baidu_refresh_token=str(token_payload["refresh_token"]),
        )
        with patch_pipeline_for_simulation(
            runtime_config,
            receipt_dir=config.output_root / "smoke",
        ):
            summary = run_pipeline(runtime_config)
            UploadWorker(
                UploadWorkerConfig(
                    run_id=run_id,
                    state_db_path=state_db_result.database_path,
                    baidu_token_file=baidu_token_file,
                    baidu_remote_root=config.baidu_remote_root,
                    worker_id="mock-smoke-upload-worker",
                    output_root=config.output_root,
                )
            ).serve()
    finally:
        server.close()

    return MockSmokeResult(
        base_url=server.base_url,
        summary=summary,
        received_root=config.storage_root,
        archive_upload_receipt=config.output_root / "simulation" / "archive_upload.json",
    )


def build_parser() -> argparse.ArgumentParser:
    """构造 smoke runner CLI 参数。"""

    parser = argparse.ArgumentParser(description="运行本地 mock control plane smoke。")
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/mock_control_plane"),
        help="mock control plane 响应 fixture 目录。",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("output/mock_smoke"),
        help="本地 smoke 输出目录。",
    )
    parser.add_argument(
        "--temp-root",
        type=Path,
        default=Path("temp/mock_smoke"),
        help="本地 smoke 临时目录。",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=Path("temp/mock_control_plane"),
        help="mock control plane 接收到的请求落盘目录。",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--game-region", default="zh_CN")
    parser.add_argument("--baidu-remote-root", default="/apps/rift-audio-pipeline")
    parser.add_argument("--requested-by", default="mock-smoke")
    parser.add_argument("--champion-ids", default="1")
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""

    args = build_parser().parse_args(argv)
    result = run_mock_control_plane_smoke(
        MockSmokeConfig(
            fixture_dir=args.fixture_dir,
            output_root=args.output_root,
            temp_root=args.temp_root,
            storage_root=args.storage_root,
            host=args.host,
            port=args.port,
            game_region=args.game_region,
            baidu_remote_root=args.baidu_remote_root,
            requested_by=args.requested_by,
            champion_ids=_parse_id_list(args.champion_ids),
        )
    )
    print(
        json.dumps(
            {
                "base_url": result.base_url,
                "status": result.summary.status.value,
                "run_id": result.summary.run_id,
                "version": result.summary.version,
                "log_dir": str(result.summary.log_dir),
                "received_root": str(result.received_root),
                "archive_upload_receipt": str(result.archive_upload_receipt),
                "summary": _summary_to_json(result.summary),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.summary.status is PipelineRunStatus.SUCCESS else 1


def _summary_to_json(summary: PipelineRunSummary) -> dict[str, object]:
    """把运行摘要转换为 JSON 兼容结构。"""

    payload = asdict(summary)
    payload["mode"] = summary.mode.value
    payload["status"] = summary.status.value
    payload["log_dir"] = str(summary.log_dir)
    return payload


def _parse_id_list(raw_value: str) -> tuple[int, ...]:
    """把逗号分隔字符串解析为 ID 元组。"""

    normalized = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not normalized:
        raise ValueError("mock smoke 至少需要一个 champion id。")
    return tuple(int(item) for item in normalized)


if __name__ == "__main__":
    raise SystemExit(main())
