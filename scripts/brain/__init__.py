"""主脑脚本的抽取子包（结构优化阶段 4·B3 起）。

`scripts/ai_brain_trader.py` 是主脑主脚本（worker 每 15 分钟 respawn），
沿用交易员侧（`scripts/trader/`）同一套**门面保留式抽取**手法：

- 门面保留同名薄壳与全部被测试钉住的字面量；
- 被测试 patch 的全局（路径、行情函数、可替换依赖）一律**调用期注入**，
  绝不在子模块 import 期烘焙 —— 原因见 `r20_backend/README.md` §5 与
  `tests/risk_test_env.py::pin_baseline_risk_env()` 的重载名单；
- 新增模块进本子包，不再往门面堆。

当前模块：

| 模块 | 内容 | 来源 |
|---|---|---|
| `packages.py` | `fetch_single_instrument_package` 单标的数据包装配（254 行） | 门面 L303-556 |
"""
