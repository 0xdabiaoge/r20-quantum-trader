r"""Binance 下单参数构建抽取对拍门（第一百一十二刀）。

`r20_backend/exchanges/binance.py` 里两段 → `r20_backend/exchanges/binance_orders.py`：
- `build_order_params(...)`：`place_order` 中段的参数归一化（数量/价格按 `step`/`tick`
  **向下取整**、`LIMIT`/`MARKET` 选择、`newClientOrderId`/`positionSide`/`reduceOnly`）；
- `apply_protective_qty_policy(...)`：保护单（TP/SL）**数量策略**，两处逐字重复的 6 行合并。

## 本门钉两条安全契约

1. **`reduceOnly` 与 `positionSide` 互斥**（审计 §2 契约）：两者同时给 ⇒ 主动抛
   `ValueError`，**不得**把矛盾参数发到交易所（对冲模式下交易所会拒单且语义不清）。
   原先该判断埋在下单方法中段、外包一层 `signed_request`，很难单独验证。
2. 数量策略决定"平多少"：给了数量 ⇒ `quantity` + `reduce_only=True` + `close_position=False`；
   没给 ⇒ `close_position=True`（**整仓平**）。TP/SL 两处必须**共用同一个函数**
   （本门断言两处调用点都是它），否则日后会各自漂移。

基线：`7658a99`（本刀动工前最后提交）。
"""
from __future__ import annotations

import ast
import builtins
import subprocess
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PRE = "7658a99"
FACADE = ROOT / "r20_backend" / "exchanges" / "binance.py"
MOD = ROOT / "r20_backend" / "exchanges" / "binance_orders.py"


def _baseline_cls() -> ast.ClassDef:
    r = subprocess.run(["git", "show", f"{PRE}:r20_backend/exchanges/binance.py"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, f"基线取不到：{r.stderr[:200]}"
    return next(n for n in ast.parse(r.stdout).body
                if isinstance(n, ast.ClassDef) and n.name == "BinanceAdapter")


def _baseline_method(name: str) -> ast.FunctionDef:
    return next(n for n in _baseline_cls().body
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _impl(name: str) -> ast.FunctionDef:
    t = ast.parse(MOD.read_text(encoding="utf-8"))
    return next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _facade_calls(name: str) -> list:
    return [n for n in ast.walk(ast.parse(FACADE.read_text(encoding="utf-8")))
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == name]


def _spec(step="0.001", tick="0.1"):
    return SimpleNamespace(step_size=Decimal(step), tick_size=Decimal(tick))


def _base_kwargs(**over):
    kw = dict(inst="BTCUSDT", position_side="", price=None, qty=2, reduce_only=False,
              s="BUY", spec=_spec(), text="", tif="gtc")
    kw.update(over)
    return kw


class BinanceOrdersExtractionTest(unittest.TestCase):
    def test_segments_are_ast_identical_to_baseline(self):
        # ① build_order_params ← place_order 语句 6..13
        seg = _baseline_method("place_order").body[6:14]
        body = list(_impl("build_order_params").body)[:-1]  # 去掉尾部 return
        body = body[1:] if (body and isinstance(body[0], ast.Expr)
                            and isinstance(body[0].value, ast.Constant)
                            and isinstance(body[0].value.value, str)) else body
        self.assertEqual(
            ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False),
            ast.dump(ast.Module(body=seg, type_ignores=[]), include_attributes=False),
            "build_order_params 段体与抽取前**不再同一棵 AST**")
        # ② apply_protective_qty_policy ← attach 的 TP 分支 If.body[1]
        tp = _baseline_method("attach_protective_orders").body[10].body[1]
        body2 = list(_impl("apply_protective_qty_policy").body)
        body2 = body2[1:] if (body2 and isinstance(body2[0], ast.Expr)
                              and isinstance(body2[0].value, ast.Constant)
                              and isinstance(body2[0].value.value, str)) else body2
        self.assertEqual(
            ast.dump(ast.Module(body=body2, type_ignores=[]), include_attributes=False),
            ast.dump(ast.Module(body=[tp], type_ignores=[]), include_attributes=False),
            "apply_protective_qty_policy 段体与抽取前**不再同一棵 AST**")

    def test_baseline_branches_were_really_identical(self):
        """合并的前提：TP/SL 两处分支**逐字相同**（否则不该合并）。"""
        m = _baseline_method("attach_protective_orders")
        self.assertEqual(ast.dump(m.body[10].body[1], include_attributes=False),
                         ast.dump(m.body[11].body[1], include_attributes=False))

    def test_call_sites_pass_every_parameter_once_same_name(self):
        for name in ("build_order_params", "apply_protective_qty_policy"):
            with self.subTest(fn=name):
                params = [a.arg for a in _impl(name).args.kwonlyargs]
                calls = _facade_calls(name)
                self.assertTrue(calls, f"{name} 在门面没有调用点")
                for call in calls:
                    self.assertEqual(call.args, [])
                    self.assertEqual([k.arg for k in call.keywords], params)
                    for k in call.keywords:
                        self.assertEqual(ast.unparse(k.value), k.arg)

    def test_both_protective_branches_share_one_helper(self):
        """TP/SL 必须都用同一个函数 —— 否则又会各自漂移。"""
        self.assertEqual(len(_facade_calls("apply_protective_qty_policy")), 2,
                         "止盈/止损两处都必须调用该助手")

    def test_no_undeclared_free_names(self):
        module = ast.parse(MOD.read_text(encoding="utf-8"))
        # 模块级可解析名：函数/类定义 + **import** + 赋值目标
        # （漏掉 import 是我第一版就踩的坑：子模块自己 import 标准库类型后，
        #  这一条会误报成"自由名解析不到"——与审计门当初同一处缺口。）
        mod_names = set()
        for n in module.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                mod_names.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    mod_names.add(a.asname or a.name.split(".")[0])
            elif isinstance(n, ast.Assign):
                for tg in n.targets:
                    if isinstance(tg, ast.Name):
                        mod_names.add(tg.id)
        for name in ("build_order_params", "apply_protective_qty_policy"):
            with self.subTest(fn=name):
                fn = _impl(name)
                local = {a.arg for a in fn.args.kwonlyargs}
                for n in ast.walk(fn):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                        local.add(n.id)
                    if isinstance(n, ast.ExceptHandler) and n.name:
                        local.add(n.name)
                    if isinstance(n, (ast.Import, ast.ImportFrom)):
                        for a in n.names:
                            local.add(a.asname or a.name.split(".")[0])
                reads = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)
                         and isinstance(n.ctx, ast.Load)}
                missing = sorted(reads - local - set(dir(builtins)) - mod_names)
                self.assertEqual(missing, [], f"{name} 解析不到: {missing}")

    # ---------- 行为例：参数构建 ----------

    def _build(self, **over):
        from r20_backend.exchanges.binance_orders import build_order_params
        return build_order_params(**_base_kwargs(**over))

    def test_market_order_when_no_price(self):
        p = self._build(price=None)
        self.assertEqual(p["type"], "MARKET")
        self.assertNotIn("price", p)
        self.assertNotIn("timeInForce", p)
        self.assertEqual(p["symbol"], "BTCUSDT")
        self.assertEqual(p["side"], "BUY")
        self.assertNotIn("newClientOrderId", p, "空 text 不落该键")
        self.assertNotIn("positionSide", p)
        self.assertNotIn("reduceOnly", p)

    def test_limit_order_rounds_down_price_to_tick(self):
        p = self._build(price="60123.4567", tif="gtc")
        self.assertEqual(p["type"], "LIMIT")
        self.assertEqual(p["timeInForce"], "GTC", "tif 必须大写")
        self.assertEqual(p["price"], "60123.4", "按 tick=0.1 向下取整，且不留尾零")

    def test_zero_price_is_market(self):
        self.assertEqual(self._build(price=0)["type"], "MARKET")

    def test_quantity_rounded_down_to_step(self):
        self.assertEqual(self._build(qty=1.23456)["quantity"], "1.234")
        self.assertEqual(self._build(qty=2)["quantity"], "2", "整值不留尾零")

    def test_spec_none_uses_fallbacks(self):
        self.assertEqual(self._build(qty=1.5, spec=None)["quantity"], "1.5")
        self.assertEqual(self._build(price="10.04", spec=None)["price"], "10",
                         "无 spec 时 tick 兜底 0.1")

    def test_client_id_and_position_side(self):
        p = self._build(text="  tg-1  ", position_side="long")
        self.assertEqual(p["newClientOrderId"], "tg-1", "必须 strip")
        self.assertEqual(p["positionSide"], "LONG", "必须大写")

    def test_reduce_only_requires_hedge_flag_absent(self):
        p = self._build(reduce_only=True, position_side="")
        self.assertEqual(p["reduceOnly"], "true")

    def test_reduce_only_and_position_side_are_mutually_exclusive(self):
        """审计 §2 契约：矛盾参数必须在本地下单前就炸掉。"""
        with self.assertRaises(ValueError) as cm:
            self._build(reduce_only=True, position_side="long")
        self.assertIn("互斥", str(cm.exception))

    # ---------- 行为例：保护单数量策略 ----------

    def test_qty_policy_with_quantity(self):
        from r20_backend.exchanges.binance_orders import apply_protective_qty_policy
        kw = {"symbol": "BTCUSDT"}
        self.assertIsNone(apply_protective_qty_policy(req_kwargs=kw, qty_str="0.5"))
        self.assertEqual(kw["quantity"], "0.5")
        self.assertTrue(kw["reduce_only"])
        self.assertFalse(kw["close_position"])
        self.assertEqual(kw["symbol"], "BTCUSDT", "只加策略键，不动其他")

    def test_qty_policy_without_quantity_closes_whole_position(self):
        from r20_backend.exchanges.binance_orders import apply_protective_qty_policy
        kw = {}
        apply_protective_qty_policy(req_kwargs=kw, qty_str=None)
        self.assertTrue(kw["close_position"], "未给数量 ⇒ 整仓平")
        self.assertNotIn("quantity", kw)
        self.assertNotIn("reduce_only", kw, "整仓平模式不落 reduce_only")

    def test_judgment_actually_notices_a_change(self):
        seg = _baseline_method("place_order").body[6:14]
        self.assertNotEqual(
            ast.dump(ast.Module(body=list(seg) + [ast.Pass()], type_ignores=[]), include_attributes=False),
            ast.dump(ast.Module(body=list(seg), type_ignores=[]), include_attributes=False))


if __name__ == "__main__":
    unittest.main()
