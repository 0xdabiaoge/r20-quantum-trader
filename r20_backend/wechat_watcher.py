"""Persistent metadata-only iLink update watcher for proactive notifications."""
from __future__ import annotations
import base64
import json
import os
import secrets
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from r20_backend.config import ROOT
from r20_backend.settings_store import update_env
from r20_backend.wechat_protocol import base_info, common_headers
from r20_backend.net_security import validate_wechat_base_url

STATE_FILE = ROOT / "data" / "wechat_session_state.json"
_stop = threading.Event()
_thread: threading.Thread | None = None


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    try:
        from r20_gateway.secrets import load_secrets
        encrypted = load_secrets()
    except Exception: encrypted = {}
    return {**os.environ, **values, **encrypted}


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"cursor": "", "status": "starting", "last_message_at": "", "user_configured": False}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".wechat-session-", suffix=".tmp", dir=STATE_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, STATE_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def public_state() -> dict[str, Any]:
    state = _load_state()
    return {
        "status": state.get("status", "starting"),
        "last_message_at": state.get("last_message_at", ""),
        "user_configured": bool(state.get("user_configured")),
        "running": bool(_thread and _thread.is_alive()),
    }


def _poll(token: str, base_url: str, cursor: str) -> dict[str, Any]:
    body = json.dumps({"get_updates_buf": cursor, "base_info": base_info()}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/ilink/bot/getupdates",
        data=body,
        headers={"User-Agent": "R20-Standalone/5.4.2", **common_headers(token)},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _notify_lifecycle(token: str, base_url: str, action: str) -> None:
    body = json.dumps({"base_info": base_info()}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/ilink/bot/msg/notify{action}",
        data=body,
        headers={"User-Agent": "R20-Standalone/5.4.2", **common_headers(token)},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")
    if payload.get("ret", 0) not in (0, None):
        raise RuntimeError(f"notify{action} ret={payload.get('ret')}")


def _run() -> None:
    state = _load_state()
    active_token_fingerprint = ""
    while not _stop.is_set():
        env = _env()
        token = env.get("R20_WECHAT_BOT_TOKEN", "")
        token_fingerprint = __import__("hashlib").sha256(token.encode()).hexdigest()[:12] if token else ""
        if token_fingerprint != active_token_fingerprint:
            state.update({"cursor": "", "status": "binding_updated" if token else "waiting_for_binding", "user_configured": False, "token_fingerprint": token_fingerprint})
            active_token_fingerprint = token_fingerprint
            _save_state(state)
        try: base_url = validate_wechat_base_url(env.get("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com"))
        except ValueError:
            state["status"] = "invalid_base_url"; _save_state(state); _stop.wait(3); continue
        if env.get("R20_WECHAT_CONTEXT_TOKEN") and env.get("R20_WECHAT_USER_ID"):
            state["user_configured"] = True
        if not token:
            state.update({"status": "waiting_for_binding", "cursor": ""})
            _save_state(state)
            _stop.wait(3)
            continue
        try:
            payload = _poll(token, base_url, str(state.get("cursor", "")))
            ret = payload.get("ret", 0)
            errcode = payload.get("errcode", 0)
            if ret not in (0, None) or errcode not in (0, None):
                if ret == -14 or errcode == -14:
                    state.update({"status": "token_stale_relogin_required", "cursor": ""})
                    _save_state(state)
                    _stop.wait(3)
                    continue
                raise RuntimeError(f"getupdates ret={ret} errcode={errcode}")
            state["cursor"] = payload.get("get_updates_buf") or state.get("cursor", "")
            state["status"] = "listening"
            for message in payload.get("msgs") or payload.get("messages") or []:
                context_token = message.get("context_token") or message.get("contextToken") or ""
                user_id = message.get("from_user_id") or message.get("fromUserId") or ""
                if context_token and user_id and str(user_id).endswith("@im.wechat"):
                    from r20_gateway.secrets import save_secrets
                    from r20_backend.settings_store import remove_env
                    save_secrets({"R20_WECHAT_CONTEXT_TOKEN": context_token})
                    remove_env({"R20_WECHAT_CONTEXT_TOKEN"})
                    update_env({"R20_WECHAT_USER_ID": user_id})
                    state["last_message_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    state["user_configured"] = True
            _save_state(state)
        except Exception as exc:
            state["status"] = f"retrying: {type(exc).__name__}"
            _save_state(state)
            _stop.wait(3)


def reset_watcher_state() -> None:
    _save_state({"cursor": "", "status": "binding_updated", "last_message_at": "", "user_configured": False})
    stop_watcher(); start_watcher()


def request_session_capture() -> dict[str, Any]:
    """Ask the single watcher to capture the next user message instead of competing getupdates calls."""
    state = _load_state()
    state["status"] = "waiting_for_user_message"
    state["user_configured"] = False
    _save_state(state)
    return public_state()


def start_watcher() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    env = _env()
    if env.get("R20_WECHAT_BOT_TOKEN"):
        try:
            _notify_lifecycle(env["R20_WECHAT_BOT_TOKEN"], env.get("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com"), "start")
        except Exception:
            pass
    _stop.clear()
    _thread = threading.Thread(target=_run, name="r20-wechat-session-watcher", daemon=True)
    _thread.start()


def stop_watcher() -> None:
    global _thread
    _stop.set()
    if _thread and _thread.is_alive() and _thread is not threading.current_thread(): _thread.join(timeout=6)
    if _thread and not _thread.is_alive(): _thread = None
    env = _env()
    if env.get("R20_WECHAT_BOT_TOKEN"):
        try:
            _notify_lifecycle(env["R20_WECHAT_BOT_TOKEN"], env.get("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com"), "stop")
        except Exception:
            pass
