"""`tests/source_scan` 领域定位工具的回归（结构优化阶段 4 引入）。

## 为什么需要这个文件

阶段 4 把主脑/交易员的大文件拆进子包，随之而来的是**三类源码锚点的失效**：

1. `ast.parse(单文件)` + 按函数名取节点 → 搬走即 `StopIteration`；
2. `inspect.getsource(门面函数)` → 门面只剩薄壳，取到的是转发语句；
3. 单文件 `assertIn` / `assertNotIn` → 正向翻红（好），负向**静默空转**（坏）。

`source_scan` 提供的域定位就是给这三类用的。它本身必须可信 ——
**一个定位错的工具会让所有依赖它的断言假通过**，所以它自己也要有回归。
本文件用**临时目录搭出「门面 + 子包」的真实目录形状**来验证，不依赖生产代码。
"""
from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from tests import source_scan


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")


class SourceAreaShapeTest(unittest.TestCase):
    def test_area_includes_facade_and_named_subpackage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "scripts/facade.py", "x = 1\n")
            _write(root, "scripts/pkg/__init__.py", "")
            _write(root, "scripts/pkg/mod.py", "y = 2\n")
            area = source_scan.source_area(root / "scripts" / "facade.py", pkg_name="pkg")
            names = sorted(p.name for p in area)
            self.assertEqual(names, ["__init__.py", "facade.py", "mod.py"])

    def test_default_pkg_name_strips_manager_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "council_manager.py", "x = 1\n")
            _write(root, "council/debate.py", "y = 2\n")
            area = source_scan.source_area(root / "council_manager.py")
            self.assertEqual(sorted(p.name for p in area), ["council_manager.py", "debate.py"])


class FindFunctionNodeTest(unittest.TestCase):
    def _tree(self, td: str):
        root = Path(td)
        _write(root, "scripts/facade.py", """
            def moved():
                return "impl-body"

            def only_here():
                return 1
        """)
        return root / "scripts" / "facade.py"

    def test_finds_node_in_facade(self):
        with tempfile.TemporaryDirectory() as td:
            facade = self._tree(td)
            node, path = source_scan.find_function_node(facade, "only_here")
            self.assertEqual(node.name, "only_here")
            self.assertEqual(path.name, "facade.py")

    def test_prefers_implementation_over_facade_shell(self):
        """门面留同名薄壳时，应返回**实现体**那份（源码更长者）。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "scripts/facade.py", """
                def moved():
                    return _moved_impl()

                def only_here():
                    return 1
            """)
            _write(root, "scripts/pkg/mod.py", """
                def moved():
                    a = 1
                    b = 2
                    return a + b
            """)
            node, path = source_scan.find_function_node(
                root / "scripts" / "facade.py", "moved", pkg_name="pkg")
            self.assertEqual(path.name, "mod.py", "应取实现体而不是薄壳")
            # 实现体有 3 条语句（薄壳只有 1 条 return），据此可区分
            self.assertEqual(len(node.body), 3)

    def test_missing_node_raises(self):
        with tempfile.TemporaryDirectory() as td:
            facade = self._tree(td)
            with self.assertRaises(LookupError):
                source_scan.find_function_node(facade, "does_not_exist")

    def test_duplicate_identical_bodies_raise(self):
        """两份**完全相同**的实现 = 搬家留下的拷贝（危险），必须抛而不是任选一份。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dup = "def copied():\n    return 42\n"
            _write(root, "scripts/facade.py", dup)
            _write(root, "scripts/pkg/mod.py", dup)
            with self.assertRaises(LookupError):
                source_scan.find_function_node(root / "scripts" / "facade.py", "copied", pkg_name="pkg")


class CountNameReferencesTest(unittest.TestCase):
    """`count_name_references` 走 AST，**注释与 docstring 天然不计入**。

    这是它相对 `text.count("name(")` 的全部意义：真实项目里，解释某条锚点的文档
    会把该标识符又写上几遍。实测 `order_margin_gate` 在领域**文本**里出现 7 次，
    而代码里只有 1 定义 + 2 调用。用文本数字当断言，等于把"文档写得多细"变成了
    测试条件。本文件把这个差异钉住。
    """

    def _mktree(self, td, facade_body, pkg_body=None):
        root = Path(td)
        _write(root, "scripts/facade.py", facade_body)
        if pkg_body is not None:
            _write(root, "scripts/pkg/mod.py", pkg_body)
        return root / "scripts" / "facade.py"

    def test_comments_and_docstrings_are_not_counted(self):
        with tempfile.TemporaryDirectory() as td:
            facade = self._mktree(td, '''
                # 注释里提到 gate( 不应被计入
                """docstring 里也提到 gate( 同样不计。"""
                def gate(x):
                    return x

                def use():
                    return gate(1)
            ''')
            counts = source_scan.count_name_references(facade, "gate")
            self.assertEqual(counts, {"defs": 1, "refs": 1},
                             "注释/docstring 里的提及不应计入 defs/refs")

    def test_text_count_would_be_inflated(self):
        """同一个文件：文本计数 > AST 计数 —— 证明为什么必须走 AST。"""
        with tempfile.TemporaryDirectory() as td:
            facade = self._mktree(td, '''
                """解释这条锚点：gate( 出现 3 次、gate( 是定义。"""
                # 这里又提一次 gate(
                def gate(x):
                    return x
                y = gate(2)
            ''')
            text = source_scan.combined(facade)
            counts = source_scan.count_name_references(facade, "gate")
            self.assertGreater(text.count("gate("), counts["refs"] + counts["defs"],
                               "文本计数应被文档抬高，否则这个测试没有意义")

    def test_defs_count_shell_and_implementation_separately(self):
        """门面薄壳 + 子包实现 → defs == 2（这是**有意**的，代表"一份壳一份实现"）。"""
        with tempfile.TemporaryDirectory() as td:
            facade = self._mktree(
                td,
                "def gate(x):\n    return _impl(x)\n",
                "def gate(x):\n    return x * 2\n")
            counts = source_scan.count_name_references(facade, "gate", pkg_name="pkg")
            self.assertEqual(counts["defs"], 2)
            self.assertEqual(counts["refs"], 0)

    def test_refs_counts_every_call_site_across_domain(self):
        with tempfile.TemporaryDirectory() as td:
            facade = self._mktree(
                td,
                "def gate(x):\n    return x\n\n\ndef a():\n    return gate(1)\n",
                "def b():\n    return gate(2)\n")
            counts = source_scan.count_name_references(facade, "gate", pkg_name="pkg")
            self.assertEqual(counts["refs"], 2, "子包里的调用点也必须计入")


class DomainTreesAndCombinedTest(unittest.TestCase):
    def test_domain_trees_returns_one_tree_per_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "scripts/facade.py", "def a():\n    return 1\n")
            _write(root, "scripts/pkg/mod.py", "def b():\n    return 2\n")
            trees = source_scan.domain_trees(root / "scripts" / "facade.py", pkg_name="pkg")
            self.assertEqual(len(trees), 2)

    def test_combined_joins_domain_text(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write(root, "scripts/facade.py", "FACADE_MARKER = 1\n")
            _write(root, "scripts/pkg/mod.py", "PKG_MARKER = 2\n")
            text = source_scan.combined(root / "scripts" / "facade.py", pkg_name="pkg")
            self.assertIn("FACADE_MARKER", text)
            self.assertIn("PKG_MARKER", text, "子包必须被纳入，否则域定位等于没做")


if __name__ == "__main__":
    unittest.main()
