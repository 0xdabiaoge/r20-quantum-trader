"""R20 notification fan-out with independently configurable delivery channels."""
from __future__ import annotations
import datetime
import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return {**values, **os.environ}


def _post_json(url: str, payload: dict[str, Any]) -> tuple[bool, str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "R20-Standalone/5.4.2"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300, f"HTTP {response.status}"
    except Exception as exc:
        return False, str(exc)


def notify(text: str) -> dict[str, str]:
    env = _env()
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    timestamp = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    message = f"【R20 Quantum Trader】{timestamp}\n{text.strip()}"
    result: dict[str, str] = {}

    if env.get("R20_NOTIFY_WEBHOOK_ENABLED") == "1" and env.get("R20_NOTIFICATION_WEBHOOK"):
        ok, detail = _post_json(env["R20_NOTIFICATION_WEBHOOK"], {"source": "R20 Quantum Trader", "timestamp": timestamp, "message": message})
        result["webhook"] = "sent" if ok else f"failed: {detail}"

    if env.get("R20_NOTIFY_WECHAT_ENABLED") == "1" and env.get("R20_WECHAT_WEBHOOK"):
        ok, detail = _post_json(env["R20_WECHAT_WEBHOOK"], {"msgtype": "text", "text": {"content": message}})
        result["wechat"] = "sent" if ok else f"failed: {detail}"

    if env.get("R20_NOTIFY_TELEGRAM_ENABLED") == "1" and env.get("R20_TELEGRAM_BOT_TOKEN") and env.get("R20_TELEGRAM_CHAT_ID"):
        token = urllib.parse.quote(env["R20_TELEGRAM_BOT_TOKEN"], safe="")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        ok, detail = _post_json(url, {"chat_id": env["R20_TELEGRAM_CHAT_ID"], "text": message})
        result["telegram"] = "sent" if ok else f"failed: {detail}"

    # Compatibility bridge: only enabled explicitly, so standalone installs need not have QwenPaw.
    if env.get("R20_NOTIFY_QQ_ENABLED") == "1":
        command = env.get("R20_QQ_BRIDGE_COMMAND", "")
        if not command:
            result["qq"] = "failed: QQ bridge command is not configured"
        else:
            try:
                completed = subprocess.run(command, input=message, shell=True, text=True, capture_output=True, timeout=20)
                result["qq"] = "sent" if completed.returncode == 0 else f"failed: {completed.stderr.strip() or completed.stdout.strip()}"
            except Exception as exc:
                result["qq"] = f"failed: {exc}"
    return result


def send_qq_message(text: str) -> bool:
    """Compatibility symbol retained for existing strategy and backup scripts."""
    result = notify(text)
    return any(value == "sent" for value in result.values())


def test_channel(channel: str) -> dict[str, str]:
    env = _env()
    key = f"R20_NOTIFY_{channel.upper()}_ENABLED"
    original = env.get(key, "0")
    os.environ[key] = "1"
    try:
        return notify(f"🔔 {channel.upper()} 通知测试：R20 独立后台连接正常。")
    finally:
        os.environ[key] = original
