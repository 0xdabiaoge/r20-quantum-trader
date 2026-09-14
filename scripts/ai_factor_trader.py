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
from scripts.trader.position_mgmt import (
    execute_ai_position_management as _execute_ai_position_management_impl,
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
    """审计③(2026-09-13)：返回 (data, corrupt)。损坏与缺失从此不同权——
    corrupt=True 时 is_in_stop_cooldown 按「在冷却」fail-closed（旧实现损坏→{}
    等价于「无冷却」，硬止损后可立即同向重进）；add 拒做 RMW 防覆盖现场。"""
    if not os.path.exists(STOP_COOLDOWN_FILE):
        return {}, False
    try:
        with open(STOP_COOLDOWN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}, True
        return data, False
    except Exception:
        return {}, True


def load_stop_cooldowns():
    # 兼容旧契约（只读展示面）；风控判断路径一律走 _read_stop_cooldowns_state
    return _read_stop_cooldowns_state()[0]

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
    cooldowns, corrupt = _read_stop_cooldowns_state()
    if corrupt:
        return True  # 不可判定=不放松：损坏按仍在冷却处理
    key = f"{inst_id}_{side}"
    if key in cooldowns:
        rem_sec = STOP_COOLDOWN_MINUTES * 60 - (int(time.time()) - cooldowns[key].get("ts", 0))
        if rem_sec > 0:
            return True
    return False



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
    """Cancel stale entry orders; any inability to verify/cancel blocks the trading cycle.

    审计④8(2026-09-13)·外所 GTC 回收：路由能把信号派到 gate/binance（三所平权+
    gate 费率占优即会被选中），但本回收过去只扫 OKX——外所入场限价 GTC 挂单
    永不超时撤除，孤儿逐日堆积占保证金并在深夜反抽时意外成交于无保护价。
    现对**执行闸开启**的场所同尺回收（闸关=该所不可能有本系统单，零触碰、其
    适配器故障也绝不拖累主链）；核验/撤销失败与 OKX 同标准 fail-closed 拦本周期。
    """
    keep_ord_ids = keep_ord_ids or set()
    STALE_MS = 240_000
    try:
        open_orders = okx_rest.pending_orders()
    except Exception as exc:
        return False, f"invalid open-orders response: {exc}"
    now_ts = int(time.time() * 1000)
    for order in open_orders:
        inst_id = str(order.get("instId") or "")
        order_id = str(order.get("ordId") or "")
        if order_id and order_id in keep_ord_ids:
            continue  # 挂单对账已判定归属（接管），不受超时生命周期清理影响
        state = str(order.get("state", "live")).lower()
        created_at = int(order.get("cTime", now_ts) or now_ts)
        if state not in {"live", "partially_filled"} or not order_id or now_ts - created_at <= STALE_MS:
            continue
        try:
            okx_rest.cancel_order(inst_id, order_id)
        except Exception as exc:
            return False, f"failed to cancel stale order {inst_id}/{order_id}: {exc}"
        print(f"[挂单生命周期管理] 自动撤销超时挂单: {inst_id} (ordId={order_id}, state={state})")

    try:
        _env_mode = str(current_environment().mode or "demo")
    except Exception:
        _env_mode = ""
    # 外所接管判定用活意图集（与 OKX 对账同一把尺：新鲜意图归属 → 保留）
    try:
        _live_intents = [i for i in load_open_intents()
                         if isinstance(i, dict) and now_ts - int(i.get("ts", 0) or 0) <= OPEN_INTENT_TTL_MS]
    except Exception:
        _live_intents = []

    def _intent_covers(venue_base: str, dir_word: str) -> bool:
        _tgt = f"{venue_base}-USDT-SWAP"
        _letter = "buy" if dir_word == "long" else "sell"
        return any(str(i.get("instId")) == _tgt and str(i.get("side", "")).lower() == _letter
                   for i in _live_intents)

    _AUTH_MARKERS = ("INVALID_KEY", "Invalid key", "Invalid API-key", "-2015", "50111",
                     "signature", "Signature", "not exist", "invalid timestamp")
    for _v in ("gate", "binance"):
        _ad = None
        _rows: List[Dict[str, Any]] = []
        try:
            if not (_env_mode and venue_registry.execution_open(_v, _env_mode)):
                continue
            _ad = venue_registry.get_adapter(_v, environment=_env_mode)
            if _v == "binance":
                _rows = _ad.open_orders() or []          # 全合约在途普通单
            else:
                try:
                    _pool = load_instruments()
                except Exception:
                    _pool = []
                for _ins in _pool:                        # Gate 列表端点按合约，逐标的扫
                    _base = str(_ins.get("instId") or "").split("-")[0].upper()
                    if not _base:
                        continue
                    _rows.extend(_ad.list_open_orders(_base) or [])
        except Exception as exc:
            _msg = str(exc)
            if any(m in _msg for m in _AUTH_MARKERS):
                # 执行闸开着但凭证已死：该所**不可能再收到我们的新单**（router 同样
                # 发不出去）→ 跳过回收不拦轮（审计#4教训：拿凭证错误拦全链=交易停摆）。
                _BROKEN_VENUES.add(_v)   # 本轮路由同步摘除其执行资格（见 venue_execution_ready）
                print(f"[挂单生命周期] CRITICAL {_v.upper()} 凭证无效但执行闸开启——本所生命周期"
                      f"管理跳过；请修复密钥或关闭 R20_{_v.upper()}_EXECUTION")
                continue
            # 其余不可核验（网络/未知）：与 OKX 同尺 fail-closed 拦本轮
            return False, f"{_v} 挂单回收不可用: {type(exc).__name__}: {_msg[:120]}"
        # 归一 (base, dir) → 按创建时间**只保最新**一条为候选存活单，其余降级为重复单；
        # 存活候选再按新鲜意图归属决定保留/超时撤销（修复：外所单此前既无人回收也无
        # 接管语义，每轮重挂造成 BTC/SUI 成对重复）。
        best: Dict[tuple, tuple] = {}
        dupes: List[tuple] = []
        for o in _rows:
            if not isinstance(o, dict):
                continue
            _raw = o.get("raw") if isinstance(o.get("raw"), dict) else {}
            order_id = str(o.get("order_id") or o.get("id") or _raw.get("id") or "")
            if not order_id or order_id in keep_ord_ids:
                continue
            _side = str(o.get("side") or _raw.get("side") or "").lower()
            _ro = o.get("reduce_only") if o.get("reduce_only") is not None else _raw.get("reduce_only")
            if _ro in (True, "true", "1"):
                continue          # 减仓/保护族不属入场生命周期管辖
            if _v == "binance":
                inst_disp = str(o.get("inst_id") or _raw.get("symbol") or "")
                created_ms = int(float(_raw.get("time") or _raw.get("updateTime") or now_ts))
            else:
                inst_disp = str(o.get("contract") or _raw.get("contract") or "")
                created_ms = int(float(o.get("create_time") or _raw.get("create_time") or (now_ts / 1000)) * 1000)
            _b = str(o.get("base") or "").upper() or inst_disp.split("_")[0].split("-")[0].upper()
            if not _b or _side not in ("buy", "sell"):
                continue
            entry = (created_ms, order_id, inst_disp)
            key = (_b, "long" if _side == "buy" else "short")
            if key in best and best[key][0] >= created_ms:
                dupes.append(entry)
            else:
                if key in best:
                    dupes.append(best[key])
                best[key] = entry
        for created_ms, order_id, inst_disp in dupes:
            if now_ts - created_ms <= STALE_MS:
                continue  # 宽限期内不动手
            _b0 = inst_disp.replace("_USDT", "").replace("USDT", "").split("-")[0].upper()
            try:
                _ad.cancel_order(_b0, order_id)
                print(f"[挂单生命周期管理] 同向重复单收敛撤销({_v.upper()}): {inst_disp} (id={order_id})")
            except Exception as exc:
                return False, f"failed to cancel duplicate order {_v} {inst_disp}/{order_id}: {exc}"
        for (venue_base, dir_word), (created_ms, order_id, inst_disp) in best.items():
            if now_ts - created_ms <= STALE_MS:
                continue
            if _intent_covers(venue_base, dir_word):
                continue  # 新鲜意图归属 → 保留（与 OKX kept 同语义）
            try:
                _ad.cancel_order(venue_base, order_id)
                print(f"[挂单生命周期管理] 自动撤销超时挂单({_v.upper()}): {inst_disp} (id={order_id})")
            except Exception as exc:
                return False, f"failed to cancel stale order {_v} {inst_disp}/{order_id}: {exc}"
    return True, "open orders verified"


# =============================================================================
# US-006 重启接管存量挂单——周期级挂单对账
# =============================================================================
OPEN_INTENT_FILE = os.path.join(DATA_DIR, "open_order_intents.json")
OPEN_INTENT_TTL_MS = 6 * 3600 * 1000  # 本地开仓意图有效期；超期 → 周期意图已失效

RECONCILE_REASON_ORPHAN = "无对应意图"
RECONCILE_REASON_SIDE_MISMATCH = "方向不一致"
RECONCILE_REASON_INTENT_STALE = "周期意图已失效"


def record_open_intent(inst_id: str, side: str, ts_ms: int = None) -> None:
    """下单成功后记录本地开仓意图，供重启后挂单对账归属（US-006）。

    审计(2026-09-13)·PEPE 永动机修复之二：写入时**清理**——过期(TTL 6h)条目丢弃、
    同标的同方向只保留最新一条。旧实现只 append（上限 200 条 FIFO），意图文件里
    永远躺着全天最老的一条，配合对账端 next() 取最老匹配 = 每轮误撤自己刚挂的单。"""
    try:
        intents = []
        if os.path.exists(OPEN_INTENT_FILE):
            try:
                with open(OPEN_INTENT_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    intents = raw
            except (ValueError, OSError):
                intents = []  # 空文件/损坏文件：从空重建，不影响本单交易
        _now_ms = int(time.time() * 1000)
        intents = [i for i in intents
                   if isinstance(i, dict) and _now_ms - int(i.get("ts", 0) or 0) <= OPEN_INTENT_TTL_MS]
        _side_l = str(side).lower()
        intents = [i for i in intents
                   if not (str(i.get("instId")) == inst_id and str(i.get("side", "")).lower() == _side_l)]
        intents.append({"instId": inst_id, "side": side, "ts": int(ts_ms or _now_ms)})
        with open(OPEN_INTENT_FILE, "w", encoding="utf-8") as f:
            json.dump(intents[-200:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[挂单对账] 记录开仓意图失败（不影响本单交易）: {e}")


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
    """周期开始（新增下单前）对本账户 USDT-SWAP 存量限价挂单做归属对账（US-006）。

    语义：
    - 持仓追踪器归属（同合约同方向）→ 接管保留；
    - 本地开仓意图（决策历史）同合约同方向且未过期 → 接管保留；
    - 同合约方向不一致 → 撤销（原因=方向不一致）；
    - 意图存在但超过 TTL → 撤销（原因=周期意图已失效）；
    - 无任何本地意图可归属 → 撤销（原因=无对应意图）。

    返回 (ok, kept_ord_ids)。ok=False 表示对账自身失败（读取/撤销网络或签名异常）
    → 调用方必须 fail-closed：本周期禁止新增下单（不是清库）。
    """
    now_ms = int(now_ms or time.time() * 1000)
    if pending is None:
        try:
            # GET /api/v5/trade/orders-pending（instType=SWAP，冻结周期环境直签）
            pending = okx_rest.pending_orders()
        except Exception as exc:
            print(f"[挂单对账] warn 读取存量挂单失败: {exc} → fail-closed，本周期禁止新增下单")
            return False, set()
    if not isinstance(pending, list):
        print("[挂单对账] warn 存量挂单响应非列表 → fail-closed，本周期禁止新增下单")
        return False, set()
    if trackers is None:
        trackers = load_trackers()
    intents = load_open_intents()
    kept: set = set()

    def _cancel_orphan(reason: str) -> bool:
        try:
            okx_rest.cancel_order(inst_id, ord_id)
        except Exception as exc:
            print(f"[挂单对账] warn 撤销失败 instId={inst_id} ordId={ord_id}: {exc} → fail-closed，本周期禁止新增下单")
            return False
        print(f"[挂单对账] 撤销孤儿单 instId={inst_id} ordId={ord_id} side={side} 原因={reason}")
        return True

    for order in pending:
        if not isinstance(order, dict):
            continue
        inst_id = str(order.get("instId") or "")
        ord_id = str(order.get("ordId") or "")
        side = str(order.get("side") or "").lower()
        state = str(order.get("state", "live")).lower()
        if state not in {"live", "partially_filled"} or not inst_id:
            continue
        pos_side = _order_pos_side(side)
        tracker_key = f"{inst_id}_{pos_side}"
        # 1) 持仓追踪器归属：同合约同方向 → 重启后接管保留
        if tracker_key in (trackers or {}):
            print(f"[挂单对账] 接管挂单 instId={inst_id} ordId={ord_id} side={side} 原因=追踪器归属")
            kept.add(ord_id)
            continue
        # 2) 本地开仓意图（决策历史）归属。
        #    审计(2026-09-13)·PEPE 永动机修复之一：旧 `next(...)` 取**最老**匹配意图——
        #    当日该标的第一笔意图越过 TTL 后，之后每一轮的新挂单都被误判「周期意图已
        #    失效」撤销、再被下一轮重新提交（撤旧挂新无限循环，实测 PEPE 10:45~15:15
        #    六连撤）。现按同标的**最新**意图判归属。
        _same_inst = [i for i in intents if str(i.get("instId")) == inst_id]
        intent = max(_same_inst, key=lambda i: int(i.get("ts", 0) or 0), default=None)
        if intent is not None:
            if str(intent.get("side", "")).lower() != side:
                if not _cancel_orphan(RECONCILE_REASON_SIDE_MISMATCH):
                    return False, kept
                continue
            if now_ms - int(intent.get("ts", 0) or 0) > OPEN_INTENT_TTL_MS:
                if not _cancel_orphan(RECONCILE_REASON_INTENT_STALE):
                    return False, kept
                continue
            print(f"[挂单对账] 接管挂单 instId={inst_id} ordId={ord_id} side={side} 原因=意图归属")
            kept.add(ord_id)
            continue
        # 3) 孤儿单：无任何本地意图可归属
        if not _cancel_orphan(RECONCILE_REASON_ORPHAN):
            return False, kept
    return True, kept

def check_black_swan_sentinel() -> Tuple[bool, str]:
    """Minute-level Black Swan Sentinel, driven by the unified V5 REST public
    market feed (market_data_service www→aws dual-domain + alt-venue fallback, 零凭证可读).

    US-014 前置收尾（归因：3137c40/09fba6f 将 smartmoney/news CLI 信号面缺失化后，
    新闻模式熔断随之休眠）：黑天鹅熔断改由此公共行情路径**复活**，并按
    「不可判定=不放松」的 fail-closed 语义兜底——行情取不到/样本不足时触发熔断，
    绝不带着盲区继续开新仓。新闻情绪层只消费**可判定**的极端值：旧实现以缺省
    overall_score=50 冒充中性「一切正常」，已删除该假中性值——文件缺失/无该字段
    一律视为不可判定，仅当数值 ≤20 才触发熔断。"""
    # 1. BTC 15M candles extreme plunge (> 3.0% in 15 mins) via unified public REST.
    try:
        candles = fetch_candles_direct("BTC-USDT-SWAP", "15m", 3)
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
        # 行情形态不可判定同样不得放宽风控
        return True, "🚨 黑天鹅熔断：行情数据格式异常不可判定，不可判定=不放松，保守暂停新开仓"

    # 2. News sentiment file：仅认显式极端值（≤20），缺失≠中性50≠放行。
    if os.path.exists(NEWS_SENTIMENT_FILE):
        try:
            with open(NEWS_SENTIMENT_FILE, "r", encoding="utf-8") as f:
                n_data = json.load(f)
            raw_score = n_data.get("overall_score")
            if raw_score is not None:
                score = float(raw_score)
                if score <= 20.0:
                    return True, f"🚨 监测到突发黑天鹅极度恶性利空舆情 (情绪指数: {score:.1f})，触发全网黑天鹅紧急熔断！"
        except Exception:
            # 情绪文件损坏同样不可判定：不因读不到而放行（与下方熔断状态文件
            # 损坏→安全暂停 的既有语义一致）
            return True, "🚨 黑天鹅熔断：新闻情绪缓存损坏不可判定，不可判定=不放松，保守暂停新开仓"

    return False, ""

def is_circuit_breaker_active(usdt_available: float = None):
    # 1. Black Swan Sentinel Check
    bs_active, bs_reason = check_black_swan_sentinel()
    if bs_active:
        return True, bs_reason

    # 2. File-based Circuit Breaker Check (shared schema with news harvester)
    if os.path.exists(CIRCUIT_BREAKER_FILE):
        try:
            with open(CIRCUIT_BREAKER_FILE, "r", encoding="utf-8") as f:
                cb = json.load(f)
            expires_at = float(cb.get("expires_at_ts", 0) or 0)
            active = bool(cb.get("active")) or cb.get("status") == "triggered"
            if active and (expires_at <= 0 or time.time() < expires_at):
                return True, cb.get("reason") or cb.get("headline") or "黑天鹅极端行情熔断中"
        except Exception as e:
            return True, f"熔断状态文件损坏，安全暂停开仓: {e}"

    # 3. Daily Max Loss Limit Check from lifecycle ledger using Beijing close_time.
    if os.path.exists(LEDGER_JSON_FILE):
        # 审计回马枪④2(2026-09-13)：上轮 A2 的「同步失败所→禁开仓」加固只进了
        # r20_backend.execution.circuit_breaker 模块版，而活路径走本函数（孪生漂移），
        # 等于闸装了死副本。现从模块导入同一实现，双进程单一事实源。
        try:
            from r20_backend.execution.circuit_breaker import (
                _ledger_sync_failed_venues, ledger_daily_closed_pnl)
            _failed_venues = _ledger_sync_failed_venues()
            if _failed_venues:
                return True, ("台账跨所同步不完整（失败所: " + ",".join(_failed_venues) +
                              "），当日亏损求和不可判全，安全暂停开仓")
        except Exception as e:
            return True, f"台账同步旁车检查不可用，安全暂停开仓: {e}"
        try:
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            tz_bj = datetime.timezone(datetime.timedelta(hours=8))
            today_str = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d")
            # 审计④1：求和必须按 current_environment().mode 过滤环境（demo↔live 切换日
            # 两环境盈亏互抵可致熔断假阴性），规则与模块版 ledger_daily_closed_pnl 同源。
            try:
                _mode = str(current_environment().mode or "")
            except Exception:
                _mode = ""  # 环境不可判 → 保守全计（宁停不漏）
            today_pnl = ledger_daily_closed_pnl(ledger, _mode, today_str)
            _loss_cap = effective_daily_loss_limit(usdt_available)
            if today_pnl < -_loss_cap:
                return True, f"今日累计回撤 ({today_pnl:.2f}U) 触及单日最大风控熔断限额 ({_loss_cap}U｜按可用余额自适应)"
        except Exception as e:
            return True, f"日亏损风控数据读取失败，安全暂停开仓: {e}"

    return False, ""

def query_positions() -> Tuple[bool, List[Dict[str, Any]], str]:
    """Distinguish an exchange-confirmed empty account from a failed query."""
    try:
        rows = okx_rest.positions()
    except Exception as exc:
        return False, [], f"invalid positions response: {exc}"
    return True, rows, ""


def close_position_confirmed(inst_id: str, pos_side: str, before_size: float, venue: str = "okx") -> Tuple[bool, str]:
    """Close a position and verify at the exchange before changing local state (Three-Venue Capable)."""
    target_venue = str(venue or "okx").lower()
    if target_venue != "okx":
        try:
            from r20_backend import execution_router
            # 审计 C2：周期内冻结环境（okx_rest 按 current_environment 签名，读
            # selected 会在 demo↔live 中途切换时产生跨环境混合决策）
            env = current_environment()
            res = execution_router.close_position(inst_id, venue=target_venue, environment=str(env.mode), pos_side=pos_side)
            if not res.get("ok"):
                return False, f"{target_venue.upper()} close failed: {res.get('detail')}"
            # 审计 B1：受理≠平掉——与 OKX 分支同一把尺做归零回读，核验通过前
            # 禁改本地状态（tracker 保留、下周期重试；假成功会让孤儿仓脱管）
            want_base = str(inst_id).split("-")[0].upper()
            want_side = str(pos_side or "").strip().lower()
            saw_successful_query = False
            for _ in range(6):
                time.sleep(0.6)
                xv_ok, xv_snap, _xv_err = fetch_other_venue_positions(str(env.mode))
                if not xv_ok:
                    continue
                saw_successful_query = True
                remaining = 0.0
                for row in (xv_snap.get(target_venue) or []):
                    base = str(row.get("base") or "").upper()
                    if base != want_base:
                        continue
                    row_side = "long" if float(row.get("size_signed") or 0) > 0 else "short"
                    if want_side in ("long", "short") and row_side != want_side:
                        continue
                    remaining = max(remaining, abs(float(row.get("size_signed") or 0)))
                if remaining < max(1e-12, abs(float(before_size)) * 0.001):
                    return True, f"{target_venue.upper()} position closed (verified flat)"
            if not saw_successful_query:
                return False, f"{target_venue.upper()} close accepted but readback unavailable; state unchanged"
            return False, f"{target_venue.upper()} still reports open position after close (before={before_size}); state unchanged"
        except Exception as exc:
            return False, f"{target_venue.upper()} close error: {exc}"

    # Pre-cancel any conflicting pending/reduce-only orders for this instrument to release available size
    try:
        for o in okx_rest.pending_orders(inst_id):
            o_side = str(o.get("posSide", "net")).lower()
            if o_side in (pos_side.lower(), "net"):
                o_id = str(o.get("ordId") or "")
                if o_id:
                    okx_rest.cancel_order(inst_id, o_id)
    except Exception as e:
        print(f"[Close Pre-Clean] Warning cancelling pending orders for {inst_id}: {e}")

    try:
        okx_rest.close_position(inst_id, pos_side, td_mode="cross", auto_cxl=True)
    except Exception as exc:
        return False, f"close command failed: {exc}"

    saw_successful_query = False
    for _ in range(6):
        time.sleep(0.6)
        query_ok, positions, query_error = query_positions()
        if not query_ok:
            continue
        saw_successful_query = True
        remaining = 0.0
        for position in positions:
            if position.get("instId") == inst_id and str(position.get("posSide", "net")).lower() == pos_side:
                remaining = abs(float(position.get("pos", 0) or 0))
                break
        if remaining < max(1e-12, abs(before_size) * 0.001):
            return True, "exchange position closed"
    if not saw_successful_query:
        return False, "position verification failed: no successful exchange response"
    return False, f"exchange still reports an open position after close request (before={before_size})"


def amend_venue_stop_loss(ad, symbol: str, pos_side: str, new_sl: float,
                          contracts: float) -> Tuple[bool, str]:
    """审计 C3（后半）：跨所云端 SL 棘轮——旧实现每轮只 attach 新单、不撤不改旧单，
    云端止损随棘轮轮次堆积（宽松旧单可能先于新单触发/占额度）。
    策略：先枚举现存 SL 触发单（Gate 腿带 text=t-r20sl* 标签、Binance 腿 type 含
    STOP）；有旧单且该所支持 amend_stop_loss → 原生改单（同单改触发价，天然无裸仓
    缝隙），残余旧单一律撤掉；否则安全序列：先挂新 SL（收紧即刻生效、更新无裸仓
    窗口）→ 再撤全部旧 SL。旧单撤失败只 warn——新单已生效，旧 reduce_only 双单
    竞发时后触发者无仓自动无效，绝不回滚收紧（宁可双、不可裸）。"""
    old_ids: List[str] = []
    list_error = ""
    try:
        for row in (ad.list_protective_orders(symbol) or []):
            if not isinstance(row, dict):
                continue
            _order = row.get("order")
            text = (str(_order.get("text") or "") if isinstance(_order, dict) else "") \
                + str(row.get("text") or "") + str(row.get("type") or "")
            rid = str(row.get("id") or row.get("algo_id") or row.get("order_id") or "")
            if rid and ("r20sl" in text.lower() or "STOP" in text.upper()):
                old_ids.append(rid)
    except Exception as exc:
        list_error = str(exc)[:160]

    def _cancel(oid: str):
        if hasattr(ad, "cancel_price_order"):
            ad.cancel_price_order(oid)
        elif hasattr(ad, "cancel_algo_order"):
            ad.cancel_algo_order(algo_id=oid)
        else:
            ad.cancel_order(symbol, oid)

    if old_ids and hasattr(ad, "amend_stop_loss"):
        try:
            eff = ad.amend_stop_loss(symbol, pos_side, old_ids[0], float(new_sl))
            for _oid in old_ids[1:]:
                if str(_oid) != str(eff):
                    try:
                        _cancel(_oid)
                    except Exception as exc:
                        print(f"[SL-Ratchet] warn {symbol} 清理残余旧SL失败 {_oid}: {exc}")
            return True, f"原生改单生效（{old_ids[0]}→{eff}），旧单 {len(old_ids)} 笔已处理"
        except Exception as exc:
            print(f"[SL-Ratchet] {symbol} amend 不可用（{str(exc)[:120]}），回退先挂新再撤旧")

    placed = ad.attach_protective_orders(symbol, pos_side, sl_px=float(new_sl), contracts=contracts)
    new_id = str((placed or {}).get("sl") or "")
    cancelled = 0
    for _oid in old_ids:
        if _oid == new_id:
            continue
        try:
            _cancel(_oid)
            cancelled += 1
        except Exception as exc:
            print(f"[SL-Ratchet] warn {symbol} 撤旧SL失败 {_oid}: {exc}")
    note = f"先挂新再撤旧（新单 {new_id or '?'}，撤旧 {cancelled}/{len(old_ids)}）"
    if list_error:
        note += f" [旧单未能枚举: {list_error}]"
    return True, note


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
    try:
        return max(0.0, float(os.getenv(PORTFOLIO_RISK_BUDGET_ENV, "") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def load_preferred_venue() -> str:
    """手动选所优先项（data/venue_routing.json 顶层 preferred_venue）。

    单一事实源在 r20_backend.exchanges.routing_policy：缺字段/非法值由其回退
    'auto' 并打 warn。此处只做模块绑定转发，方便接线级测试一键切档。
    """
    return routing_policy.load_preferred_venue()


def load_routing_mode() -> str:
    """选所路由模式（auto=最优执行B | balanced=均衡轮换A | split=资金拆分C）。

    模块绑定转发（同 load_preferred_venue 钉法）：测试 patch 本函数即可完全
    封闭，绝不在用读真实 data/venue_routing.json 的情况下跑路由断言。
    """
    return routing_policy.load_routing_mode()


def venue_execution_ready(venue: str, environment: str) -> bool:
    """该所在该资金环境下能否真实下单——一律读 registry/能力表，不写死场所名单。

    - OKX：实盘/模拟盘执行走本 trader 的 V5 直签链路（不经适配器），就绪条件 =
      当前冻结环境凭证齐备且档位一致；
    - binance/gate：能力表 adapter_execution_flag AND 环境双轴开闸旗标
      （registry.execution_open 单源判定）——开闸即自动成为真候选，无需改这里。
    """
    key = str(venue or "").strip().lower()
    try:
        if not venue_registry.is_registered(key):
            return False
        if key == "okx":
            env = current_environment()
            return bool(env.configured) and str(env.mode) == str(environment)
        # 审计(2026-09-13)·坏键所自动摘除：execution_open 只看旗标——gate 旗开着
        # 但密钥已死时仍会以最低费率赢下评分，信号派过去死在下单阶段白白烧掉
        # （且外所回收侧只能吼 CRITICAL 跳过）。回收枚举在周期开头已实测凭证生死，
        # 认证类失败当场记入 _BROKEN_VENUES（进程级=每轮重探，密钥修好自动恢复），
        # 此处一并否决，让路由把单留给真实可执行的场。
        if key in _BROKEN_VENUES:
            return False
        return bool(venue_registry.execution_open(key, environment))
    except Exception as exc:
        print(f"[选所路由] warn 场所 {key} 能力表读取失败，按不可执行处理: {exc}")
        return False


def fetch_other_venue_positions(environment: str) -> Tuple[bool, Dict[str, List[Dict[str, Any]]], str]:
    """跨所持仓快照（多所封顶用）：非 OKX 且已开闸场所的活跃持仓。

    三所平权开单后，仓位/同向上限必须把 Gate/Binance 的在管仓位算进来——
    否则每所各顶满上限，全系统实际敞口 = 上限 × 场所数（风控口径失真）。

    语义（fail-closed）：
    - 返回 (ok, {venue: [normalized_pos...]}, error)。任一开闸所读取失败 →
      ok=False，调用方本周期禁止新增开仓（宁可不计数错杀，不可漏计超卖）；
    - 未开闸所不参与读取也不构成失败（结构性无仓位来源）；
    - 孤儿持仓纪律：本函数**只计数不处置**——外所来源不明的仓可能是用户
      手动仓位，绝不清算，仅 warn 提示并占用额度；
    - 每所单次读取，异常捕获后连同场所名返回，不静默吞。
    """
    snapshot: Dict[str, List[Dict[str, Any]]] = {}
    try:
        names = list(venue_registry.registered_venues())
    except Exception as exc:
        return False, {}, f"registry 场所清单不可用: {exc}"
    for name in names:
        if name == "okx":
            continue
        if not venue_execution_ready(name, environment):
            continue
        try:
            # 审计 C3：档位轴必须经 ADAPTER_ENV 唯一映射（execution_router/manual
            # close 同源）——无档 get_adapter 走 legacy 布尔→未钉死域，generic LIVE
            # 键被打进错误沙盒域正是「跨所封顶每周期 INVALID_KEY 禁开仓」的根因。
            from r20_backend.close_intent import adapter_environment as _adapter_env
            ad = venue_registry.get_adapter(name, environment=_adapter_env(name, environment or ""))
            rows = ad.positions() or []
            live = [p for p in rows if abs(float(p.get("size_signed") or 0)) > 1e-12]
            snapshot[name] = live
            # 审计(2026-09-13)：快照函数被主周期/关闭回读/对账 fallback 多点复用，
            # 逐仓打印移交给唯一语义拥有者——主周期 1a 封顶块（此处静默=日志不再成倍）。
        except Exception as exc:
            return False, {}, f"{name} 持仓读取失败: {exc}"
    return True, snapshot, ""


def _venue_health_stamp() -> Tuple[Optional[str], Dict[str, Any]]:
    """venue_health.json → (UTC ISO 观测时刻 | None, venues 观测表)。

    缺文件/坏文件 → (None, {})：跨所观测不存在，绝不编造新鲜度。
    """
    try:
        with open(VENUE_HEALTH_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle) or {}
        venues = raw.get("venues") if isinstance(raw.get("venues"), dict) else {}
        stamp = str(raw.get("updated_utc") or "").strip()
        if stamp:
            # 文件里是 "YYYY-MM-DD HH:MM:SS" 的 UTC 时刻，补 T/Z 供路由按 UTC 解析
            stamp = stamp.replace(" ", "T")
            if not stamp.endswith("Z"):
                stamp += "Z"
            return stamp, venues
    except Exception:
        pass
    return None, {}


def build_venue_candidates(inst_id: str, environment: str) -> List[Dict[str, Any]]:
    """路由候选集 = registry 全部已登记场所（okx 真候选 + binance/gate 占位）。

    场所清单与 executable 全部来自能力表，不硬编码；价差/深度/资金费的成本观测
    输入在跨所证据二期（US-004+）接入前先给 0（评分中性），不猜数。
    """
    observed_stamp, venues = _venue_health_stamp()
    live_stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cands: List[Dict[str, Any]] = []
    try:
        names = list(venue_registry.registered_venues())
    except Exception as exc:
        print(f"[选所路由] warn registry 场所清单不可用，回退 OKX 单候选: {exc}")
        names = ["okx"]
    for name in names:
        observed = venues.get(name) if isinstance(venues.get(name), dict) else {}
        latency = [float(v) for v in (observed.get("latency_ms") or {}).values()
                   if isinstance(v, (int, float))]
        avg_latency = sum(latency) / len(latency) if latency else 0.0
        pref = load_preferred_venue()
        if name == "okx" or (pref != "auto" and name == pref and venue_execution_ready(name, environment)):
            # OKX 由巡检周期直连取数；手选锁定所（如锁定币安且就绪）享有同等现时新鲜度，
            # 不受跨所观测文件暂态老化影响（三所对等平权）。
            stamp = live_stamp
        elif observed:
            stamp = observed_stamp
        else:
            stamp = None  # 该所无跨所观测记录：诚实交新鲜度闸门判定
        # 费率平权与返佣优势：Gate 80% 返佣 Maker 净成本约 0.0001 (2.0bps 双腿)；OKX/Binance 约 0.0002 (4.0bps 双腿)
        eff_fee = (MAKER_FEE_RATE * 0.5) if name == "gate" else MAKER_FEE_RATE
        # 延迟稳定性惩罚：300ms 以内正常网络零惩罚，超出部分温和计入（上限 5bps）
        eff_stab = max(0.0, min(5.0, (avg_latency - 300.0) / 100.0)) if avg_latency > 0 else 0.0

        cands.append({
            "venue": name,
            "environment": environment,
            "executable": venue_execution_ready(name, environment),
            "fee_rate": eff_fee,
            "spread_bps": 0.0,
            "depth_usd": 0.0,
            "funding_rate": 0.0,
            "stability_penalty": eff_stab,
            "min_notional": 0.0,
            "min_qty": 0.0,
            "precision": 0.0,
            "health_updated_utc": stamp,
            "health_max_age_s": VENUE_HEALTH_MAX_AGE_S,
            "price": 0.0,
            # OKX 是本链路现任所（存量持仓与历史成交都在 OKX）
            "current_venue": name == "okx",
        })
    return cands


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
    """保证金估算：优先执行层算好的真实保证金，缺失时按 3x 保守折算。"""
    if margin_usdt and float(margin_usdt) > 0:
        return round(float(margin_usdt), 4)
    notional = max(0.0, float(notional_usdt or 0.0))
    return round(notional / 3.0, 4)


def _decision_payload(decision, preferred: str) -> Dict[str, Any]:
    """RouteDecision → 决策 JSON 的 venue_decision 段（纯附加字段）。"""
    return {
        "preferred_venue": preferred,
        "venue": decision.venue,
        "reason_code": decision.reason_code,
        "reasons": list(decision.reasons or []),
        "rejected": [dict(r) for r in (decision.rejected or [])],
        "hysteresis_applied": bool(decision.hysteresis_applied),
        "allocation": decision.allocation,
        "decided_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def persist_venue_decision(inst_id: str, venue_decision: Dict[str, Any]) -> bool:
    """把选所证据并进决策缓存（data/ai_brain_decisions.json）对应标的条目。

    只追加 `venue_decision` 键，既有字段逐键保留（老 reader 无感）；主脑缓存是
    证据的落盘位置，写回沿用原子替换语义。缓存里没有该标的条目时**不伪造**决策
    ——直接跳过并 warn（没有主脑决策就没有可附着的决策 JSON）。
    """
    try:
        # 审计③(2026-09-13)：本函数与主脑（ai_brain_trader 整档覆盖写）是同一文件的
        # 两路常驻写者——每次写虽原子，但 读→merge→写 之间可被对方插队（lost update，
        # 证据回退/整轮决策被旧副本覆盖）。RMW 外包 flock 互斥（同 evolution_shield 路数）。
        from r20_backend.file_locks import file_lock
        with file_lock(AI_DECISION_CACHE_FILE):
            with open(AI_DECISION_CACHE_FILE, "r", encoding="utf-8") as handle:
                cache = json.load(handle)
            if not isinstance(cache, dict) or not isinstance(cache.get(inst_id), dict):
                print(f"[选所证据] warn {inst_id} 不在决策缓存中，本轮证据不落盘")
                return False
            cache[inst_id]["venue_decision"] = venue_decision
            fd, tmp_path = tempfile.mkstemp(prefix=".venue-decision-", suffix=".tmp",
                                            dir=os.path.dirname(AI_DECISION_CACHE_FILE))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(cache, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, AI_DECISION_CACHE_FILE)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        return True
    except Exception as exc:
        print(f"[选所证据] warn 落盘失败（不影响本轮交易）: {exc}")
        return False


def _rejection_focus_reason(decision, candidates: List[Dict[str, Any]],
                            preferred: str) -> str:
    """ALL_REJECTED 时挑「最该解释本次跳过」的那条淘汰理由。

    优先级：手选场所 > 现任所（本链路直签所）> 首个候选 > 第一条记录；同一场所若
    有多阶段淘汰，取非 executable 的第一条（listing/precision/freshness 才是真因，
    未开闸只是结构性事实）。
    """
    wanted = [preferred] if preferred != "auto" else []
    wanted += [str(c.get("venue")) for c in candidates if c.get("current_venue")]
    wanted += [str(c.get("venue")) for c in candidates]
    rows = list(decision.rejected or [])
    for venue in wanted:
        same = [r for r in rows if str(r.get("venue")) == venue]
        if not same:
            continue
        substantive = [r for r in same if r.get("stage") != "executable"]
        return str((substantive or same)[0].get("reason") or "")
    return str((rows[0] if rows else {}).get("reason") or "无候选所")


def route_and_reserve_signal(inst_id: str, side: str, size: float, price: float,
                             notional_usdt: float = 0.0, margin_usdt: float = 0.0,
                             intent_id: str = "") -> Dict[str, Any]:
    """选所路由 → 执行面接线校验 → 预算原子预留（US-003 决策面前置闸）。

    返回 {"ok": bool, "error": str|None, "venue": str|None, "decision": dict,
          "reservation": dict|None}；任何一步不过 → ok=False，调用方本轮不下单。
    """
    env = current_environment()
    environment = str(env.mode)
    preferred = load_preferred_venue()
    notional = float(notional_usdt or 0.0) or max(0.0, float(size) * float(price))
    margin_est = estimate_margin_usdt(notional, margin_usdt)
    signal = {
        "inst_id": inst_id,
        "symbol_canonical": str(inst_id).split("-")[0].upper(),
        "side": "long" if str(side).lower() in ("buy", "long") else "short",
        "size_usdt": notional,
        "price": float(price or 0.0),
    }
    candidates = build_venue_candidates(inst_id, environment)

    if preferred != "auto":
        # 手动选所优先：只让该所参与评估（直取该所），但**仍过 route_signal**，
        # 以便 executable/listing 的 rejected 证据照常落盘（可解释不因为手选而失效）。
        candidates = [c for c in candidates if str(c.get("venue")) == preferred]
        if not candidates:
            print(f"[选所路由] warn 手选场所 {preferred} 未在 registry 登记，按不可执行候选处理")
            candidates = [{
                "venue": preferred,
                "environment": environment,
                "executable": False,
                "health_updated_utc": None,
                "current_venue": False,
            }]

    budget_total = portfolio_risk_budget_usdt()
    try:
        mgr = reservation_manager()
        budget_used = mgr.gross_exposure(environment) if budget_total > 0 else 0.0
    except Exception as exc:
        mgr = None
        budget_used = 0.0
        print(f"[预算预留] warn 预留层不可用，本轮不下单（fail-closed）: {exc}")

    # 预算硬筛**不在路由层重复执行**：路由只负责选所，预算占用由 risk_reservation
    # 的原子 reserve 单点裁决（口径=保证金，与 notional 混用会双重误杀）。路由层的
    # budget_view 预筛等 US-004 名义额口径统一后再启用，这里显式传 None。
    r_mode = load_routing_mode()
    cfg = venue_router.RouterConfig(
        routing_mode=r_mode,
        # 模式 C：生成跨所拆单方案进决策证据；执行面按现任中选所单笔落地，
        # 逐片真实分发等 US-004 名义额口径统一（allocation 已随证据落盘）
        split_enabled=(r_mode == "split"))
    decision = venue_router.route_signal(signal, candidates, budget_view=None, config=cfg)
    payload = _decision_payload(decision, preferred)

    if decision.venue is None or decision.reason_code in ("ALL_REJECTED", "NO_CANDIDATES"):
        reason = _rejection_focus_reason(decision, candidates, preferred)
        payload["outcome"] = "rejected"
        payload["skip_reason"] = f"{decision.reason_code}: {reason}"
        persist_venue_decision(inst_id, payload)
        print(f"[选所路由] 本轮不下单 {inst_id}: {decision.reason_code} → {reason}")
        return {"ok": False, "error": f"路由拒绝: {reason}",
                "venue": None, "decision": payload, "reservation": None}

    venue = str(decision.venue)
    payload["outcome"] = "selected"
    if venue not in VENUE_SUBMITTERS:
        # 路由可选中未来所，但下单实现只在登记后存在——fail-closed 不硬打 OKX 端点
        reason = f"{venue} 未登记下单实现（VENUE_SUBMITTERS 只有 {sorted(VENUE_SUBMITTERS)}）"
        payload["executed_venue"] = None
        payload["skip_reason"] = reason
        persist_venue_decision(inst_id, payload)
        print(f"[选所路由] 本轮不下单 {inst_id}: {reason}")
        return {"ok": False, "error": f"路由拒绝: {reason}",
                "venue": venue, "decision": payload, "reservation": None}

    if mgr is None:
        persist_venue_decision(inst_id, payload)
        return {"ok": False, "error": "预算预留拒绝: 预留层不可用（fail-closed 不下单）",
                "venue": venue, "decision": payload, "reservation": None}

    # 审计③(2026-09-13)：「组合风险总预算」此前名不副实——reserve 的 sqlite 上限按
    # (venue, env, fingerprint) 逐所求和，gross_exposure(environment) 跨所聚合只进证据
    # payload 不参与裁决，三所全开闸时 1000U 预算实际可占用 3000U。现把跨所合算补成
    # 真实总闸（各所子闸保留）。仅显式配置 budget>0 时生效（0=无顶语义不变）。
    # 幂等豁免：同 (account_key, intent) 重提不是新增占用（reserve 底层本就幂等），
    # 需从 gross_exposure 扣回该 intent 已占额，否则重试会被总闸误杀。
    intent = str(intent_id or f"{inst_id}:{side}:{int(time.time())}")
    account_key = (venue, environment, str(env.fingerprint))
    _prior_same_intent = 0.0
    if budget_total > 0:
        try:
            for _r in mgr.reservations(account_key):
                if str(_r.get("intent_id") or "") == intent:
                    _prior_same_intent = float(_r.get("amount_usdt") or 0.0)
                    break
        except Exception:
            pass
    _pb_err = portfolio_budget_guard(budget_total, budget_used - _prior_same_intent,
                                     margin_est, environment)
    if _pb_err:
        payload["budget"] = {"limit_usdt": budget_total,
                             "reserved_before_usdt": budget_used,
                             "gross_exposure_before_usdt": budget_used,
                             "margin_usdt": margin_est, "error": _pb_err}
        payload["outcome"] = "portfolio_budget_exceeded"
        payload["skip_reason"] = _pb_err
        persist_venue_decision(inst_id, payload)
        print(f"[预算预留] 本轮不下单 {inst_id}: {_pb_err}")
        return {"ok": False, "error": _pb_err, "venue": venue,
                "decision": payload, "reservation": None}

    try:
        record = mgr.reserve(account_key, intent, margin_est, state="pending")
    except risk_reservation.ReservationExceeded as exc:
        payload["budget"] = {"limit_usdt": budget_total, "reserved_before_usdt": budget_used,
                             "margin_usdt": margin_est, "error": str(exc)}
        payload["outcome"] = "budget_rejected"
        payload["skip_reason"] = f"预算预留拒绝: {exc}"
        persist_venue_decision(inst_id, payload)
        print(f"[预算预留] 本轮不下单 {inst_id}: {exc}")
        return {"ok": False, "error": f"预算预留拒绝: {exc}",
                "venue": venue, "decision": payload, "reservation": None}
    except Exception as exc:
        payload["budget"] = {"limit_usdt": budget_total, "margin_usdt": margin_est,
                             "error": str(exc)}
        payload["outcome"] = "budget_error"
        payload["skip_reason"] = f"预算预留拒绝: {exc}"
        persist_venue_decision(inst_id, payload)
        print(f"[预算预留] 本轮不下单 {inst_id}: 预留层异常 {exc}")
        return {"ok": False, "error": f"预算预留拒绝: {exc}",
                "venue": venue, "decision": payload, "reservation": None}

    payload["budget"] = {"limit_usdt": budget_total, "account_key": list(account_key),
                         "intent_id": intent, "amount_usdt": margin_est,
                         "reserved_before_usdt": budget_used,
                         "state": record.get("state") if isinstance(record, dict) else None}
    persist_venue_decision(inst_id, payload)
    print(f"[选所路由] {inst_id} → {venue}（{decision.reason_code}"
          + (f"，手选优先 {preferred}" if preferred != "auto" else "")
          + f"；预留保证金估算 {margin_est}U）")
    return {"ok": True, "error": None, "venue": venue, "decision": payload,
            "reservation": {"manager": mgr, "account_key": account_key,
                            "intent_id": intent, "amount_usdt": margin_est}}


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
    """审计③：跨所合算总闸的可测纯函数。返回 None=放行；返回 str=拒绝理由。
    语义：budget_total<=0 → 不封顶（保持既有 0=无顶默认）；>0 时按 gross_exposure
    已占用 + 本笔保证金估算 与总预算比较（1e-9 浮点容差）。"""
    try:
        bt = float(budget_total or 0.0)
        bu = float(budget_used or 0.0)
        me = float(margin_est or 0.0)
    except (TypeError, ValueError):
        return "预算数值不可解析，fail-closed 拒绝下单"
    if bt <= 0:
        return None
    if me > 0 and bu + me > bt + 1e-9:
        return (f"组合预算（跨所合算）用尽：已占 {bu:.2f}U + 本笔 {me:.2f}U "
                f"> 总预算 {bt:.2f}U（环境 {environment}）")
    return None


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
    """SQLite CURRENT_TIMESTAMP（UTC 'YYYY-MM-DD HH:MM:SS'）→ 秒龄。

    不可解析 = -inf（保守：年龄未知按「没到对账窗口」处理，**永不释放**；
    返回 +inf 会把脏时间戳当成超旧而错杀活占用——方向绝不能反）。
    """
    try:
        dt = datetime.datetime.strptime(str(ts_str).strip()[:19], "%Y-%m-%d %H:%M:%S")
        return max(0.0, now_utc - dt.replace(tzinfo=datetime.timezone.utc).timestamp())
    except (TypeError, ValueError):
        return float("-inf")


def reconcile_reservation_ledger(real_pos_dict: Dict[str, Any],
                                 pending_inst_ids: set,
                                 environment: str,
                                 ttl_s: float = None,
                                 venue_snapshot: Optional[Dict[str, list]] = None) -> int:
    """周期级预留对账（US-010）：账实相符原则回笼陈旧占用。

    背景：confirm 只翻状态、平仓/撤单/凭证代际轮换都无释放路径——预留台账
    单向累积，面板「已预留」虚高；一旦启用组合预算封顶，陈旧 pending 会挤占
    真实额度把合法开仓挡死。recovery() 的纪律是孤儿「标记不清算」，本函数
    就是那个「对账确认后的显式释放」：

    - 意图标的在当前真实持仓（同所同环境）或仍在挂 → **保留**（无论多旧）；
    - 现货两清（无仓无挂）且 updated_at 超 TTL → release(state=closed) 回笼；
    - 时间戳不可解析 / 环境不匹配 / account_key 异常 → 保守保留；
    - 单条释放失败不影响其余（下周期重试，幂等 UNIQUE 键）。

    返回释放条数。调用方必须传**本周期刚核验过的**持仓/挂单实况（fail-closed
    路径不会到这里），杜绝拿陈旧视图误释放活仓预算。
    """
    ttl = RESERVATION_RECONCILE_TTL_S if ttl_s is None else float(ttl_s)
    now_utc = time.time()
    try:
        mgr = reservation_manager()
        rows = mgr.list_unreleased(environment)
    except Exception as exc:
        print(f"[预留对账] warn 台账不可读，本周期跳过（不强行释放）: {exc}")
        return 0
    # 同所同环境的真实持仓索引：venue → {base: posSide}（OKX 持仓字典是 instId→p）
    live_by_venue: Dict[str, set] = {}
    for inst_id, p in (real_pos_dict or {}).items():
        v = "okx"  # 主循环持仓字典当前仅 OKX 直签链
        base = str(inst_id).split("-")[0].upper()
        side = str(p.get("posSide", "net")).lower()
        live_by_venue.setdefault(v, set()).add(f"{base}:{side}")
    # 跨所封顶快照（gate/binance）——有仓则对应意图必须保留（复用主循环已读结果，零重复出网）
    if venue_snapshot is None:
        try:
            _xv_ok, venue_snapshot, _ = fetch_other_venue_positions(environment)
            if not _xv_ok:
                venue_snapshot = {}
        except Exception:
            venue_snapshot = {}
    for v, _rows in (venue_snapshot or {}).items():
        for _p in _rows:
            base = str(_p.get("base") or str(_p.get("inst_id", "")).split("_")[0]).upper()
            live_by_venue.setdefault(v, set()).add(f"{base}:{_p.get('side', 'net')}")
    pending = {str(x) for x in (pending_inst_ids or set())}
    released_n = 0
    for row in rows:
        try:
            intent = str(row.get("intent_id") or "")
            parts = intent.split(":")
            inst_id = parts[0] if parts else ""
            pos_side = ("long" if "LONG" in intent.upper()
                        else "short" if "SHORT" in intent.upper() else "net")
            base = inst_id.split("-")[0].upper()
            venue = str(row.get("venue") or "").lower()
            still_live = (f"{base}:{pos_side}" in live_by_venue.get(venue, set())
                          or (venue == "okx" and inst_id in pending))
            if still_live:
                continue
            if _utc_age_seconds(row.get("updated_at"), now_utc) < ttl:
                continue  # 新周期意图（本周期刚预留/成交在途）：未到对账窗口
            mgr.release(str(row.get("account_key") or ""), intent,
                        state=risk_reservation.STATE_CLOSED)
            released_n += 1
            print(f"[预留对账] 释放 {intent}（{venue}/{environment} 无仓无挂 且 "
                  f"age>={ttl:.0f}s，state=closed 回笼 {row.get('amount_usdt')}U）")
        except Exception as exc:
            print(f"[预留对账] warn 单条释放失败（下周期重试）{row.get('intent_id')}: {exc}")
    if released_n:
        print(f"[预留对账] 本周期回笼 {released_n} 笔陈旧占用")
    return released_n


def submit_protected_limit_order(inst_id: str, side: str, pos_side: str, size: float, price: float, tp_px: float, sl_px: float, venue_ctx: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Submit a protected limit order; acceptance is not treated as a fill.

    venue_ctx：US-003 决策面上下文（AI 信号入口单必须带）。带上下文 → 先过选所路由
    + 预算原子预留，任一失败返回 (False, "路由拒绝/预算预留拒绝: <reason>")，本轮
    不下单；不带上下文 = 非 AI 信号的通用提交（保留 US-007 listing gate 契约），
    只 warn 不闸门——新增开仓路径时必须传 ctx。
    """
    env = current_environment()  # 审计 C2：冻结周期环境单源（同 close 路径）
    _reservation = None
    target_venue = "okx"
    if isinstance(venue_ctx, dict):
        # ---- US-003 决策面前置闸：选所路由 + 预算原子预留（失败即本轮不下单）----
        _routing = route_and_reserve_signal(
            inst_id, side, size, price,
            notional_usdt=float(venue_ctx.get("notional_usdt") or 0.0),
            margin_usdt=float(venue_ctx.get("margin_usdt") or 0.0),
            intent_id=str(venue_ctx.get("intent_id") or ""))
        if not _routing["ok"]:
            return False, str(_routing.get("error") or "路由拒绝")
        _reservation = _routing.get("reservation")
        target_venue = str(_routing.get("venue") or "okx").lower()
    else:
        print(f"[US-003 决策面] warn {inst_id} 提交未携带 venue_ctx——"
              f"未经选所路由/预算预留，仅限非 AI 信号通用路径")

    # 环境维合约存在性对账（US-007）：目录拉不到 → fail-open 放行（对账是增强不是闸门）；
    # 已下架/未上市（如 SUI 在 demo 被下架）→ fail-closed 拒单，reason 透传。
    #
    # Listing Gate Parity（三所平权命门）：inst_id 是 OKX 形态（BTC-USDT-SWAP），而
    # binance 目录键是 BTCUSDT、gate 是 BTC_USDT——直接拿 inst_id 去外所目录对账必然
    # 查不到 → 误判「沙盒未上市」，导致非 OKX 所一单都开不了。对账前必须先经
    # native_symbol_pure 翻译成目标所原生合约码（纯元数据，绝不实例化适配器→零出网）。
    try:
        from r20_backend.exchanges.listing import ensure_contract_listed
        native_contract = venue_registry.native_symbol_pure(
            canonical_base(inst_id), target_venue)
        _check = ensure_contract_listed(target_venue, "demo" if env.simulated else "live", native_contract)
        if not _check.ok:
            print(f"[listing gate] 拒绝下单 {inst_id}→{native_contract} ({target_venue}): {_check.reason}")
            release_signal_reservation(_reservation, "合约对账拒绝")
            return False, f"合约对账拒绝: {_check.reason}"
    except Exception as _le:
        print(f"[listing gate] warn 对账不可用，跳过（不阻塞）: {_le}")
    # Check if we are running in simulated/demo mode and price diverged significantly from demo orderbook
    effective_px = price
    effective_tp = tp_px
    effective_sl = sl_px

    # 审计④(2026-09-13)：现价单次读取，demo rescale 与幻觉锚共用——两次读可互相
    # 错位，且旧代码只有 simulated+okx 才取价，live/外所永远拿不到锚（裸奔真身）。
    _tick_last_raw = None
    _anchor_last = 0.0
    try:
        _tick_last_raw = (fetch_ticker(inst_id) or {}).get("last")
        if _tick_last_raw:
            _anchor_last = float(_tick_last_raw)
    except Exception as _ae:
        print(f"[价格锚定] warn 现价获取失败，本单跳过锚定/rescale: {_ae}")

    if env.simulated and target_venue == "okx":
        try:
            demo_last = _anchor_last
            if demo_last:
                if demo_last > 0 and price > 0:
                    divergence = abs(price - demo_last) / demo_last
                    # If live market price diverged from demo sandbox by more than 5% (e.g. ASTER / illiquid demo pair)
                    if divergence > 0.05:
                        scale = demo_last / price
                        prec = len(str(_tick_last_raw).split(".")[1]) if "." in str(_tick_last_raw) else 4
                        effective_px = round(price * scale, prec)
                        effective_tp = round(tp_px * scale, prec)
                        effective_sl = round(sl_px * scale, prec)
                        # Re-verify boundary constraints for demo sandbox
                        if pos_side == "long":
                            if effective_sl >= effective_px:
                                effective_sl = round(effective_px * 0.98, prec)
                            if effective_tp <= effective_px:
                                effective_tp = round(effective_px * 1.04, prec)
                        else:
                            if effective_sl <= effective_px:
                                effective_sl = round(effective_px * 1.02, prec)
                            if effective_tp >= effective_px:
                                effective_tp = round(effective_px * 0.96, prec)
        except Exception:
            pass

    # Final Non-Bypassable Verification: verify actual effective price, tp and sl
    from scripts.order_risk import validate_quote_geometry_and_rr
    action_type = "BUY_LONG" if pos_side == "long" else "SELL_SHORT"
    is_valid, reason, _ = validate_quote_geometry_and_rr(action_type, effective_px, effective_tp, effective_sl)
    if not is_valid:
        print(f"[Order Rejected] 最终有效开仓报价未通过核心安全复验: {reason} (px={effective_px}, tp={effective_tp}, sl={effective_sl})")
        release_signal_reservation(_reservation, "核心安全复验拒绝")
        return False, f"最终订单核心安全复验拒绝: {reason}"

    # 审计④(2026-09-13)：LLM 幻觉入场价锚定——几何/R:R 只验 entry/tp/sl 相互关系，
    # 从不比对现价。危险形态是「穿价」：BUY 限价挂在现价上方 → 即时成交于意外价，
    # 而配套 SL 触发价锚在幻觉 entry 上、相对真实成交价可能即刻触发 → 开-秒平循环
    # 放血（demo+okx 有 5% rescale 兜底，live 与外所此前裸奔）。回踩方向的远挂单
    # 是合法策略（不穿价即放行，OKX 侧 4 分钟超时撤兜底）。_anchor_last 来自上方
    # 单次读价；取价失败不阻断（行情断时黑天鹅哨兵/熔断已另行 fail-closed），但必吼。
    if _anchor_last > 0 and effective_px > 0:
        _cross_pct = float(os.getenv("R20_MAX_PRICE_CROSS_PCT", "0.005") or 0.005)
        _far_pct = float(os.getenv("R20_MAX_PRICE_FAR_PCT", "0.50") or 0.50)
        if action_type == "BUY_LONG" and effective_px > _anchor_last * (1.0 + _cross_pct):
            _rej = f"入场价穿价幻觉：BUY 限价 {effective_px:g} 高于现价 {_anchor_last:g} 超阈值({max(0.0,(effective_px/_anchor_last-1)*100):.2f}%>{_cross_pct*100:.1f}%)，将即时成交于意外价且 SL 锚点失真"
            print(f"[价格锚定] 拒单 {inst_id}: {_rej}")
            release_signal_reservation(_reservation, "价格锚定拒绝")
            return False, f"价格锚定拒绝: {_rej}"
        if action_type == "SELL_SHORT" and effective_px < _anchor_last * (1.0 - _cross_pct):
            _rej = f"入场价穿价幻觉：SELL 限价 {effective_px:g} 低于现价 {_anchor_last:g} 超阈值({max(0.0,(1-effective_px/_anchor_last)*100):.2f}%>{_cross_pct*100:.1f}%)，将即时成交于意外价且 SL 锚点失真"
            print(f"[价格锚定] 拒单 {inst_id}: {_rej}")
            release_signal_reservation(_reservation, "价格锚定拒绝")
            return False, f"价格锚定拒绝: {_rej}"
        if abs(effective_px - _anchor_last) / _anchor_last > _far_pct:
            _rej = f"入场价与现价距离 {abs(effective_px/_anchor_last-1)*100:.1f}% 超荒谬阈值 {_far_pct*100:.0f}%，判定为幻觉报价拒单"
            print(f"[价格锚定] 拒单 {inst_id}: {_rej}")
            release_signal_reservation(_reservation, "价格锚定拒绝")
            return False, f"价格锚定拒绝: {_rej}"

    # 多所平权执行：若路由选定 Gate 或 Binance，走统一原生受保护执行路由
    if target_venue in ("gate", "binance"):
        try:
            from r20_backend import execution_router
            asset_canonical = str(inst_id).split("-")[0].upper()
            default_lever = float(MIN_LEVERAGE or 3.0)
            margin_val = float(venue_ctx.get("margin_usdt") or (size * price / default_lever)) if isinstance(venue_ctx, dict) else (size * price / default_lever)
            lever_val = float(venue_ctx.get("leverage") or default_lever) if isinstance(venue_ctx, dict) else default_lever
            lever_val = max(float(MIN_LEVERAGE or 1.0), min(float(MAX_LEVERAGE or 20.0), lever_val))

            res = execution_router.open_protected_position({
                "venue": target_venue,
                "asset": asset_canonical,
                "action": action_type,
                "margin_usdt": margin_val,
                # 审计 P0-1：把权益占比顶一并下传，router 侧再兜一层（本处已夹过）
                "max_margin_usdt": float(venue_ctx.get("max_margin_usdt") or 0.0),
                "leverage": lever_val,
                "entry_price": effective_px,
                "take_profit_price": effective_tp,
                "stop_loss_price": effective_sl,
                "environment": str(env.mode),
                # 审计 P1-7：per-venue min_confidence 生效所需的原始 AI 置信度（缺失=不做该检查）
                "confidence": float(venue_ctx.get("confidence") or 0.0) if isinstance(venue_ctx, dict) else 0.0,
            }, environment=str(env.mode))
            if not res.get("ok"):
                detail = res.get("detail") or "多所执行路由拒绝"
                release_signal_reservation(_reservation, detail)
                return False, f"{target_venue.upper()} 下单失败: {detail}"

            order_id = str(res.get("order_id") or res.get("tp_id") or f"{target_venue}-ok")
            record_open_intent(inst_id, side)
            confirm_signal_reservation(_reservation)
            return True, order_id
        except Exception as exc:
            release_signal_reservation(_reservation, f"多所执行异常: {exc}")
            return False, f"{target_venue.upper()} 执行异常: {exc}"

    # 审计④5(2026-09-13)：OKX 直下路径从不落 AI 裁决杠杆——张数按 ai_lever 折算，
    # 但账户档位不变 → 实际保证金/强平价按旧档算，风险模型与实况脱节（净模式或
    # 10x 旧档可把 3x 计划仓的强平价拉得极近）。best-effort 发单前对齐档位：失败仅
    # warn 不阻断（保护腿/张数/几何已定，杠杆只影响保证金效率，绝不因此裸奔）。
    _want_lever = 0.0
    if isinstance(venue_ctx, dict):
        try:
            _want_lever = float(venue_ctx.get("leverage") or 0.0)
        except (TypeError, ValueError):
            _want_lever = 0.0
    if _want_lever > 0:
        _want_lever = max(1.0, min(_want_lever, float(MAX_LEVERAGE or 20.0)))
        try:
            okx_rest.set_leverage(inst_id, int(_want_lever), mgn_mode="cross",
                                  pos_side=(pos_side or None))
        except Exception as lev_exc:
            print(f"[杠杆落地] warn {inst_id} 设档至 {int(_want_lever)}x 失败，"
                  f"按账户现档发单（不影响 TP/SL 覆盖）: {lev_exc}")

    try:
        rows = okx_rest.place_order(
            inst_id, side, f"{size:g}",
            pos_side=pos_side, td_mode="cross", ord_type="limit",
            px=effective_px, attach_tp=effective_tp, attach_sl=effective_sl,
        )
    except Exception as exc:
        release_signal_reservation(_reservation, "下单异常")
        return False, str(exc)
    order_id = None
    for row in rows:
        order_id = row.get("ordId") or row.get("orderId")
        if order_id:
            break
    if not order_id:
        release_signal_reservation(_reservation, "交易所未返回可核验订单号")
        return False, "exchange accepted response without a verifiable order id"
    record_open_intent(inst_id, side)
    confirm_signal_reservation(_reservation)
    return True, str(order_id)


def _float_or_zero(value: Any) -> float:
    try:
        return abs(float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _live_oco_coverage(orders: List[Dict[str, Any]], pos_side: str) -> float:
    """Return contract size covered by live, reduce-only OCO TP/SL orders."""
    coverage = 0.0
    close_side = "sell" if pos_side == "long" else "buy"
    for order in orders:
        if str(order.get("state", "live")).lower() not in {"live", "effective"}:
            continue
        if str(order.get("posSide", "net")).lower() not in {pos_side, "net"}:
            continue
        if str(order.get("side", close_side)).lower() != close_side:
            continue
        if not order.get("tpTriggerPx") or not order.get("slTriggerPx"):
            continue
        reduce_only = str(order.get("reduceOnly", "true")).lower() in {"true", "1", "yes"}
        if not reduce_only:
            continue
        coverage += _float_or_zero(order.get("sz") or order.get("actualSz"))
    return coverage


def ensure_cloud_position_protection(inst_id: str, pos_side: str, size: float, tp_px: float, sl_px: float) -> Tuple[bool, str]:
    """Verify 100% live cloud OCO coverage, repair any gap, and verify again."""
    try:
        algo_rows = okx_rest.pending_algo_orders(inst_id)
    except Exception as exc:
        return False, f"unable to verify cloud OCO: {exc}"
    coverage = _live_oco_coverage(algo_rows, pos_side)
    missing = max(0.0, float(size) - coverage)
    if missing <= max(1e-12, float(size) * 0.001):
        return True, f"cloud OCO coverage verified ({coverage:g}/{size:g})"

    close_side = "sell" if pos_side == "long" else "buy"
    try:
        okx_rest.place_algo_oco(
            inst_id, close_side, missing, pos_side=pos_side, td_mode="cross",
            tp_trigger_px=tp_px, tp_ord_px="-1", sl_trigger_px=sl_px, sl_ord_px="-1",
            reduce_only=True, cxl_on_close_pos=True,
        )
    except Exception as exc:
        return False, f"cloud OCO repair failed: {exc}"

    for _ in range(4):
        time.sleep(0.5)
        try:
            verify_rows = okx_rest.pending_algo_orders(inst_id)
        except Exception:
            continue
        verified_coverage = _live_oco_coverage(verify_rows, pos_side)
        if verified_coverage + max(1e-12, float(size) * 0.001) >= float(size):
            return True, f"cloud OCO repaired and verified ({verified_coverage:g}/{size:g})"
    return False, "cloud OCO repair was submitted but full coverage could not be verified"


def build_signal_snapshot(f: dict) -> dict:
    """抽取开仓时刻的因果动力学与数理快照，供自进化复盘做真实因果归因（而非事后倒推）。

    兼容两套数据源 schema（2026-09-09 修复）：
    1. factor_library 快照块结构（calculus_dynamics / probability_theory / definite_integrals）
    2. 执行层 f["calculus"] = calculate_multi_timeframe 聚合结构
       （velocity / max_abs_jerk / 嵌套 probability_theory / definite_integrals）
    旧版只认结构 1，而开仓路径传入的是结构 2，导致 journal 里 22/24 字段恒为
    None → 复盘全量「数理快照不可观测」、逐单归因失效。
    """
    calc = f.get("calculus_dynamics") or {}
    prob = f.get("probability_theory") or {}
    integ = f.get("definite_integrals") or {}
    multi = f.get("calculus") or {}
    if not calc and multi:
        calc = {
            "velocity": multi.get("velocity"),
            "acceleration": multi.get("acceleration"),
            "jerk": multi.get("max_abs_jerk"),
            "impulse": multi.get("impulse"),
            "curvature": multi.get("curvature"),
            "power": multi.get("power"),
            "power_regime": multi.get("power_regime"),
            "regime": multi.get("regime"),
            "quality": multi.get("quality"),
        }
        prob = multi.get("probability_theory") or {}
        integ = multi.get("definite_integrals") or {}
    micro = f.get("microstructure") or {}
    money = f.get("smart_money_derivatives") or {}
    trend = f.get("trend_momentum") or {}
    snap = {
        "price": f.get("price"),
        "atr": f.get("atr"),
        "velocity": calc.get("velocity"),
        "acceleration": calc.get("acceleration"),
        "jerk": calc.get("jerk"),
        "impulse": calc.get("impulse"),
        "curvature": calc.get("curvature"),
        "power": calc.get("power"),
        "power_regime": calc.get("power_regime"),
        "regime": calc.get("regime"),
        "dynamics_quality": calc.get("quality"),
        "continuation_prob_pct": prob.get("continuation_prob_pct"),
        "breakdown_prob_pct": prob.get("breakdown_prob_pct"),
        "var_95_pct": prob.get("var_95_pct"),
        "cvar_95_pct": prob.get("cvar_95_pct"),
        "prob_regime": prob.get("prob_regime"),
        "is_fat_tail": prob.get("is_fat_tail"),
        "energy_integral": integ.get("energy_integral"),
        "deviation_area_integral": integ.get("deviation_area_integral"),
        "adx": trend.get("adx") or f.get("adx") or f.get("adx_1h"),
        "rsi": trend.get("rsi") or f.get("rsi") or f.get("rsi_14"),
        "funding_rate": micro.get("funding_rate") or f.get("funding_rate"),
        "composite_alpha_score": f.get("composite_alpha_score") or f.get("alpha_score"),
        "smart_money_net": money.get("net_flow") or money.get("taker_net") or money.get("smart_money_flow_usd"),
    }

    # 因子库快照（60s 频，开仓时刻即最新）二次补齐执行层 f 没有的四个外部观测字段
    if any(snap.get(k) is None for k in ("adx", "funding_rate", "composite_alpha_score", "smart_money_net")):
        try:
            lib_file = os.path.join(DATA_DIR, "factor_library_snapshot.json")
            if os.path.exists(lib_file):
                with open(lib_file, "r", encoding="utf-8") as handle:
                    lib = json.load(handle)
                entries = lib.get("instruments") or []
                if isinstance(entries, dict):
                    entries = list(entries.values())
                libf = next(
                    (x for x in entries if isinstance(x, dict) and x.get("instId") == f.get("instId")),
                    None,
                )
                if libf:
                    tm = libf.get("trend_momentum") or {}
                    sm = libf.get("smart_money_derivatives") or {}
                    if snap["adx"] is None:
                        snap["adx"] = tm.get("adx_1h")
                    if snap["funding_rate"] is None:
                        snap["funding_rate"] = sm.get("funding_rate_pct") or tm.get("funding_rate")
                    if snap["composite_alpha_score"] is None:
                        snap["composite_alpha_score"] = libf.get("composite_alpha_score")
                    if snap["smart_money_net"] is None:
                        snap["smart_money_net"] = sm.get("smart_money_flow_usd")
        except Exception:
            pass
    return snap


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
    # G10 场所标注：本链路全部为 OKX V5 直签执行，源头补 venue（gate lab 写侧
    # 自带 venue="gate"）；setdefault 不覆盖显式值，旧调用方无感。
    trade_data.setdefault("venue", "okx")
    if not isinstance(trade_data, dict):
        return
    if "policy_version" not in trade_data:
        try:
            from policy_snapshot import generate_policy_snapshot
            trade_data["policy_version"] = generate_policy_snapshot().get("policy_version", f"v{__version__}@unknown")
        except Exception:
            trade_data["policy_version"] = f"v{__version__}@unknown"
    try:
        ledger = []
        if os.path.exists(LEDGER_JSON_FILE):
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        ledger.append(trade_data)
        # 审计③(2026-09-13)：生产台账直 open("w") 覆写 → 原子替换。读者（熔断/
        # 日报/备份/面板）不再可能撞见半截 JSON。
        _atomic_write_json(LEDGER_JSON_FILE, ledger)
    except Exception as e:
        print(f"Failed to record trade to JSON: {e}")

    try:
        if record_trade_sqlite:
            # US-003 环境轴贯通：OKX 生产写方按冻结环境传真实档 live|demo；
            # 环境不可证明时交给 db_manager 兜底 unknown_legacy，绝不冒充。
            sqlite_row = dict(trade_data)
            try:
                sqlite_row.setdefault("environment", current_environment().mode)
            except Exception:
                pass
            record_trade_sqlite(sqlite_row)
    except Exception as e:
        print(f"Failed to record trade to SQLite: {e}")

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
    """Sync ratchet dynamic stop to OKX cloud conditional OCO order.
    
    Ensures that once a position reaches Breakeven (Tier 1) or Profit-Lock (Tier 2),
    the cloud trigger order is immediately amended without waiting for the 15-minute LLM cycle.
    """
    # 修复(2026-09-08)：v7.6 环境重构删除了旧全局 SIMULATED_TRADING，此处残留引用导致
    # NameError，连续 4 个交易周期崩溃(09-08 18:30~19:15 BJ)。DEMO/LIVE 统一尝试云端
    # amend：价格一致时幂等跳过；失败仅返回 False，调用方忽略返回值、由本地棘轮兜底，
    # 与 execute_ai_position_management 内联云端止损上移行为保持一致(演示盘与实盘同构)。
    try:
        algo_orders = okx_rest.pending_algo_orders(inst_id)
        live_algo = next((o for o in algo_orders if o.get("state") == "live" and o.get("posSide") == pos_side and o.get("slTriggerPx")), None)
        if not live_algo:
            return False
        current_cloud_sl = float(live_algo.get("slTriggerPx") or 0.0)
        # Avoid redundant amend if price already matches
        if abs(current_cloud_sl - new_sl) < 1e-6:
            return True
        okx_rest.amend_algo_sl(live_algo["algoId"], new_sl, inst_id=inst_id, new_sl_ord_px="-1")
        return True
    except Exception as e:
        print(f"[Cloud OCO Sync Error] {inst_id} {pos_side}: {e}")
        return False


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
    for _gv in ("gate", "binance"):
        try:
            if _gv in _BROKEN_VENUES:
                continue   # 回收侧已实证凭证死，不再逐标的空转（每轮进程级重探）
            if not (_gv_mode and venue_registry.execution_open(_gv, _gv_mode)):
                continue
            _gad = venue_registry.get_adapter(_gv, environment=_gv_mode)
            if _gv == "binance":
                _grows = _gad.open_orders() or []
            else:
                _grows = []
                for _ins in load_instruments():
                    _gb = str(_ins.get("instId") or "").split("-")[0].upper()
                    if _gb:
                        _grows.extend(_gad.list_open_orders(_gb) or [])
            for o in _grows:
                if not isinstance(o, dict):
                    continue
                _graw = o.get("raw") if isinstance(o.get("raw"), dict) else {}
                _gs = str(o.get("side") or _graw.get("side") or "").lower()
                _gro = o.get("reduce_only") if o.get("reduce_only") is not None else _graw.get("reduce_only")
                if _gs not in ("buy", "sell") or _gro in (True, "true", "1"):
                    continue
                _ginst = str(o.get("inst_id") or o.get("contract") or _graw.get("contract") or _graw.get("symbol") or "")
                _gbase = str(o.get("base") or "").upper() or _ginst.split("_")[0].split("-")[0].upper()
                if not _gbase:
                    continue
                pending_inst_ids.add(f"{_gbase}-USDT-SWAP")
                if _gs == "buy":
                    pending_long_count += 1
                else:
                    pending_short_count += 1
        except Exception as _gexc:
            if not any(m in str(_gexc) for m in _auth_markers):
                print(f"[周期快照] warn 外所 {_gv} 挂单枚举失败（去重计数从缺，回收侧已另行把关）: {str(_gexc)[:80]}")
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
            active_pos_list = []
            for f in all_factors:
                position = f.get("position")
                if not position:
                    continue
                position_payload = dict(position)
                position_payload.setdefault("venue", "okx")
                tracker = trackers.get(f"{f['instId']}_{position.get('side', '')}", {})
                position_payload["trailingStopPx"] = tracker.get("trailingStopPx")
                position_payload["highWaterMark"] = tracker.get("highWaterMark")
                position_payload["lowWaterMark"] = tracker.get("lowWaterMark")
                position_payload["takeProfitPx"] = tracker.get("takeProfitPx")
                position_payload["stage_desc"] = tracker.get("stage_desc", "")
                position_payload["atr"] = f.get("atr", 0.0)
                active_pos_list.append(position_payload)

            # 汇入多所（Binance / Gate）在管持仓，形成三所平权持仓全景
            # 审计(2026-09-13)：旧此处在主循环内**重新拉取**外所快照——同一周期两次
            # 读取既重复出网又可在瞬时不一致里撕裂展示（18:00 实锤日志双份打印）。
            # 现复用 1a 已冻结的周期快照（与预留对账「零重复出网」同一意图）。
            try:
                _xv_snap = xv_positions_by_venue
                if _xv_snap:
                    for v_name, v_rows in _xv_snap.items():
                        for p in v_rows:
                            base = str(p.get("base") or "").upper()
                            inst = str(p.get("inst_id") or base)
                            side = str(p.get("side") or "net").lower()
                            match_f = next((x for x in all_factors if x.get("name") == base), {})
                            active_pos_list.append({
                                "venue": v_name,
                                "instId": f"{v_name.upper()}:{inst}",
                                "name": base,
                                "side": side,
                                "pos": abs(float(p.get("size_signed") or 0)),
                                "avgPx": float(p.get("entry_price") or 0),
                                "markPx": float(p.get("mark_price") or 0),
                                "margin": float(p.get("margin") or 0),
                                "upl": float(p.get("unrealized_pnl") or 0),
                                "atr": match_f.get("atr", 0.0),
                                "leverage": float(p.get("leverage") or 0),
                            })
            except Exception as _xv_e:
                print(f"[三所持仓全景] 外所持仓汇入异常: {_xv_e}")
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
            ai_lever = min(max(ai_lever, float(MIN_LEVERAGE or 0.0) or 1.0), float(MAX_LEVERAGE or 20.0))
            # 审计 P2-5：池条目的 per-instrument max_leverage（tier 派生 3x/5x）此前无人读；
            # 现在它是该标的的硬上限（与全局上限取更严者），并透传给多所路由。
            try:
                _inst_lever_cap = float(f.get("max_leverage") or 0.0)
            except (TypeError, ValueError):
                _inst_lever_cap = 0.0
            if _inst_lever_cap > 0 and ai_lever > _inst_lever_cap:
                print(f"[杠杆闸门] {f['name']} 池内单标的杠杆上限 {_inst_lever_cap:g}x < 全局 {ai_lever:g}x，已按池值收紧")
                ai_lever = _inst_lever_cap
            if abs(ai_lever - float(ai_decision.get("leverage", 3) or 3)) > 1e-9:
                print(f"[杠杆闸门] {f['name']} AI 裁决杠杆 {ai_decision.get('leverage')}x "
                      f"超出配置区间 [{float(MIN_LEVERAGE or 0):g}x, {float(MAX_LEVERAGE or 0):g}x]，"
                      f"已夹至 {ai_lever:g}x")
            step_sz = float(f.get("minSz", 1) or 1)

            # If AI planned margin & leverage, calculate custom contract size
            if ai_margin > 0 and ai_lever >= 1.0 and f["price"] > 0 and ct_val > 0:
                planned_notional = ai_margin * ai_lever
                calculated_sz = quantize_size(planned_notional / (f["price"] * ct_val), step_sz)
                if calculated_sz > 0:
                    # 风险钳制：围绕自适应基准仓位的 0.5x~2.0x（按交易所最小步长量化，不再强制整数）
                    min_allowed_sz = max(step_sz, quantize_size(f["sz"] * 0.5, step_sz))
                    max_allowed_sz = max(min_allowed_sz, quantize_size(f["sz"] * 2.0, step_sz))
                    actual_sz = max(min_allowed_sz, min(max_allowed_sz, calculated_sz))
                    # 可用余额硬顶：单笔保证金不得超过风控页配置的余额占比，付不起则直接归零跳过而非放大
                    afford_sz = max_size_within_margin(usdt_available, ai_lever, f["price"], ct_val, step_sz)
                    if afford_sz is not None and afford_sz < float("inf"):
                        actual_sz = min(actual_sz, afford_sz)
                    actual_sz = quantize_size(actual_sz, step_sz)

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

                    is_profit_or_breakeven = (pos_upl > 0 and pos_upl_ratio >= MIN_SCALE_IN_PROFIT_RATIO) or (trailing_sl > 0 and trailing_sl >= pos_avg_px)
                    planned_margin = ai_margin if ai_margin > 0 else (actual_sz * ct_val * f["price"] / max(1.0, ai_lever))
                    within_margin_cap = (curr_margin + planned_margin) <= ASSET_MARGIN_CAP

                    if is_profit_or_breakeven and scale_count < MAX_SCALE_IN_COUNT and within_margin_cap and ai_conf >= MIN_SCALE_IN_CONFIDENCE and calculus_accel_ok:
                        allow_entry = True
                        is_scale_in = True
                        print(f"[Pyramiding] {f['name']} 满足顺势浮盈加多条件: 底仓浮盈={pos_upl:+.2f}U ({pos_upl_ratio*100:+.1f}%), 已加仓{scale_count}次, 微积分加速度={c_accel:+.2f}, 延续概率={p_cont:.1f}%, 计划加仓{actual_sz}张")
                    else:
                        if not is_profit_or_breakeven:
                            print(f"[Pyramiding 拦截] {f['name']} 底仓未达浮盈保本门禁 (浮盈={pos_upl:+.2f}U ROI={pos_upl_ratio*100:+.1f}%), 严禁逆势加仓")
                        elif scale_count >= MAX_SCALE_IN_COUNT:
                            print(f"[Pyramiding 拦截] {f['name']} 已达最大加仓次数 ({scale_count}/{MAX_SCALE_IN_COUNT})")
                        elif not within_margin_cap:
                            print(f"[Pyramiding 拦截] {f['name']} 加仓后总保证金将超限 ({curr_margin + planned_margin:.1f} > {ASSET_MARGIN_CAP}U)")
                        elif ai_conf < MIN_SCALE_IN_CONFIDENCE:
                            print(f"[Pyramiding 拦截] {f['name']} AI加仓置信度不足 ({ai_conf:.0f}% < {MIN_SCALE_IN_CONFIDENCE}%)")
                        elif not calculus_accel_ok:
                            print(f"[Pyramiding 拦截] {f['name']} 数理动能衰竭或延续概率偏低 (加速度={c_accel:+.2f}, 概率={p_cont:.1f}%)，禁止追多加仓")

                if allow_entry and entries_blocked:
                    print(f"[挂单对账] fail-closed 拦截 {f['name']} 新增多单下单（本周期对账失败）")
                    allow_entry = False
                if allow_entry:
                    limit_px = round(ai_decision.get("entry_price") if (ai_decision and ai_decision.get("entry_price", 0) > 0) else (f.get("bidPx") or f["price"]), prec)
                    tp_px = round(ai_decision.get("take_profit_price") if (ai_decision and ai_decision.get("take_profit_price", 0) > 0) else (limit_px + tp_dist), prec)
                    sl_px = round(ai_decision.get("stop_loss_price") if (ai_decision and ai_decision.get("stop_loss_price", 0) > 0) else (limit_px - sl_dist), prec)

                    # Hard check: 做多须 sl_px < limit_px < tp_px（钳制见 scripts/trader/brackets.py）
                    sl_px, tp_px = normalize_bracket_prices(
                        is_long=True, limit_px=limit_px, tp_px=tp_px, sl_px=sl_px,
                        sl_dist=sl_dist, tp_dist=tp_dist, price=f["price"], prec=prec)

                    # US-003 决策面上下文：名义额（选所硬筛/深度需求）+ 保证金估算
                    # （预算预留额）+ 意图号（同一条 AI 决策重投幂等，不重复占预算）
                    _notional = actual_sz * ct_val * limit_px
                    # 审计 P0-1：多所路径保证金与 OKX 同尺（AI 计划额 ∩ 张数隐含额 ∩ 权益占比 ∩ 单标的封顶）
                    _order_margin = order_margin_gate(
                        ai_margin, size=actual_sz, price=limit_px, ct_val=ct_val,
                        leverage=ai_lever, usdt_available=usdt_available)
                    accepted, order_ref = submit_protected_limit_order(
                        inst_id, "buy", "long", actual_sz, limit_px, tp_px, sl_px,
                        venue_ctx={"notional_usdt": _notional,
                                   "margin_usdt": _order_margin,
                                   "max_margin_usdt": equity_margin_cap(usdt_available),
                                   "leverage": ai_lever,
                                   # 审计 P2-5：池内单标的杠杆上限一并透传（router 取更严者）
                                   "max_leverage": _inst_lever_cap,
                                   # 审计 P1-7：per-venue min_confidence 闸门需要原始置信度（决策载荷里本没有）
                                   "confidence": ai_conf,
                                   "intent_id": f"{inst_id}:BUY_LONG:{int(ai_info.get('timestamp') or time.time())}"})
                    if accepted:
                        if is_scale_in:
                            tracker = trackers.get(f"{inst_id}_long", {})
                            tracker["scale_count"] = tracker.get("scale_count", 0) + 1
                            save_trackers(trackers)
                            executed_actions.append(f"[{f['name']}] 🚀 AI顺势浮盈金字塔加多挂单已提交 {actual_sz}张@{limit_px} (order={order_ref}, TP={tp_px}, SL={sl_px})")
                            if notify_trade_open:
                                notify_trade_open(
                                    inst=f["name"],
                                    side="多 (顺势加多)",
                                    sz=actual_sz,
                                    px=limit_px,
                                    strategy="🚀 顺势金字塔加多",
                                    reason=str(ai_reason),
                                    tp_px=tp_px,
                                    sl_px=sl_px,
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                        else:
                            executed_actions.append(f"[{f['name']}] AI限价多单已提交待成交 {actual_sz}张@{limit_px} (order={order_ref}, TP={tp_px}, SL={sl_px})")
                            pending_inst_ids.add(inst_id)
                            reserved_slot_count += 1
                            reserved_long_count += 1
                            if notify_trade_open:
                                notify_trade_open(
                                    inst=f["name"],
                                    side="多",
                                    sz=actual_sz,
                                    px=limit_px,
                                    strategy=strat_tag,
                                    reason=str(ai_reason),
                                    tp_px=tp_px,
                                    sl_px=sl_px,
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                    else:
                        executed_actions.append(f"[{f['name']}] AI限价多单提交失败: {order_ref}")

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

                    is_profit_or_breakeven = (pos_upl > 0 and pos_upl_ratio >= MIN_SCALE_IN_PROFIT_RATIO) or (trailing_sl > 0 and trailing_sl <= pos_avg_px)
                    planned_margin = ai_margin if ai_margin > 0 else (actual_sz * ct_val * f["price"] / max(1.0, ai_lever))
                    within_margin_cap = (curr_margin + planned_margin) <= ASSET_MARGIN_CAP

                    c_dyn = f.get("calculus", {})
                    c_accel = float(c_dyn.get("acceleration", 0.0) or 0.0)
                    p_th = c_dyn.get("probability_theory", {})
                    p_break = float(p_th.get("breakdown_prob_pct", 50.0) or 50.0)
                    calculus_accel_ok = (c_accel <= 0.25 and p_break >= 40.0)

                    if is_profit_or_breakeven and scale_count < MAX_SCALE_IN_COUNT and within_margin_cap and ai_conf >= MIN_SCALE_IN_CONFIDENCE and calculus_accel_ok:
                        allow_entry = True
                        is_scale_in = True
                        print(f"[Pyramiding] {f['name']} 满足顺势浮盈加空条件: 底仓浮盈={pos_upl:+.2f}U ({pos_upl_ratio*100:+.1f}%), 已加仓{scale_count}次, 微积分加速度={c_accel:+.2f}, 击穿概率={p_break:.1f}%, 计划加仓{actual_sz}张")
                    else:
                        if not is_profit_or_breakeven:
                            print(f"[Pyramiding 拦截] {f['name']} 底仓未达浮盈保本门禁 (浮盈={pos_upl:+.2f}U ROI={pos_upl_ratio*100:+.1f}%), 严禁逆势加仓")
                        elif scale_count >= MAX_SCALE_IN_COUNT:
                            print(f"[Pyramiding 拦截] {f['name']} 已达最大加仓次数 ({scale_count}/{MAX_SCALE_IN_COUNT})")
                        elif not within_margin_cap:
                            print(f"[Pyramiding 拦截] {f['name']} 加仓后总保证金将超限 ({curr_margin + planned_margin:.1f} > {ASSET_MARGIN_CAP}U)")
                        elif ai_conf < MIN_SCALE_IN_CONFIDENCE:
                            print(f"[Pyramiding 拦截] {f['name']} AI加仓置信度不足 ({ai_conf:.0f}% < {MIN_SCALE_IN_CONFIDENCE}%)")
                        elif not calculus_accel_ok:
                            print(f"[Pyramiding 拦截] {f['name']} 数理动能失速企稳或击穿概率偏低 (加速度={c_accel:+.2f}, 概率={p_break:.1f}%)，禁止追空加仓")

                if allow_entry and entries_blocked:
                    print(f"[挂单对账] fail-closed 拦截 {f['name']} 新增空单下单（本周期对账失败）")
                    allow_entry = False
                if allow_entry:
                    limit_px = round(ai_decision.get("entry_price") if (ai_decision and ai_decision.get("entry_price", 0) > 0) else (f.get("askPx") or f["price"]), prec)
                    tp_px = round(ai_decision.get("take_profit_price") if (ai_decision and ai_decision.get("take_profit_price", 0) > 0) else (limit_px - tp_dist), prec)
                    sl_px = round(ai_decision.get("stop_loss_price") if (ai_decision and ai_decision.get("stop_loss_price", 0) > 0) else (limit_px + sl_dist), prec)

                    # Hard check: 做空须 tp_px < limit_px < sl_px（钳制见 scripts/trader/brackets.py）
                    sl_px, tp_px = normalize_bracket_prices(
                        is_long=False, limit_px=limit_px, tp_px=tp_px, sl_px=sl_px,
                        sl_dist=sl_dist, tp_dist=tp_dist, price=f["price"], prec=prec)

                    # US-003 决策面上下文（与多单同构：名义额/保证金估算/幂等意图号）
                    _notional = actual_sz * ct_val * limit_px
                    # 审计 P0-1：与多单同尺（空单不允许绕过保证金闸门）
                    _order_margin = order_margin_gate(
                        ai_margin, size=actual_sz, price=limit_px, ct_val=ct_val,
                        leverage=ai_lever, usdt_available=usdt_available)
                    accepted, order_ref = submit_protected_limit_order(
                        inst_id, "sell", "short", actual_sz, limit_px, tp_px, sl_px,
                        venue_ctx={"notional_usdt": _notional,
                                   "margin_usdt": _order_margin,
                                   "max_margin_usdt": equity_margin_cap(usdt_available),
                                   "leverage": ai_lever,
                                   "max_leverage": _inst_lever_cap,   # 审计 P2-5：池内单标的杠杆上限
                                   "confidence": ai_conf,   # 审计 P1-7：per-venue 置信度门禁
                                   "intent_id": f"{inst_id}:SELL_SHORT:{int(ai_info.get('timestamp') or time.time())}"})
                    if accepted:
                        if is_scale_in:
                            tracker = trackers.get(f"{inst_id}_short", {})
                            tracker["scale_count"] = tracker.get("scale_count", 0) + 1
                            save_trackers(trackers)
                            executed_actions.append(f"[{f['name']}] 🌪️ AI顺势浮盈金字塔加空挂单已提交 {actual_sz}张@{limit_px} (order={order_ref}, TP={tp_px}, SL={sl_px})")
                            if notify_trade_open:
                                notify_trade_open(
                                    inst=f["name"],
                                    side="空 (顺势加空)",
                                    sz=actual_sz,
                                    px=limit_px,
                                    strategy="🌪️ 顺势金字塔加空",
                                    reason=str(ai_reason),
                                    tp_px=tp_px,
                                    sl_px=sl_px,
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                        else:
                            executed_actions.append(f"[{f['name']}] AI限价空单已提交待成交 {actual_sz}张@{limit_px} (order={order_ref}, TP={tp_px}, SL={sl_px})")
                            pending_inst_ids.add(inst_id)
                            reserved_slot_count += 1
                            reserved_short_count += 1
                            if notify_trade_open:
                                notify_trade_open(
                                    inst=f["name"],
                                    side="空",
                                    sz=actual_sz,
                                    px=limit_px,
                                    strategy=strat_tag,
                                    reason=str(ai_reason),
                                    tp_px=tp_px,
                                    sl_px=sl_px,
                                    leverage=int(ai_lever),  # 审计D(2026-09-13)：曾恒写 3——5x 仓实开也通知「3x 杠杆」，票圈谎报
                                )
                    else:
                        executed_actions.append(f"[{f['name']}] AI限价空单提交失败: {order_ref}")

    # 5. Persist Latest State for Web Monitoring Dashboard
    state_payload = {
        "timestamp": timestamp_full,
        "active_positions_count": active_pos_count,
        "max_positions": MAX_CONCURRENT_POSITIONS,
        "long_count": long_count,
        "short_count": short_count,
        "circuit_breaker": {"active": cb_active, "reason": cb_reason},
        "executed_actions": executed_actions,
        "instruments": []
    }

    for f in all_factors:
        score, action, reasons, strat_tag, strat_desc = evaluate_asset_signal(f)
        state_payload["instruments"].append({
            "name": f["name"],
            "instId": f["instId"],
            "type": f["type"],
            "price": f["price"],
            "rsi": round(f["rsi"], 1),
            "rsi_7": round(f.get("rsi_7", 50.0), 1),
            "vwap_bias": round(f.get("vwap_bias", 0.0), 2),
            "macd_hist": f.get("macd_hist", 0.0),
            "macd_accel": f.get("macd_accel", 0.0),
            "obv_flow": f.get("obv_flow", "NEUTRAL"),
            "bb_bandwidth": f.get("bb_bandwidth", 0.0),
            "vol_ratio": f.get("vol_ratio", 1.0),
            "market_regime": f.get("market_regime", "CHOP"),
            "structure_1h": f.get("structure_1h", "CHOP"),
            "trend_1h": "多头" if f.get("trend_1h_bullish") else "空头",
            "trend_4h": "多头" if f.get("trend_4h_bullish") else "空头",
            "score": score,
            "action": action,
            "strategy": strat_tag,
            "desc": strat_desc,
            "position": f["position"]
        })

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
