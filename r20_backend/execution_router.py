"""统一执行路由：大模型标准决策 JSON → 场所原生受保护开仓（Gate/Binance 平权）。

铁律（与 OKX 遗留链路同源）：
1. 分发前物理校验不可绕过——数值有限、多空几何、R:R 底线复用 scripts.order_risk
   单一事实源（fail-closed）；
2. 开仓必须 100% 云端保护单覆盖：TP/SL 双腿挂成并回读验证才算成功，
   任一步失败 → 已挂触发单回滚 + 撤入场单，绝不留裸仓；
3. 场所执行开闸由 registry.execution_open 决定（Gate 默认关，需 R20_GATE_EXECUTION=1）；
4. 本模块不吞异常语义：路由结果 {ok, stage, detail} 供上层台账归因。

决策契约（与 ai_brain 输出同构，币种为裸资产名）：
    {"asset": "BTC", "action": "BUY_LONG"|"SELL_SHORT", "margin_usdt": 150.0,
     "leverage": 3, "entry_price": 79650.0, "take_profit_price": 82000.0,
     "stop_loss_price": 78500.0}
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

from .exchanges import (ExchangeCapabilityError, canonical_base, execution_open,
                        get_adapter, is_sandbox_environment, require_execution)

try:  # 单一事实源：几何 + R:R 底线（与执行层遗留链路同一把尺）
    from scripts.order_risk import validate_quote_geometry_and_rr
except ImportError:
    from order_risk import validate_quote_geometry_and_rr

try:  # 单一事实源：全局保证金闸门（审计 P0-1 前本模块 0 处引用 risk_constants）
    from scripts.risk_constants import MAX_MARGIN_EQUITY_RATIO, MAX_SINGLE_ASSET_MARGIN
except ImportError:  # pragma: no cover - scripts/ 在 sys.path 时走上面分支
    try:
        from risk_constants import MAX_MARGIN_EQUITY_RATIO, MAX_SINGLE_ASSET_MARGIN
    except ImportError:
        MAX_MARGIN_EQUITY_RATIO, MAX_SINGLE_ASSET_MARGIN = 0.20, 0.0


class RouteResult(Dict[str, Any]):
    """dict 子类型：{ok, venue, stage, detail, order_id, tp_id, sl_id, size_signed...}"""


def _fail(stage: str, detail: str, venue: str = "gate", **extra: Any) -> RouteResult:
    r = RouteResult(ok=False, venue=venue, stage=stage, detail=detail)
    r.update(extra)
    return r


def open_protected_position(decision: Dict[str, Any], *,
                            price_ref: Optional[float] = None,
                            trigger_expiration: int = 604800,
                            adapter: Any = None,
                            own_position: Optional[Dict[str, Any]] = None,
                            margin_mode: Optional[str] = None,
                            environment: Optional[str] = None,
                            max_margin_usdt: Optional[float] = None) -> RouteResult:
    """标准决策 → Gate/Binance 受保护开仓（US-005 多所对等）。全程 fail-closed：任何缺口先撤后抛。

    own_position：调用方（lab/trader）在该合约上的在管仓位记录（含 size_signed/side）；
    交易所既有仓与之一致视为己仓放行，否则视为外部连坐风险拒开（stage=precheck）。
    margin_mode：由账户实况推导传入（cross/isolated）；缺省维持历史行为 cross。
    environment：显式资金环境（demo/live），优先使用；缺省读 decision.get('environment')。
    max_margin_usdt：调用方按权益算出的单笔保证金硬顶（权益×R20_MAX_MARGIN_EQUITY_RATIO）；
    缺省 0/None = 不臆造占比上限，但仍强制单标的绝对封顶（审计 P0-1）。
    """
    env_name = str(environment or decision.get("environment") or "").strip().lower() or None
    venue = str(decision.get("venue") or getattr(getattr(adapter, "capabilities", None), "venue", "gate") or "gate").strip().lower()
    if env_name and is_sandbox_environment(env_name) and venue == "gate" and env_name != "sandbox":
        env_name = "sandbox"
    ad = adapter or get_adapter(venue, environment=env_name)
    asset = canonical_base(str(decision.get("asset") or decision.get("name") or ""))
    action = str(decision.get("action") or "").upper()
    if not asset:
        return _fail("validate", "决策缺少 asset/币种", venue=venue)
    try:
        margin = float(decision.get("margin_usdt") or 0)
        leverage = float(decision.get("leverage") or 0)
        entry = float(decision.get("entry_price") or 0)
        tp = float(decision.get("take_profit_price") or 0)
        sl = float(decision.get("stop_loss_price") or 0)
    except (TypeError, ValueError):
        return _fail("validate", "决策数值字段非法", venue=venue)
    for tag, v in (("margin", margin), ("leverage", leverage), ("entry", entry)):
        if not math.isfinite(v) or v <= 0:
            return _fail("validate", f"{tag} 必须为有限正数，收到 {v}", venue=venue)

    # ── 全局保证金闸门（审计 P0-1，2026-09-13）──────────────────────────────
    # 本模块曾把 decision["margin_usdt"] 原样 ×leverage 变成名义额（见下方 notional），
    # 即 LLM 报多少就用多少：OKX 路径的「可用余额占比硬顶 / 单标的绝对封顶」在多所
    # 路径完全不存在。现在双层兜底：调用方权益顶（缺失=0 → 不臆造）+ 单标的绝对封顶
    # （真实 .env 配置值，恒生效）。夹住后写回 decision，后续 notional/回读同源。
    margin_clamped_from = 0.0
    _margin_caps = [c for c in (float(MAX_SINGLE_ASSET_MARGIN or 0.0),
                                float(max_margin_usdt or decision.get("max_margin_usdt") or 0.0))
                    if math.isfinite(c) and c > 0]
    if _margin_caps and margin > min(_margin_caps):
        margin_clamped_from = round(margin, 4)
        margin = round(min(_margin_caps), 4)
        decision = {**decision, "margin_usdt": margin}
        print(f"[保证金闸门] {venue.upper()} {asset} 单笔保证金 {margin_clamped_from}U "
              f"超上限 {margin}U（权益占比 {MAX_MARGIN_EQUITY_RATIO:.0%} / 单标的封顶 "
              f"{float(MAX_SINGLE_ASSET_MARGIN or 0):.0f}U），已夹至上限")
    ok, reason, rr = validate_quote_geometry_and_rr(action, entry, tp, sl)
    if not ok:
        return _fail("risk_gate", f"物理风控拒绝: {reason}", venue=venue, rr=rr)

    # 执行开闸（默认关；env 显式打开且凭证就绪前一切免谈）
    require_execution(venue, environment=str(getattr(ad, "environment", "live") or "live"))

    # 环境维合约存在性对账（US-007 扩展）：下单前核对**本环境**合约
    # 目录——已下架/未上市在发送前拦截（fail-closed 拒开）；目录拉不到 →
    # fail-open 放行（对账是增强不是风控闸门，绝不阻塞交易）。
    try:
        from .exchanges.listing import ensure_contract_listed
        _check = ensure_contract_listed(
            venue, str(getattr(ad, "environment", "live") or "live"),
            ad.native_symbol(asset))
        if not _check.ok:
            return _fail("listing", f"合约对账拒绝: {_check.reason}", venue=venue)
    except Exception:  # 对账自身异常一律 fail-open（含目录缓存污染等未知面）
        pass

    spec = ad.fetch_instrument_spec(asset)
    if spec is None:
        return _fail("specs", f"{venue.upper()} 无法获取 {asset} 合约规格（下架或网络故障）", venue=venue)

    tick = float(spec.tick_size or 0.1) or 0.1

    def _q(px: float) -> float:
        import math as _m
        return round(round(px / tick) * tick, max(0, int(-_m.log10(tick)) + 1))

    entry, tp, sl = _q(entry), _q(tp), _q(sl)
    ref_price = float(price_ref or 0) or 0.0
    if ref_price <= 0:
        tick_data = ad.fetch_ticker(asset) or {}
        ref_price = float(tick_data.get("mark_price") or tick_data.get("last") or 0)
    if ref_price <= 0:
        return _fail("price", f"{venue.upper()} {asset} 现价不可得，禁止盲单", venue=venue)

    notional = margin * leverage
    contracts = ad.quote_qty_to_native(notional, ref_price, spec)
    if contracts <= 0:
        return _fail("sizing",
                     f"名义 {notional:.2f}U @ {ref_price:g} 不足 {venue.upper()} 最小下单量"
                     f"（每张面值 {spec.ct_val}）", venue=venue)
    side = "long" if action == "BUY_LONG" else "short"
    is_base_asset = getattr(ad.capabilities, "quantity_unit", "") == "base_asset"
    signed = contracts if (side == "long") else -contracts
    if not is_base_asset:
        signed = int(signed)
        contracts = int(contracts)

    # —— 外部持仓前置体检（US-009）：同合约存在来源不明/尺寸不符既有仓 = 连坐风险 ——
    try:
        existing = [p for p in ad.positions()
                    if str(p.get("base") or "").upper() == asset
                    and abs(float(p.get("size_signed") or 0)) > 1e-9]
    except ExchangeCapabilityError:
        raise
    except Exception as exc:
        return _fail("precheck", f"{asset} 既有持仓探针失败，无法排除外部仓，拒开: {exc}", venue=venue)
    for p in existing:
        ex_signed = float(p.get("size_signed") or 0)
        own_signed = float(own_position.get("size_signed") or 0) if own_position else None
        own_match = bool(own_position) and abs(ex_signed - (own_signed or 0)) < 1e-6 \
            and str(own_position.get("side") or "").lower() == str(p.get("side") or "").lower()
        if not own_match:
            return _fail("precheck",
                         f"{asset} 交易所存在非本系统在管既有仓 size_signed={ex_signed:g}({p.get('side')})"
                         + ("，与 lab 记录不符" if own_position else "，lab 无在管记录")
                         + "——外部仓连坐拒开", venue=venue, existing_size=ex_signed)

    # 杠杆档位（失败即止，未下单无风险）；margin_mode 由账户实况推导，缺省 cross
    try:
        ad.set_leverage(asset, leverage, margin_mode=margin_mode or "cross")
    except ExchangeCapabilityError:
        raise
    except Exception as exc:
        return _fail("leverage", f"设置杠杆失败: {exc}", venue=venue)

    # 入场限价单
    try:
        placed = ad.place_order(asset, side, abs(contracts), price=entry)
    except ExchangeCapabilityError:
        raise
    except Exception as exc:
        return _fail("entry", f"入场委托提交失败: {exc}", venue=venue)
    order_id = str(placed.get("id") or placed.get("order_id") or placed.get("text") or "")

    # 云端 TP/SL 双腿 + 回读验证；任何缺口撤入场单回滚
    legs: dict = {}
    try:
        try:
            legs = ad.attach_protective_orders(asset, side, tp_px=tp, sl_px=sl,
                                               expiration=trigger_expiration,
                                               contracts=contracts)
        except TypeError:
            legs = ad.attach_protective_orders(asset, side, tp_px=tp, sl_px=sl,
                                               expiration=trigger_expiration)
        open_orders = ad.list_protective_orders(asset)
        open_ids = {str(o.get("id") or o.get("algo_id")) for o in open_orders if isinstance(o, dict)}
        if str(legs.get("tp")) not in open_ids or str(legs.get("sl")) not in open_ids:
            raise RuntimeError("回读未见双腿触发单")
    except Exception as exc:
        # 审计④#9(2026-09-13)：铁律「任一步失败→已挂触发单回滚+撤入场单」旧实现只
        # 撤入场单——tp 挂成、sl 失败时 tp 孤儿遗留至 expiration（无仓挂保护单不可对账）。
        # 现双段清理：①已知 legs 逐腿 best-effort 撤；②枚举该资产残留触发单，只撤
        # 带 r20 前缀的本系统单（用户手动保护单绝不触碰）；枚举失败如实标注。
        rollback_notes = []
        for _leg in ("tp", "sl"):
            _lid = str((legs or {}).get(_leg) or "")
            if not _lid or _lid in ("None", ""):
                continue
            try:
                ad.cancel_order(asset, _lid)
            except Exception as leg_exc:
                rollback_notes.append(f"{_leg.upper()}腿 {_lid} 撤销失败({leg_exc})")
        try:
            residue = ad.list_protective_orders(asset) or []
            for row in residue:
                if not isinstance(row, dict):
                    continue
                _o = row.get("order") if isinstance(row.get("order"), dict) else row
                _text = (str(_o.get("text") or "") + str(row.get("text") or "")).lower()
                if "r20" not in _text:
                    continue  # 只清本系统触发单
                _rid = str(row.get("id") or row.get("algo_id") or row.get("order_id") or _o.get("id") or "")
                if not _rid or _rid in ("None",):
                    continue
                try:
                    ad.cancel_order(asset, _rid)
                    rollback_notes.append(f"孤儿触发单 {_rid} 已撤")
                except Exception as rexc:
                    rollback_notes.append(f"孤儿触发单 {_rid} 撤销失败({rexc})")
        except Exception as lexc:
            rollback_notes.append(f"孤儿触发单未能枚举({lexc})——依赖交易所侧 OCO/到期/手动兜底")
        try:
            ad.cancel_order(asset, order_id)
            rollback_notes.append("入场单已撤销")
        except Exception as cexc:
            rollback_notes.append(f"入场单撤销失败({cexc})——交易所侧 OCO/手动兜底")
        detail = f"保护单覆盖失败: {exc}"
        if rollback_notes:
            detail += "；回滚记录: " + "；".join(rollback_notes)
        return _fail("protective", detail, venue=venue, order_id=order_id)

    return RouteResult(ok=True, venue=venue, stage="done", asset=asset,
                       action=action, order_id=order_id,
                       tp_id=str(legs.get("tp")), sl_id=str(legs.get("sl")),
                       size_signed=signed,
                       contracts=contracts, notional_usdt=round(notional, 2),
                       margin_usdt=round(margin, 4),
                       margin_clamped_from_usdt=margin_clamped_from or None,
                       ref_price=ref_price, rr=round(rr, 3), leverage=leverage,
                       detail=f"{venue.upper()} 入场限价挂单 + TP/SL 双腿云端触发单已回读验证")


def close_position(symbol: str, *, venue: str = "gate", adapter: Any = None,
                   environment: Optional[str] = None, pos_side: Optional[str] = None) -> RouteResult:
    """市价全平（close=true + ioc），依赖同前：开闸 + 凭证。"""
    v = str(venue or getattr(getattr(adapter, "capabilities", None), "venue", "gate") or "gate").lower()
    if environment and is_sandbox_environment(environment) and v == "gate" and environment != "sandbox":
        environment = "sandbox"
    ad = adapter or get_adapter(v, environment=environment)
    require_execution(v, environment=str(getattr(ad, "environment", "live") or "live"))
    asset = canonical_base(symbol)
    try:
        kwargs: Dict[str, Any] = {}
        try:
            import inspect
            if "pos_side" in inspect.signature(ad.fast_close_position).parameters and pos_side:
                kwargs["pos_side"] = str(pos_side)
        except (TypeError, ValueError):
            pass
        data = ad.fast_close_position(asset, **kwargs)
    except ExchangeCapabilityError:
        raise
    except Exception as exc:
        return _fail("close", f"{v.upper()} 平仓失败: {exc}", venue=v, asset=asset)
    # 审计 B1：适配器明示未平（closed:False，如无持仓/双向歧义/非整数张数）绝不
    # 换算成功——旧实现只查异常，把 {"closed": False} 也报成 ok=True。
    if isinstance(data, dict) and data.get("closed") is False:
        return _fail("close", f"{v.upper()} 平仓未受理: {data.get('reason') or data}", venue=v, asset=asset)
    return RouteResult(ok=True, venue=v, stage="done", asset=asset,
                       detail=f"{v.upper()} 市价全平已提交: {str(data)[:120]}")
