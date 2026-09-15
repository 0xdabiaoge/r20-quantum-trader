"""execute_portfolio 的阶段函数（B3 抽取·第九十一刀）。

从 `scripts/ai_factor_trader.py::execute_portfolio`（294 行）中
**纯搬家**两段：

| 函数 | 段长 | 原相位 |
|---|---|---|
| `fetch_universe_and_manage_positions` | 14 行 | 相位 2-3：并发取标的池因子 + 逐仓追踪止损退出 |
| `persist_state_and_sync_ledger` | 30 行 | 相位 5-6：面板状态持久化 + 生命周期台账/SQLite 实时同步 |
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
