#!/usr/bin/env python3
"""
R20 AI Brain Six-Crypto Quantitative Trading Decision Engine (ai_brain_trader.py)
Batch ingests six crypto perpetuals into one macro-context LLM call.
Maintains a validated live decision cache and durable Web audit history.
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import subprocess
import tempfile
import fcntl
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

WORKSPACE_DIR = "/app/working/workspaces/default"
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
AI_DECISION_CACHE_FILE = os.path.join(DATA_DIR, "ai_brain_decisions.json")
AI_DECISION_HISTORY_FILE = os.path.join(DATA_DIR, "ai_brain_history.json")
AI_POSITION_MANAGEMENT_FILE = os.path.join(DATA_DIR, "ai_position_management.json")
AI_LAST_PROMPT_FILE = os.path.join(DATA_DIR, "ai_brain_last_prompt.txt")
FACTOR_LIBRARY_FILE = os.path.join(DATA_DIR, "factor_library_snapshot.json")
NEWS_SENTIMENT_FILE = os.path.join(DATA_DIR, "news_sentiment.json")
AI_MEMORY_MD_FILE = os.path.join(DATA_DIR, "AI_TRADING_MEMORY.md")
CALCULUS_SNAPSHOT_FILE = os.path.join(DATA_DIR, "calculus_snapshot.json")
AI_MEMORY_FILE = os.path.join(DATA_DIR, "ai_trading_memory.json")
AI_BRAIN_LOCK_FILE = os.path.join(DATA_DIR, ".ai_brain_cycle.lock")
DECISION_MAX_AGE_SECONDS = 300

TARGET_INSTRUMENTS = [
    {"instId": "BTC-USDT-SWAP", "name": "BTC", "type": "crypto", "ccy": "BTC", "precision": 1},
    {"instId": "ETH-USDT-SWAP", "name": "ETH", "type": "crypto", "ccy": "ETH", "precision": 2},
    {"instId": "SOL-USDT-SWAP", "name": "SOL", "type": "crypto", "ccy": "SOL", "precision": 2},
    {"instId": "DOGE-USDT-SWAP", "name": "DOGE", "type": "crypto", "ccy": "DOGE", "precision": 4},
    {"instId": "SUI-USDT-SWAP", "name": "SUI", "type": "crypto", "ccy": "SUI", "precision": 4},
    {"instId": "LINK-USDT-SWAP", "name": "LINK", "type": "crypto", "ccy": "LINK", "precision": 3},
]

def atomic_write_json(path: str, payload: Any) -> None:
    """Replace JSON atomically so readers never observe a partial cache."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".ai-brain-", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def single_brain_cycle(func):
    """Prevent overlapping cron runs from overwriting the shared decision cache."""
    def wrapped(*args, **kwargs):
        os.makedirs(DATA_DIR, exist_ok=True)
        lock_handle = open(AI_BRAIN_LOCK_FILE, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_handle.close()
            print("[AI Brain Batch] Skip: another inference cycle is still running")
            return None
        try:
            lock_handle.seek(0)
            lock_handle.truncate()
            lock_handle.write(str(os.getpid()))
            lock_handle.flush()
            return func(*args, **kwargs)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
    return wrapped


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else default
    except (TypeError, ValueError):
        return default


def get_cpa_client_config() -> Tuple[str, str]:
    """Dynamically resolve LLM API base URL and API Key from environment or local encrypted vault."""
    # 1. First priority: standard environment variables
    env_base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    env_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if env_base_url and env_api_key:
        return env_base_url, env_api_key

    # 2. Second priority: QwenPaw encrypted secret store (if available locally)
    try:
        sys.path.append("/app/venv/lib/python3.11/site-packages")
        from qwenpaw.security.secret_store import decrypt
        secret_file = "/app/working.secret/providers/custom/cpa.json"
        if os.path.exists(secret_file):
            with open(secret_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            api_key = decrypt(d.get("api_key", "")) if d.get("api_key") else ""
            base_url = d.get("base_url", "https://api.openai.com/v1")
            return base_url, api_key
    except Exception as e:
        print(f"[AI Brain] Warning loading local secret store: {e}")

    return env_base_url or "https://api.openai.com/v1", env_api_key or ""

def fetch_single_instrument_package(item: Dict[str, Any]) -> Dict[str, Any]:
    inst_id = item["instId"]
    name = item["name"]
    ccy = item.get("ccy", "")
    headers = {"User-Agent": "Mozilla/5.0"}
    
    pkg = {
        "instId": inst_id,
        "name": name,
        "type": item["type"],
        "precision": item["precision"],
        "price": 0.0,
        "chg24h": 0.0,
        "bidPx": 0.0,
        "askPx": 0.0,
        "fundingRate": 0.0,
        "oiUsd": "N/A",
        "lsRatio": "N/A",
        "takerNetUsd": "N/A",
        "atr": 0.0,
        "rsi": 50.0,
        "vwap_bias": 0.0,
        "macd_hist": 0.0,
        "macd_accel": 0.0,
        "vol_ratio": 1.0,
        "obv_flow": "NEUTRAL",
        "adx_1h": 0.0,
        "smart_money": {
            "weighted_long_pct": 50.0,
            "net_flow_usdt": "0 U",
            "avg_long_entry": "--",
            "avg_short_entry": "--",
            "top_win_rate": "--"
        },
        "recent_15m": [],
        "recent_1h": [],
        "recent_4h": [],
        "calculus": {"valid": False, "regime": "DATA_UNRELIABLE", "quality": 0.0},
        "data_quality": "invalid"
    }

    # 1. Ticker
    try:
        req = urllib.request.Request(f"https://www.okx.com/api/v5/market/ticker?instId={inst_id}", headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("code") == "0" and d.get("data"):
                t = d["data"][0]
                pkg["price"] = float(t.get("last", 0))
                pkg["bidPx"] = float(t.get("bidPx", pkg["price"]) or pkg["price"])
                pkg["askPx"] = float(t.get("askPx", pkg["price"]) or pkg["price"])
                op = float(t.get("open24h", 0) or 0)
                pkg["chg24h"] = round(((pkg["price"] - op) / op * 100) if op > 0 else 0, 2)
    except Exception:
        pass

    # 2. 15M Candles (recent 24, about 6 hours) & Technical Indicators Calculation
    try:
        req = urllib.request.Request(f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=15m&limit=24", headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("code") == "0" and d.get("data"):
                raw_candles = d["data"]
                pkg["recent_15m"] = [[float(c[1]), float(c[2]), float(c[3]), float(c[4]), round(float(c[5]), 1)] for c in raw_candles[:12]]
                
                # Calculate indicators
                if len(raw_candles) >= 15:
                    closes = [float(c[4]) for c in reversed(raw_candles)]
                    highs = [float(c[2]) for c in reversed(raw_candles)]
                    lows = [float(c[3]) for c in reversed(raw_candles)]
                    vols = [float(c[5]) for c in reversed(raw_candles)]

                    # ATR 14
                    tr_list = []
                    for i in range(1, len(closes)):
                        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
                        tr_list.append(tr)
                    if len(tr_list) >= 14:
                        pkg["atr"] = round(sum(tr_list[-14:]) / 14, 4)

                    # RSI 14
                    diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                    gains = [d if d > 0 else 0 for d in diffs]
                    losses = [-d if d < 0 else 0 for d in diffs]
                    if len(gains) >= 14:
                        avg_g = sum(gains[-14:]) / 14
                        avg_l = sum(losses[-14:]) / 14
                        rs = (avg_g / avg_l) if avg_l > 0 else 100.0
                        pkg["rsi"] = round(100.0 - (100.0 / (1.0 + rs)), 1)

                    # VWAP Bias
                    pv_sum = sum(closes[i] * vols[i] for i in range(len(closes)))
                    v_sum = sum(vols)
                    if v_sum > 0:
                        vwap = pv_sum / v_sum
                        pkg["vwap_bias"] = round((pkg["price"] - vwap) / vwap * 100, 2)

                    # Volume Ratio (Last vs MA5)
                    if len(vols) >= 6:
                        avg_v5 = sum(vols[-6:-1]) / 5
                        if avg_v5 > 0:
                            pkg["vol_ratio"] = round(vols[-1] / avg_v5, 2)

                    # OBV Flow
                    obv = 0
                    for i in range(1, len(closes)):
                        if closes[i] > closes[i-1]:
                            obv += vols[i]
                        elif closes[i] < closes[i-1]:
                            obv -= vols[i]
                    pkg["obv_flow"] = "BULL_FLOW" if obv > 0 else ("BEAR_FLOW" if obv < 0 else "NEUTRAL")
    except Exception:
        pass

    # 3. 1H Candles (recent 8)
    try:
        req = urllib.request.Request(f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=1H&limit=8", headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("code") == "0" and d.get("data"):
                pkg["recent_1h"] = [[float(c[1]), float(c[2]), float(c[3]), float(c[4]), round(float(c[5]), 1)] for c in d["data"]]
    except Exception:
        pass

    # 4. 4H Candles (recent 6, about 24 hours)
    try:
        req = urllib.request.Request(f"https://www.okx.com/api/v5/market/candles?instId={inst_id}&bar=4H&limit=6", headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            if d.get("code") == "0" and d.get("data"):
                pkg["recent_4h"] = [[float(c[1]), float(c[2]), float(c[3]), float(c[4]), round(float(c[5]), 1)] for c in d["data"]]
    except Exception:
        pass

    # 5. Funding Rate & OI
    if item["type"] == "crypto":
        try:
            req = urllib.request.Request(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst_id}", headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                d = json.loads(resp.read().decode("utf-8"))
                if d.get("code") == "0" and d.get("data"):
                    pkg["fundingRate"] = round(float(d["data"][0].get("fundingRate", 0)) * 100, 4)
        except Exception:
            pass

        try:
            req = urllib.request.Request(f"https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId={inst_id}", headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                d = json.loads(resp.read().decode("utf-8"))
                if d.get("code") == "0" and d.get("data"):
                    usd = float(d["data"][0].get("oiUsd", 0) or 0)
                    pkg["oiUsd"] = f"{round(usd / 1e8, 2)}亿 U" if usd > 1e8 else f"{round(usd / 1e4, 1)}万 U"
        except Exception:
            pass

        if ccy:
            try:
                req = urllib.request.Request(f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy={ccy}&period=5m", headers=headers)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    d = json.loads(resp.read().decode("utf-8"))
                    if d.get("code") == "0" and d.get("data") and len(d["data"]) > 0:
                        pkg["lsRatio"] = float(d["data"][0][1])
            except Exception:
                pass

            try:
                req = urllib.request.Request(f"https://www.okx.com/api/v5/rubik/stat/taker-volume?ccy={ccy}&instType=CONTRACTS&period=5m", headers=headers)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    d = json.loads(resp.read().decode("utf-8"))
                    if d.get("code") == "0" and d.get("data") and len(d["data"]) > 0:
                        b_vol = float(d["data"][0][1])
                        s_vol = float(d["data"][0][2])
                        net_diff = b_vol - s_vol
                        pkg["takerNetUsd"] = f"{round(net_diff / 1e4, 1)}万 U"
            except Exception:
                pass

        # 6. OKX ADX Trend Strength Indicator (1H)
        try:
            cmd = f"okx market indicator adx {inst_id} --bar 1H --json 2>/dev/null"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            if res.stdout:
                ind_data = json.loads(res.stdout)
                if isinstance(ind_data, list) and ind_data:
                    adx_vals = ind_data[0].get("data", [{}])[0].get("timeframes", {}).get("1H", {}).get("indicators", {}).get("ADX", [])
                    if adx_vals:
                        pkg["adx_1h"] = float(adx_vals[0].get("values", {}).get("adx", 0.0) or 0.0)
        except Exception:
            pass

    required_market_data = (
        pkg["price"] > 0
        and pkg["bidPx"] > 0
        and pkg["askPx"] >= pkg["bidPx"]
        and len(pkg["recent_15m"]) >= 12
        and len(pkg["recent_1h"]) >= 8
        and len(pkg["recent_4h"]) >= 6
    )
    try:
        from calculus_engine import calculate_multi_timeframe
        pkg["calculus"] = calculate_multi_timeframe({
            "15M": pkg["recent_15m"],
            "1H": pkg["recent_1h"],
            "4H": pkg["recent_4h"],
        })
    except Exception as exc:
        pkg["calculus"] = {"valid": False, "regime": "DATA_UNRELIABLE", "quality": 0.0, "error": str(exc)}
    pkg["data_quality"] = "valid" if required_market_data else "invalid"
    return pkg

SYSTEM_PROMPT = """你是一名管理顶级加密量化对冲基金的首席AI交易官。
你的职责：在一次扫描中全景综合 OKX 六大加密永续合约的原生多周期K线(4H/1H/15M)、OKX官方顶级聪明钱(SmartMoney Top100)实盘胜率与持仓成本、三大核心数理底座【因果微积分动力学(速度v/加速度a/冲量I/冲击jerk) + 定积分能量与偏离面积(净做功/VWAP偏离面积) + 概率论与随机过程(条件延续胜率%/95%VaR/偏度峰度肥尾)】、即时盘口深度、衍生品筹码(资金费率/OI未平仓量/多空比/Taker主动买卖)、量化多因子指标(ADX趋势强度/ATR/RSI/VWAP偏离/量比/OBV)以及当前账户可用USDT余额与已有持仓，给出具有精确保证金分配、杠杆倍数设定、多空方向裁决与盈亏比≥2.0止盈止损点位的完整交易与持仓决策。

核心交易准则与高胜率铁律：
1. 顶级聪明钱 (SmartMoney) 方向对齐：
   - 重点参考 OKX 实盘 80%+ 胜率聪明钱的主力加权多空比与 24H 资金净流入；
   - 严禁逆全网顶级聪明钱主力大势盲目重仓开单；在聪明钱建仓成本价附近寻找高确定性共振点位。
2. 📐 三大底层数理基石 (Calculus, Integrals & Probability) 综合判定铁律：
   - 【微积分动力学 (Calculus Dynamics)】：
     • 速度 v 反映即时价格位移速率，冲量 I 反映多周期累计惯性；
     • 📈 扩张加速 (BULL_ACCELERATING, a > +0.10)：动能持续放大，允许积极捕捉突破或顺势加仓；
     • ⚠️ 顶部失速减速 (BULL_DECELERATING, a < -0.20)：价格虽涨但动能急剧失速衰竭，【坚决禁止追涨开多】，等待回踩企稳；
     • 📉 破位下泄加速 (BEAR_ACCELERATING, a < -0.10)：空头动能加速下泄，顺势破位做空；
     • 🛡️ 底部减速企稳 (BEAR_DECELERATING, a > +0.20)：砸盘动能衰减钝化，【坚决禁止追空】，防范 V 型反弹；
     • 🌪️ 冲击加加速度 jerk 防御：若出现高冲击异动 (|jerk| ≥ 1.8 或 SHOCK_HIGH_JERK)，代表遭遇极端异动洗盘，强制降低仓位或观望(WAIT)。
   - 【定积分能量与偏离面积 (Definite Integrals & Work Done)】：
     • 动能净做功定积分 (energy_integral > 0)：衡量多头历史做功累计的真实能量储备；
     • 均值偏离面积定积分 (deviation_area_integral)：衡量价格偏离价值中枢的累计拉伸面积；若偏离面积严重过载 (|area| ≥ 2.5)，强烈提示均值回归引力，切忌在拉伸末端追单。
   - 【概率论与随机过程 (Probability & Extreme Value Risk)】：
     • 条件延续概率 (continuation_prob_pct ≥ 70%)：基于分布函数计算的多头顺势确定性，给予多头强赋能；
     • 条件击穿概率 (breakdown_prob_pct ≥ 70%)：空头破位确定性；
     • 极端肥尾与在险价值 (Kurtosis ≥ 1.5, 95% VaR & CVaR)：若出现严重非对称偏度或超额厚尾，必须严格按 VaR 风险边界收缩单笔保证金与杠杆倍数。
3. 趋势强度硬过滤 (ADX 过滤器)：
   - 若 1H ADX < 20 (表明当前处于无量窄幅拉锯的垃圾震荡市)，必须坚决观望(WAIT)，彻底杜绝假突破与反复止损磨损；
   - 若 1H ADX ≥ 22 且伴随放量、微积分加速度与价格共振，方可积极捕捉主升/破位趋势。
4. 追求极致风险收益比 (Risk/Reward ≥ 2.0)：入场位、止盈位与止损位必须逻辑自洽，空间测算严密。
5. 动态自适应头寸与杠杆规划：
   - 必须结合当前账户可用USDT余额 (usdt_available) 规划拟投入保证金 (margin_usdt)，单笔保证金建议为可用余额的 5% ~ 20%，不可超负荷孤注一掷。
   - 杠杆倍数 (leverage) 需依据市场波动率(ATR)与置信度动态决定：高波动标的(SUI/DOGE)建议 2x~3x，主流低波标的(BTC/ETH)可 3x~5x，严禁过高杠杆。
6. 任何关键行情缺失、标记为 DATA_INVALID、价格结构不合法或无法计算真实 R:R 时，必须 WAIT；不得猜测缺失数据。
7. 长期记忆、偏好标的和历史胜率只能作为弱先验，绝不得覆盖本轮原始行情、持仓风险和硬门禁。
8. 顺势浮盈金字塔加仓 (Pyramiding) 准则：
   - 对于已有持仓标的，若底仓已处于保本/显著浮盈状态（ROI ≥ +0.8% 或已推保本止损），且盘面出现强劲的二浪突破、动量延续、微积分加速度为正(a ≥ 0)、多头延续概率 ≥ 40% 且聪明钱持续加码，允许在 decisions 中输出同向开仓指令（如多单输出 BUY_LONG 顺势加多 / 空单输出 SELL_SHORT 顺势加空），单次加仓仓位建议 ≤ 底仓，置信度需 ≥ 75%；
   - 严禁对处于浮亏、未脱离成本区或动能失速减速(a < 0)的仓位进行任何形式的逆势补仓（Averaging Down）。
9. 必须认真审查在途未成交限价挂单 (pending_orders)：若行情已大幅偏离、市场逻辑反转或挂单已过时，必须在 pending_orders_management 中果断输出 CANCEL 撤单指令，防止挂单成交在不利位置；有效挂单输出 KEEP 维持。
10. 必须输出严格标准 JSON 对象，包含全市场宏观评估(macro_assessment)、在途持仓管理(position_management)、在途挂单管理(pending_orders_management)与针对每个标的的决策字典(decisions)。
"""

def construct_full_market_prompt(packages: List[Dict[str, Any]], pos_summary: str = "当前总持仓 0/6", active_positions_detail: List[Dict[str, Any]] = None, pending_orders_detail: List[Dict[str, Any]] = None, current_time_str: str = "", usdt_available: float = 0.0) -> str:
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj_str = current_time_str or datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S (北京时间)")
    market_lines = []
    for p in packages:
        k15 = p.get("recent_15m", [])
        k1h = p.get("recent_1h", [])
        k4h = p.get("recent_4h", [])
        quality = p.get("data_quality", "invalid")
        
        sm = p.get("smart_money", {})
        adx_val = p.get("adx_1h", "--")
        calc = p.get("calculus", {})
        calc_tfs = calc.get("timeframes", {}) if isinstance(calc, dict) else {}
        d_int = calc.get("definite_integrals", {}) if isinstance(calc, dict) else {}
        p_th = calc.get("probability_theory", {}) if isinstance(calc, dict) else {}

        calc_line = (
            f"动力学态={calc.get('regime', 'DATA_UNRELIABLE')} | 速度={calc.get('velocity', '--')} "
            f"| 加速度={calc.get('acceleration', '--')} | 累计冲量={calc.get('impulse', '--')} "
            f"| 冲击变化={calc.get('max_abs_jerk', '--')} | 质量={calc.get('quality', 0)}"
        )
        integral_line = (
            f"动能净做功积分={d_int.get('energy_integral', '--')} | VWAP偏离面积分={d_int.get('deviation_area_integral', '--')} "
            f"| 量能功率积分={d_int.get('volume_action_integral', '--')} | 能量态={d_int.get('regime', 'BALANCED')}"
        )
        prob_line = (
            f"多头延续胜率={p_th.get('continuation_prob_pct', 50)}% | 空头击穿概率={p_th.get('breakdown_prob_pct', 50)}% "
            f"| 偏度S={p_th.get('skewness', 0)} | 超额峰度K={p_th.get('kurtosis', 0)} | 95%在险价值VaR={p_th.get('var_95_pct', '--')}% "
            f"| 尾部风险={p_th.get('regime', 'BALANCED')}"
        )
        calc_tf_line = "；".join(
            f"{tf}:v={v.get('velocity', '--')},a={v.get('acceleration', '--')},I={v.get('impulse', '--')},态={v.get('regime', '--')}"
            for tf, v in calc_tfs.items() if isinstance(v, dict)
        )
        info = f"""---------------------------------------------------------
【{p['name']} ({p['instId']})】| 数据质量: {quality} | 现价: {p['price']} | 24H涨跌: {p['chg24h']}% | 盘口买/卖: {p['bidPx']}/{p['askPx']}
- 👑 顶级聪明钱 (SmartMoney Top100): 加权做多占比={sm.get('weighted_long_pct', 50)}% | 24H净流入={sm.get('net_flow_usdt', '--')} | 多头均价={sm.get('avg_long_entry', '--')} | 空头均价={sm.get('avg_short_entry', '--')} | {sm.get('top_win_rate', '')}
- 📐 量化趋势与因子: 1H ADX趋势强度={adx_val} (注:<20无趋势垃圾市, ≥22强单边) | ATR(14)={p.get('atr', '--')} | RSI(14)={p.get('rsi', '--')} | VWAP乖离={p.get('vwap_bias', '--')}% | 15M量比={p.get('vol_ratio', '--')}x | OBV资金流={p.get('obv_flow', '--')}
- ∫ 微积分与定积分: {calc_line}
- ⚡ 能量与偏离面积分: {integral_line}
- ⚅ 概率论与统计分布: {prob_line}
- ∂ 分周期速度/加速度/冲量: {calc_tf_line or '数据不足'}
- 衍生品博弈: 资金费率: {p['fundingRate']}% | OI未平仓: {p['oiUsd']} | 多空比: {p['lsRatio']} | 5M主动吃单净差: {p['takerNetUsd']}
- 15M K线(倒序12根 [O,H,L,C,V]): {k15}
- 1H K线(倒序8根 [O,H,L,C,V]): {k1h}
- 4H K线(倒序6根 [O,H,L,C,V]): {k4h}"""
        market_lines.append(info)

    all_market_str = "\n".join(market_lines)
    
    pos_lines = []
    if active_positions_detail and len(active_positions_detail) > 0:
        for p in active_positions_detail:
            pos_lines.append(
                f"- 标的: {p.get('name') or p.get('instId')} | 方向: {p.get('side')} {p.get('lever', '3')}x | 开仓均价: {p.get('avgPx')} | 当前标记价: {p.get('markPx', p.get('lastPx'))} | 持仓量: {p.get('pos')}张 | 未结浮盈: {p.get('upl')} U (ROI: {round(safe_float(p.get('uplRatio')) * 100, 2)}%) | 动态止损线: {p.get('trailingStopPx', p.get('trailingSl', '--'))}"
            )
    else:
        pos_lines.append("当前无任何在途持仓敞口 (100% 现金空仓状态)")
    
    active_pos_text = "\n".join(pos_lines)

    # Format Pending Limit Orders
    pending_lines = []
    if pending_orders_detail and len(pending_orders_detail) > 0:
        for o in pending_orders_detail:
            c_ts = int(o.get("cTime", 0) or 0) / 1000.0
            c_time_str = datetime.datetime.fromtimestamp(c_ts, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S") if c_ts > 0 else "--"
            inst_id = o.get("instId", "")
            side_str = "限价买多" if o.get("side") == "buy" and o.get("posSide") == "long" else ("限价卖空" if o.get("side") == "sell" and o.get("posSide") == "short" else f"{o.get('side')} {o.get('posSide')}")
            px_val = o.get("px", "--")
            sz_val = o.get("sz", "--")
            ord_id = o.get("ordId", "")
            
            attach_list = o.get("attachAlgoOrds", [])
            tp_sl_info = ""
            if attach_list and len(attach_list) > 0:
                att = attach_list[0]
                tp_p = att.get("tpTriggerPx", "--")
                sl_p = att.get("slTriggerPx", "--")
                tp_sl_info = f" | 附带云端止盈: {tp_p} / 止损: {sl_p}"
            
            pending_lines.append(
                f"- [挂单ID: {ord_id}] {inst_id} | {side_str} {sz_val}张 @ {px_val} | 挂单时间: {c_time_str}{tp_sl_info}"
            )
    else:
        pending_lines.append("当前无任何在途未成交限价挂单 (挂单池为空)")
    
    pending_orders_text = "\n".join(pending_lines)

    memory_lessons = ""
    # Priority 1: Read Human/LLM Markdown Memory (QwenPaw-native)
    if os.path.exists(AI_MEMORY_MD_FILE):
        try:
            with open(AI_MEMORY_MD_FILE, "r", encoding="utf-8") as f:
                md_text = f.read().strip()
                if md_text:
                    memory_lessons = f"""======================= 【QwenPaw 启发式实战认知与长期记忆 (Markdown)】 =======================
{md_text}
"""
        except Exception:
            pass
    elif os.path.exists(AI_MEMORY_FILE):
        try:
            with open(AI_MEMORY_FILE, "r", encoding="utf-8") as f:
                mem = json.load(f)
                lessons = mem.get("core_lessons", [])
                if lessons:
                    formatted_lessons = "\n".join([f"  • {item}" for item in lessons])
                    memory_lessons = f"""======================= 【QwenPaw 启发式实战认知与长期记忆】 =======================
【每日复盘提炼的心法与直觉提示词 (供决策参考，不设死板禁令)】:
{formatted_lessons}
"""
        except Exception:
            pass

    # Harvest Latest Live News & Multi-Coin Sentiment
    news_briefs = []
    macro_env = "中性平衡"
    if os.path.exists(NEWS_SENTIMENT_FILE):
        try:
            with open(NEWS_SENTIMENT_FILE, "r", encoding="utf-8") as f:
                ns_data = json.load(f)
                macro_env = ns_data.get("macro_sentiment", "中性平衡")
                for n in ns_data.get("latest_news", [])[:6]:
                    news_briefs.append(f"- [{n.get('time', '')}] {n.get('title', '')} ({n.get('summary', '')[:80]}...)")
        except Exception:
            pass

    news_text = "\n".join(news_briefs) if news_briefs else "暂无突发重大新闻，市场流动性平稳"

    avail_balance_str = f"{usdt_available:.2f} USDT" if usdt_available > 0 else "根据系统风险自适应分配"

    prompt = f"""======================= 【当前决策时间戳与市场时效】 =======================
【推演基准时间】: {now_bj_str}
【当前账户可用资金】: {avail_balance_str}

======================= 【全网实时重大快讯与宏观情报】 =======================
【宏观环境基调】: {macro_env}
【最新核心资讯要闻】:
{news_text}

======================= 【账户当前持仓与风险敞口全景】 =======================
【账户持仓概况】: {pos_summary}
【当前活动在途持仓明细】:
{active_pos_text}

======================= 【在途未成交限价挂单 (Pending Maker Orders)】 =======================
【当前在途挂单列表】:
{pending_orders_text}

{memory_lessons}

======================= 【六币种原生行情、技术指标与筹码矩阵】 =======================
{all_market_str}

================================================================================
【推演与决策任务】:
你拥有【最高决策主权】，请不要受任何单一死板指标的束缚，全权由你作为首席交易官根据上述【全网快讯资讯】、【多周期K线形态】、【盘口深度】与【聪明钱资金流向】进行综合直觉与量化推演：
1. 【在途持仓管理】：对当前已有持仓逐一分析（如 LINK/ETH 等）：当前行情动能如何？是继续持有(HOLD)、提止损保本、止盈平仓(CLOSE)、还是逢高/破位止损平仓？给出持仓调整策略。
2. 【在途限价挂单生命周期审查与裁决 (Pending Orders Management)】：
   - 仔细审查上述在途未成交挂单：若挂单价格已大幅偏离最新盘口、或者行情动能/突发要闻已转变导致原挂单计划失效，必须在 pending_orders_management 中为该挂单输出 CANCEL 立即撤单指令，防止挂单成交在不利价格；若原计划仍然有效且价格合适，输出 KEEP 维持挂单。
3. 【多空开仓与顺势浮盈加仓全权裁决 (Opening & Pyramiding)】：
   - 【首发开仓】：自主判断未持仓品种是否具备确定性爆发机会，结合最新资讯、多周期形态与筹码，决定多空方向 (action: BUY_LONG / SELL_SHORT / WAIT)；
   - 【顺势浮盈金字塔加仓 (Pyramiding)】：对当前已有持仓（如 ETH/LINK），若底仓已处于显著浮盈/保本状态且盘面出现强劲二浪突破，允许在 decisions 中输出同向开仓指令（如多单输出 BUY_LONG 顺势加多），系统将执行科学金字塔加仓；浮亏或未脱离成本区的仓位严禁逆势补仓；
   - 自主规划拟开仓/加仓保证金 (margin_usdt: 建议可用余额的 5%~20%) 与 杠杆倍数 (leverage: 2~5x)；
   - 自主规划挂单入场价 (entry_price)、止盈触发价 (take_profit_price) 与 止损触发价 (stop_loss_price)，必须满足严密的盈亏比 (R:R ≥ 2.0)。
4. 必须输出严格 JSON，格式如下：
{{
  "macro_assessment": "30字内全市场宏观流动性与情绪总结",
  "position_management": [
    {{
      "instId": "LINK-USDT-SWAP",
      "action": "HOLD" | "CLOSE_MARKET" | "UPDATE_SL",
      "suggested_sl_price": float (若调整止损填具体价格，否则0),
      "confidence": 0~100,
      "reason": "30字内持仓调整原因与当前动能分析"
    }}
  ],
  "pending_orders_management": [
    {{
      "ordId": "3879092142614409217",
      "instId": "LINK-USDT-SWAP",
      "action": "KEEP" | "CANCEL",
      "reason": "30字内撤单或维持挂单原因"
    }}
  ],
  "decisions": {{
    "BTC-USDT-SWAP": {{
      "action": "BUY_LONG" | "SELL_SHORT" | "WAIT",
      "confidence": 0~100,
      "leverage": 3 (推荐杠杆2~5),
      "margin_usdt": 50.0 (推荐保证金),
      "entry_price": float,
      "take_profit_price": float,
      "stop_loss_price": float,
      "summary_reason": "30字内核心逻辑",
      "market_structure": "4H/1H趋势与15M短线形态",
      "calculus_dynamics": "微积分速度/加速度/冲量与动能扩张/衰竭推演简述",
      "math_prob_rationale": "定积分做功能量+延续胜率%+VaR在险价值依据简述",
      "volume_and_oi": "量能/筹码流向简述"
    }},
    ... (依次包含全部标的)
  }}
}}
"""
    return prompt

@single_brain_cycle
def execute_batch_ai_brain_cycle(pos_summary: str = "当前总持仓 0/6", active_positions_detail: List[Dict[str, Any]] = None, usdt_available: float = 0.0) -> Optional[Dict[str, Any]]:
    """Fetch all six crypto symbols, call the LLM once, then persist an auditable result."""
    base_url, api_key = get_cpa_client_config()
    if not api_key:
        print("[AI Brain Batch] Error: CPA API Key not found")
        return None

    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj = datetime.datetime.now(tz_bj)
    time_str = now_bj.strftime("%Y-%m-%d %H:%M:%S")

    print("[AI Brain Batch] 并行获取 6 币种原生行情、技术指标与顶级聪明钱数据...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        packages = list(executor.map(fetch_single_instrument_package, TARGET_INSTRUMENTS))

    # Fetch OKX Smart Money Signals (Top 100 80%+ Winrate Traders)
    try:
        sm_cmd = "okx smartmoney signal-overview-by-filter --instCcyList BTC,ETH,SOL,DOGE,SUI,LINK --json 2>/dev/null"
        sm_res = subprocess.run(sm_cmd, shell=True, capture_output=True, text=True, timeout=8)
        if sm_res.stdout:
            sm_data = json.loads(sm_res.stdout).get("data", [])
            sm_dict = {item.get("ccy"): item for item in sm_data if item.get("ccy")}
            for p in packages:
                ccy = p["name"]
                if ccy in sm_dict:
                    item = sm_dict[ccy]
                    ls = item.get("longShortRatio", {})
                    notional = item.get("notional", {})
                    win = item.get("winRate", {})
                    w_long = round(float(ls.get("weightedLongRatio", 0.5)) * 100, 1)
                    net_usdt = float(notional.get("netNotionalUsdt", 0) or 0)
                    net_flow_str = f"{round(net_usdt / 1e4, 1)}万 U" if abs(net_usdt) >= 1e4 else f"{round(net_usdt, 0)} U"
                    long_cost = notional.get("smartMoneyLongAvgEntry") or "--"
                    short_cost = notional.get("smartMoneyShortAvgEntry") or "--"
                    top_win = f"多胜率{round(float(win.get('avgLongWinRate', 0))*100, 1)}%" if win.get('avgLongWinRate') else "--"

                    p["smart_money"] = {
                        "weighted_long_pct": w_long,
                        "net_flow_usdt": net_flow_str,
                        "avg_long_entry": str(long_cost)[:10],
                        "avg_short_entry": str(short_cost)[:10],
                        "top_win_rate": top_win
                    }
    except Exception as e:
        print(f"[AI Brain Batch] SmartMoney fetch warning: {e}")

    active_positions_detail = active_positions_detail or []
    active_inst_ids = {
        str(p.get("instId", "")) for p in active_positions_detail if p.get("instId")
    }
    package_by_id = {p["instId"]: p for p in packages}

    # Automatically Update & Persist Comprehensive Factor Library Snapshot
    try:
        sys.path.append(os.path.join(WORKSPACE_DIR, "scripts"))
        import factor_library
        factor_library.update_factor_library()
    except Exception as e:
        print(f"[AI Brain Batch] Factor Library update warning: {e}")

    # Fetch live pending limit orders from exchange
    pending_orders_list = []
    try:
        ord_cmd = "okx --demo swap orders --json 2>/dev/null"
        ord_res = subprocess.run(ord_cmd, shell=True, capture_output=True, text=True, timeout=8)
        if ord_res.stdout:
            pending_orders_list = json.loads(ord_res.stdout)
            if not isinstance(pending_orders_list, list):
                pending_orders_list = []
    except Exception as e:
        print(f"[AI Brain Batch] Pending orders fetch warning: {e}")

    try:
        calculus_snapshot = {
            "timestamp": time_str,
            "engine": "causal-calculus-v1",
            "instruments": [
                {"name": p.get("name"), "instId": p.get("instId"), "calculus": p.get("calculus", {})}
                for p in packages
            ],
        }
        tmp_calc = CALCULUS_SNAPSHOT_FILE + ".tmp"
        with open(tmp_calc, "w", encoding="utf-8") as f:
            json.dump(calculus_snapshot, f, ensure_ascii=False, indent=2)
        os.replace(tmp_calc, CALCULUS_SNAPSHOT_FILE)
    except Exception as exc:
        print(f"[AI Brain] Calculus snapshot warning: {exc}")

    prompt = construct_full_market_prompt(packages, pos_summary, active_positions_detail, pending_orders_detail=pending_orders_list, current_time_str=time_str, usdt_available=usdt_available)
    
    # Save Realtime Prompt Snapshot for Web Transparent Inspection
    try:
        tmp_prompt = AI_LAST_PROMPT_FILE + ".tmp"
        with open(tmp_prompt, "w", encoding="utf-8") as f:
            f.write(f"【SYSTEM PROMPT】:\n{SYSTEM_PROMPT.strip()}\n\n{'='*70}\n【USER PROMPT ({time_str})】:\n{prompt.strip()}")
        os.replace(tmp_prompt, AI_LAST_PROMPT_FILE)
    except Exception:
        pass

    payload = {
        "model": "gemini-3.7-flash-high",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "reasoning_effort": "high",
        "temperature": 0.15,
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        t0 = time.time()
        print("[AI Brain Batch] 🚀 正在发起单次全市场大模型宏观决策推演 (Gemini 3.7)...")
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            content = res["choices"][0]["message"]["content"].strip()
            
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
            
            brain_output = json.loads(content.strip())
            if not isinstance(brain_output, dict):
                raise ValueError("LLM response root must be an object")
            decisions_dict = brain_output.get("decisions", {})
            pos_mgmt_list = brain_output.get("position_management", [])
            macro_summary = str(brain_output.get("macro_assessment", "宏观中性震荡"))[:120]
            if not isinstance(decisions_dict, dict):
                decisions_dict = {}
            if not isinstance(pos_mgmt_list, list):
                pos_mgmt_list = []

            validated_pos_mgmt = []
            seen_positions = set()
            for item in pos_mgmt_list:
                if not isinstance(item, dict):
                    continue
                inst_id = str(item.get("instId", ""))
                if inst_id not in active_inst_ids or inst_id in seen_positions:
                    continue
                seen_positions.add(inst_id)
                action = str(item.get("action", "HOLD")).upper()
                if action not in {"HOLD", "CLOSE_MARKET", "UPDATE_SL"}:
                    action = "HOLD"
                confidence = max(0.0, min(100.0, safe_float(item.get("confidence"))))
                suggested_sl = safe_float(item.get("suggested_sl_price"))
                if action != "UPDATE_SL":
                    suggested_sl = 0.0
                validated_pos_mgmt.append({
                    "instId": inst_id,
                    "action": action,
                    "suggested_sl_price": suggested_sl,
                    "confidence": confidence,
                    "reason": str(item.get("reason", "模型未提供持仓理由"))[:120]
                })
            for inst_id in sorted(active_inst_ids - seen_positions):
                validated_pos_mgmt.append({
                    "instId": inst_id,
                    "action": "HOLD",
                    "suggested_sl_price": 0.0,
                    "confidence": 0.0,
                    "reason": "模型遗漏该持仓，安全降级为 HOLD"
                })
            pos_mgmt_list = validated_pos_mgmt

            # Execute Pending Orders Cancellation if AI Brain decides CANCEL
            pending_mgmt_list = brain_output.get("pending_orders_management", [])
            if isinstance(pending_mgmt_list, list):
                for p_order in pending_mgmt_list:
                    if not isinstance(p_order, dict):
                        continue
                    p_act = str(p_order.get("action", "")).upper()
                    p_ord_id = str(p_order.get("ordId", ""))
                    p_inst_id = str(p_order.get("instId", ""))
                    p_reason = str(p_order.get("reason", "模型指示撤销该挂单"))
                    if p_act == "CANCEL" and p_ord_id and p_inst_id:
                        cxl_cmd = f"okx --demo swap cancel {p_inst_id} --ordId {p_ord_id} --json"
                        cxl_res = subprocess.run(cxl_cmd, shell=True, capture_output=True, text=True, timeout=10)
                        print(f"[AI Brain Batch] 🛑 AI自主撤回失效/过时限价单: {p_inst_id} (ordId={p_ord_id}, 原因={p_reason})")

            standard_cache = {}
            for p in packages:
                inst_id = p["instId"]
                d_item = decisions_dict.get(inst_id, {})
                if not isinstance(d_item, dict):
                    d_item = {}
                raw_action = str(d_item.get("action", "WAIT")).upper()
                if raw_action not in {"BUY_LONG", "SELL_SHORT", "WAIT"}:
                    raw_action = "WAIT"
                entry = safe_float(d_item.get("entry_price"))
                take_profit = safe_float(d_item.get("take_profit_price"))
                stop_loss = safe_float(d_item.get("stop_loss_price"))
                confidence = max(0.0, min(100.0, safe_float(d_item.get("confidence"))))
                ai_leverage = int(max(2, min(5, round(safe_float(d_item.get("leverage", 3))))))
                ai_margin = round(safe_float(d_item.get("margin_usdt", 0.0)), 2)
                rr = 0.0
                if raw_action == "BUY_LONG" and entry > stop_loss > 0 and take_profit > entry:
                    rr = (take_profit - entry) / (entry - stop_loss)
                elif raw_action == "SELL_SHORT" and stop_loss > entry > take_profit > 0:
                    rr = (entry - take_profit) / (stop_loss - entry)

                rejection_reason = ""
                if p.get("data_quality") != "valid":
                    rejection_reason = "关键原始行情不完整，安全降级为 WAIT。"
                elif inst_id in active_inst_ids and raw_action != "WAIT":
                    rejection_reason = "已有在途仓位，禁止重复开仓，安全降级为 WAIT。"
                elif raw_action in {"BUY_LONG", "SELL_SHORT"} and rr < 2.0:
                    rejection_reason = "模型报价未满足真实 2R，执行层降级为 WAIT。"
                if rejection_reason:
                    raw_action = "WAIT"

                standard_cache[inst_id] = {
                    "instId": inst_id,
                    "name": p["name"],
                    "timestamp": int(time.time()),
                    "time_str": time_str,
                    "macro_assessment": macro_summary,
                    "thought_process": {
                        "market_structure": d_item.get("market_structure", "多周期结构中性"),
                        "volume_and_oi": d_item.get("volume_and_oi", f"OI: {p['oiUsd']}, Taker: {p['takerNetUsd']}"),
                        "risk_reward_evaluation": "R:R ≥ 2.0 评估"
                    },
                    "smart_money": p.get("smart_money", {}),
                    "adx_1h": p.get("adx_1h", "--"),
                    "decision": {
                        "action": raw_action,
                        "confidence": confidence,
                        "leverage": ai_leverage,
                        "margin_usdt": ai_margin,
                        "entry_price": entry,
                        "take_profit_price": take_profit,
                        "stop_loss_price": stop_loss,
                        "risk_reward_ratio": f"{rr:.2f} : 1" if rr > 0 else "--",
                        "summary_reason": rejection_reason or str(d_item.get("summary_reason", "全市场矩阵综合评估中"))[:120]
                    },
                    "data_quality": p.get("data_quality", "invalid"),
                    "raw_ticker": {
                        "last": p["price"],
                        "bidPx": p["bidPx"],
                        "askPx": p["askPx"],
                        "chg24h": p["chg24h"]
                    },
                    "raw_funding_rate": f"{p['fundingRate']}%" if p.get('fundingRate') else "--",
                    "raw_oi": p.get('oiUsd') or "--",
                    "raw_taker_vol": p.get('takerNetUsd') or "--",
                    "raw_ls_ratio": str(p.get('lsRatio')) if p.get('lsRatio') is not None else "--"
                }

            atomic_write_json(AI_DECISION_CACHE_FILE, standard_cache)
            atomic_write_json(AI_POSITION_MANAGEMENT_FILE, {
                "timestamp": int(time.time()),
                "time_str": time_str,
                "instructions": pos_mgmt_list
            })

            # Record durable history for Web Audit
            full_prompt_text = f"【SYSTEM PROMPT】:\n{SYSTEM_PROMPT.strip()}\n\n{'='*70}\n【USER PROMPT ({time_str})】:\n{prompt.strip()}"
            history_record = {
                "time": time_str,
                "macro_assessment": macro_summary,
                "ai_last_prompt": full_prompt_text,
                "position_management": pos_mgmt_list,
                "top_opportunities": [
                    {
                        "inst": p["name"],
                        "action": standard_cache[p["instId"]]["decision"]["action"],
                        "confidence": standard_cache[p["instId"]]["decision"]["confidence"],
                        "leverage": standard_cache[p["instId"]]["decision"].get("leverage", 3),
                        "margin_usdt": standard_cache[p["instId"]]["decision"].get("margin_usdt", 0.0),
                        "risk_reward_ratio": standard_cache[p["instId"]]["decision"]["risk_reward_ratio"],
                        "data_quality": standard_cache[p["instId"]]["data_quality"],
                        "reason": standard_cache[p["instId"]]["decision"]["summary_reason"]
                    }
                    for p in packages
                ]
            }

            history_list = []
            if os.path.exists(AI_DECISION_HISTORY_FILE):
                try:
                    with open(AI_DECISION_HISTORY_FILE, "r", encoding="utf-8") as f:
                        history_list = json.load(f)
                except Exception:
                    pass

            history_list.insert(0, history_record)
            history_list = history_list[:50] # Keep recent 50 rounds
            
            atomic_write_json(AI_DECISION_HISTORY_FILE, history_list)

            latency = round(time.time() - t0, 2)
            print(f"[AI Brain Batch] ✅ 6 币种全景决策完成 (耗时 {latency}s, 宏观基调: {macro_summary})")
            return standard_cache

    except Exception as e:
        print(f"[AI Brain Batch] Error in batch inference: {e}")
        return None

def get_latest_ai_decision(inst_id: str, max_age_seconds: int = DECISION_MAX_AGE_SECONDS) -> Optional[Dict[str, Any]]:
    """Read a validated decision only while its cache timestamp is fresh."""
    if os.path.exists(AI_DECISION_CACHE_FILE):
        try:
            with open(AI_DECISION_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            item = data.get(inst_id)
            if not isinstance(item, dict):
                return None
            timestamp = int(item.get("timestamp", 0) or 0)
            if timestamp <= 0 or int(time.time()) - timestamp > max_age_seconds:
                return None
            return item
        except Exception:
            pass
    return None

if __name__ == "__main__":
    res = execute_batch_ai_brain_cycle("当前无持仓")
    if res:
        print("\n--- 示例标的 AI 决策结果 ---")
        for k in ["BTC-USDT-SWAP", "SOL-USDT-SWAP", "LINK-USDT-SWAP"]:
            if k in res:
                print(f"[{k}]", json.dumps(res[k]["decision"], ensure_ascii=False))
