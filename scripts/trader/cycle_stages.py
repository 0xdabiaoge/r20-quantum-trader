"""execute_portfolio 的阶段函数（B3 抽取·第九十一刀）。

从 `scripts/ai_factor_trader.py::execute_portfolio`（294 行）中
**纯搬家**两段：

| 函数 | 段长 | 原相位 |
|---|---|---|
| `fetch_universe_and_manage_positions` | 14 行 | 相位 2-3：并发取标的池因子 + 逐仓追踪止损退出 |
| `persist_state_and_sync_ledger` | 30 行 | 相位 5-6：面板状态持久化 + 生命周期台账/SQLite 实时同步 |
| `fetch_positions_and_reconcile` | 115 行 | 相位 1：取真实持仓 + 合约对账 + 跨所汇总 + 挂单盲区守卫 + 预留对账（**4 处 `return None` = 本周期中止**；13 项输出） |
| `preflight_reconcile_and_housekeeping` | 26 行 | 相位 0/0a：引擎就绪闸 + 挂单对账 + 陈旧单回收 + 舆情采集（**段内 `return None` = 本周期中止**） |

## 准入判据（沿用第九十刀定式）

两段均 **0 个 `return`、0 个 `break`**；段内写入的外围量要么作为返回值回传，
要么无人再读（`persist_state_and_sync_ledger` 无输出 ⇒ 纯副作用段）。
所有自由名（外围局部量 + 门面全局）一律**同名 kw-only 入参** ⇒ 段体 **AST 逐字**。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple


def fetch_universe_and_manage_positions(*,
        all_positions,
        real_pos_dict,
        timestamp_full,
        usdt_available,
        TARGET_INSTRUMENTS,
        ThreadPoolExecutor,
        fetch_single_instrument_data,
        load_trackers,
        manage_position_tp_and_trailing,
        prune_trackers,
        save_trackers):
    with ThreadPoolExecutor(max_workers=len(TARGET_INSTRUMENTS)) as executor:
        all_factors = list(executor.map(lambda item: fetch_single_instrument_data(item, all_positions, usdt_available), TARGET_INSTRUMENTS))

    # 3. Process Positions & Dynamic Trailing Exits
    executed_actions = []
    trackers = load_trackers()
    stale_tracker_count = prune_trackers(trackers, real_pos_dict)
    if stale_tracker_count:
        executed_actions.append(f"清理 {stale_tracker_count} 条已失效持仓追踪记录")
    for f in all_factors:
        curr_pos = f["position"]
        if curr_pos:
            manage_position_tp_and_trailing(f, curr_pos, trackers, timestamp_full, executed_actions)
    save_trackers(trackers)
    # ⚠️ 不返回 `f`：原文段后对 `f` 的那次读（`f.write(log_entry)`）是
    # `with open(LOG_FILE) as f` **自己绑定的文件句柄**，与标的字典无关
    # （首版误判为外围输出，冒烟例当场抓出 UnboundLocalError）。
    return (all_factors, executed_actions, trackers)


def persist_state_and_sync_ledger(*,
        _xv_total,
        active_pos_count,
        all_factors,
        cb_active,
        cb_reason,
        executed_actions,
        long_count,
        short_count,
        timestamp_full,
        DATA_DIR,
        LEDGER_AUTOSYNC_ENABLED,
        LOG_FILE,
        MAX_CONCURRENT_POSITIONS,
        WORKSPACE_DIR,
        __version__,
        _atomic_write_json,
        _run_captured,
        build_state_payload,
        evaluate_asset_signal,
        os):
    state_payload = build_state_payload(
        timestamp_full=timestamp_full, active_pos_count=active_pos_count,
        max_positions=MAX_CONCURRENT_POSITIONS, long_count=long_count,
        short_count=short_count, cb_active=cb_active, cb_reason=cb_reason,
        executed_actions=executed_actions, all_factors=all_factors,
        evaluate_asset_signal=evaluate_asset_signal)

    # 审计③：原子替换（读者=面板/巡检；旧直写有撕裂窗）。异常语义不变：照旧上抛。
    _atomic_write_json(os.path.join(DATA_DIR, "trading_state.json"), state_payload)

    # 6. Always Sync Full Lifecycle Ledger and SQLite DB in Realtime
    # 批E(2026-09-13)·测试封闭闸：这两条 spawn 会打三所接口并**重写生产台账/数据库**。
    # 测试若在进程内跑一轮交易员巡检（多处如此），就会连带改写 data/trading_ledger.json
    # 与 SQLite——违反「测试不触生产文件」。tests/__init__.py 在任何测试模块导入前置位
    # R20_LEDGER_SYNC_DISABLED=1，下面的模块级快照即 False；生产不设 → 行为不变。
    if LEDGER_AUTOSYNC_ENABLED:
        try:
            sync_script = os.path.join(WORKSPACE_DIR, "scripts", "sync_full_ledger.py")
            if os.path.exists(sync_script):
                _run_captured(sync_script)
            db_script = os.path.join(WORKSPACE_DIR, "scripts", "db_manager.py")
            if os.path.exists(db_script):
                _run_captured(db_script)
        except Exception as e:
            print(f"[Ledger Sync Warning] {e}")

    log_entry = f"[{timestamp_full}] ⚡ R20 Quantum Trader v{__version__} 巡检完成 | 持仓 OKX {active_pos_count}/{MAX_CONCURRENT_POSITIONS} (多{long_count}/空{short_count})｜跨所 {_xv_total if _xv_total is not None else '未知'} 笔 | 动作: {', '.join(executed_actions) if executed_actions else '无开平仓操作'}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(log_entry.strip())


def preflight_reconcile_and_housekeeping(*,
        WORKSPACE_DIR,
        _run_captured,
        clean_stale_open_orders,
        current_environment,
        datetime,
        load_trackers,
        os,
        reconcile_pending_orders):
    """相位 0/0a：引擎就绪闸 + 挂单对账 + 陈旧单回收 + 舆情采集。

    段内 `return None` 语义 = **本周期中止** ⇒ 调用点据此提前 `return None`。
    """
    _engine_env = current_environment()
    if not _engine_env.configured:
        print(f"[Engine NOT READY] OKX {_engine_env.mode.upper()} API Key 未配置：V5 直签是唯一交易通道，本周期拒绝交易。")
        return None
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_dt = datetime.datetime.now(tz_bj)
    timestamp_full = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 0a. US-006 周期级挂单对账：重启/新周期接管或撤销存量挂单（在新增下单之前）
    reconcile_ok, reconciled_kept_ord_ids = reconcile_pending_orders(trackers=load_trackers())
    if not reconcile_ok:
        # fail-closed：仅禁止本周期新增下单（不是清库），持仓管理照常执行
        print("[挂单对账] fail-closed：本周期禁止新增下单（对账失败，不清库）")
    entries_blocked = not reconcile_ok

    # 0. Clean Stale Open Orders & Harvest Real-time News Sentiment
    orders_ok, orders_error = clean_stale_open_orders(keep_ord_ids=reconciled_kept_ord_ids)
    if not orders_ok:
        print(f"[Trader] Abort: unable to verify/cancel stale open orders: {orders_error}")
        return None
    try:
        harvester_script = os.path.join(WORKSPACE_DIR, "scripts", "news_sentiment_harvester.py")
        if os.path.exists(harvester_script):
            _run_captured(harvester_script, label="news_harvester", timeout=25)
    except Exception as e:
        print(f"News Harvester sync warning: {e}")
    return (entries_blocked, timestamp_full)


def fetch_positions_and_reconcile(*,
        entries_blocked,
        _BROKEN_VENUES,
        collect_pending_inst_ids,
        current_environment,
        fetch_other_venue_positions,
        load_instruments,
        okx_rest,
        query_positions,
        reconcile_reservation_ledger,
        venue_execution_ready,
        venue_registry):
    """相位 1：取真实持仓 + 合约对账 + 跨所汇总 + 挂单盲区守卫 + 预留对账。

    段内 4 处 `return None` 语义 = **本周期中止**（调用点判 None 后 `return None`）。
    `entries_blocked` 是 **in-out**：段内只在"跨所读取失败"分支里被置 True，
    其余路径不碰它 —— 若不把上游（preflight）的值传进来，未命中分支时它会
    **未绑定**（首版即如此，空世界 smoke 当场抓出 `UnboundLocalError`）。
    其余 12 项输出在本段内均"必然绑定"（确定赋值分析），无需入参。
    """
    positions_ok, all_positions, positions_error = query_positions()
    if not positions_ok:
        print(f"[Trader] Abort: unable to verify exchange positions: {positions_error}")
        return None
    real_pos_dict = {}
    real_long_count = 0
    real_short_count = 0

    if isinstance(all_positions, list):
        for p in all_positions:
            pos_sz = float(p.get("pos", 0) or 0)
            if pos_sz > 0:
                side = p.get("posSide", "net").lower()
                inst_id = p.get("instId")
                if inst_id in real_pos_dict:
                    print(f"[Trader] Abort: simultaneous long/short positions for {inst_id} are not supported")
                    return None
                real_pos_dict[inst_id] = p
                if "long" in side:
                    real_long_count += 1
                elif "short" in side:
                    real_short_count += 1

    active_pos_count = len(real_pos_dict)
    long_count = real_long_count
    short_count = real_short_count

    try:
        pending_orders = okx_rest.pending_orders()
    except Exception as pending_exc:
        print(f"[Trader] Abort: unable to verify pending orders: {pending_exc}")
        return None
    pending_inst_ids = set()
    pending_long_count = 0
    pending_short_count = 0
    if isinstance(pending_orders, list):
        for order in pending_orders:
            if str(order.get("state", "live")).lower() not in {"live", "partially_filled"}:
                continue
            inst_id = str(order.get("instId", ""))
            if inst_id:
                pending_inst_ids.add(inst_id)
            pos_side = str(order.get("posSide", "")).lower()
            if pos_side == "long":
                pending_long_count += 1
            elif pos_side == "short":
                pending_short_count += 1
    # 审计(2026-09-13)·外所挂单盲区修复：本守卫此前只数 OKX 在途单，路由派往
    # binance/gate 的单对周期不可见 → 同信号逐轮在外所重复挂单（实锤：binance
    # demo BTC/SUI 各成对）。执行闸开的场并入同一把尺；凭证已死的场收侧已吼
    # CRITICAL 且 router 同样发不出单，此处静默跳过不重复报警。
    _auth_markers = ("INVALID_KEY", "Invalid key", "Invalid API-key", "-2015", "50111",
                     "signature", "Signature", "not exist", "invalid timestamp")
    try:
        _gv_mode = str(current_environment().mode or "")
    except Exception:
        _gv_mode = ""
    pending_inst_ids, pending_long_count, pending_short_count = \
        collect_pending_inst_ids(
            venues=("gate", "binance"), venue_mode=_gv_mode,
            broken_venues=_BROKEN_VENUES, venue_registry=venue_registry,
            load_instruments=load_instruments, auth_markers=_auth_markers,
            warn=print)
    reserved_slot_count = active_pos_count + len(pending_inst_ids)
    reserved_long_count = long_count + pending_long_count
    reserved_short_count = short_count + pending_short_count

    # 1a. 跨所封顶（三所平权开单后的风控收口）：开闸所（gate/binance）的
    # 活跃持仓计入总仓/同向配额；读取失败 → 本周期禁止新增开仓（fail-closed，
    # 与挂单对账同一把尺——宁停不错）。孤儿仓只计数不处置（可能是用户手动仓）。
    try:
        _xv_env = str(current_environment().mode)
    except Exception as _xv_exc:
        _xv_env = ""
        print(f"[跨所封顶] warn 周期冻结环境不可得（{_xv_exc}），按不可信环境处理")
    xv_ok, xv_positions_by_venue, xv_error = fetch_other_venue_positions(_xv_env)
    # 巡检文案口径（审计 D 级）：持仓数历来只报 OKX，跨所持仓仅在封顶逻辑里
    # 出现——面板/日志读起来「0/8」像全空，实际外所可能有数笔。此处统一算出
    # 跨所笔数供 AI 提示词与巡检日志；拉取失败显式标「未知」，绝不装 0。
    _xv_total = sum(len(v or []) for v in (xv_positions_by_venue or {}).values()) if xv_ok else None
    xv_enabled = bool(_xv_env) and any(venue_execution_ready(v, _xv_env)
                                       for v in ("gate", "binance"))
    if (xv_enabled or not _xv_env) and not xv_ok:
        print(f"[跨所封顶] fail-closed 本周期禁止新增开仓: {xv_error or '环境轴不可得'}")
        entries_blocked = True
    else:
        for _v, _rows in (xv_positions_by_venue or {}).items():
            for _p in _rows:
                print(f"[跨所封顶] {_v} {_p.get('inst_id')} {_p.get('side')} "
                      f"size={_p.get('size_signed')} 纳入本周期仓位配额（只计数不处置）")
                reserved_slot_count += 1
                if str(_p.get("side", "")).lower() == "long":
                    reserved_long_count += 1
                else:
                    reserved_short_count += 1

    # 1b. US-010 预留对账：基于本周期刚核验的持仓/挂单实况回笼陈旧占用
    #     （活仓/在途挂单一律保留；无仓无挂且超 TTL 才 closed——宁慢不错杀）。
    try:
        reconcile_reservation_ledger(real_pos_dict, pending_inst_ids, _xv_env,
                                     venue_snapshot=xv_positions_by_venue)
    except Exception as _rc_exc:
        print(f"[预留对账] warn 对账器异常（不影响本周期交易）: {_rc_exc}")

    try:
        bal_res = okx_rest.balances()
    except Exception as bal_exc:
        print(f"[Trader] Abort: unable to verify account balance: {bal_exc}")
        return None
    usdt_available = 0.0
    if bal_res:
        for d in bal_res[0].get("details", []):
            if d.get("ccy") == "USDT":
                usdt_available = float(d.get("availBal", 0.0))
                break
    return (_xv_total, active_pos_count, all_positions, entries_blocked, long_count, pending_inst_ids, real_pos_dict, reserved_long_count, reserved_short_count, reserved_slot_count, short_count, usdt_available, xv_positions_by_venue)
