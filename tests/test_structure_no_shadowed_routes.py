"""路由遮蔽（shadowed route）回归闸：钉住"改哪份才有效"。

背景（结构优化阶段 1，commit 68254e9）：
本项目有两套路由层 —— r20_backend/routers/*（模块化）与 dashboard/app.py（legacy 整包）。
r20_backend/app.py 是「先 include_router(...) 再 mount("/", dashboard_app)」，
Starlette 按注册顺序匹配，因此凡两边同路径同方法者一律 routers 生效，
dashboard/app.py 的同名 handler **函数体永不执行** —— 改它没有任何效果、也不报错。

阶段 1 已拆除 15 条这类影子注册。本测试把它固化为自动闸，防止今后再次踩进
"改了没效果"的坑（这类缺陷最贵的地方不是报错，而是静默无效）。

判定不做肉眼推断：用 AST 解析两条路由表（含 include 顺序与
`from r20_backend.routers import (a_router, ...)` 括号多名称导入形态），
再用 Starlette 官方 compile_path 复现真实路径匹配。

**方法必须参与判定**：同路径不同方法（GET 与 POST 的 /api/v1/admin/risk 等）
不是影子，两条都真实可达 —— 本测试初版漏了方法，把二十多条同路径不同方法的
路由误判成遮蔽，是一类典型假阳性。

纯静态、无网络、不导入应用（避免导入 dashboard.app 触发其 2s 后台线程真调 OKX）。
"""
from __future__ import annotations
import ast
import re
import unittest
from pathlib import Path

from starlette.routing import compile_path

ROOT = Path(__file__).resolve().parents[1]
APP_MAIN = ROOT / "r20_backend" / "app.py"
DASH_APP = ROOT / "dashboard" / "app.py"
ROUTER_DIR = ROOT / "r20_backend" / "routers"

# dashboard/app.py 里「仅此处定义、真实生效」的路由。删掉任何一条都会造成线上 404，
# 故显式钉住（阶段 1 已逐条实测：/favicon.svg、/、/doc 返回 200，
# /login 返回 307 → /admin/login）。
DASHBOARD_ONLY_LIVE = {
    "/favicon.svg",
    "/",
    "/doc",
    "/login",
}

_METHOD_ATTRS = {"get", "post", "put", "delete", "patch", "api_route"}

Route = tuple[int, frozenset[str], str]


def _routes(path: Path, owner: str) -> list[Route]:
    """提取 @<owner>.<method>(...) 的 (行号, 方法集, path)，保持源码顺序。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[Route] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
                continue
            kind = dec.func.attr
            if kind not in _METHOD_ATTRS:
                continue
            if not (isinstance(dec.func.value, ast.Name) and dec.func.value.id == owner):
                continue
            if not (dec.args and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)):
                continue
            methods: set[str] | None = None if kind == "api_route" else {kind.upper()}
            for kw in dec.keywords:
                if kw.arg == "methods" and isinstance(kw.value, ast.List):
                    methods = {e.value for e in kw.value.elts if isinstance(e, ast.Constant)}
            if methods is None:
                methods = {"GET"}
            if "GET" in methods:  # FastAPI 的 @get 会自动附加 HEAD
                methods = set(methods) | {"HEAD"}
            found.append((node.lineno, frozenset(methods), dec.args[0].value))
    return found


def _router_include_order() -> list[str]:
    """按注册顺序返回 routers 子模块名（与 r20_backend/app.py 的 include 顺序一致）。"""
    src = APP_MAIN.read_text(encoding="utf-8")
    tree = ast.parse(src)

    order = [m.group(1) for m in re.finditer(r"app\.include_router\((\w+)\)", src)]
    # 防空：解析一旦失败，本测试会静默退化成"没有影子"——那是最危险的假阴性
    if len(order) < 5:
        raise AssertionError(f"include_router 仅解析到 {len(order)} 条，解析逻辑可疑，拒绝给结论")

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "r20_backend.routers":
            imported += [alias.name for alias in node.names]
    if not imported:
        raise AssertionError("未解析到 r20_backend.routers 的导入清单，解析逻辑可疑")

    mods: list[str] = []
    for name in order:
        if name not in imported:
            raise AssertionError(f"include_router({name}) 未出现在 routers 导入清单中")
        mod = name[:-7] if name.endswith("_router") else name  # 'auth_router' → 'auth'
        f = ROUTER_DIR / f"{mod}.py"
        if not f.exists():
            raise AssertionError(f"router→文件 约定映射失败：{name} → {f}")
        if mod not in mods:
            mods.append(mod)
    return mods


def _front_routes() -> list[tuple[str, frozenset[str], str, object]]:
    """先注册、因而生效的那一套：[("<源位置>", 方法集, pattern, 编译后的正则), ...]。"""
    out: list[tuple[str, frozenset[str], str, object]] = []
    for mod in _router_include_order():
        for line, methods, pattern in _routes(ROUTER_DIR / f"{mod}.py", "router"):
            out.append((f"routers/{mod}.py:{line}", methods, pattern, compile_path(pattern)[0]))
    if not out:
        raise AssertionError("前台路由表为空 —— 解析逻辑可疑，拒绝给结论")
    return out


def _shadow_hits(back: list[Route], front) -> list[str]:
    """返回被 front（更早注册）遮蔽的 back 路由描述。"""
    hits: list[str] = []
    for line, methods, pattern in back:
        for src, f_methods, f_pattern, f_regex in front:
            if (methods & f_methods) and f_regex.match(pattern):
                hits.append(f"  {pattern} [{','.join(sorted(methods))}] ← {src} 的 {f_pattern}")
                break
    return hits


class NoShadowedRouteTests(unittest.TestCase):
    def test_front_route_table_is_parsed(self):
        """防空自检：解析失败必须响亮失败，而不是静默判定'无影子'。"""
        front = _front_routes()
        self.assertGreater(len(front), 50, f"前台路由仅 {len(front)} 条，疑似解析失败")
        dash = _routes(DASH_APP, "app")
        self.assertGreaterEqual(len(dash), 4, f"dashboard/app.py 路由仅 {len(dash)} 条")

    def test_dashboard_app_has_no_shadowed_route(self):
        hits = _shadow_hits(_routes(DASH_APP, "app"), _front_routes())
        self.assertEqual(
            hits,
            [],
            "dashboard/app.py 出现被遮蔽的路由（改了不会有任何效果、也不报错）：\n"
            + "\n".join(hits)
            + "\n两条出路：① 删掉本文件里的重复注册，让 routers 独占该路径；\n"
              "② 若该 handler 本就必须在本文件提供（如 routers 反向委托它），"
              "则不要给它注册装饰器。",
        )

    def test_dashboard_only_live_routes_are_kept(self):
        """这 4 条只在 dashboard/app.py 定义，是真实生效路由，不能被误删。"""
        paths = {pattern for _, _, pattern in _routes(DASH_APP, "app")}
        missing = sorted(DASHBOARD_ONLY_LIVE - paths)
        self.assertEqual(
            missing, [],
            f"dashboard/app.py 缺少这些仅此处生效的真实路由（会线上 404）: {missing}",
        )

    def test_no_dashboard_route_is_also_defined_in_routers(self):
        """更强的表述：两边不应再出现任何同路径同方法的路由对。

        阶段 1 之后这条恒成立；若将来有人在两边都注册了同一路径，
        即使他"知道" routers 会赢，也会重新制造认知陷阱。
        """
        dash_paths = {(methods, pattern) for _, methods, pattern in _routes(DASH_APP, "app")}
        clash: list[str] = []
        for src, methods, pattern, _ in _front_routes():
            for d_methods, d_pattern in dash_paths:
                if pattern == d_pattern and (methods & d_methods):
                    clash.append(f"  {pattern} [{','.join(sorted(methods & d_methods))}] 同时在 {src} 与 dashboard/app.py")
        self.assertEqual(clash, [], "同一路径同方法被两套路由层重复注册:\n" + "\n".join(clash))

    def test_router_layer_has_no_internal_shadow(self):
        """routers 内部同层也不该有遮蔽。

        这一条曾报出 24 条命中，经查**全是假阳性** —— 初版没把 HTTP 方法纳入判定，
        于是把「同路径不同方法」（GET 与 POST 的 /api/v1/admin/risk 等）误判成遮蔽。
        补上方法后真遮蔽为 0：145 条 router 路由全部真实可达。
        保留此断言，正是为了锁住这个前提。
        """
        seen: list[tuple[str, frozenset[str], str, object]] = []
        hits: list[str] = []
        for mod in _router_include_order():
            for line, methods, pattern in _routes(ROUTER_DIR / f"{mod}.py", "router"):
                src = f"routers/{mod}.py:{line}"
                for p_src, p_methods, p_pattern, p_regex in seen:
                    if (methods & p_methods) and p_regex.match(pattern):
                        hits.append(
                            f"  {src} {pattern} [{','.join(sorted(methods))}]"
                            f" ← {p_src} 的 {p_pattern}"
                        )
                        break
                seen.append((src, methods, pattern, compile_path(pattern)[0]))
        self.assertGreater(len(seen), 50, f"router 路由仅 {len(seen)} 条，疑似解析失败")
        self.assertEqual(hits, [], "router 之间出现真实遮蔽（后注册者不可达）:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
