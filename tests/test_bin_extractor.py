"""bin 输入目录工具测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from rift_audio_pipeline.bin_extractor import LOCAL_BIN_FLAG_FILE
from rift_audio_pipeline.bin_extractor import seed_bin_input_from_directory
from rift_audio_pipeline.bin_extractor import write_many_to_bin_input
from rift_audio_pipeline.bin_extractor import write_to_bin_input


def test_write_many_to_bin_input_should_create_files_and_flag(tmp_path: Path) -> None:
    """批量写入后应生成目标文件并创建本地 bin 标志。"""

    version_dir = tmp_path / "manifest" / "16.4"
    written = write_many_to_bin_input(
        version_dir=version_dir,
        bin_payloads={
            "data/characters/Ahri/skins/skin0.bin": b"ahri",
            "data\\maps\\shipping\\map11\\map11.bin": b"map11",
        },
        enable_local_bin=True,
    )

    assert len(written) == 2
    assert (
        version_dir / "bin_input" / "data" / "characters" / "Ahri" / "skins" / "skin0.bin"
    ).read_bytes() == b"ahri"
    assert (
        version_dir / "bin_input" / "data" / "maps" / "shipping" / "map11" / "map11.bin"
    ).read_bytes() == b"map11"
    assert (version_dir / LOCAL_BIN_FLAG_FILE).exists()


def test_seed_bin_input_from_directory_should_only_import_bin_files(tmp_path: Path) -> None:
    """目录导入应仅写入 `.bin` 文件并保留相对结构。"""

    source_dir = tmp_path / "downloaded_bins"
    (source_dir / "data" / "maps" / "shipping" / "map11").mkdir(parents=True, exist_ok=True)
    (source_dir / "data" / "maps" / "shipping" / "map11" / "map11.bin").write_bytes(b"bin")
    (source_dir / "data" / "maps" / "shipping" / "map11" / "ignore.txt").write_text(
        "x", encoding="utf-8"
    )

    version_dir = tmp_path / "manifest" / "16.4"
    written = seed_bin_input_from_directory(version_dir=version_dir, source_dir=source_dir)

    assert len(written) == 1
    assert (
        version_dir / "bin_input" / "data" / "maps" / "shipping" / "map11" / "map11.bin"
    ).exists()
    assert not (
        version_dir / "bin_input" / "data" / "maps" / "shipping" / "map11" / "ignore.txt"
    ).exists()


def test_write_to_bin_input_should_reject_unsafe_path(tmp_path: Path) -> None:
    """写入路径包含越界段时应抛错。"""

    with pytest.raises(ValueError):
        write_to_bin_input(
            version_dir=tmp_path,
            relative_path="../escape.bin",
            content=b"",
        )
