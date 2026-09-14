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
| `xvenue.py` | 跨所矩阵采集 / 场所健康度落盘 / 分歧标注与提示词证据行（231 行） | 门面 L446-676 |

## 注入面速查（改这两块前先看）

| 模块 | 需要在调用期注入的门面名 | 原因 |
|---|---|---|
| `packages.py` | `fetch_candles` / `fetch_single_indicator` | 门面重载后 import 期绑定会失配；且测试可能 patch 门面名 |
| `xvenue.py` | `get_adapter`（门面 `_get_xvenue_adapter`）/ `safe_float` / `atomic_write_json` / `venue_health_file` / `health`（门面 `_XV_HEALTH`） | 前四个都是既有测试缝；`_XV_HEALTH` 被 `tests/test_xvenue_prompt.py:120` 直接断言，状态必须留在门面 |

**`xvenue.py` 是本子包里注入面最宽的一块** —— 它的每个依赖都对应一条既有测试缝。
改动它时请先看 `tests/test_brain_xvenue_extraction.py`：那里的 `InjectionContractTest`
就是为"搬走时把测试缝一起搬没了"这种情况写的。
"""
