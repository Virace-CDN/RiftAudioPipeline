"""主流程辅助函数测试。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rift_audio_pipeline.config import PipelineConfig
import rift_audio_pipeline.pipeline as pipeline


def _build_diff_update_decision(
    update_paths: tuple[str, ...],
    champion_aliases: tuple[str, ...] = tuple(),
    map_ids: tuple[str, ...] = tuple(),
) -> SimpleNamespace:
    """构造 diff 场景下的更新判定对象。"""

    return SimpleNamespace(
        should_update=True,
        reason="region_manifest_changed",
        latest_versions=SimpleNamespace(
            game_version="16.4.7480682",
            game_manifest_url="https://example.test/game-new.manifest",
            lcu_version="16.4",
            lcu_manifest_url="https://example.test/lcu-new.manifest",
        ),
        previous_state=SimpleNamespace(
            game_manifest_url="https://example.test/game-old.manifest",
        ),
        changed_entities=SimpleNamespace(
            champion_aliases=champion_aliases,
            map_ids=map_ids,
        ),
        wad_changes=SimpleNamespace(
            added_paths=update_paths,
            changed_paths=tuple(),
            removed_paths=tuple(),
            update_paths=update_paths,
        ),
    )


def test_run_pipeline_should_skip_secondary_filter_when_update_wad_count_reaches_threshold(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """清单层 WAD 更新数达到阈值时应跳过 WADExtractor 二次筛选。"""

    update_paths = tuple(
        f"DATA/FINAL/Champions/Hero{index}.zh_CN.wad.client" for index in range(101)
    )
    decision = _build_diff_update_decision(
        update_paths=update_paths,
        champion_aliases=tuple(f"Hero{index}" for index in range(101)),
    )

    monkeypatch.setattr(pipeline, "ensure_official_sdk_path", lambda: tmp_path / "sdk")
    monkeypatch.setattr(pipeline, "evaluate_update_need", lambda **_: decision)
    monkeypatch.setattr(
        pipeline,
        "filter_wad_changes_by_bin_voice_paths",
        lambda **_: (_ for _ in ()).throw(AssertionError("阈值分支不应触发二次筛选")),
    )

    config = PipelineConfig(
        output_path=tmp_path / "output",
        dry_run=True,
        diff_bin_filter_threshold=100,
    )
    assert pipeline.run_pipeline(config=config) == 0


def test_run_pipeline_should_pass_unit_workers_to_secondary_filter_when_not_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """未触发阈值降级时，应按配置并发数执行二次筛选。"""

    update_paths = (
        "DATA/FINAL/Champions/Annie.zh_CN.wad.client",
        "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",
    )
    decision = _build_diff_update_decision(
        update_paths=update_paths,
        champion_aliases=("Annie",),
        map_ids=("11",),
    )
    captured_call_kwargs: dict[str, object] = {}

    def _fake_filter_wad_changes_by_bin_voice_paths(**kwargs: object) -> SimpleNamespace:
        captured_call_kwargs.update(kwargs)
        return SimpleNamespace(
            unpack_paths=(update_paths[0],),
            skipped_paths=(update_paths[1],),
            decisions=(
                SimpleNamespace(
                    should_unpack=True,
                    matched_bin_paths=("data/characters/annie/skins/skin0.bin",),
                ),
            ),
        )

    monkeypatch.setattr(pipeline, "ensure_official_sdk_path", lambda: tmp_path / "sdk")
    monkeypatch.setattr(pipeline, "evaluate_update_need", lambda **_: decision)
    monkeypatch.setattr(
        pipeline,
        "filter_wad_changes_by_bin_voice_paths",
        _fake_filter_wad_changes_by_bin_voice_paths,
    )
    monkeypatch.setattr(pipeline, "create_local_bin_flag", lambda version_dir: version_dir)

    config = PipelineConfig(
        output_path=tmp_path / "output",
        dry_run=True,
        diff_bin_filter_threshold=100,
        diff_bin_filter_workers=3,
        diff_bin_extract_concurrency=5,
    )
    assert pipeline.run_pipeline(config=config) == 0
    assert captured_call_kwargs["unit_max_workers"] == 3
    assert captured_call_kwargs["extractor_prefetch_chunk_concurrency"] == 5
    assert captured_call_kwargs["update_paths"] == update_paths


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

    calls: list[tuple[Path, Path, str | None, str | None, Path | None]] = []
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
        audio_type: str | None = None,
        report_dir: Path | None = None,
        password: str | None = None,
        encrypt_filenames: bool = True,
        extra_files: tuple[Path, ...] = tuple(),
        compression_level: int = 0,
        seven_zip_executable: str | None = None,
    ) -> tuple[Path, ...]:
        del password, encrypt_filenames, compression_level, seven_zip_executable
        calls.append((audio_dir, output_dir, version, audio_type, report_dir))
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
            "VO",
            champion_report_dir,
        ),
        (
            maps_dir,
            output_path / "packages" / "16.4" / "maps",
            "16.4",
            "VO",
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


def test_resolve_pack_archive_type_should_return_single_type(tmp_path: Path) -> None:
    """仅配置单一音频类型时应返回类型后缀。"""

    config = PipelineConfig(
        output_path=tmp_path / "output",
        audio_types=("vo",),
    )
    assert pipeline._resolve_pack_archive_type(config=config) == "VO"


def test_resolve_pack_archive_type_should_return_none_when_multiple(tmp_path: Path) -> None:
    """配置多类型时应返回 None（混合模式）。"""

    config = PipelineConfig(
        output_path=tmp_path / "output",
        audio_types=("VO", "SFX"),
    )
    assert pipeline._resolve_pack_archive_type(config=config) is None


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
            self.download_calls: list[tuple[str, Path]] = []
            self.get_path_calls: list[str] = []
            self.create_dir_calls: list[str] = []
            self.move_calls: list[tuple[str, str, str | None, str]] = []
            self.remote_dirs: set[str] = {self.remote_dir}
            self.remote_files: set[str] = set()

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            self.remote_files.add(self._normalize_remote_path(remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            self.download_calls.append((remote_path, local_path))
            raise FileNotFoundError(remote_path)

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            self.get_path_calls.append(remote_path)
            normalized = self._normalize_remote_path(remote_path)
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            if normalized in self.remote_files:
                return {"path": normalized, "isdir": 0}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(dir_path)
            self.create_dir_calls.append(dir_path)
            self.remote_dirs.add(normalized)
            return {"path": normalized, "isdir": 1, "errno": 0}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            self.move_calls.append((source_path, destination_dir, new_name, ondup))
            return {"errno": 0}

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
    first_archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    second_archive = package_root / "champions" / "154·zac·生化魔人·扎克-16.4-VO.7z"
    first_archive.parent.mkdir(parents=True, exist_ok=True)
    second_archive.parent.mkdir(parents=True, exist_ok=True)
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
    readable_manifest_file = package_root / "upload_manifest_readable.txt"
    assert readable_manifest_file.exists()
    readable_content = readable_manifest_file.read_text(encoding="utf-8")
    assert "## 在线资源" in readable_content
    assert "## OLD 归档资源" in readable_content
    assert "VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z" in readable_content
    assert payload["entry_count"] == 2
    assert payload["database_schema_version"] == 1
    assert payload["database_entry_count"] == 2
    database_values = list(payload["database"].values())
    assert any(
        item.get("entity_key") == "1·annie·黑暗之女·安妮"
        and item.get("latest_game_version") == "16.4"
        for item in database_values
    )
    assert payload["last_run"]["archive_count"] == 2
    assert payload["last_run"]["uploaded_count"] == 2
    assert payload["last_run"]["skipped_count"] == 0
    assert {entry["remote_name"] for entry in payload["entries"]} == {
        "1·annie·黑暗之女·安妮-16.4-VO.7z",
        "154·zac·生化魔人·扎克-16.4-VO.7z",
    }
    assert fake_client.upload_calls == [
        (first_archive, "VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z"),
        (second_archive, "VO/champions/154·zac·生化魔人·扎克-16.4-VO.7z"),
        (manifest_file, "upload_manifest.json"),
        (package_root / "upload_manifest_readable.txt", "upload_manifest_readable.txt"),
    ]
    assert fake_client.move_calls == []


def test_upload_archives_and_manifest_should_skip_when_remote_index_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """远端索引命中同文件时应跳过上传。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []
            self.download_calls: list[tuple[str, Path]] = []
            self.remote_dirs: set[str] = {self.remote_dir}

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            self.download_calls.append((remote_path, local_path))
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(json.dumps(remote_manifest_payload), encoding="utf-8")
            return {"path": remote_path}

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(remote_path)
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            self.remote_dirs.add(self._normalize_remote_path(dir_path))
            return {"path": dir_path, "isdir": 1}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            raise AssertionError(
                f"同版本命中跳过上传时不应触发 move：{source_path} -> {destination_dir}/{new_name}"
            )

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
    package_root.mkdir(parents=True, exist_ok=True)
    archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"annie-audio")
    remote_manifest_payload = {
        "schema_version": 2,
        "entries": [
            {
                "remote_path": "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z",
                "remote_name": "1·annie·黑暗之女·安妮-16.4-VO.7z",
                "game_version": "16.4",
                "target_group": "champions",
                "resource_type": "VO",
                "entity_key": "1·annie·黑暗之女·安妮",
                "uploaded_at": "2026-03-04T00:00:00Z",
            }
        ],
    }

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

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
        archives=(archive,),
    )

    assert manifest_file == package_root / "upload_manifest.json"
    assert fake_client.download_calls == [
        ("upload_manifest.json", package_root / ".remote_upload_manifest.json")
    ]
    assert fake_client.upload_calls == []
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert payload["entry_count"] == 1
    assert payload["last_run"]["uploaded_count"] == 0
    assert payload["last_run"]["skipped_count"] == 1


def test_upload_archives_and_manifest_should_reuse_preloaded_remote_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """传入预加载索引时，不应重复下载远端 upload_manifest。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []
            self.remote_dirs: set[str] = {self.remote_dir}

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            del local_path
            raise AssertionError(f"复用预加载索引后不应下载远端索引：{remote_path}")

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(remote_path)
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            self.remote_dirs.add(self._normalize_remote_path(dir_path))
            return {"path": dir_path, "isdir": 1}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            raise AssertionError(
                f"同版本命中跳过上传时不应触发 move：{source_path} -> {destination_dir}/{new_name}/{ondup}"
            )

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
    package_root.mkdir(parents=True, exist_ok=True)
    archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"annie-audio")
    preloaded_remote_index = {
        "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z".casefold(): {
            "remote_path": "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z",
            "remote_name": "1·annie·黑暗之女·安妮-16.4-VO.7z",
            "game_version": "16.4",
            "target_group": "champions",
            "resource_type": "VO",
            "entity_key": "1·annie·黑暗之女·安妮",
            "uploaded_at": "2026-03-04T00:00:00Z",
        }
    }

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

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
        archives=(archive,),
        preloaded_remote_index=preloaded_remote_index,
    )

    assert manifest_file == package_root / "upload_manifest.json"
    assert fake_client.upload_calls == []
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert payload["entry_count"] == 1
    assert payload["last_run"]["uploaded_count"] == 0
    assert payload["last_run"]["skipped_count"] == 1


def test_upload_archives_and_manifest_should_archive_old_version_before_upload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """同实体存在旧版本时，应先移动到 OLD 目录再上传新版本。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []
            self.download_calls: list[tuple[str, Path]] = []
            self.move_calls: list[tuple[str, str, str | None, str]] = []
            self.create_dir_calls: list[str] = []
            self.remote_dirs: set[str] = {self.remote_dir}
            self.remote_files: set[str] = {
                f"{self.remote_dir.rstrip('/')}/VO/champions/1·annie·黑暗之女·安妮-16.1-VO.7z"
            }

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            if remote_path != "upload_manifest.json":
                self.remote_files.add(self._normalize_remote_path(remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            self.download_calls.append((remote_path, local_path))
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(json.dumps(remote_manifest_payload), encoding="utf-8")
            return {"path": remote_path}

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(remote_path)
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            if normalized in self.remote_files:
                return {"path": normalized, "isdir": 0}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(dir_path)
            self.create_dir_calls.append(dir_path)
            self.remote_dirs.add(normalized)
            return {"path": normalized, "isdir": 1}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            self.move_calls.append((source_path, destination_dir, new_name, ondup))
            source_full = self._normalize_remote_path(source_path)
            destination_full = self._normalize_remote_path(
                f"{destination_dir.strip().rstrip('/')}/{new_name}"
            )
            self.remote_files.discard(source_full)
            self.remote_files.add(destination_full)
            return {"errno": 0}

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
    package_root.mkdir(parents=True, exist_ok=True)
    archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"new-version")
    remote_manifest_payload = {
        "schema_version": 2,
        "entries": [
            {
                "remote_path": "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.1-VO.7z",
                "remote_name": "1·annie·黑暗之女·安妮-16.1-VO.7z",
                "game_version": "16.1",
                "target_group": "champions",
                "resource_type": "VO",
                "entity_key": "1·annie·黑暗之女·安妮",
            }
        ],
    }

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

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
        archives=(archive,),
    )

    assert manifest_file == package_root / "upload_manifest.json"
    assert fake_client.move_calls == [
        (
            "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.1-VO.7z",
            "OLD/champions",
            "1·annie·黑暗之女·安妮-16.1-VO.7z",
            "newcopy",
        )
    ]
    assert fake_client.upload_calls == [
        (archive, "VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z"),
        (manifest_file, "upload_manifest.json"),
        (package_root / "upload_manifest_readable.txt", "upload_manifest_readable.txt"),
    ]
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    index_by_name = {entry["remote_name"]: entry for entry in payload["entries"]}
    assert (
        index_by_name["1·annie·黑暗之女·安妮-16.1-VO.7z"]["remote_path"]
        == "/apps/test/OLD/champions/1·annie·黑暗之女·安妮-16.1-VO.7z"
    )
    assert (
        index_by_name["1·annie·黑暗之女·安妮-16.4-VO.7z"]["remote_path"]
        == "/apps/test/VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z"
    )
    assert payload["last_run"]["uploaded_count"] == 1
    database_values = list(payload["database"].values())
    assert any(
        item.get("entity_key") == "1·annie·黑暗之女·安妮"
        and item.get("latest_game_version") == "16.4"
        and len(item.get("versions", [])) >= 2
        for item in database_values
    )


def test_upload_archives_and_manifest_should_enqueue_pending_sync_when_manifest_upload_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """索引回传失败时应写入待重试队列且不阻断上传主流程。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []
            self.remote_dirs: set[str] = {self.remote_dir}
            self.remote_files: set[str] = set()

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            if remote_path in {"upload_manifest.json", "upload_manifest_readable.txt"}:
                raise RuntimeError(f"模拟索引回传失败：{remote_path}")
            self.remote_files.add(self._normalize_remote_path(remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            del local_path
            raise FileNotFoundError(remote_path)

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(remote_path)
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            if normalized in self.remote_files:
                return {"path": normalized, "isdir": 0}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            self.remote_dirs.add(self._normalize_remote_path(dir_path))
            return {"path": dir_path, "isdir": 1}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            raise AssertionError(
                f"新增上传场景不应触发 move：{source_path} -> {destination_dir}/{new_name}/{ondup}"
            )

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
    queue_file = output_path / "state" / "pending_manifest_sync_queue.json"
    package_root.mkdir(parents=True, exist_ok=True)
    archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"a")

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

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
        archives=(archive,),
        pending_manifest_sync_queue_file=queue_file,
    )

    assert manifest_file == package_root / "upload_manifest.json"
    assert manifest_file.exists()
    assert queue_file.exists()
    queue_payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert isinstance(queue_payload, list)
    assert len(queue_payload) == 1
    queue_entry = queue_payload[0]
    assert queue_entry["remote_dir"] == "/apps/test"
    assert Path(queue_entry["manifest_file"]) == manifest_file.resolve()
    assert Path(queue_entry["readable_manifest_file"]) == (
        package_root / "upload_manifest_readable.txt"
    ).resolve()


def test_upload_archives_and_manifest_should_fail_when_remote_file_exists_without_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """远端存在同名文件但索引缺失时应终止上传。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []
            self.remote_dirs: set[str] = {self.remote_dir}
            self.existing_file = (
                f"{self.remote_dir.rstrip('/')}/VO/champions/1·annie·黑暗之女·安妮-16.4-VO.7z"
            )

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            del local_path
            raise FileNotFoundError(remote_path)

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(remote_path)
            if normalized == self.existing_file:
                return {"path": normalized, "isdir": 0}
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            self.remote_dirs.add(self._normalize_remote_path(dir_path))
            return {"path": dir_path, "isdir": 1}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            raise AssertionError(
                f"索引缺失冲突路径不应触发 move：{source_path} -> {destination_dir}/{new_name}"
            )

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
    package_root.mkdir(parents=True, exist_ok=True)
    archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"a")

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

    config = PipelineConfig(
        output_path=output_path,
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
        enable_upload=True,
    )
    with pytest.raises(RuntimeError, match="索引缺失"):
        pipeline._upload_archives_and_manifest(
            config=config,
            game_version="16.4",
            archives=(archive,),
        )
    assert fake_client.upload_calls == []


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


def test_upload_archives_and_manifest_should_fail_when_index_missing_in_diff_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """差异更新场景缺少远端索引时应终止上传。"""

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.remote_dirs: set[str] = {self.remote_dir}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            del local_path
            raise FileNotFoundError(remote_path)

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = remote_path if remote_path.startswith("/") else f"{self.remote_dir}/{remote_path}"
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            normalized = dir_path if dir_path.startswith("/") else f"{self.remote_dir}/{dir_path}"
            self.remote_dirs.add(normalized)
            return {"path": normalized, "isdir": 1}

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    archive = output_path / "packages" / "16.4" / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"a")

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

    config = PipelineConfig(
        output_path=output_path,
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
        enable_upload=True,
    )
    with pytest.raises(RuntimeError, match="远端缺少上传索引"):
        pipeline._upload_archives_and_manifest(
            config=config,
            game_version="16.4",
            archives=(archive,),
            allow_missing_remote_index=False,
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


def test_build_update_log_payload_should_include_diff_details() -> None:
    """更新日志负载应包含版本区间、WAD 明细与上传结果统计。"""

    decision = SimpleNamespace(
        reason="region_manifest_changed",
        previous_state=SimpleNamespace(game_version="16.3"),
        wad_changes=SimpleNamespace(
            added_paths=("DATA/FINAL/Champions/Annie.zh_CN.wad.client",),
            changed_paths=("DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",),
            removed_paths=tuple(),
            update_paths=(
                "DATA/FINAL/Champions/Annie.zh_CN.wad.client",
                "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",
            ),
        ),
    )
    target_entities = SimpleNamespace(champion_aliases=("annie",), map_ids=("11",))
    targets = SimpleNamespace(champion_ids=(1,), map_ids=(11,))
    upload_run_records = [
        {"status": "uploaded", "remote_name": "1·annie-16.4-VO.7z", "reason": "uploaded"},
        {
            "status": "skipped",
            "remote_name": "11·map11-16.4-VO.7z",
            "reason": "remote_index_hit_same_version",
        },
        {
            "status": "archived_old",
            "remote_name": "1·annie-16.3-VO.7z",
            "reason": "previous_version_archived_to_old_bucket",
        },
    ]

    payload = pipeline._build_update_log_payload(
        decision=decision,
        game_version="16.4",
        executed_at="2026-03-04T00:00:00Z",
        target_entities=target_entities,
        targets=targets,
        secondary_filter_result=None,
        upload_run_records=upload_run_records,
    )
    assert payload["from_game_version"] == "16.3"
    assert payload["to_game_version"] == "16.4"
    assert payload["wad_changes"]["changed_paths"] == [
        "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client"
    ]
    assert payload["upload_summary"]["uploaded_count"] == 1
    assert payload["upload_summary"]["skipped_count"] == 1
    assert payload["upload_summary"]["archived_count"] == 1

    readable = pipeline._build_update_log_text(payload=payload)
    assert "版本区间: 16.3 -> 16.4" in readable
    assert "## WAD 变更" in readable
    assert "## 上传结果" in readable


def test_run_streaming_unpack_pack_upload_should_upload_and_cleanup_per_entity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """流式模式应按实体单包上传，并及时清理 WAD/音频/压缩包。"""

    output_path = tmp_path / "output"
    runtime_game_path = tmp_path / "mini_game"
    champion_wad = runtime_game_path / "DATA" / "FINAL" / "Champions" / "Annie.wad.client"
    map_wad = (
        runtime_game_path / "DATA" / "FINAL" / "Maps" / "Shipping" / "Map11" / "Map11.wad.client"
    )
    champion_wad.parent.mkdir(parents=True, exist_ok=True)
    map_wad.parent.mkdir(parents=True, exist_ok=True)
    champion_wad.write_bytes(b"champion-wad")
    map_wad.write_bytes(b"map-wad")

    unpack_calls: list[tuple[tuple[int, ...], tuple[int, ...], int]] = []
    pack_calls: list[tuple[Path, Path, str, Path | None]] = []
    upload_run_records: list[dict[str, object]] = []

    def _fake_resolve_runtime_wad_paths(
        data_file_base: Path,
        region: str,
        champion_ids: tuple[int, ...],
        map_ids: tuple[int, ...],
        include_root_wad: bool = True,
    ) -> tuple[str, ...]:
        del data_file_base, region, include_root_wad
        if champion_ids:
            return ("Game/DATA/FINAL/Champions/Annie.wad.client",)
        if map_ids:
            return ("Game/DATA/FINAL/Maps/Shipping/Map11/Map11.wad.client",)
        return tuple()

    def _fake_run_unpack(
        champion_ids: tuple[int, ...],
        map_ids: tuple[int, ...],
        max_workers: int,
    ) -> None:
        unpack_calls.append((champion_ids, map_ids, max_workers))
        if champion_ids:
            entity_id = champion_ids[0]
            target = "champions"
            entity_name = f"{entity_id}·Annie"
        else:
            entity_id = map_ids[0]
            target = "maps"
            entity_name = f"{entity_id}·Map11"
        audio_dir = output_path / "audios" / "16.4" / target / entity_name
        audio_dir.mkdir(parents=True, exist_ok=True)
        (audio_dir / "voice.wav").write_bytes(b"wav")
        report_dir = output_path / "reports" / "16.4" / target
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / f"_{entity_id}_metadata.yaml").write_text("meta", encoding="utf-8")

    def _fake_pack_champion(
        champion_dir: Path,
        output_path: Path,
        *,
        archive_name: str | None = None,
        report_file: Path | None = None,
        password: str | None = None,
        encrypt_filenames: bool = True,
        extra_files: tuple[Path, ...] = tuple(),
        compression_level: int = 0,
        seven_zip_executable: str | None = None,
    ) -> Path:
        del password, encrypt_filenames, extra_files, compression_level, seven_zip_executable
        assert champion_dir.is_dir()
        output_path.mkdir(parents=True, exist_ok=True)
        archive_path = output_path / str(archive_name)
        archive_path.write_bytes(b"7z")
        pack_calls.append((champion_dir, output_path, str(archive_name), report_file))
        return archive_path

    class _FakeClient:
        def __init__(self, credentials, remote_dir, token_store) -> None:
            del credentials, token_store
            self.remote_dir = remote_dir
            self.upload_calls: list[tuple[Path, str]] = []
            self.download_calls: list[tuple[str, Path]] = []
            self.create_dir_calls: list[str] = []
            self.remote_dirs: set[str] = {self.remote_dir}
            self.remote_files: set[str] = set()

        def _normalize_remote_path(self, remote_path: str) -> str:
            if remote_path.startswith("/"):
                return remote_path
            return f"{self.remote_dir.rstrip('/')}/{remote_path.lstrip('/')}"

        def upload_file(
            self, local_path: Path, remote_path: str, rtype: int = 3
        ) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            self.remote_files.add(self._normalize_remote_path(remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            self.download_calls.append((remote_path, local_path))
            raise FileNotFoundError(remote_path)

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(remote_path)
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            if normalized in self.remote_files:
                return {"path": normalized, "isdir": 0}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            normalized = self._normalize_remote_path(dir_path)
            self.create_dir_calls.append(dir_path)
            self.remote_dirs.add(normalized)
            return {"path": normalized, "isdir": 1}

        def move_path(
            self,
            source_path: str,
            destination_dir: str,
            new_name: str | None = None,
            ondup: str = "newcopy",
        ) -> dict[str, object]:
            raise AssertionError(
                f"流式新增上传场景不应触发 move：{source_path} -> {destination_dir}/{new_name}/{ondup}"
            )

        def close(self) -> None:
            return None

    monkeypatch.setattr(pipeline, "resolve_runtime_wad_paths", _fake_resolve_runtime_wad_paths)
    monkeypatch.setattr(pipeline, "run_unpack", _fake_run_unpack)
    monkeypatch.setattr(pipeline, "pack_champion", _fake_pack_champion)
    monkeypatch.setattr(pipeline, "_resolve_pack_extra_files", lambda config: tuple())
    monkeypatch.setattr(pipeline, "_resolve_pack_archive_type", lambda config: "VO")
    monkeypatch.setattr(pipeline, "check_disk_space", lambda path, required_bytes: True)
    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(pipeline, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        pipeline,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

    config = PipelineConfig(
        output_path=output_path,
        game_region="zh_CN",
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
        pack_password=None,
        pack_encrypt_filenames=True,
    )
    manifest_file = pipeline._run_streaming_unpack_pack_upload(
        config=config,
        game_version="16.4",
        data_file_base=output_path / "manifest" / "16.4" / "data",
        targets=SimpleNamespace(champion_ids=(1,), map_ids=(11,)),
        runtime_game_path=runtime_game_path,
        runtime_wad_paths=(
            "Game/DATA/FINAL/Champions/Annie.wad.client",
            "Game/DATA/FINAL/Maps/Shipping/Map11/Map11.wad.client",
        ),
        include_root_wad=True,
        unpack_workers=2,
        allow_missing_remote_index=True,
        run_record_collector=upload_run_records,
    )

    assert manifest_file == output_path / "packages" / "16.4" / "upload_manifest.json"
    assert unpack_calls == [
        ((1,), tuple(), 2),
        (tuple(), (11,), 2),
    ]
    assert [item[2] for item in pack_calls] == ["1·Annie-16.4-VO.7z", "11·Map11-16.4-VO.7z"]
    assert fake_client.download_calls == [
        ("upload_manifest.json", output_path / "packages" / "16.4" / ".remote_upload_manifest.json")
    ]
    assert [item[1] for item in fake_client.upload_calls] == [
        "VO/champions/1·Annie-16.4-VO.7z",
        "VO/maps/11·Map11-16.4-VO.7z",
        "upload_manifest.json",
        "upload_manifest_readable.txt",
    ]
    assert [item.get("status") for item in upload_run_records] == ["uploaded", "uploaded"]
    assert not champion_wad.exists()
    assert not map_wad.exists()
    assert not (output_path / "audios" / "16.4" / "champions" / "1·Annie").exists()
    assert not (output_path / "audios" / "16.4" / "maps" / "11·Map11").exists()
    assert not (output_path / "packages" / "16.4" / "champions" / "1·Annie-16.4-VO.7z").exists()
    assert not (output_path / "packages" / "16.4" / "maps" / "11·Map11-16.4-VO.7z").exists()


def test_should_enable_streaming_mode_should_disable_for_real_game_path(tmp_path: Path) -> None:
    """真实游戏目录场景应关闭流式模式。"""

    config = PipelineConfig(output_path=tmp_path / "output", low_disk_mode=True)
    targets = SimpleNamespace(champion_ids=(1,), map_ids=tuple())
    assert (
        pipeline._should_enable_streaming_mode(
            config=config,
            runtime_is_simulated=False,
            targets=targets,
        )
        is False
    )


def test_resolve_effective_unpack_workers_should_expand_for_real_game_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实目录场景应提升解包并发到 CPU 核心数。"""

    monkeypatch.setattr(pipeline.os, "cpu_count", lambda: 8)
    effective = pipeline._resolve_effective_unpack_workers(
        configured_workers=2,
        runtime_is_simulated=False,
    )
    assert effective == 8


def test_run_pipeline_should_continue_when_update_log_stage_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """更新日志阶段失败时不应阻断主流程状态提交。"""

    latest_versions = SimpleNamespace(
        game_version="16.4.7480682",
        game_manifest_url="https://example.test/game-new.manifest",
        lcu_version="16.4",
        lcu_manifest_url="https://example.test/lcu-new.manifest",
    )
    decision = SimpleNamespace(
        should_update=True,
        reason="first_run",
        latest_versions=latest_versions,
        previous_state=None,
        changed_entities=SimpleNamespace(champion_aliases=tuple(), map_ids=tuple()),
        wad_changes=SimpleNamespace(
            added_paths=tuple(),
            changed_paths=tuple(),
            removed_paths=tuple(),
            update_paths=tuple(),
        ),
    )

    data_file_base = tmp_path / "output" / "manifest" / "16.4" / "data"
    data_file_base.parent.mkdir(parents=True, exist_ok=True)
    saved_state_file = tmp_path / "state" / "run_history.json"

    monkeypatch.setattr(pipeline, "ensure_official_sdk_path", lambda: tmp_path / "sdk")
    monkeypatch.setattr(pipeline, "evaluate_update_need", lambda **_: decision)
    monkeypatch.setattr(pipeline, "_preflight_remote_upload_index", lambda **_: {})
    monkeypatch.setattr(pipeline, "_retry_pending_manifest_sync_queue", lambda **_: None)
    monkeypatch.setattr(
        pipeline,
        "_resolve_runtime_game_path",
        lambda **_: (tmp_path / "real_game", False),
    )
    monkeypatch.setattr(pipeline, "check_local_game_path", lambda runtime_game_path: True)
    monkeypatch.setattr(pipeline, "run_data_updater", lambda **_: data_file_base)
    monkeypatch.setattr(
        pipeline,
        "resolve_processing_targets",
        lambda **_: SimpleNamespace(champion_ids=tuple(), map_ids=tuple()),
    )
    monkeypatch.setattr(pipeline, "run_bin_updater", lambda **_: None)
    monkeypatch.setattr(pipeline, "run_unpack", lambda **_: None)
    monkeypatch.setattr(pipeline, "_pack_unpacked_outputs", lambda **_: tuple())
    monkeypatch.setattr(pipeline, "_cleanup_version_audio_outputs", lambda **_: 0)
    monkeypatch.setattr(pipeline, "_upload_archives_and_manifest", lambda **_: None)
    monkeypatch.setattr(
        pipeline,
        "_write_and_upload_update_log_files",
        lambda **_: (_ for _ in ()).throw(RuntimeError("模拟更新日志上传失败")),
    )
    monkeypatch.setattr(pipeline, "build_local_state", lambda latest_versions: object())
    monkeypatch.setattr(
        pipeline,
        "save_local_state",
        lambda state, state_file: saved_state_file,
    )

    config = PipelineConfig(
        output_path=tmp_path / "output",
        game_path=tmp_path / "real_game",
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
        low_disk_mode=False,
        enable_pack=True,
        enable_upload=True,
    )
    assert pipeline.run_pipeline(config=config) == 0
