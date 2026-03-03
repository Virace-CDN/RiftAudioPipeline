"""主流程编排模块。"""

from __future__ import annotations

from loguru import logger

from rift_audio_pipeline.baidu_pan import ensure_official_sdk_path
from rift_audio_pipeline.config import PipelineConfig


def run_pipeline(config: PipelineConfig) -> int:
    """执行流水线主入口。

    Args:
        config: 流水线配置对象。

    Returns:
        退出状态码，`0` 表示执行成功。
    """

    config.output_path.mkdir(parents=True, exist_ok=True)
    sdk_dir = ensure_official_sdk_path()
    logger.info("已加载百度官方 SDK 目录：{}", sdk_dir)
    logger.info(
        "流水线骨架已就绪，后续将按阶段实现 Manifest、解包、上传流程。dry_run={}",
        config.dry_run,
    )
    return 0
