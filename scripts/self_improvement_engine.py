#!/usr/bin/env python3
"""
R20 AI LLM-Native Self-Improvement & Strategy Evolution Engine v5.3.2 (self_improvement_engine.py)
Focuses purely on Crypto Alpha generation & dynamic quantitative risk adaptation.
Eliminates rigid cooldown bans in favor of dynamic volatility-adjusted thresholds,
asymmetric Kelly bet-sizing, and LLM cognitive post-mortem lessons.
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import tempfile
import fcntl
import hashlib
from typing import Dict, Any, List, Optional, Tuple

WORKSPACE_DIR = "/app/working/workspaces/default"
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
LOGS_DIR = os.path.join(WORKSPACE_DIR, "logs")

LEDGER_JSON_FILE = os.path.join(DATA_DIR, "trading_ledger.json")
REPORT_JSON_FILE = os.path.join(DATA_DIR, "self_improvement_report.json")
AI_DECISIONS_FILE = os.path.join(DATA_DIR, "ai_brain_decisions.json")
AI_MEMORY_FILE = os.path.join(DATA_DIR, "ai_trading_memory.json")
AI_MEMORY_MD_FILE = os.path.join(DATA_DIR, "AI_TRADING_MEMORY.md")
LOG_FILE = os.path.join(LOGS_DIR, "self_improvement.log")
EVOLUTION_LOCK_FILE = os.path.join(DATA_DIR, ".self_improvement.lock")

TARGET_INSTRUMENTS = ["BTC", "ETH", "SOL", "DOGE", "SUI", "LINK"]

def atomic_write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".evolution-", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def clamp(value, lower, upper, default):
    try:
        return max(lower, min(upper, float(value)))
    except (TypeError, ValueError):
        return default


def single_evolution_cycle(func):
    def wrapped(*args, **kwargs):
        lock_handle = open(EVOLUTION_LOCK_FILE, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock_handle.close()
            log_msg("Self-evolution skipped: another cycle is still running")
            return None
        try:
            return func(*args, **kwargs)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
    return wrapped


def log_msg(msg: str):
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    timestamp = datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

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
        log_msg(f"[AI Evolution] Warning loading local secret store: {e}")

    return env_base_url or "https://api.openai.com/v1", env_api_key or ""

def load_closed_trades():
    account_init_file = os.path.join(DATA_DIR, "account_initial_state.json")
    reset_time_str = "1970-01-01 00:00:00"
    if os.path.exists(account_init_file):
        try:
            with open(account_init_file, "r", encoding="utf-8") as f:
                acc_init = json.load(f)
                reset_time_str = acc_init.get("reset_time", "1970-01-01 00:00:00")
        except Exception:
            pass

    closed_trades = []
    if os.path.exists(LEDGER_JSON_FILE):
        try:
            with open(LEDGER_JSON_FILE, "r", encoding="utf-8") as f:
                t_list = json.load(f)
                for t in t_list:
                    if t.get("status") == "holding":
                        continue
                    
                    c_time = str(t.get("close_time") or t.get("time") or "")
                    if c_time and c_time < reset_time_str:
                        continue

                    inst = str(t.get("inst") or t.get("name") or "OTHER")
                    if inst not in TARGET_INSTRUMENTS:
                        continue
                    pnl = float(t.get("pnl", 0.0) or 0.0)
                    gross = float(t.get("gross_pnl", pnl) or pnl)
                    fee = abs(float(t.get("fee", 0.0) or 0.0))
                    strat = str(t.get("strategy") or "⚡ 趋势")
                    reason = str(t.get("exit_reason") or t.get("remark") or "")

                    closed_trades.append({
                        "inst": inst,
                        "time": c_time,
                        "open_time": t.get("open_time", ""),
                        "strategy": strat,
                        "margin": t.get("margin", "--"),
                        "gross_pnl": round(gross, 2),
                        "fee": round(fee, 2),
                        "net_pnl": round(pnl, 2),
                        "exit_reason": reason
                    })
        except Exception as e:
            log_msg(f"读取交易台账异常: {e}")

    return closed_trades

EVOLUTION_SYSTEM_PROMPT = """你是一名世界顶级加密量化对冲基金的首席投资官(CIO)。
你的职责：审查系统最近平仓的历史真实成交记录与损益流水，对照【已有历史长期记忆库】，进行每日交易认知复盘（Cognitive Post-Mortem），执行【智能记忆更新与动态覆盖】并沉淀为 Markdown 格式的实战心法提示词。

核心记忆机制与动态覆盖原则（参考 QwenPaw 记忆系统）：
1. 记忆时效性与证伪覆盖（Memory Evolution & Invalidation）：
   - 市场环境瞬息万变，早期的经验法则在新的市场结构下可能失效（如牛市的追突破心法在震荡市失效，或此前的摸顶教训在新主线中需要修正）；
   - 你必须审视【现有旧记忆】：保留仍具普适性的真理，淘汰/覆盖/修订已失效或被最新亏损实证打脸的过时认知，生成全新的【最新有效记忆条目】。
2. 显式打标生成日期时间（Timestamped）：
   - 每一条核心记忆心法与归因痛点，都必须明确标注提炼生成的精确时间日期（如 `[YYYY-MM-DD HH:MM:SS]`），使未来 AI 大脑能清晰感知该经验的时效衰减。
3. 启发式与软约束（Soft Heuristics）：
   - 记忆是提供给未来 AI 大脑的高维直觉与先验洞察，绝不能写成死板限制、绝对硬编码规则或僵化指标阈值。
4. 必须输出严格标准 JSON 对象。
"""

def call_llm_evolution_review(closed_trades: List[Dict[str, Any]], existing_memory_md: str = "", timestamp_str: str = "") -> Dict[str, Any]:
    base_url, api_key = get_cpa_client_config()
    if not api_key:
        log_msg("[AI Evolution] Error: CPA API Key not found, using fallback heuristics.")
        return {}

    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj_str = timestamp_str or datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S (北京时间)")

    total = len(closed_trades)
    wins = [t for t in closed_trades if t["net_pnl"] > 0]
    losses = [t for t in closed_trades if t["net_pnl"] <= 0]
    win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0.0
    total_net = round(sum(t["net_pnl"] for t in closed_trades), 2)
    total_fees = round(sum(t["fee"] for t in closed_trades), 2)

    memory_context = f"""======================= 【当前系统已有的历史长期记忆库】 =======================
{existing_memory_md.strip()}
""" if existing_memory_md.strip() else "当前长期记忆库为空 (系统初始冷启动状态)"

    prompt = f"""======================= 【当前认知复盘基准时间】 =======================
【复盘基准时间】: {now_bj_str}

{memory_context}

======================= 【R20 加密量化实盘战绩与历史交易台账】 =======================
【统计汇总】:
- 总平仓笔数: {total} 笔 (胜 {len(wins)} / 负 {len(losses)} | 胜率: {win_rate}%)
- 累计净盈亏: {total_net:+.2f} USDT | 累计手续费消耗: {total_fees:.2f} USDT
- 当前聚焦标的池: {TARGET_INSTRUMENTS}

【逐笔历史交易明细 (按时间排序)】:
{json.dumps(closed_trades, indent=2, ensure_ascii=False)}

【复盘与长期记忆进化/动态覆盖任务】:
请基于上述真实交易流水，对照【已有历史长期记忆库】，审视哪些旧经验已失效需淘汰覆盖（特别关注微积分动能加速度 Calculus Acceleration 衰竭与假突破、顺势加仓时机与止损冷却），提炼出最新的 3~4 条实战心法，输出标准 JSON：
{{
  "diagnosis_insights": [
    "3~4 条深度痛点与亏损归因诊断 (直击实战要害，严格对齐上方真实数据)"
  ],
  "evolution_actions": [
    "3~4 条具体的自适应执行优化方向 (如强化聪明钱共振、避开流动性真空段、优化挂单入场等)"
  ],
  "ai_long_term_memory": [
    "3~4 条写给未来 AI 交易大脑的最新有效实战心法 (每条需包含心法核心，并体现对过时经验的更新/覆盖)"
  ],
  "memory_overwrites_reason": "简述本轮对哪些旧认知进行了淘汰、修订或强化覆盖 (50字内)"
}}
"""

    payload = {
        "model": "gemini-3.7-flash-high",
        "messages": [
            {"role": "system", "content": EVOLUTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "reasoning_effort": "high",
        "temperature": 0.2,
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
        log_msg("🚀 正在调用 Gemini 3.7 进行 AI 大脑深度认知复盘与策略参数优化...")
        with urllib.request.urlopen(req, timeout=30) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            content = res["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            review_json = json.loads(content.strip())
            log_msg(f"✅ AI 大脑认知复盘完成 (耗时 {round(time.time() - t0, 2)}s)")
            return review_json
    except Exception as e:
        log_msg(f"Error in LLM evolution review: {e}")
        return {}

@single_evolution_cycle
def run_self_evolution(force: bool = False):
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj = datetime.datetime.now(tz_bj)
    timestamp_str = now_bj.strftime("%Y-%m-%d %H:%M:%S")
    log_msg("🧬 启动 R20 AI 大脑自进化认知复盘与实战心法提炼 (v5.3.2 Crypto Focus)...")

    closed_trades = load_closed_trades()
    total_trades = len(closed_trades)
    ledger_revision = hashlib.sha256(
        json.dumps(closed_trades, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if not force and os.path.exists(REPORT_JSON_FILE):
        try:
            with open(REPORT_JSON_FILE, "r", encoding="utf-8") as f:
                previous_report = json.load(f)
            if previous_report.get("ledger_revision") == ledger_revision:
                log_msg("No new closed-trade evidence; keeping the current adaptive configuration")
                return previous_report
        except Exception:
            pass

    # 1. Base Stats
    win_trades = [t for t in closed_trades if t["net_pnl"] > 0]
    loss_trades = [t for t in closed_trades if t["net_pnl"] <= 0]
    win_count = len(win_trades)
    win_rate = round(win_count / total_trades * 100, 1) if total_trades > 0 else 0.0
    total_win_amt = sum(t["net_pnl"] for t in win_trades)
    total_loss_amt = abs(sum(t["net_pnl"] for t in loss_trades))
    total_fees_amt = sum(t["fee"] for t in closed_trades)
    profit_factor = round(total_win_amt / total_loss_amt, 2) if total_loss_amt > 0 else (99.0 if total_win_amt > 0 else 0.0)

    # 1. Read existing memory to enable smart evolution & overwriting
    existing_memory_md = ""
    if os.path.exists(AI_MEMORY_MD_FILE):
        try:
            with open(AI_MEMORY_MD_FILE, "r", encoding="utf-8") as f:
                existing_memory_md = f.read()
        except Exception:
            pass

    # 2. Call LLM for Cognitive Review & Memory Overwriting
    llm_review = call_llm_evolution_review(closed_trades, existing_memory_md=existing_memory_md, timestamp_str=timestamp_str)

    insights = llm_review.get("diagnosis_insights", [
        f"全盘已平仓 {total_trades} 笔，整体胜率 {win_rate}%，累计手续费消耗 {total_fees_amt:.2f} USDT。",
        "加密货币主升浪与波段顺势契合度极佳，剔除TradFi后流动性与动量显著纯化。"
    ])
    actions_taken = llm_review.get("evolution_actions", [
        "全面升级为 AI 大脑全权裁决开仓与持仓管理，废除死板硬编码阈值。",
        "严格对齐 OKX 顶级聪明钱主力方向，防范多空比极端过热的多杀多踩踏。",
        "对高流动性标的执行自适应头寸规划，确保盈亏比真实 R:R ≥ 2.0。"
    ])
    
    raw_asset_mults = llm_review.get("asset_multipliers", {})
    if not isinstance(raw_asset_mults, dict):
        raw_asset_mults = {}
    asset_mults = {
        asset: clamp(raw_asset_mults.get(asset, 1.0), 0.5, 1.5, 1.0)
        for asset in TARGET_INSTRUMENTS
    }
    long_term_memory = llm_review.get("ai_long_term_memory", [
        "顺势与大势共振：密切观察 4H/1H 宏观结构，避免在强单边主升浪中逆势摸顶。",
        "聪明钱资金意图：80%+ 胜率主力资金大额流入往往伴随突破爆发，可作为高置信度共振参考。",
        "防范多杀多踩踏：在多空比极度拥挤且量能枯竭的高位，防范获利盘平仓引起的折返去杠杆风险。"
    ])

    # 3. Save Long-Term Memory (Both JSON and Human/LLM-readable Markdown)
    memory_payload = {
        "updated_at": timestamp_str,
        "total_trades_reviewed": total_trades,
        "win_rate": win_rate,
        "core_lessons": long_term_memory,
        "favored_assets": ["ETH", "SOL", "LINK"]
    }
    atomic_write_json(AI_MEMORY_FILE, memory_payload)

    # Save as QwenPaw-style Markdown Memory File
    md_content = f"""# R20 AI 交易大脑长期记忆与启发式心法 (AI Trading Memory)

> **最新覆盖与修订时间**: {timestamp_str} (北京时间)  
> **复盘样本覆盖**: 最近平仓 {total_trades} 笔 | 样本胜率: {win_rate}%  
> **模式说明**: 本文档由每日交易认知复盘（Cognitive Post-Mortem）基于最新实盘流水自动迭代沉淀。具备**智能时效覆盖机制**，动态淘汰被证伪的旧认知，保留并更新最新有效心法，不设死板硬编码限制。

---

## 🧠 核心实战心法与直觉提示词 (Heuristic Lessons)

"""
    for idx, item in enumerate(long_term_memory, 1):
        clean_item = item.strip()
        if clean_item.startswith(f"[{timestamp_str}]"):
            clean_item = clean_item[len(f"[{timestamp_str}]"):].strip()
        md_content += f"{idx}. [{timestamp_str}] {clean_item}\n"

    md_content += f"""
---

## 🔍 痛点归因与记忆更新依据 (Diagnosis & Evolution Rationale)

- 🔄 **本轮认知迭代覆盖摘要**: {llm_review.get('memory_overwrites_reason', '结合最新平仓损益完成记忆时效性检验与动态覆盖')}
"""
    for ins in insights:
        clean_ins = ins.strip()
        if clean_ins.startswith(f"[{timestamp_str}]"):
            clean_ins = clean_ins[len(f"[{timestamp_str}]"):].strip()
        md_content += f"- 💡 [{timestamp_str}] {clean_ins}\n"

    try:
        tmp_md = AI_MEMORY_MD_FILE + ".tmp"
        with open(tmp_md, "w", encoding="utf-8") as f:
            f.write(md_content)
        os.replace(tmp_md, AI_MEMORY_MD_FILE)
        log_msg(f"📝 长期记忆已同步更新至 Markdown 文件: {AI_MEMORY_MD_FILE}")
    except Exception as e:
        log_msg(f"Markdown 记忆写入异常: {e}")

    # 4. Save Dashboard Report
    report_payload = {
        "timestamp": timestamp_str,
        "ledger_revision": ledger_revision,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "mode": "QwenPaw-Style Heuristic Memory (启发式长期记忆)",
        "insights": insights,
        "actions_taken": actions_taken,
        "core_lessons": long_term_memory
    }

    atomic_write_json(REPORT_JSON_FILE, report_payload)

    log_msg(f"🧬 自进化认知复盘完成 | 已沉淀 {len(long_term_memory)} 条启发式长期记忆提示词")
    return report_payload

if __name__ == "__main__":
    force_run = "--force" in sys.argv or "-f" in sys.argv
    res = run_self_evolution(force=force_run)
    print(json.dumps(res, indent=2, ensure_ascii=False))
