"""本地 mock control plane smoke runner。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from dataclasses import dataclass
import json
from pathlib import Path

from rift_audio_pipeline.control_plane.mock_server import MockControlPlaneConfig
from rift_audio_pipeline.control_plane.mock_server import MockControlPlaneServer
from rift_audio_pipeline.control_plane.simulation import patch_pipeline_for_simulation
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunSummary
from rift_audio_pipeline.pipeline.orchestrator import run_pipeline


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
    log_upload_receipt: Path


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
        runtime_config = PipelineRunConfig(
            mode=PipelineMode.REMOTE,
            game_region=config.game_region,
            output_root=config.output_root,
            temp_root=config.temp_root,
            log_root=config.output_root / "logs",
            baidu_remote_root=config.baidu_remote_root,
            control_plane_base_url=server.base_url,
            control_plane_requested_by=config.requested_by,
            champion_ids=config.champion_ids,
            include_maps=False,
        )
        with patch_pipeline_for_simulation(
            runtime_config,
            receipt_dir=config.output_root / "smoke",
        ) as artifact_paths:
            summary = run_pipeline(runtime_config)
    finally:
        server.close()

    return MockSmokeResult(
        base_url=server.base_url,
        summary=summary,
        received_root=config.storage_root,
        archive_upload_receipt=artifact_paths.archive_upload_receipt,
        log_upload_receipt=artifact_paths.log_upload_receipt,
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
                "log_upload_receipt": str(result.log_upload_receipt),
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
