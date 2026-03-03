"""打包模块。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import shutil
import subprocess
import tempfile

DEFAULT_COMPRESSION_LEVEL = 0
MAX_COMPRESSION_LEVEL = 9
ARCHIVE_SUFFIX = ".7z"
SEVEN_ZIP_CANDIDATES = ("7z", "7zz", "7za")


def pack_champion(
    champion_dir: Path,
    output_path: Path,
    *,
    archive_name: str | None = None,
    report_file: Path | None = None,
    password: str | None = None,
    encrypt_filenames: bool = True,
    extra_files: Sequence[Path] = tuple(),
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
    seven_zip_executable: str | None = None,
) -> Path:
    """打包单个英雄语音目录。

    Args:
        champion_dir: 英雄语音目录。
        output_path: 打包产物目录。
        archive_name: 压缩包文件名；为空时使用目录名。
        report_file: 可选的 `_id_metadata.yaml` 报告文件。
        password: 压缩包密码；为空时不启用密码。
        encrypt_filenames: 启用密码时是否开启文件名加密（`-mhe=on`）。
        extra_files: 需要附加到压缩包根目录的额外文件集合。
        compression_level: 压缩级别（`0-9`）。
        seven_zip_executable: 指定 7z 可执行文件；为空时自动查找。

    Returns:
        产物路径。

    Raises:
        FileNotFoundError: 源目录、附加文件或 7z 可执行文件不存在时抛出。
        ValueError: 参数非法（如压缩级别越界）时抛出。
        RuntimeError: 7z 命令执行失败时抛出。
    """

    source_dir = champion_dir.expanduser().resolve()
    if not source_dir.is_dir():
        raise FileNotFoundError(f"英雄语音目录不存在或不可读：{source_dir}")

    output_dir = output_path.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_file_name = _normalize_archive_name(archive_name=archive_name, fallback=source_dir.name)
    archive_path = output_dir / archive_file_name
    normalized_password = password if password else None

    executable = _resolve_7zip_executable(seven_zip_executable)
    level = _validate_compression_level(compression_level)
    staged_extra_files = _normalize_extra_files(extra_files)
    normalized_report_file = _normalize_report_file(report_file)

    with tempfile.TemporaryDirectory(prefix="rift_pack_") as temp_dir:
        stage_root = Path(temp_dir)
        _stage_directory(stage_root=stage_root, source_dir=source_dir)
        _stage_report_file(stage_root=stage_root, report_file=normalized_report_file)
        _stage_extra_files(stage_root=stage_root, extra_files=staged_extra_files)
        command = _build_7z_command(
            executable=executable,
            archive_path=archive_path,
            compression_level=level,
            password=normalized_password,
            encrypt_filenames=encrypt_filenames,
        )
        _execute_7z_command(command=command, cwd=stage_root)

    return archive_path


def pack_all(
    audio_dir: Path,
    output_dir: Path,
    *,
    version: str | None = None,
    audio_type: str | None = None,
    report_dir: Path | None = None,
    password: str | None = None,
    encrypt_filenames: bool = True,
    extra_files: Sequence[Path] = tuple(),
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
    seven_zip_executable: str | None = None,
) -> tuple[Path, ...]:
    """批量打包语音目录。

    Args:
        audio_dir: 音频目录。
        output_dir: 产物目录。
        version: 压缩包版本后缀（例如 `16.4`）。
        audio_type: 压缩包类型后缀（例如 `VO`）。
        report_dir: 报告目录，命名规则为 `_<实体ID>_metadata.yaml`。
        password: 压缩包密码；为空时不启用密码。
        encrypt_filenames: 启用密码时是否开启文件名加密（`-mhe=on`）。
        extra_files: 需要附加到压缩包根目录的额外文件集合。
        compression_level: 压缩级别（`0-9`）。
        seven_zip_executable: 指定 7z 可执行文件；为空时自动查找。

    Returns:
        打包产物路径集合。

    Raises:
        FileNotFoundError: 音频目录不存在时抛出。
        ValueError: 参数非法时抛出。
        RuntimeError: 7z 命令执行失败时抛出。
    """

    source_root = audio_dir.expanduser().resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"音频目录不存在或不可读：{source_root}")

    archives: list[Path] = []
    for item in sorted(source_root.iterdir(), key=lambda path: path.name.casefold()):
        if not item.is_dir():
            continue
        archives.append(
            pack_champion(
                champion_dir=item,
                output_path=output_dir,
                archive_name=_build_archive_name(
                    directory_name=item.name,
                    version=version,
                    audio_type=audio_type,
                ),
                report_file=_resolve_report_file(folder_name=item.name, report_dir=report_dir),
                password=password,
                encrypt_filenames=encrypt_filenames,
                extra_files=extra_files,
                compression_level=compression_level,
                seven_zip_executable=seven_zip_executable,
            )
        )
    return tuple(archives)


def _resolve_7zip_executable(seven_zip_executable: str | None) -> str:
    """解析 7z 可执行文件路径。"""

    if seven_zip_executable:
        return seven_zip_executable
    for candidate in SEVEN_ZIP_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError("未找到 7z 可执行文件，请安装 7-Zip 并加入 PATH")


def _validate_compression_level(compression_level: int) -> int:
    """校验压缩级别。"""

    if compression_level < 0 or compression_level > MAX_COMPRESSION_LEVEL:
        raise ValueError(
            f"compression_level 超出范围，期望 0-{MAX_COMPRESSION_LEVEL}，实际 {compression_level}"
        )
    return compression_level


def _normalize_extra_files(extra_files: Sequence[Path]) -> tuple[Path, ...]:
    """标准化并校验附加文件列表。"""

    resolved: list[Path] = []
    for file_path in extra_files:
        resolved_path = file_path.expanduser().resolve()
        if not resolved_path.is_file():
            raise FileNotFoundError(f"附加文件不存在或不可读：{resolved_path}")
        resolved.append(resolved_path)
    return tuple(resolved)


def _normalize_report_file(report_file: Path | None) -> Path | None:
    """标准化并校验报告文件。"""

    if report_file is None:
        return None
    resolved = report_file.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"报告文件不存在或不可读：{resolved}")
    return resolved


def _normalize_archive_name(archive_name: str | None, fallback: str) -> str:
    """规范化压缩包文件名。"""

    raw_name = archive_name.strip() if isinstance(archive_name, str) else fallback
    if not raw_name:
        raw_name = fallback
    if not raw_name.endswith(ARCHIVE_SUFFIX):
        return f"{raw_name}{ARCHIVE_SUFFIX}"
    return raw_name


def _build_archive_name(
    directory_name: str,
    version: str | None,
    audio_type: str | None,
) -> str:
    """构建压缩包文件名。"""

    parts = [directory_name]
    if version is not None and version.strip():
        parts.append(version.strip())
    if audio_type is not None and audio_type.strip():
        parts.append(audio_type.strip())
    return f"{'-'.join(parts)}{ARCHIVE_SUFFIX}"


def _resolve_report_file(folder_name: str, report_dir: Path | None) -> Path | None:
    """根据目录名解析对应报告文件。"""

    if report_dir is None:
        return None
    resolved_report_dir = report_dir.expanduser().resolve()
    if not resolved_report_dir.is_dir():
        return None
    entity_id = folder_name.split("·", maxsplit=1)[0].strip()
    if not entity_id:
        return None
    candidate = resolved_report_dir / f"_{entity_id}_metadata.yaml"
    if candidate.is_file():
        return candidate
    return None


def _stage_directory(stage_root: Path, source_dir: Path) -> None:
    """将目录以链接或复制方式放入临时打包目录。"""

    target = stage_root / source_dir.name
    try:
        target.symlink_to(source_dir, target_is_directory=True)
    except OSError:
        shutil.copytree(source_dir, target)


def _stage_report_file(stage_root: Path, report_file: Path | None) -> None:
    """将报告文件复制到压缩包根目录。"""

    if report_file is None:
        return
    target = stage_root / report_file.name
    shutil.copy2(report_file, target)


def _stage_extra_files(stage_root: Path, extra_files: Sequence[Path]) -> None:
    """将附加文件复制到压缩包根目录。"""

    used_names: set[str] = set()
    for file_path in extra_files:
        target = stage_root / file_path.name
        lowered = file_path.name.casefold()
        if lowered in used_names:
            raise ValueError(f"附加文件名冲突：{file_path.name}")
        used_names.add(lowered)
        shutil.copy2(file_path, target)


def _build_7z_command(
    executable: str,
    archive_path: Path,
    compression_level: int,
    password: str | None,
    encrypt_filenames: bool,
) -> tuple[str, ...]:
    """构建 7z 打包命令。"""

    command: list[str] = [
        executable,
        "a",
        "-t7z",
        "-y",
        f"-mx{compression_level}",
    ]
    if password:
        command.append(f"-p{password}")
        if encrypt_filenames:
            command.append("-mhe=on")
    command.extend([str(archive_path), "."])
    return tuple(command)


def _execute_7z_command(command: Sequence[str], cwd: Path) -> None:
    """执行 7z 命令并在失败时抛出带上下文的异常。"""

    try:
        subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or "").strip()
        message = f"7z 打包失败，cwd={cwd}"
        if details:
            message = f"{message}，details={details}"
        raise RuntimeError(message) from error
