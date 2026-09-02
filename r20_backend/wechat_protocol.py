"""Tencent iLink wire constants aligned with current QwenPaw/OpenClaw clients."""
from __future__ import annotations
import base64
import secrets

# Match Tencent's current official openclaw-weixin package metadata exactly.
PROTOCOL_VERSION = "2.4.8"
ILINK_APP_ID = "bot"
ILINK_APP_CLIENT_VERSION = str((2 << 16) | (4 << 8) | 8)
BOT_AGENT = "R20/6.0.0-preview"


def base_info() -> dict[str, str]:
    return {"channel_version": PROTOCOL_VERSION, "bot_agent": BOT_AGENT}


def common_headers(bot_token: str = "") -> dict[str, str]:
    uin = base64.b64encode(str(secrets.randbelow(0xFFFFFFFF)).encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": uin,
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": ILINK_APP_CLIENT_VERSION,
    }
    if bot_token:
        headers["Authorization"] = f"Bearer {bot_token}"
    return headers
