#!/usr/bin/env python3
"""
R20 Authentic OKX Positions-History Ledger Synchronizer (sync_full_ledger.py)
Directly reads OKX official `account positions-history` & `account positions` API.
Eliminates bills heuristic split-error, accurately records real position-level trades!
"""

import json
import os
import sys
import datetime
import tempfile

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import scripts.okx_rest as okx_rest
import scripts.okx_runtime as okx_runtime

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
LEDGER_JSON_FILE = os.path.join(DATA_DIR, "trading_ledger.json")
LEDGER_SYNC_STATUS_FILE = os.path.join(DATA_DIR, "ledger_sync_status.json")
# 审计 A2（数据诚实）：逐所台账同步状态旁车。任一 fetch 失败只 print-warn 后
# 返回 []，与「该所确无平仓」在 trading_ledger.json 里不可分辨；旁车记录
# ok/failed(原因)/failed(截断风险)，供 data_health/前台显式 PARTIAL。
_FETCH_STATUS = {}


def _mark(venue, status, **extra):
    rec = {"status": status}
    rec.update(extra)
    _FETCH_STATUS[venue] = rec


def _fetch_history_paged(fetch_fn, *, id_field="posId", cursor_field="uTime", limit=100, max_pages=5):
    """OKX 历史接口分页取尽（after=取更早）。

    批C(2026-09-13)：原实现单页 limit 条即止 —— 平仓笔数越 100 后更早记录永远取不到，
    台账只能靠旧 JSON 合并续命（重算/迁移即静默丢历史），data_health 也只能挂一条
    「触顶 limit=100，可能存在截断」的常驻告警。

    ⚠️ 实测校正（demo 实号，2026-09-13）：positions-history 的 after/before **只认毫秒
    时间戳**——传 posId 直接 `51000 Parameter after error`（官方文档措辞为 "earlier than
    the requested posId"，与实现不符）。故游标取末条的 uTime，after=向更早回溯。

    返回 (rows, truncated)：
      · 防漏 —— 逐页累加，按 (id, uTime) 去重（实测分页边界有 4 条重叠）；
      · 防死循环 —— 页未满即取尽；游标不再变旧/零新增（服务端忽略 after 时会把同一页
        反复返回）立即停；页满且用尽 max_pages 也停；
      · 诚实 —— 凡「停时仍未证取尽」一律 truncated=True，前台继续显式 PARTIAL，
        绝不因为「多取了几页」就假称完整。
    """
    rows: list = []
    seen: set = set()
    cursor = None
    prev_cursor = None
    truncated = False
    for _ in range(max(1, int(max_pages))):
        page = fetch_fn(limit=limit, after=cursor) or []
        if not page:
            break
        fresh = 0
        for _r in page:
            _k = (str(_r.get(id_field) or ""), str(_r.get(cursor_field) or ""))
            if _k in seen:
                continue
            seen.add(_k)
            rows.append(_r)
            fresh += 1
        _new_cursor = str(page[-1].get(cursor_field) or "")
        if len(page) < limit:
            break                      # 服务端已给尽
        if fresh == 0 or not _new_cursor or _new_cursor == prev_cursor:
            truncated = True           # 无法继续（游标无效/被忽略）→ 诚实标记
            break
        prev_cursor = _new_cursor
        cursor = _new_cursor
    else:
        truncated = True               # 页页全满且用尽页数上限
    return rows, truncated


def _write_sync_status(env):
    """原子写旁车；读侧一律容错缺文件（旧版本无旁车=按 OK 不误伤）。
    路径按调用时 DATA_DIR 解析——测试 patch 模块 DATA_DIR 即封闭（律①）。"""
    _dir = DATA_DIR
    target = os.path.join(_dir, "ledger_sync_status.json")
    payload = {
        "generated_at": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "environment": "demo" if getattr(env, "simulated", False) else "live",
        "venues": dict(_FETCH_STATUS),
    }
    fd, tmp = tempfile.mkstemp(prefix=".lss-", suffix=".tmp", dir=_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception as exc:
        print(f"[sync_full_ledger] warn 台账同步状态旁车写入失败: {exc}")
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


INITIAL_STATE_FILE = os.path.join(DATA_DIR, "account_initial_state.json")
POSITION_TRACKER_FILE = os.path.join(DATA_DIR, "position_trackers.json")

from instrument_pool import load_instruments

TARGET_INSTRUMENTS = load_instruments()

# 历史币种白名单缓存：交易所规格回退查询用（进程内一次即可）
_CTVAL_CACHE = {}

def _sqlite_traded_names():
    """SQLite 台账里出现过的币种名（已下架币种的历史事实源）。"""
    names = set()
    try:
        import sqlite3
        db = os.path.join(DATA_DIR, "r20_quant.db")
        if os.path.exists(db):
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            for (inst,) in con.execute("SELECT DISTINCT inst FROM trades"):
                if inst:
                    names.add(str(inst))
            con.close()
    except Exception:
        pass
    return names

def allowed_inst_ids(existing_ledger_trades=None):
    """台账重建允许集合 = 当前标的池 ∪ 历史留痕币种。

    修复(2026-09-09)：此前重建仅认当前池，用户从池中删除币种后，下一次同步
    会把该币种的全部已平仓历史从 trading_ledger.json 抹掉（SQLite 仍在，但页面
    台账消失）；持仓中途删币还会让在途仓位在台账里隐身。历史是交易所事实，
    不随池配置消亡；噪声过滤（拦截 R20 从未交易过的手动单）由并集继续保证。
    """
    allowed = {item["instId"] for item in TARGET_INSTRUMENTS}
    names = _sqlite_traded_names()
    for t in (existing_ledger_trades or []):
        inst = str(t.get("inst") or t.get("name") or "")
        if inst:
            names.add(inst)
    try:
        if os.path.exists(POSITION_TRACKER_FILE):
            with open(POSITION_TRACKER_FILE, "r", encoding="utf-8") as f:
                for key in json.load(f):
                    inst = str(key).rsplit("_", 1)[0]
                    if inst:
                        names.add(inst)
    except Exception:
        pass
    for n in names:
        n = n.strip()
        if not n:
            continue
        allowed.add(n if "-USDT-SWAP" in n or "-USD-SWAP" in n else f"{n}-USDT-SWAP")
    return allowed

def get_ct_val(inst_name):
    for item in TARGET_INSTRUMENTS:
        if item["name"] == inst_name or item["instId"] == inst_name:
            return item["ctVal"]
    # 已下架币种回退：查 OKX 公共合约规格（免费、无需鉴权），进程内缓存
    inst_id = inst_name if "-SWAP" in inst_name else f"{inst_name}-USDT-SWAP"
    if inst_id in _CTVAL_CACHE:
        return _CTVAL_CACHE[inst_id]
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://www.okx.com/api/v5/public/instruments?instType=SWAP&instId={inst_id}",
            headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        rows = payload.get("data") or []
        ct = float(rows[0].get("ctVal", 1.0) or 1.0) if rows else 1.0
    except Exception:
        ct = 1.0
    _CTVAL_CACHE[inst_id] = ct
    return ct

def fetch_binance_closed_trades(environment: str = "demo", tz_bj=None) -> list:
    """拉取币安真实平仓盈亏台账（/fapi/v1/income REALIZED_PNL + /fapi/v1/userTrades）。"""
    if tz_bj is None:
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    out = []
    try:
        from r20_backend.exchanges import get_adapter
        ad_bn = get_adapter("binance", environment=environment)
        income_rows = ad_bn.signed_request("GET", "/fapi/v1/income", params={"incomeType": "REALIZED_PNL", "limit": 100})
        if not income_rows or not isinstance(income_rows, list):
            return []

        symbols = sorted(set(r.get("symbol", "") for r in income_rows if r.get("symbol")))
        user_trades_by_id = {}
        for sym in symbols:
            try:
                ut = ad_bn.signed_request("GET", "/fapi/v1/userTrades", params={"symbol": sym, "limit": 50})
                for t in (ut or []):
                    user_trades_by_id[str(t.get("id"))] = t
            except Exception:
                pass

        for r in income_rows:
            t_id = str(r.get("tradeId") or r.get("tranId") or "")
            time_ms = int(r.get("time", 0) or 0)
            pnl = round(float(r.get("income", 0) or 0), 4)
            symbol = str(r.get("symbol", "")).upper()
            base = symbol.replace("USDT", "").replace("_USDT", "")
            close_time = datetime.datetime.fromtimestamp(time_ms / 1000.0, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S")

            matched = user_trades_by_id.get(t_id) or {}
            side_raw = str(matched.get("side", "")).upper()
            side = "多" if side_raw == "SELL" else ("空" if side_raw == "BUY" else "多")
            close_px = float(matched.get("price", 0) or 0)
            sz = float(matched.get("qty", 0) or 0)
            fee = round(abs(float(matched.get("commission", 0) or 0)), 4)
            lever = 2
            margin = round(sz * close_px / lever, 2) if (sz > 0 and close_px > 0) else 50.0
            net_pnl = round(pnl - fee, 2)
            roi_pct = round((pnl / max(1.0, margin)) * 100, 2)

            out.append({
                "id": f"binance_closed_{t_id}_{time_ms}",
                "inst": base,
                "side": side,
                "venue": "binance",
                "account_mode": environment.upper(),
                "environment": environment.lower(),
                "lever": f"{lever}x",
                "strategy": "🏛️ Binance",
                "margin": margin,
                "sz": sz,
                "open_time": close_time,
                "open_px": close_px,
                "close_time": close_time,
                "close_px": close_px,
                "gross_pnl": pnl,
                "fee": fee,
                "pnl": net_pnl,
                "net_pnl": net_pnl,
                "roi": roi_pct,
                "roi_pct": roi_pct,
                "duration": "0时0分",
                "status": "closed",
                "exit_reason": "🎯 目标止盈达成" if net_pnl > 0 else "🛑 触发云端止损"
            })
    except Exception as exc:
        _mark("binance", "failed", reason=str(exc)[:200])
        print(f"[sync_full_ledger] warn Binance 台账同步跳过: {exc}")
    return out


def fetch_gate_closed_trades(environment: str = "sandbox", tz_bj=None) -> list:
    """拉取 Gate 真实平仓记录（/api/v4/futures/usdt/position_close）。"""
    if tz_bj is None:
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    out = []
    try:
        from r20_backend.exchanges import get_adapter
        ad_gate = get_adapter("gate", environment=environment)
        close_rows = ad_gate.signed_request("GET", "/api/v4/futures/usdt/position_close", params={"limit": 100})
        if not close_rows or not isinstance(close_rows, list):
            return []

        for r in close_rows:
            close_id = str(r.get("id") or "")
            contract = str(r.get("contract", "")).upper()
            base = contract.replace("_USDT", "").replace("USDT", "")
            pnl = round(float(r.get("pnl", 0) or 0), 4)
            fee = round(abs(float(r.get("fee", 0) or 0)), 4)
            net_pnl = round(float(r.get("pnl_pnl", pnl) or pnl), 2)
            time_sec = int(r.get("time", 0) or 0)
            close_time = datetime.datetime.fromtimestamp(time_sec, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S")
            first_open = int(r.get("first_open_time", 0) or 0)
            open_time = datetime.datetime.fromtimestamp(first_open, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S") if first_open else close_time

            side = "多" if float(r.get("long_price") or 0) > 0 else "空"
            open_px = float(r.get("long_price") or r.get("short_price") or 0)
            close_px = float(r.get("short_price") if side == "多" else r.get("long_price") or 0)
            sz = abs(float(r.get("accum_size", 0) or 0))
            lever = 2
            margin = round(sz * (open_px or close_px) / lever, 2) if sz > 0 else 50.0
            roi_pct = round((net_pnl / max(1.0, margin)) * 100, 2)

            out.append({
                "id": f"gate_closed_{close_id}_{time_sec}",
                "inst": base,
                "side": side,
                "venue": "gate",
                "account_mode": "DEMO" if environment == "sandbox" else "LIVE",
                "environment": "demo" if environment == "sandbox" else "live",
                "lever": f"{lever}x",
                "strategy": "🏛️ Gate",
                "margin": margin,
                "sz": sz,
                "open_time": open_time,
                "open_px": open_px,
                "close_time": close_time,
                "close_px": close_px,
                "gross_pnl": pnl,
                "fee": fee,
                "pnl": net_pnl,
                "net_pnl": net_pnl,
                "roi": roi_pct,
                "roi_pct": roi_pct,
                "duration": "0时0分",
                "status": "closed",
                "exit_reason": "🎯 目标止盈达成" if net_pnl > 0 else "🛑 触发云端止损"
            })
    except Exception as exc:
        _mark("gate", "failed", reason=str(exc)[:200])
        print(f"[sync_full_ledger] warn Gate 台账同步跳过: {exc}")
    return out


def _history_truncated_in_scope(truncated, oldest_ms, reset_time, tz_bj):
    """分页未取尽时，判断「是否仍可能漏掉在册记录」。

    台账只收 `close_time >= reset_time` 的记录（build 内同判据，见 build_lifecycle_ledger）。
    因此：取到的最早记录若已早于基线，未取尽的部分不可能含在册记录 → 不算截断。
    批C(2026-09-13)：若无此判定，max_pages 上限会让 data_health 永久挂一条假 PARTIAL
    （实测 500 条时最早到 05-15，而基线是 09-11，台账其实一条不漏），真正的取数失败
    反而淹没在常驻噪声里。
    取不到最早时间（oldest_ms<=0）时保守判为截断。
    """
    if not truncated:
        return False
    try:
        _ms = int(oldest_ms or 0)
    except Exception:
        _ms = 0
    if _ms <= 0:
        return True
    try:
        _t = datetime.datetime.fromtimestamp(_ms / 1000.0, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return True
    return _t >= str(reset_time)


def _other_venue_live_positions(env_axis):
    """binance/gate 活动持仓，归一成与 OKX 同形的字段（与仪表盘同一事实源：
    r20_backend.exchanges.get_adapter）。

    批E(2026-09-13·用户报「台账和活动持仓对不上」)：台账 holding 行原本**只由
    okx_rest.positions() 生成**（builder 全源 OKX V5），于是活动持仓面板显示 6 条
    binance 持仓时，台账只有 1 条 OKX 的——用户在两个页面看到两个事实。

    返回 (items, ok_venues)。ok_venues **只含真正取数成功的场所**：清理失效 holding
    行必须以它为闸，取数失败时宁留旧行——「不知道」绝不能渲染成「已平仓」。
    """
    items: list = []
    ok_venues: set = set()
    try:
        from r20_backend.exchanges import get_adapter
    except Exception:
        return items, ok_venues
    for v_name in ("binance", "gate"):
        try:
            ad = get_adapter(v_name, environment=env_axis)
            v_positions = ad.positions() if hasattr(ad, "positions") else []
        except Exception as _e:
            print(f"[sync_full_ledger] {v_name} 活动持仓取数失败（保守跳过，不清旧行）: {str(_e)[:120]}")
            continue
        ok_venues.add(v_name)
        for vp in (v_positions or []):
            try:
                amt = float(vp.get("size_signed", 0) or 0)
            except (TypeError, ValueError):
                continue
            if abs(amt) < 1e-12:
                continue
            base = str(vp.get("base") or vp.get("symbol", "")).replace("USDT", "").replace("_USDT", "").upper()
            if not base:
                continue
            v_side = str(vp.get("side") or ("long" if amt > 0 else "short")).lower()
            items.append({
                "venue": v_name,
                "instId": f"{base}-USDT-SWAP",
                "posSide": v_side,
                "pos": abs(amt),
                "avgPx": float(vp.get("entry_price", 0) or 0),
                "markPx": float(vp.get("mark_price", 0) or vp.get("entry_price", 0) or 0),
                "upl": float(vp.get("unrealized_pnl", 0) or 0),
                "lever": vp.get("leverage", 3) or 3,
                "fee": 0.0,
                "cTime": vp.get("open_time") or vp.get("cTime") or 0,
            })
    return items, ok_venues


def _holding_row(p, venue, *, env, trackers, tz_bj, allowed, council_by_inst):
    """活动持仓 → 台账 holding 行（OKX 与 binance/gate 共用同一构造器，字段语义一致）。

    id 带场所：`holding_{venue}_{inst}_{side}`。旧式 `holding_{inst}_{side}` 不含场所，
    多所同时持有同一标的即撞键（后写覆盖先写）。
    """
    pos_sz = float(p.get("pos", 0.0) or 0.0)
    if pos_sz == 0.0:
        return None
    inst_id = p.get("instId", "")
    if inst_id not in allowed:
        return None
    inst = inst_id.replace("-USDT-SWAP", "")
    side_raw = str(p.get("posSide", p.get("side", ""))).lower()
    # 审计 C8：net-mode 行 posSide="net"，旧式 `"long" in side_raw` 恒 False
    # → 净模式多仓被系统性标成"空"（策略/追踪 join 全错位）。按符号回退判向，
    # 符号不可判 → 诚实标"未知"，绝不猜。
    if "long" in side_raw:
        side = "多"
    elif "short" in side_raw:
        side = "空"
    else:
        try:
            _signed = float(p.get("pos", 0) or 0)
        except (TypeError, ValueError):
            _signed = 0.0
        side = "多" if _signed > 0 else ("空" if _signed < 0 else "未知")
    avg_px = float(p.get("avgPx", 0) or 0)
    mark_px = float(p.get("markPx", 0) or 0)
    upl = float(p.get("upl", 0) or 0)
    try:
        lever = int(float(p.get("lever", "3") or 3))
    except (TypeError, ValueError):
        lever = 3
    fee = float(p.get("fee", 0.0) or 0.0)
    ct_val = get_ct_val(inst)

    notional = pos_sz * ct_val * mark_px
    margin_usdt = round(notional / lever, 2) if lever > 0 else round(notional, 2)
    roi_pct = round((upl / margin_usdt * 100) if margin_usdt > 0 else 0.0, 2)

    _c_raw = p.get("cTime", 0) or 0
    try:
        c_ts = float(_c_raw) / 1000.0
    except (TypeError, ValueError):
        c_ts = 0.0
    open_time = datetime.datetime.fromtimestamp(c_ts, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S") if c_ts > 0 else "--"

    pos_k = f"{inst_id}_{'long' if side == '多' else 'short'}"
    t_info = trackers.get(pos_k, {})
    strat_tag = t_info.get("strategy_tag") or ("🌊 低吸" if side == "多" else "⚡ 高空")

    try:
        t1 = datetime.datetime.strptime(open_time, "%Y-%m-%d %H:%M:%S")
        now_dt = datetime.datetime.now(tz_bj)
        dur_mins = int((now_dt - t1).total_seconds() / 60)
        duration_str = f"{dur_mins}分钟" if dur_mins < 60 else f"{dur_mins//60}时{dur_mins%60}分"
    except Exception:
        duration_str = "--"

    return {
        "id": f"holding_{venue}_{inst}_{side}",
        "inst": inst,
        "side": side,
        "venue": venue,
        "account_mode": env.mode.upper(),
        "environment": env.mode.lower(),
        "lever": f"{lever}x",
        "strategy": strat_tag,
        "margin": margin_usdt,
        "sz": pos_sz,
        "open_time": open_time,
        "open_px": avg_px,
        "close_time": "持仓中...",
        "close_px": mark_px,
        "gross_pnl": round(upl, 2),
        "open_fee": round(fee, 4),
        "close_fee": 0.0,
        "fee": round(fee, 2),
        "funding_fee": 0.0,
        "pnl": round(upl, 2),
        "net_pnl": round(upl, 2),
        "roi_pct": roi_pct,
        "duration": duration_str,
        "status": "holding",
        "exit_reason": "⏳ 运行监控中",
        "council": council_by_inst.get(inst),
    }


def build_lifecycle_ledger():
    reset_time = "1970-01-01 00:00:00"
    if os.path.exists(INITIAL_STATE_FILE):
        try:
            with open(INITIAL_STATE_FILE, "r", encoding="utf-8") as f:
                acc = json.load(f)
                reset_time = acc.get("reset_time", "1970-01-01 00:00:00")
        except Exception:
            pass

    existing_closed_ids = set()
    old_trades = []
    if os.path.exists(LEDGER_JSON_FILE):
        try:
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                old_trades = json.load(f)
                existing_closed_ids = {t["id"] for t in old_trades if t.get("status") == "closed"}
        except Exception:
            old_trades = []

    # 重建白名单 = 当前池 ∪ 历史留痕（SQLite/旧台账/持仓追踪），下架币种历史永久保留
    allowed = allowed_inst_ids(old_trades)

    trackers = {}
    if os.path.exists(POSITION_TRACKER_FILE):
        try:
            with open(POSITION_TRACKER_FILE, "r", encoding="utf-8") as f:
                trackers = json.load(f)
        except Exception:
            pass

    # 投委会溯源（2026-09-10）：持仓行的决策来源徽章来自最新 per-symbol 决策缓存。
    # 历史平仓行不伪造该数据——开仓当周期的委员会状态从未持久化，缺失就显示缺失。
    council_by_inst = {}
    try:
        with open(os.path.join(DATA_DIR, "ai_brain_decisions.json"), "r", encoding="utf-8") as f:
            _brain_cache = json.load(f)
        for _k, _v in (_brain_cache or {}).items():
            if not isinstance(_v, dict):
                continue
            _c = _v.get("council")
            if isinstance(_c, dict):
                _name = str(_v.get("name") or str(_k).split("-")[0])
                council_by_inst[_name] = _c
    except Exception:
        council_by_inst = {}

    tz_bj = datetime.timezone(datetime.timedelta(hours=8))

    env = okx_runtime.current_environment()
    if not env.configured:
        raise okx_rest.OKXNotConfigured("OKX API Key 未配置 — 台账同步 fail-closed（既有 trading_ledger.json 保持不动）")
    pos_history = []
    pos_data = []
    close_orders = []
    # 批E：显式记录「活动持仓取数是否成功」——空列表既可能是「确无持仓」也可能是
    # 「取数失败」，二者对清理幽灵持仓的含义完全相反（成功才允许清理）。
    _okx_positions_ok = False

    try:
        # 批C(2026-09-13)：分页取尽。原单页 limit=100 即止 —— 平仓越 100 笔后更早记录
        # 永久取不到，且每轮都挂「触顶 limit=100」常驻告警。truncated 仍由分页器诚实给出
        # （取不尽才标），不再用 len>=100 反推。
        pos_history, _ph_trunc = _fetch_history_paged(okx_rest.positions_history, id_field="posId")
        pos_data = okx_rest.positions() or []
        _okx_positions_ok = True
        orders_history, _oh_trunc = _fetch_history_paged(okx_rest.orders_history, id_field="ordId")
        close_orders = [o for o in orders_history if str(o.get('reduceOnly', '')).lower() == 'true' and o.get('state') == 'filled']
        # 截断判定按「在册窗口」收口：取到的最早记录若已早于 reset_time，未取尽的部分
        # 不可能含在册记录 → 不标截断（否则分页上限会让 data_health 永久假 PARTIAL）。
        _ph_old = min((int(r.get("uTime") or 0) for r in pos_history), default=0)
        _oh_old = min((int(r.get("uTime") or r.get("cTime") or 0) for r in orders_history), default=0)
        _okx_trunc = bool(
            _history_truncated_in_scope(_ph_trunc, _ph_old, reset_time, tz_bj)
            or _history_truncated_in_scope(_oh_trunc, _oh_old, reset_time, tz_bj)
        )
        _mark("okx", "partial" if _okx_trunc else "ok",
              **({"truncated_at": 100} if _okx_trunc else {}))
    except Exception as _okx_err:
        _mark("okx", "failed", reason=str(_okx_err)[:200])
        print(f"[sync_full_ledger] OKX 台账同步跳过: {_okx_err}")

    trades_lifecycle = []

    # Process Active Holding Positions FIRST（批E·多所）
    # 用户报「台账和活动持仓对不上」根因：本 builder 全源 OKX V5，holding 行只由
    # okx_rest.positions() 生成——活动持仓面板显示 6 条 binance 持仓时台账只有 1 条
    # OKX 的；而旧行靠 id 合并续命，OKX 平掉后那条 holding 行永不消失（幽灵持仓）。
    _holding_rows = []
    _queried_venues = set()
    if _okx_positions_ok:
        _queried_venues.add("okx")
    for p in pos_data:
        _row = _holding_row(p, "okx", env=env, trackers=trackers, tz_bj=tz_bj,
                            allowed=allowed, council_by_inst=council_by_inst)
        if _row:
            _holding_rows.append(_row)

    _other_positions, _ok_venues = _other_venue_live_positions(env.mode)
    _queried_venues |= _ok_venues
    for p in _other_positions:
        _row = _holding_row(p, str(p.get("venue") or ""), env=env, trackers=trackers, tz_bj=tz_bj,
                            allowed=allowed, council_by_inst=council_by_inst)
        if _row:
            _holding_rows.append(_row)

    trades_lifecycle.extend(_holding_rows)

    # Process Official Closed Positions
    # 审计批7(2026-09-13)·同 posId 多轮往返吞腿修复：PEPE 当日两笔平仓（06:33→10:31
    # +7.89、15:37→16:30 -18.18）在 OKX positions-history 里**共享同一 posId**
    # (391748010248)——旧 `id=pos_hist_{posId}_{inst}` 撞键，合并进 trades_map 时后者
    # 覆盖前者，一条真实亏损从台账蒸发（前台与台账对不上的根因之一）。id 追加开仓
    # 时刻 c_ts + 同键自增序号，保证「每一笔平仓」有唯一稳定身份。
    _pos_id_seen: dict = {}
    for h in pos_history:
        c_ts = int(h.get("cTime", 0) or 0) / 1000.0
        u_ts = int(h.get("uTime", 0) or 0) / 1000.0
        open_time = datetime.datetime.fromtimestamp(c_ts, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S") if c_ts > 0 else "--"
        close_time = datetime.datetime.fromtimestamp(u_ts, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S") if u_ts > 0 else "--"

        if close_time < reset_time:
            continue

        inst_id = h.get("instId", "")
        if inst_id not in allowed:
            continue
        inst = inst_id.replace("-USDT-SWAP", "")
        direction = str(h.get("direction", "")).lower()
        side = "多" if "long" in direction else "空"
        
        open_px = float(h.get("openAvgPx", 0) or 0)
        close_px = float(h.get("closeAvgPx", 0) or 0)
        gross_pnl = float(h.get("pnl", 0) or 0)
        fee = float(h.get("fee", 0) or 0)
        net_pnl = round(gross_pnl + fee, 2)
        lever = int(float(h.get("lever", "3") or 3))
        
        # Calculate Margin & Real Position Size
        ct_val = get_ct_val(inst)
        close_pos_sz = float(h.get("closeTotalPos", 0) or h.get("openMaxPos", 0) or 0)
        
        if close_pos_sz > 0 and open_px > 0 and ct_val > 0:
            notional = close_pos_sz * ct_val * open_px
            margin_usdt = round(notional / lever, 2) if lever > 0 else round(notional, 2)
        else:
            pnl_ratio = float(h.get("pnlRatio", 0) or 0)
            margin_usdt = 500.0 # Standard fallback
            if pnl_ratio != 0:
                est_margin = abs(gross_pnl / pnl_ratio)
                margin_usdt = round(est_margin, 2)
        
        roi_pct = round((net_pnl / margin_usdt * 100) if margin_usdt > 0 else 0.0, 2)

        # Duration
        try:
            t1 = datetime.datetime.strptime(open_time, "%Y-%m-%d %H:%M:%S")
            t2 = datetime.datetime.strptime(close_time, "%Y-%m-%d %H:%M:%S")
            dur_mins = int((t2 - t1).total_seconds() / 60)
            duration_str = f"{dur_mins}分钟" if dur_mins < 60 else f"{dur_mins//60}时{dur_mins%60}分"
        except Exception:
            duration_str = "--"

        # Strategy tag
        strat_tag = "🌊 顺势做多" if side == "多" else "⚡ 阻力高空"
        
        # Accurate Exit Reason Inference via Matched Close Order Attributes
        exit_type = str(h.get("type", ""))
        if exit_type == "3":
            exit_reason = "💥 强平出场"
        else:
            # Match filled close order within 5000ms window
            u_ms = int(h.get("uTime", 0) or 0)
            matched_close = next(
                (o for o in close_orders if o.get("instId") == inst_id and o.get("posSide") == direction and abs(int(o.get("uTime", 0) or 0) - u_ms) < 5000),
                None
            )
            if matched_close:
                algo_id = matched_close.get("algoId")
                cl_ord_id = str(matched_close.get("clOrdId", ""))
                
                if algo_id:
                    if net_pnl > 3.0:
                        exit_reason = "🎯 目标止盈达成"
                    elif net_pnl < -1.0:
                        exit_reason = "🛑 触发云端止损"
                    else:
                        exit_reason = "🛡️ 移动止损保本出场"
                elif cl_ord_id.startswith("O") or "CLI" in matched_close.get("tag", ""):
                    if net_pnl > 3.0:
                        exit_reason = "✨ 移动止盈锁利"
                    elif net_pnl < -1.0:
                        exit_reason = "🛑 策略风控止损"
                    else:
                        exit_reason = "⏱️ 超时/保本平仓"
                else:
                    exit_reason = "🎯 目标止盈达成" if net_pnl > 3.0 else ("🛑 止损离场" if net_pnl < -1.0 else "🛡️ 保本平仓")
            else:
                exit_reason = "🎯 目标止盈达成" if net_pnl > 3.0 else ("🛑 止损出场" if net_pnl < -1.0 else "🛡️ 保本平仓")

        funding_fee = round(float(h.get("fundingFee") or 0.0), 4)

        # 审计 D8：去重键原嵌 u_ts（持仓最后更新时间）——同一笔平仓被 OKX 改写
        # uTime（如补算资金费/结算修正）时 id 漂移，与旧行按 id 去重失败 → 同笔
        # 重复计入台账/日亏。改用不可变 posId，缺失时退回开仓时刻 c_ts（同样稳定）。
        _stable = str(h.get("posId") or "").strip() or (str(int(c_ts)) if c_ts > 0 else str(int(u_ts)))
        # 审计批7：posId 会在多轮往返间复用（见上方注释），故 id 追加开仓时刻 c_ts
        # 区分同 posId 的不同轮；同 (posId,c_ts) 仍多笔时再挂自增序号兜底，绝不再撞键。
        _key = f"{_stable}|{int(c_ts)}"
        _seq = _pos_id_seen.get(_key, 0)
        _pos_id_seen[_key] = _seq + 1
        _id_suffix = f"_{int(c_ts)}" + (f"#{_seq}" if _seq else "")
        trades_lifecycle.append({
            "id": f"pos_hist_{_stable}_{inst}{_id_suffix}",
            "inst": inst,
            "side": side,
            "venue": "okx",   # G10：同上，OKX 历史行源头标注
            "account_mode": env.mode.upper(),
            "environment": env.mode.lower(),
            "lever": f"{lever}x",
            "strategy": strat_tag,
            "margin": margin_usdt,
            "sz": round(close_pos_sz, 4),
            "open_time": open_time,
            "open_px": round(open_px, 4),
            "close_time": close_time,
            "close_px": round(close_px, 4),
            "gross_pnl": round(gross_pnl, 2),
            "open_fee": round(fee / 2.0, 4),
            "close_fee": round(fee / 2.0, 4),
            "fee": round(fee, 2),
            "funding_fee": funding_fee,
            "pnl": net_pnl,
            "net_pnl": net_pnl,
            "roi": roi_pct,
            "roi_pct": roi_pct,
            "duration": duration_str,
            "status": "closed",
            "exit_reason": exit_reason
        })

    # 多所台账协同（US-009 / v7.9.1）：自动并发拉取 Binance 与 Gate 真实平仓盈亏
    # 审计 A2：fetch 内部吞异常（except 内 _mark failed）——调用点为未标失败的所
    # 记 ok，并携带行数与 limit=100 截断风险标记，供旁车/data_health 诚实呈现。
    binance_trades = fetch_binance_closed_trades("demo" if env.simulated else "live", tz_bj=tz_bj)
    gate_trades = fetch_gate_closed_trades("sandbox" if env.simulated else "live", tz_bj=tz_bj)
    for _v, _rows in (("binance", binance_trades), ("gate", gate_trades)):
        if _FETCH_STATUS.get(_v, {}).get("status") != "failed":
            _mark(_v, "ok", rows=len(_rows), truncated=len(_rows) >= 100)

    # 聚合去重合并（按 id 去重，按 close_time 降序）
    trades_map = {}
    for t in old_trades:
        if t.get("id"):
            trades_map[t["id"]] = t

    # 审计 D8 迁移：去重键由 u_ts 换为 posId 后首跑，同一笔持仓的新旧行 id 不同
    # 会并存双计。对 okx 历史行按 (venue, inst, open_time, close_time) 稳定签名
    # 撞键——旧键行让位于本轮再生成的新键行；窗口外无法再生的旧行一律不动（防迁移误删）。
    def _sig(t):
        return (str(t.get("venue") or ""), str(t.get("inst") or ""),
                str(t.get("open_time") or ""), str(t.get("close_time") or ""))
    _new_sigs = {_sig(t) for t in trades_lifecycle}
    for _oid in [k for k, v in trades_map.items()
                 if str(k).startswith("pos_hist_") and isinstance(v, dict) and _sig(v) in _new_sigs]:
        trades_map.pop(_oid)

    for t in (trades_lifecycle + binance_trades + gate_trades):
        if t.get("id"):
            trades_map[t["id"]] = t

    # 批E·幽灵持仓清理：台账 holding 行必须以「本轮成功取数的场所的实时持仓」为准。
    # 旧实现只按 id 覆盖新行、从不删除失效行 → 平仓后 holding 行永久留存（实测
    # holding_ALGO_多 标 venue=okx 而 OKX 已零持仓，前台台账里挂着一条不存在的仓）。
    # 仅对 _queried_venues 内的场所生效：取数失败的场所保守保留旧行（缺失≠已平仓）。
    _live_holding_ids = {t["id"] for t in _holding_rows}
    _purged_holdings = []
    for _oid in [k for k, v in trades_map.items()
                 if isinstance(v, dict) and v.get("status") == "holding"
                 and str(v.get("venue") or "").lower() in _queried_venues
                 and k not in _live_holding_ids]:
        trades_map.pop(_oid)
        _purged_holdings.append(_oid)
    if _purged_holdings:
        print(f"[sync_full_ledger] 清理失效持仓行 {len(_purged_holdings)} 条："
              f"{', '.join(_purged_holdings[:8])}")

    combined_trades = sorted(
        trades_map.values(),
        key=lambda x: str(x.get("close_time") or x.get("time") or x.get("open_time") or ""),
        reverse=True
    )

    fd, tmp_path = tempfile.mkstemp(prefix=".ledger-", suffix=".tmp", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(combined_trades, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, LEDGER_JSON_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # 审计 A2：台账原子写成功后同步落逐所状态旁车（读侧容错缺文件）。
    _write_sync_status(env)

    # Notify newly closed trades via QQ
    try:
        from qq_notifier import notify_trade_close
        for t in (trades_lifecycle + binance_trades + gate_trades):
            if t["id"] not in existing_closed_ids and t.get("status") == "closed":
                notify_trade_close(
                    inst=t.get("inst", "CRYPTO"),
                    pnl=float(t.get("pnl", 0.0) or 0.0),
                    stage=t.get("exit_reason", "平仓结清"),
                    exit_px=float(t.get("close_px", 0.0) or 0.0),
                    roi_pct=float(t.get("roi_pct", 0.0) or 0.0),
                    duration_str=str(t.get("duration", "")),
                )
    except Exception as e:
        print(f"[Ledger Sync Notify Warning] {e}")

    # 批E：trades_lifecycle 现含「OKX 平仓 + 全场所活动持仓」，输出必须分开报，
    # 否则「OKX: 12」会把 binance 的 6 条持仓算进 OKX 业绩里（口径自欺）。
    _okx_closed_n = sum(1 for t in trades_lifecycle if t.get("status") != "holding")
    print(f"✅ Authentic Multi-Venue Ledger: {len(combined_trades)} total trades "
          f"(OKX 平仓: {_okx_closed_n}, 活动持仓: {len(_holding_rows)}, "
          f"Binance 平仓: {len(binance_trades)}, Gate 平仓: {len(gate_trades)}).")
    return combined_trades

if __name__ == "__main__":
    try:
        build_lifecycle_ledger()
    except okx_rest.OKXNotConfigured as exc:
        print(f"[NOT READY] {exc}")
        raise SystemExit(3)
