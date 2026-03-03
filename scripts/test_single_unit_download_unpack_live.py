"""单单位下载与解包链路实测脚本。"""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import shutil

import msgpack

from rift_audio_pipeline.asset_downloader import download_game_content_metadata
from rift_audio_pipeline.asset_downloader import download_game_wads_by_runtime_paths
from rift_audio_pipeline.asset_downloader import download_lcu_data_wads
from rift_audio_pipeline.audio_processor import run_bin_updater
from rift_audio_pipeline.audio_processor import run_data_updater
from rift_audio_pipeline.audio_processor import run_unpack_by_entity
from rift_audio_pipeline.game_dir_builder import build_simulated_dir
from rift_audio_pipeline.manifest_ops import get_latest_versions


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="单单位下载+解包实测")
    parser.add_argument("--region", default="zh_CN", help="语言区域")
    parser.add_argument("--champion-id", type=int, default=1, help="测试英雄 ID")
    parser.add_argument("--work-dir", default="temp/live_single_unit", help="测试工作目录")
    parser.add_argument("--workers", type=int, default=1, help="解包并发数")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="执行前清空工作目录",
    )
    return parser


def _read_data_msgpack(data_file_base: Path) -> dict:
    file = data_file_base.with_suffix(".msgpack")
    if not file.exists():
        raise FileNotFoundError(f"未找到 data.msgpack：{file}")
    with file.open("rb") as stream:
        return msgpack.unpackb(stream.read(), raw=False)


def main() -> int:
    args = _build_parser().parse_args()
    work_dir = Path(args.work_dir).expanduser().resolve()
    game_dir = work_dir / "mini_game"
    output_dir = work_dir / "output"
    download_dir = work_dir / "downloads"

    if args.clean and work_dir.exists():
        shutil.rmtree(work_dir)

    build_simulated_dir(game_dir)
    latest = get_latest_versions()

    metadata_file = download_game_content_metadata(
        game_manifest_url=latest.game_manifest_url,
        download_dir=download_dir / "game",
        game_path=game_dir,
    )
    lcu_wads = download_lcu_data_wads(
        lcu_manifest_url=latest.lcu_manifest_url,
        download_dir=download_dir / "lcu",
        game_path=game_dir,
        region=args.region,
    )

    data_file_base = run_data_updater(
        game_path=game_dir,
        output_path=output_dir,
        region=args.region,
        force_update=True,
    )
    data = _read_data_msgpack(data_file_base)
    champions = data.get("champions", {})
    champion = champions.get(str(args.champion_id))
    if not isinstance(champion, dict):
        raise ValueError(f"data.msgpack 中不存在 champion_id={args.champion_id}")
    wad_info = champion.get("wad", {})
    if not isinstance(wad_info, dict):
        raise ValueError(f"champion_id={args.champion_id} 缺少 wad 字段")
    root_wad = str(wad_info.get("root", ""))
    region_wad = str(wad_info.get(args.region, ""))
    if not root_wad or not region_wad:
        raise ValueError(f"champion_id={args.champion_id} 缺少 root 或 {args.region} WAD 路径")

    champion_wads = download_game_wads_by_runtime_paths(
        game_manifest_url=latest.game_manifest_url,
        download_dir=download_dir / "game",
        game_path=game_dir,
        runtime_wad_paths=(root_wad, region_wad),
    )

    run_bin_updater(
        champion_ids=(args.champion_id,),
        map_ids=tuple(),
        force_update=True,
        process_events=False,
    )
    run_unpack_by_entity(
        champion_ids=(args.champion_id,),
        map_ids=tuple(),
        max_workers=max(1, int(args.workers)),
    )

    audio_dir = output_dir / "audios" / "champions"
    print("=== 单单位链路验证成功 ===")
    print(f"work_dir={work_dir}")
    print(f"metadata={metadata_file}")
    print(f"lcu_wad_count={len(lcu_wads)}")
    print(f"champion_wad_count={len(champion_wads)}")
    print(f"data_file={data_file_base.with_suffix('.msgpack')}")
    print(f"audio_root={audio_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
