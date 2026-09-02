"""WeChat iLink QR authentication helpers."""
from __future__ import annotations
import base64
import json
import secrets
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 40) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "R20-Standalone/6.0.0-preview", **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload


def create_qrcode(base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    payload = _get_json(f"{base_url.rstrip('/')}/ilink/bot/get_bot_qrcode?bot_type=3", timeout=15)
    qrcode = payload.get("qrcode", "")
    image_content = payload.get("qrcode_img_content") or payload.get("url") or ""
    if not qrcode or not image_content:
        raise RuntimeError("微信 iLink 未返回有效二维码")
    return {"qrcode": qrcode, "image_content": image_content, "expires_hint": "二维码过期后请重新生成"}


def latest_session(bot_token: str, base_url: str = DEFAULT_BASE_URL) -> dict[str, str]:
    uin = base64.b64encode(str(secrets.randbelow(0xFFFFFFFF)).encode()).decode()
    payload = _post_json(
        f"{base_url.rstrip('/')}/ilink/bot/getupdates",
        {"get_updates_buf": "", "base_info": {"channel_version": "2.0.1"}},
        {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": uin,
            "Authorization": f"Bearer {bot_token}",
        },
    )
    messages = payload.get("msgs") or payload.get("messages") or []
    for message in reversed(messages):
        context_token = message.get("context_token") or message.get("contextToken") or ""
        user_id = message.get("from_user_id") or message.get("fromUserId") or ""
        if context_token and user_id:
            return {"context_token": context_token, "user_id": user_id}
    raise RuntimeError("尚未收到可用于主动通知的微信消息，请先向 Bot 发送一条文字消息")


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"User-Agent": "R20-Standalone/6.0.0-preview", **headers}, method="POST")
    with urllib.request.urlopen(request, timeout=40) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def qrcode_status(qrcode: str, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/ilink/bot/get_qrcode_status?qrcode={urllib.parse.quote(qrcode, safe='')}"
    payload = _get_json(url, {"iLink-App-ClientVersion": "1"}, timeout=40)
    return {
        "status": payload.get("status", "wait"),
        "bot_token": payload.get("bot_token", ""),
        "base_url": payload.get("baseurl") or payload.get("base_url") or base_url,
        "bot_id": payload.get("ilink_bot_id") or payload.get("bot_id") or "",
        "user_id": payload.get("ilink_user_id") or payload.get("user_id") or "",
    }
