"""R20-native notification fan-out. No QwenPaw/OpenClaw runtime dependency."""
from __future__ import annotations
import base64
import datetime
import json
import os
import secrets
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from r20_backend.wechat_protocol import base_info as wechat_base_info, common_headers as wechat_common_headers

ROOT = Path(__file__).resolve().parents[1]
QQ_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
QQ_API_BASE = "https://api.sgroup.qq.com"


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return {**values, **os.environ}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> tuple[bool, str, dict[str, Any]]:
    request_headers = {"Content-Type": "application/json", "User-Agent": "R20-Standalone/5.4.2"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {"raw": raw}
            return 200 <= response.status < 300, f"HTTP {response.status}", data
    except Exception as exc:
        return False, str(exc), {}


def _send_qq(env: dict[str, str], message: str) -> tuple[bool, str]:
    app_id = env.get("R20_QQ_APP_ID", "")
    secret = env.get("R20_QQ_CLIENT_SECRET", "")
    openid = env.get("R20_QQ_OPENID", "")
    if not app_id or not secret or not openid:
        return False, "QQ App ID / Client Secret / OpenID 未完整配置"
    ok, detail, token_data = _post_json(QQ_TOKEN_URL, {"appId": app_id, "clientSecret": secret})
    access_token = token_data.get("access_token") if ok else ""
    if not access_token:
        return False, f"QQ access token 获取失败：{detail}"
    sequence = int(datetime.datetime.now().timestamp() * 1000) % 1_000_000
    ok, detail, response = _post_json(
        f"{QQ_API_BASE}/v2/users/{urllib.parse.quote(openid, safe='')}/messages",
        {"content": message, "msg_type": 0, "msg_seq": sequence},
        {"Authorization": f"QQBot {access_token}"},
    )
    return ok, detail if ok else f"{detail} {response}"


def _wechat_headers(bot_token: str) -> dict[str, str]:
    return wechat_common_headers(bot_token)


def _send_wechat_ilink(env: dict[str, str], message: str) -> tuple[bool, str]:
    token = env.get("R20_WECHAT_BOT_TOKEN", "")
    user_id = env.get("R20_WECHAT_USER_ID", "")
    context_token = env.get("R20_WECHAT_CONTEXT_TOKEN", "")
    base_url = env.get("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com").rstrip("/")
    if not token or not user_id or not context_token:
        return False, "微信 Bot Token / 用户 ID / Context Token 未完整配置"
    payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": user_id,
            "client_id": str(uuid.uuid4()),
            "message_type": 2,
            "message_state": 2,
            "context_token": context_token,
            "item_list": [{"type": 1, "text_item": {"text": message}}],
        },
        "base_info": wechat_base_info(),
    }
    ok, detail, response = _post_json(f"{base_url}/ilink/bot/sendmessage", payload, _wechat_headers(token))
    if not ok:
        return False, f"{detail} {response}"
    ret = response.get("ret", 0) if isinstance(response, dict) else 0
    if ret not in (0, None):
        if ret == -2:
            return False, "微信业务拒绝 ret=-2：会话 Context Token 已失效；请向 Bot 发送新消息以刷新会话"
        return False, f"微信业务拒绝 ret={ret} errmsg={response.get('errmsg', '')}"
    return True, detail


def notify(text: str) -> dict[str, str]:
    env = _env()
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    timestamp = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    message = f"【R20 Quantum Trader】{timestamp}\n{text.strip()}"
    result: dict[str, str] = {}

    if env.get("R20_NOTIFY_WEBHOOK_ENABLED") == "1" and env.get("R20_NOTIFICATION_WEBHOOK"):
        ok, detail, _ = _post_json(env["R20_NOTIFICATION_WEBHOOK"], {"source": "R20 Quantum Trader", "timestamp": timestamp, "message": message})
        result["webhook"] = "sent" if ok else f"failed: {detail}"

    if env.get("R20_NOTIFY_WECHAT_ENABLED") == "1" and env.get("R20_WECHAT_WEBHOOK"):
        ok, detail, _ = _post_json(env["R20_WECHAT_WEBHOOK"], {"msgtype": "text", "text": {"content": message}})
        result["wechat"] = "sent" if ok else f"failed: {detail}"

    if env.get("R20_NOTIFY_WECHAT_ILINK_ENABLED") == "1":
        ok, detail = _send_wechat_ilink(env, message)
        result["wechat_ilink"] = "sent" if ok else f"failed: {detail}"

    if env.get("R20_NOTIFY_TELEGRAM_ENABLED") == "1" and env.get("R20_TELEGRAM_BOT_TOKEN") and env.get("R20_TELEGRAM_CHAT_ID"):
        token = urllib.parse.quote(env["R20_TELEGRAM_BOT_TOKEN"], safe="")
        ok, detail, _ = _post_json(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": env["R20_TELEGRAM_CHAT_ID"], "text": message})
        result["telegram"] = "sent" if ok else f"failed: {detail}"

    if env.get("R20_NOTIFY_QQ_ENABLED") == "1":
        ok, detail = _send_qq(env, message)
        result["qq"] = "sent" if ok else f"failed: {detail}"
    return result


def send_qq_message(text: str) -> bool:
    """Compatibility symbol retained for existing strategy scripts."""
    return any(value == "sent" for value in notify(text).values())


def test_channel(channel: str) -> dict[str, str]:
    env = _env()
    key = f"R20_NOTIFY_{channel.upper()}_ENABLED"
    previous = os.environ.get(key)
    os.environ[key] = "1"
    try:
        return notify(f"🔔 {channel.upper()} 通知测试：R20 独立后台连接正常。")
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
