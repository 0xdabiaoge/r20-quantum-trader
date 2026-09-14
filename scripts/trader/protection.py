"""持仓保护判定与阶梯止损计算（B3 抽取第三块）。

从 `scripts/ai_factor_trader.py` 的 `manage_position_tp_and_trailing`（331 行）搬出的
**两块纯计算**。它们原先在长/空两个分支里各写一遍，是同一份数学的两次抄写。

## 为什么是这块（为什么安全）

- 只搬**纯函数**：入参全是数值/布尔，返回值是数值/布尔，无 I/O、无模块状态读取。
  因此不存在 `tests/risk_test_env.py::pin_baseline_risk_env()` 的重载陷阱
  —— 那个名单只含 `risk_constants` / `ai_factor_trader` / `ai_brain_trader`，
  但本模块**不 import 任何门面全局**，没有任何 import 期烘焙值可被刷新或失效。
- 两个函数都**不在任何测试的源码锚点或结构 split 断言里**（已逐条比对
  `grep -rn 'split("def ' tests/` 与 8 个读源码的审计测试）。
- 门面里全部调用点都走**全局名**查找，原位置无需留壳（新名字不覆盖任何旧名字），
  **调用点只改这一处**。

## 被搬走的两次抄写

| 函数 | 原门面位置 | 作用 |
|---|---|---|
| `protection_signals` | 硬止损判定（L2005-L2006） | 云端追踪止损是否已被击穿 |
| `ratcheted_trailing_stop` | 阶梯锁利 L2105-L2114 / L2185-L2192 | 按峰值浮盈把保底止损单向推进 |

对比：搬走前长空两份 `if peak_profit_px >= tier2_lock_trigger / elif … tier1 …`
共 20 行，数学相同、方向相反。合并后由 `is_long` 选 `max` / `min` 与
`prec` 舍入方向，语义逐字对齐（见 `tests/test_trader_protection_extraction.py`
的旧实现差分）。
"""


def protection_signals(*, is_long, cur_px, hard_stop_px):
    """云端追踪止损是否已被击穿（硬止损只做亏损保护，与锁利是否激活无关）。

    原门面对应一行（长空方向合一）：

        hard_stop_px > 0 and ((is_long and cur_px <= hard_stop_px)
                              or (not is_long and cur_px >= hard_stop_px))

    `hard_stop_px > 0` 必须先判：`trailingStopPx` 缺失/为 0 表示"无止损保护"，
    此时**不得**把任意价格当成击穿（否则等于无止损强平）。
    """
    return hard_stop_px > 0 and (
        (is_long and cur_px <= hard_stop_px) or (not is_long and cur_px >= hard_stop_px)
    )


def ratcheted_trailing_stop(*, is_long, entry_px, atr, prec, peak_profit_px,
                            old_sl, tier1_breakeven_trigger, tier2_lock_trigger):
    """按峰值浮盈把保底止损**单向**推进，返回 `(dynamic_floor_sl, stage_desc)`。

    - 峰值浮盈 >= `tier2_lock_trigger`（2.2x ATR）：锁 1.0x ATR 大波段利润。
    - 否则若 >= `tier1_breakeven_trigger`（1.5x ATR）：推到保本（+0.20% 成本垫），
      以覆盖 taker 费。
    - 两者都不满足：维持原止损（`old_sl`）。

    方向的正确性由 `max`（多）/ `min`（空）保证 —— 止损只能朝有利方向单调推进，
    绝不后退。返回的 `stage_desc` 仅在"确实推进了（且原止损 > 0）"时才被门面
    写回 tracker，与原实现的读取时机一致。
    """
    dynamic_floor_sl = old_sl
    stage_desc = None
    if peak_profit_px >= tier2_lock_trigger:
        locked = round(entry_px + 1.0 * atr, prec) if is_long else round(entry_px - 1.0 * atr, prec)
        dynamic_floor_sl = max(dynamic_floor_sl, locked) if is_long else min(dynamic_floor_sl, locked)
        stage_desc = f"锁定大波段利润 (保底止损 {dynamic_floor_sl})"
    elif peak_profit_px >= tier1_breakeven_trigger:
        breakeven = round(entry_px + 0.0020 * entry_px, prec) if is_long \
            else round(entry_px - 0.0020 * entry_px, prec)
        dynamic_floor_sl = max(dynamic_floor_sl, breakeven) if is_long else min(dynamic_floor_sl, breakeven)
        stage_desc = f"已推保本无风险 (保底止损 {dynamic_floor_sl})"
    return dynamic_floor_sl, stage_desc
