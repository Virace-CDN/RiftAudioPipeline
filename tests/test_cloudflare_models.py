"""Cloudflare 对接层模型测试。"""

from __future__ import annotations

import pytest

from rift_audio_pipeline.cloudflare.models import CloudflareControlConfig


def test_cloudflare_control_config_should_normalize_base_url() -> None:
    """应去掉末尾斜杠。"""

    config = CloudflareControlConfig(base_url="https://control.example.com/")
    assert config.base_url == "https://control.example.com"


def test_cloudflare_control_config_should_require_access_pair_together() -> None:
    """Access 鉴权字段应成对提供。"""

    with pytest.raises(ValueError, match="access_client_id"):
        CloudflareControlConfig(
            base_url="https://control.example.com",
            access_client_id="client-id",
        )
