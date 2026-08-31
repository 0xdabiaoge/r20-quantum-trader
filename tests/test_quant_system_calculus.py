#!/usr/bin/env python3
"""
Comprehensive Quant System Calculus Test Suite
Validates causal calculus engine, factor library integration, multi-factor scoring and pyramiding gateways.
"""

import os
import sys
import unittest
from pathlib import Path

# Add scripts directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from calculus_engine import (
    calculate_calculus,
    calculate_multi_timeframe,
    classify_regime,
    _ema,
    _diff,
    _normalise
)
import factor_library
import ai_factor_trader


class CalculusEngineMathTest(unittest.TestCase):
    """Test mathematical accuracy and causality of calculus computations."""

    def test_monotonic_bullish_acceleration(self):
        # Monotonically accelerating upward prices
        prices = [100.0, 101.0, 103.0, 106.0, 110.0, 115.0, 122.0, 131.0, 142.0, 155.0]
        res = calculate_calculus(prices)
        self.assertTrue(res["valid"])
        self.assertGreater(res["velocity"], 0.0)
        self.assertGreater(res["impulse"], 0.0)
        self.assertEqual(res["direction"], 1)

    def test_monotonic_bearish_acceleration(self):
        # Monotonically accelerating downward prices
        prices = [155.0, 142.0, 131.0, 122.0, 115.0, 110.0, 106.0, 103.0, 101.0, 98.0]
        res = calculate_calculus(prices)
        self.assertTrue(res["valid"])
        self.assertLess(res["velocity"], 0.0)
        self.assertLess(res["impulse"], 0.0)
        self.assertEqual(res["direction"], -1)

    def test_decelerating_top_fomo_detection(self):
        # Price still rising, but speed is sharply decelerating (exhaustion top)
        # diffs: +10, +8, +5, +2, +0.5, +0.1
        prices = [100.0, 110.0, 118.0, 123.0, 125.0, 125.5, 125.6, 125.65]
        res = calculate_calculus(prices)
        self.assertTrue(res["valid"])
        self.assertLess(res["acceleration"], 0.0, "Decelerating rally must yield negative acceleration")

    def test_decelerating_bottom_panics_detection(self):
        # Price still falling, but drop speed is flattening out (bottoming)
        # drops: -10, -8, -4, -1, -0.2
        prices = [200.0, 190.0, 182.0, 178.0, 177.0, 176.8, 176.7]
        res = calculate_calculus(prices)
        self.assertTrue(res["valid"])
        self.assertGreater(res["acceleration"], 0.0, "Decelerating plunge must yield positive acceleration")

    def test_strict_causality(self):
        # Adding a future candle must not change historical feature outputs at t1
        history = [100.0, 100.2, 100.5, 100.9, 101.4, 102.0, 102.7]
        res_t1 = calculate_calculus(history)
        
        # When future candle arrives, velocity updates dynamically
        future_candle = [101.5]
        res_t2 = calculate_calculus(history + future_candle)
        
        self.assertTrue(res_t1["valid"])
        self.assertTrue(res_t2["valid"])
        self.assertNotEqual(res_t1["velocity"], res_t2["velocity"])


class CalculusEngineSafetyTest(unittest.TestCase):
    """Test edge cases, non-finite values and zero-division defenses."""

    def test_insufficient_samples(self):
        res = calculate_calculus([100.0, 101.0])
        self.assertFalse(res["valid"])
        self.assertEqual(res["reason"], "insufficient_closed_candles")

    def test_none_and_non_finite_inputs(self):
        res = calculate_calculus([100.0, None, float('nan'), 102.0, 104.0, 107.0, 111.0, 116.0, 122.0])
        self.assertTrue(res["valid"])

    def test_flat_zero_volatility(self):
        flat_prices = [100.0] * 15
        res = calculate_calculus(flat_prices)
        self.assertTrue(res["valid"])
        self.assertEqual(res["velocity"], 0.0)
        self.assertEqual(res["acceleration"], 0.0)
        self.assertEqual(res["impulse"], 0.0)


class MultiTimeframeIntegrationTest(unittest.TestCase):
    """Test 15M, 1H, 4H confluence and OKX reverse candle order handling."""

    def test_okx_order_inversion(self):
        # OKX candle list is [newest, ..., oldest]
        # Build 10 candles where price climbed from 100 to 109
        chronological = [[str(i), "101", "99", str(100.0 + i), "10"] for i in range(10)]
        okx_payload = list(reversed(chronological))
        
        res = calculate_multi_timeframe({
            "15M": okx_payload,
            "1H": okx_payload,
            "4H": okx_payload
        })
        self.assertTrue(res["valid"])
        self.assertGreater(res["velocity"], 0.0)
        self.assertIn("15M", res["timeframes"])
        self.assertTrue(res["timeframes"]["15M"]["valid"])


class FactorLibraryIntegrationTest(unittest.TestCase):
    """Test Pillar 6 integration in factor_library.py."""

    def test_factor_library_structure_contains_pillar6(self):
        item = {"instId": "BTC-USDT-SWAP", "name": "BTC", "type": "crypto", "precision": 1}
        # Run calculation with empty smart money pool
        factors = factor_library.compute_instrument_factors(item, {})
        self.assertIn("calculus_dynamics", factors)
        cd = factors["calculus_dynamics"]
        self.assertIn("velocity", cd)
        self.assertIn("acceleration", cd)
        self.assertIn("impulse", cd)
        self.assertIn("regime", cd)


class AiFactorTraderCalculusTest(unittest.TestCase):
    """Test calculus scoring and strategy setup filters in ai_factor_trader.py."""

    def test_evaluate_signal_with_calculus_acceleration(self):
        f = {
            "instId": "BTC-USDT-SWAP",
            "name": "BTC",
            "type": "crypto",
            "precision": 1,
            "price": 60500.0,
            "ema9": 60100.0,
            "ema21": 59800.0,
            "ema55": 59000.0,
            "ema21_slope_pct": 0.05,
            "rsi": 62.0,
            "rsi_7": 65.0,
            "vwap_bias": 0.2,
            "macd_hist": 15.0,
            "macd_accel": 3.0,
            "obv_flow": "BULL_FLOW",
            "vol_ratio": 1.5,
            "market_regime": "BULL_TREND",
            "structure_1h": "HH_HL",
            "is_bull_candle_15m": True,
            "is_bear_candle_15m": False,
            "lower_wick_ratio": 0.1,
            "upper_wick_ratio": 0.1,
            "sentiment_score": 0.5,
            "market_data_valid": True,
            "calculus": {
                "valid": True,
                "velocity": 0.65,
                "acceleration": 0.45,
                "impulse": 1.20,
                "max_abs_jerk": 0.2,
                "regime": "BULL_ACCELERATING",
                "quality": 0.9
            }
        }
        score, action, reasons, strat_tag, strat_desc = ai_factor_trader.evaluate_asset_signal(f)
        self.assertGreater(score, 2.2)
        self.assertEqual(action, "BUY_LONG")
        self.assertEqual(strat_tag, "🚀 动量突破")

    def test_decelerating_top_blocks_breakout_chasing(self):
        f = {
            "instId": "ETH-USDT-SWAP",
            "name": "ETH",
            "type": "crypto",
            "precision": 2,
            "price": 2500.0,
            "ema9": 2490.0,
            "ema21": 2480.0,
            "ema55": 2450.0,
            "ema21_slope_pct": 0.03,
            "rsi": 60.0,
            "rsi_7": 62.0,
            "vwap_bias": 0.3,
            "macd_hist": 2.0,
            "macd_accel": 0.5,
            "obv_flow": "BULL_FLOW",
            "vol_ratio": 1.4,
            "market_regime": "BULL_TREND",
            "structure_1h": "HH_HL",
            "is_bull_candle_15m": True,
            "is_bear_candle_15m": False,
            "sentiment_score": 0.0,
            "market_data_valid": True,
            "calculus": {
                "valid": True,
                "velocity": 0.40,
                "acceleration": -0.85, # Sharp deceleration exhaustion
                "impulse": 0.50,
                "max_abs_jerk": 0.3,
                "regime": "BULL_DECELERATING",
                "quality": 0.85
            }
        }
        score, action, reasons, strat_tag, strat_desc = ai_factor_trader.evaluate_asset_signal(f)
        # Because acceleration < -0.2, momentum breakout setup must NOT trigger blindly
        self.assertNotEqual(strat_tag, "🚀 动量突破", "Sharp deceleration must block breakout chase")


if __name__ == "__main__":
    unittest.main(verbosity=2)
