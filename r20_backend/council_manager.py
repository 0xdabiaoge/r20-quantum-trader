"""R20 Quantum Hedge Fund Investment Committee (Trading Desk Council).
Fully Re-architected in v7.2.2:
1. Symmetrical Trader Roles (Equal Peer Traders):
   - Trader A: Senior Trend-Pullback Trader (Conservative & High Win-rate)
   - Trader B: Senior Momentum-Breakout Trader (Aggressive & High R:R)
   - Trader C: Senior Quantitative & Calculus Trader (Data-Driven & Microstructure)
2. Trade Proposal Protocol:
   Every trader is a complete trader who analyzes the market, formulates a complete
   trading proposal (Symbol, Action, Limit Price, 2.0x ATR Stop Loss, 2.0R Take Profit,
   Confidence & Calculus Thesis), and challenges peer traders' potential blind spots.
3. Chief Investment Officer (CIO / Head of Trading) Verdict:
   The CIO reviews all submitted proposals, weighs cross-examination feedback, determines
   which trader's plan to fund and execute (or rejects all for WAIT), and outputs the
   final deterministic trading JSON contract.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
COUNCIL_CONFIG_FILE = DATA_DIR / "council_config.json"

DEFAULT_PRESET_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "trader_trend": {
        "id": "trader_trend",
        "name": "资深交易员 A (顺势稳健型)",
        "role_title": "Senior Trend Trader",
        "description": "专注 4H/1H 顺大势回踩低吸与承压高抛，坚守 0.8R 保本移损与高胜率。",
        "prompt": (
            "【角色：资深交易员 A · 稳健顺势波段操盘手】\n"
            "你是对冲基金交易台的核心波段交易员，你的交易哲学是「顺应大势、耐心等待确定性回踩打折点，宁可踏空绝不盲目追高」：\n\n"
            "【核心分析工具与插槽】：\n"
            "- 重点核验: {{macro_4h}} (4H 宏观多空通道与大级别趋势)\n"
            "- 重点核验: {{trading_memory}} (自进化长期实战防踩踏心法)\n\n"
            "【你的任务】：\n"
            "对池内 6 大币种逐一研判并拿出你的完整作战提案：\n"
            "1. 顺势判定：只在 4H 多头通道中找回踩短均线企稳的低吸买点；只在 4H 空头通道中找反弹承压的高抛卖点。\n"
            "2. 给出你的明确提案（标的、倾向 BUY_LONG/SELL_SHORT/WAIT、建议入场限价 limit_price、2.0x ATR 止损 stop_loss、2.0R 止盈 take_profit、置信度及核心逻辑，50字内/币种）。\n"
            "3. 简要指出激进追涨杀跌交易员可能面临的假突破被套风险。"
        ),
        "weight": 0.35,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "trader_momentum": {
        "id": "trader_momentum",
        "name": "资深交易员 B (动能突破型)",
        "role_title": "Senior Momentum Trader",
        "description": "专注微积分一阶速度 v 与二阶加速度 a 爆发，捕捉高爆发动量波段与大盈亏比机会。",
        "prompt": (
            "【角色：资深交易员 B · 进取动能突破操盘手】\n"
            "你是对冲基金交易台的进攻型突破交易员，你的交易哲学是「紧跟资金最凶猛的非线性动能爆发，用数学期望放大盈亏比」：\n\n"
            "【核心分析工具与插槽】：\n"
            "- 重点核验: {{calculus_1h}} (微积分一阶速度 v 与二阶加速度 a)\n"
            "- 重点核验: {{sentiment}} (全网舆情多空比与情绪爆发点)\n\n"
            "【你的任务】：\n"
            "对池内 6 大币种逐一研判并拿出你的完整作战提案：\n"
            "1. 动能校验：一阶速度 v > 0 且加速度 a > 0 判定为加速顺势爆发；若动能背离减速，坚决观望。\n"
            "2. 给出你的明确提案（标的、倾向 BUY_LONG/SELL_SHORT/WAIT、建议入场限价 limit_price、2.0x ATR 止损 stop_loss、2.5R 止盈 take_profit、置信度及爆发动能依据，50字内/币种）。\n"
            "3. 简要评价当前市场是否处于假突破高危期，并说明你的风控防线。"
        ),
        "weight": 0.35,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "trader_quant": {
        "id": "trader_quant",
        "name": "资深交易员 C (数理筹码型)",
        "role_title": "Senior Quantitative Trader",
        "description": "专注做功定积分 E、聪明钱真实仓位动向与盘口挂单挂撤深度博弈。",
        "prompt": (
            "【角色：资深交易员 C · 数理量化与筹码操盘手】\n"
            "你是对冲基金交易台的客观量化交易员，你的交易哲学是「不听任何市场故事与主观幻觉，只认数学公式、筹码定积分与盘口挂单墙」：\n\n"
            "【核心分析工具与插槽】：\n"
            "- 重点核验: {{smart_money}} (主力聪明钱持仓占比与大单流向)\n"
            "- 重点核验: {{orderbook_depth}} (盘口挂单深度比与流动性陷阱)\n\n"
            "【你的任务】：\n"
            "对池内 6 大币种逐一研判并拿出你的完整作战提案：\n"
            "1. 数理概率硬审：条件延续概率 P续 是否 ≥ 50%？若 ADX < 18 判定为震荡垃圾时间，坚决反对开仓。\n"
            "2. 给出你的明确提案（标的、倾向 BUY_LONG/SELL_SHORT/WAIT、建议入场限价 limit_price、止损、止盈、置信度及数学期望支持度，50字内/币种）。\n"
            "3. 质疑其他交易员的方案：指出是否存在聪明钱暗中派发或盘口深度支撑不足的致命缺陷。"
        ),
        "weight": 0.30,
        "enabled": True,
        "reasoning_effort": "high",
        "temperature": 0.1,
        "is_arbitrator": False,
        "model_id": "",
    },
    "cio": {
        "id": "cio",
        "name": "首席投资官 / 交易总监 (Chief Investment Officer)",
        "role_title": "Head of Trading / CIO",
        "description": "统领交易台全体交易员，审阅作战提案与互评辩论，拍板采纳谁的方案执行发单或全员驳回。",
        "prompt": (
            "【角色：对冲基金首席投资官 (CIO) 兼交易总监】\n"
            "你统领交易台全体资深交易员。现在各位交易员（Trader A, Trader B, Trader C）已经就当前 6 大币种提交了各自的作战方案与相互质疑反驳。\n\n"
            "【你的决策权力与使命】：\n"
            "1. 严格基于基金最高风控宪法（顺势交易、2.0x ATR 宽止损、0.8R 保本锁胜率）进行终审。\n"
            "2. 详细审阅每位交易员的作战提案（限价、止损、止盈与依据），评估谁的逻辑最扎实、谁的方案存在漏洞。\n"
            "3. 明确批复裁定：\n"
            "   - 若批准入场：明确宣布「采纳交易员 X 对某币种的作战方案，批准发单执行！」\n"
            "   - 若分歧严重或风险巨大：明确宣布「驳回全体交易员方案，当前市场不具备确定性优势，全员空仓观望 WAIT！」\n"
            "4. 强制输出落地发单契约：无论采纳谁的方案，必须输出符合交易所接口的完整点位（limit_price, stop_loss, take_profit, leverage, margin_usd, reasoning）。"
        ),
        "weight": 1.0,
        "enabled": True,
        "reasoning_effort": "high",
        "temperature": 0.2,
        "is_arbitrator": True,
        "model_id": "",
    },
}

ALL_AVAILABLE_PRESETS = dict(DEFAULT_PRESET_TEMPLATES)

COUNCIL_PRESET_SUITES: Dict[str, Dict[str, Any]] = {
    "hedge_fund_desk": {
        "id": "hedge_fund_desk",
        "name": "对冲基金投委会标准台 (Hedge Fund Desk)",
        "desc": "Trader A (顺势) + Trader B (动能) + Trader C (数理) 提交完整方案互相质询，CIO 交易总监终审裁定",
        "consensus_mode": "weighted",
        "roles": ["trader_trend", "trader_momentum", "trader_quant", "cio"],
    },
}


def _atomic_write_json(file_path: Path, data: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = file_path.parent
    with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        temp_name = tf.name
    os.replace(temp_name, file_path)


def load_council_config() -> Dict[str, Any]:
    if COUNCIL_CONFIG_FILE.is_file():
        try:
            with open(COUNCIL_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "roles" in data:
                # If legacy arbitrator key exists without CIO, smoothly upgrade to new Hedge Fund Desk
                roles = data.get("roles", {})
                if "trader_trend" in roles or "cio" in roles:
                    return data
        except Exception:
            pass

    default_config: Dict[str, Any] = {
        "enabled": False,
        "consensus_mode": "weighted",
        "timeout_seconds": 60.0,
        "roles": {k: dict(v) for k, v in DEFAULT_PRESET_TEMPLATES.items()},
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _atomic_write_json(COUNCIL_CONFIG_FILE, default_config)
    return default_config


def save_council_config(config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("Council config must be a dict")
    roles = config.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise ValueError("委员会至少需要包含角色配置")

    has_arbitrator = any(r.get("is_arbitrator") or k in {"cio", "arbitrator"} for k, r in roles.items())
    if not has_arbitrator:
        raise ValueError("委员会必须保留至少一位首席终审仲裁官/交易总监(CIO)！")

    for role_id, role in roles.items():
        if not isinstance(role, dict):
            raise ValueError(f"角色 {role_id} 配置必须为字典")
        role["id"] = role_id
        role.setdefault("enabled", True)
        role.setdefault("weight", 0.3)
        role.setdefault("reasoning_effort", "medium")
        role.setdefault("temperature", 0.2)

    config["consensus_mode"] = str(config.get("consensus_mode", "weighted")).lower()
    if config["consensus_mode"] not in {"strict", "weighted", "aggressive"}:
        config["consensus_mode"] = "weighted"

    config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _atomic_write_json(COUNCIL_CONFIG_FILE, config)
    return config


def get_available_presets() -> List[Dict[str, Any]]:
    return list(ALL_AVAILABLE_PRESETS.values())


def get_preset_suites() -> List[Dict[str, Any]]:
    return list(COUNCIL_PRESET_SUITES.values())


def apply_preset_suite(suite_id: str) -> Dict[str, Any]:
    suite = COUNCIL_PRESET_SUITES.get(suite_id)
    if not suite:
        suite = list(COUNCIL_PRESET_SUITES.values())[0]

    config = load_council_config()
    new_roles: Dict[str, Any] = {}
    for r_id in suite["roles"]:
        if r_id in ALL_AVAILABLE_PRESETS:
            preset = dict(ALL_AVAILABLE_PRESETS[r_id])
            old_model = config.get("roles", {}).get(r_id, {}).get("model_id", "")
            preset["model_id"] = old_model
            new_roles[r_id] = preset

    config["consensus_mode"] = suite.get("consensus_mode", "weighted")
    config["roles"] = new_roles
    return save_council_config(config)


def reset_role_template(role_id: str) -> Dict[str, Any]:
    config = load_council_config()
    roles = config.get("roles", {})
    if role_id not in roles:
        raise ValueError(f"未找到角色 ID: {role_id}")

    preset = ALL_AVAILABLE_PRESETS.get(role_id)
    if not preset:
        if role_id in {"cio", "arbitrator"} or roles[role_id].get("is_arbitrator"):
            preset = DEFAULT_PRESET_TEMPLATES["cio"]
        else:
            raise ValueError(f"该角色无内置出厂模板: {role_id}")

    old_model = roles[role_id].get("model_id", "")
    new_role = dict(preset)
    new_role["model_id"] = old_model
    roles[role_id] = new_role
    config["roles"] = roles
    return save_council_config(config)


def _call_single_trader(
    role_id: str,
    role_spec: Dict[str, Any],
    market_prompt: str,
    master_constitutional_rules: str,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Invokes a senior trader role to pitch their complete trade proposal."""
    from r20_backend.llm_manager import execute_llm_request, get_active_llm_runtime, load_llm_config

    model_id = role_spec.get("model_id") or ""
    override_model = None
    override_url = None
    override_key = None
    override_format = None
    override_effort = role_spec.get("reasoning_effort") or "medium"
    temperature = float(role_spec.get("temperature", 0.2))

    cfg = load_llm_config(mask_keys=False)
    if model_id:
        for item in cfg.get("models", []):
            if item.get("id") == model_id:
                override_model = item.get("id")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                override_effort = item.get("reasoning_effort") or override_effort
                break
    else:
        override_effort = cfg.get("active_reasoning_effort", "medium")

    prompt_content = role_spec.get("prompt", "")
    role_name = role_spec.get("name", role_id)

    trader_system_prompt = (
        f"【最高交易宪法与策略纪律】\n"
        f"{master_constitutional_rules}\n\n"
        f"====================================================\n"
        f"【你的交易员身份与操盘职责】\n"
        f"{prompt_content}\n"
        f"注意：你作为专业交易员，必须在上述【最高交易宪法】框架内提交完整的实战作战提案（Pitch），包含明确的点位、逻辑与对同行漏洞的质疑！"
    )

    trader_user_prompt = (
        f"【市场实时全景数据 (6大主力标的)】\n"
        f"{market_prompt}\n\n"
        f"请以你「{role_name}」的身份，向首席投资官 (CIO) 提交本轮作战方案：\n"
        f"1. 针对每一个标的输出明确方案：倾向（BUY_LONG / SELL_SHORT / WAIT）、入场限价 limit_price、2.0x ATR 止损 stop_loss、止盈 take_profit 及置信度。\n"
        f"2. 阐述你的核心逻辑，并简要指出其他交易员可能忽略的致命风险（60字内/标的）。"
    )

    messages = [
        {"role": "system", "content": trader_system_prompt},
        {"role": "user", "content": trader_user_prompt},
    ]

    try:
        content, reasoning, usage, latency = execute_llm_request(
            messages=messages,
            model=override_model,
            base_url=override_url,
            api_key=override_key,
            api_format=override_format,
            reasoning_effort=override_effort,
            temperature=temperature,
            timeout=timeout,
        )
        return {
            "role_id": role_id,
            "role_name": role_name,
            "model_used": override_model or get_active_llm_runtime().get("model", "default"),
            "status": "ok",
            "content": content.strip(),
            "reasoning": reasoning.strip() if reasoning else "",
            "latency_ms": latency,
            "weight": role_spec.get("weight", 1.0),
        }
    except Exception as e:
        return {
            "role_id": role_id,
            "role_name": role_name,
            "model_used": override_model or "unknown",
            "status": "error",
            "content": f"交易员方案提交异常/超时降级: {e}",
            "reasoning": "",
            "latency_ms": 0,
            "weight": 0.0,
        }


def execute_council_debate(
    market_prompt: str,
    original_system_prompt: str,
    timeout: float = 60.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute Hedge Fund Investment Committee Deliberation:

    1. All Senior Traders submit complete trade proposals.
    2. CIO reviews proposals, cross-examinations, arbitrates which trader's plan to fund,
       and outputs the final standard trading JSON contract.
    """
    from r20_backend.llm_manager import execute_llm_request, get_active_llm_runtime, load_llm_config

    config = load_council_config()
    roles = config.get("roles", {})
    consensus_mode = config.get("consensus_mode", "weighted")
    t_start = time.time()

    # Step 1: Identify CIO (Arbitrator) and Active Traders
    cio_key = next(
        (k for k, r in roles.items() if r.get("is_arbitrator") or k in {"cio", "arbitrator"}),
        "cio",
    )
    cio_spec = roles.get(cio_key, DEFAULT_PRESET_TEMPLATES["cio"])
    trader_keys = [
        k for k in roles.keys()
        if k != cio_key and roles[k].get("enabled", True) is not False
    ]

    trader_proposals: Dict[str, Dict[str, Any]] = {}
    if trader_keys:
        member_timeout = max(15.0, timeout * 0.50)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(trader_keys))) as pool:
            futures = {
                pool.submit(
                    _call_single_trader,
                    key,
                    roles[key],
                    market_prompt,
                    original_system_prompt,
                    member_timeout,
                ): key
                for key in trader_keys
            }
            for fut in concurrent.futures.as_completed(futures):
                key = futures[fut]
                try:
                    trader_proposals[key] = fut.result()
                except Exception as exc:
                    trader_proposals[key] = {
                        "role_id": key,
                        "role_name": roles[key].get("name", key),
                        "status": "error",
                        "content": f"Proposal exception: {exc}",
                        "weight": 0.0,
                    }

    # Step 2: Compile the Structured Investment Committee Docket
    transcript_blocks = []
    for k in trader_keys:
        res = trader_proposals.get(k, {})
        weight_str = f" [绩效权重: {res.get('weight', 1.0)}]" if res.get("weight") is not None else ""
        transcript_blocks.append(
            f"=== 【{res.get('role_name', k)}】实战作战提案与风控质询（模型：{res.get('model_used', 'default')}{weight_str}）===\n"
            f"{res.get('content', '（该交易员本轮未提交有效提案）')}\n"
        )
    compiled_proposals = "\n".join(transcript_blocks) if transcript_blocks else "（无其他交易员提交方案，首席投资官独立决策）"

    # Step 3: CIO Final Review & Funding Verdict
    cio_model_id = cio_spec.get("model_id") or ""
    override_model = None
    override_url = None
    override_key = None
    override_format = None
    override_effort = "high"
    cio_temperature = float(cio_spec.get("temperature", 0.2))

    cfg = load_llm_config(mask_keys=False)
    if cio_model_id:
        for item in cfg.get("models", []):
            if item.get("id") == cio_model_id:
                override_model = item.get("id")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                override_effort = item.get("reasoning_effort") or "high"
                break
    else:
        override_effort = cfg.get("active_reasoning_effort", "high")

    cio_system_prompt = (
        f"{original_system_prompt}\n\n"
        "====================================================\n"
        f"【身份特别授权：你是对冲基金首席投资官 (CIO) 兼交易总监】\n"
        f"{cio_spec.get('prompt', '')}\n\n"
        "====================================================\n"
        "【投委会终审发单契约强约束（必须输出全量点位，严禁遗漏！）】\n"
        "你必须对 6 大主力标的（BTC, ETH, SOL, DOGE, SUI, ASTER）做出最终裁决：\n"
        "- 仔细对比各位交易员提交的作战方案（限价、止损、止盈与依据），评估谁的逻辑最扎实、谁的方案存在漏洞；\n"
        "- 在 reasoning 中必须明确写出你的仲裁批复：\n"
        "  例如：「采纳交易员 A 的稳健回踩买多方案，驳回交易员 B 的激进追多，因 1H 动能已减速背离」；\n"
        "  或者：「驳回全体交易员方案，当前处于高位无序震荡，全员空仓观望 WAIT！」\n\n"
        "若决定对某标的发单开仓（BUY_LONG 或 SELL_SHORT），decisions[标的] 内部必须且只能输出完整的四维点位与参数字典：\n"
        "{\n"
        '  "action": "BUY_LONG" 或 "SELL_SHORT",\n'
        '  "confidence": 82,  // 最终核定置信度整数 0~100\n'
        '  "limit_price": 78250.0,  // 挂单入场限价（数字），严禁市价追高\n'
        '  "stop_loss": 76500.0,  // 严格基于 1.8~2.2x 1H ATR 设置的防插针止损价（数字）\n'
        '  "take_profit": 81750.0,  // 至少 2.0R 盈亏比的目标止盈价（数字）\n'
        '  "leverage": 3,  // 杠杆倍数（整型 2~5）\n'
        '  "margin_usd": 150.0,  // 下注保证金（数字）\n'
        '  "reasoning": "【CIO批复】采纳/驳回了哪位交易员的提案，具体风控与动能考量"\n'
        "}\n"
        "若判定为 WAIT 观望，输出: {\"action\": \"WAIT\", \"confidence\": 50, \"reasoning\": \"【CIO批复】驳回方案，观望理由\"}\n"
        "最终必须且只能输出严格符合原有交易契约的 JSON 格式，绝不包含任何多余文本！"
    )

    cio_user_prompt = (
        "【市场实时全景数据 (6大主力标的)】\n"
        f"{market_prompt}\n\n"
        "====================================================\n"
        "【各交易员实战作战提案与互评质询卷宗】\n"
        f"{compiled_proposals}\n\n"
        "====================================================\n"
        "请作为首席投资官 (CIO) 审阅卷宗，裁定本轮发单并输出标准 JSON：\n"
        "1. 在 macro_assessment 中给出全局资金偏好与宏观裁定总括。\n"
        "2. 在各标的的 decisions 中明确说明采纳了谁的方案并给出完整四维点位。\n"
        "3. 根对象包含 decisions, position_management, macro_assessment 三个顶层键！"
    )

    rem_time = max(25.0, timeout - (time.time() - t_start))
    content, reasoning, usage, latency = execute_llm_request(
        messages=[
            {"role": "system", "content": cio_system_prompt},
            {"role": "user", "content": cio_user_prompt},
        ],
        model=override_model,
        base_url=override_url,
        api_key=override_key,
        api_format=override_format,
        reasoning_effort=override_effort,
        temperature=cio_temperature,
        response_format={"type": "json_object"},
        timeout=rem_time,
    )

    clean_content = content.strip()
    if clean_content.startswith("```json"):
        clean_content = clean_content[7:]
    if clean_content.startswith("```"):
        clean_content = clean_content[3:]
    if clean_content.endswith("```"):
        clean_content = clean_content[:-3]
    clean_content = clean_content.strip()

    brain_output = json.loads(clean_content)
    if not isinstance(brain_output, dict):
        raise ValueError("CIO output root must be a JSON object")

    council_transcript = {
        "council_mode": True,
        "council_architecture": "Hedge Fund Investment Committee",
        "consensus_mode": consensus_mode,
        "total_duration_ms": int((time.time() - t_start) * 1000),
        "arbitrator": {
            "role_name": cio_spec.get("name", "首席投资官 (CIO)"),
            "model_used": override_model or get_active_llm_runtime().get("model", "default"),
            "latency_ms": latency,
            "reasoning": reasoning,
        },
        "advisors": trader_proposals,
    }

    brain_output["council_transcript"] = council_transcript
    return brain_output, council_transcript
