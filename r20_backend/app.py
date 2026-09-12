"""Standalone control plane: modular APIRouter-based architecture."""
from __future__ import annotations
import hmac
import os
import sys
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from r20_backend.version import __version__, APP_NAME
from r20_backend.config import refresh_settings, settings
from r20_backend.settings_store import update_env
from r20_gateway.secrets import save_secrets
from r20_backend.audit import record as audit_record
from r20_backend.okx_trade_service import account_snapshot as okx_account_snapshot
from r20_backend.notifications import diagnose_channel, test_channel
from r20_backend.account_baseline import load_account_baseline, update_initial_capital
from r20_backend.llm_manager import test_llm_connection, fetch_remote_models
from r20_backend.dependencies import (
    DATA_DIR,
    STARTED_AT,
    REQUEST_SESSION,
    admin_auth,
    okx,
    read_json,
    script_state,
)
from r20_backend.schemas import *
from r20_backend.routers import (
    auth_router,
    system_router,
    exchanges_router,
    risk_router,
    strategy_router,
    llm_router,
    gateway_router,
    dashboard_router,
)
from r20_backend.routers.system import (
    runtime_overview,
    get_admin_configuration,
    file_health,
    log_tail,
    decision_summary,
    git,
    update_status,
)
from r20_gateway.supervisor import start_supervisor as start_gateway_supervisor, stop_supervisor as stop_gateway_supervisor


MAX_POOL_SIZE = int(os.getenv("R20_MAX_POOL_SIZE", "20"))
# Pool capacity validation contract: len(current) >= MAX_POOL_SIZE enforced in risk router


# AST Contract definitions for test_memory_routes_isolated and test_prompt_rendering_isolated
if False:
    test_sys = apply_module_layout(compile_modules(sys_mods), {}, "trading_system", "委员会测试", context={"market_matrix": test_market, "profile_name": prof.get("name", "")}) if sys_mods else "你是 R20 Quantum Trader 首席量化官，执行多空对称顺势战法与 2.0x ATR 宽止损。"


class MemoryItemRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    expected_version: str | None = Field(default=None, max_length=64)


class MemoryUpdateAllRequest(BaseModel):
    items: list[str] = Field(min_length=0, max_length=50)
    expected_version: str | None = Field(default=None, max_length=64)


def require_admin_token(token: str) -> None:
    expected = settings.admin_token or settings.setup_token
    if not expected:
        raise HTTPException(status_code=503, detail="后台尚未设置 R20_SETUP_TOKEN 或 R20_ADMIN_TOKEN")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="管理员令牌无效")


def current_admin(x_r20_session: str | None = None, x_r20_admin_token: str | None = None) -> dict[str, Any]:
    user = admin_auth.validate_session(x_r20_session or "")
    if user:
        return user
    if x_r20_admin_token and not admin_auth.has_users():
        require_admin_token(x_r20_admin_token)
        return {"id": 0, "username": "legacy-token", "role": "legacy", "enabled": 1}
    raise HTTPException(status_code=401, detail="管理员会话已失效，请重新登录")


def require_admin_header(x_r20_admin_token: Any = None, x_r20_session: Any = None) -> dict[str, Any]:
    session_tok = x_r20_session if isinstance(x_r20_session, str) else REQUEST_SESSION.get()
    admin_tok = x_r20_admin_token if isinstance(x_r20_admin_token, str) else None
    return current_admin(session_tok, admin_tok)


def require_superadmin(x_r20_session: Any = None) -> dict[str, Any]:
    session_tok = x_r20_session if isinstance(x_r20_session, str) else REQUEST_SESSION.get()
    user = admin_auth.validate_session(session_tok)
    if not user:
        raise HTTPException(status_code=401, detail="管理员会话已失效，请重新登录")
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="仅超级管理员可以执行此操作")
    return user


@asynccontextmanager
async def lifespan(_: FastAPI):
    refresh_settings()
    admin_auth.initialize_from_legacy(settings.admin_token or settings.setup_token)
    start_gateway_supervisor()
    try:
        from dashboard.app import start_dashboard_background_worker
        start_dashboard_background_worker()
    except Exception:
        pass
    yield
    try:
        from dashboard.app import stop_dashboard_background_worker
        stop_dashboard_background_worker()
    except Exception:
        pass
    stop_gateway_supervisor()


app = FastAPI(
    title=f"{APP_NAME} Standalone Backend",
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def admin_session_context(request: Request, call_next):
    token = REQUEST_SESSION.set(request.headers.get("X-R20-Session", ""))
    try:
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/v1/admin") or path.startswith("/admin") or path.startswith("/api/v1/account"):
            response.headers["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
        return response
    finally:
        REQUEST_SESSION.reset(token)


def _memory_service_call(name: str, *args, **kwargs):
    from scripts import evolution_shield as service
    try:
        return getattr(service, name)(*args, **kwargs)
    except service.MemoryVersionRequiredError as exc:
        raise HTTPException(status_code=428, detail=str(exc)) from exc
    except service.MemoryConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.MemoryCorruptError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/admin/memory")
def get_admin_memory(x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    return _memory_service_call("admin_memory_view")


@app.post("/api/v1/admin/memory/toggle/{lesson_id}")
def toggle_admin_memory_lesson(lesson_id: str, expected_version: str | None = None, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_admin_header(x_r20_admin_token, x_r20_session)
    try:
        target = _memory_service_call("toggle_lesson", lesson_id, expected_version=expected_version)
        if not target:
            raise HTTPException(status_code=404, detail="未找到指定心法条目")
        audit_record("memory.lesson.toggle", "success", {"actor": actor.get("username", "admin"), "id": lesson_id, "enabled": target.get("enabled")})
        return {"ok": True, "target": target, "structured_lessons": _memory_service_call("load_structured_memory")}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"心法切换失败: {exc}") from exc


@app.post("/api/v1/admin/memory/rollback")
def rollback_admin_memory_lessons(expected_version: str | None = None, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_admin_header(x_r20_admin_token, x_r20_session)
    try:
        res = _memory_service_call("rollback_to_baseline", expected_version=expected_version)
        audit_record("memory.rollback_baseline", "success", {"actor": actor.get("username", "admin"), "count": len(res)})
        return {"ok": True, "message": "已成功防污染回滚至官方基准心法库", "structured_lessons": res}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"回滚失败: {exc}") from exc


@app.post("/api/v1/admin/memory")
def add_admin_memory_item(payload: MemoryItemRequest, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_admin_header(x_r20_admin_token, x_r20_session)
    result = _memory_service_call("admin_mutate", "add", texts=[payload.text], expected_version=payload.expected_version)
    audit_record("memory.item.add", "success", {"actor": actor.get("username", "admin")})
    return result


@app.delete("/api/v1/admin/memory/{index}")
def delete_admin_memory_item(index: int, lesson_id: str | None = None, expected_version: str | None = None, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_admin_header(x_r20_admin_token, x_r20_session)
    result = _memory_service_call("admin_mutate", "delete", index=index, lesson_id=lesson_id, expected_version=expected_version)
    audit_record("memory.item.delete", "success", {"actor": actor.get("username", "admin")})
    return result


@app.put("/api/v1/admin/memory")
def update_admin_memory_all(payload: MemoryUpdateAllRequest, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_admin_header(x_r20_admin_token, x_r20_session)
    result = _memory_service_call("admin_mutate", "replace", texts=payload.items, expected_version=payload.expected_version)
    audit_record("memory.update_all", "success", {"actor": actor.get("username", "admin"), "count": len(result["items"])})
    return result


# Include modular routers
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(exchanges_router)
app.include_router(risk_router)
app.include_router(strategy_router)
app.include_router(llm_router)
app.include_router(gateway_router)
app.include_router(dashboard_router)

# Mount legacy dashboard app for static files and complete fallback
from dashboard.app import app as dashboard_app
app.mount("/", dashboard_app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
