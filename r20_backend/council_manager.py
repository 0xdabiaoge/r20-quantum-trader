"""Multi-Agent Council Decision Engine for R20 Quantum Trader.
Fully Re-architected in v7.2.2:
1. Unified Constitutional Inheritance:
   Advisors and Arbitrator strictly inherit the primary Prompt Studio strategy rules
   (2.0x ATR noise-resistant SL, 0.8R breakeven ratchet, Calculus Momentum, and Heuristic Memory).
2. Structured White-Box Deliberation Protocol:
   Each advisor audits against the Master Trading Rules, outputting structured evaluations
   rather than free-form hallucinations.
3. Resilient Fail-Safe & Auto-Healing:
   If an advisor times out or errors, it fails gracefully without blocking the debate.
   If the whole council experiences upstream failure, it falls back cleanly to the main brain.
4. Deterministic Consensus Convergence:
   Arbitrator arbitrates based on strict/weighted/aggressive consensus rules, enforcing
   the primary trading JSON output contract (decisions, position_management, macro_assessment).
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
    "alpha": {
        "id": "alpha",
        "name": "动量进攻官 (Alpha Aggressor)",
        "role_title": "顺势突破 / 动量加速",
        "description": "专注一阶速度 v 与二阶加速度 a，寻找顺势回踩确认与高期望值突破入场点。",
        "prompt": (
            "【角色：R20 动量进攻官】\n"
            "最高宪法授权：在顺势交易与期望值优势框架内，寻找动能最强、盈亏比最优的进攻机会。\n\n"
            "【核心研判参数与插槽要求】：\n"
            "- 重点核验: {{calculus_1h}} (微积分一阶速度 v 与二阶加速度 a)\n"
            "- 重点核验: {{macro_4h}} (4H 宏观多空通道与大级别顺势方向)\n\n"
            "【进攻准则与硬门禁】：\n"
            "1. 严格服从顺势主轴：4H 多头通道中只寻找回踩企稳的低吸买点；4H 空头通道中只寻找反弹承压的高抛卖点，严禁大级别逆势摸顶抄底！\n"
            "2. 微积分动能校验：一阶速度 v > 0 且加速度 a > 0 确认为加速顺势上行；若动能减速背离，无条件禁止追高。\n"
            "3. 对关注标的必须明确给出：倾向（BUY_LONG / SELL_SHORT / WAIT）、置信度（0~100%）、建议入场限价 limit_price 及核心动量买点依据（80字内/标的）。"
        ),
        "weight": 0.35,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "risk": {
        "id": "risk",
        "name": "保守风控官 (Paranoid Guardian)",
        "role_title": "底线捍卫 / 止损合规",
        "description": "持怀疑一切态度，严查假突破陷阱、2.0x ATR 止损合规性与单边拥挤踩踏风险。",
        "prompt": (
            "【角色：R20 保守风控官】\n"
            "最高宪法授权：担任风控守门人，座右铭是「宁可错过十次波动，绝不承担一次灾难性风险」。\n\n"
            "【核心研判参数与插槽要求】：\n"
            "- 重点核验: {{orderbook_depth}} (盘口买卖盘挂单深度比与流动性枯竭检测)\n"
            "- 重点核验: {{trading_memory}} (自进化长期实战防踩踏心法)\n\n"
            "【风控准则与硬门禁】：\n"
            "1. 2.0x ATR 止损合规性硬审：开仓建议的止损 stop_loss 必须严格设在结构外 1.8x ~ 2.2x 1H ATR 以外，给足波动呼吸空间，未达安全垫必须一票否决！\n"
            "2. 0.8R 浮盈保本移损保护：评估该点位能否在价格走出 0.8R 盈利时迅速触发 UPDATE_SL 移至开仓价保本。\n"
            "3. 陷阱与踩踏审查：是否存在流动性枯竭、多空拥挤度过高或巨鲸砸盘隐患？大级别逆势一律否决建议 WAIT。"
        ),
        "weight": 0.35,
        "enabled": True,
        "reasoning_effort": "high",
        "temperature": 0.1,
        "is_arbitrator": False,
        "model_id": "",
    },
    "quant": {
        "id": "quant",
        "name": "量化数理官 (Quant & Math)",
        "role_title": "客观中立 / 数学期望",
        "description": "纯粹基于数学公式与概率论，核验条件延续概率 P续、做功积分 E 以及 ADX 震荡过滤。",
        "prompt": (
            "【角色：R20 量化数理官】\n"
            "最高宪法授权：纯粹客观的数理概率推演，不听主观叙事，只认数学公式与期望值分布。\n\n"
            "【核心研判参数与插槽要求】：\n"
            "- 重点核验: {{smart_money}} (主力聪明钱持仓占比与大单多空偏好)\n"
            "- 重点核验: {{sentiment}} (全网舆情多空比与情绪极值衰竭)\n\n"
            "【数理准则与硬门禁】：\n"
            "1. 数学期望门禁：条件延续概率 P续 必须 ≥ 50%~55%，做功定积分 E 必须支持发单方向，预期盈亏比 R:R 必须 ≥ 2.0。\n"
            "2. 震荡过滤：若 1H ADX < 18 判定为伪动量高噪无序区间，根据统计假信号率超 70%，无条件建议 WAIT 观望。\n"
            "3. 资金流与筹码验证：CMF 资金流与主力聪明钱占比必须同向支撑，输出纯数据支持度评分与量化预期。"
        ),
        "weight": 0.30,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.1,
        "is_arbitrator": False,
        "model_id": "",
    },
    "arbitrator": {
        "id": "arbitrator",
        "name": "首席仲裁官 (Chief Arbitrator)",
        "role_title": "终审仲裁 / 契约落地",
        "description": "统领各专家参谋，依设定的共识准则去伪存真，最终收敛输出标准发单 JSON。",
        "prompt": (
            "【角色：R20 首席仲裁官兼执行官】\n"
            "你负责权衡各位参谋的辩论意见，在最高交易宪法下做出最终裁决，并强制输出全量点位参数。\n\n"
            "【仲裁与落地契约】：\n"
            "1. 严格遵照委员会共识策略进行加权收敛。\n"
            "2. 只有各参谋达成顺势共识、期望值明确且通过风控 2.0x ATR 审核时，方可批准开仓。\n"
            "3. 【发单必须输出全量点位，绝不允许只输出止损点】：\n"
            "   若判定开仓（BUY_LONG / SELL_SHORT），必须且只能完整输出：\n"
            "   - limit_price: 挂单入场限价（数字）\n"
            "   - stop_loss: 严格基于 1.8~2.2x 1H ATR 设置的止损价（数字）\n"
            "   - take_profit: 至少 2.0R 盈亏比的目标止盈价（数字）\n"
            "   - leverage: 杠杆倍数（整型 2~5）\n"
            "   - margin_usd: 下注保证金（数字）\n"
            "   - reasoning: 仲裁理由（明确说明采纳了哪位参谋的依据，否决了谁的观点）\n"
            "4. 最终必须且只能输出严格符合原有交易契约的 JSON 格式，绝不包含任何多余文本！"
        ),
        "weight": 1.0,
        "enabled": True,
        "reasoning_effort": "high",
        "temperature": 0.2,
        "is_arbitrator": True,
        "model_id": "",
    },
}

ADDITIONAL_PRESET_LIBRARY: Dict[str, Dict[str, Any]] = {
    "news_scout": {
        "id": "news_scout",
        "name": "舆情侦察官 (News Scout)",
        "role_title": "突发情报 / 链上异动",
        "description": "专注全网突发新闻、监管异动、黑天鹅熔断与极端狂热/恐慌情绪识别。",
        "prompt": (
            "【角色：R20 舆情与链上情报侦察官】\n"
            "你的职责是专门从全网突发资讯、市场情绪狂热度与链上大单角度进行独立研判：\n"
            "1. 审查当前是否有突发极端监管传闻、交易所脱锚或地缘事件；\n"
            "2. 警惕市场极度 FOMO 狂热时的诱多见顶信号，以及极度恐慌时的绝望割肉底；\n"
            "3. 提示链上大额转账异动与潜在巨鲸抛压。\n"
            "请对输入各标的给出情报面的支持或警示意见（50字内/币种）。"
        ),
        "weight": 0.25,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.3,
        "is_arbitrator": False,
        "model_id": "",
    },
    "macro": {
        "id": "macro",
        "name": "宏观策略官 (Macro Strategist)",
        "role_title": "流动性周期 / 大盘贝塔",
        "description": "研判美联储利率预期、美元指数 DXY、全球流动性潮汐与 BTC 龙头贝塔强弱。",
        "prompt": (
            "【角色：R20 宏观经济与流动性策略官】\n"
            "你的职责是从宏观经济与大盘全局流动性角度进行前瞻研判：\n"
            "1. 结合 DXY、美股联动与主流资金动向，确定当前处于增量风险偏好（Risk-On）还是存量避险（Risk-Off）；\n"
            "2. 判定当前山寨币走势是否受制于 BTC 强势吸血或流动性抽水；\n"
            "3. 给出大盘中长期趋势的宏观评分。"
        ),
        "weight": 0.25,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.3,
        "is_arbitrator": False,
        "model_id": "",
    },
    "whale_tracker": {
        "id": "whale_tracker",
        "name": "巨鲸穿透官 (Whale Tracker)",
        "role_title": "聪明钱透视 / 筹码分布",
        "description": "专注大额持仓异动、多空未平仓合约变化与大单成交集中度。",
        "prompt": (
            "【角色：R20 巨鲸与筹码穿透官】\n"
            "你的职责是盯防主力大户行为：\n"
            "1. 分析聪明钱（Top Traders）的真实多空占比变动；\n"
            "2. 识别主力挂单诱多诱空墙；\n"
            "3. 揭示未平仓合约（OI）异动背后的吸筹或派发真相。"
        ),
        "weight": 0.30,
        "enabled": True,
        "reasoning_effort": "high",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
}

ALL_AVAILABLE_PRESETS = {**DEFAULT_PRESET_TEMPLATES, **ADDITIONAL_PRESET_LIBRARY}

COUNCIL_PRESET_SUITES: Dict[str, Dict[str, Any]] = {
    "full_spectrum": {
        "id": "full_spectrum",
        "name": "全维度攻防博弈基准 (Full Spectrum Consensus)",
        "desc": "动量进攻 + 严苛风控 + 量化数理 + 首席终审仲裁（系统唯一权威全维度委员会基准方案）",
        "consensus_mode": "weighted",
        "roles": ["alpha", "risk", "quant", "arbitrator"],
    },
}


def get_available_presets() -> List[Dict[str, Any]]:
    return list(ALL_AVAILABLE_PRESETS.values())


def get_preset_suites() -> List[Dict[str, Any]]:
    return list(COUNCIL_PRESET_SUITES.values())


def apply_preset_suite(suite_id: str) -> Dict[str, Any]:
    suite = COUNCIL_PRESET_SUITES.get(suite_id)
    if not suite:
        raise ValueError(f"未知的预设套件 ID: {suite_id}")

    config = load_council_config()
    new_roles: Dict[str, Any] = {}
    for r_id in suite["roles"]:
        if r_id in ALL_AVAILABLE_PRESETS:
            preset = dict(ALL_AVAILABLE_PRESETS[r_id])
            old_model = config.get("roles", {}).get(r_id, {}).get("model_id", "")
            preset["model_id"] = old_model
            new_roles[r_id] = preset

    config["consensus_mode"] = suite.get("consensus_mode", "strict")
    config["roles"] = new_roles
    return save_council_config(config)


def reset_role_template(role_id: str) -> Dict[str, Any]:
    config = load_council_config()
    roles = config.get("roles", {})
    if role_id not in roles:
        raise ValueError(f"未找到角色 ID: {role_id}")

    preset = ALL_AVAILABLE_PRESETS.get(role_id)
    if not preset:
        if role_id == "arbitrator" or roles[role_id].get("is_arbitrator"):
            preset = DEFAULT_PRESET_TEMPLATES["arbitrator"]
        else:
            raise ValueError(f"该角色无内置出厂模板: {role_id}")

    old_model = roles[role_id].get("model_id", "")
    new_role = dict(preset)
    new_role["model_id"] = old_model
    roles[role_id] = new_role
    config["roles"] = roles
    return save_council_config(config)


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
                return data
        except Exception:
            pass

    default_config: Dict[str, Any] = {
        "enabled": False,
        "consensus_mode": "strict",  # strict (一票否决) | weighted (加权共识) | aggressive (动能突破优先)
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

    has_arbitrator = any(r.get("is_arbitrator") or k == "arbitrator" for k, r in roles.items())
    if not has_arbitrator:
        raise ValueError("委员会必须保留至少一位首席终审仲裁官！")

    for role_id, role in roles.items():
        if not isinstance(role, dict):
            raise ValueError(f"角色 {role_id} 配置必须为字典")
        role["id"] = role_id
        role.setdefault("enabled", True)
        role.setdefault("weight", 0.3)
        role.setdefault("reasoning_effort", "medium")
        role.setdefault("temperature", 0.2)

    config["consensus_mode"] = str(config.get("consensus_mode", "strict")).lower()
    if config["consensus_mode"] not in {"strict", "weighted", "aggressive"}:
        config["consensus_mode"] = "strict"

    config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _atomic_write_json(COUNCIL_CONFIG_FILE, config)
    return config


def _call_single_role(
    role_id: str,
    role_spec: Dict[str, Any],
    market_prompt: str,
    master_constitutional_rules: str,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Invokes a single advisor role with Master Strategy context inheritance."""
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

    # Seamless Master Constitutional Prompt Injection
    advisor_system_prompt = (
        f"【最高交易宪法与策略纪律】\n"
        f"{master_constitutional_rules}\n\n"
        f"====================================================\n"
        f"【你当前被赋予的委员会专家席位】\n"
        f"{prompt_content}\n"
        f"注意：你的一切研判必须严格以【最高交易宪法】为基础基准，绝不能脱离策略纪律凭空臆测！"
    )

    advisor_user_prompt = (
        f"【市场实时全景数据】\n"
        f"{market_prompt}\n\n"
        f"请严格以你「{role_name}」的专有视角，基于上述最高宪法进行审稿研判。\n"
        f"对关注标的逐一输出精炼评估（包含：倾向 BUY_LONG / SELL_SHORT / WAIT，置信度百分比，及核心审查理由，80字内/标的）。"
    )

    messages = [
        {"role": "system", "content": advisor_system_prompt},
        {"role": "user", "content": advisor_user_prompt},
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
            "content": f"参谋推演降级或异常: {e}",
            "reasoning": "",
            "latency_ms": 0,
            "weight": 0.0,
        }


def execute_council_debate(
    market_prompt: str,
    original_system_prompt: str,
    timeout: float = 60.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute the full Council deliberation workflow with master strategy inheritance and robust consensus convergence.

    Returns:
      (brain_output_dict, council_transcript_dict)
    """
    from r20_backend.llm_manager import execute_llm_request, get_active_llm_runtime, load_llm_config

    config = load_council_config()
    roles = config.get("roles", {})
    consensus_mode = config.get("consensus_mode", "strict")
    t_start = time.time()

    # Step 1: Identify Arbitrator and Active Advisors
    arbitrator_key = next(
        (k for k, r in roles.items() if r.get("is_arbitrator") or k == "arbitrator"),
        "arbitrator",
    )
    arbitrator_spec = roles.get(arbitrator_key, DEFAULT_PRESET_TEMPLATES["arbitrator"])
    advisor_keys = [
        k for k in roles.keys()
        if k != arbitrator_key and roles[k].get("enabled", True) is not False
    ]

    advisor_results: Dict[str, Dict[str, Any]] = {}
    if advisor_keys:
        # Allocate ~50% of the total budget to concurrent advisors (min 15s)
        member_timeout = max(15.0, timeout * 0.50)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(advisor_keys))) as pool:
            futures = {
                pool.submit(
                    _call_single_role,
                    key,
                    roles[key],
                    market_prompt,
                    original_system_prompt,
                    member_timeout,
                ): key
                for key in advisor_keys
            }
            for fut in concurrent.futures.as_completed(futures):
                key = futures[fut]
                try:
                    advisor_results[key] = fut.result()
                except Exception as exc:
                    advisor_results[key] = {
                        "role_id": key,
                        "role_name": roles[key].get("name", key),
                        "status": "error",
                        "content": f"Execution exception: {exc}",
                        "weight": 0.0,
                    }

    # Step 2: Compile the Structured Debate Transcript
    transcript_blocks = []
    for k in advisor_keys:
        res = advisor_results.get(k, {})
        weight_str = f" [权重: {res.get('weight', 1.0)}]" if res.get("weight") is not None else ""
        transcript_blocks.append(
            f"=== 【{res.get('role_name', k)}】现场研判（模型：{res.get('model_used', 'default')}{weight_str}）===\n"
            f"{res.get('content', '（该参谋未发言）')}\n"
        )
    compiled_debate = "\n".join(transcript_blocks) if transcript_blocks else "（无其他参谋发言，首席仲裁官独立推演）"

    # Step 3: Chief Arbitrator Final Verdict
    arb_model_id = arbitrator_spec.get("model_id") or ""
    override_model = None
    override_url = None
    override_key = None
    override_format = None
    override_effort = "high"
    arb_temperature = float(arbitrator_spec.get("temperature", 0.2))

    cfg = load_llm_config(mask_keys=False)
    if arb_model_id:
        for item in cfg.get("models", []):
            if item.get("id") == arb_model_id:
                override_model = item.get("id")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                override_effort = item.get("reasoning_effort") or "high"
                break
    else:
        override_effort = cfg.get("active_reasoning_effort", "high")

    consensus_instructions = {
        "strict": (
            "【当前委员会裁决准则：一票否决制 (STRICT_VETO)】\n"
            "- 本金安全与确定性高于一切！\n"
            "- 只要风控官或数理官明确提出假突破、止损垫不足 1.8x ATR 或大级别逆势风险，必须坚决执行一票否决，判定为 WAIT！\n"
            "- 只有在参谋们无硬伤反对、高度共识顺势且期望值明确时，方可批准开仓。"
        ),
        "weighted": (
            "【当前委员会裁决准则：加权共识制 (WEIGHTED_MAJORITY)】\n"
            "- 严格结合各位参谋发言附带的加权数值进行数学收敛。\n"
            "- 当且仅当顺势方向的加权支持度超过 65% 且不存在致命风控隐患时，方可批准开仓。\n"
            "- 遇重大分歧一律保守判定 WAIT 观望；若开单，必须遵照风控意见削减保证金。"
        ),
        "aggressive": (
            "【当前委员会裁决准则：动能猎手优先制 (MOMENTUM_PRIORITY)】\n"
            "- 重点采纳动量进攻官意见。\n"
            "- 若一阶速度 v 与二阶加速度 a 确认强顺势突破，允许小仓位试探出击，但止损必须严格遵守 2.0x ATR 纪律。"
        ),
    }.get(consensus_mode, "strict")

    arbitrator_system_prompt = (
        f"{original_system_prompt}\n\n"
        "====================================================\n"
        f"【特别授权：你现在是 R20 多模型决策委员会的首席仲裁官兼终审执行官】\n"
        f"{arbitrator_spec.get('prompt', '')}\n\n"
        f"{consensus_instructions}\n"
        "====================================================\n"
        "【终审发单契约强约束（必须输出全量点位，严禁遗漏！）】\n"
        "若对某标的做出开仓裁决（BUY_LONG 或 SELL_SHORT），decisions[标的] 内部必须且只能输出完整的四维点位与参数字典，绝不允许只输出止损点：\n"
        "{\n"
        '  "action": "BUY_LONG" 或 "SELL_SHORT" 或 "WAIT",\n'
        '  "confidence": 82,  // 置信度整数 0~100\n'
        '  "limit_price": 78250.0,  // 挂单入场限价（数字），严禁市价追高\n'
        '  "stop_loss": 76500.0,  // 严格基于 1.8~2.2x 1H ATR 结构外设置的止损价（数字）\n'
        '  "take_profit": 81750.0,  // 至少 2.0R 盈亏比的目标止盈价（数字）\n'
        '  "leverage": 3,  // 杠杆倍数（整型 2~5）\n'
        '  "margin_usd": 150.0,  // 单笔下注保证金额度（数字）\n'
        '  "reasoning": "仲裁理由（明确说明采纳了哪位参谋的依据，否决了谁的观点）"\n'
        "}\n"
        "若判定为 WAIT，只需输出 action: WAIT, confidence: 0~60, reasoning: 观望理由。\n"
        "你必须权衡各位参谋的攻防辩论，在【最高交易宪法】框架下去伪存真，做出最终全局决策，并严格输出标准 JSON 格式！"
    )

    arbitrator_user_prompt = (
        "【市场基础数据与多周期动力学因子】\n"
        f"{market_prompt}\n\n"
        "【委员会各专家参谋实录】\n"
        f"{compiled_debate}\n\n"
        "====================================================\n"
        "请作为首席仲裁官收敛全局裁决：\n"
        f"1. 在 macro_assessment 中明确说明共识模式（{consensus_mode}）下的裁决考量。\n"
        "2. 在各标的的 reasoning 中详细写出仲裁逻辑（采纳了哪位参谋的依据，否决了谁的观点）。\n"
        "3. 必须输出严格符合主交易系统契约的 JSON，根对象包含 decisions, position_management, macro_assessment 三个顶层键！"
    )

    rem_time = max(25.0, timeout - (time.time() - t_start))
    content, reasoning, usage, latency = execute_llm_request(
        messages=[
            {"role": "system", "content": arbitrator_system_prompt},
            {"role": "user", "content": arbitrator_user_prompt},
        ],
        model=override_model,
        base_url=override_url,
        api_key=override_key,
        api_format=override_format,
        reasoning_effort=override_effort,
        temperature=arb_temperature,
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
        raise ValueError("Arbitrator output root must be a JSON object")

    council_transcript = {
        "council_mode": True,
        "consensus_mode": consensus_mode,
        "total_duration_ms": int((time.time() - t_start) * 1000),
        "arbitrator": {
            "role_name": arbitrator_spec.get("name", "首席仲裁官"),
            "model_used": override_model or get_active_llm_runtime().get("model", "default"),
            "latency_ms": latency,
            "reasoning": reasoning,
        },
        "advisors": advisor_results,
    }

    brain_output["council_transcript"] = council_transcript
    return brain_output, council_transcript
