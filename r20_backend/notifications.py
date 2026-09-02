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
from r20_backend.net_security import validate_outbound_url, validate_wechat_base_url

ROOT = Path(__file__).resolve().parents[1]
SECRET_LOADER = None
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
    # Dynamic encrypted secrets override both stale inherited values and legacy .env values.
    try:
        if SECRET_LOADER is not None:
            encrypted = SECRET_LOADER()
        elif ROOT == Path(__file__).resolve().parents[1]:
            from r20_gateway.secrets import load_secrets
            encrypted = load_secrets()
        else:
            encrypted = {}
    except Exception: encrypted = {}
    return {**os.environ, **values, **encrypted}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> tuple[bool, str, dict[str, Any]]:
    request_headers = {"Content-Type": "application/json", "User-Agent": "R20-Standalone/6.0.0-preview"}
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
        return False, f"QQ access token 获取失败：{detail} code={token_data.get('code','')} message={token_data.get('message','')}"
    sequence = int(datetime.datetime.now().timestamp() * 1000) % 1_000_000
    ok, detail, response = _post_json(
        f"{QQ_API_BASE}/v2/users/{urllib.parse.quote(openid, safe='')}/messages",
        {"content": message, "msg_type": 0, "msg_seq": sequence},
        {"Authorization": f"QQBot {access_token}"},
    )
    if not ok: return False, f"{detail} {response}"
    if response.get("code") not in (None, 0, "0") or response.get("message") and not response.get("id"):
        return False, f"QQ 业务拒绝 code={response.get('code')} message={response.get('message','')}"
    return True, f"accepted: id={response.get('id') or response.get('message_id') or '--'}"


def _wechat_headers(bot_token: str) -> dict[str, str]:
    return wechat_common_headers(bot_token)


def _send_wechat_ilink(env: dict[str, str], message: str) -> tuple[bool, str]:
    """Submit one iLink message and report only Tencent-side acceptance.

    The iLink API offers no end-device/read receipt.  A `ret=0` response means
    only that Tencent accepted the request, never that the recipient's WeChat
    client displayed it.  Callers must therefore not label this as delivered.
    """
    token = env.get("R20_WECHAT_BOT_TOKEN", "")
    user_id = env.get("R20_WECHAT_USER_ID", "")
    context_token = env.get("R20_WECHAT_CONTEXT_TOKEN", "")
    try: base_url = validate_wechat_base_url(env.get("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com"))
    except ValueError as exc: return False, f"微信 Base URL 无效：{exc}"
    if not token or not user_id or not context_token:
        return False, "微信 Bot Token / 用户 ID / Context Token 未完整配置"
    client_id = f"r20-wechat-{uuid.uuid4()}"
    payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": user_id,
            "client_id": client_id,
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
    response = response if isinstance(response, dict) else {}
    ret, errcode = response.get("ret", 0), response.get("errcode", 0)
    if ret not in (0, None) or errcode not in (0, None):
        code = ret if ret not in (0, None) else errcode
        errmsg = str(response.get("errmsg", ""))
        if code == -14:
            return False, "微信 Bot Token 已失效；请重新扫码绑定"
        if code == -2 and errmsg.lower() == "unknown error":
            try:
                from r20_backend.wechat_watcher import mark_context_stale
                mark_context_stale(f"ret={ret} errcode={errcode} errmsg={errmsg}")
            except Exception:
                pass
            return False, "微信会话 Context Token 已失效并已清除；请向 Bot 发送一条新文字消息，系统将自动刷新会话"
        if code == -2:
            return False, f"微信 iLink 发送受限或会话失效 ret={ret} errcode={errcode} errmsg={errmsg or '--'}；请稍后重试，若持续失败请向 Bot 发一条新文字消息"
        return False, f"微信业务拒绝 ret={ret} errcode={errcode} errmsg={errmsg}"
    return True, f"腾讯 iLink 已受理（非客户端送达回执）client_id={client_id} {detail} ret={ret} errcode={errcode}"


def enabled_channels(env: dict[str, str] | None = None) -> list[str]:
    env = env or _env()
    channels = []
    for channel in ("webhook", "wechat", "wechat_ilink", "telegram", "qq"):
        if env.get(f"R20_NOTIFY_{channel.upper()}_ENABLED") == "1":
            channels.append(channel)
    return channels


def diagnose_channel(channel: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Configuration-only diagnosis. It never sends a user-visible message."""
    env = env or _env(); required = {
        "webhook": ("R20_NOTIFICATION_WEBHOOK",), "wechat": ("R20_WECHAT_WEBHOOK",),
        "wechat_ilink": ("R20_WECHAT_BOT_TOKEN","R20_WECHAT_USER_ID","R20_WECHAT_CONTEXT_TOKEN"),
        "telegram": ("R20_TELEGRAM_BOT_TOKEN","R20_TELEGRAM_CHAT_ID"), "qq": ("R20_QQ_APP_ID","R20_QQ_CLIENT_SECRET","R20_QQ_OPENID"),
    }
    if channel not in required: return {"status":"failed","detail":"未知通知通道"}
    missing=[key for key in required[channel] if not env.get(key)]
    if missing: return {"status":"incomplete","missing":missing,"detail":"配置不完整"}
    if channel == "wechat_ilink":
        return {"status":"ready","detail":"必要配置完整；仅能确认腾讯 iLink 受理，无法确认微信客户端送达"}
    return {"status":"ready","detail":"必要配置完整；尚未发送测试消息"}


def send_channel(channel: str, message: str, env: dict[str, str] | None = None) -> tuple[bool, str]:
    env = env or _env()
    if channel == "webhook":
        url = env.get("R20_NOTIFICATION_WEBHOOK", "")
        if not url:
            return False, "通用 Webhook URL 未配置"
        try: url = validate_outbound_url(url)
        except ValueError as exc: return False, f"通用 Webhook URL 无效：{exc}"
        ok, detail, response = _post_json(url, {"source": "R20 Quantum Trader", "message": message})
        if not ok: return False, f"{detail} {response}"
        if isinstance(response, dict) and response.get("success") is False: return False, f"Webhook 业务拒绝：{response}"
        return True, f"accepted: {detail}"
    if channel == "wechat":
        url = env.get("R20_WECHAT_WEBHOOK", "")
        if not url:
            return False, "企业微信 Webhook 未配置"
        try: url = validate_outbound_url(url, allowed_hosts={"qyapi.weixin.qq.com"})
        except ValueError as exc: return False, f"企业微信 Webhook 无效：{exc}"
        ok, detail, response = _post_json(url, {"msgtype": "text", "text": {"content": message}})
        if not ok: return False, f"{detail} {response}"
        if int(response.get("errcode", -1)) != 0: return False, f"企业微信业务拒绝 errcode={response.get('errcode')} errmsg={response.get('errmsg','')}"
        return True, f"accepted: HTTP 200 errcode=0"
    if channel == "wechat_ilink":
        return _send_wechat_ilink(env, message)
    if channel == "telegram":
        token, chat_id = env.get("R20_TELEGRAM_BOT_TOKEN", ""), env.get("R20_TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            return False, "Telegram Bot Token / Chat ID 未完整配置"
        ok, detail, response = _post_json(f"https://api.telegram.org/bot{urllib.parse.quote(token, safe='')}/sendMessage", {"chat_id": chat_id, "text": message})
        if not ok: return False, f"{detail} {response}"
        if response.get("ok") is not True: return False, f"Telegram 业务拒绝：{response.get('description') or response}"
        return True, f"accepted: message_id={((response.get('result') or {}).get('message_id',''))}"
    if channel == "qq":
        return _send_qq(env, message)
    return False, f"未知通知通道：{channel}"


def notify(text: str) -> dict[str, str]:
    env = _env(); timestamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    message = f"【R20 Quantum Trader】{timestamp}\n{text.strip()}"; result: dict[str, str] = {}
    for channel in enabled_channels(env):
        ok, detail = send_channel(channel, message, env)
        result[channel] = f"accepted: {detail}" if ok else f"failed: {detail}"
    return result


def send_qq_message(text: str) -> bool:
    """Compatibility symbol retained for existing strategy scripts."""
    return any(value.startswith("accepted:") for value in notify(text).values())


def test_channel(channel: str) -> dict[str, str]:
    """Strictly test only the selected channel; another channel cannot mask failure."""
    env = _env()
    timestamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    ok, detail = send_channel(channel, f"【R20 Quantum Trader】{timestamp}\n🔔 {channel.upper()} 通知测试：指定通道连接正常。", env)
    prefix = "accepted:" if ok else "failed:"
    return {channel: f"{prefix} {detail}"}
