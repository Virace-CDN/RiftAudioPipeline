"""Pipeline CLI 入口。"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import Sequence

from rift_audio_pipeline.control_plane.simulation import maybe_patch_pipeline_for_simulation
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.orchestrator import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """构造 pipeline CLI 参数解析器。"""

    parser = argparse.ArgumentParser(description="运行 RiftAudioPipeline 主流程。")
    parser.add_argument("--mode", choices=[mode.value for mode in PipelineMode], required=True)
    parser.add_argument("--game-region", default="zh_CN")
    parser.add_argument("--output-root", type=Path, default=Path("output"))
    parser.add_argument("--temp-root", type=Path, default=Path("temp"))
    parser.add_argument("--log-root", type=Path, default=None)
    parser.add_argument("--run-id")
    parser.add_argument("--baidu-remote-root", default="/apps/rift-audio-pipeline")
    parser.add_argument("--remote-live-region")
    parser.add_argument("--baidu-app-key")
    parser.add_argument("--baidu-secret-key")
    parser.add_argument("--baidu-refresh-token")
    parser.add_argument("--current-version")
    parser.add_argument("--current-lcu-manifest-url")
    parser.add_argument("--current-game-manifest-url")
    parser.add_argument("--previous-version")
    parser.add_argument("--previous-lcu-manifest-url")
    parser.add_argument("--previous-game-manifest-url")
    parser.add_argument("--previous-match-mode")
    parser.add_argument("--previous-match-reason")
    parser.add_argument("--relay-socket-path", type=Path)
    parser.add_argument("--state-db-path", type=Path)
    parser.add_argument("--control-plane-base-url")
    parser.add_argument("--control-plane-bearer-token")
    parser.add_argument("--control-plane-access-client-id")
    parser.add_argument("--control-plane-access-client-secret")
    parser.add_argument("--control-plane-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--control-plane-requested-by")
    parser.add_argument("--game-path", type=Path)
    parser.add_argument("--wwiser-path", type=Path)
    parser.add_argument("--champion-ids")
    parser.add_argument("--map-ids")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--download-retry-attempts", type=int, default=3)
    parser.add_argument("--entity-retry-attempts", type=int, default=3)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--force-update", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-champions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-maps", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-update", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-extract", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--run-mapping", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--integrate-data", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--cleanup-remote", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dev-mode", action=argparse.BooleanOptionalAction, default=False)
    return parser


def build_run_config(args: argparse.Namespace) -> PipelineRunConfig:
    """把 CLI 参数转换为 `PipelineRunConfig`。"""

    output_root = args.output_root
    log_root = args.log_root or output_root / "logs"
    baidu_app_key = args.baidu_app_key or os.getenv("RIFT_BAIDU_APP_KEY")
    baidu_secret_key = args.baidu_secret_key or os.getenv("RIFT_BAIDU_SECRET_KEY")
    baidu_refresh_token = args.baidu_refresh_token or os.getenv("RIFT_BAIDU_REFRESH_TOKEN")
    return PipelineRunConfig(
        mode=PipelineMode(args.mode),
        game_region=args.game_region,
        output_root=output_root,
        temp_root=args.temp_root,
        log_root=log_root,
        run_id=args.run_id,
        baidu_remote_root=args.baidu_remote_root,
        remote_live_region=args.remote_live_region,
        baidu_app_key=baidu_app_key,
        baidu_secret_key=baidu_secret_key,
        baidu_refresh_token=baidu_refresh_token,
        current_version=args.current_version,
        current_lcu_manifest_url=args.current_lcu_manifest_url,
        current_game_manifest_url=args.current_game_manifest_url,
        previous_version=args.previous_version,
        previous_lcu_manifest_url=args.previous_lcu_manifest_url,
        previous_game_manifest_url=args.previous_game_manifest_url,
        previous_match_mode=args.previous_match_mode,
        previous_match_reason=args.previous_match_reason,
        relay_socket_path=args.relay_socket_path,
        state_db_path=args.state_db_path,
        control_plane_base_url=args.control_plane_base_url,
        control_plane_bearer_token=args.control_plane_bearer_token,
        control_plane_access_client_id=args.control_plane_access_client_id,
        control_plane_access_client_secret=args.control_plane_access_client_secret,
        control_plane_timeout_seconds=args.control_plane_timeout_seconds,
        control_plane_requested_by=args.control_plane_requested_by,
        game_path=args.game_path,
        wwiser_path=args.wwiser_path,
        force_update=args.force_update,
        include_champions=args.include_champions,
        include_maps=args.include_maps,
        champion_ids=_parse_id_list(args.champion_ids),
        map_ids=_parse_id_list(args.map_ids),
        run_update=args.run_update,
        run_extract=args.run_extract,
        run_mapping=args.run_mapping,
        integrate_data=args.integrate_data,
        cleanup_remote=args.cleanup_remote,
        dev_mode=args.dev_mode,
        max_workers=args.max_workers,
        download_retry_attempts=args.download_retry_attempts,
        entity_retry_attempts=args.entity_retry_attempts,
        log_level=args.log_level,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主入口。"""

    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = build_run_config(args)
    patch_context = maybe_patch_pipeline_for_simulation(config)
    with patch_context if patch_context is not None else nullcontext():
        summary = run_pipeline(config)
    print(json.dumps(_to_json_compatible(asdict(summary)), ensure_ascii=False, indent=2))
    return 0 if summary.status == "success" else 1


def _parse_id_list(raw_value: str | None) -> tuple[int, ...] | None:
    """把逗号分隔 ID 字符串转换为整数元组。"""

    if raw_value is None:
        return None
    normalized_values = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not normalized_values:
        return tuple()
    return tuple(int(item) for item in normalized_values)


def _to_json_compatible(value: object) -> object:
    """把摘要对象转换为 JSON 兼容结构。"""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_compatible(item) for item in value]
    if hasattr(value, "value"):
        enum_value = getattr(value, "value")
        if isinstance(enum_value, str):
            return enum_value
    return value


if __name__ == "__main__":
    raise SystemExit(main())
