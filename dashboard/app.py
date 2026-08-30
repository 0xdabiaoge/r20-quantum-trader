"""
Web Dashboard Application Module
"""
import os
import json
import time
import datetime
import subprocess
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = BASE_DIR
WORKSPACE_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
LOGS_DIR = os.path.join(WORKSPACE_DIR, "logs")

LEDGER_JSON_FILE = os.path.join(DATA_DIR, "trading_ledger.json")
LOG_FILE = os.path.join(LOGS_DIR, "ai_factor_trader.log")
NEWS_SENTIMENT_FILE = os.path.join(DATA_DIR, "news_sentiment.json")
REVIEW_JOURNAL_FILE = os.path.join(DATA_DIR, "trade_review_journal.json")
REPORT_JSON_FILE = os.path.join(DATA_DIR, "self_improvement_report.json")
POSITION_TRACKER_FILE = os.path.join(DATA_DIR, "position_trackers.json")
SNAPSHOTS_JSON_FILE = os.path.join(DATA_DIR, "snapshots.json")
STATE_JSON_FILE = os.path.join(DATA_DIR, "trading_state.json")
AI_DECISIONS_FILE = os.path.join(DATA_DIR, "ai_brain_decisions.json")
AI_HISTORY_FILE = os.path.join(DATA_DIR, "ai_brain_history.json")
AI_LAST_PROMPT_FILE = os.path.join(DATA_DIR, "ai_brain_last_prompt.txt")
FACTOR_LIBRARY_FILE = os.path.join(DATA_DIR, "factor_library_snapshot.json")
AI_MEMORY_MD_FILE = os.path.join(DATA_DIR, "AI_TRADING_MEMORY.md")

TARGET_INSTRUMENTS = [
    {"instId": "BTC-USDT-SWAP", "name": "BTC", "type": "crypto", "sz": "1", "ctVal": 0.01},
    {"instId": "ETH-USDT-SWAP", "name": "ETH", "type": "crypto", "sz": "3", "ctVal": 0.1},
    {"instId": "SOL-USDT-SWAP", "name": "SOL", "type": "crypto", "sz": "7", "ctVal": 1.0},
    {"instId": "DOGE-USDT-SWAP", "name": "DOGE", "type": "crypto", "sz": "100", "ctVal": 100.0},
    {"instId": "SUI-USDT-SWAP", "name": "SUI", "type": "crypto", "sz": "50", "ctVal": 1.0},
    {"instId": "LINK-USDT-SWAP", "name": "LINK", "type": "crypto", "sz": "64", "ctVal": 1.0},
]

app = FastAPI(title="R20 AI Quantitative Matrix")
templates = Jinja2Templates(directory=os.path.join(DASHBOARD_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(DASHBOARD_DIR, "static")), name="static")

def run_json_cmd_status(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return True, json.loads(res.stdout.strip()), ""
        return False, None, res.stderr.strip() or res.stdout.strip() or "empty response"
    except Exception as e:
        return False, None, str(e)


def run_json_cmd(cmd):
    ok, data, _ = run_json_cmd_status(cmd)
    return data if ok else None

CACHE_DATA = {}
LAST_CACHE_TIME = 0
CACHE_LOCK = None
SYNC_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dashboard_sync")

def get_cache_lock():
    global CACHE_LOCK
    if CACHE_LOCK is None:
        CACHE_LOCK = asyncio.Lock()
    return CACHE_LOCK

def update_cache_cycle():
    global CACHE_DATA, LAST_CACHE_TIME
    tz_beijing = datetime.timezone(datetime.timedelta(hours=8))
    now_bj = datetime.datetime.now(tz_beijing)
    today_bj_str = now_bj.strftime("%Y-%m-%d")
    timestamp_full = now_bj.strftime("%Y-%m-%d %H:%M:%S (北京时间)")

    source_errors = []
    # 1. Fetch OKX Live Balance (Strictly USDT Contract Sub-account)
    balance_ok, bal_data, balance_error = run_json_cmd_status("okx --demo account balance --json")
    if not balance_ok:
        source_errors.append(f"balance: {balance_error}")
        bal_data = []
    total_eq = 0.0
    avail_eq = 0.0
    cash_bal = 0.0
    upl_acc = 0.0

    if isinstance(bal_data, list) and bal_data:
        for d in bal_data[0].get("details", []):
            if d.get("ccy") == "USDT":
                total_eq = float(d.get("eq", 0.0) or 0.0)
                avail_eq = float(d.get("availBal", 0.0) or 0.0)
                cash_bal = float(d.get("cashBal", 0.0) or 0.0)
                upl_acc = float(d.get("upl", 0.0) or 0.0)
                break

    # 2. Fetch OKX Live Positions
    positions_ok, pos_data, positions_error = run_json_cmd_status("okx --demo account positions --json")
    if not positions_ok:
        source_errors.append(f"positions: {positions_error}")
        pos_data = []
    positions = []
    total_pos_upl = 0.0
    long_count = 0
    short_count = 0

    trackers = {}
    if os.path.exists(POSITION_TRACKER_FILE):
        try:
            with open(POSITION_TRACKER_FILE, "r", encoding="utf-8") as f:
                trackers = json.load(f)
        except Exception:
            pass

    if isinstance(pos_data, list):
        for p in pos_data:
            pos_val = float(p.get("pos", 0.0) or 0.0)
            if pos_val == 0.0:
                continue

            pos_side = p.get("posSide", p.get("side", "")).lower()
            if "long" in pos_side:
                long_count += 1
            elif "short" in pos_side:
                short_count += 1

            upl = float(p.get("upl", 0.0) or 0.0)
            total_pos_upl += upl

            pos_key = f"{p.get('instId')}_{p.get('posSide', 'net')}"
            t_info = trackers.get(pos_key, {})
            trailing_sl = t_info.get("trailingStopPx", "--")
            stage_desc = t_info.get("stage_desc", "持有监控中")
            strategy_tag = t_info.get("strategy_tag") or ("🌊 低吸" if "long" in pos_side else "⚡ 高空")

            avg_px = float(p.get("avgPx", 0) or 0)
            mark_px = float(p.get("markPx", 0) or 0)
            pos_sz = float(p.get("pos", 0) or 0)

            ct_val = 1.0
            inst_id_val = p.get("instId", "")
            for target_item in TARGET_INSTRUMENTS:
                if target_item["instId"] == inst_id_val:
                    ct_val = target_item.get("ctVal", 1.0)
                    break
            
            notional_usdt = round(pos_sz * ct_val * (mark_px if mark_px > 0 else avg_px), 2)
            raw_upl_ratio = float(p.get("uplRatio", 0.0) or 0.0)
            real_roi_pct = round(raw_upl_ratio * 100, 2)
            price_chg = round(((mark_px - avg_px) / avg_px * 100) if avg_px > 0 else 0, 2)

            lever_val = float(p.get("lever", "3") or 3.0)
            margin_usdt_val = round(notional_usdt / lever_val, 2) if lever_val > 0 else notional_usdt

            positions.append({
                "instId": p.get("instId"),
                "name": p.get("instId", "").replace("-USDT-SWAP", ""),
                "posSide": pos_side,
                "pos": p.get("pos"),
                "pos_sz": pos_sz,
                "notional_usdt": notional_usdt,
                "margin_usdt": margin_usdt_val,
                "lever": p.get("lever", "3"),
                "avgPx": avg_px,
                "markPx": mark_px,
                "upl": upl,
                "uplRatio": real_roi_pct,
                "roi_pct": real_roi_pct,
                "price_change_pct": price_chg,
                "liqPx": p.get("liqPx", "--"),
                "bePx": p.get("bePx", "--"),
                "trailingSl": trailing_sl,
                "stageDesc": stage_desc,
                "strategyTag": strategy_tag,
                "tp1Hit": t_info.get("tp1_hit", False),
                "tp2Hit": t_info.get("tp2_hit", False)
            })

    # 2.5 Fetch OKX Live Pending Maker Orders
    orders_ok, orders_data, orders_error = run_json_cmd_status("okx --demo swap orders --json")
    pending_orders_list = []
    if isinstance(orders_data, list):
        for o in orders_data:
            c_ts = int(o.get("cTime", 0) or 0) / 1000.0
            c_time_str = datetime.datetime.fromtimestamp(c_ts, tz=tz_beijing).strftime("%m-%d %H:%M:%S") if c_ts > 0 else "--"
            inst_id = o.get("instId", "")
            inst_clean = inst_id.replace("-USDT-SWAP", "").replace("-SWAP", "")
            side_raw = str(o.get("side", "")).lower()
            pos_side = str(o.get("posSide", "")).lower()
            is_long = (pos_side == "long" or side_raw == "buy")
            side_label = "限价买多" if is_long else "限价卖空"
            side_color = "emerald" if is_long else "rose"
            
            attach_list = o.get("attachAlgoOrds", [])
            tp_px = "--"
            sl_px = "--"
            if attach_list and len(attach_list) > 0:
                att = attach_list[0]
                tp_px = str(att.get("tpTriggerPx") or "--")
                sl_px = str(att.get("slTriggerPx") or "--")

            pending_orders_list.append({
                "ordId": str(o.get("ordId", "")),
                "inst": inst_clean,
                "instId": inst_id,
                "side": side_label,
                "side_raw": side_raw,
                "posSide": pos_side,
                "is_long": is_long,
                "side_color": side_color,
                "lever": f"{o.get('lever', '3')}x",
                "px": str(o.get("px", "--")),
                "sz": str(o.get("sz", "--")),
                "time": c_time_str,
                "state": str(o.get("state", "live")),
                "tp_px": tp_px,
                "sl_px": sl_px
            })

    # A failed core account query must never overwrite last-known-good data with zeros.
    if not balance_ok or not positions_ok:
        if CACHE_DATA:
            stale = dict(CACHE_DATA)
            stale["data_health"] = {
                "status": "STALE",
                "partial": True,
                "errors": source_errors,
                "last_success_at": CACHE_DATA.get("timestamp"),
                "attempted_at": timestamp_full,
                "cache_age_seconds": round(time.time() - LAST_CACHE_TIME, 1),
            }
            CACHE_DATA = stale
            return
        CACHE_DATA = {
            "timestamp": timestamp_full,
            "data_health": {"status": "OFFLINE", "partial": True, "errors": source_errors},
            "account": {}, "today_stats": {}, "performance": {},
            "positions_summary": {"total": 0, "max_positions": len(TARGET_INSTRUMENTS), "items": []},
            "factors": [], "trades": [], "logs": [], "snapshots": [],
        }
        return

    # Exchange algo orders are the source of truth for live TP/SL protection.
    for position in positions:
        algo_ok, algo_orders, algo_error = run_json_cmd_status(f"okx --demo swap algo orders --instId {position['instId']} --json")
        if not algo_ok:
            source_errors.append(f"algo {position['instId']}: {algo_error}")
            algo_orders = []
        matching_algos = [
            o for o in algo_orders
            if o.get("state") == "live"
            and o.get("posSide") == position["posSide"]
            and str(o.get("reduceOnly", "")).lower() == "true"
        ]
        protected_size = sum(float(o.get("sz", 0) or 0) for o in matching_algos if o.get("slTriggerPx"))
        full_coverage = protected_size >= float(position["pos_sz"]) * 0.999
        live_algo = next((o for o in matching_algos if o.get("slTriggerPx") and o.get("tpTriggerPx")), None)
        if live_algo and full_coverage:
            position["exchangeSl"] = float(live_algo.get("slTriggerPx", 0) or 0)
            position["exchangeTp"] = float(live_algo.get("tpTriggerPx", 0) or 0)
            position["protectionStatus"] = "fully_protected"
            position["protectionCoveragePct"] = 100.0
            position["protectionAlgoId"] = live_algo.get("algoId", "")
        elif matching_algos:
            sl_algo = next((o for o in matching_algos if o.get("slTriggerPx")), {})
            position["exchangeSl"] = float(sl_algo.get("slTriggerPx", 0) or 0) or None
            position["exchangeTp"] = float(sl_algo.get("tpTriggerPx", 0) or 0) or None
            position["protectionStatus"] = "partially_protected"
            position["protectionCoveragePct"] = round(min(100.0, protected_size / max(position["pos_sz"], 1e-12) * 100), 1)
            position["protectionAlgoId"] = sl_algo.get("algoId", "")
        else:
            position["exchangeSl"] = None
            position["exchangeTp"] = None
            position["protectionStatus"] = "unprotected"
            position["protectionCoveragePct"] = 0.0
            position["protectionAlgoId"] = ""

    # 3. Read Reset Initial State
    account_init_file = os.path.join(DATA_DIR, "account_initial_state.json")
    reset_time_str = "1970-01-01 00:00:00"
    initial_capital_val = float(os.getenv("INITIAL_CAPITAL", "10000.0"))
    if os.path.exists(account_init_file):
        try:
            with open(account_init_file, "r", encoding="utf-8") as f:
                acc_init = json.load(f)
                reset_time_str = acc_init.get("reset_time", "1970-01-01 00:00:00")
                initial_capital_val = float(acc_init.get("initial_capital", 10000.0) or 10000.0)
        except Exception:
            pass

    # 4. Load Bills and Real Order-Level Ledger
    bills_ok, bills_data, bills_error = run_json_cmd_status("okx --demo account bills --limit 100 --json")
    if not bills_ok:
        source_errors.append(f"bills: {bills_error}")
        bills_data = []
    
    # Process Real Orders Aggregation (Minute + Inst + Action)
    orders_by_key = {}
    today_realized_gross = 0.0
    today_fees = 0.0
    cum_total_fees = 0.0
    today_funding = 0.0
    funding_history_list = []
    
    if isinstance(bills_data, list):
        for b in reversed(bills_data):
            ts = int(b.get("ts", 0) or 0) / 1000.0
            dt_bj = datetime.datetime.fromtimestamp(ts, tz=tz_beijing).strftime("%Y-%m-%d %H:%M:%S")
            if dt_bj < reset_time_str:
                continue

            sub_type = str(b.get("subType", ""))
            b_type = str(b.get("type", ""))
            inst = b.get("instId", "").replace("-USDT-SWAP", "")
            pnl = float(b.get("pnl", 0) or 0)
            fee = float(b.get("fee", 0) or 0)
            bal_chg = float(b.get("balChg", 0) or 0)
            sz = float(b.get("sz", 0) or 0)

            # Accumulate all trading fees (Cum & Today)
            cum_total_fees += fee
            if today_bj_str in dt_bj:
                today_fees += fee

            if b_type == "8" or sub_type in ["173", "174"]:
                funding_pnl = (bal_chg if bal_chg != 0 else pnl)
                if today_bj_str in dt_bj:
                    today_funding += funding_pnl
                funding_desc = "收取资金费 (+)" if sub_type == "174" or funding_pnl > 0 else "支付资金费 (-)"
                funding_history_list.append({
                    "time": dt_bj,
                    "inst": inst,
                    "type_desc": funding_desc,
                    "pnl": round(funding_pnl, 6),
                    "pos_sz": f"{sz} 张"
                })
                continue

            if sub_type in ["5", "6"]: # Closed order
                # Group by exact Minute + Inst + Close Action
                time_min = dt_bj[:16]
                agg_key = f"{time_min}_{inst}"
                if agg_key not in orders_by_key:
                    orders_by_key[agg_key] = {
                        "time": dt_bj,
                        "inst": inst,
                        "gross_pnl": 0.0,
                        "fee": 0.0,
                        "pnl": 0.0
                    }
                orders_by_key[agg_key]["gross_pnl"] += pnl
                orders_by_key[agg_key]["fee"] += fee
                orders_by_key[agg_key]["pnl"] += (pnl + fee)

    today_win_trades = 0
    today_loss_trades = 0
    all_win_trades = 0
    all_loss_trades = 0
    all_win_amt = 0.0
    all_loss_amt = 0.0
    by_inst = {}

    for agg_k, o in orders_by_key.items():
        net = o["pnl"]
        inst = o["inst"]
        t_time = o["time"]

        if inst not in by_inst:
            by_inst[inst] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        by_inst[inst]["trades"] += 1
        by_inst[inst]["pnl"] += net

        if net > 0:
            all_win_trades += 1
            all_win_amt += net
            by_inst[inst]["wins"] += 1
            if today_bj_str in t_time:
                today_win_trades += 1
        elif net < 0:
            all_loss_trades += 1
            all_loss_amt += abs(net)
            by_inst[inst]["losses"] += 1
            if today_bj_str in t_time:
                today_loss_trades += 1

        if today_bj_str in t_time:
            today_realized_gross += o["gross_pnl"]

    today_closed = today_win_trades + today_loss_trades
    today_win_rate = round((today_win_trades / today_closed) * 100, 1) if today_closed > 0 else 0.0

    all_closed = all_win_trades + all_loss_trades
    all_win_rate = round((all_win_trades / all_closed) * 100, 1) if all_closed > 0 else 0.0
    profit_factor = round((all_win_amt / all_loss_amt), 2) if all_loss_amt > 0 else (99.0 if all_win_amt > 0 else 0.0)
    avg_win = round(all_win_amt / all_win_trades, 2) if all_win_trades > 0 else 0.0
    avg_loss = round(all_loss_amt / all_loss_trades, 2) if all_loss_trades > 0 else 0.0

    # Strict Realized PnL strictly from settled trades + settled fundings (Fixed, not jumping with mark price)
    today_net_realized_pnl = round(today_realized_gross + today_fees + today_funding, 2)
    
    # Strict Total Cumulative Net PnL strictly from Equity vs Base Capital
    total_cum_net_pnl = round(total_eq - initial_capital_val, 2)
    cum_roi_pct = round((total_cum_net_pnl / initial_capital_val * 100) if initial_capital_val > 0 else 0.0, 2)
    total_cum_realized_pnl = round(total_cum_net_pnl - total_pos_upl, 2)

    inst_leaderboard = []
    for inst, s in by_inst.items():
        w_r = round((s["wins"] / s["trades"]) * 100, 1) if s["trades"] > 0 else 0.0
        inst_leaderboard.append({
            "inst": inst,
            "trades": s["trades"],
            "wins": s["wins"],
            "losses": s["losses"],
            "win_rate": w_r,
            "pnl": round(s["pnl"], 2)
        })
    inst_leaderboard.sort(key=lambda x: x["pnl"], reverse=True)

    # 5. Load Log Lines
    log_lines = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                log_lines = [l.strip() for l in lines[-60:] if l.strip()]
        except Exception:
            pass

    # 6. Read Trading State & AI Brain LLM Decisions
    state_data = {}
    ai_decisions = {}
    if os.path.exists(AI_DECISIONS_FILE):
        try:
            with open(AI_DECISIONS_FILE, "r", encoding="utf-8") as f:
                ai_decisions = json.load(f)
        except Exception:
            pass

    factors_list = []
    pos_map = {p.get("instId"): p for p in positions} if isinstance(positions, list) else {}
    if os.path.exists(STATE_JSON_FILE):
        try:
            with open(STATE_JSON_FILE, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                inst_states = state_data.get("instruments", [])
                for ins in inst_states:
                    inst_id = ins.get("instId")
                    ai_info = ai_decisions.get(inst_id, {})
                    ai_dec = ai_info.get("decision", {})
                    ai_thought = ai_info.get("thought_process", {})
                    
                    action_val = ai_dec.get("action", ins.get("action", "WAIT"))
                    confidence = ai_dec.get("confidence")
                    reason = ai_dec.get("summary_reason", ins.get("desc", "等待明确形态信号"))
                    
                    strategy_val = "🟢 建议做多" if action_val == "BUY_LONG" else ("🔴 建议做空" if action_val == "SELL_SHORT" else "⚪ AI观望")
                    score_val = 2.5 if action_val == "BUY_LONG" else (-2.5 if action_val == "SELL_SHORT" else 0.0)
                    vwap_b = float(ins.get("vwap_bias", 0.0) or 0.0)
                    
                    m_struct = ai_thought.get("market_structure", f"{ins.get('market_regime', 'CHOP')} ({ins.get('trend_1h', '震荡')})")
                    v_oi = ai_thought.get("volume_and_oi", f"OBV: {ins.get('obv_flow', 'NEUTRAL')}, 量能: {ins.get('vol_ratio', 1.0)}x")
                    rr_ratio = ai_thought.get("risk_reward_evaluation", "盈亏比评估中")

                    raw_t = ai_info.get("raw_ticker", {})
                    funding_r = ai_info.get("raw_funding_rate") or "--"
                    oi_str = ai_info.get("raw_oi") or "--"
                    taker_str = ai_info.get("raw_taker_vol") or "--"
                    ls_str = ai_info.get("raw_ls_ratio") or "--"

                    factors_list.append({
                        "name": ins.get("name"),
                        "instId": inst_id,
                        "position": pos_map.get(inst_id),
                        "type": ins.get("type", "crypto"),
                        "price": ins.get("price", "--"),
                        "score": score_val,
                        "change24h": raw_t.get("chg24h"),
                        "chg24h": raw_t.get("chg24h"),
                        "bidPx": raw_t.get("bidPx", ins.get("price", "--")),
                        "askPx": raw_t.get("askPx", ins.get("price", "--")),
                        "fundingRate": funding_r,
                        "oiUsd": oi_str,
                        "takerNetUsd": taker_str,
                        "lsRatio": ls_str,
                        "rsi": ins.get("rsi", 50.0),
                        "rsi_7": ins.get("rsi_7", 50.0),
                        "vwap_bias": ins.get("vwap_bias", 0.0),
                        "macd_hist": ins.get("macd_hist", 0.0),
                        "macd_accel": ins.get("macd_accel", 0.0),
                        "obv_flow": ins.get("obv_flow", "NEUTRAL"),
                        "bb_bandwidth": ins.get("bb_bandwidth", 0.0),
                        "vol_ratio": ins.get("vol_ratio", 1.0),
                        "trend_1h": ins.get("trend_1h", "震荡"),
                        "trend_4h": ins.get("trend_4h", "震荡"),
                        "market_regime": ins.get("market_regime", "CHOP"),
                        "strategy_tag": strategy_val,
                        "action": action_val,
                        "confidence": confidence,
                        "smart_money": ai_info.get("smart_money", {}),
                        "adx_1h": ai_info.get("adx_1h", "--"),
                        "leverage": ai_dec.get("leverage", 3),
                        "margin_usdt": ai_dec.get("margin_usdt", 0.0),
                        "entry_price": ai_dec.get("entry_price", 0.0),
                        "take_profit_price": ai_dec.get("take_profit_price", 0.0),
                        "stop_loss_price": ai_dec.get("stop_loss_price", 0.0),
                        "risk_reward_ratio": ai_dec.get("risk_reward_ratio", "--"),
                        "reason": reason,
                        "market_structure": m_struct,
                        "volume_and_oi": v_oi,
                        "rr_ratio": rr_ratio,
                        "thought_process": ai_thought,
                        "confluence_15m": m_struct,
                        "confluence_1h": v_oi,
                        "desc": reason,
                        "ai_last_prompt": ai_info.get("ai_last_prompt", ""),
                        "time_str": ai_info.get("time_str") or state_data.get("timestamp") or timestamp_full,
                        "timestamp": ai_info.get("timestamp")
                    })
        except Exception:
            pass

    # 7. Read Ledger Lifecycle Trades for Table (Directly sync fresh ledger if stale > 60s)
    ledger_trades = []
    need_ledger_sync = True
    if os.path.exists(LEDGER_JSON_FILE):
        try:
            mtime = os.path.getmtime(LEDGER_JSON_FILE)
            if time.time() - mtime < 60:
                need_ledger_sync = False
        except Exception:
            pass

    if need_ledger_sync:
        try:
            sync_script = os.path.join(WORKSPACE_DIR, "scripts", "sync_full_ledger.py")
            if os.path.exists(sync_script):
                subprocess.run(f"python3 {sync_script}", shell=True, capture_output=True, text=True, timeout=10)
        except Exception:
            pass

    if os.path.exists(LEDGER_JSON_FILE):
        try:
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                ledger_trades = json.load(f)
        except Exception:
            pass
    
    # Filter lifecycle trades past reset_time
    valid_ledger_trades = []
    for t in ledger_trades:
        # Check either close_time or open_time >= reset_time
        c_time = str(t.get("close_time", ""))
        o_time = str(t.get("open_time", ""))
        t_time = str(t.get("time", ""))
        if (c_time and c_time >= reset_time_str) or (o_time and o_time >= reset_time_str) or (t_time and t_time >= reset_time_str) or t.get("status") == "holding":
            valid_ledger_trades.append(t)

    trades_table = valid_ledger_trades[:60]

    # 8. Read Review & Adaptive Config
    review_data = {}
    if os.path.exists(REPORT_JSON_FILE):
        try:
            with open(REPORT_JSON_FILE, "r", encoding="utf-8") as f:
                review_data = json.load(f)
        except Exception:
            pass

    adaptive_cfg = {}

    # 9. Read Snapshots
    snapshots_list = []
    if os.path.exists(SNAPSHOTS_JSON_FILE):
        try:
            with open(SNAPSHOTS_JSON_FILE, "r", encoding="utf-8") as f:
                snaps = json.load(f)
                if isinstance(snaps, list):
                    # Filter strictly >= reset_time
                    for s in snaps:
                        s_time = str(s.get("time", ""))
                        if s_time >= reset_time_str:
                            t_eq = float(s.get("total_eq", s.get("equity", initial_capital_val)) or initial_capital_val)
                            pnl_v = round(t_eq - initial_capital_val, 2)
                            roi_v = round((pnl_v / initial_capital_val * 100), 2)
                            snapshots_list.append({
                                "time": s_time,
                                "total_eq": round(t_eq, 2),
                                "pnl": pnl_v,
                                "roi": roi_v
                            })
                    snapshots_list = snapshots_list[-60:]
        except Exception:
            pass

    # Append live current point
    snapshots_list.append({
        "time": timestamp_full.replace(" (北京时间)", ""),
        "total_eq": round(total_eq, 2),
        "pnl": round(total_eq - initial_capital_val, 2),
        "roi": round((total_eq - initial_capital_val) / initial_capital_val * 100, 2)
    })

    # 10. Read News & AI Decisions History
    news_data = {}
    if os.path.exists(NEWS_SENTIMENT_FILE):
        try:
            with open(NEWS_SENTIMENT_FILE, "r", encoding="utf-8") as f:
                news_data = json.load(f)
        except Exception:
            pass

    ai_last_prompt_text = ""
    if os.path.exists(AI_LAST_PROMPT_FILE):
        try:
            with open(AI_LAST_PROMPT_FILE, "r", encoding="utf-8") as f:
                ai_last_prompt_text = f.read()
        except Exception:
            pass

    ai_history_list = []
    if os.path.exists(AI_HISTORY_FILE):
        try:
            with open(AI_HISTORY_FILE, "r", encoding="utf-8") as f:
                ai_history_list = json.load(f)
        except Exception:
            pass

    # Inject latest prompt into review payload if running under older worker
    if isinstance(review_data, dict):
        review_data["ai_last_prompt"] = ai_last_prompt_text

    factor_lib_snapshot = {}
    if os.path.exists(FACTOR_LIBRARY_FILE):
        try:
            with open(FACTOR_LIBRARY_FILE, "r", encoding="utf-8") as f:
                factor_lib_snapshot = json.load(f)
        except Exception:
            pass

    ai_memory_md_content = ""
    if os.path.exists(AI_MEMORY_MD_FILE):
        try:
            with open(AI_MEMORY_MD_FILE, "r", encoding="utf-8") as f:
                ai_memory_md_content = f.read()
        except Exception:
            pass

    ai_last_prompt_text = ""
    if os.path.exists(AI_LAST_PROMPT_FILE):
        try:
            with open(AI_LAST_PROMPT_FILE, "r", encoding="utf-8") as f:
                ai_last_prompt_text = f.read()
        except Exception:
            pass

    # System Disk info
    total_b, used_b, free_b = shutil.disk_usage("/")
    disk_free_gb = round(free_b / (1024 ** 3), 1)

    CACHE_DATA = {
        "timestamp": timestamp_full,
        "date": today_bj_str,
        "data_health": {
            "status": "LIVE" if not source_errors else "PARTIAL",
            "partial": bool(source_errors),
            "errors": source_errors,
            "last_success_at": timestamp_full,
            "cache_age_seconds": 0,
            "timezone": "Asia/Shanghai",
            "bills_complete": False,
            "bills_coverage_note": "OKX latest 100 bills; NAV remains the cumulative equity source of truth"
        },
        "system": {
            "disk": {
                "free_gb": disk_free_gb
            }
        },
        "account": {
            "initial_capital": round(initial_capital_val, 2),
            "total_eq": round(total_eq, 2),
            "avail_eq": round(avail_eq, 2),
            "cash_bal": round(cash_bal, 2),
            "upl": round(upl_acc, 2),
            "pos_upl_total": round(total_pos_upl, 2),
            "cum_realized_pnl": round(total_cum_realized_pnl, 2),
            "cum_net_pnl": round(total_cum_net_pnl, 2),
            "cum_roi_pct": cum_roi_pct,
            "cum_total_fees": round(cum_total_fees, 2),
            "margin_usage_pct": round(((total_eq - avail_eq) / total_eq * 100) if total_eq > 0 else 0, 1)
        },
        "today_stats": {
            "realized_gross": round(today_realized_gross, 2),
            "fees_paid": round(today_fees, 2),
            "funding_paid": round(today_funding, 2),
            "net_realized": round(today_net_realized_pnl, 2),
            "total_pnl": round(today_net_realized_pnl + total_pos_upl, 2),
            "win_trades": today_win_trades,
            "loss_trades": today_loss_trades,
            "win_rate": today_win_rate
        },
        "performance": {
            "all_trades": all_closed,
            "win_trades": all_win_trades,
            "loss_trades": all_loss_trades,
            "win_rate": all_win_rate,
            "profit_factor": profit_factor,
            "total_win_amt": round(all_win_amt, 2),
            "total_loss_amt": round(all_loss_amt, 2),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "leaderboard": inst_leaderboard
        },
        "positions_summary": {
            "total": len(positions),
            "active_count": len(positions),
            "max": len(TARGET_INSTRUMENTS),
            "max_positions": len(TARGET_INSTRUMENTS),
            "long_count": long_count,
            "short_count": short_count,
            "total_upl": round(total_pos_upl, 2),
            "items": positions
        },
        "pending_orders": pending_orders_list,
        "factors": factors_list,
        "funding_settlements": {
            "total_funding_pnl": round(today_funding, 4),
            "items": sorted(funding_history_list, key=lambda x: x["time"], reverse=True)[:30]
        },
        "adaptive_config": adaptive_cfg,
        "review": review_data,
        "ai_trading_memory_md": ai_memory_md_content,
        "ai_last_prompt": ai_last_prompt_text,
        "snapshots": snapshots_list,
        "state_snapshot": state_data,
        "logs": log_lines,
        "trades": trades_table,
        "news_intelligence": news_data,
        "ai_brain_history": ai_history_list,
        "factor_library": factor_lib_snapshot
    }
    LAST_CACHE_TIME = time.time()

async def refresh_cache_if_needed(ttl_seconds: float = 3.0):
    global LAST_CACHE_TIME, CACHE_DATA
    if time.time() - LAST_CACHE_TIME <= ttl_seconds and CACHE_DATA:
        return CACHE_DATA
    lock = get_cache_lock()
    async with lock:
        if time.time() - LAST_CACHE_TIME <= ttl_seconds and CACHE_DATA:
            return CACHE_DATA
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(SYNC_EXECUTOR, update_cache_cycle)
        return CACHE_DATA

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/all")
async def get_all_data():
    data = await refresh_cache_if_needed(3.0)
    return JSONResponse(data)

@app.get("/api/overview")
async def get_overview():
    data = await refresh_cache_if_needed(3.0)
    return JSONResponse(data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
