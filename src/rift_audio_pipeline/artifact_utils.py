"""产物文件与远端路径辅助函数。"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def calculate_sha256(file_path: Path) -> str:
    """计算文件的 SHA256。"""

    digest = sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def join_remote_file_path(*, remote_dir: str, remote_name: str) -> str:
    """拼接远端目录和文件相对路径。"""

    normalized_dir = remote_dir.strip().replace("\\", "/").rstrip("/")
    normalized_name = remote_name.strip().replace("\\", "/").lstrip("/")
    if not normalized_dir:
        return f"/{normalized_name}" if not normalized_name.startswith("/") else normalized_name
    if not normalized_dir.startswith("/"):
        normalized_dir = f"/{normalized_dir}"
    return f"{normalized_dir}/{normalized_name}" if normalized_name else normalized_dir
