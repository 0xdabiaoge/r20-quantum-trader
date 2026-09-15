r"""Binance 签名串构建抽取对拍门（第一百一十五刀）。

`r20_backend/exchanges/binance.py::BinanceAdapter.signed_request`（48 行）里 7 行 →
`r20_backend/exchanges/binance_signing.py::build_signed_query`（2 入参 / 1 输出）。

## 本门钉的是**签名规则**（安全相关）

1. 毫秒 `timestamp` 与 `recvWindow=5000` 由该函数补齐；
2. **空值与 `None` 剔除**，但 `0`／`False` **必须保留** —— 判据是 `v not in (None, "")`，
   不是 `if v`。这是最容易被"顺手简化"而改坏的一处：一旦改成 `if v`，
   数量为 0 的平仓单参数会被**静默丢掉**，请求含义就变了；
3. 签名 = `HMAC-SHA256(secret, query_string)` 十六进制 —— 门用**独立重算**验证（属性例），
   而不是比对硬编码串；
4. 最终串形如 `...&signature=<hex>`，且整串**顺序敏感**（签名覆盖的就是它）。

HTTP 传送（`Request`/`urlopen`）仍留在门面 ⇒ `patch.object(binance,"urlopen")` 等既有接缝不变；
鉴权头 `X-MBX-APIKEY` 也仍在门面。

基线：`a40f342`（本刀动工前最后提交）。
"""
from __future__ import annotations

import ast
import builtins
import hashlib
import hmac
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PRE = "a40f342"
FACADE = ROOT / "r20_backend" / "exchanges" / "binance.py"
MOD = ROOT / "r20_backend" / "exchanges" / "binance_signing.py"


def _baseline_method() -> ast.FunctionDef:
    r = subprocess.run(["git", "show", f"{PRE}:r20_backend/exchanges/binance.py"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, f"基线取不到：{r.stderr[:200]}"
    cls = next(n for n in ast.parse(r.stdout).body
               if isinstance(n, ast.ClassDef) and n.name == "BinanceAdapter")
    return next(n for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == "signed_request")


def _impl() -> ast.FunctionDef:
    t = ast.parse(MOD.read_text(encoding="utf-8"))
    return next(n for n in t.body
                if isinstance(n, ast.FunctionDef) and n.name == "build_signed_query")


class BinanceSigningExtractionTest(unittest.TestCase):
    def test_segment_is_ast_identical_to_baseline(self):
        seg = _baseline_method().body[2:9]
        body = list(_impl().body)[:-1]          # 去掉尾部 return
        body = body[1:] if (body and isinstance(body[0], ast.Expr)
                            and isinstance(body[0].value, ast.Constant)
                            and isinstance(body[0].value.value, str)) else body
        self.assertEqual(
            ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False),
            ast.dump(ast.Module(body=list(seg), type_ignores=[]), include_attributes=False),
            "build_signed_query 段体与抽取前**不再同一棵 AST**")

    def test_call_site_passes_every_parameter_once_same_name(self):
        params = [a.arg for a in _impl().args.kwonlyargs]
        tree = ast.parse(FACADE.read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BinanceAdapter")
        fn = next(n for n in cls.body
                  if isinstance(n, ast.FunctionDef) and n.name == "signed_request")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "build_signed_query"]
        self.assertEqual(len(calls), 1)
        self.assertEqual([k.arg for k in calls[0].keywords], params)
        for k in calls[0].keywords:
            self.assertEqual(ast.unparse(k.value), k.arg)
        # 传送层接缝仍在门面
        self.assertIn("urlopen", {n.func.id for n in ast.walk(fn)
                                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)})

    def test_module_imports_stdlib_itself(self):
        src = MOD.read_text(encoding="utf-8")
        for name in ("import hashlib", "import hmac", "import time", "from urllib.parse import urlencode"):
            self.assertIn(name, src, f"标准库名应由子模块自己 import：{name}")

    def test_no_undeclared_free_names(self):
        mod = ast.parse(MOD.read_text(encoding="utf-8"))
        mod_names = set()
        for n in mod.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                mod_names.add(n.name)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                mod_names |= {a.asname or a.name.split(".")[0] for a in n.names}
        fn = _impl()
        local = {a.arg for a in fn.args.kwonlyargs}
        for n in ast.walk(fn):
            if isinstance(n, ast.comprehension):
                tg = n.target
                for e in (tg.elts if isinstance(tg, (ast.Tuple, ast.List)) else [tg]):
                    if isinstance(e, ast.Name):
                        local.add(e.id)
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                local.add(n.id)
        reads = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        self.assertEqual(sorted(reads - local - set(dir(builtins)) - mod_names), [])

    # ---------- 行为例 ----------

    def _build(self, params, secret="sk-test"):
        from r20_backend.exchanges.binance_signing import build_signed_query
        return build_signed_query(params=params, secret=secret)

    def test_contains_timestamp_and_recv_window(self):
        q = self._build({"symbol": "BTCUSDT"})
        parts = dict(p.split("=", 1) for p in q.split("&") if "=" in p)
        self.assertEqual(parts["recvWindow"], "5000")
        self.assertEqual(parts["symbol"], "BTCUSDT")
        self.assertTrue(parts["timestamp"].isdigit() and len(parts["timestamp"]) == 13,
                        f"毫秒时间戳应为 13 位数字，实际 {parts.get('timestamp')!r}")

    def test_signature_is_hmac_sha256_of_query_string(self):
        secret = "sk-test"
        q = self._build({"side": "BUY", "quantity": "1.234"}, secret=secret)
        query_string, signature = q.rsplit("&signature=", 1)
        expected = hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"),
                            hashlib.sha256).hexdigest()
        self.assertEqual(signature, expected, "签名必须覆盖**除 signature 外**的整串")

    def test_empty_and_none_dropped_but_zero_and_false_kept(self):
        """`v not in (None, "")` 的真值语义 —— 0/False 必须保留。"""
        q = self._build({"a": None, "b": "", "c": 0, "d": False, "e": "x"})
        parts = dict(p.split("=", 1) for p in q.rsplit("&signature=", 1)[0].split("&") if "=" in p)
        self.assertNotIn("a", parts, "None 必须剔除")
        self.assertNotIn("b", parts, "空串必须剔除")
        self.assertEqual(parts["c"], "0", "0 不是空值，必须保留（否则平仓数量会被丢掉）")
        self.assertEqual(parts["d"], "False", "False 不是空值，必须保留")
        self.assertEqual(parts["e"], "x")

    def test_none_params_is_ok(self):
        q = self._build(None)
        self.assertIn("recvWindow=5000", q)
        self.assertIn("signature=", q)

    def test_values_are_url_encoded(self):
        q = self._build({"note": "a b&c"})
        head = q.rsplit("&signature=", 1)[0]
        self.assertIn("note=a+b%26c", head, "urlencode 语义：空格成 +、& 转义")

    def test_input_dict_is_not_mutated(self):
        params = {"symbol": "BTCUSDT"}
        self._build(params)
        self.assertEqual(params, {"symbol": "BTCUSDT"}, "不得改动调用方传入的 dict")

    def test_judgment_actually_notices_a_change(self):
        seg = _baseline_method().body[2:9]
        self.assertNotEqual(
            ast.dump(ast.Module(body=list(seg) + [ast.Pass()], type_ignores=[]), include_attributes=False),
            ast.dump(ast.Module(body=list(seg), type_ignores=[]), include_attributes=False))


if __name__ == "__main__":
    unittest.main()
