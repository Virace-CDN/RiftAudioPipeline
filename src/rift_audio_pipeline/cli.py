"""命令行入口。"""

from __future__ import annotations

import argparse
from argparse import BooleanOptionalAction

from rift_audio_pipeline.config import PipelineConfig
from rift_audio_pipeline.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    Returns:
        配置完成的参数解析器。
    """

    parser = argparse.ArgumentParser(description="LOL 语音资源自动化流水线")
    parser.add_argument("--output-path", required=True, help="输出目录（必填）")
    parser.add_argument("--game-path", default=None, help="本地游戏根目录")
    parser.add_argument("--region", default="zh_CN", help="语言区域")
    parser.add_argument(
        "--lcu-mode",
        default="full",
        choices=["full", "extract"],
        help="LCU 资源下载策略",
    )
    parser.add_argument(
        "--audio-types",
        nargs="+",
        default=["VO"],
        help="解包音频类型，例如 VO",
    )
    parser.add_argument("--temp-dir", default=None, help="临时目录")
    parser.add_argument(
        "--local-bin-dir",
        default=None,
        help="本地 bin 目录（将写入 output/manifest/<version>/bin_input）",
    )
    parser.add_argument(
        "--unpack-workers",
        type=int,
        default=2,
        help="解包并发线程数（低磁盘模式建议 1-2）",
    )
    parser.add_argument(
        "--low-disk-mode",
        action=BooleanOptionalAction,
        default=True,
        help="低磁盘模式，启用时按实体顺序解包并减少峰值占用",
    )
    parser.add_argument(
        "--baidu-remote-dir",
        default="/apps/lol-audio/",
        help="百度网盘目标目录",
    )
    parser.add_argument("--baidu-app-key", default=None, help="百度 app key")
    parser.add_argument("--baidu-secret-key", default=None, help="百度 secret key")
    parser.add_argument("--baidu-refresh-token", default=None, help="百度 refresh token")
    parser.add_argument("--dry-run", action="store_true", help="仅执行检测流程")
    return parser


def main() -> int:
    """命令行主函数。

    Returns:
        退出状态码，`0` 表示执行成功。
    """

    parser = build_parser()
    args = parser.parse_args()
    config = PipelineConfig.from_namespace(args)
    return run_pipeline(config=config)
