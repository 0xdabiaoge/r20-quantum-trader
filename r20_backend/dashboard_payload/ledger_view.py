"""台账读取与生命周期成交筛选（结构优化阶段 2·B2 第八刀）。

从 update_cache_cycle 第 7 段迁出。注意其中「测试封闭闸」的语义：
autosync_enabled 以门面模块导入时的快照值注入，绝不在调用时重读环境变量。
"""
from __future__ import annotations

import json
import os
import time

from r20_backend.time_utils import beijing_text

__all__ = ["load_ledger_lifecycle_trades"]


def load_ledger_lifecycle_trades(ledger_file, workspace_dir, autosync_enabled, reset_time_str):
    """读取台账并筛出 reset_time 之后（或仍 holding）的生命周期成交。

    原样搬自 update_cache_cycle 第 7 段（52 行）。三个注入项都有讲究：
    - ledger_file：被测试 patch；
    - workspace_dir：用于定位 scripts/sync_full_ledger.py；
    - autosync_enabled：**模块导入时快照**的常量（批E 测试封闭闸）。
      不能改成「调用时读环境变量」——多个测试用 patch.dict(clear=True) 清空环境，
      会把标志一起抹掉。以门面常量的当前值注入即等价于原语义。
    """
    ledger_trades = []
    need_ledger_sync = True
    if os.path.exists(ledger_file):
        try:
            mtime = os.path.getmtime(ledger_file)
            if time.time() - mtime < 60:
                need_ledger_sync = False
        except Exception:
            pass

    # 批E(2026-09-13)·测试封闭闸：本触发点会 spawn 真实同步子进程（打三所接口 +
    # 重写 data/trading_ledger.json）。多个仪表盘测试走真实 DATA_DIR ⇒ 测试期间会
    # 打真网络并改写生产台账（违反「测试不触生产文件」）。
    # 注意：仅在调用时读 os.environ 不够——多个测试用 patch.dict(..., clear=True)
    # 清空整个环境，会把标志一起抹掉。故以**模块导入时快照**为准（tests/__init__.py
    # 在任何测试模块导入 r20_backend.dashboard_cache 之前置位），生产不设该变量 → 行为不变。
    _ledger_sync_disabled = (
        not autosync_enabled
        or str(os.environ.get("R20_LEDGER_SYNC_DISABLED", "")).strip().lower() in ("1", "true", "yes")
    )
    if need_ledger_sync and not _ledger_sync_disabled:
        try:
            sync_script = os.path.join(workspace_dir, "scripts", "sync_full_ledger.py")
            if os.path.exists(sync_script):
                # 审计批7：旧 `python3` shell 串在这台主机根本不存在（rc=127 被
                # capture_output 吞）→ 服务器侧台账刷新从未生效；且旧 timeout=10s
                # 短于真实三所全史拉取（约20-30s）必然静默超时。改同解释器+吼。
                from r20_backend.spawn import run_script
                run_script(sync_script, timeout=45, label="sync_full_ledger")
        except Exception:
            pass

    if os.path.exists(ledger_file):
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                ledger_trades = json.load(f)
        except Exception:
            pass

    # Filter lifecycle trades past reset_time
    valid_ledger_trades = []
    for t in ledger_trades:
        # Check either close_time or open_time >= reset_time
        c_time = beijing_text(t.get("close_time"))
        o_time = beijing_text(t.get("open_time"))
        t_time = beijing_text(t.get("time"))
        if (c_time and c_time >= beijing_text(reset_time_str)) or (o_time and o_time >= beijing_text(reset_time_str)) or (t_time and t_time >= beijing_text(reset_time_str)) or t.get("status") == "holding":
            valid_ledger_trades.append(t)

    trades_table = valid_ledger_trades[:60]

    # 8-10. 本地读取（结构优化阶段 2·B2 第六刀：迁至 dashboard_payload/local_reads.py）
    return valid_ledger_trades, trades_table
