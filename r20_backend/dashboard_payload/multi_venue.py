"""多所持仓/挂单对齐（结构优化阶段 2·B2 第七刀）。

从 update_cache_cycle 的「2.5 Multi-Venue Parity」段整段迁出。本段不读任何会被
测试 patch 的门面路径常量（只走 r20_backend.exchanges 适配器与纯函数
`_global_env_axis`），故门面直接重导出即可，无需薄壳注入。
"""
from __future__ import annotations

from r20_backend.dashboard_payload.market import _global_env_axis

__all__ = ["collect_cross_venue_positions"]


def collect_cross_venue_positions(positions, pending_orders_list,
                                  long_count, short_count, total_pos_upl):
    """把 Binance/Gate 的持仓与挂单并入 OKX 主视野（就地追加，返回累计计数）。

    原样搬自 update_cache_cycle 的「2.5 Multi-Venue Parity」段：
    - positions / pending_orders_list 是**传入后原地 append**，不是返回新列表；
    - 三个计数器以「入参 → 返回」的形式流转；
    - 整段被 try/except Exception: pass 包裹（跨所接口不可用时静默降级，
      绝不影响主缓存）—— 包括那句**函数内**的 `from r20_backend.exchanges import`，
      保持惰性导入：exchanges 导入期若出错，也落在同一个 except 里。
    """
    try:
        from r20_backend.exchanges import get_adapter, is_registered
        env_axis = _global_env_axis()
        for v_name in ("binance", "gate"):
            try:
                ad = get_adapter(v_name, environment=env_axis)
                v_positions = ad.positions() if hasattr(ad, "positions") else []
                v_open_orders = ad.open_orders() if hasattr(ad, "open_orders") else []
                v_algos = ad.list_protective_orders() if hasattr(ad, "list_protective_orders") else []

                for vp in (v_positions or []):
                    amt = float(vp.get("size_signed", 0) or 0)
                    if abs(amt) < 1e-12:
                        continue
                    base_sym = str(vp.get("base") or vp.get("symbol", "")).replace("USDT", "").replace("_USDT", "").upper()
                    v_inst_id = f"{base_sym}-USDT-SWAP"
                    v_pos_side = str(vp.get("side") or ("long" if amt > 0 else "short")).lower()
                    if "long" in v_pos_side:
                        long_count += 1
                    else:
                        short_count += 1
                    v_upl = float(vp.get("unrealized_pnl", 0) or 0)
                    total_pos_upl += v_upl
                    v_sz = abs(amt)
                    v_avg = float(vp.get("entry_price", 0) or 0)
                    v_mark = float(vp.get("mark_price", 0) or v_avg)
                    v_lever = float(vp.get("leverage", 3) or 3)
                    v_notional = round(v_sz * (v_mark if v_mark > 0 else v_avg), 2)
                    v_margin = round(v_notional / max(1.0, v_lever), 2)
                    v_roi = round((v_upl / max(1.0, v_margin)) * 100, 2) if v_margin > 0 else 0.0
                    v_chg = round(((v_mark - v_avg) / v_avg * 100) if v_avg > 0 else 0, 2)

                    # Check cloud OCO protective orders
                    matching_v_algos = [a for a in v_algos if base_sym in str(a.get("symbol", "")).upper()]
                    v_sl = next((float(a.get("trigger_price") or a.get("triggerPrice") or 0) for a in matching_v_algos if "STOP" in str(a.get("raw", {}).get("orderType", "")).upper() or "STOP" in str(a.get("type", "")).upper()), None)
                    v_tp = next((float(a.get("trigger_price") or a.get("triggerPrice") or 0) for a in matching_v_algos if "TAKE_PROFIT" in str(a.get("raw", {}).get("orderType", "")).upper() or "TAKE_PROFIT" in str(a.get("type", "")).upper()), None)

                    positions.append({
                        "venue": v_name,
                        "exchange": v_name,
                        "instId": v_inst_id,
                        "name": base_sym,
                        "posSide": v_pos_side,
                        "side": v_pos_side,
                        "pos": str(v_sz),
                        "pos_sz": v_sz,
                        "notional_usdt": v_notional,
                        "margin_usdt": v_margin,
                        "marginSource": "exchange_imr",
                        "lever": f"{int(v_lever)}",
                        "avgPx": v_avg,
                        "markPx": v_mark,
                        "upl": v_upl,
                        "uplRatio": v_roi,
                        "roi_pct": v_roi,
                        "price_change_pct": v_chg,
                        "liqPx": vp.get("liq_price", "--"),
                        "bePx": "--",
                        "trailingSl": v_sl,
                        "stageDesc": "云端双腿防护中" if (v_sl and v_tp) else "持有监控中",
                        "strategyTag": f"🏛️ {v_name.capitalize()}",
                        "exchangeSl": v_sl,
                        "exchangeTp": v_tp,
                        "protectionStatus": "fully_protected" if (v_sl and v_tp) else ("partially_protected" if (v_sl or v_tp) else "unprotected"),
                        "protectionCoveragePct": 100.0 if (v_sl and v_tp) else (50.0 if (v_sl or v_tp) else 0.0),
                        "cloud_oco_verified": bool(v_sl and v_tp),
                    })

                for vo in (v_open_orders or []):
                    base_sym = str(vo.get("base") or vo.get("symbol", "")).replace("USDT", "").replace("_USDT", "").upper()
                    v_inst_id = f"{base_sym}-USDT-SWAP"
                    vo_side_raw = str(vo.get("side", "")).lower()
                    vo_is_long = vo_side_raw == "buy"
                    vo_px_float = float(vo.get("price", 0) or 0)
                    vo_sz = str(vo.get("size", "--"))
                    vo_ord_id = str(vo.get("order_id", vo.get("orderId", "")))
                    pending_orders_list.append({
                        "venue": v_name,
                        "exchange": v_name,
                        "ordId": vo_ord_id,
                        "name": base_sym,
                        "inst": base_sym,
                        "instId": v_inst_id,
                        "side": "buy" if vo_is_long else "sell",
                        "side_label": "限价买多" if vo_is_long else "限价卖空",
                        "side_raw": vo_side_raw,
                        "posSide": "long" if vo_is_long else "short",
                        "is_long": vo_is_long,
                        "side_color": "emerald" if vo_is_long else "rose",
                        "ord_type": "limit",
                        "lever": "3x",
                        "px": f"{vo_px_float:g}" if vo_px_float > 0 else "--",
                        "sz": vo_sz,
                        "cTime": str(vo.get("time", "")),
                        "time": "刚刚",
                        "state": "live",
                        "tp_px": "--",
                        "sl_px": "--"
                    })
            except Exception:
                pass
    except Exception:
        pass
    return long_count, short_count, total_pos_upl
