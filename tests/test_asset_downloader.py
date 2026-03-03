"""下载组件测试。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

import rift_audio_pipeline.asset_downloader as downloader


@dataclass(frozen=True, slots=True)
class _FakeFile:
    """模拟 manifest 文件对象。"""

    name: str
    flags: tuple[str, ...] | None = None


class _FakeManifest:
    """模拟 PatcherManifest。"""

    PRESET_FILES: tuple[_FakeFile, ...] = (
        _FakeFile("content-metadata.json"),
        _FakeFile("Plugins/rcp-be-lol-game-data/default-assets2.wad"),
        _FakeFile("DATA/FINAL/Champions/Annie.wad.client"),
    )

    def __init__(self, file: str, path: str) -> None:
        self.file = file
        self.path = Path(path)
        self.files: dict[str, _FakeFile] = {
            f"fake-{index}": item for index, item in enumerate(self.PRESET_FILES)
        }

    def filter_files(self, pattern: str) -> list[_FakeFile]:
        import re

        regex = re.compile(pattern)
        return [item for item in self.PRESET_FILES if regex.search(item.name)]

    async def download_files_concurrently(
        self,
        files: list[_FakeFile],
        concurrency_limit: int,
        raise_on_error: bool,
    ) -> tuple[bool, ...]:
        assert concurrency_limit >= 1
        assert raise_on_error is False
        for file_obj in files:
            local = self.path / file_obj.name
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text(f"downloaded:{file_obj.name}", encoding="utf-8")
        return tuple(True for _ in files)


def test_to_game_manifest_path_should_strip_game_prefix() -> None:
    """运行时 GAME 路径应可映射到 manifest 路径。"""

    assert (
        downloader._to_game_manifest_path("Game/DATA/FINAL/Champions/Annie.wad.client")
        == "DATA/FINAL/Champions/Annie.wad.client"
    )
    assert (
        downloader._to_game_manifest_path("DATA/FINAL/Champions/Annie.wad.client")
        == "DATA/FINAL/Champions/Annie.wad.client"
    )


def test_to_game_manifest_path_should_raise_on_invalid_path() -> None:
    """非 GAME 路径应拒绝映射。"""

    with pytest.raises(ValueError):
        downloader._to_game_manifest_path("LeagueClient/Plugins/xxx.wad")


def test_to_runtime_relative_path_should_map_core_paths() -> None:
    """manifest 路径应映射到运行时目录。"""

    assert (
        downloader._to_runtime_relative_path("content-metadata.json")
        == "Game/content-metadata.json"
    )
    assert (
        downloader._to_runtime_relative_path("DATA/FINAL/Champions/Annie.wad.client")
        == "Game/DATA/FINAL/Champions/Annie.wad.client"
    )
    assert (
        downloader._to_runtime_relative_path("Plugins/rcp-be-lol-game-data/default-assets.wad")
        == "LeagueClient/Plugins/rcp-be-lol-game-data/default-assets.wad"
    )


def test_download_manifest_exact_paths_should_download_expected_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """精确路径下载应写入目标文件。"""

    monkeypatch.setattr(downloader, "PatcherManifest", _FakeManifest)

    files = downloader.download_manifest_exact_paths(
        manifest_url="https://example.test/game.manifest",
        download_dir=tmp_path / "downloads",
        exact_paths=("content-metadata.json",),
    )
    assert len(files) == 1
    assert files[0].exists()
    assert files[0].read_text(encoding="utf-8") == "downloaded:content-metadata.json"


def test_download_manifest_exact_paths_should_raise_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """指定路径不在清单中时应抛错。"""

    monkeypatch.setattr(downloader, "PatcherManifest", _FakeManifest)

    with pytest.raises(FileNotFoundError):
        downloader.download_manifest_exact_paths(
            manifest_url="https://example.test/game.manifest",
            download_dir=tmp_path / "downloads",
            exact_paths=("DATA/FINAL/Champions/Missing.wad.client",),
        )
