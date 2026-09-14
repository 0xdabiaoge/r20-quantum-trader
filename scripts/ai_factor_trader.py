#!/usr/bin/env python3
"""
R20 High-Alpha Quantitative Multi-Factor Trading Matrix & Execution Engine (R20 Quantum Trader v6.8.1)
Architecture:
1. Multi-Dimensional Quant Factor Sub-Engine:
   - Trend Momentum: EMA Slope (9/21/55), Multi-Timeframe Alignment (15M, 1H, 4H)
   - Volume & Price Dynamics: MACD Histogram Acceleration, OBV Flow Divergence, Volume Expansion Ratio
   - Mean Reversion & Volatility: Multi-Scale VWAP Bias, RSI 14/7 Dynamic Zones, Bollinger Bandwidth & Squeeze
   - Market Microstructure: Dynamic High/Low Dow Theory, Wick Absorption Geometry, Volatility Quantile (ATR%)
2. Continuous Non-Linear Alpha Scoring (-5.0 to +5.0 Score Distribution):
   - Dynamic weight synthesis across Momentum, Volume, Volatility, and Macro Sentiment
3. 6 Institutional Quant Setups:
   - 🌊 Institutional Pullback (顺势机构回踩)
   - 🚀 Momentum Squeeze Breakout (动量挤压突破)
   - 💎 Extreme Mean Reversion (极值均值回归)
   - ⚡ Resistance Exhaustion Short (阻力抛压做空)
   - 🌪️ Breakdown Acceleration Short (破位放量追空)
   - 🛡️ Liquidity Sweep Reversal (流动性猎杀反转)
4. Dynamic Adaptive Position Sizing, Volatility-Trailing Exits & Cooldown Protection.
"""

import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

try:
    from r20_backend.version import __version__
except Exception:
    __version__ = "7.6.0"

from r20_backend.time_utils import beijing_day

# 结构优化阶段4·B3：纯信号逻辑已搬入 scripts/trader/signals.py，re-export 保持门面表面不变
from scripts.trader.signals import clamp, evaluate_asset_signal as _evaluate_asset_signal  # noqa: F401
from scripts.trader.reservation_reconcile import (
    utc_age_seconds as _rr_utc_age_seconds,
    reconcile_reservation_ledger as _rr_reconcile,
)
from scripts.trader.position_mgmt import (
    execute_ai_position_management as _execute_ai_position_management_impl,
)
from scripts.trader.leverage import clamp_ai_leverage
from scripts.trader.sizing import size_for_decision
from scripts.trader.venue_evidence import (
    build_venue_candidates as _venue_evidence_candidates,
    persist_venue_decision as _venue_evidence_persist,
)
from scripts.trader.order_submit import (
    submit_protected_limit_order as _order_submit_protected,
)
from scripts.trader.routing_policy import (
    estimate_margin_usdt as _routing_policy_estimate_margin,
    load_preferred_venue as _routing_policy_load_pref,
    load_routing_mode as _routing_policy_load_mode,
    portfolio_budget_guard as _routing_policy_budget_guard,
    portfolio_risk_budget_usdt as _routing_policy_risk_budget,
    route_and_reserve_signal as _routing_policy_route,
    _decision_payload as _routing_policy_decision_payload,
    _rejection_focus_reason as _routing_policy_rejection_reason,
)
from scripts.trader.venue_query import (
    close_position_confirmed as _venue_query_close_confirmed,
    fetch_other_venue_positions as _venue_query_other_positions,
    query_positions as _venue_query_positions,
    venue_execution_ready as _venue_query_exec_ready,
    _venue_health_stamp as _venue_query_health_stamp,
)
from scripts.trader.cloud_protection import (
    amend_venue_stop_loss as _cloud_protection_amend,
    ensure_cloud_position_protection as _cloud_protection_ensure,
    sync_cloud_algo_stop as _cloud_protection_sync_stop,
    _live_oco_coverage as _cloud_protection_coverage,
)
from scripts.trader.order_lifecycle import (
    clean_stale_open_orders as _order_lifecycle_clean,
    reconcile_pending_orders as _order_lifecycle_reconcile,
)
from scripts.trader.ledger_writer import (
    record_open_intent as _ledger_writer_intent,
    record_trade as _ledger_writer_trade,
)
from scripts.trader.signal_snapshot import (
    build_signal_snapshot as _signal_snapshot_build,
)
from scripts.trader.circuit_guard import (
    check_black_swan_sentinel as _circuit_guard_sentinel,
    is_circuit_breaker_active as _circuit_guard_breaker,
)
from scripts.trader.cycle_snapshot import (
    build_state_payload,
    collect_pending_inst_ids,
)
from scripts.trader.notifications import (
    entry_action_message,
    entry_failure_message,
    trade_open_kwargs,
)
from scripts.trader.order_intent import (
    build_order_intent,
    resolve_entry_prices,
)
from scripts.trader.pyramiding import (
    pyramiding_gate,
)
from scripts.trader.brackets import (
    normalize_bracket_prices,
)
from scripts.trader.gates import (
    order_margin_gate as _order_margin_gate_impl,
    equity_margin_cap as _equity_margin_cap_impl,
    is_tradfi_market_liquid as _is_tradfi_market_liquid_impl,
)
from scripts.trader.factors import fetch_single_instrument_data as _fetch_single_instrument_data
from scripts.trader.position_universe import (
    collect_okx_position_payloads as _collect_okx_position_payloads,
    merge_cross_venue_positions as _merge_cross_venue_positions,
)
from scripts.trader.protection import (
    protection_signals,
    ratcheted_trailing_stop,
    ai_tightens_stop,
    close_fee as _close_fee,
    close_trade_payload as _close_trade_payload,
)

# US-003 决策面接线：选所路由（US-002）与预算原子预留（US-001）以模块绑定名引用，
# 接线级测试 patch 模块属性即可完全离线（零出网/零凭证/零真实预留库）。
from r20_backend import risk_reservation
from r20_backend import venue_router
from r20_backend.exchanges import canonical_base
from r20_backend.exchanges import registry as venue_registry
from r20_backend.exchanges import routing_policy

# 必须用 scripts.okx_runtime 包形式：okx_rest 读的是同一模块实例的冻结环境，
# 裸 okx_runtime 是另一份 _FROZEN_ENVIRONMENT 全局，freeze 周期对其无效（US-002 命门）。
from scripts.okx_runtime import (
    current_environment,
    freeze_environment as freeze_okx_environment,
    unfreeze_environment as unfreeze_okx_environment,
    selected_environment,
)
import json
import math
import tempfile
import time
import datetime
import subprocess
import urllib.request
import fcntl
from typing import Tuple, Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
from market_data_service import fetch_candles, fetch_ticker
import scripts.okx_rest as okx_rest

# 执行层风控参数单一事实源（后台「风控管理页」写入 .env，本进程 import 时读取生效）
from risk_constants import (
    MAX_CONCURRENT_POSITIONS_CAP,
    MAX_MARGIN_EQUITY_RATIO,
    MAX_SCALE_IN_COUNT,
    MAX_SINGLE_ASSET_MARGIN,
    MAX_LEVERAGE,
    MIN_LEVERAGE,
    MIN_ENTRY_CONFIDENCE,
    MIN_SCALE_IN_CONFIDENCE,
    MIN_SCALE_IN_PROFIT_RATIO,
    DAILY_LOSS_EQUITY_RATIO,
    MAX_DAILY_LOSS_USDT,
    RISK_PER_TRADE_EQUITY_RATIO,
    SINGLE_ASSET_EQUITY_RATIO,
    STOP_COOLDOWN_MINUTES,
    TIME_STOP_ATR_BAND,
    TIME_STOP_HOURS,
    effective_max_positions,
    effective_daily_loss_limit,
    effective_single_asset_margin,
)

WORKSPACE_DIR = str(_PROJECT_ROOT)
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
LOGS_DIR = os.path.join(WORKSPACE_DIR, "logs")

LEDGER_JSON_FILE = os.path.join(DATA_DIR, "trading_ledger.json")
# 批E(2026-09-13)：周期收尾的台账/DB spawn 总闸（模块导入时快照——测试用
# patch.dict(clear=True) 清空环境也抹不掉）。生产不设 R20_LEDGER_SYNC_DISABLED。
LEDGER_AUTOSYNC_ENABLED = str(os.environ.get("R20_LEDGER_SYNC_DISABLED", "")).strip().lower() not in ("1", "true", "yes")
LOG_FILE = os.path.join(LOGS_DIR, "ai_factor_trader.log")
POSITION_TRACKER_FILE = os.path.join(DATA_DIR, "position_trackers.json")
SIGNAL_JOURNAL_FILE = os.path.join(DATA_DIR, "signal_journal.json")
STOP_COOLDOWN_FILE = os.path.join(DATA_DIR, "stop_cooldown.json")
CIRCUIT_BREAKER_FILE = os.path.join(DATA_DIR, "circuit_breaker.json")
NEWS_SENTIMENT_FILE = os.path.join(DATA_DIR, "news_sentiment.json")
AI_POSITION_MANAGEMENT_FILE = os.path.join(DATA_DIR, "ai_position_management.json")
TRADER_LOCK_FILE = os.path.join(DATA_DIR, ".ai_factor_trader.lock")
TRADER_SLOT_FILE = os.path.join(DATA_DIR, ".ai_factor_trader_slot.json")

try:
    import sys
    sys.path.append(os.path.join(WORKSPACE_DIR, "scripts"))
    from db_manager import record_trade_sqlite
    from qq_notifier import notify_trade_open, notify_trade_close
    from ai_brain_trader import execute_batch_ai_brain_cycle, get_latest_ai_decision, read_cycle_health
except Exception:
    record_trade_sqlite = None
    notify_trade_open = None
    notify_trade_close = None
    execute_batch_ai_brain_cycle = None
    get_latest_ai_decision = None
    read_cycle_health = None

from instrument_pool import load_instruments, pool_is_trustworthy, pool_state

TARGET_INSTRUMENTS = load_instruments()

ASSET_CLASS_PROFILES = {
    "commodity": {
        "entry_threshold": 2.2,
        "min_profit_ratio": 0.0075,
        "tp_atr_mult": 2.2,
        "sl_atr_mult": 1.3,
        "trailing_kick_in": 1.1,
        "trailing_pullback": 0.45
    },
    "index": {
        "entry_threshold": 2.2,
        "min_profit_ratio": 0.0065,
        "tp_atr_mult": 2.0,
        "sl_atr_mult": 1.2,
        "trailing_kick_in": 1.0,
        "trailing_pullback": 0.40
    },
    "stock": {
        "entry_threshold": 2.2,
        "min_profit_ratio": 0.0090,
        "tp_atr_mult": 2.3,
        "sl_atr_mult": 1.3,
        "trailing_kick_in": 1.2,
        "trailing_pullback": 0.50
    },
    "crypto": {
        "entry_threshold": 2.2,
        "min_profit_ratio": 0.0250,
        "tp_atr_mult": 2.8,
        "sl_atr_mult": 1.4,
        "trailing_kick_in": 2.2,
        "trailing_pullback": 0.80
    }
}

# 并发/同向持仓上限：后台风控管理页可配 (R20_MAX_CONCURRENT_POSITIONS=0 表示自动跟随标的池容量)
MAX_CONCURRENT_POSITIONS, MAX_SAME_DIRECTION_POSITIONS = effective_max_positions(len(TARGET_INSTRUMENTS))
TAKER_FEE_RATE = 0.0005
MAKER_FEE_RATE = 0.0002 # Limit Order Maker Fee (60% Lower Than Market Taker)
# 单笔 1R 风险额 / 数量量化 / 可用余额硬顶：**不再本地孪生**（审计批6）。
# 曾与 r20_backend/execution/sizing.py 逐字重复两份，是「改一处漏一处」的漂移源。
from r20_backend.execution import (
    effective_risk_per_trade,
    max_size_within_margin,
    quantize_size,
)
from r20_backend.execution.cooldowns import (
    is_in_stop_cooldown as _cooldowns_is_in,
    load_stop_cooldowns as _cooldowns_load,
    read_stop_cooldowns_state as _cooldowns_read_state,
)

def order_margin_gate(planned_margin: float, *, size: float, price: float, ct_val: float,
                      leverage: float, usdt_available: float) -> float:
    """多所下单保证金闸门。实现与理由见 scripts/trader/gates.py。

    风控常量在**调用期**读取（`risk_constants` 的 .env 改参由门面重载刷新）。
    注意：本函数名在**本文件里**出现 3 次（1 定义 + 开多 + 开空），这是计数锚点
    `tests/test_audit_config_p0_hardening.py::test_both_call_sites_pass_gate_and_equity_cap`
    所依赖的。不要把本壳改成别名赋值；也不要在注释里写出带左括号的函数名
    —— 那会把自己也数进去，锚点会以"多了一次"的形式翻红（本轮就踩过这个坑）。
    """
    return _order_margin_gate_impl(
        planned_margin, size=size, price=price, ct_val=ct_val, leverage=leverage,
        usdt_available=usdt_available,
        max_single_asset_margin=MAX_SINGLE_ASSET_MARGIN,
        max_margin_equity_ratio=MAX_MARGIN_EQUITY_RATIO,
    )


def equity_margin_cap(usdt_available: float) -> float:
    """权益占比硬顶。实现见 scripts/trader/gates.py。"""
    return _equity_margin_cap_impl(usdt_available,
                                   max_margin_equity_ratio=MAX_MARGIN_EQUITY_RATIO)
# MIN_SCALE_IN_CONFIDENCE (顺势加仓最低 AI 置信度) 由 risk_constants 单一事实源注入

def is_tradfi_market_liquid(asset_type: str) -> bool:
    """美股常规交易时段判定。实现见 scripts/trader/gates.py。"""
    return _is_tradfi_market_liquid_impl(asset_type)

# 交易 shell 子进程三件套（结果/字符串/JSON 包装）已随 US-007 全量 REST 迁移删除
# （2026-09-10）：V5 直签唯一通道见 scripts/okx_rest.py；subprocess 仅保留本地
# python 脚本调度用途。禁止复活任何 shell=True 的交易所调用。

def fetch_candles_direct(inst_id: str, bar: str = "15m", limit: int = 45):
    """Direct fetch from OKX Official Market REST API with Keep-Alive connection pooling."""
    return fetch_candles(inst_id, bar=bar, limit=limit)

def load_trackers():
    if os.path.exists(POSITION_TRACKER_FILE):
        try:
            with open(POSITION_TRACKER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_trackers(trackers):
    try:
        with open(POSITION_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(trackers, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _atomic_write_json(path, payload):
    """审计③(2026-09-13)：常驻写者统一原子路数（mkstemp+fsync+os.replace，对齐
    sync_full_ledger / r20_gateway.secrets）。此前台账/状态/冷却直 open("w") 覆写，
    并发读者（熔断/日报/备份/面板）可读到半截 JSON：误停开仓、推「0胜0负」假研报、
    止损冷却静默解除。失败时旧文件原样保全（绝不撕裂）。"""
    _dir = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + "-", dir=_dir)
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


def _read_stop_cooldowns_state():
    """薄壳：转调单一事实源，并在**调用时**解析本模块的 `STOP_COOLDOWN_FILE`。

    结构优化阶段 4·B3 第五十刀：本函数与
    `r20_backend/execution/circuit_breaker.py` 的同名函数原为等价重复
    （差在 `os.path.exists` vs `Path.exists`）。已收敛到
    `r20_backend.execution.cooldowns.read_stop_cooldowns_state`。

    ⚠️ 文件路径**必须**在调用时从本模块全局解析：测试会
    `patch.object(aft, "STOP_COOLDOWN_FILE", f)`（见
    `tests/test_audit_batch3_persistence_atomic.py`），import 期烘焙会让补丁静默失效。

    审计③(2026-09-13)：返回 (data, corrupt)。损坏与缺失从此不同权——
    corrupt=True 时 is_in_stop_cooldown 按「在冷却」fail-closed（旧实现损坏→{}
    等价于「无冷却」，硬止损后可立即同向重进）；add 拒做 RMW 防覆盖现场。
    """
    return _cooldowns_read_state(STOP_COOLDOWN_FILE)


def load_stop_cooldowns():
    # 兼容旧契约（只读展示面）；风控判断路径一律走 _read_stop_cooldowns_state
    return _cooldowns_load(STOP_COOLDOWN_FILE)

def add_stop_cooldown(inst_id: str, side: str, reason: str = "止损冷却"):
    cooldowns, corrupt = _read_stop_cooldowns_state()
    if corrupt:
        print(f"[止损冷却] CRITICAL 状态文件损坏，拒绝合并写回以保全现场"
              f"（期间所有标的按『仍在冷却』fail-closed）: {STOP_COOLDOWN_FILE}")
        return
    key = f"{inst_id}_{side}"
    cooldowns[key] = {
        "instId": inst_id,
        "side": side,
        "ts": int(time.time()),
        "reason": reason
    }
    try:
        _atomic_write_json(STOP_COOLDOWN_FILE, cooldowns)
    except Exception as e:
        print(f"[止损冷却] warn 落盘失败（本笔冷却丢失，依赖云端SL兜底）: {e}")

def is_in_stop_cooldown(inst_id: str, side: str) -> bool:
    """薄壳：转调单一事实源（结构优化阶段 4·B3 第五十刀）。

    ⚠️ 冷却文件与冷却时长都在**调用时**从本模块全局解析 ——
    测试会 patch `STOP_COOLDOWN_FILE`，且 `risk_test_env.pin_baseline_risk_env()`
    会重载本模块（它在重载名单里），故按全局名查找是必须的。
    """
    return _cooldowns_is_in(inst_id, side, STOP_COOLDOWN_FILE,
                            STOP_COOLDOWN_MINUTES * 60)



def instrument_profile(inst: dict[str, Any], asset_type: str = "crypto") -> dict[str, Any]:
    """单标的参数解析（审计 P2-5）。

    旧实现：池文件里每条都写了 `max_leverage`/`sl_atr_mult`（TIER_PROFILES 派生），
    但代码只读硬编码 ASSET_CLASS_PROFILES —— 于是管理页/池文件里的参数是装饰品，
    而提示词又给出第三套口径（"止损基准 1.5~2.0x 1H ATR"）。现在单一优先级：
    池条目 per-instrument > 资产类别档 > 代码兜底，三处（提示词/下单/复算）同源。"""
    base = dict(ASSET_CLASS_PROFILES.get(asset_type, ASSET_CLASS_PROFILES["crypto"]))
    for key in ("sl_atr_mult", "tp_atr_mult", "trailing_kick_in", "trailing_pullback", "entry_threshold", "min_profit_ratio"):
        raw = (inst or {}).get(key)
        try:
            if raw is not None and str(raw).strip() != "":
                base[key] = float(raw)
        except (TypeError, ValueError):
            continue
    return base


def load_adaptive_config():
    """Fallback config reader maintaining compatibility."""
    return {}

def _run_captured(script, label=None, timeout=15):
    """审计(2026-09-13)：同解释器子进程 + 非零必吼（旧裸 python3 shell 串=静默死亡）。"""
    from r20_backend.spawn import run_script
    return run_script(script, timeout=timeout, label=label)


# 本进程内被回收枚举实证「凭证已死」的外所集合（审计 2026-09-13：坏键所自动摘除
# 执行资格，防最低费率赢下评分后死在下单阶段白烧信号）。trader 每轮新进程=每轮
# 重探，密钥修好后下一轮自动恢复，无需人工。
_BROKEN_VENUES: set = set()


def clean_stale_open_orders(keep_ord_ids: Optional[set] = None) -> Tuple[bool, str]:
    """壳（第八十四刀搬至 `scripts/trader/order_lifecycle.py`，调用期同名注入）。"""
    return _order_lifecycle_clean(
        keep_ord_ids,
        load_open_intents=load_open_intents,
        OPEN_INTENT_TTL_MS=OPEN_INTENT_TTL_MS,
        _BROKEN_VENUES=_BROKEN_VENUES,
        current_environment=current_environment,
        load_instruments=load_instruments,
        okx_rest=okx_rest,
        venue_registry=venue_registry)

# =============================================================================
# US-006 重启接管存量挂单——周期级挂单对账
# =============================================================================
OPEN_INTENT_FILE = os.path.join(DATA_DIR, "open_order_intents.json")
OPEN_INTENT_TTL_MS = 6 * 3600 * 1000  # 本地开仓意图有效期；超期 → 周期意图已失效

RECONCILE_REASON_ORPHAN = "无对应意图"
RECONCILE_REASON_SIDE_MISMATCH = "方向不一致"
RECONCILE_REASON_INTENT_STALE = "周期意图已失效"


def record_open_intent(inst_id: str, side: str, ts_ms: int = None) -> None:
    """壳（第八十三刀搬至 `scripts/trader/ledger_writer.py`，调用期同名注入）。"""
    return _ledger_writer_intent(inst_id, side, ts_ms,
                                 OPEN_INTENT_FILE=OPEN_INTENT_FILE,
                                 OPEN_INTENT_TTL_MS=OPEN_INTENT_TTL_MS)

def load_open_intents() -> List[Dict[str, Any]]:
    """读取原始本地开仓意图（不做 TTL 过滤，过期判定交给对账语义分层）。"""
    try:
        if os.path.exists(OPEN_INTENT_FILE):
            with open(OPEN_INTENT_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                return [i for i in raw if isinstance(i, dict) and i.get("instId")]
    except Exception as e:
        print(f"[挂单对账] 读取本地意图失败: {e}")
    return []


def _order_pos_side(side: str) -> str:
    return "long" if str(side).lower() == "buy" else "short"


def reconcile_pending_orders(trackers: Dict[str, Any] = None, now_ms: int = None, pending: List[Dict[str, Any]] = None) -> Tuple[bool, set]:
    """壳（第八十四刀搬至 `scripts/trader/order_lifecycle.py`，调用期同名注入）。"""
    return _order_lifecycle_reconcile(
        trackers, now_ms, pending,
        _order_pos_side=_order_pos_side,
        load_open_intents=load_open_intents,
        load_trackers=load_trackers,
        OPEN_INTENT_TTL_MS=OPEN_INTENT_TTL_MS,
        RECONCILE_REASON_SIDE_MISMATCH=RECONCILE_REASON_SIDE_MISMATCH,
        RECONCILE_REASON_INTENT_STALE=RECONCILE_REASON_INTENT_STALE,
        RECONCILE_REASON_ORPHAN=RECONCILE_REASON_ORPHAN,
        okx_rest=okx_rest)
def check_black_swan_sentinel() -> Tuple[bool, str]:
    """壳（第八十一刀搬至 `scripts/trader/circuit_guard.py`）。

    调用期解析模块全局再注入 —— `patch.object(aft, "NEWS_SENTIMENT_FILE"/
    "fetch_candles_direct")` 的既有测试面保真。
    """
    return _circuit_guard_sentinel(
        fetch_candles_direct=fetch_candles_direct,
        news_sentiment_file=NEWS_SENTIMENT_FILE)


def is_circuit_breaker_active(usdt_available: float = None):
    """壳（第八十一刀搬至 `scripts/trader/circuit_guard.py`，同上注入形状）。"""
    # 注意：行情/情绪文件的注入**不在这里** —— 基线 breaker 经由门面全局
    # sentinel 间接使用它们；本壳把 sentinel 本身注入（同一 patch 面、更短的路径）。
    return _circuit_guard_breaker(
        usdt_available,
        circuit_breaker_file=CIRCUIT_BREAKER_FILE,
        ledger_json_file=LEDGER_JSON_FILE,
        current_environment=current_environment,
        effective_daily_loss_limit=effective_daily_loss_limit,
        # 活体接线测试的 patch 面（aft.check_black_swan_sentinel）经此保留
        sentinel_check=check_black_swan_sentinel)



def query_positions() -> Tuple[bool, List[Dict[str, Any]], str]:
    """壳（第八十六刀搬至 `scripts/trader/venue_query.py`）。"""
    return _venue_query_positions(okx_rest=okx_rest)

def close_position_confirmed(inst_id: str, pos_side: str, before_size: float, venue: str = "okx") -> Tuple[bool, str]:
    """壳（第八十六刀搬至 `scripts/trader/venue_query.py`）。"""
    return _venue_query_close_confirmed(
        inst_id, pos_side, before_size, venue,
        okx_rest=okx_rest, current_environment=current_environment,
        query_positions=query_positions,
        fetch_other_venue_positions=fetch_other_venue_positions)

def amend_venue_stop_loss(ad, symbol: str, pos_side: str, new_sl: float,
                          contracts: float) -> Tuple[bool, str]:
    """壳（第八十五刀搬至 `scripts/trader/cloud_protection.py`，纯函数无注入）。"""
    return _cloud_protection_amend(ad, symbol, pos_side, new_sl, contracts)

def prune_trackers(trackers: Dict[str, Any], real_pos_dict: Dict[str, Any]) -> int:
    """Remove stale/non-universe trackers while preserving every live exchange position."""
    valid_keys = {
        f"{inst_id}_{str(position.get('posSide', 'net')).lower()}"
        for inst_id, position in real_pos_dict.items()
        if float(position.get("pos", 0) or 0) > 0
    }
    removed = 0
    for key in list(trackers):
        if key not in valid_keys:
            trackers.pop(key, None)
            removed += 1
    return removed


# =============================================================================
# US-003 交易决策面接入：手动选所优先 + 可解释评分路由 + 预算原子预留
# =============================================================================
# 主脑信号进下单流程**之前**必须先过选所路由与预算预留；任一失败 → 本轮不下单
# （fail-closed），并把选所证据（含 rejected）随决策 JSON 落盘。
# 封闭性约定（测试依赖）：venue_router / risk_reservation / registry /
# routing_policy / AI_DECISION_CACHE_FILE 全部按**模块绑定名**在本文件引用，
# 逐项 patch 即可完全离线；本文件绝不直连除 OKX 直签链路以外的下单端点。

AI_DECISION_CACHE_FILE = os.path.join(DATA_DIR, "ai_brain_decisions.json")
VENUE_HEALTH_FILE = os.path.join(DATA_DIR, "venue_health.json")
#: 组合风险预算总上限（US-001 预留层封顶口径；0/未配置 = 只累计台账不封顶）
PORTFOLIO_RISK_BUDGET_ENV = "R20_PORTFOLIO_RISK_BUDGET_USDT"
#: 场所取数健康度可容忍年龄（brain 15min 周期写盘，给 2 个周期 + 余量）
VENUE_HEALTH_MAX_AGE_S = 1900.0

#: 已接入真实下单实现的场所 → 提交函数。三所对等支持原生受保护开仓。
VENUE_SUBMITTERS: Dict[str, str] = {
    "okx": "okx_rest.place_order",
    "gate": "execution_router.open_protected_position",
    "binance": "execution_router.open_protected_position",
}


def portfolio_risk_budget_usdt() -> float:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，调用期同名注入）。"""
    return _routing_policy_risk_budget(
        PORTFOLIO_RISK_BUDGET_ENV=PORTFOLIO_RISK_BUDGET_ENV)

def load_preferred_venue() -> str:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，调用期同名注入）。"""
    return _routing_policy_load_pref(
        routing_policy=routing_policy)

def load_routing_mode() -> str:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，调用期同名注入）。"""
    return _routing_policy_load_mode(
        routing_policy=routing_policy)

def venue_execution_ready(venue: str, environment: str) -> bool:
    """壳（第八十六刀搬至 `scripts/trader/venue_query.py`）。"""
    return _venue_query_exec_ready(
        venue, environment,
        venue_registry=venue_registry,
        current_environment=current_environment,
        _BROKEN_VENUES=_BROKEN_VENUES)

def fetch_other_venue_positions(environment: str):
    """壳（第八十六刀搬至 `scripts/trader/venue_query.py`）。"""
    return _venue_query_other_positions(
        environment, venue_registry=venue_registry,
        venue_execution_ready=venue_execution_ready)

def _venue_health_stamp():
    """壳（第八十六刀搬至 `scripts/trader/venue_query.py`）。"""
    return _venue_query_health_stamp(VENUE_HEALTH_FILE=VENUE_HEALTH_FILE)

def build_venue_candidates(inst_id: str, environment: str) -> List[Dict[str, Any]]:
    """壳（第八十二刀搬至 `scripts/trader/venue_evidence.py`，调用期注入门面全局）。"""
    return _venue_evidence_candidates(
        inst_id, environment,
        venue_health_stamp=_venue_health_stamp,
        venue_registry=venue_registry,
        load_preferred_venue=load_preferred_venue,
        venue_execution_ready=venue_execution_ready,
        MAKER_FEE_RATE=MAKER_FEE_RATE,
        VENUE_HEALTH_MAX_AGE_S=VENUE_HEALTH_MAX_AGE_S)

def reservation_manager():
    """US-001 预留层单一台账（默认 data/risk_reservation.db）。

    每次取用都新建实例：RiskReservationManager 无进程内态（逐操作短连接 + 表内
    幂等），实例化只多一次建表；换来的是**总上限热生效**——get_manager 的默认
    单例会把首次读到的 limit 钉死，风控页改预算要重启进程才生效。
    """
    budget = portfolio_risk_budget_usdt()
    return risk_reservation.get_manager(
        db_path=risk_reservation.DEFAULT_DB_PATH,
        total_limit_usdt=budget if budget > 0 else None)


def estimate_margin_usdt(notional_usdt: float, margin_usdt: float = 0.0) -> float:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，纯函数）。"""
    return _routing_policy_estimate_margin(notional_usdt, margin_usdt)

def _decision_payload(decision, preferred: str) -> Dict[str, Any]:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，纯函数）。"""
    return _routing_policy_decision_payload(decision, preferred)

def persist_venue_decision(inst_id: str, venue_decision: Dict[str, Any]) -> bool:
    """壳（第八十二刀搬至 `scripts/trader/venue_evidence.py`）。

    同名注入 `AI_DECISION_CACHE_FILE`：patch 门面常量的既有面保真；
    flock 包裹的写路径真现在子包（batch3 tripwire 断言指向那里）。
    """
    return _venue_evidence_persist(inst_id, venue_decision,
                                   AI_DECISION_CACHE_FILE=AI_DECISION_CACHE_FILE)

def _rejection_focus_reason(decision, candidates: List[Dict[str, Any]],
                            preferred: str) -> str:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，纯函数）。"""
    return _routing_policy_rejection_reason(decision, candidates, preferred)

def route_and_reserve_signal(inst_id: str, side: str, size: float, price: float,
                             notional_usdt: float = 0.0, margin_usdt: float = 0.0,
                             intent_id: str = "") -> Dict[str, Any]:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，调用期同名注入）。"""
    return _routing_policy_route(
        inst_id, side, size, price, notional_usdt, margin_usdt, intent_id,
        _decision_payload=_decision_payload,
        _rejection_focus_reason=_rejection_focus_reason,
        build_venue_candidates=build_venue_candidates,
        estimate_margin_usdt=estimate_margin_usdt,
        load_preferred_venue=load_preferred_venue,
        load_routing_mode=load_routing_mode,
        persist_venue_decision=persist_venue_decision,
        portfolio_budget_guard=portfolio_budget_guard,
        portfolio_risk_budget_usdt=portfolio_risk_budget_usdt,
        reservation_manager=reservation_manager,
        VENUE_SUBMITTERS=VENUE_SUBMITTERS,
        current_environment=current_environment,
        risk_reservation=risk_reservation,
        venue_router=venue_router)

def confirm_signal_reservation(reservation: Dict[str, Any]) -> None:
    """审计④6(2026-09-13)：成交后把预算预留 pending→confirmed（仍占预算直至终态）。
    旧调用点用 except:pass 吞掉了「confirm 方法不存在」的 AttributeError——每次成交必
    抛必吞、状态字段永远说谎。现方法已在 RiskReservationManager 补齐；失败仍不阻断
    交易主流程，但必须可见（预算由 TTL/recovery 兜底对账）。"""
    if not isinstance(reservation, dict):
        return
    try:
        reservation["manager"].confirm(reservation["account_key"], reservation["intent_id"])
    except Exception as exc:
        print(f"[预算预留] warn confirmed 状态推进失败（预算仍占用，对账兜底）: {exc}")


def portfolio_budget_guard(budget_total: float, budget_used: float, margin_est: float,
                           environment: str = "") -> Optional[str]:
    """壳（第八十七刀搬至 `scripts/trader/routing_policy.py`，纯函数）。"""
    return _routing_policy_budget_guard(budget_total, budget_used, margin_est, environment)

def release_signal_reservation(reservation: Dict[str, Any], reason: str = "") -> None:
    """下单未获受理 → 释放本轮预留（终态 rejected，预算即刻回笼）。"""
    if not isinstance(reservation, dict):
        return
    try:
        reservation["manager"].release(reservation["account_key"],
                                       reservation["intent_id"],
                                       state=risk_reservation.STATE_REJECTED)
        print(f"[预算预留] 已释放 {reservation['intent_id']}（{reason or '下单未受理'}）")
    except Exception as exc:
        print(f"[预算预留] warn 释放失败（交由重启 recovery 处理）: {exc}")


#: 预留对账释放 TTL（秒）：现货交易所已不存在且超时 → 终态 closed 回笼预算。
#: 7200s ≈ 8 个 15min 周期——远大于限价单挂单窗口与成交确认窗口，宁慢勿错杀。
RESERVATION_RECONCILE_TTL_S = 7200.0


def _utc_age_seconds(ts_str: str, now_utc: float) -> float:
    """薄壳：转调 `scripts/trader/reservation_reconcile.py`（第五十八刀）。

    ⚠️ 依赖一律调用期注入（本模块会被 `pin_baseline_risk_env()` 原地 reload，
    而重载名单**不含子模块**，import 期绑定会读到旧值）。
    """
    return _rr_utc_age_seconds(ts_str, now_utc)


def reconcile_reservation_ledger(real_pos_dict: Dict[str, Any],
                                 pending_inst_ids: set,
                                 environment: str,
                                 ttl_s: float = None,
                                 venue_snapshot: Optional[Dict[str, list]] = None) -> int:
    """薄壳：转调 `scripts/trader/reservation_reconcile.py`（第五十八刀）。

    ⚠️ **签名对外一字未变**（`tests/test_reservation_reconcile.py` 用位置参数调用）。
    四个依赖全部在**调用时**注入 —— 尤其 `reservation_manager` 与
    `fetch_other_venue_positions` 是本模块的模块级名字，测试用
    `patch.object(trader, …)` 替换它们；若子模块 import 期绑一份，
    那 9 条用例会当场翻红（且会真的出网）。
    """
    return _rr_reconcile(
        real_pos_dict,
        pending_inst_ids,
        environment,
        reservation_manager=reservation_manager,
        fetch_other_venue_positions=fetch_other_venue_positions,
        state_closed=risk_reservation.STATE_CLOSED,
        default_ttl_s=RESERVATION_RECONCILE_TTL_S,
        ttl_s=ttl_s,
        venue_snapshot=venue_snapshot,
    )


def submit_protected_limit_order(inst_id: str, side: str, pos_side: str, size: float, price: float, tp_px: float, sl_px: float, venue_ctx: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """壳（第八十八刀搬至 `scripts/trader/order_submit.py`，调用期同名注入）。"""
    return _order_submit_protected(
        inst_id, side, pos_side, size, price, tp_px, sl_px, venue_ctx,
        confirm_signal_reservation=confirm_signal_reservation,
        record_open_intent=record_open_intent,
        release_signal_reservation=release_signal_reservation,
        route_and_reserve_signal=route_and_reserve_signal,
        MAX_LEVERAGE=MAX_LEVERAGE,
        MIN_LEVERAGE=MIN_LEVERAGE,
        canonical_base=canonical_base,
        current_environment=current_environment,
        fetch_ticker=fetch_ticker,
        okx_rest=okx_rest,
        venue_registry=venue_registry)


def _float_or_zero(value: Any) -> float:
    try:
        return abs(float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _live_oco_coverage(orders: List[Dict[str, Any]], pos_side: str) -> float:
    """壳（第八十五刀搬至 `scripts/trader/cloud_protection.py`）。"""
    return _cloud_protection_coverage(orders, pos_side, _float_or_zero=_float_or_zero)

def ensure_cloud_position_protection(inst_id: str, pos_side: str, size: float, tp_px: float, sl_px: float) -> Tuple[bool, str]:
    """壳（第八十五刀搬至 `scripts/trader/cloud_protection.py`）。"""
    return _cloud_protection_ensure(
        inst_id, pos_side, size, tp_px, sl_px,
        okx_rest=okx_rest, _live_oco_coverage=_live_oco_coverage)

def build_signal_snapshot(f: dict) -> dict:
    """壳（第八十二刀搬至 `scripts/trader/signal_snapshot.py`）。

    调用期解析 `DATA_DIR` 注入 —— `patch.object(aft, "DATA_DIR", tmp)`
    的既有专测面保真。
    """
    return _signal_snapshot_build(f, data_dir=DATA_DIR)

def record_signal_snapshot(snap: dict) -> None:
    """把开仓时刻的数理快照写入 signal_journal.json，保留最近 500 条供复盘 join。"""
    try:
        journal = []
        if os.path.exists(SIGNAL_JOURNAL_FILE):
            with open(SIGNAL_JOURNAL_FILE, "r", encoding="utf-8") as handle:
                journal = json.load(handle)
        journal.append(snap)
        with open(SIGNAL_JOURNAL_FILE, "w", encoding="utf-8") as handle:
            json.dump(journal[-500:], handle, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to record signal snapshot: {e}")


def record_trade(trade_data):
    """壳（第八十三刀搬至 `scripts/trader/ledger_writer.py`，调用期同名注入）。"""
    return _ledger_writer_trade(
        trade_data,
        LEDGER_JSON_FILE=LEDGER_JSON_FILE,
        _atomic_write_json=_atomic_write_json,
        record_trade_sqlite=record_trade_sqlite,
        current_environment=current_environment,
        __version__=__version__)
# =============================================================================
# 🧮 Enhanced Quantitative Technical Indicators Math Engine
# =============================================================================
from r20_backend.execution import (
    calc_ema,
    calc_rsi,
    calc_atr,
    calc_macd_histogram_acceleration,
    calc_obv_trend,
    calc_bollinger_squeeze,
)

# =============================================================================
# 🚀 High-Alpha Multi-Factor Extraction & Quantitative Feature Assembly
# =============================================================================
def fetch_single_instrument_data(item, all_positions, usdt_available):
    """装配单个标的的多因子特征。实现见 scripts/trader/factors.py。

    门面保留同名壳：唯一调用点（execute_portfolio 内 executor.map）以及可能的外部
    引用都按全局名查找，调用点无需改动。依赖在**调用时**注入 —— 理由见该模块 docstring。
    """
    return _fetch_single_instrument_data(
        item, all_positions, usdt_available,
        news_sentiment_file=NEWS_SENTIMENT_FILE,
        fetch_candles_direct=fetch_candles_direct,
        instrument_profile=instrument_profile,
        load_adaptive_config=load_adaptive_config,
    )

# =============================================================================
# Trailing Stop & Risk Management
# =============================================================================
def sync_cloud_algo_stop(inst_id: str, pos_side: str, new_sl: float, reason: str = "") -> bool:
    """壳（第八十五刀搬至 `scripts/trader/cloud_protection.py`）。"""
    return _cloud_protection_sync_stop(inst_id, pos_side, new_sl, reason, okx_rest=okx_rest)

def manage_position_tp_and_trailing(f, curr_pos, trackers, timestamp_full, executed_actions):
    if not f.get("market_data_valid"):
        executed_actions.append(f"[{f['name']}] 行情数据不完整，保留云端保护并跳过本地移动止盈")
        return False, "行情无效"
    inst_id = f["instId"]
    name = f["name"]
    cur_px = f["price"]
    asset_type = f.get("type", "crypto")
    profile = ASSET_CLASS_PROFILES.get(asset_type, ASSET_CLASS_PROFILES["crypto"])
    atr = max(f["atr"], cur_px * 0.005)
    prec = f["precision"]
    ct_val = f["ctVal"]
    
    pos_sz = float(curr_pos["pos"])
    is_long = "long" in curr_pos["side"].lower()
    entry_px = float(curr_pos["avgPx"])
    pos_key = f"{inst_id}_{curr_pos['side']}"

    now_ts = int(time.time())
    if pos_key not in trackers:
        score, action, reasons, strat_tag, strat_desc = evaluate_asset_signal(f)
        trackers[pos_key] = {
            "instId": inst_id,
            "name": name,
            "side": curr_pos["side"],
            "policy_version": f.get("policy_version", ""),
            "policy_hash": f.get("policy_hash", ""),
            "strategy_tag": strat_tag if strat_tag != "⚪ 观望" else ("🌊 顺势回踩" if is_long else "⚡ 阻力抛压"),
            "entryPx": entry_px,
            "entryTs": now_ts,
            "entryTime": timestamp_full,
            "initialSz": pos_sz,
            "currentSz": pos_sz,
            "highWaterMark": cur_px,
            "lowWaterMark": cur_px,
            "trailingStopPx": round((entry_px - atr * profile["sl_atr_mult"]) if is_long else (entry_px + atr * profile["sl_atr_mult"]), prec),
            "takeProfitPx": round((entry_px + max(atr * profile["tp_atr_mult"], entry_px * profile["min_profit_ratio"])) if is_long else (entry_px - max(atr * profile["tp_atr_mult"], entry_px * profile["min_profit_ratio"])), prec),
            "signal_snapshot": build_signal_snapshot(f),
            "stage_desc": "持有监控中"
        }
        record_signal_snapshot({
            "instId": inst_id,
            "name": name,
            "side": curr_pos["side"],
            "entryTs": now_ts,
            "entryTime": timestamp_full,
            "entryPx": entry_px,
            "sz": pos_sz,
            "policy_version": f.get("policy_version", ""),
            "snapshot": trackers[pos_key]["signal_snapshot"],
        })

    t = trackers[pos_key]
    if not t.get("policy_version") and f.get("policy_version"):
        t["policy_version"] = f.get("policy_version")
        t["policy_hash"] = f.get("policy_hash", "")
    t["currentSz"] = pos_sz
    if "entryTs" not in t:
        t["entryTs"] = now_ts

    # Peak Profit Tracking
    if is_long:
        t["highWaterMark"] = max(t.get("highWaterMark", cur_px), cur_px)
        cur_profit_px = cur_px - entry_px
        peak_profit_px = t["highWaterMark"] - entry_px
    else:
        t["lowWaterMark"] = min(t.get("lowWaterMark", cur_px), cur_px)
        cur_profit_px = entry_px - cur_px
        peak_profit_px = entry_px - t["lowWaterMark"]

    # 1. Hard Stop Loss (loss protection is independent of profit-lock activation).
    # The tracker stop is the exchange-protection source of truth; if a legacy or
    # partially migrated position has no live cloud OCO, the local 15-minute
    # fail-safe still closes it once the stop is breached.
    # 判定见 scripts/trader/protection.py（长空方向合一）。
    hard_stop_px = float(t.get("trailingStopPx", 0.0) or 0.0)
    hard_stop_hit = protection_signals(is_long=is_long, cur_px=cur_px, hard_stop_px=hard_stop_px)
    if hard_stop_hit:
        closed, close_detail = close_position_confirmed(inst_id, "long" if is_long else "short", pos_sz)
        if not closed:
            executed_actions.append(f"[{name}] 硬止损平仓失败，仓位仍保留: {close_detail}")
            return False, "硬止损平仓失败"
        close_fee = _close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE)
        pnl_val = curr_pos["upl"]
        executed_actions.append(f"[{name}] 🛑 触发硬止损 {hard_stop_px} 并确认平仓 (净盈亏: {pnl_val:+.2f}U)")
        record_trade(_close_trade_payload(
            is_long=is_long, timestamp_full=timestamp_full, name=name,
            action_type="硬止损", side_suffix="硬止损",
            pos_sz=pos_sz, cur_px=cur_px, fee=close_fee, pnl=pnl_val,
            remark=f"价格 {cur_px} 触及保护止损 {hard_stop_px}，交易所确认平仓",
        ))
        add_stop_cooldown(inst_id, "long" if is_long else "short", "硬止损")
        if notify_trade_close:
            notify_trade_close(inst=name, pnl=pnl_val, stage="硬止损平仓", exit_px=cur_px)
        trackers.pop(pos_key, None)
        return True, "已硬止损"

    default_tp_dist = max(atr * profile["tp_atr_mult"], entry_px * profile["min_profit_ratio"])
    if not _float_or_zero(t.get("takeProfitPx")):
        t["takeProfitPx"] = round(entry_px + default_tp_dist if is_long else entry_px - default_tp_dist, prec)
    protected, protection_detail = ensure_cloud_position_protection(
        inst_id, "long" if is_long else "short", pos_sz, float(t["takeProfitPx"]), hard_stop_px
    )
    if not protected:
        closed, close_detail = close_position_confirmed(inst_id, "long" if is_long else "short", pos_sz)
        if not closed:
            executed_actions.append(f"[{name}] 🚨 云端 OCO 缺失且安全退出失败: {protection_detail}; {close_detail}")
            return False, "保护与退出均失败"
        pnl_val = curr_pos["upl"]
        executed_actions.append(f"[{name}] 🧯 云端 OCO 无法确认，已安全平仓: {protection_detail}")
        record_trade(_close_trade_payload(
            is_long=is_long, timestamp_full=timestamp_full, name=name,
            action_type="保护失效退出", side_suffix="保护失效退出",
            pos_sz=pos_sz, cur_px=cur_px,
            fee=_close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE), pnl=pnl_val,
            remark=f"云端 OCO 无法达到全仓覆盖，交易所确认安全平仓：{protection_detail}",
        ))
        add_stop_cooldown(inst_id, "long" if is_long else "short", "云端保护失效")
        if notify_trade_close:
            notify_trade_close(inst=name, pnl=pnl_val, stage="云端保护失效退出", exit_px=cur_px)
        trackers.pop(pos_key, None)
        return True, "保护失效安全退出"
    t["cloudProtection"] = {"verifiedAt": timestamp_full, "detail": protection_detail}

    # 2. Volatility Time-Stop Exit (持仓超最长持仓时间且缩量横盘 → 时间止损，参数见后台风控管理页)
    hold_duration_sec = now_ts - t["entryTs"]
    if hold_duration_sec > TIME_STOP_HOURS * 3600 and abs(cur_profit_px) < TIME_STOP_ATR_BAND * atr:
        closed, close_detail = close_position_confirmed(inst_id, "long" if is_long else "short", pos_sz)
        if not closed:
            executed_actions.append(f"[{name}] 时间止损平仓失败，仓位仍保留: {close_detail}")
            return False, "平仓失败"
        close_fee = _close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE)
        executed_actions.append(f"[{name}] ⌛ 超过 {TIME_STOP_HOURS:g} 小时无波动横盘，时间止损平仓释放保证金")
        record_trade(_close_trade_payload(
            is_long=is_long, timestamp_full=timestamp_full, name=name,
            action_type="时间止损", side_suffix="无波动出场",
            pos_sz=pos_sz, cur_px=cur_px, fee=close_fee, pnl=curr_pos["upl"],
            remark=f"持仓超 {TIME_STOP_HOURS:g} 小时无突破，主动平仓释放配比",
        ))
        if notify_trade_close:
            notify_trade_close(inst=name, pnl=float(curr_pos.get("upl", 0.0) or 0.0), stage="时间止损平仓", exit_px=cur_px)
        if pos_key in trackers: del trackers[pos_key]
        return True, "时间止损"

    # 3. Three-Tier Ratchet Profit-Locking & Momentum Take-Profit Engine
    # Tier 1: Breakeven Lock at +1.5x ATR (~1.0R profit, covers taker fee + 0.20% cushion)
    # Tier 2: Solid Wave Profit Lock at +2.2x ATR (~1.6R profit, lock in at least +1.0x ATR profit)
    # Tier 3: Kinetic Momentum Pullback Exit (Symmetric >= 2.0x ATR peak profit with 0.75x ATR pullback)
    
    tier1_breakeven_trigger = 1.5 * atr
    tier2_lock_trigger = 2.2 * atr
    momentum_tp_trigger = 2.0 * atr
    momentum_pullback_buffer = 0.75 * atr
    
    if is_long:
        # Dynamic Ratchet Stop Calculation for Long（数学见 scripts/trader/protection.py）
        old_sl = float(t.get("trailingStopPx", 0.0) or 0.0)
        dynamic_floor_sl, stage_desc = ratcheted_trailing_stop(
            is_long=True, entry_px=entry_px, atr=atr, prec=prec,
            peak_profit_px=peak_profit_px, old_sl=old_sl,
            tier1_breakeven_trigger=tier1_breakeven_trigger,
            tier2_lock_trigger=tier2_lock_trigger,
        )
        if stage_desc:
            t["stage_desc"] = stage_desc
        
        # If dynamic floor stop ratcheted up, commit and sync to cloud OCO
        if dynamic_floor_sl > old_sl and old_sl > 0:
            t["trailingStopPx"] = dynamic_floor_sl
            sync_cloud_algo_stop(inst_id, "long", dynamic_floor_sl, reason=t["stage_desc"])
        else:
            t["trailingStopPx"] = dynamic_floor_sl

        # A. Hit Ratchet Floor Stop (Locked Profit Trigger)
        if cur_px <= dynamic_floor_sl and peak_profit_px >= tier1_breakeven_trigger:
            closed, close_detail = close_position_confirmed(inst_id, "long", pos_sz)
            if not closed:
                executed_actions.append(f"[{name}] 锁利平多失败，仓位仍保留: {close_detail}")
                return False, "平仓失败"
            close_fee = _close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE)
            pnl_val = curr_pos["upl"]
            executed_actions.append(f"[{name}] 🛡️ 触发阶梯动态锁利平仓 (净盈亏: {pnl_val:+.2f}U)")
            record_trade(_close_trade_payload(
                is_long=is_long, timestamp_full=timestamp_full, name=name,
                action_type="阶梯锁利", side_suffix="阶梯锁利平仓",
                pos_sz=pos_sz, cur_px=cur_px, fee=close_fee, pnl=pnl_val,
                remark=f"最高 {t['highWaterMark']} 触发阶梯利润锁定线 {dynamic_floor_sl}",
            ))
            if notify_trade_close:
                notify_trade_close(inst=name, pnl=pnl_val, stage="阶梯锁利平仓", exit_px=cur_px)
            if pos_key in trackers: del trackers[pos_key]
            return True, "已阶梯锁利"

        # B. Kinetic Momentum Pullback Exit from Peak (Symmetric 2.0x ATR profit with 0.75x ATR pullback)
        if peak_profit_px >= momentum_tp_trigger and cur_px <= (t["highWaterMark"] - momentum_pullback_buffer):
            closed, close_detail = close_position_confirmed(inst_id, "long", pos_sz)
            if not closed:
                executed_actions.append(f"[{name}] 动能见顶移动止盈失败，仓位仍保留: {close_detail}")
                return False, "平仓失败"
            close_fee = _close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE)
            pnl_val = curr_pos["upl"]
            executed_actions.append(f"[{name}] 🎯 触发高点回撤动能止盈 (净盈亏: {pnl_val:+.2f}U)")
            record_trade(_close_trade_payload(
                is_long=is_long, timestamp_full=timestamp_full, name=name,
                action_type="移动止盈", side_suffix="高点回撤止盈",
                pos_sz=pos_sz, cur_px=cur_px, fee=close_fee, pnl=pnl_val,
                remark=f"最高 {t['highWaterMark']} 动能回撤触及移动止盈线",
            ))
            if notify_trade_close:
                notify_trade_close(inst=name, pnl=pnl_val, stage="移动止盈", exit_px=cur_px)
            if pos_key in trackers: del trackers[pos_key]
            return True, "已移动止盈"

    else:
        # Dynamic Ratchet Stop Calculation for Short（数学见 scripts/trader/protection.py）
        old_sl = float(t.get("trailingStopPx", 0.0) or 0.0)
        dynamic_floor_sl, stage_desc = ratcheted_trailing_stop(
            is_long=False, entry_px=entry_px, atr=atr, prec=prec,
            peak_profit_px=peak_profit_px, old_sl=old_sl,
            tier1_breakeven_trigger=tier1_breakeven_trigger,
            tier2_lock_trigger=tier2_lock_trigger,
        )
        if stage_desc:
            t["stage_desc"] = stage_desc
        
        # If dynamic floor stop ratcheted down (tightened for short), commit and sync to cloud OCO
        if dynamic_floor_sl < old_sl and old_sl > 0:
            t["trailingStopPx"] = dynamic_floor_sl
            sync_cloud_algo_stop(inst_id, "short", dynamic_floor_sl, reason=t["stage_desc"])
        else:
            t["trailingStopPx"] = dynamic_floor_sl

        # A. Hit Ratchet Floor Stop (Locked Profit Trigger)
        if cur_px >= dynamic_floor_sl and peak_profit_px >= tier1_breakeven_trigger:
            closed, close_detail = close_position_confirmed(inst_id, "short", pos_sz)
            if not closed:
                executed_actions.append(f"[{name}] 锁利平空失败，仓位仍保留: {close_detail}")
                return False, "平仓失败"
            close_fee = _close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE)
            pnl_val = curr_pos["upl"]
            executed_actions.append(f"[{name}] 🛡️ 触发阶梯动态锁利平仓 (净盈亏: {pnl_val:+.2f}U)")
            record_trade(_close_trade_payload(
                is_long=is_long, timestamp_full=timestamp_full, name=name,
                action_type="阶梯锁利", side_suffix="阶梯锁利平仓",
                pos_sz=pos_sz, cur_px=cur_px, fee=close_fee, pnl=pnl_val,
                remark=f"最低 {t['lowWaterMark']} 触发阶梯利润锁定线 {dynamic_floor_sl}",
            ))
            if notify_trade_close:
                notify_trade_close(inst=name, pnl=pnl_val, stage="阶梯锁利平仓", exit_px=cur_px)
            if pos_key in trackers: del trackers[pos_key]
            return True, "已阶梯锁利"

        # B. Kinetic Momentum Pullback Exit from Peak (Symmetric 2.0x ATR profit with 0.75x ATR pullback)
        if peak_profit_px >= momentum_tp_trigger and cur_px >= (t["lowWaterMark"] + momentum_pullback_buffer):
            closed, close_detail = close_position_confirmed(inst_id, "short", pos_sz)
            if not closed:
                executed_actions.append(f"[{name}] 动能见底移动止盈失败，仓位仍保留: {close_detail}")
                return False, "平仓失败"
            close_fee = _close_fee(pos_sz, ct_val, cur_px, TAKER_FEE_RATE)
            pnl_val = curr_pos["upl"]
            executed_actions.append(f"[{name}] 🎯 触发低点反弹动能止盈 (净盈亏: {pnl_val:+.2f}U)")
            record_trade(_close_trade_payload(
                is_long=is_long, timestamp_full=timestamp_full, name=name,
                action_type="移动止盈", side_suffix="低点反弹止盈",
                pos_sz=pos_sz, cur_px=cur_px, fee=close_fee, pnl=pnl_val,
                remark=f"最低 {t['lowWaterMark']} 动能反弹触及移动止盈线",
            ))
            if notify_trade_close:
                notify_trade_close(inst=name, pnl=pnl_val, stage="移动止盈", exit_px=cur_px)
            if pos_key in trackers: del trackers[pos_key]
            return True, "已移动止盈"

    return False, "持仓监控中"

def execute_ai_position_management(real_pos_dict, trackers, timestamp_full, executed_actions):
    """执行主脑写下的持仓指令。实现与两条安全语义见 scripts/trader/position_mgmt.py。

    注入项**调用期**从门面取值：`AI_POSITION_MANAGEMENT_FILE` 是既有测试缝
    （测试会 patch 门面属性），其余是执行层函数与配置常量。
    """
    return _execute_ai_position_management_impl(
        real_pos_dict, trackers, timestamp_full, executed_actions,
        ai_position_management_file=AI_POSITION_MANAGEMENT_FILE,
        ai_tightens_stop=ai_tightens_stop,
        close_position_confirmed=close_position_confirmed,
        okx_rest=okx_rest,
        venue_registry=venue_registry,
        current_environment=current_environment,
        amend_venue_stop_loss=amend_venue_stop_loss,
    )

# =============================================================================
# 🧠 R20 Quantum Trader v6.8.1 Multi-Factor Scoring & Strategy Setup Classifier
# =============================================================================
def evaluate_asset_signal(f):
    """连续多因子量化评分（-5.0 ~ +5.0）。实现见 scripts/trader/signals.py。

    门面保留同名壳：本函数在文件内的 3 处调用点（以及测试里的
    `ai_factor_trader.evaluate_asset_signal(f)`）都按全局名查找，故调用点无需改动。
    依赖在**调用时**注入，而不是被子模块 import 期烘焙 —— 详见该模块 docstring
    （`pin_baseline_risk_env()` 的重载名单不含子模块，import 期绑定会让基线风控测试翻红）。
    """
    return _evaluate_asset_signal(
        f,
        asset_class_profiles=ASSET_CLASS_PROFILES,
        is_in_stop_cooldown=is_in_stop_cooldown,
        load_adaptive_config=load_adaptive_config,
    )

def single_trader_cycle(func):
    """Prevent cron/manual overlap across the complete order-management cycle."""
    def wrapped(*args, **kwargs):
        os.makedirs(DATA_DIR, exist_ok=True)
        lock_handle = open(TRADER_LOCK_FILE, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_handle.close()
            print("[Trader] Skip: another portfolio cycle is still running")
            return None
        try:
            now_slot = int(time.time()) // 900
            if os.path.exists(TRADER_SLOT_FILE):
                try:
                    with open(TRADER_SLOT_FILE, "r", encoding="utf-8") as f:
                        slot_state = json.load(f)
                    same_slot = int(slot_state.get("slot", -1)) == now_slot
                    recently_started = int(time.time()) - int(slot_state.get("started_at", 0) or 0) < 120
                    if same_slot and recently_started:
                        print("[Trader] Skip: duplicate trigger detected in this 15-minute slot")
                        return None
                except Exception:
                    pass
            with open(TRADER_SLOT_FILE, "w", encoding="utf-8") as f:
                json.dump({"slot": now_slot, "started_at": int(time.time()), "pid": os.getpid()}, f)
            lock_handle.seek(0)
            lock_handle.truncate()
            lock_handle.write(str(os.getpid()))
            lock_handle.flush()
            cycle_environment = freeze_okx_environment()
            print(f"[Trader] OKX environment frozen for cycle: {cycle_environment.mode.upper()} / {cycle_environment.identity}")
            return func(*args, **kwargs)
        finally:
            unfreeze_okx_environment()
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
    return wrapped


# =============================================================================
# Master Portfolio Execution Loop
# =============================================================================
@single_trader_cycle
def execute_portfolio():
    # US-002 fail-closed entry gate: without a static V5 API Key for the frozen
    # cycle environment the engine must physically refuse to trade.
    # current_environment (not selected_environment): the decorator froze the env
    # for this cycle and okx_rest reads the same frozen instance — the gate must
    # judge the very environment the REST channel will sign with.
    _engine_env = current_environment()
    if not _engine_env.configured:
        print(f"[Engine NOT READY] OKX {_engine_env.mode.upper()} API Key 未配置：V5 直签是唯一交易通道，本周期拒绝交易。")
        return None
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_dt = datetime.datetime.now(tz_bj)
    timestamp_full = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 0a. US-006 周期级挂单对账：重启/新周期接管或撤销存量挂单（在新增下单之前）
    reconcile_ok, reconciled_kept_ord_ids = reconcile_pending_orders(trackers=load_trackers())
    if not reconcile_ok:
        # fail-closed：仅禁止本周期新增下单（不是清库），持仓管理照常执行
        print("[挂单对账] fail-closed：本周期禁止新增下单（对账失败，不清库）")
    entries_blocked = not reconcile_ok

    # 0. Clean Stale Open Orders & Harvest Real-time News Sentiment
    orders_ok, orders_error = clean_stale_open_orders(keep_ord_ids=reconciled_kept_ord_ids)
    if not orders_ok:
        print(f"[Trader] Abort: unable to verify/cancel stale open orders: {orders_error}")
        return None
    try:
        harvester_script = os.path.join(WORKSPACE_DIR, "scripts", "news_sentiment_harvester.py")
        if os.path.exists(harvester_script):
            _run_captured(harvester_script, label="news_harvester", timeout=25)
    except Exception as e:
        print(f"News Harvester sync warning: {e}")

    # 1. Fetch Real Positions. A failed account query aborts the complete cycle.
    positions_ok, all_positions, positions_error = query_positions()
    if not positions_ok:
        print(f"[Trader] Abort: unable to verify exchange positions: {positions_error}")
        return None
    real_pos_dict = {}
    real_long_count = 0
    real_short_count = 0

    if isinstance(all_positions, list):
        for p in all_positions:
            pos_sz = float(p.get("pos", 0) or 0)
            if pos_sz > 0:
                side = p.get("posSide", "net").lower()
                inst_id = p.get("instId")
                if inst_id in real_pos_dict:
                    print(f"[Trader] Abort: simultaneous long/short positions for {inst_id} are not supported")
                    return None
                real_pos_dict[inst_id] = p
                if "long" in side:
                    real_long_count += 1
                elif "short" in side:
                    real_short_count += 1

    active_pos_count = len(real_pos_dict)
    long_count = real_long_count
    short_count = real_short_count

    try:
        pending_orders = okx_rest.pending_orders()
    except Exception as pending_exc:
        print(f"[Trader] Abort: unable to verify pending orders: {pending_exc}")
        return None
    pending_inst_ids = set()
    pending_long_count = 0
    pending_short_count = 0
    if isinstance(pending_orders, list):
        for order in pending_orders:
            if str(order.get("state", "live")).lower() not in {"live", "partially_filled"}:
                continue
            inst_id = str(order.get("instId", ""))
            if inst_id:
                pending_inst_ids.add(inst_id)
            pos_side = str(order.get("posSide", "")).lower()
            if pos_side == "long":
                pending_long_count += 1
            elif pos_side == "short":
                pending_short_count += 1
    # 审计(2026-09-13)·外所挂单盲区修复：本守卫此前只数 OKX 在途单，路由派往
    # binance/gate 的单对周期不可见 → 同信号逐轮在外所重复挂单（实锤：binance
    # demo BTC/SUI 各成对）。执行闸开的场并入同一把尺；凭证已死的场收侧已吼
    # CRITICAL 且 router 同样发不出单，此处静默跳过不重复报警。
    _auth_markers = ("INVALID_KEY", "Invalid key", "Invalid API-key", "-2015", "50111",
                     "signature", "Signature", "not exist", "invalid timestamp")
    try:
        _gv_mode = str(current_environment().mode or "")
    except Exception:
        _gv_mode = ""
    pending_inst_ids, pending_long_count, pending_short_count = \
        collect_pending_inst_ids(
            venues=("gate", "binance"), venue_mode=_gv_mode,
            broken_venues=_BROKEN_VENUES, venue_registry=venue_registry,
            load_instruments=load_instruments, auth_markers=_auth_markers,
            warn=print)
    reserved_slot_count = active_pos_count + len(pending_inst_ids)
    reserved_long_count = long_count + pending_long_count
    reserved_short_count = short_count + pending_short_count

    # 1a. 跨所封顶（三所平权开单后的风控收口）：开闸所（gate/binance）的
    # 活跃持仓计入总仓/同向配额；读取失败 → 本周期禁止新增开仓（fail-closed，
    # 与挂单对账同一把尺——宁停不错）。孤儿仓只计数不处置（可能是用户手动仓）。
    try:
        _xv_env = str(current_environment().mode)
    except Exception as _xv_exc:
        _xv_env = ""
        print(f"[跨所封顶] warn 周期冻结环境不可得（{_xv_exc}），按不可信环境处理")
    xv_ok, xv_positions_by_venue, xv_error = fetch_other_venue_positions(_xv_env)
    # 巡检文案口径（审计 D 级）：持仓数历来只报 OKX，跨所持仓仅在封顶逻辑里
    # 出现——面板/日志读起来「0/8」像全空，实际外所可能有数笔。此处统一算出
    # 跨所笔数供 AI 提示词与巡检日志；拉取失败显式标「未知」，绝不装 0。
    _xv_total = sum(len(v or []) for v in (xv_positions_by_venue or {}).values()) if xv_ok else None
    xv_enabled = bool(_xv_env) and any(venue_execution_ready(v, _xv_env)
                                       for v in ("gate", "binance"))
    if (xv_enabled or not _xv_env) and not xv_ok:
        print(f"[跨所封顶] fail-closed 本周期禁止新增开仓: {xv_error or '环境轴不可得'}")
        entries_blocked = True
    else:
        for _v, _rows in (xv_positions_by_venue or {}).items():
            for _p in _rows:
                print(f"[跨所封顶] {_v} {_p.get('inst_id')} {_p.get('side')} "
                      f"size={_p.get('size_signed')} 纳入本周期仓位配额（只计数不处置）")
                reserved_slot_count += 1
                if str(_p.get("side", "")).lower() == "long":
                    reserved_long_count += 1
                else:
                    reserved_short_count += 1

    # 1b. US-010 预留对账：基于本周期刚核验的持仓/挂单实况回笼陈旧占用
    #     （活仓/在途挂单一律保留；无仓无挂且超 TTL 才 closed——宁慢不错杀）。
    try:
        reconcile_reservation_ledger(real_pos_dict, pending_inst_ids, _xv_env,
                                     venue_snapshot=xv_positions_by_venue)
    except Exception as _rc_exc:
        print(f"[预留对账] warn 对账器异常（不影响本周期交易）: {_rc_exc}")

    try:
        bal_res = okx_rest.balances()
    except Exception as bal_exc:
        print(f"[Trader] Abort: unable to verify account balance: {bal_exc}")
        return None
    usdt_available = 0.0
    if bal_res:
        for d in bal_res[0].get("details", []):
            if d.get("ccy") == "USDT":
                usdt_available = float(d.get("availBal", 0.0))
                break

    # 2. Parallel fetch for the configured crypto universe
    with ThreadPoolExecutor(max_workers=len(TARGET_INSTRUMENTS)) as executor:
        all_factors = list(executor.map(lambda item: fetch_single_instrument_data(item, all_positions, usdt_available), TARGET_INSTRUMENTS))

    # 3. Process Positions & Dynamic Trailing Exits
    executed_actions = []
    trackers = load_trackers()
    stale_tracker_count = prune_trackers(trackers, real_pos_dict)
    if stale_tracker_count:
        executed_actions.append(f"清理 {stale_tracker_count} 条已失效持仓追踪记录")
    for f in all_factors:
        curr_pos = f["position"]
        if curr_pos:
            manage_position_tp_and_trailing(f, curr_pos, trackers, timestamp_full, executed_actions)
    save_trackers(trackers)

    # 4. Check Circuit Breaker & Batch AI Brain Scan (Including Active Positions Detail)
    cb_active, cb_reason = is_circuit_breaker_active(usdt_available)
    # 单标的累计保证金上限按可用余额自适应，与提示词 {{risk_budget}} 同口径
    ASSET_MARGIN_CAP = effective_single_asset_margin(usdt_available)

    brain_cache = {}
    # One LLM call covers the full six-instrument universe and all active positions.
    if not cb_active and execute_batch_ai_brain_cycle:
        try:
            pos_desc = f"当前系统总持仓 OKX {active_pos_count}/{MAX_CONCURRENT_POSITIONS} (多{long_count}/空{short_count})｜跨所持仓 {_xv_total if _xv_total is not None else '未知(拉取失败)'} 笔"
            # 持仓全景装配（阶段 4·B3 第三十一刀：迁至 scripts/trader/position_universe.py）
            active_pos_list = _collect_okx_position_payloads(all_factors, trackers)
            # 汇入多所（Binance / Gate）在管持仓，形成三所平权持仓全景。
            # 审计(2026-09-13)：必须复用 1a 已冻结的周期快照（零重复出网）。
            _merge_cross_venue_positions(active_pos_list, xv_positions_by_venue, all_factors)
            brain_cache = execute_batch_ai_brain_cycle(pos_desc, active_pos_list, usdt_available=usdt_available) or {}
            if brain_cache:
                refreshed_ok, refreshed_positions, refreshed_error = query_positions()
                if not refreshed_ok:
                    executed_actions.append(f"AI持仓管理跳过：无法刷新真实仓位 ({refreshed_error})")
                else:
                    refreshed_pos_dict = {
                        p.get("instId"): p for p in refreshed_positions
                        if float(p.get("pos", 0) or 0) > 0
                    }
                    execute_ai_position_management(refreshed_pos_dict, trackers, timestamp_full, executed_actions)
                    save_trackers(trackers)
            else:
                _hf = read_cycle_health() if read_cycle_health else {}
                if _hf.get("last_status") == "failed":
                    _cf = int(_hf.get("consecutive_failures", 0) or 0)
                    _warn = f"本轮AI推理失败（连续{_cf}轮｜{_hf.get('last_error') or '未知原因'}），禁止复用旧持仓指令"
                    if _cf >= 3:
                        _warn = "🔴 AI决策链连续" + str(_cf) + "轮失败——非并发跳过，模型/密钥/额度需人工核查！" + _warn
                    executed_actions.append(_warn)
                    if _cf >= 3:
                        print(f"[AI Health] 🔴 连续 {_cf} 轮批次决策失败，最近错误: {_hf.get('last_error')}")
                else:
                    executed_actions.append("本轮AI推理并发跳过（旧指令不违规复用），禁止复用旧持仓指令")
        except Exception as e:
            print(f"[AI Brain Batch Scan Warning] {e}")

    # 审计 P2-11：标的池不可信（文件损坏/为空/条目非法）时，旧实现会拿 10 币出厂默认
    # 清单继续开新仓 —— 管理员删掉的标的会因"文件坏了"重新被交易。这里 fail-closed：
    # 只保留持仓风控接管（止损/移动止损/AI 平仓在上面的分支已跑完），不开新仓。
    if not cb_active and not pool_is_trustworthy():
        _ps = pool_state()
        _pool_warn = (f"⛔ 标的池不可信（{_ps.get('status')}: {_ps.get('detail')}）"
                      f"——本轮只做持仓风控接管，禁止开新仓")
        print(f"[交易池闸门] {_pool_warn}")
        executed_actions.append(_pool_warn)

    if not cb_active and pool_is_trustworthy():
        for f in all_factors:
            asset_type = f.get("type", "crypto")
            if not is_tradfi_market_liquid(asset_type):
                continue

            score, action, reasons, strat_tag, strat_desc = evaluate_asset_signal(f)
            inst_id = f["instId"]
            curr_pos = f["position"]
            prec = f["precision"]
            ct_val = f["ctVal"]
            profile = ASSET_CLASS_PROFILES.get(asset_type, ASSET_CLASS_PROFILES["crypto"])
            
            adaptive_cfg = load_adaptive_config()
            # P2-5：池条目 per-instrument 参数优先（旧实现只认资产类别硬编码）
            _inst_profile = instrument_profile(f, asset_type)
            tp_mult = adaptive_cfg.get("tp_atr_mult", _inst_profile.get("tp_atr_mult", 2.2))
            sl_mult = adaptive_cfg.get("sl_atr_mult", _inst_profile.get("sl_atr_mult", 1.3))

            atr = max(f["atr"], f["price"] * 0.005)
            min_prof = adaptive_cfg.get("min_profit_ratio", profile.get("min_profit_ratio", 0.008))
            tp_dist = max(atr * tp_mult, f["price"] * min_prof)
            sl_dist = atr * sl_mult

            # Gate 1: LLM AI Brain Full Execution Authority
            # When AI Brain is active, AI Brain is the SOLE decider for action, leverage, margin, and TP/SL.
            ai_info = brain_cache.get(inst_id) if isinstance(brain_cache, dict) else None
            if not ai_info or "decision" not in ai_info:
                print(f"[AI Brain 全权拦截] {f['name']} 本轮无有效新鲜 AI 决策，禁止开仓")
                continue

            ai_decision = ai_info["decision"]
            ai_act = str(ai_decision.get("action", "WAIT")).upper()
            ai_conf = float(ai_decision.get("confidence", 0) or 0)
            ai_reason = ai_decision.get("summary_reason", "")

            f["ai_thought"] = ai_info.get("thought_process", {})
            f["ai_reason"] = ai_reason
            f["ai_confidence"] = ai_conf
            f["policy_version"] = ai_info.get("policy_version", "")
            f["policy_hash"] = ai_info.get("policy_hash", "")

            # Direct Action Assignment from LLM
            if ai_act in ["BUY_LONG", "SELL_SHORT"]:
                action = ai_act
                strat_tag = f"🧠 AI大脑({ai_act})"
                strat_desc = f"【AI全权决策】{ai_reason}"
                print(f"[AI Brain 全权指令] {f['name']} AI 直接指示 {action} (置信度={ai_conf}%, 理由: {ai_reason})")
            else:
                action = "HOLD"
                strat_tag = "🤖 AI观望"
                strat_desc = f"AI大脑判定当前无高确定性机会({ai_reason})"
                continue

            # Dynamic Equal-Risk Position Size with AI Custom Margin Allocation
            actual_sz = f["sz"]
            ai_margin = float(ai_decision.get("margin_usdt", 0.0) or 0.0)
            ai_lever = float(ai_decision.get("leverage", 3) or 3)
            # 杠杆硬钳制：无论 AI 裁决多激进，执行层都夹在后台风控页配置的区间内
            # （审计 P2-8：旧实现下限写死 1.0，风控页的 MIN_LEVERAGE 在单所路径不成立）
            # 审计 P2-5：池条目的 per-instrument max_leverage（tier 派生 3x/5x）此前无人读；
            # 现在它是该标的的硬上限（与全局上限取更严者），并透传给多所路由。
            # 具体夹取顺序见 scripts/trader/leverage.py。
            try:
                _inst_lever_cap = float(f.get("max_leverage") or 0.0)
            except (TypeError, ValueError):
                _inst_lever_cap = 0.0
            _ai_lever_raw = ai_lever
            ai_lever, _lever_tightened = clamp_ai_leverage(
                ai_lever, min_leverage=MIN_LEVERAGE, max_leverage=MAX_LEVERAGE,
                inst_lever_cap=_inst_lever_cap)
            if _lever_tightened:
                print(f"[杠杆闸门] {f['name']} 池内单标的杠杆上限 {_inst_lever_cap:g}x < 全局 {_ai_lever_raw:g}x，已按池值收紧")
            if abs(ai_lever - float(ai_decision.get("leverage", 3) or 3)) > 1e-9:
                print(f"[杠杆闸门] {f['name']} AI 裁决杠杆 {ai_decision.get('leverage')}x "
                      f"超出配置区间 [{float(MIN_LEVERAGE or 0):g}x, {float(MAX_LEVERAGE or 0):g}x]，"
                      f"已夹至 {ai_lever:g}x")
            step_sz = float(f.get("minSz", 1) or 1)

            # If AI planned margin & leverage, calculate custom contract size
            # （四道钳制的顺序见 scripts/trader/sizing.py —— 顺序换了会放大仓位）
            actual_sz = size_for_decision(
                ai_margin=ai_margin, ai_lever=ai_lever, price=f["price"],
                ct_val=ct_val, step_sz=step_sz, base_sz=f["sz"],
                usdt_available=usdt_available, actual_sz=actual_sz,
                quantize_size=quantize_size,
                max_size_within_margin=max_size_within_margin)

            if actual_sz <= 0:
                if f.get("size_below_exchange_min") or ai_margin > 0:
                    print(f"[仓位跳过] {f['name']} 按风险预算推导的数量低于交易所最小下单量 {step_sz} 张"
                          f"(可用余额 {usdt_available}, 单笔风险额 {f['risk_per_trade_usd']}U)，本周期不交易该标的")
                continue

            # Long Execution (Initial Entry or Strict Pyramiding Scale-In)
            if action == "BUY_LONG":
                is_scale_in = False
                allow_entry = False

                # Case A: Standard Initial Entry (No existing position & slot available)
                if not curr_pos and inst_id not in pending_inst_ids and reserved_slot_count < MAX_CONCURRENT_POSITIONS and reserved_long_count < MAX_SAME_DIRECTION_POSITIONS:
                    if ai_conf >= MIN_ENTRY_CONFIDENCE:
                        allow_entry = True
                    else:
                        print(f"[首发开多拦截] {f['name']} AI置信度 {ai_conf:.1f}% 未达 80% 门禁，宁缺毋滥，拦截入场")

                # Case B: Strict Pyramiding Scale-In (Existing long position in profit/breakeven)
                elif curr_pos and str(curr_pos.get("side", "")).lower() == "long" and inst_id not in pending_inst_ids:
                    pos_upl = float(curr_pos.get("upl", 0.0) or 0.0)
                    pos_upl_ratio = float(curr_pos.get("uplRatio", 0.0) or 0.0)
                    pos_avg_px = float(curr_pos.get("avgPx", 0.0) or 0.0)
                    curr_margin = float(curr_pos.get("margin", 0.0) or 0.0)
                    tracker = trackers.get(f"{inst_id}_long", {})
                    scale_count = int(tracker.get("scale_count", 0))
                    trailing_sl = float(tracker.get("trailingStopPx", 0.0) or 0.0)

                    # Ironclad Pyramiding Rules:
                    # 1. Base position must be in profit (ROI >= +0.8%) OR stop-loss already moved to/above avg entry px (No-risk trade).
                    # 2. Maximum 1 scale-in per position to prevent overconcentration.
                    # 3. Combined margin must not exceed MAX_SINGLE_ASSET_MARGIN.
                    # 4. AI Confidence must be >= 75%.
                    # 5. Calculus Momentum & Probability Gateway: Acceleration a >= -0.25 and Continuation Prob >= 40%
                    c_dyn = f.get("calculus", {})
                    c_accel = float(c_dyn.get("acceleration", 0.0) or 0.0)
                    p_th = c_dyn.get("probability_theory", {})
                    p_cont = float(p_th.get("continuation_prob_pct", 50.0) or 50.0)
                    calculus_accel_ok = (c_accel >= -0.25 and p_cont >= 40.0)

                    allow_entry, is_scale_in = pyramiding_gate(
                        is_long=True, f=f, pos_upl=pos_upl, pos_upl_ratio=pos_upl_ratio,
                        pos_avg_px=pos_avg_px, curr_margin=curr_margin, trailing_sl=trailing_sl,
                        scale_count=scale_count, c_accel=c_accel, p_th=p_th,
                        ai_margin=ai_margin, actual_sz=actual_sz, ct_val=ct_val,
                        ai_lever=ai_lever, ai_conf=ai_conf,
                        min_scale_in_profit_ratio=MIN_SCALE_IN_PROFIT_RATIO,
                        max_scale_in_count=MAX_SCALE_IN_COUNT,
                        min_scale_in_confidence=MIN_SCALE_IN_CONFIDENCE,
                        asset_margin_cap=ASSET_MARGIN_CAP)

                if allow_entry and entries_blocked:
                    print(f"[挂单对账] fail-closed 拦截 {f['name']} 新增多单下单（本周期对账失败）")
                    allow_entry = False
                if allow_entry:
                    limit_px, tp_px, sl_px = resolve_entry_prices(
                        is_long=True, ai_decision=ai_decision, f=f, prec=prec,
                        tp_dist=tp_dist, sl_dist=sl_dist)

                    # Hard check: 做多须 sl_px < limit_px < tp_px（钳制见 scripts/trader/brackets.py）
                    sl_px, tp_px = normalize_bracket_prices(
                        is_long=True, limit_px=limit_px, tp_px=tp_px, sl_px=sl_px,
                        sl_dist=sl_dist, tp_dist=tp_dist, price=f["price"], prec=prec)

                    # US-003 决策面上下文：名义额（选所硬筛/深度需求）+ 保证金估算
                    # （预算预留额）+ 意图号（同一条 AI 决策重投幂等，不重复占预算）
                    # 审计 P0-1：多所路径保证金与 OKX 同尺（AI 计划额 ∩ 张数隐含额 ∩ 权益占比 ∩ 单标的封顶）
                    _order_margin = order_margin_gate(
                        ai_margin, size=actual_sz, price=limit_px, ct_val=ct_val,
                        leverage=ai_lever, usdt_available=usdt_available)
                    _side, _pos_side, _venue_ctx = build_order_intent(
                        is_long=True, inst_id=inst_id, actual_sz=actual_sz, ct_val=ct_val,
                        limit_px=limit_px, ai_lever=ai_lever,
                        margin_usdt=_order_margin,
                        max_margin_usdt=equity_margin_cap(usdt_available),
                        inst_lever_cap=_inst_lever_cap, ai_conf=ai_conf, ai_info=ai_info)
                    accepted, order_ref = submit_protected_limit_order(
                        inst_id, _side, _pos_side, actual_sz, limit_px, tp_px, sl_px,
                        venue_ctx=_venue_ctx)
                    if accepted:
                        if is_scale_in:
                            tracker = trackers.get(f"{inst_id}_long", {})
                            tracker["scale_count"] = tracker.get("scale_count", 0) + 1
                            save_trackers(trackers)
                            executed_actions.append(entry_action_message(
                                is_long=True, is_scale_in=True, name=f["name"], sz=actual_sz,
                                px=limit_px, order_ref=order_ref, tp_px=tp_px, sl_px=sl_px))
                            if notify_trade_open:
                                notify_trade_open(
                                    **trade_open_kwargs(
                                        is_long=True, is_scale_in=True, name=f["name"], sz=actual_sz,
                                        px=limit_px, strat_tag=strat_tag, ai_reason=ai_reason,
                                        tp_px=tp_px, sl_px=sl_px),
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                        else:
                            executed_actions.append(entry_action_message(
                                is_long=True, is_scale_in=False, name=f["name"], sz=actual_sz,
                                px=limit_px, order_ref=order_ref, tp_px=tp_px, sl_px=sl_px))
                            pending_inst_ids.add(inst_id)
                            reserved_slot_count += 1
                            reserved_long_count += 1
                            if notify_trade_open:
                                notify_trade_open(
                                    **trade_open_kwargs(
                                        is_long=True, is_scale_in=False, name=f["name"], sz=actual_sz,
                                        px=limit_px, strat_tag=strat_tag, ai_reason=ai_reason,
                                        tp_px=tp_px, sl_px=sl_px),
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                    else:
                        executed_actions.append(entry_failure_message(
                            is_long=True, name=f["name"], order_ref=order_ref))

            # Short Execution (Initial Entry or Strict Pyramiding Scale-In)
            elif action == "SELL_SHORT":
                is_scale_in = False
                allow_entry = False

                # Case A: Standard Initial Entry
                if not curr_pos and inst_id not in pending_inst_ids and reserved_slot_count < MAX_CONCURRENT_POSITIONS and reserved_short_count < MAX_SAME_DIRECTION_POSITIONS:
                    if ai_conf >= MIN_ENTRY_CONFIDENCE:
                        allow_entry = True
                    else:
                        print(f"[首发开空拦截] {f['name']} AI置信度 {ai_conf:.1f}% 未达 80% 门禁，宁缺毋滥，拦截入场")

                # Case B: Strict Pyramiding Scale-In (Existing short position in profit/breakeven)
                elif curr_pos and str(curr_pos.get("side", "")).lower() == "short" and inst_id not in pending_inst_ids:
                    pos_upl = float(curr_pos.get("upl", 0.0) or 0.0)
                    pos_upl_ratio = float(curr_pos.get("uplRatio", 0.0) or 0.0)
                    pos_avg_px = float(curr_pos.get("avgPx", 0.0) or 0.0)
                    curr_margin = float(curr_pos.get("margin", 0.0) or 0.0)
                    tracker = trackers.get(f"{inst_id}_short", {})
                    scale_count = int(tracker.get("scale_count", 0))
                    trailing_sl = float(tracker.get("trailingStopPx", 0.0) or 0.0)

                    c_dyn = f.get("calculus", {})
                    c_accel = float(c_dyn.get("acceleration", 0.0) or 0.0)
                    p_th = c_dyn.get("probability_theory", {})

                    allow_entry, is_scale_in = pyramiding_gate(
                        is_long=False, f=f, pos_upl=pos_upl, pos_upl_ratio=pos_upl_ratio,
                        pos_avg_px=pos_avg_px, curr_margin=curr_margin, trailing_sl=trailing_sl,
                        scale_count=scale_count, c_accel=c_accel, p_th=p_th,
                        ai_margin=ai_margin, actual_sz=actual_sz, ct_val=ct_val,
                        ai_lever=ai_lever, ai_conf=ai_conf,
                        min_scale_in_profit_ratio=MIN_SCALE_IN_PROFIT_RATIO,
                        max_scale_in_count=MAX_SCALE_IN_COUNT,
                        min_scale_in_confidence=MIN_SCALE_IN_CONFIDENCE,
                        asset_margin_cap=ASSET_MARGIN_CAP)

                if allow_entry and entries_blocked:
                    print(f"[挂单对账] fail-closed 拦截 {f['name']} 新增空单下单（本周期对账失败）")
                    allow_entry = False
                if allow_entry:
                    limit_px, tp_px, sl_px = resolve_entry_prices(
                        is_long=False, ai_decision=ai_decision, f=f, prec=prec,
                        tp_dist=tp_dist, sl_dist=sl_dist)

                    # Hard check: 做空须 tp_px < limit_px < sl_px（钳制见 scripts/trader/brackets.py）
                    sl_px, tp_px = normalize_bracket_prices(
                        is_long=False, limit_px=limit_px, tp_px=tp_px, sl_px=sl_px,
                        sl_dist=sl_dist, tp_dist=tp_dist, price=f["price"], prec=prec)

                    # US-003 决策面上下文：名义额（选所硬筛/深度需求）+ 保证金估算
                    # （预算预留额）+ 意图号（同一条 AI 决策重投幂等，不重复占预算）
                    # 审计 P0-1：多所路径保证金与 OKX 同尺（AI 计划额 ∩ 张数隐含额 ∩ 权益占比 ∩ 单标的封顶）
                    _order_margin = order_margin_gate(
                        ai_margin, size=actual_sz, price=limit_px, ct_val=ct_val,
                        leverage=ai_lever, usdt_available=usdt_available)
                    _side, _pos_side, _venue_ctx = build_order_intent(
                        is_long=False, inst_id=inst_id, actual_sz=actual_sz, ct_val=ct_val,
                        limit_px=limit_px, ai_lever=ai_lever,
                        margin_usdt=_order_margin,
                        max_margin_usdt=equity_margin_cap(usdt_available),
                        inst_lever_cap=_inst_lever_cap, ai_conf=ai_conf, ai_info=ai_info)
                    accepted, order_ref = submit_protected_limit_order(
                        inst_id, _side, _pos_side, actual_sz, limit_px, tp_px, sl_px,
                        venue_ctx=_venue_ctx)
                    if accepted:
                        if is_scale_in:
                            tracker = trackers.get(f"{inst_id}_short", {})
                            tracker["scale_count"] = tracker.get("scale_count", 0) + 1
                            save_trackers(trackers)
                            executed_actions.append(entry_action_message(
                                is_long=False, is_scale_in=True, name=f["name"], sz=actual_sz,
                                px=limit_px, order_ref=order_ref, tp_px=tp_px, sl_px=sl_px))
                            if notify_trade_open:
                                notify_trade_open(
                                    **trade_open_kwargs(
                                        is_long=False, is_scale_in=True, name=f["name"], sz=actual_sz,
                                        px=limit_px, strat_tag=strat_tag, ai_reason=ai_reason,
                                        tp_px=tp_px, sl_px=sl_px),
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                        else:
                            executed_actions.append(entry_action_message(
                                is_long=False, is_scale_in=False, name=f["name"], sz=actual_sz,
                                px=limit_px, order_ref=order_ref, tp_px=tp_px, sl_px=sl_px))
                            pending_inst_ids.add(inst_id)
                            reserved_slot_count += 1
                            reserved_short_count += 1
                            if notify_trade_open:
                                notify_trade_open(
                                    **trade_open_kwargs(
                                        is_long=False, is_scale_in=False, name=f["name"], sz=actual_sz,
                                        px=limit_px, strat_tag=strat_tag, ai_reason=ai_reason,
                                        tp_px=tp_px, sl_px=sl_px),
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                    else:
                        executed_actions.append(entry_failure_message(
                            is_long=False, name=f["name"], order_ref=order_ref))

    # 5. Persist Latest State for Web Monitoring Dashboard
    state_payload = build_state_payload(
        timestamp_full=timestamp_full, active_pos_count=active_pos_count,
        max_positions=MAX_CONCURRENT_POSITIONS, long_count=long_count,
        short_count=short_count, cb_active=cb_active, cb_reason=cb_reason,
        executed_actions=executed_actions, all_factors=all_factors,
        evaluate_asset_signal=evaluate_asset_signal)

    # 审计③：原子替换（读者=面板/巡检；旧直写有撕裂窗）。异常语义不变：照旧上抛。
    _atomic_write_json(os.path.join(DATA_DIR, "trading_state.json"), state_payload)

    # 6. Always Sync Full Lifecycle Ledger and SQLite DB in Realtime
    # 批E(2026-09-13)·测试封闭闸：这两条 spawn 会打三所接口并**重写生产台账/数据库**。
    # 测试若在进程内跑一轮交易员巡检（多处如此），就会连带改写 data/trading_ledger.json
    # 与 SQLite——违反「测试不触生产文件」。tests/__init__.py 在任何测试模块导入前置位
    # R20_LEDGER_SYNC_DISABLED=1，下面的模块级快照即 False；生产不设 → 行为不变。
    if LEDGER_AUTOSYNC_ENABLED:
        try:
            sync_script = os.path.join(WORKSPACE_DIR, "scripts", "sync_full_ledger.py")
            if os.path.exists(sync_script):
                _run_captured(sync_script)
            db_script = os.path.join(WORKSPACE_DIR, "scripts", "db_manager.py")
            if os.path.exists(db_script):
                _run_captured(db_script)
        except Exception as e:
            print(f"[Ledger Sync Warning] {e}")

    log_entry = f"[{timestamp_full}] ⚡ R20 Quantum Trader v{__version__} 巡检完成 | 持仓 OKX {active_pos_count}/{MAX_CONCURRENT_POSITIONS} (多{long_count}/空{short_count})｜跨所 {_xv_total if _xv_total is not None else '未知'} 笔 | 动作: {', '.join(executed_actions) if executed_actions else '无开平仓操作'}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)
    print(log_entry.strip())

if __name__ == "__main__":
    if not selected_environment().configured:
        print("[Engine NOT READY] OKX API Key 未配置（LIVE/DEMO）——退出，不执行任何交易。")
        sys.exit(3)
    execute_portfolio()
