"""仪表盘载荷拆分的「薄壳纪律」回归闸（结构优化阶段 2 / B2）。

## 背景：为什么需要这道闸

`dashboard/app.py` 的域代码正被逐步迁到 `r20_backend/dashboard_payload/`。迁移用
**薄壳 + 核心**：核心收显式参数，门面薄壳在**调用时**解析门面模块全局（路径常量、
甚至可调用对象）并注入。

这么做的唯一理由是**保留测试注入接缝**：测试与 `tests/config_sandbox.py` 靠
`patch.object(dashboard, "LOG_FILE"/"STATE_JSON_FILE"/"DATA_DIR"/…)` 把读写重定向到沙箱。
核心若在导入期绑定这些名字，补丁就**静默失效**、读到真实项目文件 —— 那正是
"测试写生产 data/" 的事故形态。

## 本闸钉的四件事（每一条都由实际踩过的坑得来）

1. **薄壳不得自递归**。生成薄壳时漏掉 `_core_` 前缀会写成
   `return load_position_trackers(POSITION_TRACKER_FILE)` —— 无限递归，
   且只有在真的调用并带上多余实参时才暴露（`TypeError: takes 0 positional
   arguments but 1 was given`）。
2. **实参个数必须等于核心形参个数**。B6 曾出现核心新增 `root` 参数而薄壳没跟上。
3. **实参顺序必须与核心形参逐位对齐**。B2 第三刀把
   `(factor_file, decisions_file, state_file)` 传成了
   `(AI_DECISIONS_FILE, FACTOR_LIBRARY_FILE, STATE_JSON_FILE)` ——
   三个路径整体错配，症状是"因子库读到了决策文件"，而**单测全绿**
   （单测要么只喂 tracker、要么不校验这三个文件的具体来源），只有逐例差分才发现。
4. **核心模块不得反向 import `dashboard.app`**（会与 `routers/dashboard.py` 的
   `import dashboard.app` 构成循环）。

另外钉住门面公开面：测试直接经 `dashboard.<name>` 调用的那批符号必须仍在。
"""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard.app as app  # noqa: E402
from r20_backend import dashboard_payload as payload_pkg  # noqa: E402
from r20_backend.dashboard_payload import cache, factors, health, market, slim  # noqa: E402

PAYLOAD_DIR = ROOT / "r20_backend" / "dashboard_payload"

# 测试与沙箱会直接访问的门面符号（实测清单：tests/*.py 的 dashboard.<name>）
FACADE_SURFACE = [
    # 路径常量（沙箱重定向目标）
    "DATA_DIR", "LOG_FILE", "STATE_JSON_FILE", "DASHBOARD_CACHE_FILE",
    "AI_DECISIONS_FILE", "AI_HISTORY_FILE", "AI_LAST_PROMPT_FILE", "AI_MEMORY_MD_FILE",
    "NEWS_SENTIMENT_FILE", "REPORT_JSON_FILE", "LEDGER_JSON_FILE",
    "POSITION_TRACKER_FILE", "FACTOR_LIBRARY_FILE", "SNAPSHOTS_JSON_FILE",
    # 已迁出的函数（必须仍可从 dashboard.app 取到）
    "slim_payload", "load_position_trackers", "enrich_position_risk_fields",
    "_load_local_factor_library", "_build_factors_from_local_files",
    "_load_cross_venue_data", "load_trading_memory_md", "build_ai_health",
    "load_persisted_dashboard_cache", "persist_dashboard_cache",
    "_inject_local_data_into_stale", "_is_meaningful_dashboard_snapshot",
    "_safe_float", "_global_env_axis", "_load_portfolio_risk_data",
    "_load_multi_venue_portfolio", "get_target_instruments",
    # 载荷装配主体
    "update_cache_cycle", "refresh_cache_if_needed", "get_cache_lock",
]

# 核心模块白名单：新迁出的域模块都应在此，且必须被门面导入（否则 sandbox 覆盖不到）
CORE_MODULES = (slim, market, factors, health, cache)


def _core_aliases() -> dict[str, object]:
    """收集 dashboard.app 里 `from ...dashboard_payload.X import Y as _core_...` 的别名。"""
    out: dict[str, object] = {}
    for name, value in vars(app).items():
        if name.startswith("_core") and callable(value):
            out[name] = value
    return out


_STOP = {"file", "dir", "path", "json", "md", "a", "the", "of", "for", "in", "to"}


def _tokens(name: str) -> set[str]:
    """把标识符拆成有意义的小词（丢掉 file/dir/json/md 之类后缀词）。"""
    import re
    parts = re.split(r"[^a-z0-9]+", name.lower())
    return {p for p in parts if p and p not in _STOP}


class ShellDisciplineTests(unittest.TestCase):
    def setUp(self):
        self.aliases = _core_aliases()
        self.assertTrue(self.aliases, "dashboard.app 里找不到任何 _core_* 薄壳别名")

    # ── 1/2/3. 薄壳调用形态 ────────────────────────────────────
    def test_every_shell_forwards_correctly(self):
        problems: list[str] = []
        checked = 0
        app_module_name = getattr(app, "__name__", "dashboard.app")
        for fname, fobj in vars(app).items():
            if fname.startswith("__") or not inspect.isfunction(fobj):
                continue
            # 只审查**定义在本门面模块**里的函数：全量跑时别的测试会往 dashboard.app
            # 上挂函数（inspect.getsource 拿到的首语句是赋值而非 def），
            # 单独跑该用例时不存在 → 曾导致"单跑通过、全量失败"。
            if getattr(fobj, "__module__", None) != app_module_name:
                continue
            try:
                src = textwrap.dedent(inspect.getsource(fobj))
                node = ast.parse(src).body[0]
            except (OSError, SyntaxError, IndexError, TypeError):
                continue
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            shell_params = [a.arg for a in node.args.args]
            # 1) 自递归必须在**别名过滤之前**检查 —— 薄壳写成 `return <同名函数>(...)`
            #    时它根本不带 _core_ 前缀，若放在下面就会被整段跳过（负向验证抓到过）。
            for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
                if isinstance(call.func, ast.Name) and call.func.id == fname:
                    problems.append(f"{fname}: 薄壳调用了自己（无限递归）")
            for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
                if not (isinstance(call.func, ast.Name) and call.func.id in self.aliases):
                    continue
                checked += 1
                core = self.aliases[call.func.id]
                core_params = list(inspect.signature(core).parameters)
                # 2) 实参个数
                if len(call.args) != len(core_params):
                    problems.append(
                        f"{fname}: 实参 {len(call.args)} 个，核心 {call.func.id}"
                        f" 形参 {len(core_params)} 个 {core_params}")
                    continue
                # 3) 顺序：门面自身参数必须**按原顺序**出现在实参尾部
                tail = [a.id for a in call.args[-len(shell_params):] if isinstance(a, ast.Name)] \
                    if shell_params else []
                if shell_params and tail != shell_params:
                    problems.append(
                        f"{fname}: 透传参数顺序 {tail} != 门面形参顺序 {shell_params}")
                # 3b) 注入项必须与核心形参名逐位对应（前缀部分应为门面模块级名字）
                for arg, pname in zip(call.args, core_params):
                    if not isinstance(arg, ast.Name):
                        problems.append(f"{fname}: 实参 {ast.unparse(arg)} 非简单名字，无法核对")
                        continue
                    if arg.id in shell_params:
                        continue
                    if not hasattr(app, arg.id) and not arg.id.isupper():
                        problems.append(
                            f"{fname}: 注入项 {arg.id}（对应核心形参 {pname}）在门面不存在")
                    if not (_tokens(arg.id) & _tokens(pname)):
                        problems.append(
                            f"{fname}: 注入项 {arg.id} 与核心形参 {pname} 名称不相干 —— "
                            f"很可能是实参顺序错位（本阶段第三刀就是被这个坑到的）")
        self.assertGreater(checked, 0, "未找到任何薄壳调用，检查器失效")
        self.assertEqual(problems, [], "薄壳转发不合规：\n  " + "\n  ".join(problems))

    # ── 4. 无循环依赖 ─────────────────────────────────────────
    def test_core_modules_do_not_import_dashboard_app(self):
        offenders = []
        for path in sorted(PAYLOAD_DIR.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name == "dashboard.app" or a.name.startswith("dashboard."):
                            offenders.append(f"{path.name}:{node.lineno} import {a.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod == "dashboard" or mod.startswith("dashboard."):
                        offenders.append(f"{path.name}:{node.lineno} from {mod} import ...")
        self.assertEqual(offenders, [], "载荷模块反向 import 了 dashboard 包（循环依赖）:\n  "
                         + "\n  ".join(offenders))

    def test_core_modules_are_imported_by_facade(self):
        """新模块必须被门面导入 —— config_sandbox 只重定向 sys.modules 里已有模块的属性。"""
        missing = [m.__name__ for m in CORE_MODULES
                   if not any(getattr(v, "__module__", None) == m.__name__
                              for v in vars(app).values())]
        self.assertEqual(missing, [], f"这些域模块未被 dashboard.app 导入，沙箱覆盖不到: {missing}")

    # ── 5. 公开面 ─────────────────────────────────────────────
    def test_facade_surface_intact(self):
        missing = [n for n in FACADE_SURFACE if not hasattr(app, n)]
        self.assertEqual(missing, [], f"dashboard.app 缺少测试直接引用的符号: {missing}")

    # ── 6. 接缝传导（最关键）：patch 门面路径常量必须影响已迁出的核心 ──
    def test_path_constant_patch_reaches_moved_cores(self):
        import json
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="r20-dash-seam-"))
        (tmp / "t.json").write_text(json.dumps({"BTC-USDT-SWAP_long": {"strategy_tag": "SEAM"}}),
                                    encoding="utf-8")
        with patch.object(app, "POSITION_TRACKER_FILE", str(tmp / "t.json")):
            got = app.load_position_trackers()
        self.assertEqual(got.get("BTC-USDT-SWAP_long", {}).get("strategy_tag"), "SEAM",
                         "patch 门面 POSITION_TRACKER_FILE 未传导到已迁出的核心")

        # 三个路径各带**可区分标记**：只要实参顺序错位，任一断言都会失败
        # （只断言其中一个文件是抓不到错位的 —— 本阶段第三刀正是如此漏过的）。
        (tmp / "state.json").write_text(json.dumps({
            "timestamp": "TS-SEAM", "instruments": [{"instId": "BTC-USDT-SWAP", "desc": "FROM_STATE"}]}),
            encoding="utf-8")
        (tmp / "factor.json").write_text(json.dumps({
            "instruments": [{"instId": "BTC-USDT-SWAP", "chg24h": 42.5}]}), encoding="utf-8")
        (tmp / "dec.json").write_text(json.dumps({
            "BTC-USDT-SWAP": {"decision": {"action": "BUY_LONG", "summary_reason": "FROM_DECISIONS"}}}),
            encoding="utf-8")
        with patch.object(app, "STATE_JSON_FILE", str(tmp / "state.json")), \
             patch.object(app, "FACTOR_LIBRARY_FILE", str(tmp / "factor.json")), \
             patch.object(app, "AI_DECISIONS_FILE", str(tmp / "dec.json")):
            flist, state = app._build_factors_from_local_files([], "NOW")
        self.assertEqual(state.get("timestamp"), "TS-SEAM",
                         "patch 门面 STATE_JSON_FILE 未传导（实参顺序错位？）")
        btc = next((x for x in flist if x.get("instId") == "BTC-USDT-SWAP"), None)
        self.assertIsNotNone(btc, "沙箱 state.json 未被用于枚举标的")
        self.assertEqual(btc.get("action"), "BUY_LONG",
                         "AI_DECISIONS_FILE 未传导（实参顺序错位？）")
        self.assertEqual(btc.get("chg24h"), 42.5,
                         "FACTOR_LIBRARY_FILE 未传导（实参顺序错位？）")

    def test_missing_production_write_guard(self):
        """沙箱外的真实路径必须是生产 data/ —— 若核心持有自己的副本，写盘会落到生产。"""
        self.assertTrue(str(app.DATA_DIR).endswith("data") or "data" in str(app.DATA_DIR))


if __name__ == "__main__":
    unittest.main(verbosity=2)
