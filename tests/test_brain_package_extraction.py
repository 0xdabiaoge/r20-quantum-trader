"""B3（主脑侧第一块）`scripts/brain/packages.py` 的抽取回归。

## 这个测试在守什么

`fetch_single_instrument_package` 从 `scripts/ai_brain_trader.py`（原 L303-556，
254 行）整段搬进 `scripts/brain/packages.py`。**搬走前该函数零测试覆盖**，
而它是主脑每 15 分钟对每个标的跑一次的行情/指标装配 —— 它悄悄坏掉的表现是
"主脑拿到一包空数据继续决策"，而不是抛错。

因此这里守三件事：

1. **搬运无损**：子模块里的函数体与搬走前的门面文本**逐行相同**（只允许签名
   与 docstring 变）。字节级对拍，杜绝"搬的时候手抖漏了一行"。
2. **门面确实在转发**：门面同名壳必须真的调用子模块，且把两个行情函数
   **按调用期注入**传下去 —— 若改回 import 期绑定，`patch.object(门面, …)` 会失效。
3. **失败仍然是 fail-soft**：行情取不到时必须返回结构完整的包（`data_quality`
   降级），绝不能抛 —— 这是原函数的语义，搬运不得改变。
"""
from __future__ import annotations

import ast
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

import scripts.ai_brain_trader as abt
from scripts.brain import packages as brain_packages

ROOT = Path(__file__).resolve().parents[1]
FACADE = ROOT / "scripts" / "ai_brain_trader.py"
SUBMODULE = ROOT / "scripts" / "brain" / "packages.py"

# 搬走前门面里该函数的原文（提取时留档），用于逐行对拍。
PRE_MOVE_SOURCE = Path(__file__).resolve().parent / "data" / "brain_package_pre_move.py"


def _submodule_function_lines() -> list[str]:
    src = SUBMODULE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "fetch_single_instrument_package")
    return src.splitlines()[fn.lineno - 1:fn.end_lineno]


class MoveIsLosslessTest(unittest.TestCase):
    def test_body_is_line_identical_to_pre_move_source(self):
        original = PRE_MOVE_SOURCE.read_text(encoding="utf-8").splitlines()
        moved = _submodule_function_lines()
        # 允许的差异只有两处：签名展开（1 行 → 3 行）与新增 docstring（1 行）
        original_body = [ln for ln in original if not ln.startswith("def fetch_single_instrument_package")]
        moved_body = moved[4:]
        self.assertEqual(len(original_body), len(moved_body),
                         "函数体行数变了 —— 搬运过程中漏行或多行")
        for i, (a, b) in enumerate(zip(original_body, moved_body)):
            self.assertEqual(a, b, f"函数体第 {i + 1} 行不一致（搬运被改动）")

    def test_submodule_takes_the_two_market_functions_as_parameters(self):
        fn = next(n for n in ast.parse(SUBMODULE.read_text(encoding="utf-8")).body
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "fetch_single_instrument_package")
        kwonly = [a.arg for a in fn.args.kwonlyargs]
        self.assertEqual(kwonly, ["fetch_candles", "fetch_single_indicator"],
                         "两个行情函数必须走调用期注入")
        # 反向哨：子模块不得在 import 期绑定它们
        self.assertNotIn("from market_data_service import", SUBMODULE.read_text(encoding="utf-8"))


class FacadeDelegationTest(unittest.TestCase):
    def test_facade_imports_and_forwards(self):
        src = FACADE.read_text(encoding="utf-8")
        self.assertIn("from scripts.brain.packages import fetch_single_instrument_package as _fetch_single_instrument_package", src)
        self.assertIn("fetch_candles=fetch_candles,", src)
        self.assertIn("fetch_single_indicator=fetch_single_indicator,", src)

    def test_facade_shell_actually_calls_submodule(self):
        """打桩子模块，确认门面壳真的走它（而不是偷偷留了旧实现）。"""
        sentinel = {"instId": "X", "name": "X"}
        with patch.object(abt, "_fetch_single_instrument_package",
                          lambda item, **kw: {"delegated": item, **kw}) as _:
            got = abt.fetch_single_instrument_package(sentinel)
        self.assertEqual(got["delegated"], sentinel)
        self.assertIs(got["fetch_candles"], abt.fetch_candles)
        self.assertIs(got["fetch_single_indicator"], abt.fetch_single_indicator)


class FailSoftContractTest(unittest.TestCase):
    ITEM = {"instId": "FAKE-USDT-SWAP", "name": "FAKE", "type": "crypto", "precision": 4}

    def _call(self, candles):
        # 断网：ticker 走 urllib；确保测试零网络
        with patch.object(urllib.request, "urlopen", side_effect=OSError("offline")):
            return brain_packages.fetch_single_instrument_package(
                self.ITEM,
                fetch_candles=lambda *a, **k: candles,
                fetch_single_indicator=lambda *a, **k: {"adx": 0.0},
            )

    def test_all_data_missing_still_returns_intact_package(self):
        pkg = self._call([])
        for key in ("instId", "name", "type", "precision", "price", "chg24h", "bidPx",
                    "askPx", "fundingRate", "oiUsd", "vol24h", "lsRatio", "takerNetUsd",
                    "atr", "rsi", "vwap_bias", "macd_hist", "macd_accel", "vol_ratio",
                    "obv_flow", "adx_1h", "smart_money", "recent_15m", "recent_1h",
                    "recent_4h", "calculus", "data_quality"):
            self.assertIn(key, pkg, f"失败路径缺字段 {key}")
        self.assertEqual(pkg["instId"], "FAKE-USDT-SWAP")
        self.assertEqual(pkg["price"], 0.0)
        self.assertEqual(pkg["data_quality"], "invalid")
        self.assertFalse(pkg["calculus"]["valid"])

    def test_smart_money_is_explicitly_unavailable_not_fabricated(self):
        pkg = self._call([])
        self.assertFalse(pkg["smart_money"]["available"])
        self.assertIn("OKX CLI", pkg["smart_money"]["reason"])

    def test_never_raises_on_garbage_candles(self):
        for garbage in ([None], [[1, 2]], ["x"], [[{}]], [{"o": "a"}], [[]]):
            with self.subTest(garbage=garbage):
                self._call(garbage)  # 不得抛

    def test_fetch_candles_is_called_per_timeframe(self):
        seen = []
        with patch.object(urllib.request, "urlopen", side_effect=OSError("offline")):
            brain_packages.fetch_single_instrument_package(
                self.ITEM,
                fetch_candles=lambda inst, bar=None, limit=None: seen.append(bar) or [],
                fetch_single_indicator=lambda *a, **k: {},
            )
        self.assertEqual(sorted(set(seen)), ["15m", "1H", "4H"],
                         "三个周期都必须取数")


if __name__ == "__main__":
    unittest.main()
