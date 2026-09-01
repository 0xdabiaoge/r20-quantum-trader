"""Backward-compatible import bridge for the R20 multi-channel notifier."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r20_backend.notifications import notify, send_qq_message


def notify_trade_open(inst: str, side: str, sz: int, px: float, strategy: str, reason: str):
    return send_qq_message(f"🟢 【开仓信号触发】\n• 标的：{inst}-USDT-SWAP\n• 方向：{side}（{sz} 张）\n• 策略：{strategy}\n• 入场：{px}\n• 逻辑：{reason}")


def notify_trade_close(inst: str, pnl: float, stage: str, exit_px: float):
    sign = "+" if pnl >= 0 else ""
    return send_qq_message(f"🎯 【平仓结清通知】\n• 标的：{inst}-USDT-SWAP\n• 动作：{stage}\n• 平仓：{exit_px}\n• 净盈亏：{sign}{pnl:.4f} USDT")


def notify_circuit_breaker(macro_event: str, reason: str):
    return send_qq_message(f"🚨 【黑天鹅避险熔断】\n• 事件：{macro_event}\n• 原因：{reason}")


def notify_daily_summary(summary_text: str):
    return send_qq_message(f"📊 【每日 AI 量化晨/晚报】\n{summary_text}")
