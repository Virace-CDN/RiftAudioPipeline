"""百度 OAuth 授权与本地 token 管理。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import importlib
import json
import os
from pathlib import Path
from typing import Any
from typing import Mapping
from urllib.parse import urlencode

from rift_audio_pipeline.baidu.sdk import ensure_official_sdk_path
from rift_audio_pipeline.baidu.sdk import load_openapi_client_module

DEFAULT_BAIDU_SCOPE = "basic,netdisk"
DEFAULT_BAIDU_REDIRECT_URI = "oob"
DEFAULT_BAIDU_DEV_CONFIG_FILE = Path(".dev.baidu")
DEFAULT_BAIDU_TOKEN_FILE = Path(".config/baidu/token.json")
BAIDU_OAUTH_AUTHORIZE_URL = "https://openapi.baidu.com/oauth/2.0/authorize"


class BaiduOAuthError(RuntimeError):
    """百度 OAuth 请求异常。"""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        """初始化异常对象。

        Args:
            message: 异常描述信息。
            error_code: 百度接口返回的错误码。
        """

        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True, slots=True)
class BaiduAppCredentials:
    """百度开放平台应用凭据。"""

    app_key: str
    secret_key: str


@dataclass(frozen=True, slots=True)
class BaiduOAuthToken:
    """百度 OAuth token 数据。"""

    access_token: str
    refresh_token: str
    expires_in: int
    scope: str
    session_key: str | None
    session_secret: str | None
    obtained_at: str

    @property
    def expires_at(self) -> str:
        """返回过期时间（UTC ISO8601）。"""

        obtained_at = _parse_utc_iso(self.obtained_at)
        return _to_utc_iso(obtained_at + timedelta(seconds=self.expires_in))

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        fallback_refresh_token: str | None = None,
    ) -> BaiduOAuthToken:
        """从百度接口响应构建 token。

        Args:
            payload: 接口响应字典。
            fallback_refresh_token: 刷新接口未返回新 refresh_token 时的回退值。

        Returns:
            标准化后的 token 对象。

        Raises:
            BaiduOAuthError: 响应缺失必需字段时抛出。
        """

        access_token = _as_non_empty_str(payload.get("access_token"))
        refresh_token = _as_non_empty_str(payload.get("refresh_token")) or fallback_refresh_token
        expires_in_value = payload.get("expires_in")
        scope = _as_non_empty_str(payload.get("scope")) or ""
        session_key = _as_non_empty_str(payload.get("session_key"))
        session_secret = _as_non_empty_str(payload.get("session_secret"))

        if access_token is None:
            raise BaiduOAuthError("百度 OAuth 响应缺少 access_token。")
        if refresh_token is None:
            raise BaiduOAuthError("百度 OAuth 响应缺少 refresh_token。")
        if not isinstance(expires_in_value, int):
            raise BaiduOAuthError(
                f"百度 OAuth 响应缺少合法 expires_in，当前值：{expires_in_value!r}"
            )

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in_value,
            scope=scope,
            session_key=session_key,
            session_secret=session_secret,
            obtained_at=_to_utc_iso(datetime.now(tz=timezone.utc)),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BaiduOAuthToken:
        """从本地 JSON 反序列化 token。"""

        return cls(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            expires_in=int(data["expires_in"]),
            scope=str(data.get("scope", "")),
            session_key=_as_non_empty_str(data.get("session_key")),
            session_secret=_as_non_empty_str(data.get("session_secret")),
            obtained_at=str(data["obtained_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化 token 到 JSON 字典。"""

        return dict(asdict(self))


class LocalBaiduTokenStore:
    """本地 token 文件存储。"""

    def __init__(self, token_file: Path) -> None:
        """初始化 token 存储。

        Args:
            token_file: token 文件完整路径。
        """

        self._token_file = token_file

    @property
    def token_file(self) -> Path:
        """返回 token 文件路径。"""

        return self._token_file

    def load_token(self) -> BaiduOAuthToken:
        """读取本地 token。

        Returns:
            解析后的 token 对象。

        Raises:
            FileNotFoundError: token 文件不存在。
            ValueError: token 文件内容非法。
        """

        if not self._token_file.exists():
            raise FileNotFoundError(f"未找到 token 文件：{self._token_file}")
        raw_text = self._token_file.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError(f"token 文件格式错误，期望 JSON 对象：{self._token_file}")
        return BaiduOAuthToken.from_dict(data=data)

    def save_token(self, token: BaiduOAuthToken) -> None:
        """写入本地 token。

        Args:
            token: 需持久化的 token 对象。
        """

        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(token.to_dict(), ensure_ascii=False, indent=2)
        self._token_file.write_text(serialized, encoding="utf-8")
        if os.name != "nt":
            os.chmod(self._token_file, 0o600)


class BaiduOAuthClient:
    """百度 OAuth 客户端（官方 SDK AuthApi 适配）。"""

    def __init__(self, timeout: float = 30.0) -> None:
        """初始化客户端。

        Args:
            timeout: 接口请求超时（秒）。
        """

        self._timeout = timeout
        ensure_official_sdk_path()
        self._openapi_client = load_openapi_client_module()
        self._api_client = self._openapi_client.ApiClient()

        auth_api_module = importlib.import_module("openapi_client.api.auth_api")
        exception_module = importlib.import_module("openapi_client.exceptions")
        self._auth_api = auth_api_module.AuthApi(self._api_client)
        self._api_exception_cls = exception_module.ApiException

    def __enter__(self) -> BaiduOAuthClient:
        return self

    def __exit__(self, exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """关闭连接池。"""

        self._api_client.close()

    def build_authorization_url(
        self,
        app_key: str,
        scope: str = DEFAULT_BAIDU_SCOPE,
        redirect_uri: str = DEFAULT_BAIDU_REDIRECT_URI,
        state: str | None = None,
    ) -> str:
        """生成授权码模式 URL。"""

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": app_key,
            "redirect_uri": redirect_uri,
            "scope": scope,
        }
        if state is not None:
            params["state"] = state
        return f"{BAIDU_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_token(
        self,
        code: str,
        credentials: BaiduAppCredentials,
        redirect_uri: str = DEFAULT_BAIDU_REDIRECT_URI,
    ) -> BaiduOAuthToken:
        """使用授权码换取 token。"""

        payload = self._invoke_auth_api(
            lambda: self._auth_api.oauth_token_code2token(
                code,
                credentials.app_key,
                credentials.secret_key,
                redirect_uri,
                _request_timeout=self._timeout,
            ),
            operation="oauth_token_code2token",
        )
        return BaiduOAuthToken.from_payload(payload=payload, fallback_refresh_token=None)

    def refresh_access_token(
        self,
        refresh_token: str,
        credentials: BaiduAppCredentials,
    ) -> BaiduOAuthToken:
        """使用 refresh_token 刷新 access_token。"""

        payload = self._invoke_auth_api(
            lambda: self._auth_api.oauth_token_refresh_token(
                refresh_token,
                credentials.app_key,
                credentials.secret_key,
                _request_timeout=self._timeout,
            ),
            operation="oauth_token_refresh_token",
        )
        return BaiduOAuthToken.from_payload(
            payload=payload,
            fallback_refresh_token=refresh_token,
        )

    def _invoke_auth_api(self, action: Any, operation: str) -> dict[str, Any]:
        """执行官方 AuthApi 调用并统一处理错误。"""

        try:
            raw_payload = action()
        except self._api_exception_cls as error:  # type: ignore[misc]
            raise BaiduOAuthError(
                message=f"百度 OAuth SDK 调用失败：{operation}，{_extract_api_exception_message(error)}"
            ) from error

        payload = _payload_to_dict(raw_payload)
        error_code = _as_non_empty_str(payload.get("error"))
        if error_code is not None:
            error_description = _as_non_empty_str(payload.get("error_description")) or "未知错误"
            raise BaiduOAuthError(
                message=f"百度 OAuth 请求失败，error={error_code}，description={error_description}",
                error_code=error_code,
            )
        return payload


def load_baidu_app_credentials(
    app_key: str | None,
    secret_key: str | None,
    dev_config_file: Path = DEFAULT_BAIDU_DEV_CONFIG_FILE,
) -> BaiduAppCredentials:
    """加载应用凭据，优先级为参数 > 环境变量 > `.dev.baidu`。"""

    resolved_app_key = app_key or _as_non_empty_str(os.getenv("BAIDU_PAN_APP_KEY"))
    resolved_secret_key = secret_key or _as_non_empty_str(os.getenv("BAIDU_PAN_SECRET_KEY"))
    file_values = _load_kv_file(dev_config_file)
    if resolved_app_key is None:
        resolved_app_key = _as_non_empty_str(file_values.get("AppKey"))
    if resolved_secret_key is None:
        resolved_secret_key = _as_non_empty_str(file_values.get("SecretKey"))

    if resolved_app_key is None:
        raise ValueError("缺少 app key，请传 --app-key 或配置 BAIDU_PAN_APP_KEY / .dev.baidu")
    if resolved_secret_key is None:
        raise ValueError(
            "缺少 secret key，请传 --secret-key 或配置 BAIDU_PAN_SECRET_KEY / .dev.baidu"
        )
    return BaiduAppCredentials(app_key=resolved_app_key, secret_key=resolved_secret_key)


def resolve_token_store(token_file: Path = DEFAULT_BAIDU_TOKEN_FILE) -> LocalBaiduTokenStore:
    """创建 token 存储对象。"""

    return LocalBaiduTokenStore(token_file=token_file.expanduser().resolve())


def mask_secret(value: str) -> str:
    """对敏感字段做脱敏显示。"""

    if len(value) <= 12:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


def _load_kv_file(path: Path) -> dict[str, str]:
    """读取简单 `key=value` 配置文件。"""

    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        result[key.strip()] = _normalize_config_value(raw_value.strip())
    return result


def _payload_to_dict(payload: Any) -> dict[str, Any]:
    """将 SDK 响应统一转换为字典。"""

    if isinstance(payload, dict):
        return payload
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, dict):
            return converted

    attribute_map = getattr(payload, "attribute_map", None)
    if isinstance(attribute_map, dict):
        result: dict[str, Any] = {}
        for field_name in attribute_map:
            result[field_name] = getattr(payload, field_name, None)
        return result

    if isinstance(payload, Mapping):
        return dict(payload)
    raise BaiduOAuthError(message=f"无法解析 OAuth SDK 响应类型：{type(payload)!r}")


def _extract_api_exception_message(error: Exception) -> str:
    """提取官方 SDK 异常可读信息。"""

    reason = getattr(error, "reason", None)
    body = getattr(error, "body", None)
    status = getattr(error, "status", None)
    return f"status={status}, reason={reason}, body={body}"


def _as_non_empty_str(value: object) -> str | None:
    """将对象安全转换为非空字符串。"""

    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _normalize_config_value(value: str) -> str:
    """标准化配置值，去除包裹引号。"""

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value


def _to_utc_iso(value: datetime) -> str:
    """将时间转换为 UTC ISO8601 字符串。"""

    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc_iso(value: str) -> datetime:
    """解析 UTC ISO8601 字符串。"""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))
