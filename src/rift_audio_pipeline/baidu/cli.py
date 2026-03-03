"""百度 OAuth 本地调试命令行。"""

from __future__ import annotations

import argparse
from pathlib import Path

from rift_audio_pipeline.baidu.oauth import BaiduOAuthClient
from rift_audio_pipeline.baidu.oauth import DEFAULT_BAIDU_DEV_CONFIG_FILE
from rift_audio_pipeline.baidu.oauth import DEFAULT_BAIDU_REDIRECT_URI
from rift_audio_pipeline.baidu.oauth import DEFAULT_BAIDU_SCOPE
from rift_audio_pipeline.baidu.oauth import DEFAULT_BAIDU_TOKEN_FILE
from rift_audio_pipeline.baidu.oauth import load_baidu_app_credentials
from rift_audio_pipeline.baidu.oauth import mask_secret
from rift_audio_pipeline.baidu.oauth import resolve_token_store


def build_parser() -> argparse.ArgumentParser:
    """构建 OAuth 调试 CLI。"""

    parser = argparse.ArgumentParser(description="百度 OAuth 本地调试工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_url_parser = subparsers.add_parser("auth-url", help="生成授权 URL")
    _add_common_credential_args(auth_url_parser)
    auth_url_parser.add_argument(
        "--scope",
        default=DEFAULT_BAIDU_SCOPE,
        help="授权范围，默认 basic,netdisk",
    )
    auth_url_parser.add_argument(
        "--redirect-uri",
        default=DEFAULT_BAIDU_REDIRECT_URI,
        help="重定向地址，默认 oob",
    )
    auth_url_parser.add_argument("--state", default=None, help="可选 state 参数")
    auth_url_parser.set_defaults(handler=_handle_auth_url)

    exchange_parser = subparsers.add_parser("exchange-code", help="授权码换 token")
    _add_common_credential_args(exchange_parser)
    exchange_parser.add_argument("--code", required=True, help="授权码")
    exchange_parser.add_argument(
        "--redirect-uri",
        default=DEFAULT_BAIDU_REDIRECT_URI,
        help="重定向地址，默认 oob",
    )
    exchange_parser.add_argument(
        "--token-file",
        default=str(DEFAULT_BAIDU_TOKEN_FILE),
        help="token 存储文件路径",
    )
    exchange_parser.set_defaults(handler=_handle_exchange_code)

    refresh_parser = subparsers.add_parser("refresh-token", help="刷新 access token")
    _add_common_credential_args(refresh_parser)
    refresh_parser.add_argument(
        "--refresh-token",
        default=None,
        help="显式指定 refresh token；不传则从 token-file 读取",
    )
    refresh_parser.add_argument(
        "--token-file",
        default=str(DEFAULT_BAIDU_TOKEN_FILE),
        help="token 存储文件路径",
    )
    refresh_parser.set_defaults(handler=_handle_refresh_token)

    show_token_parser = subparsers.add_parser("show-token", help="查看本地 token 元信息")
    show_token_parser.add_argument(
        "--token-file",
        default=str(DEFAULT_BAIDU_TOKEN_FILE),
        help="token 存储文件路径",
    )
    show_token_parser.set_defaults(handler=_handle_show_token)

    return parser


def main() -> int:
    """CLI 主函数。"""

    parser = build_parser()
    args = parser.parse_args()
    handler = args.handler
    return int(handler(args))


def _add_common_credential_args(parser: argparse.ArgumentParser) -> None:
    """为命令添加凭据参数。"""

    parser.add_argument("--app-key", default=None, help="百度 app key")
    parser.add_argument("--secret-key", default=None, help="百度 secret key")
    parser.add_argument(
        "--dev-config",
        default=str(DEFAULT_BAIDU_DEV_CONFIG_FILE),
        help="开发凭据文件路径，默认 .dev.baidu",
    )


def _handle_auth_url(args: argparse.Namespace) -> int:
    """处理 auth-url 命令。"""

    credentials = load_baidu_app_credentials(
        app_key=args.app_key,
        secret_key=args.secret_key,
        dev_config_file=Path(args.dev_config),
    )
    with BaiduOAuthClient() as client:
        url = client.build_authorization_url(
            app_key=credentials.app_key,
            scope=args.scope,
            redirect_uri=args.redirect_uri,
            state=args.state,
        )
    print("请在浏览器打开以下 URL 并完成授权：")
    print(url)
    return 0


def _handle_exchange_code(args: argparse.Namespace) -> int:
    """处理 exchange-code 命令。"""

    credentials = load_baidu_app_credentials(
        app_key=args.app_key,
        secret_key=args.secret_key,
        dev_config_file=Path(args.dev_config),
    )
    token_store = resolve_token_store(token_file=Path(args.token_file))
    with BaiduOAuthClient() as client:
        token = client.exchange_code_for_token(
            code=args.code,
            credentials=credentials,
            redirect_uri=args.redirect_uri,
        )
    token_store.save_token(token=token)
    print(f"token 已写入：{token_store.token_file}")
    print(f"access_token（脱敏）：{mask_secret(token.access_token)}")
    print(f"refresh_token（脱敏）：{mask_secret(token.refresh_token)}")
    print(f"expires_at（UTC）：{token.expires_at}")
    return 0


def _handle_refresh_token(args: argparse.Namespace) -> int:
    """处理 refresh-token 命令。"""

    credentials = load_baidu_app_credentials(
        app_key=args.app_key,
        secret_key=args.secret_key,
        dev_config_file=Path(args.dev_config),
    )
    token_store = resolve_token_store(token_file=Path(args.token_file))
    refresh_token = args.refresh_token
    if refresh_token is None:
        refresh_token = token_store.load_token().refresh_token

    with BaiduOAuthClient() as client:
        token = client.refresh_access_token(
            refresh_token=refresh_token,
            credentials=credentials,
        )
    token_store.save_token(token=token)
    print(f"token 已刷新并写入：{token_store.token_file}")
    print(f"access_token（脱敏）：{mask_secret(token.access_token)}")
    print(f"refresh_token（脱敏）：{mask_secret(token.refresh_token)}")
    print(f"expires_at（UTC）：{token.expires_at}")
    return 0


def _handle_show_token(args: argparse.Namespace) -> int:
    """处理 show-token 命令。"""

    token_store = resolve_token_store(token_file=Path(args.token_file))
    token = token_store.load_token()
    print(f"token 文件：{token_store.token_file}")
    print(f"scope：{token.scope}")
    print(f"obtained_at（UTC）：{token.obtained_at}")
    print(f"expires_at（UTC）：{token.expires_at}")
    print(f"access_token（脱敏）：{mask_secret(token.access_token)}")
    print(f"refresh_token（脱敏）：{mask_secret(token.refresh_token)}")
    return 0
