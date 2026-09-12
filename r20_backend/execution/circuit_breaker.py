"""Circuit breaker engine: Black swan sentinel, daily loss limits, and stop cooldowns."""
from __future__ import annotations
import datetime
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from scripts.risk_constants import STOP_COOLDOWN_MINUTES
from r20_backend.time_utils import beijing_day
from r20_backend.execution.sizing import effective_daily_loss_limit

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
NEWS_SENTIMENT_FILE = DATA_DIR / "news_sentiment.json"
CIRCUIT_BREAKER_FILE = DATA_DIR / "circuit_breaker.json"
LEDGER_JSON_FILE = DATA_DIR / "trading_ledger.json"
STOP_COOLDOWN_FILE = DATA_DIR / "stop_cooldowns.json"


def load_stop_cooldowns() -> Dict[str, Any]:
    if STOP_COOLDOWN_FILE.exists():
        try:
            with open(STOP_COOLDOWN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def add_stop_cooldown(inst_id: str, side: str, reason: str = "止损冷却") -> None:
    cooldowns = load_stop_cooldowns()
    key = f"{inst_id}_{side}"
    cooldowns[key] = {
        "instId": inst_id,
        "side": side,
        "ts": int(time.time()),
        "reason": reason,
    }
    try:
        with open(STOP_COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(cooldowns, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def is_in_stop_cooldown(inst_id: str, side: str) -> bool:
    cooldowns = load_stop_cooldowns()
    key = f"{inst_id}_{side}"
    if key in cooldowns:
        rem_sec = STOP_COOLDOWN_MINUTES * 60 - (int(time.time()) - cooldowns[key].get("ts", 0))
        if rem_sec > 0:
            return True
    return False


def check_black_swan_sentinel(fetch_candles_fn=None) -> Tuple[bool, str]:
    """Minute-level Black Swan Sentinel: fail-closed against extreme plunges and severe news."""
    if fetch_candles_fn is None:
        from scripts.market_data_service import fetch_candles
        fetch_candles_fn = fetch_candles

    try:
        candles = fetch_candles_fn("BTC-USDT-SWAP", bar="15m", limit=3)
    except Exception as exc:
        return True, f"🚨 黑天鹅熔断：统一行情通道异常 ({type(exc).__name__})，不可判定=不放松，保守暂停新开仓"
    if not candles or len(candles) < 2:
        return True, "🚨 黑天鹅熔断：统一行情通道无有效数据（双域+备源皆断），不可判定=不放松，保守暂停新开仓"
    try:
        latest_c = candles[0]
        c_open = float(latest_c[1])
        c_close = float(latest_c[4])
        c_low = float(latest_c[3])
        drop_pct = (c_close - c_open) / c_open * 100.0
        if drop_pct <= -3.0 or ((c_low - c_open) / c_open * 100.0 <= -4.0):
            return True, f"🚨 监测到 BTC 15M 级别发生断崖式暴跌插针 ({drop_pct:.2f}%)，触发全网黑天鹅紧急熔断！"
    except (ValueError, TypeError, IndexError):
        return True, "🚨 黑天鹅熔断：行情数据格式异常不可判定，不可判定=不放松，保守暂停新开仓"

    if NEWS_SENTIMENT_FILE.exists():
        try:
            with open(NEWS_SENTIMENT_FILE, "r", encoding="utf-8") as f:
                n_data = json.load(f)
            raw_score = n_data.get("overall_score")
            if raw_score is not None:
                score = float(raw_score)
                if score <= 20.0:
                    return True, f"🚨 监测到突发黑天鹅极度恶性利空舆情 (情绪指数: {score:.1f})，触发全网黑天鹅紧急熔断！"
        except Exception:
            return True, "🚨 黑天鹅熔断：新闻情绪缓存损坏不可判定，不可判定=不放松，保守暂停新开仓"

    return False, ""


def is_circuit_breaker_active(usdt_available: Optional[float] = None, fetch_candles_fn=None) -> Tuple[bool, str]:
    """Unified circuit breaker check combining black swan sentinel, state file, and daily loss."""
    bs_active, bs_reason = check_black_swan_sentinel(fetch_candles_fn=fetch_candles_fn)
    if bs_active:
        return True, bs_reason

    if CIRCUIT_BREAKER_FILE.exists():
        try:
            with open(CIRCUIT_BREAKER_FILE, "r", encoding="utf-8") as f:
                cb = json.load(f)
            expires_at = float(cb.get("expires_at_ts", 0) or 0)
            active = bool(cb.get("active")) or cb.get("status") == "triggered"
            if active and (expires_at <= 0 or time.time() < expires_at):
                return True, cb.get("reason") or cb.get("headline") or "黑天鹅极端行情熔断中"
        except Exception as e:
            return True, f"熔断状态文件损坏，安全暂停开仓: {e}"

    if LEDGER_JSON_FILE.exists():
        try:
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            tz_bj = datetime.timezone(datetime.timedelta(hours=8))
            today_str = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d")
            today_pnl = sum(
                float(t.get("pnl", 0) or 0)
                for t in ledger
                if t.get("status") == "closed" and beijing_day(t.get("close_time")) == today_str
            )
            _loss_cap = effective_daily_loss_limit(usdt_available)
            if today_pnl < -_loss_cap:
                return True, f"今日累计回撤 ({today_pnl:.2f}U) 触及单日最大风控熔断限额 ({_loss_cap}U｜按可用余额自适应)"
        except Exception as e:
            return True, f"日亏损风控数据读取失败，安全暂停开仓: {e}"

    return False, ""
