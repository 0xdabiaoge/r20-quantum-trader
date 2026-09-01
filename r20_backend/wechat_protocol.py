"""Wire constants matching Tencent openclaw-weixin 2.4.8."""
from __future__ import annotations
import base64
import secrets

PROTOCOL_VERSION = "2.4.8"
ILINK_APP_ID = "bot"
ILINK_APP_CLIENT_VERSION = str((2 << 16) | (4 << 8) | 8)
BOT_AGENT = "R20/5.4.2"


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
