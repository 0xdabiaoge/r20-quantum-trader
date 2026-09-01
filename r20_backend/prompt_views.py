"""Read-only base and rendered prompt views for the admin prompt library."""
from __future__ import annotations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

EVOLUTION_USER_TEMPLATE = """======================= 【当前认知复盘基准时间】 =======================
【复盘基准时间】: {{timestamp_beijing}}

======================= 【当前系统已有的历史长期记忆库】 =======================
{{existing_memory_markdown}}

======================= 【R20 加密量化实盘战绩与历史交易台账】 =======================
【统计汇总】:
- 总平仓笔数: {{total}} 笔（胜 {{wins}} / 负 {{losses}} | 胜率 {{win_rate}}%）
- 累计净盈亏: {{total_net}} USDT | 累计手续费: {{total_fees}} USDT
- 当前聚焦标的池: {{target_instruments}}

【逐笔历史交易明细】:
{{closed_trades_json}}

【复盘与长期记忆进化任务】:
对照历史记忆审查失效经验，重点分析微积分动能衰竭、假突破、顺势加仓与止损冷却，输出 diagnosis_insights、evolution_actions、ai_long_term_memory、memory_overwrites_reason 的严格 JSON。
"""

TRADING_USER_TEMPLATE = """动态用户提示词由 scripts/ai_brain_trader.py::construct_full_market_prompt 在每轮 Python 进程中直接渲染，包含：
1. 北京时间与可用资金；
2. 宏观新闻与情绪；
3. 当前持仓、在途挂单与长期记忆；
4. 全标的多周期 K 线、盘口、聪明钱、微积分、定积分、概率与 VaR；
5. 持仓管理、挂单管理、开仓/加仓裁决任务；
6. 完整 JSON 输出 Schema。

最近一次实际渲染版本显示在“最近实盘用户提示词”区域，风格模板作为附加层由 Python 直接拼接后发送。
"""


def _split_snapshot(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"system": "", "user": "", "updated": ""}
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "【USER PROMPT"
    index = text.find(marker)
    system = text[:index].strip() if index >= 0 else ""
    user = text[index:].strip() if index >= 0 else text.strip()
    return {"system": system, "user": user, "updated": str(int(path.stat().st_mtime))}


def rendered_snapshots() -> dict[str, Any]:
    return {
        "trading": _split_snapshot(DATA / "ai_brain_last_prompt.txt"),
        "evolution": _split_snapshot(DATA / "self_improvement_last_prompt.txt"),
    }
