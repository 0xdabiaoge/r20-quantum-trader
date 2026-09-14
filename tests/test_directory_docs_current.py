"""目录说明文档与文件系统**保持一致**（结构优化阶段 4·B3 第三十三刀）。

## 这个测试在守什么

目标里有一条"**新增目录说明文档**"。本仓的目录说明写在各子包的 `__init__.py`
文档串里（`scripts/trader/`、`scripts/brain/`、`scripts/factors/` …），
每个都带一张「模块清单」表。

问题是：**这类文档会腐烂**。我这一阶段实测到 ——

| 子包 | 文档漏掉的模块 |
|---|---|
| `scripts/trader/` | `position_universe.py`（第三十一刀新增） |
| `scripts/factors/` | `scoring.py`、`candles_15m.py`（第二十九/三十二刀新增） |
| `r20_backend/council/` | 完全没有模块清单 |
| `scripts/ledger/` | 完全没有模块清单 |

而且**没有任何测试会红** —— 文档腐烂是静默的。等到有人照着清单找模块时才发现。

## 做法

对每个受管子包：把 `__init__.py` 文档串里出现的 `xxx.py` 名字
**与磁盘上的实际 `.py` 文件**做双向集合比对：

- 磁盘上有、文档没提 → **新增了模块却没更新说明**；
- 文档提了、磁盘上没有 → **模块被删/改名但说明没改**（更危险：指向不存在的文件）。

## ⚠️ 这个测试的边界（必须说清）

它只保证**"名字出现过"**，**不保证描述内容正确**。- 描述写得对不对、
  注入面列得准不准，机器判不了。故它挡的是"**忘了登记**"，不是"**写错了**"。

`__pycache__`、`__init__.py` 自身、以及 `_` 前缀的私有辅助文件不参与比对。
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 受管子包 → 该子包的文件名出现形式。
#: `allowed_extra` 是在文档里**有意**提到但不在本目录的文件（如门面、测试）。
#: `docs` 是"登记名册"的额外来源 —— 有些子包把清单写在 README 而不是 __init__.py
#: （`dashboard_payload/` 就是：它的总约定在 r20_backend/README.md）。
MANAGED = {
    "scripts/trader": {"allowed_extra": set()},
    "scripts/brain": {"allowed_extra": {"ai_brain_trader.py"}},
    "scripts/factors": {"allowed_extra": {"factor_library.py"}},
    "scripts/ledger": {"allowed_extra": {"sync_full_ledger.py"}},
    "r20_backend/council": {"allowed_extra": {"council_manager.py"}},
    "r20_backend/dashboard_payload": {
        "allowed_extra": {"dashboard.py", "app.py"},
        "docs": ["r20_backend/README.md"],
    },
    # 第三十八刀补登记：`execution_router.py::open_protected_position` 的风控闸门
    # 抽成 `risk_gates.py` 后才发现本子包**此前根本不在受管名单里** ——
    # 也就是说 `indicators.py` / `sizing.py` / `circuit_breaker.py` 烂了文档也没人管。
    # 顺手纳入。
    "r20_backend/execution": {"allowed_extra": {"execution_router.py"}},
}

#: 从文档里抽出的 `xxx.py` 文件名。
#:
#: ⚠️ 左侧用 `(?<![\w*])` 而不是 `\b`：`\b` 会在
#: `tests/test_brain_*_extraction.py` 这样的**通配写法**中间匹配到 `_extraction.py`，
#: 于是报"提到 _extraction.py 但全仓找不到"—— 假警报。
#: 要求左边既不是词字符、也不是 `*`（通配符），才是真正的文件名开头。
_DOC_NAME = re.compile(r"(?<![\w*])([a-z_][a-z0-9_]*\.py)\b")


def _doc_names(init_py: Path, extra_docs: list[str] | None = None) -> set[str]:
    """该子包**登记名册**里提到的所有 `xxx.py`。

    名册来源 = `__init__.py` 文档串 + 任意 `docs` 里的 Markdown。
    （`dashboard_payload/` 的清单写在 `r20_backend/README.md` —— 那里才是
    新人会去翻的地方，所以在 README 里登记是合理的，不该被本测试判为漏登记。）
    """
    tree = ast.parse(init_py.read_text(encoding="utf-8"))
    texts = [ast.get_docstring(tree) or ""]
    for rel in (extra_docs or []):
        texts.append((ROOT / rel).read_text(encoding="utf-8"))
    return {m.group(1) for t in texts for m in _DOC_NAME.finditer(t)}


def _disk_modules(pkg_dir: Path) -> set[str]:
    out = set()
    for p in pkg_dir.glob("*.py"):
        if p.name == "__init__.py":
            continue
        if p.name.startswith("_"):
            continue
        out.add(p.name)
    return out


class DirectoryDocsTest(unittest.TestCase):
    def test_every_managed_package_has_a_docstring(self):
        for rel in MANAGED:
            init = ROOT / rel / "__init__.py"
            with self.subTest(pkg=rel):
                self.assertTrue(init.exists(), f"{rel}/__init__.py 不存在")
                tree = ast.parse(init.read_text(encoding="utf-8"))
                self.assertTrue(ast.get_docstring(tree),
                                f"{rel}/__init__.py 没有文档串")

    def test_no_undocumented_module(self):
        """磁盘上的每个模块都必须在 `__init__.py` 文档里出现过。"""
        problems = []
        for rel, cfg in MANAGED.items():
            pkg = ROOT / rel
            documented = _doc_names(pkg / "__init__.py", cfg.get("docs"))
            for mod in sorted(_disk_modules(pkg)):
                if mod not in documented:
                    problems.append(f"{rel}/{mod} 未登记在 {rel}/__init__.py 的说明里")
        self.assertEqual(problems, [],
                         "新增模块后请更新该子包 __init__.py 的模块清单（本测试就是为此而设）")

    def test_no_doc_reference_to_a_missing_file(self):
        """文档里提到的 `.py` 必须在磁盘上真实存在。

        这比"漏登记"更危险：说明指向一个**不存在**的文件，会把人引到死路。
        """
        problems = []
        for rel, cfg in MANAGED.items():
            pkg = ROOT / rel
            existing = {p.name for p in pkg.glob("*.py")}
            for name in sorted(_doc_names(pkg / "__init__.py", cfg.get("docs"))):
                if name in existing:
                    continue
                if name in cfg.get("allowed_extra", set()):
                    continue
                # 允许引用同域的**兄弟**包文件（如 tests/、项目根），只要全仓能找到
                hits = list(ROOT.rglob(name))
                hits = [h for h in hits if ".venv" not in str(h) and "node_modules" not in str(h)]
                if not hits:
                    problems.append(f"{rel}/__init__.py 提到 {name}，但全仓找不到该文件")
        self.assertEqual(problems, [])

    def test_manifest_tables_are_present(self):
        """受管子包的文档串里应有一张「模块清单」表（便于"新文件放哪"）。"""
        for rel in ("scripts/trader", "scripts/brain", "scripts/factors",
                    "scripts/ledger", "r20_backend/council"):
            init = ROOT / rel / "__init__.py"
            doc = ast.get_docstring(ast.parse(init.read_text(encoding="utf-8"))) or ""
            with self.subTest(pkg=rel):
                self.assertIn("模块清单", doc,
                              f"{rel}/__init__.py 缺少「模块清单」表")

    def test_managed_packages_all_exist(self):
        for rel in MANAGED:
            with self.subTest(pkg=rel):
                self.assertTrue((ROOT / rel).is_dir(), f"{rel} 不是目录")


class DocsDescribeRealityTest(unittest.TestCase):
    """抽查：文档里声称的"注入面"是否与代码相符（只查可机器判定的几条）。"""

    def test_factors_scoring_is_dependency_free(self):
        """`scoring.py` 文档称"注入面无" → 断言它确实不 import 取数模块。"""
        src = (ROOT / "scripts" / "factors" / "scoring.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods |= {a.asname or a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                mods |= {a.asname or a.name for a in node.names}
        self.assertEqual(mods - {"annotations", "Any", "Dict"},
                         set(), f"scoring.py 声称零注入面，却 import 了 {mods}")

    def test_candles_15m_does_not_import_fetching(self):
        """`candles_15m.py` 文档称"取数留在门面" → 断言它不 import 取数函数。"""
        tree = ast.parse((ROOT / "scripts" / "factors" / "candles_15m.py")
                         .read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertNotIn("market_data_service", mods)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names |= {a.name for a in node.names}
        self.assertNotIn("fetch_candles", names)

    def test_position_universe_does_not_fetch(self):
        """`position_universe.py` 文档称"不取数" → 断言无任何网络/交易所 import。"""
        tree = ast.parse((ROOT / "scripts" / "trader" / "position_universe.py")
                         .read_text(encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods |= {a.asname or a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                mods |= {a.asname or a.name for a in node.names}
        for forbidden in ("requests", "urllib", "okx_rest", "subprocess", "os"):
            self.assertNotIn(forbidden, mods)


if __name__ == "__main__":
    unittest.main()
