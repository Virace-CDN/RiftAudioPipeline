"""主流程辅助函数测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rift_audio_pipeline.config import PipelineConfig
import rift_audio_pipeline.pipeline as pipeline


def test_pack_unpacked_outputs_should_pack_existing_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应仅对存在的 champions/maps 目录执行打包。"""

    output_path = tmp_path / "output"
    champions_dir = output_path / "audios" / "16.4" / "champions"
    maps_dir = output_path / "audios" / "16.4" / "maps"
    champions_dir.mkdir(parents=True, exist_ok=True)
    maps_dir.mkdir(parents=True, exist_ok=True)

    calls: list[tuple[Path, Path, str | None, Path | None]] = []
    extra_files = (tmp_path / "extra" / "说明.txt",)
    extra_files[0].parent.mkdir(parents=True, exist_ok=True)
    extra_files[0].write_text("x", encoding="utf-8")
    champion_report_dir = output_path / "reports" / "16.4" / "champions"
    champion_report_dir.mkdir(parents=True, exist_ok=True)
    champion_report = champion_report_dir / "_1_metadata.yaml"
    champion_report.write_text("meta", encoding="utf-8")
    maps_report_dir = output_path / "reports" / "16.4" / "maps"
    maps_report_dir.mkdir(parents=True, exist_ok=True)

    def _fake_pack_all(
        audio_dir: Path,
        output_dir: Path,
        *,
        version: str | None = None,
        report_dir: Path | None = None,
        password: str | None = None,
        encrypt_filenames: bool = True,
        extra_files: tuple[Path, ...] = tuple(),
        compression_level: int = 0,
        seven_zip_executable: str | None = None,
    ) -> tuple[Path, ...]:
        del password, encrypt_filenames, compression_level, seven_zip_executable
        calls.append((audio_dir, output_dir, version, report_dir))
        assert tuple(extra_files) == extra_files_expected
        return (output_dir / f"{audio_dir.name}.7z",)

    extra_files_expected = extra_files
    monkeypatch.setattr(pipeline, "pack_all", _fake_pack_all)
    monkeypatch.setattr(pipeline, "_resolve_pack_extra_files", lambda config: extra_files_expected)

    config = PipelineConfig(
        output_path=output_path,
        enable_pack=True,
        pack_password="secret",
        pack_encrypt_filenames=True,
    )
    archives = pipeline._pack_unpacked_outputs(config=config, game_version="16.4")

    assert calls == [
        (
            champions_dir,
            output_path / "packages" / "16.4" / "champions",
            "16.4",
            champion_report_dir,
        ),
        (
            maps_dir,
            output_path / "packages" / "16.4" / "maps",
            "16.4",
            maps_report_dir,
        ),
    ]
    assert archives == (
        output_path / "packages" / "16.4" / "champions" / "champions.7z",
        output_path / "packages" / "16.4" / "maps" / "maps.7z",
    )


def test_pack_unpacked_outputs_should_return_empty_when_version_dir_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """缺失版本音频目录时应直接返回空集合。"""

    monkeypatch.setattr(
        pipeline,
        "pack_all",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应触发打包")),
    )

    config = PipelineConfig(
        output_path=tmp_path / "output",
        enable_pack=True,
    )
    archives = pipeline._pack_unpacked_outputs(config=config, game_version="16.4")
    assert archives == tuple()


def test_resolve_pack_extra_files_should_use_config_dir_first(tmp_path: Path) -> None:
    """显式配置目录时应优先使用该目录。"""

    configured_dir = tmp_path / "extras"
    configured_dir.mkdir(parents=True, exist_ok=True)
    first = configured_dir / "食用说明.txt"
    second = configured_dir / "license.txt"
    first.write_text("readme", encoding="utf-8")
    second.write_text("license", encoding="utf-8")

    config = PipelineConfig(
        output_path=tmp_path / "output",
        pack_extra_dir=configured_dir,
    )
    resolved = pipeline._resolve_pack_extra_files(config=config)
    assert resolved == (first.resolve(), second.resolve())


def test_resolve_pack_extra_files_should_return_empty_when_missing(tmp_path: Path) -> None:
    """未找到附加文件目录时应返回空集合。"""

    config = PipelineConfig(
        output_path=tmp_path / "output",
        pack_extra_dir=tmp_path / "missing",
    )
    resolved = pipeline._resolve_pack_extra_files(config=config)
    assert resolved == tuple()


def test_resolve_pack_extra_files_should_use_bundled_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """未显式配置时应读取项目内置 extra 目录。"""

    bundled_dir = tmp_path / "bundled"
    bundled_dir.mkdir(parents=True, exist_ok=True)
    first = bundled_dir / "食用说明.txt"
    second = bundled_dir / "license.txt"
    first.write_text("readme", encoding="utf-8")
    second.write_text("license", encoding="utf-8")

    monkeypatch.setattr(pipeline, "DEFAULT_BUNDLED_PACK_EXTRA_DIR", bundled_dir)
    config = PipelineConfig(output_path=tmp_path / "output")
    resolved = pipeline._resolve_pack_extra_files(config=config)
    assert resolved == (first.resolve(), second.resolve())


def test_upload_archives_and_manifest_should_upload_archives_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应上传所有压缩包并同步上传清单。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            return {"path": remote_path, "errno": 0}

        def close(self) -> None:
            return None

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
    package_root.mkdir(parents=True, exist_ok=True)
    first_archive = package_root / "Annie.7z"
    second_archive = package_root / "Zac.7z"
    first_archive.write_bytes(b"a")
    second_archive.write_bytes(b"b")

    config = PipelineConfig(
        output_path=output_path,
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
        enable_upload=True,
    )
    manifest_file = pipeline._upload_archives_and_manifest(
        config=config,
        game_version="16.4",
        archives=(first_archive, second_archive),
    )

    assert manifest_file == package_root / "upload_manifest.json"
    assert manifest_file.exists()
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert payload["archive_count"] == 2
    assert [entry["local_path"] for entry in payload["entries"]] == [
        str(first_archive),
        str(second_archive),
    ]
    assert fake_client.upload_calls == [
        (first_archive, "package_16.4_Annie.7z"),
        (second_archive, "package_16.4_Zac.7z"),
        (manifest_file, "upload_manifest_16.4.json"),
    ]


def test_upload_archives_and_manifest_should_raise_when_credentials_missing(
    tmp_path: Path,
) -> None:
    """缺少凭据时应拒绝上传。"""

    output_path = tmp_path / "output"
    archive = output_path / "packages" / "16.4" / "Annie.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"a")

    config = PipelineConfig(
        output_path=output_path,
        enable_upload=True,
    )
    with pytest.raises(ValueError, match="缺少百度凭据"):
        pipeline._upload_archives_and_manifest(
            config=config,
            game_version="16.4",
            archives=(archive,),
        )


def test_cleanup_simulated_runtime_files_should_remove_wads_and_downloads(
    tmp_path: Path,
) -> None:
    """应清理模拟目录中的 WAD 与下载缓存文件。"""

    runtime_game_path = tmp_path / "mini_game"
    champion_wad = runtime_game_path / "Game" / "DATA" / "FINAL" / "Champions" / "Annie.wad.client"
    map_wad = (
        runtime_game_path
        / "Game"
        / "DATA"
        / "FINAL"
        / "Maps"
        / "Shipping"
        / "Map11"
        / "Map11.wad.client"
    )
    other_file = runtime_game_path / "Game" / "DATA" / "FINAL" / "Champions" / "keep.txt"
    champion_wad.parent.mkdir(parents=True, exist_ok=True)
    map_wad.parent.mkdir(parents=True, exist_ok=True)
    champion_wad.write_bytes(b"1")
    map_wad.write_bytes(b"2")
    other_file.write_text("x", encoding="utf-8")

    runtime_download_dir = tmp_path / "downloads" / "16.4" / "zh_CN"
    (runtime_download_dir / "game").mkdir(parents=True, exist_ok=True)
    (runtime_download_dir / "lcu").mkdir(parents=True, exist_ok=True)
    (runtime_download_dir / "game" / "a.bin").write_bytes(b"a")
    (runtime_download_dir / "lcu" / "b.bin").write_bytes(b"b")

    removed_wads, removed_downloads = pipeline._cleanup_simulated_runtime_files(
        runtime_game_path=runtime_game_path,
        runtime_download_dir=runtime_download_dir,
    )

    assert removed_wads == 2
    assert removed_downloads == 2
    assert not champion_wad.exists()
    assert not map_wad.exists()
    assert other_file.exists()
    assert not runtime_download_dir.exists()
