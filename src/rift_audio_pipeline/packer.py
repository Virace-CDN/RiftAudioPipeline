"""打包模块。"""

from __future__ import annotations

from pathlib import Path


def pack_champion(champion_dir: Path, output_path: Path) -> Path:
    """打包单个英雄语音目录。

    Args:
        champion_dir: 英雄语音目录。
        output_path: 打包产物目录。

    Returns:
        产物路径。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第四阶段实现。
    """

    raise NotImplementedError(
        f"待实现：打包单英雄目录，champion_dir={champion_dir}, output_path={output_path}"
    )


def pack_all(audio_dir: Path, output_dir: Path) -> tuple[Path, ...]:
    """批量打包语音目录。

    Args:
        audio_dir: 音频目录。
        output_dir: 产物目录。

    Returns:
        打包产物路径集合。

    Raises:
        NotImplementedError: 当前仅完成目录骨架，待第四阶段实现。
    """

    raise NotImplementedError(f"待实现：批量打包，audio_dir={audio_dir}, output_dir={output_dir}")
