"""Standalone control plane: read-only monitoring plus process health."""
from __future__ import annotations
import base64
import hashlib
import hmac
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from r20_backend.config import refresh_settings, settings
from r20_backend.okx_client import OKXClient
from r20_backend.settings_store import mask, update_env
from r20_backend.notifications import test_channel
from r20_backend.audit import recent as recent_audit, record as audit_record
from r20_backend.schedule_store import load_schedule, save_schedule
from r20_backend.wechat_login import create_qrcode, latest_session, qrcode_status
from r20_backend.wechat_watcher import public_state as wechat_watcher_state, reset_watcher_state, start_watcher, stop_watcher
from r20_gateway.publisher import DB_PATH as GATEWAY_DB_PATH
from r20_gateway.store import GatewayStore
from r20_gateway.supervisor import start_supervisor as start_gateway_supervisor, stop_supervisor as stop_gateway_supervisor
from scripts.instrument_pool import from_okx_instrument, load_instruments, save_instruments

PROMPT_OVERRIDE_FILE = DATA_DIR / "system_prompt_override.txt"
BACKUP_LOG_FILE = ROOT / "logs" / "r20_backup_manual.log"
STARTED_AT = time.time()

@asynccontextmanager
async def lifespan(_: FastAPI):
    start_watcher()
    start_gateway_supervisor()
    yield
    stop_gateway_supervisor()
    stop_watcher()


app = FastAPI(title="R20 Quantum Trader Standalone Backend", version="5.4.2", lifespan=lifespan)
okx = OKXClient()
ADMIN_HTML = ROOT / "r20_backend" / "admin.html"


class AdminConfigUpdate(BaseModel):
    okx_api_key: str | None = None
    okx_secret_key: str | None = None
    okx_passphrase: str | None = None
    okx_simulated: bool | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_reasoning_effort: str | None = Field(default=None, pattern=r"^(low|medium|high)$")
    notification_webhook: str | None = None
    admin_token: str | None = None
    manual_close_enabled: bool | None = None


class InstrumentAddRequest(BaseModel):
    inst_id: str = Field(pattern=r"^[A-Z0-9]{2,15}-USDT-SWAP$")


class InstrumentDeleteRequest(BaseModel):
    confirmation: str


class ManualCloseRequest(BaseModel):
    inst_id: str = Field(pattern=r"^[A-Z0-9]+-USDT-SWAP$")
    position_side: str = Field(pattern=r"^(long|short)$")
    admin_token: str
    confirmation: str


class UpdateRequest(BaseModel):
    confirmation: str


class PromptOverrideRequest(BaseModel):
    content: str = Field(max_length=12000)


class NotificationConfigUpdate(BaseModel):
    webhook_enabled: bool = False
    webhook_url: str = ""
    wechat_enabled: bool = False
    wechat_webhook: str = ""
    wechat_ilink_enabled: bool = False
    wechat_bot_token: str | None = None
    wechat_base_url: str = "https://ilinkai.weixin.qq.com"
    wechat_user_id: str = ""
    wechat_context_token: str | None = None
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str = ""
    qq_enabled: bool = False
    qq_app_id: str = ""
    qq_client_secret: str | None = None
    qq_openid: str = ""


class NotificationTestRequest(BaseModel):
    channel: str = Field(pattern=r"^(webhook|wechat|wechat_ilink|telegram|qq)$")


class NotificationScheduleUpdate(BaseModel):
    briefing_times: list[str] = Field(min_length=1, max_length=6)


class WechatQrStatusRequest(BaseModel):
    qrcode: str = Field(min_length=1, max_length=500)


class BackupRequest(BaseModel):
    confirmation: str


def require_admin_token(token: str) -> None:
    expected = settings.admin_token or settings.setup_token
    if not expected:
        raise HTTPException(status_code=503, detail="后台尚未设置 R20_SETUP_TOKEN 或 R20_ADMIN_TOKEN")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="管理员令牌无效")


def require_admin_header(x_r20_admin_token: str | None) -> None:
    require_admin_token(x_r20_admin_token or "")


def read_json(filename: str, default: Any) -> Any:
    path = DATA_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def script_state(script_name: str) -> dict[str, Any]:
    path = SCRIPTS_DIR / script_name
    return {"name": script_name, "exists": path.exists(), "path": str(path)}


def file_health(filename: str, expected_interval: int) -> dict[str, Any]:
    path = DATA_DIR / filename
    if not path.exists():
        return {"name": filename, "exists": False, "age_seconds": None, "fresh": False}
    age = max(0, int(time.time() - path.stat().st_mtime))
    return {"name": filename, "exists": True, "age_seconds": age, "fresh": age <= expected_interval * 2, "bytes": path.stat().st_size}


def log_tail(filename: str, lines: int = 30) -> str:
    path = ROOT / "logs" / filename
    if not path.exists():
        return "暂无日志"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(lines, 200)):])


def decision_summary() -> list[dict[str, Any]]:
    raw = read_json("ai_brain_decisions.json", {})
    result = []
    for inst_id, item in raw.items():
        decision = item.get("decision", {}) if isinstance(item, dict) else {}
        result.append({
            "instId": inst_id,
            "action": decision.get("action", "WAIT"),
            "confidence": decision.get("confidence", 0),
            "summary": decision.get("summary_reason", ""),
            "updated_at": item.get("time_str", "") if isinstance(item, dict) else "",
        })
    return result


def runtime_overview() -> dict[str, Any]:
    health_files = [
        file_health("ai_brain_decisions.json", 15 * 60),
        file_health("factor_library_snapshot.json", 60),
        file_health("news_sentiment.json", 10 * 60),
        file_health("trading_ledger.json", 15 * 60),
    ]
    positions_payload = read_json("position_trackers.json", {})
    return {
        "service": {"version": "5.4.2", "pid": os.getpid(), "uptime_seconds": int(time.time() - STARTED_AT)},
        "credentials": {"okx": bool(settings.okx_api_key and settings.okx_secret_key and settings.okx_passphrase), "llm": bool(settings.llm_api_key)},
        "data_health": health_files,
        "decisions": decision_summary(),
        "trackers": len(positions_payload) if isinstance(positions_payload, dict) else 0,
        "logs": {
            "trader": log_tail("ai_factor_trader.log", 18),
            "backend": log_tail("r20_backend.log", 18),
            "scheduler": log_tail("r20_scheduler.log", 18),
        },
        "audit": recent_audit(20),
    }


def git(command: list[str]) -> str:
    result = subprocess.run(["git", *command], cwd=ROOT, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def update_status() -> dict[str, Any]:
    try:
        local = git(["rev-parse", "--short", "HEAD"])
        branch = git(["branch", "--show-current"])
        dirty = bool(git(["status", "--porcelain"]))
        remote = ""
        behind = ahead = 0
        try:
            git(["fetch", "--quiet", "origin", branch])
            remote = git(["rev-parse", "--short", f"origin/{branch}"])
            ahead, behind = [int(item) for item in git(["rev-list", "--left-right", "--count", f"HEAD...origin/{branch}"]).split()]
        except RuntimeError:
            pass
        return {"branch": branch, "local": local, "remote": remote, "behind": behind, "ahead": ahead, "dirty": dirty}
    except RuntimeError as exc:
        return {"error": str(exc)}



@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(ADMIN_HTML)


@app.get("/api/v1/admin/overview")
def admin_overview(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    return runtime_overview()


@app.get("/api/v1/admin/audit")
def admin_audit(x_r20_admin_token: str | None = Header(default=None), limit: int = 50) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    return {"records": recent_audit(limit)}


@app.get("/api/v1/admin/gateway")
def gateway_status(x_r20_admin_token: str | None = Header(default=None), limit: int = 50) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    store = GatewayStore(GATEWAY_DB_PATH)
    pid_file = DATA_DIR / "r20_gateway.pid"
    pid = int(pid_file.read_text().strip()) if pid_file.exists() and pid_file.read_text().strip().isdigit() else 0
    running = False
    if pid:
        try:
            os.kill(pid, 0)
            running = True
        except OSError:
            pass
    return {"version": "0.1.0", "running": running, "pid": pid or None, "stats": store.stats(), "deliveries": store.recent(limit)}


@app.get("/api/v1/admin/config")
def admin_config(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    return {
        "configuration": {
            "OKX API Key": "已设置" if settings.okx_api_key else "未设置",
            "OKX Secret Key": "已设置" if settings.okx_secret_key else "未设置",
            "OKX Passphrase": "已设置" if settings.okx_passphrase else "未设置",
            "LLM API Key": "已设置" if settings.llm_api_key else "未设置",
            "管理员令牌": "已设置" if settings.admin_token else "使用首次引导令牌",
            "通知 Webhook": "已设置" if settings.notification_webhook else "未设置",
            "手动平仓": "已启用" if settings.manual_close_enabled else "已禁用",
        },
        "editable": {
            "okx_simulated": settings.okx_simulated,
            "llm_base_url": settings.llm_base_url,
            "llm_model": settings.llm_model,
            "llm_reasoning_effort": settings.llm_reasoning_effort,
            "notification_webhook": settings.notification_webhook,
            "manual_close_enabled": settings.manual_close_enabled,
        },
    }


@app.put("/api/v1/admin/config")
def update_admin_config(payload: AdminConfigUpdate, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    data = payload.model_dump(exclude_none=True)
    if "llm_base_url" in data and data["llm_base_url"] and not data["llm_base_url"].startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="LLM Base URL 必须以 http:// 或 https:// 开头")
    if "notification_webhook" in data and data["notification_webhook"] and not data["notification_webhook"].startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="Webhook 必须以 http:// 或 https:// 开头")
    env_values = {
        "OKX_API_KEY": data.get("okx_api_key"),
        "OKX_SECRET_KEY": data.get("okx_secret_key"),
        "OKX_PASSPHRASE": data.get("okx_passphrase"),
        "OKX_IS_SIMULATED": "1" if data.get("okx_simulated") else "0" if "okx_simulated" in data else None,
        "LLM_BASE_URL": data.get("llm_base_url"),
        "LLM_API_KEY": data.get("llm_api_key"),
        "LLM_MODEL": data.get("llm_model"),
        "LLM_REASONING_EFFORT": data.get("llm_reasoning_effort"),
        "R20_NOTIFICATION_WEBHOOK": data.get("notification_webhook"),
        "R20_ADMIN_TOKEN": data.get("admin_token"),
        "R20_MANUAL_CLOSE_ENABLED": "1" if data.get("manual_close_enabled") else "0" if "manual_close_enabled" in data else None,
    }
    update_env(env_values)
    audit_record("config.update", "success", {"fields": sorted(data.keys())})
    return {
        "updated": True,
        "restart_note": "Long-running strategy processes read updated .env on their next execution cycle.",
        "manual_close_enabled": settings.manual_close_enabled,
    }


@app.post("/api/v1/admin/positions/close")
def manual_close_position(payload: ManualCloseRequest) -> dict[str, Any]:
    if not settings.manual_close_enabled:
        raise HTTPException(status_code=403, detail="后台手动平仓功能未启用")
    require_admin_token(payload.admin_token)
    expected_confirmation = f"CLOSE {payload.inst_id} {payload.position_side.upper()}"
    if payload.confirmation.strip().upper() != expected_confirmation:
        raise HTTPException(status_code=400, detail=f"确认短语必须精确为：{expected_confirmation}")
    if not settings.okx_api_key or not settings.okx_secret_key or not settings.okx_passphrase:
        raise HTTPException(status_code=503, detail="OKX API 凭证未完整配置")
    try:
        result = okx.close_position(payload.inst_id, payload.position_side)
        audit_record("position.close", "accepted", {"instId": payload.inst_id, "side": payload.position_side})
        return {"accepted": True, "instId": payload.inst_id, "positionSide": payload.position_side, "result": result}
    except Exception as exc:
        audit_record("position.close", "failed", {"instId": payload.inst_id, "side": payload.position_side, "error": str(exc)[:300]})
        raise HTTPException(status_code=502, detail=f"OKX 平仓请求失败：{exc}") from exc


@app.get("/api/v1/admin/instruments")
def admin_instruments(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    trackers = read_json("position_trackers.json", {})
    active = set(trackers.keys()) if isinstance(trackers, dict) else set()
    return {
        "instruments": [{**item, "protected": item["instId"] == "BTC-USDT-SWAP", "has_tracker": item["instId"] in active or item["name"] in active} for item in load_instruments()],
        "limits": {"minimum": 1, "maximum": 6, "btc_required": True},
    }


@app.post("/api/v1/admin/instruments")
def add_admin_instrument(payload: InstrumentAddRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    inst_id = payload.inst_id.upper()
    current = load_instruments()
    if any(item["instId"] == inst_id for item in current):
        raise HTTPException(status_code=409, detail="该币种已在交易池中")
    if len(current) >= 6:
        raise HTTPException(status_code=409, detail="交易池最多允许 6 个币种；请先删除一个无持仓币种")
    try:
        matches = okx.instruments("SWAP", inst_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OKX 合约校验失败：{exc}") from exc
    raw = matches[0] if matches else {}
    if raw.get("instId") != inst_id or raw.get("settleCcy") != "USDT" or raw.get("state") != "live":
        raise HTTPException(status_code=400, detail="仅允许添加 OKX 在线可交易的 USDT 永续合约")
    item = from_okx_instrument(raw)
    save_instruments([*current, item])
    audit_record("instrument.add", "success", {"instId": inst_id})
    return {"added": item, "count": len(current) + 1, "effective": "next_process_cycle"}


@app.delete("/api/v1/admin/instruments/{inst_id}")
def delete_admin_instrument(inst_id: str, payload: InstrumentDeleteRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    inst_id = inst_id.upper()
    if payload.confirmation.strip().upper() != f"REMOVE {inst_id}":
        raise HTTPException(status_code=400, detail=f"确认短语必须精确为：REMOVE {inst_id}")
    if inst_id == "BTC-USDT-SWAP":
        raise HTTPException(status_code=403, detail="BTC 是全局黑天鹅哨兵基准，不允许从交易池删除")
    current = load_instruments()
    if len(current) <= 1:
        raise HTTPException(status_code=409, detail="交易池至少保留 1 个币种")
    if not any(item["instId"] == inst_id for item in current):
        raise HTTPException(status_code=404, detail="该币种不在交易池中")
    trackers = read_json("position_trackers.json", {})
    coin = inst_id.split("-", 1)[0]
    if isinstance(trackers, dict) and (inst_id in trackers or coin in trackers):
        raise HTTPException(status_code=409, detail="该币种存在持仓追踪记录，为防止失去风控接管，禁止删除")
    updated = [item for item in current if item["instId"] != inst_id]
    save_instruments(updated)
    audit_record("instrument.remove", "success", {"instId": inst_id})
    return {"removed": inst_id, "count": len(updated), "effective": "next_process_cycle"}


@app.get("/api/v1/admin/update-status")
def admin_update_status(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    return update_status()


@app.post("/api/v1/admin/update")
def update_application(payload: UpdateRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    if payload.confirmation.strip().upper() != "UPDATE R20":
        raise HTTPException(status_code=400, detail="确认短语必须精确为：UPDATE R20")
    status_before = update_status()
    if status_before.get("error"):
        raise HTTPException(status_code=502, detail=status_before["error"])
    if status_before["dirty"]:
        raise HTTPException(status_code=409, detail="工作区存在未提交修改；为防止覆盖本地改动，后台拒绝更新")
    if not status_before["remote"]:
        raise HTTPException(status_code=502, detail="无法读取远程仓库状态")
    try:
        output = git(["pull", "--ff-only", "origin", status_before["branch"]])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"更新失败：{exc}") from exc
    status_after = update_status()
    audit_record("application.update", "success", {"before": status_before.get("local"), "after": status_after.get("local")})
    return {
        "updated": status_before["local"] != status_after.get("local"),
        "before": status_before,
        "after": status_after,
        "git_output": output,
        "restart_required": True,
        "restart_note": "请重启 r20-quantum 与 r20-scheduler 服务，让新代码接管后台与调度。",
    }


@app.get("/api/v1/admin/prompts")
def prompt_override(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    from scripts.ai_brain_trader import SYSTEM_PROMPT
    content = PROMPT_OVERRIDE_FILE.read_text(encoding="utf-8") if PROMPT_OVERRIDE_FILE.exists() else ""
    effective = SYSTEM_PROMPT if not content.strip() else f"{SYSTEM_PROMPT}\n\n【管理员提示词覆盖层（同样必须遵守上述风控和 JSON 约束）】\n{content.strip()}"
    return {
        "content": content,
        "enabled": bool(content.strip()),
        "base_prompt": SYSTEM_PROMPT,
        "effective_prompt": effective,
        "path": str(PROMPT_OVERRIDE_FILE),
    }


@app.put("/api/v1/admin/prompts")
def update_prompt_override(payload: PromptOverrideRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    content = payload.content.strip()
    if content:
        temp = PROMPT_OVERRIDE_FILE.with_suffix(".tmp")
        temp.write_text(content + "\n", encoding="utf-8")
        os.replace(temp, PROMPT_OVERRIDE_FILE)
    elif PROMPT_OVERRIDE_FILE.exists():
        PROMPT_OVERRIDE_FILE.unlink()
    audit_record("prompt.update", "success", {"enabled": bool(content), "characters": len(content)})
    return {"saved": True, "enabled": bool(content), "restart_note": "下一次 AI 推演循环将自动叠加此提示词覆盖层。"}


@app.get("/api/v1/admin/notifications")
def notification_config(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    return {
        "webhook": {"enabled": os.getenv("R20_NOTIFY_WEBHOOK_ENABLED", "0") == "1", "url": settings.notification_webhook},
        "wechat": {"enabled": os.getenv("R20_NOTIFY_WECHAT_ENABLED", "0") == "1", "webhook": os.getenv("R20_WECHAT_WEBHOOK", "")},
        "wechat_ilink": {
            "enabled": os.getenv("R20_NOTIFY_WECHAT_ILINK_ENABLED", "0") == "1",
            "bot_token": mask(os.getenv("R20_WECHAT_BOT_TOKEN", "")),
            "bot_configured": bool(os.getenv("R20_WECHAT_BOT_TOKEN", "")),
            "base_url": os.getenv("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com"),
            "user_id": os.getenv("R20_WECHAT_USER_ID", ""),
            "context_token": mask(os.getenv("R20_WECHAT_CONTEXT_TOKEN", "")),
            "context_configured": bool(os.getenv("R20_WECHAT_CONTEXT_TOKEN", "")),
            "ready": bool(os.getenv("R20_WECHAT_BOT_TOKEN", "") and os.getenv("R20_WECHAT_USER_ID", "") and os.getenv("R20_WECHAT_CONTEXT_TOKEN", "")),
            "watcher": wechat_watcher_state(),
            "protocol": "Tencent iLink 2.4.8",
        },
        "telegram": {"enabled": os.getenv("R20_NOTIFY_TELEGRAM_ENABLED", "0") == "1", "bot_token": mask(os.getenv("R20_TELEGRAM_BOT_TOKEN", "")), "chat_id": os.getenv("R20_TELEGRAM_CHAT_ID", "")},
        "qq": {
            "enabled": os.getenv("R20_NOTIFY_QQ_ENABLED", "0") == "1",
            "app_id": os.getenv("R20_QQ_APP_ID", ""),
            "client_secret": mask(os.getenv("R20_QQ_CLIENT_SECRET", "")),
            "openid": os.getenv("R20_QQ_OPENID", ""),
        },
    }


@app.put("/api/v1/admin/notifications")
def update_notification_config(payload: NotificationConfigUpdate, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    for value, title in ((payload.webhook_url, "通用 Webhook"), (payload.wechat_webhook, "企业微信 Webhook")):
        if value and not value.startswith(("https://", "http://")):
            raise HTTPException(status_code=400, detail=f"{title} 必须以 http:// 或 https:// 开头")
    update_env({
        "R20_NOTIFY_WEBHOOK_ENABLED": "1" if payload.webhook_enabled else "0",
        "R20_NOTIFICATION_WEBHOOK": payload.webhook_url,
        "R20_NOTIFY_WECHAT_ENABLED": "1" if payload.wechat_enabled else "0",
        "R20_WECHAT_WEBHOOK": payload.wechat_webhook,
        "R20_NOTIFY_WECHAT_ILINK_ENABLED": "1" if payload.wechat_ilink_enabled else "0",
        "R20_WECHAT_BOT_TOKEN": payload.wechat_bot_token,
        "R20_WECHAT_BASE_URL": payload.wechat_base_url,
        "R20_WECHAT_USER_ID": payload.wechat_user_id,
        "R20_WECHAT_CONTEXT_TOKEN": payload.wechat_context_token,
        "R20_NOTIFY_TELEGRAM_ENABLED": "1" if payload.telegram_enabled else "0",
        "R20_TELEGRAM_BOT_TOKEN": payload.telegram_bot_token,
        "R20_TELEGRAM_CHAT_ID": payload.telegram_chat_id,
        "R20_NOTIFY_QQ_ENABLED": "1" if payload.qq_enabled else "0",
        "R20_QQ_APP_ID": payload.qq_app_id,
        "R20_QQ_CLIENT_SECRET": payload.qq_client_secret,
        "R20_QQ_OPENID": payload.qq_openid,
    })
    audit_record("notifications.update", "success", {
        "webhook": payload.webhook_enabled,
        "wechat": payload.wechat_enabled,
        "wechat_ilink": payload.wechat_ilink_enabled,
        "telegram": payload.telegram_enabled,
        "qq": payload.qq_enabled,
    })
    return {"saved": True, "restart_note": "通知配置已写入 .env；下一轮脚本执行会读取新通道。"}


@app.post("/api/v1/admin/notifications/test")
def send_notification_test(payload: NotificationTestRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    result = test_channel(payload.channel)
    audit_record("notifications.test", "completed", {"channel": payload.channel, "result": result})
    return {"channel": payload.channel, "result": result}


@app.get("/api/v1/admin/notifications/schedule")
def notification_schedule(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    schedule = load_schedule()
    return {
        **schedule,
        "event_notifications": "开仓、平仓与风险事件实时推送，不受每日简报时间限制",
        "restart_note": "保存后调度器将在 60 秒内读取新时间，无需重启。",
    }


@app.put("/api/v1/admin/notifications/schedule")
def update_notification_schedule(payload: NotificationScheduleUpdate, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    normalized: list[str] = []
    for value in payload.briefing_times:
        value = value.strip()
        try:
            parsed = time.strptime(value, "%H:%M")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效时间：{value}；必须使用 HH:MM 24 小时格式") from exc
        canonical = f"{parsed.tm_hour:02d}:{parsed.tm_min:02d}"
        if canonical not in normalized:
            normalized.append(canonical)
    normalized.sort()
    schedule = load_schedule()
    schedule["briefing_times"] = normalized
    save_schedule(schedule)
    audit_record("notifications.schedule", "success", {"briefing_times": normalized, "timezone": "Asia/Shanghai"})
    return {**schedule, "saved": True, "restart_note": "调度器将在 60 秒内读取新时间。"}


@app.post("/api/v1/admin/notifications/wechat/qr")
def create_wechat_qr(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    base_url = os.getenv("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com")
    try:
        result = create_qrcode(base_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取微信登录二维码失败：{exc}") from exc
    audit_record("wechat.qr.create", "success", {})
    try:
        import qrcode as qr_library
        image = qr_library.make(result["image_content"])
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_data = base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"二维码渲染失败：{exc}") from exc
    return {"qrcode": result["qrcode"], "image_data": f"data:image/png;base64,{image_data}", "expires_hint": result["expires_hint"]}


@app.post("/api/v1/admin/notifications/wechat/qr/status")
def check_wechat_qr(payload: WechatQrStatusRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    base_url = os.getenv("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com")
    try:
        result = qrcode_status(payload.qrcode, base_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"查询微信扫码状态失败：{exc}") from exc
    if result["status"] == "confirmed" and result["bot_token"]:
        update_env({
            "R20_WECHAT_BOT_TOKEN": result["bot_token"],
            "R20_WECHAT_BASE_URL": result["base_url"],
            "R20_WECHAT_USER_ID": result["user_id"] or None,
            "R20_WECHAT_CONTEXT_TOKEN": "",
            "R20_NOTIFY_WECHAT_ILINK_ENABLED": "1",
        })
        reset_watcher_state()
        audit_record("wechat.qr.confirm", "success", {"bot_id": result["bot_id"], "user_id_configured": bool(result["user_id"])})
        return {"status": "confirmed", "configured": True, "bot_id": result["bot_id"], "user_id": result["user_id"], "context_required": True}
    return {"status": result["status"], "configured": False}


@app.post("/api/v1/admin/notifications/wechat/session")
def sync_wechat_session(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    bot_token = os.getenv("R20_WECHAT_BOT_TOKEN", "")
    base_url = os.getenv("R20_WECHAT_BASE_URL", "https://ilinkai.weixin.qq.com")
    if not bot_token:
        raise HTTPException(status_code=409, detail="请先完成微信扫码绑定")
    try:
        result = latest_session(bot_token, base_url)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    update_env({"R20_WECHAT_USER_ID": result["user_id"], "R20_WECHAT_CONTEXT_TOKEN": result["context_token"]})
    audit_record("wechat.session.sync", "success", {"user_id": result["user_id"]})
    return {"synced": True, "user_id": result["user_id"], "context_configured": True}


@app.get("/api/v1/admin/backups")
def backup_status(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    backups_dir = ROOT / "backups"
    local_archives = [{"name": item.name, "bytes": item.stat().st_size, "mtime": int(item.stat().st_mtime)} for item in backups_dir.glob("*.tar.gz")] if backups_dir.exists() else []
    return {
        "schedule": "每天北京时间 02:00，上传百度网盘成功后自动删除本地压缩包",
        "script": str(SCRIPTS_DIR / "nightly_backup_and_clean.py"),
        "local_archives": sorted(local_archives, key=lambda item: item["mtime"], reverse=True),
        "last_log": BACKUP_LOG_FILE.read_text(encoding="utf-8")[-4000:] if BACKUP_LOG_FILE.exists() else "尚无后台手动灾备日志",
    }


@app.post("/api/v1/admin/backups/run")
def run_backup(payload: BackupRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    if payload.confirmation.strip().upper() != "BACKUP R20":
        raise HTTPException(status_code=400, detail="确认短语必须精确为：BACKUP R20")
    script = SCRIPTS_DIR / "nightly_backup_and_clean.py"
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, text=True, capture_output=True, timeout=600)
    BACKUP_LOG_FILE.parent.mkdir(exist_ok=True)
    BACKUP_LOG_FILE.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        audit_record("backup.run", "failed", {"returncode": result.returncode})
        raise HTTPException(status_code=502, detail=f"灾备任务失败：{result.stderr[-800:] or result.stdout[-800:]}")
    audit_record("backup.run", "success", {})
    return {"completed": True, "output": result.stdout[-2500:]}


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {
        "service": "r20-standalone-backend",
        "version": "5.4.2",
        "status": "ok",
        "timestamp": int(time.time()),
        "credentials": {
            "okx_configured": bool(settings.okx_api_key and settings.okx_secret_key and settings.okx_passphrase),
            "llm_configured": bool(settings.llm_api_key),
            "simulated_trading": settings.okx_simulated,
        },
    }


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    return {
        "version": "5.4.2",
        "mode": "read_only_control_plane",
        "scripts": [
            script_state("ai_factor_trader.py"),
            script_state("ai_brain_trader.py"),
            script_state("daemon_web_sync.py"),
            script_state("self_improvement_engine.py"),
            script_state("nightly_backup_and_clean.py"),
        ],
        "last_decisions": read_json("ai_brain_decisions.json", {}),
        "position_trackers": read_json("position_trackers.json", {}),
    }


@app.get("/api/v1/cache/{resource}")
def cache(resource: str) -> JSONResponse:
    allowed = {
        "decisions": "ai_brain_decisions.json",
        "factors": "factor_library_snapshot.json",
        "ledger": "trading_ledger.json",
        "sentiment": "news_sentiment.json",
        "self-improvement": "self_improvement_report.json",
    }
    filename = allowed.get(resource)
    if not filename:
        raise HTTPException(status_code=404, detail="unknown cache resource")
    return JSONResponse(read_json(filename, {} if resource != "ledger" else []))


@app.get("/api/v1/market/{inst_id}")
def market(inst_id: str) -> dict[str, Any]:
    if not inst_id.endswith("-SWAP"):
        raise HTTPException(status_code=400, detail="only SWAP instrument ids are accepted")
    try:
        ticker = okx.ticker(inst_id)
        return {"instId": inst_id, "ticker": ticker[0] if ticker else {}, "source": "OKX REST"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OKX market request failed: {exc}") from exc


@app.get("/api/v1/account/positions")
def positions() -> dict[str, Any]:
    if not settings.okx_api_key:
        raise HTTPException(status_code=503, detail="OKX credentials are not configured in .env")
    try:
        return {"positions": okx.positions(), "source": "OKX REST"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OKX account request failed: {exc}") from exc


# Preserve the existing public dashboard and its relative-path API contract at /.
# Admin and /api/v1 routes above are evaluated before this catch-all mount.
from dashboard.app import app as dashboard_app
app.mount("/", dashboard_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
