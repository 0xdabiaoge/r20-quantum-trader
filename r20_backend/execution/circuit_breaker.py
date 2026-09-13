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
# 审计 A2（数据诚实→fail-closed）：台账是逐所拼合的，任一所在同步周期内拉取
# 失败时其平仓亏损缺席，日亏求和天然偏小；此时「未触限」不可判定，按本模块
# 「不可判定=不放松」纪律暂停开仓（宁停不错，与状态文件损坏同策）。



def _sync_status_path():
    """调用时解析（测试 patch 模块 DATA_DIR 即封闭，律①）。"""
    return DATA_DIR / "ledger_sync_status.json"


def _ledger_sync_failed_venues(max_age_seconds: float = 2700.0) -> list[str]:
    """读台账同步旁车：返回最近一次同步 failed 的所列表。旁车缺失/过旧/损坏
    一律返回空（过旧场景由 ledger 文件 file_health 的 STALE 通道兜底）。"""
    try:
        path = _sync_status_path()
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        generated_at = str(payload.get("generated_at") or "")
        if generated_at:
            ts = datetime.datetime.fromisoformat(generated_at)
            age = (datetime.datetime.now(ts.tzinfo) - ts).total_seconds()
            if age > max_age_seconds:
                return []
        return [str(v) for v, d in (payload.get("venues") or {}).items()
                if isinstance(d, dict) and d.get("status") == "failed"]
    except Exception:
        return []
# 审计③(2026-09-13)：文件名分裂修复——旧值（复数 .json）与 trader 活文件
# stop_cooldown.json（单数）互不可见；若后端接平仓写复数而 trader 消费单数，冷却
# 静默失效。归一到既成事实文件名（两边 key/schema 本就同构）。
STOP_COOLDOWN_FILE = DATA_DIR / "stop_cooldown.json"


def ledger_daily_closed_pnl(ledger, environment_mode: str, today_str: str) -> float:
    """审计④1(2026-09-13) 单一事实源：当日已平仓盈亏求和必须带环境轴。
    台账行自带 environment 标签（sync_full_ledger 写入），demo↔live 切换当天若不
    过滤，两环境盈亏互相抵消/虚增可让熔断假阴性。规则：
    - 行环境与当前环境明确不同 → 剔除；
    - 行缺环境标签（历史旧行）或当前环境拿不到 → 保守计入（宁停不漏，与
      本模块「不可判定=不放松」纪律一致，绝不静默放宽）。"""
    want = str(environment_mode or "").strip().lower()
    total = 0.0
    for t in ledger:
        try:
            if t.get("status") != "closed":
                continue
            if beijing_day(t.get("close_time")) != today_str:
                continue
            row_env = str(t.get("environment") or "").strip().lower()
            if row_env and want and row_env != want:
                continue
            total += float(t.get("pnl", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def _read_stop_cooldowns_state() -> Tuple[Dict[str, Any], bool]:
    """(data, corrupt)。损坏≠缺失：corrupt 时 is_in_stop_cooldown fail-closed。"""
    if not STOP_COOLDOWN_FILE.exists():
        return {}, False
    try:
        with open(STOP_COOLDOWN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}, True
        return data, False
    except Exception:
        return {}, True


def load_stop_cooldowns() -> Dict[str, Any]:
    return _read_stop_cooldowns_state()[0]


def _atomic_write_json(path, payload) -> None:
    """审计③：与 trader._atomic_write_json / secrets 同路数（mkstemp+fsync+replace）。"""
    import tempfile
    d = str(Path(path).parent)
    fd, tmp = tempfile.mkstemp(prefix="." + Path(path).name + "-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def add_stop_cooldown(inst_id: str, side: str, reason: str = "止损冷却") -> None:
    cooldowns, corrupt = _read_stop_cooldowns_state()
    if corrupt:
        print(f"[止损冷却] CRITICAL 状态文件损坏，拒绝合并写回保全现场: {STOP_COOLDOWN_FILE}")
        return
    key = f"{inst_id}_{side}"
    cooldowns[key] = {
        "instId": inst_id,
        "side": side,
        "ts": int(time.time()),
        "reason": reason,
    }
    try:
        _atomic_write_json(STOP_COOLDOWN_FILE, cooldowns)
    except Exception as e:
        print(f"[止损冷却] warn 落盘失败: {e}")


def is_in_stop_cooldown(inst_id: str, side: str) -> bool:
    cooldowns, corrupt = _read_stop_cooldowns_state()
    if corrupt:
        return True  # 不可判定=不放松：损坏按仍在冷却处理
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
        _failed_venues = _ledger_sync_failed_venues()
        if _failed_venues:
            return True, ("台账跨所同步不完整（失败所: " + ",".join(_failed_venues) +
                          "），当日亏损求和不可判全，安全暂停开仓")
        try:
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            tz_bj = datetime.timezone(datetime.timedelta(hours=8))
            today_str = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d")
            try:
                from scripts.okx_runtime import current_environment
                _mode = str(current_environment().mode or "")
            except Exception:
                _mode = ""  # 环境不可判 → ledger_daily_closed_pnl 保守全计
            today_pnl = ledger_daily_closed_pnl(ledger, _mode, today_str)
            _loss_cap = effective_daily_loss_limit(usdt_available)
            if today_pnl < -_loss_cap:
                return True, f"今日累计回撤 ({today_pnl:.2f}U) 触及单日最大风控熔断限额 ({_loss_cap}U｜按可用余额自适应)"
        except Exception as e:
            return True, f"日亏损风控数据读取失败，安全暂停开仓: {e}"

    return False, ""
