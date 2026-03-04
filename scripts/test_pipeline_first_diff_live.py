"""本地完整 Pipeline 联调脚本（首次/非首次 diff，单单位）。"""

from __future__ import annotations

from argparse import ArgumentParser
from argparse import BooleanOptionalAction
import base64
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from typing import Iterator
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen

from loguru import logger
from riotmanifest import RiotGameData
from rift_audio_pipeline.baidu.oauth import load_baidu_app_credentials
from rift_audio_pipeline.baidu.oauth import resolve_token_store
from rift_audio_pipeline.config import PipelineConfig
from rift_audio_pipeline.manifest_ops import LatestVersions
from rift_audio_pipeline.manifest_ops import LOCAL_STATE_SCHEMA_VERSION
from rift_audio_pipeline.manifest_ops import LocalRunState
from rift_audio_pipeline.manifest_ops import ManifestVoiceFilterResult
from rift_audio_pipeline.manifest_ops import evaluate_update_need_with_latest
from rift_audio_pipeline.manifest_ops import get_latest_versions
from rift_audio_pipeline.manifest_ops import load_local_state
from rift_audio_pipeline.manifest_ops import save_local_state
import rift_audio_pipeline.pipeline as pipeline_module

DEFAULT_WORK_DIR = Path("temp/live_pipeline_first_diff")
DEFAULT_REMOTE_DIR = "/apps/lol-audio/"
GITHUB_API_BASE = (
    "https://api.github.com/repos/Morilli/riot-manifests/contents/LoL/EUW1/windows/lol-game-client"
)
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/Morilli/riot-manifests/main/LoL/EUW1/windows/lol-game-client"
)
LOG_LEVEL_CHOICES = ("TRACE", "DEBUG", "INFO", "WARNING", "ERROR")


def _build_parser() -> ArgumentParser:
    """构建命令行参数。"""

    parser = ArgumentParser(description="本地完整 Pipeline 联调（首次/非首次 diff）")
    parser.add_argument(
        "--mode",
        choices=("first", "diff", "both", "upload"),
        default="both",
        help="执行模式：首次、非首次 diff、两者都跑，或仅上传",
    )
    parser.add_argument("--region", default="zh_CN", help="语言区域")
    parser.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR), help="本地测试工作目录")
    parser.add_argument(
        "--game-path",
        default=None,
        help="可选真实游戏目录；不传则自动构建最小游戏目录",
    )
    parser.add_argument(
        "--temp-game-dir",
        default=None,
        help="模拟目录路径（仅在未传 --game-path 时生效）",
    )
    parser.add_argument(
        "--audio-type",
        default="VO",
        choices=("VO", "SFX", "MUSIC"),
        help="打包与上传使用的资源类型",
    )
    parser.add_argument(
        "--limit-units",
        type=int,
        default=1,
        help="限制处理单位数量（优先英雄）",
    )
    parser.add_argument(
        "--previous-version",
        default="16.3.7457600",
        help="diff 模式写入本地历史状态的旧版本号",
    )
    parser.add_argument(
        "--latest-version-override",
        default=None,
        help="测试用最新版本覆盖（例如 16.3.7457600，仅用于本地联调）",
    )
    parser.add_argument(
        "--upload-game-version",
        default=None,
        help="upload 模式指定打包版本目录（例如 16.4）；不传则自动选择最新目录",
    )
    parser.add_argument(
        "--allow-missing-remote-index",
        action=BooleanOptionalAction,
        default=True,
        help="upload 模式是否允许远端索引缺失并自动初始化",
    )
    parser.add_argument(
        "--unpack-workers",
        type=int,
        default=1,
        help="解包并发线程数",
    )
    parser.add_argument(
        "--download-concurrency",
        type=int,
        default=8,
        help="模拟目录下载并发数（LCU/GAME manifest 下载）",
    )
    parser.add_argument(
        "--diff-bin-filter-workers",
        type=int,
        default=4,
        help="WADExtractor 二次筛选外层并发（按英雄/地图单位）",
    )
    parser.add_argument(
        "--diff-bin-extract-concurrency",
        type=int,
        default=6,
        help="WADExtractor 内部下载并发（prefetch_chunk_concurrency）",
    )
    parser.add_argument(
        "--diff-bin-filter-threshold",
        type=int,
        default=100,
        help="清单层 WAD 更新数达到阈值时跳过 WADExtractor 二次筛选",
    )
    parser.add_argument(
        "--diff-smoke-single-champion",
        action=BooleanOptionalAction,
        default=True,
        help="diff 联调快捷模式：命中首个可解包英雄后立即进入下载流程",
    )
    parser.add_argument(
        "--low-disk-mode",
        action=BooleanOptionalAction,
        default=True,
        help="是否启用低磁盘流式模式",
    )
    parser.add_argument(
        "--remote-dir",
        default=DEFAULT_REMOTE_DIR,
        help="百度网盘目标目录",
    )
    parser.add_argument(
        "--dev-config",
        default=".dev.baidu",
        help="百度开发者配置文件（AppKey/SecretKey）",
    )
    parser.add_argument(
        "--token-file",
        default=".config/baidu/token.json",
        help="百度 token 文件（refresh token 来源）",
    )
    parser.add_argument("--app-key", default=None, help="可选覆盖 app key")
    parser.add_argument("--secret-key", default=None, help="可选覆盖 secret key")
    parser.add_argument("--refresh-token", default=None, help="可选覆盖 refresh token")
    parser.add_argument("--pack-password", default=None, help="7z 打包密码")
    parser.add_argument(
        "--pack-encrypt-filenames",
        action=BooleanOptionalAction,
        default=True,
        help="启用密码时是否加密文件名",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=LOG_LEVEL_CHOICES,
        help="日志输出级别，排障建议使用 TRACE 或 DEBUG",
    )
    parser.add_argument("--clean", action="store_true", help="执行前清空 work_dir")
    return parser


def _configure_log_level(level: str) -> None:
    """配置全局日志输出等级。"""

    normalized = level.strip().upper()
    logger.remove()
    logger.add(
        sys.stderr,
        level=normalized,
        colorize=True,
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )


def _http_get_json(url: str) -> dict[str, Any]:
    """执行 HTTP GET 并解析 JSON。"""

    request = Request(
        url=url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "RiftAudioPipeline-PipelineLiveTest",
        },
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_manifest_url_from_repo(version: str) -> str:
    """读取指定版本 manifest URL（优先发布源，回退 Morilli 仓库）。"""

    file_name = f"{version}.txt"
    releases = RiotGameData()
    releases.load_game_data(regions=["EUW1"])
    release_items = getattr(releases, "_game_data", {}).get("EUW1", [])
    for item in release_items:
        if str(item.get("version", "")).strip() != version.strip():
            continue
        release_url = str(item.get("url", "")).strip()
        if release_url:
            return release_url

    try:
        payload = _http_get_json(f"{GITHUB_API_BASE}/{quote(file_name)}")
    except HTTPError as error:
        if error.code != 403:
            raise
        fallback_url = f"{GITHUB_RAW_BASE}/{quote(file_name)}"
        request = Request(
            fallback_url,
            headers={"User-Agent": "RiftAudioPipeline-PipelineLiveTest"},
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8").strip()
    encoded_content = str(payload.get("content", "")).replace("\n", "")
    if not encoded_content:
        raise RuntimeError(f"读取版本清单失败，缺少 content 字段：{file_name}")
    return base64.b64decode(encoded_content).decode("utf-8").strip()


def _limit_targets_to_units(targets: object, limit_units: int) -> object:
    """将处理目标截断到指定数量（优先英雄）。"""

    if limit_units <= 0:
        return targets

    champion_ids = tuple(int(item) for item in getattr(targets, "champion_ids", tuple()))
    map_ids = tuple(int(item) for item in getattr(targets, "map_ids", tuple()))

    selected_champions = champion_ids[:limit_units]
    if selected_champions:
        return type(targets)(champion_ids=selected_champions, map_ids=tuple())

    selected_maps = map_ids[:limit_units]
    return type(targets)(champion_ids=tuple(), map_ids=selected_maps)


def _build_latest_versions_override(version: str) -> LatestVersions:
    """构建测试用“最新版本”覆盖对象。"""

    normalized_version = version.strip()
    if not normalized_version:
        raise ValueError("latest_version_override 不能为空。")
    latest = get_latest_versions()
    manifest_url = _fetch_manifest_url_from_repo(normalized_version)
    return LatestVersions(
        game_version=normalized_version,
        game_manifest_url=manifest_url,
        lcu_version=latest.lcu_version,
        lcu_manifest_url=latest.lcu_manifest_url,
    )


def _is_champion_manifest_wad_path(path: str) -> bool:
    """判断 manifest WAD 路径是否为英雄资源。"""

    return "/champions/" in path.strip().replace("\\", "/").casefold()


def _build_single_champion_smoke_filter(
    original_filter: Callable[..., ManifestVoiceFilterResult],
) -> Callable[..., ManifestVoiceFilterResult]:
    """构建 diff 联调快捷筛选函数。

    规则：
    - 按 `update_paths` 顺序逐个探测；
    - 优先命中“可解包英雄”并立即返回；
    - 若无英雄可解包但存在其他可解包条目，返回首个可解包结果；
    - 若均不可解包，返回聚合后的“全跳过”结果。
    """

    def _patched_filter(**kwargs: object) -> ManifestVoiceFilterResult:
        update_paths_obj = kwargs.get("update_paths", tuple())
        if not isinstance(update_paths_obj, tuple):
            update_paths = tuple(update_paths_obj) if isinstance(update_paths_obj, list) else tuple()
        else:
            update_paths = update_paths_obj
        normalized_paths = tuple(
            path.strip().replace("\\", "/")
            for path in update_paths
            if isinstance(path, str) and path.strip()
        )
        if len(normalized_paths) <= 1:
            return original_filter(**kwargs)

        first_unpack_result: ManifestVoiceFilterResult | None = None
        all_skipped: set[str] = set()
        all_decisions: list[object] = []
        for index, manifest_path in enumerate(normalized_paths):
            single_kwargs = dict(kwargs)
            single_kwargs["update_paths"] = (manifest_path,)
            result = original_filter(**single_kwargs)
            all_decisions.extend(result.decisions)
            all_skipped.update(result.skipped_paths)
            if not result.unpack_paths:
                continue
            if any(_is_champion_manifest_wad_path(path) for path in result.unpack_paths):
                logger.info(
                    "diff 联调快捷模式命中可解包英雄，提前进入下载流程：probe_index={}, path={}",
                    index,
                    manifest_path,
                )
                return result
            if first_unpack_result is None:
                first_unpack_result = result

        if first_unpack_result is not None:
            logger.info("diff 联调快捷模式未命中英雄，回退到首个可解包路径。")
            return first_unpack_result

        return ManifestVoiceFilterResult(
            unpack_paths=tuple(),
            skipped_paths=tuple(sorted(all_skipped or set(normalized_paths), key=str.casefold)),
            decisions=tuple(all_decisions),
        )

    return _patched_filter


@contextmanager
def _patch_pipeline_for_local_live_test(
    state_file: Path,
    limit_units: int,
    latest_versions_override: LatestVersions | None,
    diff_smoke_single_champion: bool,
) -> Iterator[None]:
    """临时 patch Pipeline 状态路径与目标解析函数。"""

    original_state_file = pipeline_module.DEFAULT_LOCAL_STATE_FILE
    original_resolve_processing_targets = pipeline_module.resolve_processing_targets
    original_resolve_all_processing_targets = pipeline_module.resolve_all_processing_targets
    original_evaluate_update_need = pipeline_module.evaluate_update_need
    original_filter_wad_changes = pipeline_module.filter_wad_changes_by_bin_voice_paths

    def _limited_resolve_processing_targets(
        data_file_base: Path,
        champion_aliases: tuple[str, ...] | list[str],
        map_ids: tuple[str, ...] | list[str],
    ) -> object:
        targets = original_resolve_processing_targets(
            data_file_base=data_file_base,
            champion_aliases=champion_aliases,
            map_ids=map_ids,
        )
        return _limit_targets_to_units(targets=targets, limit_units=limit_units)

    def _limited_resolve_all_processing_targets(data_file_base: Path) -> object:
        targets = original_resolve_all_processing_targets(data_file_base=data_file_base)
        return _limit_targets_to_units(targets=targets, limit_units=limit_units)

    def _patched_evaluate_update_need(
        region: str,
        state_file: Path = pipeline_module.DEFAULT_LOCAL_STATE_FILE,
        game_release_region: str = "EUW1",
        lcu_release_region: str = "EUW",
    ) -> object:
        del game_release_region, lcu_release_region
        if latest_versions_override is None:
            return original_evaluate_update_need(region=region, state_file=state_file)
        previous_state = load_local_state(state_file=state_file)
        return evaluate_update_need_with_latest(
            region=region,
            latest_versions=latest_versions_override,
            previous_state=previous_state,
        )

    pipeline_module.DEFAULT_LOCAL_STATE_FILE = state_file
    pipeline_module.resolve_processing_targets = _limited_resolve_processing_targets
    pipeline_module.resolve_all_processing_targets = _limited_resolve_all_processing_targets
    pipeline_module.evaluate_update_need = _patched_evaluate_update_need
    if diff_smoke_single_champion:
        pipeline_module.filter_wad_changes_by_bin_voice_paths = _build_single_champion_smoke_filter(
            original_filter=original_filter_wad_changes
        )
    try:
        yield
    finally:
        pipeline_module.DEFAULT_LOCAL_STATE_FILE = original_state_file
        pipeline_module.resolve_processing_targets = original_resolve_processing_targets
        pipeline_module.resolve_all_processing_targets = original_resolve_all_processing_targets
        pipeline_module.evaluate_update_need = original_evaluate_update_need
        pipeline_module.filter_wad_changes_by_bin_voice_paths = original_filter_wad_changes


def _prepare_first_run_state(state_file: Path) -> None:
    """准备首次运行状态（删除本地历史状态）。"""

    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.unlink(missing_ok=True)


def _prepare_diff_run_state(state_file: Path, previous_version: str) -> LocalRunState:
    """准备非首次 diff 状态（写入旧版本历史状态）。"""

    latest = get_latest_versions()
    if previous_version.strip() == latest.game_version.strip():
        raise ValueError(
            "diff 模式要求 previous_version 与当前最新版本不同："
            f"previous_version={previous_version}, latest={latest.game_version}"
        )
    previous_manifest_url = _fetch_manifest_url_from_repo(previous_version)
    checked_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    state = LocalRunState(
        schema_version=LOCAL_STATE_SCHEMA_VERSION,
        game_version=previous_version,
        game_manifest_url=previous_manifest_url,
        lcu_version=latest.lcu_version,
        lcu_manifest_url=latest.lcu_manifest_url,
        checked_at=checked_at,
    )
    save_local_state(state=state, state_file=state_file)
    return state


def _build_pipeline_config(
    region: str,
    output_path: Path,
    game_path: Path | None,
    temp_game_dir: Path,
    audio_type: str,
    download_concurrency: int,
    diff_bin_filter_workers: int,
    diff_bin_extract_concurrency: int,
    diff_bin_filter_threshold: int,
    unpack_workers: int,
    low_disk_mode: bool,
    remote_dir: str,
    app_key: str,
    secret_key: str,
    refresh_token: str,
    pack_password: str | None,
    pack_encrypt_filenames: bool,
) -> PipelineConfig:
    """构建脚本专用 Pipeline 配置。"""

    return PipelineConfig(
        output_path=output_path,
        game_region=region,
        game_path=game_path,
        audio_types=(audio_type,),
        temp_dir=temp_game_dir,
        baidu_pan_remote_dir=remote_dir,
        baidu_pan_app_key=app_key,
        baidu_pan_secret_key=secret_key,
        baidu_pan_refresh_token=refresh_token,
        download_concurrency=max(1, download_concurrency),
        diff_bin_filter_workers=max(1, diff_bin_filter_workers),
        diff_bin_extract_concurrency=max(1, diff_bin_extract_concurrency),
        diff_bin_filter_threshold=diff_bin_filter_threshold,
        unpack_workers=max(1, unpack_workers),
        low_disk_mode=low_disk_mode,
        enable_pack=True,
        enable_upload=True,
        pack_password=pack_password,
        pack_encrypt_filenames=pack_encrypt_filenames,
    )


def _collect_upload_archives(
    output_path: Path,
    game_version: str | None,
    limit_units: int,
) -> tuple[str, tuple[Path, ...]]:
    """收集 upload 模式所需压缩包。"""

    packages_root = output_path / "packages"
    if game_version is None:
        if not packages_root.is_dir():
            raise FileNotFoundError(f"未找到 packages 目录：{packages_root}")
        version_dirs = sorted(
            (item for item in packages_root.iterdir() if item.is_dir()),
            key=lambda item: item.name.casefold(),
        )
        if not version_dirs:
            raise FileNotFoundError(f"packages 目录为空：{packages_root}")
        resolved_version = version_dirs[-1].name
    else:
        resolved_version = game_version.strip()
    package_dir = packages_root / resolved_version
    if not package_dir.is_dir():
        raise FileNotFoundError(f"未找到指定版本打包目录：{package_dir}")

    archives = tuple(
        sorted(
            (item for item in package_dir.rglob("*.7z") if item.is_file()),
            key=lambda item: item.as_posix().casefold(),
        )
    )
    if not archives:
        raise FileNotFoundError(f"未找到可上传压缩包：{package_dir}")
    if limit_units > 0:
        archives = archives[:limit_units]
    return resolved_version, archives


def main() -> int:
    """脚本主入口。"""

    args = _build_parser().parse_args()
    _configure_log_level(level=str(args.log_level))
    work_dir = Path(args.work_dir).expanduser().resolve()
    if args.clean and work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    output_path = work_dir / "output"
    state_file = work_dir / "state" / "run_history.json"
    game_path = Path(args.game_path).expanduser().resolve() if args.game_path else None
    temp_game_dir = (
        Path(args.temp_game_dir).expanduser().resolve()
        if args.temp_game_dir
        else (work_dir / "mini_game")
    )

    app_credentials = load_baidu_app_credentials(
        app_key=args.app_key,
        secret_key=args.secret_key,
        dev_config_file=Path(args.dev_config).expanduser().resolve(),
    )
    token_store = resolve_token_store(token_file=Path(args.token_file).expanduser().resolve())
    token = token_store.load_token()
    refresh_token = str(args.refresh_token or token.refresh_token)

    config = _build_pipeline_config(
        region=str(args.region),
        output_path=output_path,
        game_path=game_path,
        temp_game_dir=temp_game_dir,
        audio_type=str(args.audio_type).upper(),
        download_concurrency=int(args.download_concurrency),
        diff_bin_filter_workers=int(args.diff_bin_filter_workers),
        diff_bin_extract_concurrency=int(args.diff_bin_extract_concurrency),
        diff_bin_filter_threshold=int(args.diff_bin_filter_threshold),
        unpack_workers=int(args.unpack_workers),
        low_disk_mode=bool(args.low_disk_mode),
        remote_dir=str(args.remote_dir),
        app_key=app_credentials.app_key,
        secret_key=app_credentials.secret_key,
        refresh_token=refresh_token,
        pack_password=args.pack_password,
        pack_encrypt_filenames=bool(args.pack_encrypt_filenames),
    )

    print("=== Pipeline 本地联调参数 ===")
    print(f"mode={args.mode}")
    print(f"work_dir={work_dir}")
    print(f"state_file={state_file}")
    print(f"region={args.region}")
    print(f"remote_dir={args.remote_dir}")
    print(f"limit_units={max(1, int(args.limit_units))}")
    print(f"download_concurrency={max(1, int(args.download_concurrency))}")
    print(f"diff_bin_filter_workers={max(1, int(args.diff_bin_filter_workers))}")
    print(f"diff_bin_extract_concurrency={max(1, int(args.diff_bin_extract_concurrency))}")
    print(f"diff_bin_filter_threshold={int(args.diff_bin_filter_threshold)}")
    print(f"diff_smoke_single_champion={bool(args.diff_smoke_single_champion)}")
    print(f"game_path={game_path}")
    print(f"temp_game_dir={temp_game_dir}")
    print(f"latest_version_override={args.latest_version_override}")

    latest_versions_override = (
        _build_latest_versions_override(str(args.latest_version_override))
        if args.latest_version_override
        else None
    )
    if args.mode == "upload":
        upload_version, upload_archives = _collect_upload_archives(
            output_path=output_path,
            game_version=args.upload_game_version,
            limit_units=max(1, int(args.limit_units)),
        )
        print("=== 开始 upload 模式 ===")
        print(f"upload_game_version={upload_version}")
        print(f"archive_count={len(upload_archives)}")
        for archive in upload_archives:
            print(f"- {archive}")
        manifest_file = pipeline_module._upload_archives_and_manifest(
            config=config,
            game_version=upload_version,
            archives=upload_archives,
            allow_missing_remote_index=bool(args.allow_missing_remote_index),
            run_record_collector=None,
        )
        print("=== upload 模式完成 ===")
        print(f"manifest_file={manifest_file}")
        return 0

    run_results: list[tuple[str, int]] = []
    with _patch_pipeline_for_local_live_test(
        state_file=state_file,
        limit_units=max(1, int(args.limit_units)),
        latest_versions_override=latest_versions_override,
        diff_smoke_single_champion=bool(args.diff_smoke_single_champion),
    ):
        if args.mode in ("first", "both"):
            _prepare_first_run_state(state_file=state_file)
            print("=== 开始首次模式 ===")
            first_code = pipeline_module.run_pipeline(config=config)
            run_results.append(("first", first_code))
            if first_code != 0:
                print(f"首次模式失败，exit_code={first_code}")
                return first_code

        if args.mode in ("diff", "both"):
            diff_state = _prepare_diff_run_state(
                state_file=state_file,
                previous_version=str(args.previous_version),
            )
            print("=== 开始 diff 模式 ===")
            print(
                "diff 基线状态："
                f"game_version={diff_state.game_version}, "
                f"manifest_url={diff_state.game_manifest_url}"
            )
            diff_code = pipeline_module.run_pipeline(config=config)
            run_results.append(("diff", diff_code))
            if diff_code != 0:
                print(f"diff 模式失败，exit_code={diff_code}")
                return diff_code

    print("=== 联调完成 ===")
    for mode_name, code in run_results:
        print(f"{mode_name}: exit_code={code}")
    print(f"本地状态文件：{state_file}")
    print(f"本地输出目录：{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
