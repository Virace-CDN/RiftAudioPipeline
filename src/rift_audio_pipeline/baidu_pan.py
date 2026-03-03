"""百度网盘客户端适配层。"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from types import ModuleType

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_BAIDU_SDK_DIR = PROJECT_ROOT / "third_party" / "baidu_sdk"


def ensure_official_sdk_path() -> Path:
    """确保官方 SDK 目录在 `sys.path` 中。

    Returns:
        官方 SDK 根目录路径。

    Raises:
        FileNotFoundError: 官方 SDK 目录不存在。
    """

    if not OFFICIAL_BAIDU_SDK_DIR.exists():
        raise FileNotFoundError(f"未找到百度官方 SDK 目录：{OFFICIAL_BAIDU_SDK_DIR}")
    sdk_path_text = str(OFFICIAL_BAIDU_SDK_DIR)
    if sdk_path_text not in sys.path:
        sys.path.insert(0, sdk_path_text)
    return OFFICIAL_BAIDU_SDK_DIR


def load_openapi_client_module() -> ModuleType:
    """动态加载官方 `openapi_client` 模块。

    Returns:
        官方 SDK 的 `openapi_client` 模块对象。

    Raises:
        ModuleNotFoundError: SDK 目录存在但模块缺失。
    """

    ensure_official_sdk_path()
    return importlib.import_module("openapi_client")


@dataclass(frozen=True, slots=True)
class BaiduCredentials:
    """百度开放平台凭据。"""

    app_key: str
    secret_key: str
    refresh_token: str


class BaiduPanClient:
    """百度网盘客户端封装。

    该类用于隔离“业务调用”与“官方 SDK / REST API 实现细节”，后续统一在此扩展。
    """

    def __init__(self, credentials: BaiduCredentials, remote_dir: str) -> None:
        """初始化客户端。

        Args:
            credentials: 百度开放平台凭据。
            remote_dir: 网盘上传目录。
        """

        self._credentials = credentials
        self._remote_dir = remote_dir
        self._http_client = httpx.Client(timeout=60.0)

    def close(self) -> None:
        """关闭内部 HTTP 连接池。"""

        self._http_client.close()

    def refresh_access_token(self) -> str:
        """刷新 access token。

        Returns:
            新的 access token。

        Raises:
            NotImplementedError: 当前仅完成第一阶段整理，待第五阶段实现。
        """

        raise NotImplementedError("待实现：access token 自动刷新。")

    def list_files(self, dir_path: str) -> dict[str, object]:
        """列出网盘目录文件。

        Args:
            dir_path: 网盘目录路径。

        Returns:
            百度网盘接口返回的文件列表数据。

        Raises:
            NotImplementedError: 当前仅完成第一阶段整理，待第五阶段实现。
        """

        raise NotImplementedError(f"待实现：文件列表查询，dir_path={dir_path}")

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """上传单个文件。

        Args:
            local_path: 本地文件路径。
            remote_path: 网盘目标文件路径。

        Raises:
            NotImplementedError: 当前仅完成第一阶段整理，待第五阶段实现。
        """

        raise NotImplementedError(
            f"待实现：文件上传（precreate/superfile2/create），local_path={local_path}, "
            f"remote_path={remote_path}"
        )

    def download_file(self, remote_path: str, local_path: Path) -> None:
        """下载单个文件。

        Args:
            remote_path: 网盘源文件路径。
            local_path: 本地目标路径。

        Raises:
            NotImplementedError: 当前仅完成第一阶段整理，待第五阶段实现。
        """

        raise NotImplementedError(
            f"待实现：文件下载，remote_path={remote_path}, local_path={local_path}"
        )
