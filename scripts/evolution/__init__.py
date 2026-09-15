"""自进化领域的可复用实现（结构优化阶段 4·B3 第四十二刀起）。

门面仍是单文件 `scripts/self_improvement_engine.py`
（`run_self_evolution` / `call_llm_evolution_review` / `compose_evolution_prompts` /
`EVOLUTION_SYSTEM_PROMPT` / 记忆合并 / 文件与锁等）。
本子包承接从那个文件里抽出的**成块领域逻辑**。

## 模块清单

| 模块 | 职责 | 注入面 |
|---|---|---|
| `observability.py` | 数理快照**可观测性**审计：字段表 / 门槛 / 逐单分类 / 剔除 null / 汇总 / 渲染摘要 | 无（纯计算；仅依赖 `r20_backend.time_utils.parse_beijing`） |

## 约定

1. **门面必须继续提供被搬走的名字**（`from scripts.evolution.observability import …`
   在门面里**再导出**）。外部（`r20_backend/routers/strategy/prompts.py`、
   `scripts/prompt_library.py`）与既有测试都按门面解析这些名字。
2. **`SNAPSHOT_MAX_STALE_SECONDS` / `SIDE_ALIASES` 留在门面** ——
   它们属于 **join 侧**（`_match_snapshot` 的 6 小时窗口与多空别名），
   与"可观测性判定"是两件事，**勿**顺手一起搬。
3. `DYNAMICS_OBSERVED_MIN` 必须**由字段表推导**，不得写死
   （`17 × 0.85 → 14 + 1 = 15`）。
"""
