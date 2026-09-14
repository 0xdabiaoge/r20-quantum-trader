"""`r20_backend/dashboard_payload/trade_stats.py`（B3 第二十四刀）回归。

## 这个测试在守什么

`aggregate_trade_stats` 把「分钟+币种」平仓聚合滚动成仪表盘 KPI 需要的
当日/累计胜负统计。三处最容易错：

1. **尘埃过滤的双条件**：`abs(net) < 0.01 AND abs(gross_pnl) < 0.01`。
   只判一个会误删"净额小而毛额大"的真实交易（手续费吃掉全部利润、
   但方向确实盈利的单子）。
2. **过滤发生在 `by_inst` 记账之后** —— 所以分币种的 `trades` 计数
   **包含**尘埃单，全局 win/loss 计数**不含**。两者口径不同是**故意的**，
   不是 bug。若"顺手统一"，分币种表笔数会与前端预期不符。
3. **`today_bj_str in t_time` 是子串判断**（与 `bills.py` 同款），
   且 `today_realized_gross` 用 `gross_pnl`（不含手续费），而胜负用
   `pnl`（含手续费）—— 两个口径不能互相替代。
"""

from __future__ import annotations

import ast
import random
import unittest
from pathlib import Path

from r20_backend.dashboard_payload.trade_stats import aggregate_trade_stats

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dashboard" / "app.py"
MODULE = ROOT / "r20_backend" / "dashboard_payload" / "trade_stats.py"

TODAY = "2026-09-14"


def _legacy(orders_by_key, *, today_bj_str):
    """搬走前 update_cache_cycle 里的内联平仓聚合（逐字原样）。"""
    today_win_trades = 0
    today_loss_trades = 0
    all_win_trades = 0
    all_loss_trades = 0
    all_win_amt = 0.0
    all_loss_amt = 0.0
    by_inst = {}
    today_realized_gross = 0.0

    for agg_k, o in orders_by_key.items():
        net = o["pnl"]
        inst = o["inst"]
        t_time = o["time"]
        if inst not in by_inst:
            by_inst[inst] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        by_inst[inst]["trades"] += 1
        by_inst[inst]["pnl"] += net
        if abs(net) < 0.01 and abs(o.get("gross_pnl", 0.0)) < 0.01:
            continue
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

    return {
        "by_inst": by_inst,
        "today_realized_gross": today_realized_gross,
        "today_win_trades": today_win_trades,
        "today_loss_trades": today_loss_trades,
        "all_win_trades": all_win_trades,
        "all_loss_trades": all_loss_trades,
        "all_win_amt": all_win_amt,
        "all_loss_amt": all_loss_amt,
    }


def _order(inst="BTC", time="2026-09-14 10:00", pnl=0.0, gross=None):
    return {"inst": inst, "time": time, "pnl": pnl,
            "gross_pnl": pnl if gross is None else gross}


def _call(orders, today=TODAY):
    return aggregate_trade_stats(orders, today_bj_str=today)


class BasicTest(unittest.TestCase):
    def test_empty_returns_zeroes(self):
        out = _call({})
        self.assertEqual(out["by_inst"], {})
        for k in ("today_realized_gross", "all_win_amt", "all_loss_amt"):
            self.assertEqual(out[k], 0.0)
        for k in ("today_win_trades", "today_loss_trades",
                  "all_win_trades", "all_loss_trades"):
            self.assertEqual(out[k], 0)

    def test_win_counted(self):
        out = _call({"k": _order(pnl=10.0)})
        self.assertEqual(out["all_win_trades"], 1)
        self.assertEqual(out["all_win_amt"], 10.0)
        self.assertEqual(out["today_win_trades"], 1)

    def test_loss_counted_with_absolute_amount(self):
        out = _call({"k": _order(pnl=-7.5)})
        self.assertEqual(out["all_loss_trades"], 1)
        self.assertEqual(out["all_loss_amt"], 7.5, "亏损额取绝对值")

    def test_zero_pnl_counts_as_neither(self):
        out = _call({"k": _order(pnl=0.0, gross=5.0)})
        self.assertEqual(out["all_win_trades"], 0)
        self.assertEqual(out["all_loss_trades"], 0)

    def test_all_keys_present(self):
        out = _call({})
        self.assertEqual(set(out), {
            "by_inst", "today_realized_gross", "today_win_trades",
            "today_loss_trades", "all_win_trades", "all_loss_trades",
            "all_win_amt", "all_loss_amt"})


class TodaySubstringTest(unittest.TestCase):
    def test_today_is_substring_match(self):
        out = _call({"k": _order(time="2026-09-14 10:00", pnl=1.0)})
        self.assertEqual(out["today_win_trades"], 1)

    def test_substring_vs_equality_is_distinguishable(self):
        """**唯一能区分 `in` 与 `==` 的输入**：`time` 带时间部分。

        `"2026-09-14" in "2026-09-14 10:00"` → True（正确）
        `"2026-09-14" == "2026-09-14 10:00"` → False（若实现写成 ==，这条会红）

        我第一版**没写这条**：负向验证把 `in` 改成 `==` 时测试**依然全绿**，
        因为我的所有 fixture 都是带时间部分的字符串 —— 而那种输入下
        `today_bj_str in t_time` 与 `== t_time` 结果**恰好相同**，
        差分是盲的。补上这条后该缺陷才被抓住。
        """
        self.assertIn(TODAY, "2026-09-14 10:00")
        self.assertNotEqual(TODAY, "2026-09-14 10:00")
        out = _call({"k": _order(time="2026-09-14 10:00", pnl=1.0)})
        self.assertEqual(out["today_win_trades"], 1,
                         "若实现是 ==，这里会是 0")

    def test_exact_date_only_time_string_also_matches(self):
        """`time` 恰好只含日期时 `in` 与 `==` 都成立 —— 故这条**不能**用来区分两者。"""
        out = _call({"k": _order(time=TODAY, pnl=1.0)})
        self.assertEqual(out["today_win_trades"], 1)
        self.assertIn(TODAY, TODAY)
        self.assertEqual(TODAY, TODAY)

    def test_other_day_not_counted_as_today(self):
        out = _call({"k": _order(time="2026-09-13 23:59", pnl=1.0)})
        self.assertEqual(out["today_win_trades"], 0)
        self.assertEqual(out["all_win_trades"], 1, "但计入累计")

    def test_today_realized_gross_only_from_today(self):
        out = _call({
            "a": _order(time="2026-09-14 10:00", pnl=1.0, gross=10.0),
            "b": _order(time="2026-09-13 10:00", pnl=1.0, gross=100.0),
        })
        self.assertEqual(out["today_realized_gross"], 10.0,
                         "只累加当日行")

    def test_today_realized_gross_uses_gross_not_net(self):
        """`today_realized_gross` 用 `gross_pnl`（不含手续费），胜负用 `pnl`。"""
        out = _call({"k": _order(time="2026-09-14 10:00", pnl=1.0, gross=42.0)})
        self.assertEqual(out["today_realized_gross"], 42.0)
        self.assertEqual(out["all_win_amt"], 1.0)

    def test_gross_accumulated_even_for_losses(self):
        out = _call({"k": _order(time="2026-09-14 10:00", pnl=-5.0, gross=-5.0)})
        self.assertEqual(out["today_realized_gross"], -5.0)


class DustFilterTest(unittest.TestCase):
    def test_both_small_is_filtered(self):
        out = _call({"k": _order(pnl=0.005, gross=0.005)})
        self.assertEqual(out["all_win_trades"], 0, "两个都 < 0.01 → 尘埃，不计胜负")
        self.assertEqual(out["all_loss_trades"], 0)

    def test_small_net_but_large_gross_is_kept(self):
        """**双条件的关键**：净额小但毛额大 → 不是尘埃，要计入。

        这是"手续费吃掉全部利润、但方向确实盈利"的真实交易。
        若只判 `abs(net) < 0.01`，这笔会被误删。
        """
        out = _call({"k": _order(pnl=0.005, gross=12.0)})
        self.assertEqual(out["all_win_trades"], 1, "毛额大 → 是真交易，不是尘埃")

    def test_exactly_threshold_is_kept(self):
        """阈值是严格小于 0.01；等于 0.01 不过滤。"""
        out = _call({"k": _order(pnl=0.01, gross=0.01)})
        self.assertEqual(out["all_win_trades"], 1)

    def test_dust_still_counted_in_by_inst_trades(self):
        """⚠️ 口径差异：尘埃单**仍计入** `by_inst[inst]["trades"]`。

        过滤发生在 `by_inst` 记账**之后**，所以分币种笔数 ≥ 全局胜负笔数。
        这是**故意的**，不是 bug —— 若"顺手统一"，分币种表会与前端预期不符。
        """
        out = _call({"k": _order(inst="BTC", pnl=0.001, gross=0.001)})
        self.assertEqual(out["all_win_trades"], 0, "全局不计")
        self.assertEqual(out["by_inst"]["BTC"]["trades"], 1, "分币种仍计")
        self.assertEqual(out["by_inst"]["BTC"]["wins"], 0, "但 wins 不计")

    def test_dust_pnl_still_accumulated_in_by_inst_pnl(self):
        out = _call({"k": _order(inst="BTC", pnl=0.001, gross=0.001)})
        self.assertAlmostEqual(out["by_inst"]["BTC"]["pnl"], 0.001, places=10)


class ByInstTest(unittest.TestCase):
    def test_grouped_by_inst(self):
        out = _call({
            "a": _order(inst="BTC", pnl=10.0),
            "b": _order(inst="ETH", pnl=-3.0),
            "c": _order(inst="BTC", pnl=-1.0),
        })
        self.assertEqual(set(out["by_inst"]), {"BTC", "ETH"})
        self.assertEqual(out["by_inst"]["BTC"]["trades"], 2)
        self.assertEqual(out["by_inst"]["BTC"]["wins"], 1)
        self.assertEqual(out["by_inst"]["BTC"]["losses"], 1)
        self.assertAlmostEqual(out["by_inst"]["BTC"]["pnl"], 9.0, places=10)
        self.assertEqual(out["by_inst"]["ETH"]["trades"], 1)

    def test_by_inst_new_dict_each_call(self):
        """不得在多次调用间共享 `by_inst`（否则会跨周期累积）。"""
        a = _call({"k": _order(inst="BTC", pnl=1.0)})
        b = _call({"k": _order(inst="ETH", pnl=1.0)})
        self.assertEqual(set(a["by_inst"]), {"BTC"})
        self.assertEqual(set(b["by_inst"]), {"ETH"})
        self.assertIsNot(a["by_inst"], b["by_inst"])


class RandomParityTest(unittest.TestCase):
    def test_random_parity(self):
        rng = random.Random(20261001)
        for _ in range(5000):
            n = rng.randint(0, 6)
            orders = {}
            for i in range(n):
                orders[f"k{i}"] = _order(
                    inst=rng.choice(["BTC", "ETH", "SOL"]),
                    # 含"带时间部分"的形态（区分 in/== 的关键）与"仅日期"形态
                time=rng.choice(["2026-09-14 10:00", "2026-09-14 23:59",
                                 "2026-09-14", "2026-09-13 10:00",
                                 "2026-09-01 00:00", ""]),
                    pnl=rng.choice([-50.0, -0.005, 0.0, 0.005, 0.01, 1.0, 100.0]),
                    gross=rng.choice([-50.0, -0.005, 0.0, 0.005, 0.01, 12.0, 100.0]),
                )
            today = rng.choice(["2026-09-14", "2026-09-13", "2026-01-01"])
            got = _call(orders, today)
            exp = _legacy(orders, today_bj_str=today)
            self.assertEqual(got, exp, f"分叉: today={today} orders={orders}")


class WiringTest(unittest.TestCase):
    def test_impl_in_submodule_not_facade(self):
        app_src = APP.read_text(encoding="utf-8")
        mod_src = MODULE.read_text(encoding="utf-8")
        self.assertIn("def aggregate_trade_stats(", mod_src)
        self.assertNotIn("def aggregate_trade_stats(", app_src)
        self.assertIn("_core_aggregate_trade_stats(", app_src)

    def test_facade_no_longer_contains_the_inline_loop(self):
        app_src = APP.read_text(encoding="utf-8")
        for gone in ("friction dust", "all_win_amt += net", 'by_inst[inst]["losses"] += 1'):
            self.assertNotIn(gone, app_src, f"门面仍残留内联片段 {gone!r}")

    def test_today_accumulation_uses_plus_equal(self):
        """`today_realized_gross` 必须 `+=` 而不是 `=`。

        bills 段可能已经给了非零初值（虽然当前实现恒 0），用 `=` 会把它覆盖掉。
        这条钉住"不要为了简洁改成赋值"。
        """
        app_src = APP.read_text(encoding="utf-8")
        self.assertIn('today_realized_gross += _stats["today_realized_gross"]', app_src)

    def test_module_uses_substring_not_equality_for_today(self):
        """直接在源码层面钉住 `in`（3 处）—— 与上面的行为测试互为补充。"""
        mod_src = MODULE.read_text(encoding="utf-8")
        body = mod_src.split('"""', 2)[-1]      # 跳过模块文档串（它"提到"了 in）
        self.assertEqual(body.count("if today_bj_str in t_time:"), 3,
                         "三处当日判定都必须是子串判断")
        self.assertNotIn("today_bj_str == t_time", body)

    def test_all_eight_outputs_consumed_by_facade(self):
        app_src = APP.read_text(encoding="utf-8")
        for key in ("by_inst", "today_realized_gross", "today_win_trades",
                    "today_loss_trades", "all_win_trades", "all_loss_trades",
                    "all_win_amt", "all_loss_amt"):
            self.assertIn(f'_stats["{key}"]', app_src, f"门面未取用 {key}")

    def test_module_is_pure_no_dashboard_import(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertFalse(a.name.startswith("dashboard"),
                                     f"反向 import {a.name}")
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or "").startswith("dashboard"),
                                 f"反向 import {node.module}")

    def test_module_does_not_read_external_state(self):
        """纯计算：除了入参，不得出现模块级/全局读取。"""
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        # `tree.body[0]` 是模块文档串（Expr），要显式找函数
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        assigned = {n.id for n in ast.walk(fn)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        loaded = {n.id for n in ast.walk(fn)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
        import builtins
        free = loaded - assigned - params - set(dir(builtins))
        self.assertEqual(free, set(), f"存在未绑定的外部名: {sorted(free)}")


if __name__ == "__main__":
    unittest.main()
