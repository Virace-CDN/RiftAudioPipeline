"""最小游戏目录构建工具测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rift_audio_pipeline.game_dir_builder import build_simulated_dir
from rift_audio_pipeline.game_dir_builder import cleanup_updater_inputs
from rift_audio_pipeline.game_dir_builder import stage_wad_file
from rift_audio_pipeline.game_dir_builder import write_content_metadata


def test_build_simulated_dir_should_create_required_directories(tmp_path: Path) -> None:
    """应创建 `Game` 与 `LeagueClient` 的最低目录结构。"""

    game_dir = build_simulated_dir(tmp_path / "sim_game")

    assert (game_dir / "Game" / "DATA" / "FINAL" / "Champions").is_dir()
    assert (game_dir / "Game" / "DATA" / "FINAL" / "Maps" / "Shipping").is_dir()
    assert (game_dir / "LeagueClient" / "Plugins" / "rcp-be-lol-game-data").is_dir()


def test_write_content_metadata_should_write_version(tmp_path: Path) -> None:
    """应写入可供下游读取的版本号字段。"""

    game_dir = build_simulated_dir(tmp_path / "sim_game")
    metadata_file = write_content_metadata(game_path=game_dir, version="16.4.7480682")

    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert payload["version"] == "16.4.7480682"


def test_stage_wad_file_should_copy_to_relative_path(tmp_path: Path) -> None:
    """按相对路径落地 WAD 文件应成功。"""

    game_dir = build_simulated_dir(tmp_path / "sim_game")
    source_wad = tmp_path / "source.wad"
    source_wad.write_bytes(b"wad-data")

    target_wad = stage_wad_file(
        game_path=game_dir,
        relative_wad_path="Game/DATA/FINAL/Champions/Ahri.zh_CN.wad.client",
        source_wad_file=source_wad,
        strategy="copy",
    )

    assert target_wad.read_bytes() == b"wad-data"
    assert (
        target_wad == game_dir / "Game" / "DATA" / "FINAL" / "Champions" / "Ahri.zh_CN.wad.client"
    )


def test_stage_wad_file_should_reject_escape_path(tmp_path: Path) -> None:
    """越界路径应被拒绝。"""

    source_wad = tmp_path / "source.wad"
    source_wad.write_bytes(b"wad")

    with pytest.raises(ValueError):
        stage_wad_file(
            game_path=tmp_path / "sim_game",
            relative_wad_path="../escape.wad",
            source_wad_file=source_wad,
            strategy="copy",
        )


def test_cleanup_updater_inputs_should_remove_lcu_wad_and_bin_input(tmp_path: Path) -> None:
    """应清理 LCU WAD 与 bin_input 目录。"""

    game_dir = build_simulated_dir(tmp_path / "sim_game")
    lcu_dir = game_dir / "LeagueClient" / "Plugins" / "rcp-be-lol-game-data"
    (lcu_dir / "default-assets.wad").write_bytes(b"lcu")
    (lcu_dir / "default-assets2.wad").write_bytes(b"lcu2")
    (lcu_dir / "keep.txt").write_text("keep", encoding="utf-8")

    version_dir = tmp_path / "output" / "manifest" / "16.4"
    (version_dir / "bin_input" / "data" / "maps" / "shipping").mkdir(parents=True, exist_ok=True)
    (version_dir / "bin_input" / "data" / "maps" / "shipping" / "map11.bin").write_bytes(b"bin")
    (version_dir / ".use_local_bin").touch()

    removed_lcu_wads, removed_bin_files = cleanup_updater_inputs(
        game_path=game_dir,
        version_dir=version_dir,
    )

    assert removed_lcu_wads == 2
    assert removed_bin_files == 1
    assert not (lcu_dir / "default-assets.wad").exists()
    assert not (lcu_dir / "default-assets2.wad").exists()
    assert (lcu_dir / "keep.txt").exists()
    assert not (version_dir / "bin_input").exists()
    assert not (version_dir / ".use_local_bin").exists()
