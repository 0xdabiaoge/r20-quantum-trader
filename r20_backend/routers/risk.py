"""Risk constants, instrument pool, baseline capital, and position close routes."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Body, Header, HTTPException

from r20_backend.config import settings, refresh_settings
from r20_backend.settings_store import update_env, remove_env
from r20_backend.account_baseline import update_initial_capital
from r20_backend.audit import record as audit_record
from r20_backend import risk_config
from r20_backend.dependencies import (
    DATA_DIR, MAX_POOL_SIZE, MIN_POOL_SIZE, REQUEST_SESSION,
    app_attr, admin_auth, okx, read_json, require_admin_header, require_superadmin,
)
from r20_backend.schemas import (
    RiskConfigUpdate,
    RiskResetRequest,
    InitialCapitalUpdate,
    InstrumentAddRequest,
    InstrumentDeleteRequest,
    ManualCloseRequest,
)
from r20_backend.okx_trade_service import fast_close_confirmed
from scripts.okx_rest import OKXNotConfigured
from scripts.instrument_pool import from_okx_instrument, load_instruments, save_instruments

router = APIRouter(tags=["risk"])


@router.get("/api/v1/admin/risk")
def admin_risk_get(x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_session=x_r20_session)
    return {
        "schema": risk_config.schema(),
        "suites": risk_config.SUITES,
        "values": risk_config.current_values(),
        "effect": "交易引擎每 15 分钟一个巡检周期；子进程启动时重新读取 .env，保存后下一周期自动生效，无需重启后台。",
    }


@router.post("/api/v1/admin/risk")
def admin_risk_update(payload: RiskConfigUpdate, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_superadmin(x_r20_session)
    merged: dict[str, Any] = {}
    if payload.suite_id:
        try:
            merged.update(risk_config.suite_values(payload.suite_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    merged.update(payload.values)
    if not merged:
        raise HTTPException(status_code=400, detail="没有需要保存的修改")
    before = risk_config.current_values()
    try:
        env_updates = risk_config.normalize(merged)
    except ValueError as exc:
        audit_record("risk.config.update", "failed", {"actor": actor["username"], "suite": payload.suite_id, "reason": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    update_env(env_updates)
    refresh_settings()
    audit_record("risk.config.update", "success", {
        "actor": actor["username"],
        "suite": payload.suite_id or None,
        "changed": {k: {"before": before.get(k), "after": float(v)} for k, v in env_updates.items()},
    })
    return {
        "updated": sorted(env_updates.keys()),
        "applied_suite": payload.suite_id or None,
        "values": risk_config.current_values(),
        "effect": "已写入 .env；下一交易巡检周期（≤15 分钟）起对新开仓/加仓/时间止损全面生效，AI 主脑提示词中的风控口径同步对齐。",
    }


@router.post("/api/v1/admin/risk/reset")
def admin_risk_reset(payload: RiskResetRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    actor = require_superadmin(x_r20_session)
    if payload.confirmation.strip().upper() != "RESET RISK":
        raise HTTPException(status_code=400, detail="确认短语必须精确为：RESET RISK")
    remove_env(set(risk_config.reset_keys()))
    refresh_settings()
    audit_record("risk.config.reset", "success", {"actor": actor["username"]})
    return {
        "reset": True,
        "values": risk_config.current_values(),
        "effect": "全部自定义风控覆盖值已清除，执行层回退到代码默认基线。",
    }


@router.put("/api/v1/admin/account-baseline")
def admin_update_account_baseline(payload: InitialCapitalUpdate, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if payload.confirmation.strip().upper() != "UPDATE CAPITAL":
        raise HTTPException(status_code=400, detail="确认短语必须精确为：UPDATE CAPITAL")
    try:
        fn_update = app_attr("update_initial_capital", update_initial_capital)
        result = fn_update(payload.initial_capital)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rec_audit = app_attr("audit_record", audit_record)
    rec_audit("account.baseline.update", "success", {
        "actor": actor["username"],
        "previous_initial_capital": result["previous_initial_capital"],
        "initial_capital": result["initial_capital"],
        "reset_time_preserved": result["reset_time"],
    })
    return {
        "updated": True,
        **result,
        "effect": "主页累计盈亏、累计 ROI 与权益基准线将按新本金重算；历史起算时间保持不变。",
    }


@router.get("/api/v1/admin/instruments")
def admin_instruments(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    trackers = read_json("position_trackers.json", {})
    active = set(trackers.keys()) if isinstance(trackers, dict) else set()
    return {
        "instruments": [{**item, "protected": item["instId"] == "BTC-USDT-SWAP", "has_tracker": item["instId"] in active or item["name"] in active} for item in load_instruments()],
        "limits": {"minimum": MIN_POOL_SIZE, "maximum": MAX_POOL_SIZE, "btc_required": True},
    }


@router.post("/api/v1/admin/instruments")
def add_admin_instrument(payload: InstrumentAddRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    inst_id = payload.inst_id.upper()
    current = load_instruments()
    if any(item["instId"] == inst_id for item in current):
        raise HTTPException(status_code=409, detail="该币种已在交易池中")
    if len(current) >= MAX_POOL_SIZE:
        raise HTTPException(status_code=409, detail=f"交易池最多允许 {MAX_POOL_SIZE} 个币种；请先删除一个无持仓币种，或调整环境变量 R20_MAX_POOL_SIZE")
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
    return {"added": item, "count": len(current) + 1, "effective": "immediate", "message": f"{item['name']} 已成功加入交易池并实时同步全网大屏与因果雷达"}


@router.delete("/api/v1/admin/instruments/{inst_id}")
def delete_admin_instrument(
    inst_id: str,
    payload: InstrumentDeleteRequest | None = Body(default=None),
    confirmation: str | None = None,
    x_r20_admin_token: str | None = Header(default=None),
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session")
) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    inst_id = inst_id.upper()
    conf = ((payload.confirmation if payload else None) or confirmation or "").strip().upper()
    if conf and conf != f"REMOVE {inst_id}":
        raise HTTPException(status_code=400, detail=f"确认短语必须精确为：REMOVE {inst_id}")
    if inst_id == "BTC-USDT-SWAP":
        raise HTTPException(status_code=403, detail="BTC 是全局黑天鹅哨兵基准，不允许从交易池删除")
    current = load_instruments()
    if len(current) <= MIN_POOL_SIZE:
        raise HTTPException(status_code=409, detail=f"交易池至少保留 {MIN_POOL_SIZE} 个币种")
    if not any(item["instId"] == inst_id for item in current):
        raise HTTPException(status_code=404, detail="该币种不在交易池中")
    trackers = read_json("position_trackers.json", {})
    coin = inst_id.split("-", 1)[0]
    if isinstance(trackers, dict) and (inst_id in trackers or coin in trackers):
        raise HTTPException(status_code=409, detail="该币种存在持仓追踪记录，为防止失去风控接管，禁止删除")
    updated = [item for item in current if item["instId"] != inst_id]
    save_instruments(updated)
    audit_record("instrument.remove", "success", {"instId": inst_id})
    return {"removed": inst_id, "count": len(updated), "effective": "immediate", "message": f"{inst_id} 已从交易池移除并实时同步全网大屏与因果雷达"}


@router.post("/api/v1/admin/positions/close")
def manual_close_position(payload: ManualCloseRequest) -> dict[str, Any]:
    actor = require_superadmin(REQUEST_SESSION.get())
    refresh_settings()
    from scripts.okx_runtime import current_environment
    _close_env = current_environment()
    _close_venue = str(getattr(payload, "venue", "") or "okx").strip().lower()
    if _close_venue not in ("okx", "binance", "gate"):
        raise HTTPException(status_code=400, detail=f"不支持的平仓场所：{_close_venue}")
    if _close_venue == "okx" and not _close_env.configured:
        raise HTTPException(status_code=503, detail=f"OKX {_close_env.mode.upper()} 静态 API Key 未配置（系统 NOT READY）：V5 直签是唯一私有通道，禁止后台手动平仓；请先在「账户接入」补齐完整三件套")
    if not settings.manual_close_enabled:
        raise HTTPException(status_code=403, detail="后台手动平仓功能未启用")
    import fcntl
    lock_path = DATA_DIR / ".ai_factor_trader.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    from r20_backend.dependencies import get_auth_store
    auth_store = get_auth_store()
    if actor.get("role") == "legacy" or not auth_store.verify_password(int(actor["id"]), payload.admin_password):
        raise HTTPException(status_code=403, detail="管理员密码验证失败")
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HTTPException(status_code=409, detail="交易主循环正在执行，暂不允许后台快速平仓；请等待本周期结束")
        try:
            if _close_venue == "okx":
                result = fast_close_confirmed(payload.close_token, payload.confirmation)
            else:
                from r20_backend.close_intent import venue_fast_close
                result = venue_fast_close(_close_venue, _close_env.mode, payload.close_token, payload.confirmation)
            audit_record("position.close", "confirmed_closed", {"instId": result.get("instId"), "side": result.get("posSide"), "venue": _close_venue, "environment": result.get("environment"), "size": result.get("closed_size"), "actor": actor.get("username", "admin")})
            return result
        except OKXNotConfigured as exc:
            audit_record("position.close", "rejected_not_ready", {"venue": _close_venue, "error": str(exc)[:300], "actor": actor.get("username", "admin")})
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            audit_record("position.close", "rejected", {"venue": _close_venue, "error": str(exc)[:300], "actor": actor.get("username", "admin")})
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            audit_record("position.close", "verification_failed", {"venue": _close_venue, "error": str(exc)[:300], "actor": actor.get("username", "admin")})
            raise HTTPException(status_code=502, detail=f"{_close_venue.upper()} 快速平仓未完成确认：{exc}") from exc
        finally:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
