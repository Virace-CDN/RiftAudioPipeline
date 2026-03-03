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

    calls: list[Path] = []

    def _fake_pack_champion(
        champion_dir: Path,
        output_path: Path,
        *,
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
        calls.append(champion_dir)
        return tmp_path / "archives" / f"{champion_dir.name}.7z"

    monkeypatch.setattr(packer, "pack_champion", _fake_pack_champion)

    archives = packer.pack_all(audio_dir=audio_dir, output_dir=tmp_path / "archives")

    assert calls == [annie_dir, zac_dir]
    assert archives == (
        tmp_path / "archives" / "Annie.7z",
        tmp_path / "archives" / "Zac.7z",
    )
