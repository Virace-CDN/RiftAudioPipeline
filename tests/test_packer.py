"""打包模块测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

import rift_audio_pipeline.packer as packer


def test_pack_champion_should_build_7z_command_with_password_and_mhe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """启用密码时应携带 `-p` 与 `-mhe=on` 参数。"""

    champion_dir = tmp_path / "annie"
    champion_dir.mkdir(parents=True, exist_ok=True)
    (champion_dir / "voice.txt").write_text("voice", encoding="utf-8")
    extra_file = tmp_path / "README.txt"
    extra_file.write_text("extra", encoding="utf-8")

    calls: dict[str, object] = {}

    monkeypatch.setattr(packer, "_resolve_7zip_executable", lambda _: "/usr/bin/7z")

    def _fake_execute_7z_command(command: tuple[str, ...], cwd: Path) -> None:
        calls["command"] = command
        calls["cwd"] = cwd
        assert (cwd / "README.txt").exists()
        assert (cwd / "annie").exists()

    monkeypatch.setattr(packer, "_execute_7z_command", _fake_execute_7z_command)

    archive = packer.pack_champion(
        champion_dir=champion_dir,
        output_path=tmp_path / "archives",
        password="secret",
        encrypt_filenames=True,
        extra_files=(extra_file,),
        compression_level=0,
    )

    command = calls["command"]
    assert isinstance(command, tuple)
    assert command[0] == "/usr/bin/7z"
    assert "-psecret" in command
    assert "-mhe=on" in command
    assert command[-1] == "."
    assert archive == (tmp_path / "archives" / "annie.7z").resolve()


def test_pack_champion_should_stage_report_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """传入报告文件时应写入实体目录根。"""

    champion_dir = tmp_path / "annie"
    champion_dir.mkdir(parents=True, exist_ok=True)
    (champion_dir / "voice.txt").write_text("voice", encoding="utf-8")
    report_file = tmp_path / "_1_metadata.yaml"
    report_file.write_text("meta: 1", encoding="utf-8")

    monkeypatch.setattr(packer, "_resolve_7zip_executable", lambda _: "/usr/bin/7z")

    def _fake_execute_7z_command(command: tuple[str, ...], cwd: Path) -> None:
        del command
        assert (cwd / "annie" / "_1_metadata.yaml").exists()

    monkeypatch.setattr(packer, "_execute_7z_command", _fake_execute_7z_command)

    archive = packer.pack_champion(
        champion_dir=champion_dir,
        output_path=tmp_path / "archives",
        report_file=report_file,
    )
    assert archive == (tmp_path / "archives" / "annie.7z").resolve()


def test_pack_champion_should_stage_extra_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """传入附加目录时应将目录内容展开到压缩包根目录。"""

    champion_dir = tmp_path / "annie"
    champion_dir.mkdir(parents=True, exist_ok=True)
    (champion_dir / "voice.txt").write_text("voice", encoding="utf-8")
    extra_dir = tmp_path / "pack_extra"
    extra_dir.mkdir(parents=True, exist_ok=True)
    (extra_dir / "说明.txt").write_text("extra", encoding="utf-8")

    monkeypatch.setattr(packer, "_resolve_7zip_executable", lambda _: "/usr/bin/7z")

    def _fake_execute_7z_command(command: tuple[str, ...], cwd: Path) -> None:
        del command
        assert (cwd / "说明.txt").read_text(encoding="utf-8") == "extra"
        assert not (cwd / "pack_extra").exists()

    monkeypatch.setattr(packer, "_execute_7z_command", _fake_execute_7z_command)

    packer.pack_champion(
        champion_dir=champion_dir,
        output_path=tmp_path / "archives",
        extra_files=(extra_dir,),
    )


def test_pack_champion_should_raise_on_invalid_compression_level(tmp_path: Path) -> None:
    """压缩级别越界时应抛错。"""

    champion_dir = tmp_path / "annie"
    champion_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError, match="compression_level"):
        packer.pack_champion(
            champion_dir=champion_dir,
            output_path=tmp_path / "archives",
            compression_level=99,
            seven_zip_executable="/usr/bin/7z",
        )


def test_pack_champion_should_raise_on_duplicate_extra_file_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """附加文件同名时应拒绝继续打包。"""

    champion_dir = tmp_path / "annie"
    champion_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "a" / "说明.txt").parent.mkdir(parents=True, exist_ok=True)
    first = tmp_path / "a" / "说明.txt"
    second = tmp_path / "b" / "说明.txt"
    second.parent.mkdir(parents=True, exist_ok=True)
    first.write_text("1", encoding="utf-8")
    second.write_text("2", encoding="utf-8")

    monkeypatch.setattr(packer, "_resolve_7zip_executable", lambda _: "/usr/bin/7z")
    monkeypatch.setattr(packer, "_execute_7z_command", lambda command, cwd: None)

    with pytest.raises(ValueError, match="附加文件名冲突"):
        packer.pack_champion(
            champion_dir=champion_dir,
            output_path=tmp_path / "archives",
            extra_files=(first, second),
        )


def test_pack_all_should_pack_each_subdirectory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """批量打包应按目录遍历并跳过普通文件。"""

    audio_dir = tmp_path / "audios"
    annie_dir = audio_dir / "Annie"
    zac_dir = audio_dir / "Zac"
    annie_dir.mkdir(parents=True, exist_ok=True)
    zac_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "ignore.txt").write_text("x", encoding="utf-8")

    calls: list[tuple[Path, str | None, Path | None]] = []

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
        del (
            output_path,
            password,
            encrypt_filenames,
            extra_files,
            compression_level,
            seven_zip_executable,
        )
        calls.append((champion_dir, archive_name, report_file))
        normalized = archive_name if archive_name is not None else f"{champion_dir.name}.7z"
        return tmp_path / "archives" / normalized

    monkeypatch.setattr(packer, "pack_champion", _fake_pack_champion)

    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "_Annie_metadata.yaml").write_text("meta", encoding="utf-8")
    archives = packer.pack_all(
        audio_dir=audio_dir,
        output_dir=tmp_path / "archives",
        version="16.4",
        audio_type="VO",
        report_dir=report_dir,
    )

    assert calls[0][0] == annie_dir
    assert calls[1][0] == zac_dir
    assert calls[0][1] == "Annie-16.4-VO.7z"
    assert calls[1][1] == "Zac-16.4-VO.7z"
    assert calls[0][2] == (report_dir / "_Annie_metadata.yaml").resolve()
    assert calls[1][2] is None
    assert archives == (
        tmp_path / "archives" / "Annie-16.4-VO.7z",
        tmp_path / "archives" / "Zac-16.4-VO.7z",
    )
