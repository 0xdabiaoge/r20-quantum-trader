#!/usr/bin/env python3
"""
QQ Channel Notification Dispatcher for R20 Trading System
Pushes real-time trading signals, TP/SL executions, circuit breakers & daily summaries to user via QQ.
"""

import subprocess
import json
import datetime
import os

AGENT_ID = os.getenv("QQ_AGENT_ID", "default")
CHANNEL = os.getenv("QQ_CHANNEL", "qq")
TARGET_USER = os.getenv("QQ_TARGET_USER", "YOUR_QQ_USER_ID")
TARGET_SESSION = os.getenv("QQ_TARGET_SESSION", "qq:YOUR_QQ_USER_ID")

def send_qq_message(text: str) -> bool:
    """Send text message to user's QQ channel via qwenpaw channels send"""
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_str = datetime.datetime.now(tz_bj).strftime("%H:%M:%S")
    formatted_msg = f"⚡【R20量化系统】{now_str}\n{text.strip()}"
    
    cmd = [
        "qwenpaw", "channels", "send",
        "--agent-id", AGENT_ID,
        "--channel", CHANNEL,
        "--target-user", TARGET_USER,
        "--target-session", TARGET_SESSION,
        "--text", formatted_msg
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return res.returncode == 0
    except Exception as e:
        print(f"Failed to send QQ notification: {e}")
        return False

def notify_trade_open(inst: str, side: str, sz: int, px: float, strategy: str, reason: str):
    emoji = "🟢" if "多" in side or "long" in side.lower() else "🔴"
    text = (
        f"{emoji} 【开仓信号触发】\n"
        f"• 标的：{inst}-USDT-SWAP\n"
        f"• 方向：{side}（{sz} 张）\n"
        f"• 触发策略：{strategy}\n"
        f"• 入场价格：{px}\n"
        f"• 逻辑：{reason}"
    )
    return send_qq_message(text)

def notify_trade_close(inst: str, pnl: float, stage: str, exit_px: float):
    emoji = "🎉" if pnl >= 0 else "🛡️"
    sign = "+" if pnl >= 0 else ""
    text = (
        f"{emoji} 【平仓结清通知】\n"
        f"• 标的：{inst}-USDT-SWAP\n"
        f"• 平仓动作：{stage}\n"
        f"• 平仓价格：{exit_px}\n"
        f"• 实结净盈亏：{sign}{pnl:.4f} USDT"
    )
    return send_qq_message(text)

def notify_circuit_breaker(macro_event: str, reason: str):
    text = (
        f"🚨 【黑天鹅避险熔断激活】\n"
        f"• 监测事件：{macro_event}\n"
        f"• 熔断原因：{reason}\n"
        f"• 动作：暂停 30 分钟新开仓，启动持仓保本回撤防御！"
    )
    return send_qq_message(text)

def notify_daily_summary(summary_text: str):
    text = f"📊 【每日 AI 量化晨/晚报】\n{summary_text}"
    return send_qq_message(text)

if __name__ == "__main__":
    send_qq_message("🚀 R20 交易系统 QQ 实时告警推送通道已成功对接并上线！")
