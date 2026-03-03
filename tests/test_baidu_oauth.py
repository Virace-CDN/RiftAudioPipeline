"""百度 OAuth 工具基础测试。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse

from rift_audio_pipeline.baidu.oauth import BaiduOAuthClient
from rift_audio_pipeline.baidu.oauth import BaiduOAuthToken
from rift_audio_pipeline.baidu.oauth import load_baidu_app_credentials
from rift_audio_pipeline.baidu.oauth import LocalBaiduTokenStore


def test_build_authorization_url_should_include_required_params() -> None:
    """授权 URL 需包含 code 模式必填参数。"""

    with BaiduOAuthClient() as client:
        url = client.build_authorization_url(
            app_key="app_key_for_test",
            scope="basic,netdisk",
            redirect_uri="oob",
            state="state123",
        )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "openapi.baidu.com"
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["app_key_for_test"]
    assert query["redirect_uri"] == ["oob"]
    assert query["scope"] == ["basic,netdisk"]
    assert query["state"] == ["state123"]


def test_local_token_store_round_trip_should_preserve_token_data(tmp_path: Path) -> None:
    """本地 token 存储应可正确读写。"""

    token_file = tmp_path / ".config" / "baidu" / "token.json"
    store = LocalBaiduTokenStore(token_file=token_file)
    token = BaiduOAuthToken(
        access_token="access_token_value",
        refresh_token="refresh_token_value",
        expires_in=2592000,
        scope="basic,netdisk",
        session_key="session_key_value",
        session_secret="session_secret_value",
        obtained_at=datetime.now(tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    )

    store.save_token(token=token)
    loaded = store.load_token()
    assert loaded.access_token == token.access_token
    assert loaded.refresh_token == token.refresh_token
    assert loaded.scope == token.scope
    assert loaded.expires_in == token.expires_in


def test_load_baidu_app_credentials_should_read_dev_file(tmp_path: Path) -> None:
    """应用凭据应支持从 .dev.baidu 读取。"""

    dev_file = tmp_path / ".dev.baidu"
    dev_file.write_text("AppKey=test_app_key\nSecretKey=test_secret_key\n", encoding="utf-8")

    credentials = load_baidu_app_credentials(
        app_key=None,
        secret_key=None,
        dev_config_file=dev_file,
    )
    assert credentials.app_key == "test_app_key"
    assert credentials.secret_key == "test_secret_key"
