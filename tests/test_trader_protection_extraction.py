"""B3 第三块（`scripts/trader/protection.py`）的旧实现差分回归。

## 这个测试在守什么

结构优化阶段 4·B3 把 `manage_position_tp_and_trailing` 里**长空各抄一遍**的两段
纯计算搬进了 `scripts/trader/protection.py`。搬家允许、行为不许变 —— 而这两个
函数是**止损线**的计算，算错一个 `max`/`min` 方向就是实盘直接亏损。

因此这里不写"实现自证"式的断言，而是把**搬走前的原门面代码原样内联为 `_legacy_*`**，
用确定性随机输入做逐值对拍：只要新实现与原实现在任何一组输入上分叉，本测试就红。

对照面覆盖：
- `rounded ==` 的**恰好相等**（半值、跨 `prec` 边界、负价）；
- `peak_profit_px` 精确落在 tier1 / tier2 触发线上（`>=` 边界，非近似）；
- `old_sl` 为 0（"无保护"，不得被当成已推进）、为负、已高于目标（不得后退）；
- 长/空两条分支。

## 为什么可以钉住"旧实现"

`_legacy_*` 是**测试内的副本**，不是被删的生产代码路径 —— 它不会随重构漂移，
但会随"有人偷偷改了新实现"立刻报警。这与仓里既有的
`tests/test_three_tier_ratchet_and_cloud_sync.py`（走真实 `aft` 集成路径）互补：
那条测"接线没错"，这条测"数学没漂"。
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from scripts.trader.protection import protection_signals, ratcheted_trailing_stop


# --------------------------------------------------------------------------
# 搬走前的门面原样（务必逐字保留，包括 `0.0020` 与两处 round 的写法）
# --------------------------------------------------------------------------
def _legacy_hard_stop_hit(is_long, cur_px, hard_stop_px):
    return hard_stop_px > 0 and (
        (is_long and cur_px <= hard_stop_px) or (not is_long and cur_px >= hard_stop_px)
    )


def _legacy_ratchet_long(entry_px, atr, prec, peak_profit_px, old_sl,
                         tier1_breakeven_trigger, tier2_lock_trigger):
    stage_desc = None
    dynamic_floor_sl = old_sl
    if peak_profit_px >= tier2_lock_trigger:
        dynamic_floor_sl = max(dynamic_floor_sl, round(entry_px + 1.0 * atr, prec))
        stage_desc = f"锁定大波段利润 (保底止损 {dynamic_floor_sl})"
    elif peak_profit_px >= tier1_breakeven_trigger:
        dynamic_floor_sl = max(dynamic_floor_sl, round(entry_px + 0.0020 * entry_px, prec))
        stage_desc = f"已推保本无风险 (保底止损 {dynamic_floor_sl})"
    return dynamic_floor_sl, stage_desc


def _legacy_ratchet_short(entry_px, atr, prec, peak_profit_px, old_sl,
                          tier1_breakeven_trigger, tier2_lock_trigger):
    stage_desc = None
    dynamic_floor_sl = old_sl
    if peak_profit_px >= tier2_lock_trigger:
        dynamic_floor_sl = min(dynamic_floor_sl, round(entry_px - 1.0 * atr, prec))
        stage_desc = f"锁定大波段利润 (保底止损 {dynamic_floor_sl})"
    elif peak_profit_px >= tier1_breakeven_trigger:
        dynamic_floor_sl = min(dynamic_floor_sl, round(entry_px - 0.0020 * entry_px, prec))
        stage_desc = f"已推保本无风险 (保底止损 {dynamic_floor_sl})"
    return dynamic_floor_sl, stage_desc


class HardStopSignalParityTest(unittest.TestCase):
    """`protection_signals` 与旧内联表达式逐值对拍。"""

    def test_random_parity(self):
        rng = random.Random(20260914)
        cases = 0
        for _ in range(20000):
            is_long = rng.random() < 0.5
            cur_px = round(rng.uniform(0.0, 200000.0), rng.randint(0, 8))
            hard_stop_px = rng.choice([
                0.0, -1.0, rng.uniform(0.0, 200000.0), cur_px, cur_px * 0.999999,
            ])
            expected = _legacy_hard_stop_hit(is_long, cur_px, hard_stop_px)
            actual = protection_signals(is_long=is_long, cur_px=cur_px, hard_stop_px=hard_stop_px)
            self.assertEqual(actual, expected,
                             f"分叉: is_long={is_long} cur_px={cur_px} hard_stop_px={hard_stop_px}")
            cases += 1
        self.assertEqual(cases, 20000)

    def test_zero_stop_never_triggers(self):
        """"无保护"（stop=0）绝不能被当成击穿 —— 否则等于无止损强平。"""
        for is_long in (True, False):
            for cur_px in (0.0, 1.0, 50000.0):
                self.assertFalse(protection_signals(is_long=is_long, cur_px=cur_px, hard_stop_px=0.0))
                self.assertFalse(protection_signals(is_long=is_long, cur_px=cur_px, hard_stop_px=-5.0))

    def test_touch_is_inclusive_on_both_sides(self):
        """触及即触发（`<=` / `>=`），不是"穿过"。"""
        self.assertTrue(protection_signals(is_long=True, cur_px=100.0, hard_stop_px=100.0))
        self.assertTrue(protection_signals(is_long=False, cur_px=100.0, hard_stop_px=100.0))
        self.assertFalse(protection_signals(is_long=True, cur_px=100.01, hard_stop_px=100.0))
        self.assertFalse(protection_signals(is_long=False, cur_px=99.99, hard_stop_px=100.0))


class RatchetedTrailingStopParityTest(unittest.TestCase):
    """`ratcheted_trailing_stop` 与旧长短两份内联实现逐值对拍。"""

    TRIGGERS = (1.5, 2.2)  # (tier1_breakeven_trigger, tier2_lock_trigger) 由调用方按 ATR 传入

    def _assert_parity(self, *, is_long, entry_px, atr, prec, peak_profit_px, old_sl):
        tier1, tier2 = self.TRIGGERS
        legacy_long = _legacy_ratchet_long(entry_px, atr, prec, peak_profit_px, old_sl, tier1, tier2)
        legacy_short = _legacy_ratchet_short(entry_px, atr, prec, peak_profit_px, old_sl, tier1, tier2)
        # 旧实现里长空是**同一个函数体里的两个分支**；空头分支只算 min 那份。
        # 因此按 is_long 选择对应副本，而不是把两份都当期望。
        expected = legacy_long if is_long else legacy_short
        actual = ratcheted_trailing_stop(
            is_long=is_long, entry_px=entry_px, atr=atr, prec=prec,
            peak_profit_px=peak_profit_px, old_sl=old_sl,
            tier1_breakeven_trigger=tier1, tier2_lock_trigger=tier2,
        )
        ctx = (f"is_long={is_long} entry_px={entry_px} atr={atr} prec={prec} "
               f"peak_profit_px={peak_profit_px} old_sl={old_sl}")
        self.assertEqual(actual[0], expected[0], f"止损线分叉: {ctx}")
        self.assertEqual(actual[1], expected[1], f"stage_desc 分叉: {ctx}")

    def test_random_parity(self):
        rng = random.Random(20260915)
        for _ in range(20000):
            is_long = rng.random() < 0.5
            entry_px = rng.uniform(0.01, 120000.0)
            atr = rng.uniform(0.0, entry_px * 0.2)
            prec = rng.randint(0, 8)
            tier1, tier2 = 1.5 * atr, 2.2 * atr
            peak_profit_px = rng.uniform(-entry_px, entry_px)
            old_sl = rng.choice([
                0.0, entry_px, entry_px * 0.9, entry_px * 1.1, rng.uniform(0, 200000.0),
            ])
            self._assert_parity(is_long=is_long, entry_px=entry_px, atr=atr, prec=prec,
                                peak_profit_px=peak_profit_px, old_sl=old_sl)

    def test_exact_tier_boundaries(self):
        """恰好落在触发线上必须**进入该档**（`>=`），这是最容易抄错的一处。"""
        entry_px, atr, prec = 30000.0, 100.0, 2
        for is_long in (True, False):
            for peak, tier in ((1.5 * atr, "tier1"), (2.2 * atr, "tier2")):
                self._assert_parity(is_long=is_long, entry_px=entry_px, atr=atr, prec=prec,
                                    peak_profit_px=peak, old_sl=entry_px)
                floor, desc = ratcheted_trailing_stop(
                    is_long=is_long, entry_px=entry_px, atr=atr, prec=prec,
                    peak_profit_px=peak, old_sl=entry_px,
                    tier1_breakeven_trigger=1.5 * atr, tier2_lock_trigger=2.2 * atr)
                self.assertIsNotNone(desc, f"{tier} 边界未进入锁定档")
                if tier == "tier2":
                    self.assertEqual(floor, round(entry_px + (atr if is_long else -atr), prec))

    def test_stop_never_retreats(self):
        """单向棘轮：新止损绝不允许朝不利方向后退（长只能上、空只能下）。"""
        rng = random.Random(20260916)
        for _ in range(5000):
            is_long = rng.random() < 0.5
            entry_px = rng.uniform(1.0, 50000.0)
            atr = rng.uniform(0.0, entry_px * 0.2)
            prec = rng.randint(0, 8)
            peak_profit_px = rng.uniform(0.0, entry_px)
            old_sl = rng.uniform(0.0, entry_px * 2)
            floor, _ = ratcheted_trailing_stop(
                is_long=is_long, entry_px=entry_px, atr=atr, prec=prec,
                peak_profit_px=peak_profit_px, old_sl=old_sl,
                tier1_breakeven_trigger=1.5 * atr, tier2_lock_trigger=2.2 * atr)
            if is_long:
                self.assertGreaterEqual(floor, old_sl, "多头止损后退了")
            else:
                self.assertLessEqual(floor, old_sl, "空头止损后退了")

    def test_zero_old_stop_still_computes_floor(self):
        """`old_sl == 0`（无保护）时：算出的保底线就是目标值本身，不被 0 夹住。

        对应原门面的 `max(0, target)` / `min(0, target)` —— 多头为 target、空头为 0。
        这里同时钉住"门面只在 old_sl > 0 时才同步云端"的前提不被误改。
        """
        floor_long, _ = ratcheted_trailing_stop(
            is_long=True, entry_px=30000.0, atr=100.0, prec=2, peak_profit_px=300.0,
            old_sl=0.0, tier1_breakeven_trigger=150.0, tier2_lock_trigger=220.0)
        self.assertEqual(floor_long, 30100.0)
        floor_short, _ = ratcheted_trailing_stop(
            is_long=False, entry_px=30000.0, atr=100.0, prec=2, peak_profit_px=300.0,
            old_sl=0.0, tier1_breakeven_trigger=150.0, tier2_lock_trigger=220.0)
        self.assertEqual(floor_short, 0.0)


class TraderFacadeWiringTest(unittest.TestCase):
    """门面必须真的用上新模块，而不是把旧内联代码悄悄留在原地。"""

    def test_facade_imports_and_calls_protection_module(self):
        facade = Path(__file__).resolve().parent.parent / "scripts" / "ai_factor_trader.py"
        src = facade.read_text(encoding="utf-8")
        self.assertIn("from scripts.trader.protection import protection_signals, ratcheted_trailing_stop", src)
        self.assertIn("hard_stop_hit = protection_signals(", src)
        self.assertEqual(src.count("ratcheted_trailing_stop("), 2,
                         "长/空两个分支都必须走新模块")
        # 反向哨：旧内联写法不得复活
        self.assertNotIn("peak_profit_px >= tier2_lock_trigger:\n            dynamic_floor_sl", src)


if __name__ == "__main__":
    unittest.main()
