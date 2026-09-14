r"""生产 `data/` 文件在跑测试时**不被写**（结构优化阶段 4·B3 第七十三～七十五刀）。

## 这个测试在防什么（第七十二刀实测到的真事故）

第七十二刀给离线套件做基线标定时，用**对照实验**证实：
跑测试套件会覆盖生产 `data/` 里的交易状态文件。对照窗口 02:18:02 → 02:20:01
内**无任何 trader 周期**（周期在 :00/:15/:30/:45，日志亦无记录）：

| 文件 | 运行前 | 运行后 |
|---|---|---|
| `data/llm_models.json` | `bc8b1cf2…` | 未变 |
| `data/trading_state.json` | `e44a6e6c…` | **变了**（mtime 02:18:14） |
| `data/trading_ledger.json` | `e8ebb421…` | **变了**（mtime 02:19:29） |

**根因**（`scripts/instrument_pool.py`）：写入函数
`sync_instruments_state()` 里是**函数局部**拼接 ——

```python
state_file = ROOT / "data" / "trading_state.json"   # 局部变量
```

`tests/config_sandbox.isolate_config` 的重定向只对**模块级 UPPERCASE 常量**生效
（它遍历 `vars(module)`，看不见函数局部名；`ROOT` 指向仓库根，也不满足
"值在 `project/data` 之下"），于是这条路径**永远逃过沙箱**。
与第四十八刀那次事故（池文件被写成缺字段、实盘周期 fail-safe）**同一机制**。

## ⚠️ 为什么判据是"行为"而不是"静态形状"（第七十五刀的教训）

第七十三刀我先写了静态判据（正则/AST 找 `ROOT / "data"` 内联拼接），结果**连错两次**：

1. **过宽**：把 17 个**模块级** `X = ROOT / "data" / …` 报成违规 ——
   它们其实能被沙箱重定向（是大写常量且值在 `data/` 下）；
2. **判据方向错**：改判"函数内拼接=违规"并把 6 处改成模块级 `DATA_DIR` 后，
   **反而弄坏 5 个既有测试** —— `dashboard` / `strategy` / `backup_runtime` /
   `agents` / `worker` 的测试用
   `patch.object(module, "ROOT", tmp)` 隔离，函数内调用期拼 `ROOT / "data"`
   **正是它们能隔离的原因**；提成 import 期定值的 `DATA_DIR` 后 patch 失效。

⇒ **两种隔离机制（isolate_config 重定向常量 / 测试手工 patch ROOT）互相矛盾，
任何"静态形状"判据都表达不了"这条路径会不会写生产"。**
只有**行为断言**可靠：真调那个写入函数（在沙箱下），断言生产文件哈希不变。

这正是 §88.5 建议的修法（"断言跑 `sync_instruments_state()` 后生产文件 sha256 不变"）。
"""

from __future__ import annotations

import ast
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: 事故里被写过的四个生产文件（instrument_pool.sync_instruments_state 的写集）
GUARDED_FILES = (
    "data/trading_state.json",
    "data/factor_library_snapshot.json",
    "data/news_sentiment.json",
    "data/dashboard_last_good.json",
)


def _hash_or_absent(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        return "<absent>"
    return hashlib.sha256(p.read_bytes()).hexdigest()


class SyncInstrumentsStateNeverWritesProductionTest(unittest.TestCase):
    """⚠️ 核心回归：真调 `sync_instruments_state()`（沙箱下），
    断言生产 `data/` 四个文件哈希**分毫不动**。

    这是行为判据 —— 若有人把 `instrument_pool` 的模块级常量
    改回函数局部拼接，沙箱重定向失效，生产哈希会变，本用例当场翻红。
    """

    def test_production_files_untouched(self):
        from tests import config_sandbox
        import scripts.instrument_pool as pool

        before = {rel: _hash_or_absent(rel) for rel in GUARDED_FILES}

        sandbox = config_sandbox.isolate_config(self)   # addCleanup 自动还原

        # 先确认沙箱确实接管了这几个常量（否则"没写到生产"只是因为根本没跑到写）
        for name in ("TRADING_STATE_FILE", "FACTOR_LIBRARY_FILE",
                     "NEWS_SENTIMENT_FILE", "DASHBOARD_CACHE_FILE"):
            value = str(getattr(pool, name, ""))
            self.assertTrue(
                value.startswith(str(sandbox)),
                f"{name} 未被重定向（实际 {value}）—— 沙箱已失效，本测试失去意义")

        # ⚠️ 屏蔽第 5 步的后台子进程（`_run_bg` → `_run_captured` 会 spawn
        # `factor_library.py` / `news_sentiment_harvester.py` 两个**独立进程**，
        # 它们各自从真实 ROOT 重新拼路径 → 那是**另一类**预先存在的子进程泄漏，
        # 不由"模块常量重定向"机制管，也不在本刀的修复范围内）。
        # 本测试钉的是**本进程内**第 1-4 步的模块常量写入 —— 即 §88 事故的机制。
        p = patch.object(pool, "_run_captured", lambda *a, **k: None)
        p.start(); self.addCleanup(p.stop)

        # 真跑一遍写入函数（它读沙箱池、写沙箱文件）
        pool.sync_instruments_state()

        after = {rel: _hash_or_absent(rel) for rel in GUARDED_FILES}
        changed = [rel for rel in GUARDED_FILES if before[rel] != after[rel]]
        self.assertEqual(
            changed, [],
            "跑 sync_instruments_state() 覆盖了生产 data/ 文件：" + ", ".join(changed)
            + " —— 第七十二刀实测事故复发。修法：把这些路径保持为"
              "**模块级常量**（isolate_config 才能重定向），"
              "见 scripts/instrument_pool.py 的 DATA_DIR 注释。")

    def test_all_four_paths_are_module_level_constants(self):
        """结构前提：四个写集路径必须是**模块级**常量。

        （函数局部名 `vars(module)` 看不见，沙箱就无法重定向。）
        """
        src = (ROOT / "scripts" / "instrument_pool.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        top_level = set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        top_level.add(t.id)
        for name in ("DATA_DIR", "POOL_FILE", "TRADING_STATE_FILE",
                     "FACTOR_LIBRARY_FILE", "NEWS_SENTIMENT_FILE",
                     "DASHBOARD_CACHE_FILE"):
            with self.subTest(const=name):
                self.assertIn(name, top_level,
                              f"{name} 必须是**模块级**常量，否则沙箱看不到它")

    def test_old_local_names_do_not_resurrect(self):
        """第四十八/七十二刀的两个旧局部名不得复活。

        只在**代码**里查（`_strip` 掉注释与 docstring）——
        本模块与 instrument_pool 的文档里正解释着这些旧名字，
        不排除会把"解释问题的文字"当成"问题本身"（假红，§82.3 / §80.3 反复踩的坑）。
        """
        src = (ROOT / "scripts" / "instrument_pool.py").read_text(encoding="utf-8")
        code = _strip_docstrings_and_comments(src)
        for gone in ("state_file", "factor_file", "news_file", "dashboard_cache"):
            with self.subTest(gone=gone):
                self.assertNotIn(
                    gone, code,
                    f"{gone} 曾是函数内局部变量（沙箱拦不住），不应复活")

    def test_isolate_config_redirects_module_level_data_paths(self):
        """⚠️ 顺带守护机制本身：isolate_config 会重定向**已导入**模块里
        值在 `project/data` 之下的大写常量。

        这是 instrument_pool 修复生效的**前提**；若 config_sandbox 被改成
        不再遍历 `scripts.` 前缀，本用例先红，避免"修复悄悄失效"。
        """
        from tests import config_sandbox
        import scripts.instrument_pool  # 确保已进 sys.modules

        sandbox = config_sandbox.isolate_config(self)
        module = sys.modules["scripts.instrument_pool"]
        redirected = [k for k, v in vars(module).items()
                      if k.isupper() and isinstance(v, (str, Path))
                      and str(v).startswith(str(sandbox))]
        self.assertIn("TRADING_STATE_FILE", redirected,
                      "isolate_config 不再重定向 instrument_pool 的写集常量")


def _strip_docstrings_and_comments(src: str) -> str:
    """去掉 docstring 与 `#` 注释（保留换行以对齐行号）。

    用**字符扫描**而非正则剥离，避免把字符串字面量里的 `#` 误判成注释。
    """
    out, i, n = [], 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if src.startswith(('"""', "'''"), i):
            quote = src[i:i + 3]
            i += 3
            while i < n and not src.startswith(quote, i):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            i += 3
            out.append(" ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


if __name__ == "__main__":
    unittest.main()
