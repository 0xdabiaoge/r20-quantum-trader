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
from .reservation import (
    route_and_reserve_signal,
    build_venue_candidates,
    reservation_manager,
    reconcile_reservation_ledger,
    release_signal_reservation,
    fetch_other_venue_positions,
)

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
    "route_and_reserve_signal",
    "build_venue_candidates",
    "reservation_manager",
    "reconcile_reservation_ledger",
    "release_signal_reservation",
    "fetch_other_venue_positions",
]
