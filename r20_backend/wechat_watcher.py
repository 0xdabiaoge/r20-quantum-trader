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
    return {**values, **os.environ}


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
    uin = base64.b64encode(str(secrets.randbelow(0xFFFFFFFF)).encode()).decode()
    body = json.dumps({"get_updates_buf": cursor, "base_info": {"channel_version": "1.0.2"}}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/ilink/bot/getupdates",
        data=body,
        headers={
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": uin,
            "Authorization": f"Bearer {token}",
            "User-Agent": "R20-Standalone/5.4.2",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _run() -> None:
    state = _load_state()
    while not _stop.is_set():
        env = _env()
        token = env.get("R20_WECHAT_BOT_TOKEN", "")
        base_url = env.get("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com")
        if not token:
            state.update({"status": "waiting_for_binding", "cursor": ""})
            _save_state(state)
            _stop.wait(3)
            continue
        try:
            payload = _poll(token, base_url, str(state.get("cursor", "")))
            state["cursor"] = payload.get("get_updates_buf") or state.get("cursor", "")
            state["status"] = "listening"
            for message in payload.get("msgs") or payload.get("messages") or []:
                context_token = message.get("context_token") or message.get("contextToken") or ""
                user_id = message.get("from_user_id") or message.get("fromUserId") or ""
                if context_token and user_id and str(user_id).endswith("@im.wechat"):
                    update_env({"R20_WECHAT_USER_ID": user_id, "R20_WECHAT_CONTEXT_TOKEN": context_token})
                    state["last_message_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    state["user_configured"] = True
            _save_state(state)
        except Exception as exc:
            state["status"] = f"retrying: {type(exc).__name__}"
            _save_state(state)
            _stop.wait(3)


def reset_watcher_state() -> None:
    _save_state({"cursor": "", "status": "binding_updated", "last_message_at": "", "user_configured": False})


def start_watcher() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, name="r20-wechat-session-watcher", daemon=True)
    _thread.start()


def stop_watcher() -> None:
    _stop.set()
