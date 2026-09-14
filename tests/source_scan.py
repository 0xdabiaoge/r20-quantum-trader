"""源码文本锚点的定位工具（结构优化阶段 2 引入）。

## 为什么需要它

本仓有一批"读源码文本做断言"的审计测试（`read_text` + `assertIn` / `count`）。
它们钉的其实是**语义**：「某段强制逻辑确实存在于运行时源码里」——例如
「两种共识模式都必须给 CIO 预留预算」「比例切分必须带 90s 地板」。

但这类测试常把语义钉死在**某一个文件**上。一旦阶段 2 的模块拆分把这段逻辑
搬到同包的其他文件（如 `council_manager.py` → `council/debate.py`），测试就会
失败 —— 而**搬家本身并不是回归**。此时正确的处理是：

  · 断言**强度不变**（同样的 needle、同样的计数下限）；
  · **定位方式升级**：从"某个文件"改成"该领域的运行时源码集合"。

这样代码再搬家也不会误报，而且覆盖面比原来更广（原来只看一个文件）。

## 防空的必要性

"在更大范围里搜"会带来一个新风险：如果路径算错、读到空内容，
`assertIn` 会失败（好事，响亮），但 `assertNotIn` 与 `count(...) == 0` 会**假通过**。
因此调用方必须同时断言"确实读到了目标领域"，例如断言合并文本里含某个必然存在的
符号、且长度超过下限。本模块提供 `assert_area_looks_real` 供直接调用。
"""
from __future__ import annotations

from pathlib import Path


def source_area(module_file: str | Path, *, pkg_name: str | None = None) -> dict[Path, str]:
    """返回「该模块文件 + 同目录下的同名包目录」的全部 .py 源码。

    例：`source_area(r20_backend/council_manager.py)`
        → {council_manager.py, council/__init__.py, council/debate.py, council/policy.py}
        `source_area("scripts/ai_factor_trader.py", pkg_name="trader")`
        → {ai_factor_trader.py, trader/__init__.py, trader/signals.py, trader/factors.py, …}

    约定：包目录名默认 = 模块文件名去掉 `_manager` 后缀与 `.py` 后缀
    （`council_manager.py` → `council/`）。当门面与子包**不同名**时（如
    `ai_factor_trader.py` 的抽取子包叫 `trader/`），用 `pkg_name` 显式指定 ——
    这样后续再往该子包搬文件时，断言面**自动覆盖**，不用回来改测试。
    找不到包目录时只返回模块文件本身，由调用方的防空断言决定是否可接受。
    """
    module = Path(module_file)
    if not module.is_absolute():
        module = Path(__file__).resolve().parents[1] / module
    sources = {module: module.read_text(encoding="utf-8")}
    stem = module.stem
    if pkg_name is None:
        pkg_name = stem[:-len("_manager")] if stem.endswith("_manager") else stem
    pkg_dir = module.parent / pkg_name
    if pkg_dir.is_dir():
        for extra in sorted(pkg_dir.glob("*.py")):
            sources[extra] = extra.read_text(encoding="utf-8")
    return sources


def combined(*module_files: str | Path, pkg_name: str | None = None) -> str:
    """把若干领域源码拼成一段文本，供 assertIn / assertNotIn / str.count 使用。

    `pkg_name` 会透传给每一个 `source_area()`（见其文档：门面与子包不同名时用）。
    """
    parts: list[str] = []
    for module_file in module_files:
        parts.extend(source_area(module_file, pkg_name=pkg_name).values())
    return "\n".join(parts)


def assert_area_looks_real(testcase, text: str, *, must_contain: str,
                           min_chars: int = 20000) -> None:
    """防空：确认合并文本确实是目标领域，避免 assertNotIn / count==0 假通过。"""
    testcase.assertIn(must_contain, text, f"未读到目标领域源码（缺少 {must_contain}）")
    testcase.assertGreater(len(text), min_chars, "目标领域源码过短，疑似定位错误")


def domain_trees(module_file: str | Path, *, pkg_name: str | None = None) -> list:
    """把「门面 + 同名字包」逐个 `ast.parse`，返回 AST 列表（按路径排序，门面在前）。

    与 `combined()` 的关系：那个拼**文本**（给 assertIn / count 用），这个保留
    **每文件独立的 AST**（给"按名字取函数节点再 exec"这类用法用）。

    为什么需要它：仓里有 3 处测试用 `ast.parse(单文件)` 再按函数名取节点
    （`test_prompt_rendering_isolated`、`test_self_evolution_safety`、
    `test_dashboard_payload_seam` 的同类写法）。一旦目标函数搬进子包，
    `next(...)` 会 `StopIteration`。改成扫整个领域后，**函数搬到哪都找得到**。
    """
    import ast
    return [ast.parse(text) for text in source_area(module_file, pkg_name=pkg_name).values()]


def find_function_node(module_file: str | Path, name: str, *, pkg_name: str | None = None,
                       node_only: bool = False):
    """在「门面 + 同名字包」全领域里按名字找顶层函数节点。

    找不到直接抛错。返回 `(node, 该节点所在文件路径)`，便于报错时指明位置。

    ## 关于「同名两份」

    本仓的抽取手法是**门面保留同名薄壳**（`return _xxx_impl(...)`）+ 子包放实现，
    所以领域内同名函数**合理地出现两次**。此时：

    - 默认（`node_only=False`）：返回**实现体**那一份 —— 即二者中源码更长的那个。
      这是"要执行的真实逻辑"，也正是这类测试想要的。
    - 域内同名多份且**源码完全相同**：判为搬家留下的拷贝（危险），抛错。
    """
    import ast
    hits: list[tuple] = []
    for path, text in source_area(module_file, pkg_name=pkg_name).items():
        for node in ast.parse(text).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                hits.append((node, path, ast.get_source_segment(text, node) or ""))
    if not hits:
        raise LookupError(f"领域内找不到顶层函数 {name!r}（{module_file}）")
    if len(hits) == 1:
        return hits[0][0], hits[0][1]

    bodies = [body for _, _, body in hits]
    if len(set(bodies)) < len(bodies):
        raise LookupError(
            f"领域内 {name!r} 有 {len(bodies)} 份**完全相同**的实现，疑似搬家留下的拷贝："
            + ", ".join(str(p) for _, p, _ in hits))
    # 门面壳 vs 子包实现：取实现体（源码更长者）
    node, path, _ = max(hits, key=lambda h: len(h[2]))
    return node, path
