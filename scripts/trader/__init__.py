"""交易员脚本的抽取子包（结构优化阶段 4·B3）。

`scripts/ai_factor_trader.py` 是实盘主脚本（由 worker 每 15 分钟 respawn），
按研究文档 B3 采用**门面保留式抽取**：只把不依赖模块状态的纯逻辑搬进来，
门面保留同名壳与全部被测试钉住的字面量。

## 模块清单

| 模块 | 内容 | 注入面 |
|---|---|---|
| `factors.py` | `fetch_single_instrument_data` 单标的行情/指标装配 | 宽（多函数） |
| `signals.py` | `evaluate_asset_signal` / `clamp` 多因子评分 | `asset_class_profiles` / `is_in_stop_cooldown` / `load_adaptive_config` |
| `protection.py` | 止损信号、棘轮移损、AI 收紧判定、平仓载荷/手续费 | `safe_float` 等，全部调用期注入 |
| `gates.py` | `order_margin_gate` / `equity_margin_cap` / `is_tradfi_market_liquid` | `MAX_SINGLE_ASSET_MARGIN` / `MAX_MARGIN_EQUITY_RATIO` |
| `position_mgmt.py` | `execute_ai_position_management` 主脑持仓指令执行器（95 行） | 文件路径 / `ai_tightens_stop` / `close_position_confirmed` / `okx_rest` / 多所三项，全部调用期 |
| `brackets.py` | `normalize_bracket_prices` 限价单三价顺序钳制（长/空各一份内联合并为一处） | 无（纯函数，数值全部入参） |
| `pyramiding.py` | `pyramiding_gate` 顺势浮盈加仓五条门禁（长/空各一份内联合并为一处） | 4 个风控常量 + 全部中间量，均调用期 |
| `order_intent.py` | `resolve_entry_prices` 三价定价 + `build_order_intent` 下单载荷装配（长/空各一份内联合并为一处） | 全部入参；保证金闸门/权益顶刻意留在门面（计数锚点载体） |
| `notifications.py` | `entry_action_message` / `entry_failure_message` / `trade_open_kwargs` 方向文案与通知参数（12 个方向常量收成单一来源） | 全部入参；`leverage` 与全部状态变更刻意留在门面 |
| `cycle_snapshot.py` | `collect_pending_inst_ids` 外所挂单枚举与去重计数 + `build_state_payload` 面板状态快照 | venue_registry/load_instruments/信号求值函数，均调用期 |
| `leverage.py` | `clamp_ai_leverage` AI 杠杆夹取（配置区间 → 池内单标的上限，顺序是关键） | MIN/MAX_LEVERAGE + 池值，均调用期 |
| `sizing.py` | `size_for_decision` 按 AI 决策推导下单张数（四道钳制：0.5x 下限 / 2.0x 上限 / 余额硬顶只砍不放 / 步长量化） | quantize_size + max_size_within_margin 由门面注入 |

## 两条铁律

1. **子模块不得在 import 期绑定门面名字**。`pin_baseline_risk_env()` 的原地重载
   名单里**没有**任何子模块，import 期绑定会变成过期快照；`patch.object(门面, 名字)`
   这类测试缝也会被静默关掉。一律**调用期注入**。
2. **门面壳必须是 `def name(...)`，不能是 `name = impl` 别名**。计数锚点
   （如 `ai_factor_trader.py` 里 `order_margin_gate(` 恰 3 次）与
   `inspect.getsource(trader.xxx)` 都依赖"门面里有一个真正的 def"。

## 本包是实盘进程的 import 根之一 —— 改完必须做语法校验

`scripts/ai_factor_trader.py` 第 41 行起就 `from scripts.trader.xxx import ...`。
本包任何文件只要有 **SyntaxError**，交易员整个周期会在 import 阶段直接死掉：
`logs/ai_factor_trader.log` **不会**新增任何行（含 traceback），表现为"周期静默消失"。
2026-09-14 10:00 那次事故就是这么来的（往本文件尾部追加文档时漏了 docstring 闭合）。
所以：**改本包任何文件后，务必 `python -c "import scripts.trader"` 或至少
`ast.parse(...)` 验证一次**，不要只看测试是否绿。
"""
