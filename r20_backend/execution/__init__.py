"""Modular Execution Engine and Quantitative Pipeline for R20 Quantum Trader."""
from __future__ import annotations

from .indicators import (
    calc_ema,
    calc_rsi,
    calc_atr,
    calc_macd_histogram_acceleration,
    calc_obv_trend,
    calc_bollinger_squeeze,
)
from .sizing import (
    quantize_size,
    max_size_within_margin,
    effective_daily_loss_limit,
    effective_single_asset_margin,
    effective_risk_per_trade,
)
from .circuit_breaker import (
    check_black_swan_sentinel,
    is_circuit_breaker_active,
    is_in_stop_cooldown,
    add_stop_cooldown,
    load_stop_cooldowns,
)
# 审计④#7(2026-09-13)：删除 execution/reservation.py 幻影孪生——它按不存在的 API 写
# （mgr.reserve(venue=…, ttl_seconds=…) / res.ok / DEFAULT_RESERVATION_TTL_SECONDS /
# list_active 均不存在），任何调用即 TypeError，却挂在包导出面上「谁接谁炸」。
# 选所/预留的**活实现**在 scripts/ai_factor_trader.py（route_and_reserve_signal 等，
# API 对齐、tests/test_venue_wiring 钉死）；未来单源迁移属结构工程批次，勿再复制副本。

__all__ = [
    "calc_ema",
    "calc_rsi",
    "calc_atr",
    "calc_macd_histogram_acceleration",
    "calc_obv_trend",
    "calc_bollinger_squeeze",
    "quantize_size",
    "max_size_within_margin",
    "effective_daily_loss_limit",
    "effective_single_asset_margin",
    "effective_risk_per_trade",
    "check_black_swan_sentinel",
    "is_circuit_breaker_active",
    "is_in_stop_cooldown",
    "add_stop_cooldown",
    "load_stop_cooldowns",
]
