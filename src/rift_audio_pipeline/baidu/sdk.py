"""百度官方 SDK 加载工具。"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[3]
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
    """动态加载官方 `openapi_client` 模块。"""

    ensure_official_sdk_path()
    return importlib.import_module("openapi_client")
