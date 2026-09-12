"""Multi-venue routing & atomic risk reservation manager."""
from __future__ import annotations
import datetime
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from r20_backend.exchanges import registry as venue_registry
from r20_backend.exchanges import routing_policy
from r20_backend import venue_router, risk_reservation
from scripts.okx_runtime import current_environment

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
VENUE_HEALTH_FILE = DATA_DIR / "venue_health.json"
AI_DECISION_CACHE_FILE = DATA_DIR / "ai_brain_decisions.json"
PORTFOLIO_RISK_BUDGET_ENV = "R20_PORTFOLIO_RISK_BUDGET_USDT"
VENUE_HEALTH_MAX_AGE_S = 300.0
MAKER_FEE_RATE = 0.0002


def portfolio_risk_budget_usdt() -> float:
    try:
        return max(0.0, float(os.getenv(PORTFOLIO_RISK_BUDGET_ENV, "") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def load_preferred_venue() -> str:
    return routing_policy.load_preferred_venue()


def load_routing_mode() -> str:
    return routing_policy.load_routing_mode()


def venue_execution_ready(venue: str, environment: str) -> bool:
    key = str(venue or "").strip().lower()
    try:
        if not venue_registry.is_registered(key):
            return False
        if key == "okx":
            env = current_environment()
            return bool(env.configured) and str(env.mode) == str(environment)
        return bool(venue_registry.execution_open(key, environment))
    except Exception as exc:
        print(f"[选所路由] warn 场所 {key} 能力表读取失败，按不可执行处理: {exc}")
        return False


def fetch_other_venue_positions(environment: str) -> Tuple[bool, Dict[str, List[Dict[str, Any]]], str]:
    snapshot: Dict[str, List[Dict[str, Any]]] = {}
    try:
        names = list(venue_registry.registered_venues())
    except Exception as exc:
        return False, {}, f"registry 场所清单不可用: {exc}"
    for name in names:
        if name == "okx":
            continue
        if not venue_execution_ready(name, environment):
            continue
        try:
            ad = venue_registry.get_adapter(name)
            rows = ad.positions() or []
            live = [p for p in rows if abs(float(p.get("size_signed") or 0)) > 1e-12]
            snapshot[name] = live
            for p in live:
                print(f"[跨所封顶] {name} {p.get('inst_id')} {p.get('side')} "
                      f"size={p.get('size_signed')} 纳入本周期仓位配额（只计数不处置）")
        except Exception as exc:
            return False, {}, f"{name} 持仓读取失败: {exc}"
    return True, snapshot, ""


def _venue_health_stamp() -> Tuple[Optional[str], Dict[str, Any]]:
    try:
        with open(VENUE_HEALTH_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle) or {}
        venues = raw.get("venues") if isinstance(raw.get("venues"), dict) else {}
        stamp = str(raw.get("updated_utc") or "").strip()
        if stamp:
            stamp = stamp.replace(" ", "T")
            if not stamp.endswith("Z"):
                stamp += "Z"
            return stamp, venues
    except Exception:
        pass
    return None, {}


def build_venue_candidates(inst_id: str, environment: str) -> List[Dict[str, Any]]:
    observed_stamp, venues = _venue_health_stamp()
    live_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cands: List[Dict[str, Any]] = []
    try:
        names = list(venue_registry.registered_venues())
    except Exception as exc:
        print(f"[选所路由] warn registry 场所清单不可用，回退 OKX 单候选: {exc}")
        names = ["okx"]
    for name in names:
        observed = venues.get(name) if isinstance(venues.get(name), dict) else {}
        latency = [float(v) for v in (observed.get("latency_ms") or {}).values()
                   if isinstance(v, (int, float))]
        avg_latency = sum(latency) / len(latency) if latency else 0.0
        pref = load_preferred_venue()
        if name == "okx" or (pref != "auto" and name == pref and venue_execution_ready(name, environment)):
            stamp = live_stamp
        elif observed:
            stamp = observed_stamp
        else:
            stamp = None
        eff_fee = (MAKER_FEE_RATE * 0.5) if name == "gate" else MAKER_FEE_RATE
        eff_stab = max(0.0, min(5.0, (avg_latency - 300.0) / 100.0)) if avg_latency > 0 else 0.0

        cands.append({
            "venue": name,
            "environment": environment,
            "executable": venue_execution_ready(name, environment),
            "fee_rate": eff_fee,
            "spread_bps": 0.0,
            "depth_usd": 0.0,
            "funding_rate": 0.0,
            "stability_penalty": eff_stab,
            "min_notional": 0.0,
            "min_qty": 0.0,
            "precision": 0.0,
            "health_updated_utc": stamp,
            "health_max_age_s": VENUE_HEALTH_MAX_AGE_S,
            "price": 0.0,
            "current_venue": name == "okx",
        })
    return cands


def reservation_manager():
    budget = portfolio_risk_budget_usdt()
    return risk_reservation.get_manager(
        db_path=risk_reservation.DEFAULT_DB_PATH,
        total_limit_usdt=budget if budget > 0 else None)


def estimate_margin_usdt(notional_usdt: float, margin_usdt: float = 0.0) -> float:
    if margin_usdt and float(margin_usdt) > 0:
        return round(float(margin_usdt), 4)
    notional = max(0.0, float(notional_usdt or 0.0))
    return round(notional / 3.0, 4)


def _decision_payload(decision, preferred: str) -> Dict[str, Any]:
    return {
        "preferred_venue": preferred,
        "venue": decision.venue,
        "reason_code": decision.reason_code,
        "reasons": list(decision.reasons or []),
        "rejected": [dict(r) for r in (decision.rejected or [])],
        "hysteresis_applied": bool(decision.hysteresis_applied),
        "allocation": decision.allocation,
        "decided_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def persist_venue_decision(inst_id: str, venue_decision: Dict[str, Any]) -> bool:
    try:
        with open(AI_DECISION_CACHE_FILE, "r", encoding="utf-8") as handle:
            cache = json.load(handle)
        if not isinstance(cache, dict) or not isinstance(cache.get(inst_id), dict):
            print(f"[选所证据] warn {inst_id} 不在决策缓存中，本轮证据不落盘")
            return False
        cache[inst_id]["venue_decision"] = venue_decision
        fd, tmp_path = tempfile.mkstemp(prefix=".venue-decision-", suffix=".tmp",
                                        dir=os.path.dirname(AI_DECISION_CACHE_FILE))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(cache, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, AI_DECISION_CACHE_FILE)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        return True
    except Exception as exc:
        print(f"[选所证据] warn 落盘失败（不影响本轮交易）: {exc}")
        return False


def _rejection_focus_reason(decision, candidates: List[Dict[str, Any]], preferred: str) -> str:
    wanted = [preferred] if preferred != "auto" else []
    wanted += [str(c.get("venue")) for c in candidates if c.get("current_venue")]
    wanted += [str(c.get("venue")) for c in candidates]
    rows = list(decision.rejected or [])
    for venue in wanted:
        same = [r for r in rows if str(r.get("venue")) == venue]
        if not same:
            continue
        substantive = [r for r in same if r.get("stage") != "executable"]
        return str((substantive or same)[0].get("reason") or "")
    return str((rows[0] if rows else {}).get("reason") or "无候选所")


def route_and_reserve_signal(inst_id: str, side: str, size: float, price: float,
                             notional_usdt: float = 0.0, margin_usdt: float = 0.0,
                             intent_id: str = "") -> Dict[str, Any]:
    env = current_environment()
    environment = str(env.mode)
    preferred = load_preferred_venue()
    notional = float(notional_usdt or 0.0) or max(0.0, float(size) * float(price))
    margin_est = estimate_margin_usdt(notional, margin_usdt)
    signal = {
        "inst_id": inst_id,
        "symbol_canonical": str(inst_id).split("-")[0].upper(),
        "side": "long" if str(side).lower() in ("buy", "long") else "short",
        "size_usdt": notional,
        "price": float(price or 0.0),
    }
    candidates = build_venue_candidates(inst_id, environment)

    if preferred != "auto":
        candidates = [c for c in candidates if str(c.get("venue")) == preferred]
        if not candidates:
            print(f"[选所路由] warn 手选场所 {preferred} 未在 registry 登记，按不可执行候选处理")
            candidates = [{
                "venue": preferred,
                "environment": environment,
                "executable": False,
                "health_updated_utc": None,
                "current_venue": False,
            }]

    budget_total = portfolio_risk_budget_usdt()
    try:
        mgr = reservation_manager()
        budget_used = mgr.gross_exposure(environment) if budget_total > 0 else 0.0
    except Exception as exc:
        mgr = None
        budget_used = 0.0
        print(f"[预算预留] warn 预留层不可用，本轮不下单（fail-closed）: {exc}")

    r_mode = load_routing_mode()
    cfg = venue_router.RouterConfig(
        routing_mode=r_mode,
        split_enabled=(r_mode == "split"))
    decision = venue_router.route_signal(signal, candidates, None, cfg)
    payload = _decision_payload(decision, preferred)
    persist_venue_decision(inst_id, payload)

    if not decision.ok or not decision.venue:
        focus = _rejection_focus_reason(decision, candidates, preferred)
        err = f"选所路由淘汰（{decision.reason_code}）：{focus}"
        print(f"[选所路由] {inst_id} {err}")
        return {"ok": False, "error": err, "venue": None, "decision": payload,
                "reservation": None}

    selected = decision.venue
    print(f"[选所路由] {inst_id} 中选场所={selected}（模式={r_mode}，原因={decision.reasons}）")

    if not mgr:
        err = "预算预留管理器不可用（fail-closed 拒绝开仓）"
        print(f"[预算预留] {inst_id} {err}")
        return {"ok": False, "error": err, "venue": selected, "decision": payload,
                "reservation": None}

    if not intent_id:
        intent_id = f"sig:{inst_id}:{int(time.time()*1000)}"
    base_sym = str(inst_id).split("-")[0].upper()

    res = mgr.reserve(
        venue=selected,
        environment=environment,
        symbol=base_sym,
        side=signal["side"],
        amount_usdt=margin_est,
        intent_id=intent_id,
        ttl_seconds=risk_reservation.DEFAULT_RESERVATION_TTL_SECONDS,
    )
    if not res.ok:
        err = f"组合风险预算预留被拒（{res.reason_code}）：{res.reason}"
        print(f"[预算预留] {inst_id} {err}")
        return {"ok": False, "error": err, "venue": selected, "decision": payload,
                "reservation": None}

    print(f"[预算预留] {inst_id} 成功预留保证金={margin_est:.2f}U "
          f"（场所={selected}，id={res.reservation_id}，总占用={res.gross_exposure_after:.2f}U）")
    res_dict = {
        "id": res.reservation_id,
        "venue": selected,
        "environment": environment,
        "symbol": base_sym,
        "side": signal["side"],
        "amount_usdt": margin_est,
        "intent_id": intent_id,
        "notional_usdt": notional,
    }
    return {"ok": True, "error": None, "venue": selected, "decision": payload,
            "reservation": res_dict}


def release_signal_reservation(reservation: Dict[str, Any], reason: str = "") -> None:
    if not reservation or not reservation.get("id"):
        return
    res_id = str(reservation["id"])
    venue = str(reservation.get("venue") or "")
    inst = str(reservation.get("symbol") or "")
    try:
        mgr = reservation_manager()
        ok = mgr.release(res_id, reason=reason or "signal_rejected_or_aborted")
        print(f"[预算释放] id={res_id} venue={venue} symbol={inst} "
              f"ok={ok} 原因={reason or '未指明'}")
    except Exception as exc:
        print(f"[预算释放] warn id={res_id} 释放异常（可能已过期/已释放）: {exc}")


def _utc_age_seconds(ts_str: str, now_utc: float) -> float:
    try:
        clean = str(ts_str or "").strip().replace("Z", "")
        if "T" in clean:
            dt = datetime.datetime.fromisoformat(clean)
        else:
            dt = datetime.datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
        ts = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
        return max(0.0, now_utc - ts)
    except Exception:
        return 999999.0


def reconcile_reservation_ledger(real_pos_dict: Dict[str, Any],
                                 pending_orders: List[Dict[str, Any]] = None,
                                 now_utc: float = None) -> Dict[str, int]:
    try:
        mgr = reservation_manager()
    except Exception as exc:
        print(f"[预留对账] warn 管理器不可用: {exc}")
        return {"active": 0, "released": 0, "retained": 0, "orphaned": 0}

    now = float(now_utc if now_utc is not None else time.time())
    active_rows = mgr.list_active()
    pending = pending_orders if pending_orders is not None else []
    released = 0
    retained = 0
    orphaned = 0

    for r in active_rows:
        res_id = str(r["id"])
        sym = str(r.get("symbol") or "").upper()
        venue = str(r.get("venue") or "").lower()
        side = str(r.get("side") or "").lower()
        has_pos = False
        inst_key = f"{sym}-USDT-SWAP"
        pos = real_pos_dict.get(inst_key) if isinstance(real_pos_dict, dict) else None
        if pos:
            p_side = str(pos.get("posSide", pos.get("side", ""))).lower()
            if p_side == side and float(pos.get("pos", 0) or 0) > 0:
                has_pos = True

        has_order = False
        for o in pending:
            o_inst = str(o.get("instId", "")).upper()
            if sym not in o_inst:
                continue
            o_side = str(o.get("posSide", o.get("side", ""))).lower()
            if o_side == side:
                has_order = True
                break

        age_s = _utc_age_seconds(r.get("created_utc", ""), now)

        if has_pos or has_order:
            retained += 1
            continue

        if age_s >= risk_reservation.DEFAULT_RESERVATION_TTL_SECONDS:
            orphaned += 1
            reason = f"对账发现孤儿且超 TTL ({age_s:.0f}s >= {risk_reservation.DEFAULT_RESERVATION_TTL_SECONDS}s)：无持仓无挂单"
            mgr.release(res_id, reason=reason)
            released += 1
            print(f"[预留对账] 释放孤儿预留 id={res_id} {venue} {sym} {side} (耗时 {age_s:.1f}s)")
        else:
            retained += 1

    return {"active": len(active_rows), "released": released,
            "retained": retained, "orphaned": orphaned}
