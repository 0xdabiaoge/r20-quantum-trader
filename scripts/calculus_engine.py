"""Causal calculus features for market time series.

All functions are causal: the newest observation is the last value in the
input sequence. Callers should pass closed-candle data only.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Sequence


def _finite(values: Iterable[float]) -> List[float]:
    return [float(v) for v in values if v is not None and math.isfinite(float(v)) and float(v) > 0]


def _ema(values: Sequence[float], span: int = 3) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (max(1, span) + 1.0)
    out = [float(values[0])]
    for value in values[1:]:
        out.append(alpha * float(value) + (1.0 - alpha) * out[-1])
    return out


def _diff(values: Sequence[float], lag: int = 1) -> List[float]:
    lag = max(1, int(lag))
    return [values[i] - values[i - lag] for i in range(lag, len(values))]


def _normalise(value: float, scale: float) -> float:
    if scale <= 1e-12:
        return 0.0
    # Bounded output keeps one shock from dominating the LLM score.
    return max(-3.0, min(3.0, value / scale))


def _sign(value: float, threshold: float = 0.08) -> int:
    return 1 if value > threshold else (-1 if value < -threshold else 0)


def classify_regime(velocity: float, acceleration: float, impulse: float, jerk: float) -> str:
    if abs(jerk) >= 1.8 and abs(velocity) >= 0.8:
        return "SHOCK_HIGH_JERK"
    if abs(velocity) < 0.12 and abs(acceleration) < 0.12:
        return "RANGE_LOW_VELOCITY"
    direction = 1 if impulse >= 0 else -1
    if direction > 0:
        if velocity > 0.15 and acceleration > 0.10:
            return "BULL_ACCELERATING"
        if velocity > 0.08 and acceleration < -0.10:
            return "BULL_DECELERATING"
        if velocity < -0.08:
            return "BULL_REVERSING"
        return "BULL_STABLE"
    if velocity < -0.15 and acceleration < -0.10:
        return "BEAR_ACCELERATING"
    if velocity < -0.08 and acceleration > 0.10:
        return "BEAR_DECELERATING"
    if velocity > 0.08:
        return "BEAR_REVERSING"
    return "BEAR_STABLE"


def calculate_calculus(closes: Sequence[float], highs: Sequence[float] | None = None,
                      lows: Sequence[float] | None = None, smooth_span: int = 3,
                      lag: int = 1) -> Dict[str, Any]:
    """Return bounded causal velocity, acceleration and impulse features.

    `closes` must be chronological (oldest -> newest). Values are log-price
    differences and are normalised by recent log-return volatility.
    """
    prices = _finite(closes)
    if len(prices) < 6:
        return {"valid": False, "reason": "insufficient_closed_candles", "sample_size": len(prices)}

    log_prices = [math.log(p) for p in prices]
    smooth = _ema(log_prices, smooth_span)
    returns = _diff(smooth, lag)
    if len(returns) < 4:
        return {"valid": False, "reason": "insufficient_derivative_samples", "sample_size": len(prices)}

    recent_returns = returns[-min(20, len(returns)):]
    mean_r = sum(recent_returns) / len(recent_returns)
    variance = sum((r - mean_r) ** 2 for r in recent_returns) / max(1, len(recent_returns) - 1)
    volatility = math.sqrt(variance)
    scale = max(volatility, 1e-5)

    velocity_raw = returns[-1]
    acceleration_raw = returns[-1] - returns[-2]
    acceleration_series = _diff(returns, 1)
    jerk_raw = acceleration_series[-1] - acceleration_series[-2] if len(acceleration_series) >= 2 else 0.0

    window = min(8, len(returns))
    decay = 0.82
    impulse_raw = sum((decay ** i) * returns[-1 - i] for i in range(window))

    velocity = _normalise(velocity_raw, scale)
    acceleration = _normalise(acceleration_raw, scale)
    jerk = _normalise(jerk_raw, scale)
    impulse = _normalise(impulse_raw, scale * 2.0)

    # ATR percentage provides an independent quality check when OHLC exists.
    atr_pct = 0.0
    if highs is not None and lows is not None and len(highs) == len(prices) and len(lows) == len(prices):
        ranges = []
        for i, (high, low) in enumerate(zip(highs, lows)):
            try:
                h, lo = float(high), float(low)
                prev = prices[i - 1] if i else prices[i]
                ranges.append(max(h - lo, abs(h - prev), abs(lo - prev)) / prices[i])
            except (TypeError, ValueError, ZeroDivisionError):
                continue
        if ranges:
            atr_pct = sum(ranges[-min(14, len(ranges)):]) / min(14, len(ranges))

    quality = min(1.0, max(0.0, 0.45 + min(0.35, len(prices) / 100.0) + (0.20 if volatility > 1e-5 else 0.0)))
    regime = classify_regime(velocity, acceleration, impulse, jerk)
    return {
        "valid": True,
        "sample_size": len(prices),
        "velocity": round(velocity, 4),
        "acceleration": round(acceleration, 4),
        "impulse": round(impulse, 4),
        "jerk": round(jerk, 4),
        "atr_pct": round(atr_pct * 100.0, 4),
        "volatility": round(volatility, 6),
        "regime": regime,
        "quality": round(quality, 3),
        "direction": _sign(impulse),
    }


def calculate_multi_timeframe(candles_by_tf: Dict[str, Sequence[Sequence[float]]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    valid = []
    for timeframe, candles in candles_by_tf.items():
        # OKX packages are newest-first; reverse to chronological order.
        rows = list(reversed(candles or []))
        closes = [row[3] for row in rows if len(row) >= 4]
        highs = [row[1] for row in rows if len(row) >= 4]
        lows = [row[2] for row in rows if len(row) >= 4]
        features = calculate_calculus(closes, highs, lows)
        result[timeframe] = features
        if features.get("valid"):
            valid.append(features)

    if not valid:
        return {"valid": False, "timeframes": result, "regime": "DATA_UNRELIABLE", "quality": 0.0}

    impulse = sum(f["impulse"] for f in valid) / len(valid)
    velocity = sum(f["velocity"] for f in valid) / len(valid)
    acceleration = sum(f["acceleration"] for f in valid) / len(valid)
    jerk = max(abs(f["jerk"]) for f in valid)
    direction_votes = sum(f["direction"] for f in valid)
    if direction_votes >= 2 and acceleration > 0.05:
        regime = "BULL_ACCELERATING"
    elif direction_votes <= -2 and acceleration < -0.05:
        regime = "BEAR_ACCELERATING"
    elif abs(direction_votes) <= 1:
        regime = "RANGE_LOW_VELOCITY"
    else:
        regime = "BULL_DECELERATING" if direction_votes > 0 and acceleration < 0 else ("BEAR_DECELERATING" if acceleration > 0 else "MIXED_TRANSITION")
    return {
        "valid": True,
        "timeframes": result,
        "velocity": round(velocity, 4),
        "acceleration": round(acceleration, 4),
        "impulse": round(impulse, 4),
        "max_abs_jerk": round(jerk, 4),
        "regime": regime,
        "quality": round(sum(f["quality"] for f in valid) / len(valid), 3),
    }
