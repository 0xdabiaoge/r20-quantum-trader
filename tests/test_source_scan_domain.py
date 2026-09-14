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
