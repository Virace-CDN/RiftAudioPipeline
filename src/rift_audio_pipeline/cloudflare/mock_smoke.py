"""本地 mock control plane smoke runner。"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from rift_audio_pipeline.cloudflare.mock_server import MockControlPlaneConfig
from rift_audio_pipeline.cloudflare.mock_server import MockControlPlaneServer
import rift_audio_pipeline.pipeline.orchestrator as orchestrator
from rift_audio_pipeline.pipeline.models import EntityArtifacts
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.models import PipelineRunStatus
from rift_audio_pipeline.pipeline.models import PipelineRunSummary


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
    """启动 mock server 并执行一轮本地 smoke。

    Args:
        config: smoke runner 配置。

    Returns:
        MockSmokeResult: 本轮 smoke 的关键产物定位。
    """

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
        smoke_receipt_dir = config.output_root / "smoke"
        smoke_receipt_dir.mkdir(parents=True, exist_ok=True)
        archive_upload_receipt = smoke_receipt_dir / "archive_upload.json"
        log_upload_receipt = smoke_receipt_dir / "log_upload.json"
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    orchestrator,
                    "run_remote_pipeline",
                    _build_fake_run_remote_pipeline(),
                )
            )
            stack.enter_context(
                patch.object(
                    orchestrator,
                    "pack_champion",
                    _build_fake_pack_champion(),
                )
            )
            stack.enter_context(
                patch.object(
                    orchestrator,
                    "_upload_archives_for_run",
                    _build_fake_archive_upload(archive_upload_receipt),
                )
            )
            stack.enter_context(
                patch.object(
                    orchestrator,
                    "_create_baidu_client",
                    lambda config: _FakeBaiduClient(),
                )
            )
            stack.enter_context(
                patch.object(
                    orchestrator,
                    "upload_run_logs",
                    _build_fake_log_upload(log_upload_receipt),
                )
            )
            summary = orchestrator.run_pipeline(runtime_config)
    finally:
        server.close()

    return MockSmokeResult(
        base_url=server.base_url,
        summary=summary,
        received_root=config.storage_root,
        archive_upload_receipt=archive_upload_receipt,
        log_upload_receipt=log_upload_receipt,
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


def _build_fake_run_remote_pipeline() -> Any:
    """构造本地 fake remote 执行函数。"""

    def _fake_run_remote_pipeline(
        config: PipelineRunConfig,
        pair: object,
        log_ctx: object,
    ) -> list[EntityArtifacts]:
        del log_ctx
        version = getattr(pair, "version")
        if not isinstance(version, str):
            raise ValueError("mock smoke 缺少有效 version。")
        artifacts: list[EntityArtifacts] = []
        for champion_id in config.champion_ids or tuple():
            audio_dir = config.output_root / "audios" / version / f"{champion_id}-smoke"
            audio_dir.mkdir(parents=True, exist_ok=True)
            (audio_dir / "sample.txt").write_text("mock audio payload", encoding="utf-8")
            artifacts.append(
                EntityArtifacts(
                    entity_type="champion",
                    entity_id=champion_id,
                    audio_output_paths=(audio_dir,),
                )
            )
        return artifacts

    return _fake_run_remote_pipeline


def _build_fake_pack_champion() -> Any:
    """构造本地 fake 打包函数。"""

    def _fake_pack_champion(
        champion_dir: Path,
        output_path: Path,
        *,
        archive_name: str | None = None,
        report_file: Path | None = None,
        password: str | None = None,
        encrypt_filenames: bool = True,
        extra_files: tuple[Path, ...] = tuple(),
        compression_level: int = 0,
        seven_zip_executable: str | None = None,
    ) -> Path:
        del (
            report_file,
            password,
            encrypt_filenames,
            extra_files,
            compression_level,
            seven_zip_executable,
        )
        output_path.mkdir(parents=True, exist_ok=True)
        archive_path = output_path / f"{archive_name or champion_dir.name}.7z"
        archive_path.write_text("mock archive payload", encoding="utf-8")
        return archive_path

    return _fake_pack_champion


def _build_fake_archive_upload(receipt_path: Path) -> Any:
    """构造本地 fake archive 上传函数。"""

    def _fake_upload_archives_for_run(
        config: PipelineRunConfig,
        archives: tuple[Path, ...],
        version: str,
    ) -> None:
        _write_json(
            receipt_path,
            {
                "recorded_at": _timestamp_now(),
                "remote_root": config.baidu_remote_root,
                "version": version,
                "archives": [str(path) for path in archives],
            },
        )

    return _fake_upload_archives_for_run


def _build_fake_log_upload(receipt_path: Path) -> Any:
    """构造本地 fake 日志上传函数。"""

    def _fake_upload_run_logs(log_ctx: object, config: PipelineRunConfig, client: object) -> None:
        del client
        log_dir = getattr(log_ctx, "log_dir")
        run_id = getattr(log_ctx, "run_id")
        run_date = getattr(log_ctx, "run_date")
        if not isinstance(log_dir, Path):
            raise ValueError("mock smoke 缺少有效 log_dir。")
        _write_json(
            receipt_path,
            {
                "recorded_at": _timestamp_now(),
                "run_id": run_id,
                "remote_root": f"{config.baidu_remote_root.rstrip('/')}/logs/{run_date}/{run_id}",
                "files": sorted(
                    str(path.relative_to(log_dir))
                    for path in log_dir.rglob("*")
                    if path.is_file()
                ),
            },
        )

    return _fake_upload_run_logs


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


def _timestamp_now() -> str:
    """返回当前 ISO 8601 时间。"""

    return datetime.now().astimezone().isoformat()


def _write_json(file_path: Path, payload: object) -> None:
    """写入 UTF-8 JSON 文件。"""

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class _FakeBaiduClient:
    """满足 orchestrator close 调用的最小客户端。"""

    def close(self) -> None:
        """关闭 client。"""

        return None


if __name__ == "__main__":
    raise SystemExit(main())
