"""项目配置管理。"""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
import os

DEFAULT_GAME_REGION = "zh_CN"
DEFAULT_LCU_DOWNLOAD_MODE = "full"
DEFAULT_BAIDU_PAN_REMOTE_DIR = "/apps/lol-audio/"
DEFAULT_AUDIO_TYPES: tuple[str, ...] = ("VO",)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """流水线运行配置。

    Args:
        output_path: 输出目录，必须存在或可创建。
        game_region: 游戏区域标识。
        game_path: 本地游戏路径。
        lcu_download_mode: LCU 下载策略，支持 `full` 或 `extract`。
        audio_types: 音频类型列表。
        temp_dir: 临时目录。
        baidu_pan_remote_dir: 百度网盘上传目标目录。
        baidu_pan_app_key: 百度开放平台 app key。
        baidu_pan_secret_key: 百度开放平台 secret key。
        baidu_pan_refresh_token: 百度开放平台 refresh token。
        dry_run: 仅检测，不执行耗时步骤。
    """

    output_path: Path
    game_region: str = DEFAULT_GAME_REGION
    game_path: Path | None = None
    lcu_download_mode: str = DEFAULT_LCU_DOWNLOAD_MODE
    audio_types: tuple[str, ...] = DEFAULT_AUDIO_TYPES
    temp_dir: Path | None = None
    baidu_pan_remote_dir: str = DEFAULT_BAIDU_PAN_REMOTE_DIR
    baidu_pan_app_key: str | None = None
    baidu_pan_secret_key: str | None = None
    baidu_pan_refresh_token: str | None = None
    dry_run: bool = False

    @classmethod
    def from_namespace(cls, args: Namespace) -> PipelineConfig:
        """从 CLI 参数和环境变量构建配置。

        Args:
            args: `argparse` 解析得到的参数对象。

        Returns:
            完整的流水线配置对象。
        """

        env_app_key = os.getenv("BAIDU_PAN_APP_KEY")
        env_secret_key = os.getenv("BAIDU_PAN_SECRET_KEY")
        env_refresh_token = os.getenv("BAIDU_PAN_REFRESH_TOKEN")
        output_path = Path(args.output_path).expanduser().resolve()
        game_path = Path(args.game_path).expanduser().resolve() if args.game_path else None
        temp_dir = Path(args.temp_dir).expanduser().resolve() if args.temp_dir else None

        return cls(
            output_path=output_path,
            game_region=args.region,
            game_path=game_path,
            lcu_download_mode=args.lcu_mode,
            audio_types=tuple(args.audio_types),
            temp_dir=temp_dir,
            baidu_pan_remote_dir=args.baidu_remote_dir,
            baidu_pan_app_key=args.baidu_app_key or env_app_key,
            baidu_pan_secret_key=args.baidu_secret_key or env_secret_key,
            baidu_pan_refresh_token=args.baidu_refresh_token or env_refresh_token,
            dry_run=args.dry_run,
        )
