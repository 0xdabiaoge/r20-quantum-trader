"""Standalone control plane: read-only monitoring plus process health."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from r20_backend.config import refresh_settings, settings
from r20_backend.okx_client import OKXClient
from r20_backend.settings_store import mask, update_env

app = FastAPI(title="R20 Quantum Trader Standalone Backend", version="5.4.2")
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
    notification_webhook: str | None = None
    admin_token: str | None = None
    manual_close_enabled: bool | None = None


class ManualCloseRequest(BaseModel):
    inst_id: str = Field(pattern=r"^[A-Z0-9]+-USDT-SWAP$")
    position_side: str = Field(pattern=r"^(long|short)$")
    admin_token: str
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


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(ADMIN_HTML)


@app.get("/api/v1/admin/config")
def admin_config(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    return {
        "configuration": {
            "OKX API Key": mask(settings.okx_api_key),
            "OKX Secret Key": mask(settings.okx_secret_key),
            "OKX Passphrase": mask(settings.okx_passphrase),
            "LLM API Key": mask(settings.llm_api_key),
            "管理员令牌": "已设置" if settings.admin_token else "未设置",
            "通知 Webhook": mask(settings.notification_webhook),
            "手动平仓": "已启用" if settings.manual_close_enabled else "已禁用",
        },
        "editable": {
            "okx_simulated": settings.okx_simulated,
            "llm_base_url": settings.llm_base_url,
            "llm_model": settings.llm_model,
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
        "R20_NOTIFICATION_WEBHOOK": data.get("notification_webhook"),
        "R20_ADMIN_TOKEN": data.get("admin_token"),
        "R20_MANUAL_CLOSE_ENABLED": "1" if data.get("manual_close_enabled") else "0" if "manual_close_enabled" in data else None,
    }
    update_env(env_values)
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
        return {"accepted": True, "instId": payload.inst_id, "positionSide": payload.position_side, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OKX 平仓请求失败：{exc}") from exc


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
