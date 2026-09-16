"""台账读取与生命周期成交筛选（结构优化阶段 2·B2 第八刀）。

从 update_cache_cycle 第 7 段迁出。注意其中「测试封闭闸」的语义：
autosync_enabled 以门面模块导入时的快照值注入，绝不在调用时重读环境变量。
"""
from __future__ import annotations

import json
import os
import time

from r20_backend.time_utils import beijing_text
from scripts.evolution.observability import classify_snapshot_observability

__all__ = ["load_ledger_lifecycle_trades", "LEDGER_TRADES_MAX"]

#: 台账视图一次下发的**最大逐笔行数**（唯一事实源）。
#:
#: ⚠️ 2026-09-16：这个常量此前是 `[:60]` 的字面量，而 `slim.py` 的
#: `SLIM_TRADES` 另写了 20 —— 于是 `/api/all` 默认瘦身把台账**静默**砍到最近
#: 20 笔（34 笔里丢 14 笔），而台账页的「累计平仓/胜率/净盈亏/手续费」全部
#: 在这个被砍的切片上聚合，页面却没有任何截断提示（前端从不读
#: `_meta.omitted`）—— 既是少数据，也是 UI 说谎。两处上限现已同源：
#: slim 侧不能再比本上限更紧，否则台账页必然少行。
LEDGER_TRADES_MAX = 60

#: 逐单可观测性标签的合法取值（与 `scripts/evolution/observability.py` 同源）。
_OBSERVABILITY_TAGS = ("DYNAMICS_OBSERVED", "PARTIAL", "PRICE_ONLY", "NONE")

#: 台账成交行可能携带开仓快照的字段名（历史上不同写入路径用过不同键）。
_SNAPSHOT_KEYS = ("signal_snapshot", "entry_snapshot", "snapshot")


def classify_trade_observability(trade: dict) -> str:
    """逐单判定「开仓时刻数理快照」可观测性（前台台账展示用）。

    ⚠️ 证据纪律（2026-09-16 用户要求，与宿主宪章第 2 条一致）：

    - **只认该笔成交自身携带的证据**（显式标签，或 `signal_snapshot` /
      `entry_snapshot` / `snapshot` 字段）；
    - **绝不向 `signal_journal.json` 之类的外部日志回填匹配**，也绝不由
      price/atr/adx 之类普通观测**推算** v/a/j/I、能量积分、偏离面积积分、
      延续/击穿概率、VaR/CVaR —— 台账当时没记，就是「不可观测」；
    - 缺失本身不得被解读为「动力学异常」等任何证据。

    故台账行没有快照 → `NONE`（前台据此明确标注「数理快照不可观测」）。
    """
    tag = str(trade.get("snapshot_observability") or "").upper()
    if tag in _OBSERVABILITY_TAGS:
        return tag
    for key in _SNAPSHOT_KEYS:
        snap = trade.get(key)
        if isinstance(snap, dict) and snap:
            return classify_snapshot_observability(snap)
    return "NONE"


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

    trades_table = valid_ledger_trades[:LEDGER_TRADES_MAX]

    # 逐单挂「数理快照可观测性」标签（前台台账/抽屉据此明确标注「不可观测」）。
    # 纯分类、零回填：见 classify_trade_observability 的证据纪律说明。
    for _t in trades_table:
        if isinstance(_t, dict):
            _t["snapshot_observability"] = classify_trade_observability(_t)

    # 8-10. 本地读取（结构优化阶段 2·B2 第六刀：迁至 dashboard_payload/local_reads.py）
    return valid_ledger_trades, trades_table
