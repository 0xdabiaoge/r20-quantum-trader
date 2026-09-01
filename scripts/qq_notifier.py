#!/usr/bin/env python3
"""Generic R20 notification dispatcher.

Set R20_NOTIFICATION_WEBHOOK to a trusted endpoint that accepts JSON POST payloads.
The trading engine remains fully functional when notifications are not configured.
"""

import datetime
import json
import os
import urllib.request

NOTIFICATION_WEBHOOK = os.getenv("R20_NOTIFICATION_WEBHOOK", "")


def send_qq_message(text: str) -> bool:
    """Backward-compatible name; delivery is now an optional generic webhook."""
    if not NOTIFICATION_WEBHOOK:
        print("[R20 Notification] No webhook configured; notification retained in process log")
        return False

    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_str = datetime.datetime.now(tz_bj).strftime("%H:%M:%S")
    payload = json.dumps({
        "source": "R20 Quantum Trader",
        "timestamp": now_str,
        "message": text.strip(),
    }).encode("utf-8")
    request = urllib.request.Request(
        NOTIFICATION_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "R20-Standalone/5.4.2"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        print(f"[R20 Notification] Delivery failed: {exc}")
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
