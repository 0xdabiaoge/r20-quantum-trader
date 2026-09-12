"""Position sizing, risk budgeting, and margin constraints."""
from __future__ import annotations
import math
from typing import Optional

from scripts.risk_constants import (
    MAX_DAILY_LOSS_USDT,
    DAILY_LOSS_EQUITY_RATIO,
    MAX_SINGLE_ASSET_MARGIN,
    SINGLE_ASSET_EQUITY_RATIO,
    RISK_PER_TRADE_EQUITY_RATIO,
    MAX_MARGIN_EQUITY_RATIO,
)


def effective_daily_loss_limit(usdt_available: Optional[float] = None) -> float:
    """单日亏损熔断线 = min(绝对封顶, 可用余额 5%)，小资金账户自动收紧。"""
    cap = MAX_DAILY_LOSS_USDT
    if usdt_available and usdt_available > 0:
        cap = min(cap, max(round(float(usdt_available) * DAILY_LOSS_EQUITY_RATIO, 2), 1.0))
    return cap


def effective_single_asset_margin(usdt_available: Optional[float] = None) -> float:
    """单标的累计保证金上限 = min(绝对封顶, 可用余额 30%)，与提示词风险预算同口径。"""
    cap = MAX_SINGLE_ASSET_MARGIN
    if usdt_available and usdt_available > 0:
        cap = min(cap, max(round(float(usdt_available) * SINGLE_ASSET_EQUITY_RATIO, 2), 1.0))
    return cap


def effective_risk_per_trade(pool_risk_usd: float, usdt_available: Optional[float] = None) -> float:
    """单笔基准风险额 = min(池内配置绝对值, 可用余额 × 2%)，避免小资金账户超额承担风险。"""
    cap = float(pool_risk_usd or 0.0)
    if usdt_available and usdt_available > 0:
        cap = min(cap, max(round(float(usdt_available) * RISK_PER_TRADE_EQUITY_RATIO, 4), 0.05))
    return cap


def quantize_size(raw_sz: float, min_sz: float) -> float:
    """按交易所最小下单步长(minSz)向下量化张数。低于最小步长返回 0.0。"""
    step = float(min_sz or 0) or 1.0
    try:
        raw = float(raw_sz or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if raw <= 0:
        return 0.0
    return round(math.floor(raw / step + 1e-9) * step, 10)


def max_size_within_margin(usdt_available: float, leverage: float, price: float, ct_val: float, min_sz: float) -> float:
    """可用余额硬顶：单笔保证金不得超过可用余额的 MAX_MARGIN_EQUITY_RATIO，超出部分直接砍掉。"""
    if not usdt_available or usdt_available <= 0 or price <= 0 or ct_val <= 0:
        return float("inf")
    max_margin = float(usdt_available) * MAX_MARGIN_EQUITY_RATIO
    raw = (max_margin * max(1.0, float(leverage or 1.0))) / (float(price) * float(ct_val))
    return quantize_size(raw, min_sz)
