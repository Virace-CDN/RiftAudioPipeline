"""上传与索引模块测试。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import rift_audio_pipeline.upload as upload_module
import rift_audio_pipeline.upload_utils as upload_utils
from rift_audio_pipeline.upload import UploadConfig


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
    extra_file = tmp_path / "extra" / "说明.txt"
    extra_file.parent.mkdir(parents=True, exist_ok=True)
    extra_file.write_text("x", encoding="utf-8")
    champion_report_dir = output_path / "reports" / "16.4" / "champions"
    champion_report_dir.mkdir(parents=True, exist_ok=True)
    (champion_report_dir / "_1_metadata.yaml").write_text("meta", encoding="utf-8")
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
        assert extra_files == (extra_file.resolve(),)
        return (output_dir / f"{audio_dir.name}.7z",)

    monkeypatch.setattr(upload_module, "pack_all", _fake_pack_all)
    monkeypatch.setattr(upload_module, "_resolve_pack_extra_files", lambda config: (extra_file.resolve(),))

    config = UploadConfig(output_path=output_path, pack_password="secret")
    archives = upload_module._pack_unpacked_outputs(config=config, game_version="16.4")

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

        def upload_file(self, local_path: Path, remote_path: str, rtype: int = 3) -> dict[str, object]:
            del rtype
            self.upload_calls.append((local_path, remote_path))
            return {"path": remote_path, "errno": 0}

        def download_file(self, remote_path: str, local_path: Path) -> dict[str, object]:
            del local_path
            raise AssertionError(f"复用预加载索引后不应下载远端索引：{remote_path}")

        def get_path_entry(self, remote_path: str) -> dict[str, object]:
            normalized = remote_path if remote_path.startswith("/") else f"{self.remote_dir.rstrip('/')}/{remote_path}"
            if normalized in self.remote_dirs:
                return {"path": normalized, "isdir": 1}
            raise FileNotFoundError(remote_path)

        def create_directory(self, dir_path: str) -> dict[str, object]:
            normalized = dir_path if dir_path.startswith("/") else f"{self.remote_dir.rstrip('/')}/{dir_path}"
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
                f"同版本命中跳过上传时不应触发 move：{source_path} -> {destination_dir}/{new_name}/{ondup}"
            )

        def close(self) -> None:
            return None

    output_path = tmp_path / "output"
    package_root = output_path / "packages" / "16.4"
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
    monkeypatch.setattr(upload_module, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        upload_module,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

    config = UploadConfig(
        output_path=output_path,
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
    )
    manifest_file = upload_module._upload_archives_and_manifest(
        config=config,
        game_version="16.4",
        archives=(archive,),
        preloaded_remote_index=preloaded_remote_index,
    )

    assert manifest_file == package_root / "upload_manifest.json"
    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert fake_client.upload_calls == []
    assert payload["last_run"]["uploaded_count"] == 0
    assert payload["last_run"]["skipped_count"] == 1
    assert payload["entries"][0]["schema_version"] == 1
    assert payload["database_entry_count"] == 1
    db_entry = next(iter(payload["database"].values()))
    assert db_entry["schema_version"] == 1
    assert db_entry["versions"][0]["schema_version"] == 1
    assert payload["last_run"]["entries"][0]["schema_version"] == 1


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

        def upload_file(self, local_path: Path, remote_path: str, rtype: int = 3) -> dict[str, object]:
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
    archive = package_root / "champions" / "1·annie·黑暗之女·安妮-16.4-VO.7z"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b"a")

    fake_client = _FakeClient(credentials=None, remote_dir="/apps/test", token_store=None)
    monkeypatch.setattr(upload_module, "resolve_token_store", lambda: object())
    monkeypatch.setattr(
        upload_module,
        "BaiduPanClient",
        lambda credentials, remote_dir, token_store: fake_client,
    )

    config = UploadConfig(
        output_path=output_path,
        baidu_pan_remote_dir="/apps/test",
        baidu_pan_app_key="app",
        baidu_pan_secret_key="secret",
        baidu_pan_refresh_token="refresh",
    )
    manifest_file = upload_module._upload_archives_and_manifest(
        config=config,
        game_version="16.4",
        archives=(archive,),
        pending_manifest_sync_queue_file=queue_file,
    )

    assert manifest_file == package_root / "upload_manifest.json"
    queue_payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert len(queue_payload) == 1
    assert queue_payload[0]["schema_version"] == 1
    assert Path(queue_payload[0]["manifest_file"]) == manifest_file.resolve()


def test_build_update_log_payload_should_include_diff_details() -> None:
    """更新日志负载应包含版本区间、变更实体与上传结果统计。"""

    decision = SimpleNamespace(
        reason="region_manifest_changed",
        previous_state=SimpleNamespace(game_version="16.4"),
        wad_changes=SimpleNamespace(
            added_paths=("DATA/FINAL/Champions/Ahri.zh_CN.wad.client",),
            changed_paths=("DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",),
            removed_paths=tuple(),
            update_paths=(
                "DATA/FINAL/Champions/Ahri.zh_CN.wad.client",
                "DATA/FINAL/Maps/Shipping/Map11/Map11.zh_CN.wad.client",
            ),
        ),
    )
    target_entities = SimpleNamespace(champion_aliases=("ahri",), map_ids=(11,))
    targets = SimpleNamespace(champion_ids=(103,), map_ids=(11,))
    upload_run_records = [
        {"status": "uploaded", "remote_name": "103·ahri-16.5-VO.7z", "reason": "uploaded"},
        {"status": "skipped", "remote_name": "11·map11-16.5-VO.7z", "reason": "remote_index_hit_same_version"},
    ]

    payload = upload_module._build_update_log_payload(
        decision=decision,
        game_version="16.5",
        executed_at="2026-03-04T00:00:00Z",
        target_entities=target_entities,
        targets=targets,
        secondary_filter_result=None,
        upload_run_records=upload_run_records,
    )
    assert payload["from_game_version"] == "16.4"
    assert payload["to_game_version"] == "16.5"
    assert payload["changed_entities"]["champion_aliases"] == ["ahri"]
    assert payload["schema_version"] == 1
    assert payload["upload_summary"]["uploaded_count"] == 1
    assert payload["upload_summary"]["skipped_count"] == 1
    readable = upload_utils._build_update_log_text(payload=payload)
    assert "版本区间: 16.4 -> 16.5" in readable
