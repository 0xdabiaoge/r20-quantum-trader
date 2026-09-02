"""QQ Bot one-click QR binding (official q.qq.com /lite protocol).

Implements the same wire flow as Tencent's official @tencent-connect/qqbot-connector:
  1. POST https://q.qq.com/lite/create_bind_task {"key": base64(32 random bytes)}
  2. user opens/scan https://q.qq.com/qqbot/openclaw/connect.html?task_id=...&_wv=2
  3. POST https://q.qq.com/lite/poll_bind_result {"task_id": ...}
  4. on status=2 the bot secret arrives AES-256-GCM encrypted with our ephemeral key;
     decrypt locally and persist AppID / Client Secret / user OpenID immediately.

Credentials are written only to the local encrypted secret store; plaintext is never
returned to the browser nor logged.
"""
from __future__ import annotations

import base64
import binascii
import json
import secrets
import threading
import time
import urllib.request
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

QQ_HOST = "q.qq.com"
BIND_STATUS = {"NONE": 0, "PENDING": 1, "COMPLETED": 2, "EXPIRED": 3}
TASK_TTL_SECONDS = 300
MAX_ACTIVE_TASKS = 3


class _BindTask:
    def __init__(self, task_id: str, key_b64: str, connect_url: str):
        self.task_id = task_id
        self.key_b64 = key_b64
        self.connect_url = connect_url
        self.created_at = time.time()
        self.status = "pending"  # pending | bound | expired | failed
        self.error = ""
        self.app_id = ""
        self.openid = ""
        self.last_poll = 0.0
        self.lock = threading.Lock()


_TASKS: dict[str, _BindTask] = {}
_TASKS_LOCK = threading.Lock()


def _post_qq(path: str, payload: dict[str, Any], timeout: int = 12) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://{QQ_HOST}{path}",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "R20-Standalone/6.1.0-preview"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw) if raw else {}
    if data.get("retcode") != 0:
        raise RuntimeError(str(data.get("msg") or "QQ 绑定接口返回异常"))
    return data.get("data") or {}


def _decrypt_secret(encrypt_secret_b64: str, key_b64: str) -> str:
    """AES-256-GCM with the 32-byte base64 key; layout: iv(12) || ciphertext || tag(16)."""
    try:
        key = base64.b64decode(key_b64)
        blob = base64.b64decode(encrypt_secret_b64)
        if len(key) != 32 or len(blob) < 28:
            raise ValueError("bad key/blob length")
        plain = AESGCM(key).decrypt(blob[:12], blob[12:], None)
        return plain.decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"QQ 密钥解密失败：{exc}") from exc


def _gc_tasks() -> None:
    now = time.time()
    stale = [tid for tid, task in _TASKS.items() if now - task.created_at > TASK_TTL_SECONDS + 60 or (task.status in {"bound", "failed"} and now - task.created_at > 120)]
    for tid in stale:
        _TASKS.pop(tid, None)


def create_bind_task(source: str = "R20 Quantum Trader") -> dict[str, Any]:
    with _TASKS_LOCK:
        _gc_tasks()
        active = [task for task in _TASKS.values() if task.status == "pending" and time.time() - task.created_at < TASK_TTL_SECONDS]
        if len(active) >= MAX_ACTIVE_TASKS:
            raise RuntimeError("已有 3 个进行中的绑定任务，请先完成或等待过期")
        key_b64 = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
        data = _post_qq("/lite/create_bind_task", {"key": key_b64})
        task_id = str(data.get("task_id") or "")
        if not task_id:
            raise RuntimeError("QQ 未返回 task_id")
        connect_url = f"https://{QQ_HOST}/qqbot/openclaw/connect.html?task_id={task_id}&source={source}&_wv=2"
        task = _BindTask(task_id, key_b64, connect_url)
        _TASKS[task_id] = task
    return {"task_id": task_id, "connect_url": connect_url, "expires_in": TASK_TTL_SECONDS}


def _public_view(task: _BindTask) -> dict[str, Any]:
    return {
        "status": task.status,
        "error": task.error,
        "app_id": task.app_id if task.status == "bound" else "",
        "openid": task.openid if task.status == "bound" else "",
        "expires_in": max(0, round(TASK_TTL_SECONDS - (time.time() - task.created_at))),
    }


def poll_bind_task(task_id: str) -> dict[str, Any]:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
    if not task:
        raise RuntimeError("绑定任务不存在或已过期，请重新生成二维码")
    with task.lock:
        if task.status in {"bound", "failed"}:
            return _public_view(task)
        if time.time() - task.created_at > TASK_TTL_SECONDS:
            task.status = "expired"
            return _public_view(task)
        # Rate-limit upstream polling to one request per second per task.
        if time.time() - task.last_poll < 1.0:
            return _public_view(task)
        task.last_poll = time.time()
        try:
            data = _post_qq("/lite/poll_bind_result", {"task_id": task_id})
        except Exception as exc:
            task.error = str(exc)[:200]
            return _public_view(task)
        status = int(data.get("status") or 0)
        if status == BIND_STATUS["COMPLETED"]:
            app_id = str(data.get("bot_appid") or "")
            encrypted = str(data.get("bot_encrypt_secret") or "")
            openid = str(data.get("user_openid") or "")
            if not app_id or not encrypted:
                task.status = "failed"
                task.error = "QQ 返回的绑定结果缺少 AppID 或密钥"
                return _public_view(task)
            try:
                client_secret = _decrypt_secret(encrypted, task.key_b64)
            except RuntimeError as exc:
                task.status = "failed"
                task.error = str(exc)
                return _public_view(task)
            try:
                _persist(app_id, client_secret, openid)
            except Exception as exc:
                task.status = "failed"
                task.error = f"凭证保存失败：{exc}"
                return _public_view(task)
            task.app_id = app_id
            task.openid = openid
            task.status = "bound"
        elif status == BIND_STATUS["EXPIRED"]:
            task.status = "expired"
        else:
            task.status = "pending"
        return _public_view(task)


def _persist(app_id: str, client_secret: str, openid: str) -> None:
    from r20_gateway.secrets import save_secrets
    from r20_backend.settings_store import update_env

    values = {"R20_QQ_CLIENT_SECRET": client_secret}
    if openid:
        values["R20_QQ_OPENID"] = openid
    save_secrets(values)
    update_env({"R20_QQ_APP_ID": app_id})
