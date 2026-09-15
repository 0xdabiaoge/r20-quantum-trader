r"""自进化复盘上下文装配抽取对拍门（第一百零五刀）。

`self_improvement_engine.py::compose_evolution_prompts`（95 行）里两段 → `scripts/evolution/review_context.py`：
- `summarize_closed_trades(...)`：平仓统计 + 可观测性审计摘要（8 输出）；
- `build_host_constitution(...)`：**宿主宪章**（Code is Law 代码层硬约束）。

## 本门的重点不是"搬对了"，而是"**宪章不能被悄悄改坏**"

宿主宪章是安全语义文本：它要求模型"字段缺失不得解读为证据""基准心法不得静默删除"
"证据不足必须 NO_CHANGE"。埋在 95 行提示词装配里时，删掉一条没人会注意；
本门把四条硬约束**逐条**断言，并验证 `observability_brief` 真的被插值。

基线：`78c4da1`（本刀动工前最后提交）。
"""
from __future__ import annotations

import ast
import builtins
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PRE = "78c4da1"
FACADE = ROOT / "scripts" / "self_improvement_engine.py"
MOD = ROOT / "scripts" / "evolution" / "review_context.py"
OWNER = "compose_evolution_prompts"
SPECS = {"summarize_closed_trades": (3, 10), "build_host_constitution": (20, 20)}


def _baseline_fn() -> ast.FunctionDef:
    r = subprocess.run(["git", "show", f"{PRE}:scripts/self_improvement_engine.py"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, f"基线取不到：{r.stderr[:200]}"
    return next(n for n in ast.parse(r.stdout).body
                if isinstance(n, ast.FunctionDef) and n.name == OWNER)


def _impl(name: str) -> ast.FunctionDef:
    t = ast.parse(MOD.read_text(encoding="utf-8"))
    return next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _facade_calls() -> dict:
    out = {}
    for n in ast.walk(ast.parse(FACADE.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in SPECS:
            out.setdefault(n.func.id, n)
    return out


class EvolutionReviewContextTest(unittest.TestCase):
    def test_segments_are_ast_identical_to_baseline(self):
        base = _baseline_fn()
        for name, (lo, hi) in SPECS.items():
            with self.subTest(fn=name):
                seg = base.body[lo:hi + 1]
                body = list(_impl(name).body)
                if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                if body and isinstance(body[-1], ast.Return):
                    body = body[:-1]
                self.assertEqual(
                    ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False),
                    ast.dump(ast.Module(body=seg, type_ignores=[]), include_attributes=False),
                    f"{name} 段体与抽取前**不再同一棵 AST**")

    def test_calls_pass_every_parameter_once_same_name(self):
        calls = _facade_calls()
        for name in SPECS:
            with self.subTest(fn=name):
                params = [a.arg for a in _impl(name).args.kwonlyargs]
                call = calls[name]
                self.assertEqual(call.args, [])
                self.assertEqual([k.arg for k in call.keywords], params)
                for k in call.keywords:
                    self.assertEqual(ast.unparse(k.value), k.arg)

    def test_statistics_call_unpacks_all_eight_in_natural_order(self):
        tree = ast.parse(FACADE.read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == OWNER)
        tgt = [n.targets[0] for n in ast.walk(fn) if isinstance(n, ast.Assign)
               and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == "summarize_closed_trades"]
        self.assertEqual(len(tgt), 1)
        self.assertEqual([e.id for e in tgt[0].elts],
                         ["total", "wins", "losses", "win_rate", "total_net", "total_fees",
                          "snapshot_audit", "observability_brief"])

    def test_no_undeclared_free_names(self):
        module = ast.parse(MOD.read_text(encoding="utf-8"))
        mod_names = {n.name for n in module.body if isinstance(n, ast.FunctionDef)}
        for name in SPECS:
            with self.subTest(fn=name):
                fn = _impl(name)
                local = {a.arg for a in fn.args.kwonlyargs}
                for n in ast.walk(fn):
                    if isinstance(n, ast.Lambda):
                        local |= {a.arg for a in n.args.args}
                    if isinstance(n, ast.comprehension):
                        tg = n.target
                        for e in (tg.elts if isinstance(tg, (ast.Tuple, ast.List)) else [tg]):
                            if isinstance(e, ast.Name):
                                local.add(e.id)
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

    # ---------- 行为例：统计 ----------

    def _sum(self, trades, audit=None, render=None):
        from scripts.evolution.review_context import summarize_closed_trades
        return summarize_closed_trades(
            closed_trades=trades,
            audit_snapshot_observability=audit or (lambda ts: {"n": len(ts)}),
            render_observability_brief=render or (lambda a: f"brief:{a['n']}"))

    def test_statistics_classify_and_round(self):
        # 用**二进制可精确表示**的数，避免浮点舍入让断言变得不可复现
        trades = [{"net_pnl": 10.5, "fee": 0.1}, {"net_pnl": -3.25, "fee": 0.2},
                  {"net_pnl": 0.0, "fee": 0.3}]
        total, wins, losses, win_rate, total_net, total_fees, audit, brief = self._sum(trades)
        self.assertEqual(total, 3)
        self.assertEqual(len(wins), 1)
        self.assertEqual(len(losses), 2, "净利为 0 计入亏损侧（`<= 0`，既有口径）")
        self.assertEqual(win_rate, 33.3)
        self.assertEqual(total_net, 7.25, "净利求和后保留 2 位（10.5 − 3.25）")
        self.assertEqual(total_fees, 0.6)
        self.assertEqual(audit, {"n": 3})
        self.assertEqual(brief, "brief:3")

    def test_statistics_empty_input_is_safe(self):
        total, wins, losses, win_rate, total_net, total_fees, _a, brief = self._sum([])
        self.assertEqual((total, len(wins), len(losses), win_rate, total_net, total_fees),
                         (0, 0, 0, 0.0, 0.0, 0.0), "空输入必须零除安全")

    # ---------- 行为例：宿主宪章（安全语义） ----------

    def test_constitution_contains_all_four_hard_rules(self):
        from scripts.evolution.review_context import build_host_constitution
        text = build_host_constitution(observability_brief="BRIEF-XYZ")
        self.assertIn("宿主宪章·代码层硬约束", text)
        self.assertIn("BRIEF-XYZ", text, "可观测性摘要必须被插值")
        # ① 逐单标注含义（数据源缺失不得当证据）
        self.assertIn("DYNAMICS_OBSERVED", text)
        self.assertIn("PARTIAL", text)
        self.assertIn("PRICE_ONLY / NONE", text)
        self.assertIn("字段缺失本身不得解读为任何证据", text)
        # ② 基准心法保护（不得静默删除）
        self.assertIn("is_baseline", text)
        self.assertIn("原样补回并留痕", text)
        self.assertIn("禁止静默删除", text)
        # ③ 证据不足必须 NO_CHANGE
        self.assertIn("NO_CHANGE 永不覆盖或清空长期记忆", text)
        # ④ 编号四条齐全（防误删一整条）
        for n in ("1.", "2.", "3.", "4."):
            self.assertIn(n, text)

    def test_constitution_is_pure_and_deterministic(self):
        from scripts.evolution.review_context import build_host_constitution
        self.assertEqual(build_host_constitution(observability_brief="X"),
                         build_host_constitution(observability_brief="X"))
        self.assertNotEqual(build_host_constitution(observability_brief="X"),
                            build_host_constitution(observability_brief="Y"))

    def test_judgment_actually_notices_a_change(self):
        seg = _baseline_fn().body[SPECS["build_host_constitution"][0]:
                                  SPECS["build_host_constitution"][1] + 1]
        self.assertNotEqual(
            ast.dump(ast.Module(body=seg + [ast.Pass()], type_ignores=[]), include_attributes=False),
            ast.dump(ast.Module(body=seg, type_ignores=[]), include_attributes=False))


if __name__ == "__main__":
    unittest.main()
