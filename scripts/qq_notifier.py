"""Backward-compatible bridge that publishes durable R20 Gateway events."""
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r20_gateway.publisher import publish


def _publish(event_type: str, title: str, message: str, payload: dict | None = None, priority: int = 50) -> bool:
    try:
        publish(event_type, title, message, payload=payload, priority=priority)
        return True
    except Exception:
        return False


def send_qq_message(text: str) -> bool:
    """Compatibility symbol: true means durably queued, not synchronously delivered."""
    return _publish("notification.generic", "系统通知", text, priority=50)


def notify_trade_open(inst: str, side: str, sz: int, px: float, strategy: str, reason: str) -> bool:
    message = f"• 标的：{inst}-USDT-SWAP\n• 方向：{side}（{sz} 张）\n• 策略：{strategy}\n• 入场：{px}\n• 逻辑：{reason}"
    return _publish("trade.opened", "🟢 【开仓信号触发】", message, {"instrument": inst, "side": side, "size": sz, "price": px, "strategy": strategy}, 90)


def notify_trade_close(inst: str, pnl: float, stage: str, exit_px: float) -> bool:
    sign = "+" if pnl >= 0 else ""
    message = f"• 标的：{inst}-USDT-SWAP\n• 动作：{stage}\n• 平仓：{exit_px}\n• 净盈亏：{sign}{pnl:.4f} USDT"
    return _publish("trade.closed", "🎯 【平仓结清通知】", message, {"instrument": inst, "pnl": pnl, "stage": stage, "exit_price": exit_px}, 95)


def notify_circuit_breaker(macro_event: str, reason: str) -> bool:
    return _publish("risk.triggered", "🚨 【黑天鹅避险熔断】", f"• 事件：{macro_event}\n• 原因：{reason}", {"event": macro_event, "reason": reason}, 100)


def notify_daily_summary(summary_text: str) -> bool:
    return _publish("briefing.ready", "📊 【每日 AI 量化晨/晚报】", summary_text, priority=40)
