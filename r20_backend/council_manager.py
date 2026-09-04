"""Multi-Agent Council Decision Engine for R20 Quantum Trader.

Architecture:
  Market Data (Snapshot)
           │
           ├─► Advisor 1 (e.g. 动量进攻官) ─┐
           ├─► Advisor 2 (e.g. 保守风控官) ─┼─► Concurrent Debate (ThreadPoolExecutor)
           ├─► Advisor N (e.g. 动态增减参谋) ─┘
                         │
                         ▼
             Chief Arbitrator (首席终审仲裁官)
                         │ (根据 consensus_mode 执行：一票否决 / 加权共识 / 动能优先)
                         ▼
        1. Standard Trading JSON (for ai_brain_trader发单)
        2. Council Discussion Transcript (for 前台推演审计展示)

Upgrades in v6.6.2:
  - Consensus Modes: strict (一票否决) / weighted (加权共识) / aggressive (突破优先)
  - Per-Role Enabled/Disabled Switch (灵活启闭，无需删除席位)
  - Per-Role Reasoning Effort & Temperature (独立长思考深度与采样温度)
  - Extended Advisor Library (+费率与基差套利官, +巨鲸与筹码穿透官)
  - One-Click Recommended Preset Suites (经典三权分立 / 六维全景 / 动量猎手)
  - Fail-to-Fast: If council fails or times out, seamlessly falls back to single-model.
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
        "role_title": "激进进攻 / 寻找 Alpha",
        "description": "敏锐捕捉微积分动能爆发、突破均线与聪明钱净流入，寻找高盈亏比机会。",
        "prompt": (
            "【角色：R20 动量进攻官】\n"
            "你的唯一职责是寻找市场中最具爆发力的做多与做空机会。你拥有极高的风险偏好，偏好顺势突破与动量加速：\n"
            "1. 重点分析微积分一阶速度 v 与二阶加速度 a：当 v>0 且 a>0 时强烈看多；当 v<0 且 a<0 时强烈看空。\n"
            "2. 紧盯聪明钱（Smart Money）净买入占比与主力资金流向，寻找量价共振启动点。\n"
            "3. 敢于在 ADX>20 动量确认时给出高置信度 (80%~95%) 的 BUY_LONG 或 SELL_SHORT 建议。\n"
            "请对输入的各币种简明扼要陈述你的进攻视角（50字内/币种），给出方向与置信度，并指出潜在获利空间。"
        ),
        "weight": 0.35,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.3,
        "is_arbitrator": False,
        "model_id": "",
    },
    "risk": {
        "id": "risk",
        "name": "保守风控官 (Paranoid Guardian)",
        "role_title": "极度谨慎 / 一票否决",
        "description": "持怀疑一切的态度，专找假突破陷阱、大级别背离与流动性滑点，保护本金安全。",
        "prompt": (
            "【角色：R20 保守风控官】\n"
            "你的唯一职责是保护本金，防止账户遭遇不可逆回撤。你的座右铭是「宁可错过十次行情，绝不承担一次灾难性风险」：\n"
            "1. 专门寻找陷阱：盘口流动性是否薄弱？是否存在严重多空踩踏？上方/下方是否存在巨鲸套牢抛压？\n"
            "2. 警惕假突破与背离：若价格创出新高但资金流 CMF 为负或 ADX<18，坚决投出反对票。\n"
            "3. 检查资金费率与杠杆磨损，一旦单边多头拥挤度过高，必须坚决制止追多。\n"
            "请对输入的各币种出具风控质询意见（50字内/币种），指出致命隐患，置信度不足一律建议 WAIT。"
        ),
        "weight": 0.35,
        "enabled": True,
        "reasoning_effort": "high",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "quant": {
        "id": "quant",
        "name": "量化数理官 (Quant & Math)",
        "role_title": "客观中立 / 数理阈值",
        "description": "完全基于数学公式与统计概率，ADX/CMF/深度比硬性卡点，排除情绪噪音。",
        "prompt": (
            "【角色：R20 量化数理官】\n"
            "你的唯一职责是纯粹客观的数理概率计算。你没有情绪，不听任何主观叙事，只认公式与统计阈值：\n"
            "1. 强震荡过滤：若 ADX < 18，根据统计回测此区间假信号率高达 71%，必须无条件判定为 WAIT。\n"
            "2. 资金流确认：CMF 必须与动能方向同向（做多需 CMF>0，做空需 CMF<0）。\n"
            "3. 盘口买卖盘深度比（Bid/Ask Depth Ratio）：失衡度必须支持发单方向。\n"
            "请基于纯数据指标输出你的概率评分与数理建议（50字内/币种）。"
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
        "role_title": "综合裁决 / 契约落地",
        "description": "权衡各位参谋的激辩，按共识策略出具最终决策，并强制输出标准交易 JSON。",
        "prompt": (
            "【角色：R20 首席仲裁官兼执行官】\n"
            "你负责听取各位专家参谋的辩论意见，做出最终裁决。\n"
            "裁决准则：\n"
            "1. 严格遵照设定的委员会共识策略（一票否决/加权共识/动能优先）进行裁决。\n"
            "2. 只有当共识达标、且符合风控边界时，方可批准开仓，并根据风控意见动态设定合理的保证金与杠杆。\n"
            "3. 必须在 reasoning 中简明总结各方争辩核心与仲裁取舍依据。\n"
            "4. 最终必须且只能输出严格符合原有交易契约的 JSON 格式，不得包含任何其他文本！"
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
            "你的职责是从宏观流动性与大盘贝塔（Beta）视角定调大周期：\n"
            "1. 评估当前大盘处于流动性扩张还是紧缩抽水阶段；\n"
            "2. 观察主流币（BTC/ETH）大趋势是否压制山寨币动能；\n"
            "3. 逆大盘宏观趋势不轻易开顺势重仓。\n"
            "请对输入标的给出宏观环境匹配度评分（50字内/币种）。"
        ),
        "weight": 0.25,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.3,
        "is_arbitrator": False,
        "model_id": "",
    },
    "orderbook": {
        "id": "orderbook",
        "name": "盘口微结构官 (Microstructure)",
        "role_title": "订单薄深度 / 费率滑点",
        "description": "关注买一卖一挂单厚度、Taker 成交冲击成本与多空费率拥挤度。",
        "prompt": (
            "【角色：R20 高频盘口与微结构官】\n"
            "你的职责是深入微观订单薄深度（Orderbook Depth）与实时资金费率：\n"
            "1. 检查买一卖一挂单价差（Spread）是否大于 0.05%，严禁在高滑点时刻开仓；\n"
            "2. 观察买卖盘深度比是否倾斜支持当前发单方向；\n"
            "3. 警惕高额持仓费率挤压。\n"
            "请从纯盘口与执行成本角度给出准入评估（50字内/币种）。"
        ),
        "weight": 0.25,
        "enabled": True,
        "reasoning_effort": "low",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "funding_arb": {
        "id": "funding_arb",
        "name": "资金费率与对冲官 (Funding Arbitrageur)",
        "role_title": "多空拥挤 / 费率收割",
        "description": "深度量化当前各标的年化资金费率与未平仓量 OI 异动，防范费率反噬与逼仓踩踏。",
        "prompt": (
            "【角色：R20 资金费率与基差量化官】\n"
            "你的职责是专注衍生品费率与未平仓合约结构：\n"
            "1. 监测资金费率年化是否异常高企（多头过度拥挤容易发生长下影洗盘，空头过度拥挤容易发生扎针逼空）；\n"
            "2. 结合 OI 异动识别真实主力建仓还是散户追涨杀跌；\n"
            "3. 在费率极端倒挂时提示多空潜在变盘点。\n"
            "请出具费率拥挤度评估与准入建议（50字内/币种）。"
        ),
        "weight": 0.25,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "whale_tracker": {
        "id": "whale_tracker",
        "name": "巨鲸筹码追踪官 (Whale Tracker)",
        "role_title": "大户持仓 / 筹码沉淀",
        "description": "穿透 OKX Top 100 实盘大户加权多空持仓均价、净敞口变化与现货大单流向。",
        "prompt": (
            "【角色：R20 巨鲸与大户筹码量化官】\n"
            "你的职责是监控顶级聪明钱与主力大户筹码动向：\n"
            "1. 对比大户多空比与散户多空比的背离度（聪明钱与散户往往对立）；\n"
            "2. 估算主力持仓成本线与安全垫；\n"
            "3. 严禁与巨鲸主力大单反向博弈。\n"
            "请从筹码博弈角度给出明确站队或警示建议（50字内/币种）。"
        ),
        "weight": 0.30,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.2,
        "is_arbitrator": False,
        "model_id": "",
    },
    "custom": {
        "id": "custom",
        "name": "自定义专家参谋 (Custom Advisor)",
        "role_title": "专项策略 / 自定义视角",
        "description": "由用户自由设定研判逻辑、专家背景与偏好的独立参谋角色。",
        "prompt": (
            "【角色：R20 自定义量化专家】\n"
            "请严格依据你设定的专业分析逻辑，对输入的各币种数据进行研判并输出核心意见（50字内/币种）。"
        ),
        "weight": 0.30,
        "enabled": True,
        "reasoning_effort": "medium",
        "temperature": 0.3,
        "is_arbitrator": False,
        "model_id": "",
    },
}

ALL_AVAILABLE_PRESETS = {**DEFAULT_PRESET_TEMPLATES, **ADDITIONAL_PRESET_LIBRARY}

COUNCIL_PRESET_SUITES: Dict[str, Dict[str, Any]] = {
    "classic_trio": {
        "id": "classic_trio",
        "name": "经典三权分立套件 (推荐)",
        "consensus_mode": "strict",
        "description": "动量进攻官 + 保守风控官 + 量化数理官 + 首席仲裁官。一票否决制，攻守兼备，适合稳健波段交易。",
        "roles": ["alpha", "risk", "quant", "arbitrator"],
    },
    "full_spectrum": {
        "id": "full_spectrum",
        "name": "六维全景参谋套件",
        "consensus_mode": "weighted",
        "description": "涵盖动量、风控、数理、舆情快讯、宏观周期与微观盘口。加权共识制，适合大资金全方位严密研判。",
        "roles": ["alpha", "risk", "quant", "news_scout", "macro", "orderbook", "arbitrator"],
    },
    "trend_hunter": {
        "id": "trend_hunter",
        "name": "极速突破猎手套件",
        "consensus_mode": "aggressive",
        "description": "动量进攻官 + 舆情侦察官 + 巨鲸筹码追踪官 + 首席仲裁官。突破优先制，适合牛市单边行情捕捉高动能机会。",
        "roles": ["alpha", "news_scout", "whale_tracker", "arbitrator"],
    },
}


def get_available_presets() -> List[Dict[str, Any]]:
    """Return all factory templates that can be used to add new roles or reset prompts."""
    return list(ALL_AVAILABLE_PRESETS.values())


def get_preset_suites() -> List[Dict[str, Any]]:
    """Return list of quick-apply recommendation suites."""
    return list(COUNCIL_PRESET_SUITES.values())


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def load_council_config() -> Dict[str, Any]:
    """Load council config from disk, initializing with default presets if absent."""
    if COUNCIL_CONFIG_FILE.exists():
        try:
            with open(COUNCIL_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "roles" in data and isinstance(data["roles"], dict):
                    # Ensure arbitrator exists and is marked as arbitrator
                    arb_found = False
                    for r_id, role in data["roles"].items():
                        role.setdefault("enabled", True)
                        role.setdefault("reasoning_effort", "medium")
                        role.setdefault("temperature", 0.3)
                        if role.get("is_arbitrator") or r_id == "arbitrator":
                            role["is_arbitrator"] = True
                            arb_found = True
                        else:
                            role.setdefault("is_arbitrator", False)
                    if not arb_found:
                        data["roles"]["arbitrator"] = dict(DEFAULT_PRESET_TEMPLATES["arbitrator"])
                    data.setdefault("consensus_mode", "strict")
                    return data
        except Exception:
            pass

    default_config: Dict[str, Any] = {
        "enabled": False,  # Off by default (speed-first)
        "consensus_mode": "strict",  # strict (一票否决) | weighted (加权共识) | aggressive (动能突破优先)
        "timeout_seconds": 60.0,
        "roles": {k: dict(v) for k, v in DEFAULT_PRESET_TEMPLATES.items()},
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _atomic_write_json(COUNCIL_CONFIG_FILE, default_config)
    return default_config


def save_council_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and persist council configuration."""
    if not isinstance(config, dict):
        raise ValueError("Council config must be a dict")
    roles = config.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise ValueError("委员会至少需要包含角色配置")

    # Ensure at least one arbitrator exists
    has_arbitrator = any(r.get("is_arbitrator") or k == "arbitrator" for k, r in roles.items())
    if not has_arbitrator:
        raise ValueError("委员会必须保留至少一位首席终审仲裁官以输出标准交易决策JSON！")

    # Validate each role
    for role_id, role in roles.items():
        if not isinstance(role, dict):
            raise ValueError(f"角色 {role_id} 配置必须为字典")
        if not str(role.get("name", "")).strip():
            raise ValueError(f"角色 {role_id} 名称不能为空")
        if not str(role.get("prompt", "")).strip():
            raise ValueError(f"角色 {role.get('name', role_id)} 的 System Prompt 不能为空")
        role["id"] = role_id
        role.setdefault("enabled", True)
        role.setdefault("weight", 0.3)
        role.setdefault("reasoning_effort", "medium")
        role.setdefault("temperature", 0.3)

    config["consensus_mode"] = str(config.get("consensus_mode", "strict")).lower()
    if config["consensus_mode"] not in {"strict", "weighted", "aggressive"}:
        config["consensus_mode"] = "strict"

    config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _atomic_write_json(COUNCIL_CONFIG_FILE, config)
    return config


def apply_preset_suite(suite_id: str) -> Dict[str, Any]:
    """One-click apply a recommended preset suite."""
    suite = COUNCIL_PRESET_SUITES.get(suite_id)
    if not suite:
        raise ValueError(f"未知的预设套件 ID: {suite_id}")

    config = load_council_config()
    new_roles: Dict[str, Any] = {}
    for r_id in suite["roles"]:
        if r_id in ALL_AVAILABLE_PRESETS:
            preset = dict(ALL_AVAILABLE_PRESETS[r_id])
            # Preserve existing model_id if previously configured
            old_model = config.get("roles", {}).get(r_id, {}).get("model_id", "")
            preset["model_id"] = old_model
            new_roles[r_id] = preset

    config["consensus_mode"] = suite.get("consensus_mode", "strict")
    config["roles"] = new_roles
    return save_council_config(config)


def reset_role_template(role_id: str) -> Dict[str, Any]:
    """Reset a specific role to its factory default template."""
    config = load_council_config()
    roles = config.get("roles", {})
    if role_id not in roles:
        raise ValueError(f"未找到角色 ID: {role_id}")

    preset = ALL_AVAILABLE_PRESETS.get(role_id)
    if not preset:
        if role_id == "arbitrator" or roles[role_id].get("is_arbitrator"):
            preset = DEFAULT_PRESET_TEMPLATES["arbitrator"]
        else:
            preset = ALL_AVAILABLE_PRESETS["custom"]

    current_model = roles[role_id].get("model_id", "")
    roles[role_id] = {
        **preset,
        "id": role_id,
        "name": preset["name"],
        "role_title": preset.get("role_title", "参谋专家"),
        "description": preset.get("description", ""),
        "prompt": preset["prompt"],
        "weight": preset.get("weight", 0.3),
        "enabled": True,
        "reasoning_effort": preset.get("reasoning_effort", "medium"),
        "temperature": preset.get("temperature", 0.3),
        "is_arbitrator": preset.get("is_arbitrator", False),
        "model_id": current_model,
    }
    return save_council_config(config)


def _call_single_role(
    role_id: str,
    role_spec: Dict[str, Any],
    market_prompt: str,
    timeout: float = 35.0,
) -> Dict[str, Any]:
    """Call one council member with its dedicated system prompt and return its viewpoint."""
    from r20_backend.llm_manager import execute_llm_request, get_active_llm_runtime, load_llm_config

    t0 = time.perf_counter()
    model_id = role_spec.get("model_id") or ""
    override_model = None
    override_url = None
    override_key = None
    override_format = None
    override_effort = role_spec.get("reasoning_effort") or "medium"
    temperature = float(role_spec.get("temperature", 0.3))

    if model_id:
        cfg = load_llm_config(mask_keys=False)
        for item in cfg.get("models", []):
            if item.get("id") == model_id:
                override_model = item.get("model")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                if not role_spec.get("reasoning_effort"):
                    override_effort = item.get("reasoning_effort", "medium")
                break

    prompt_content = role_spec.get("prompt", "")
    role_name = role_spec.get("name", role_id)
    messages = [
        {"role": "system", "content": prompt_content},
        {
            "role": "user",
            "content": (
                f"【市场实时数据输入】\n{market_prompt}\n\n"
                f"请严格以你「{role_name}」的专有视角进行研判。输出一段精炼的评估报告（包含各标的倾向：BUY_LONG / SELL_SHORT / WAIT，置信度及最核心理由）。"
            ),
        },
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
            "error": str(e),
            "content": f"[参谋超时/错误: {e}] 自动弃权",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "weight": 0.0,
        }


def execute_council_debate(
    market_prompt: str,
    original_system_prompt: str,
    timeout: float = 60.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute the full Council deliberation workflow with dynamic roles and consensus modes.

    Returns:
      (brain_output_dict, council_transcript_dict)
    """
    from r20_backend.llm_manager import execute_llm_request, get_active_llm_runtime, load_llm_config

    config = load_council_config()
    roles = config.get("roles", {})
    consensus_mode = config.get("consensus_mode", "strict")
    t_start = time.time()

    # Step 1: Identify Arbitrator and Advisors dynamically
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
        # Allocate ~55% of the total budget to concurrent advisors (min 15s)
        member_timeout = max(15.0, timeout * 0.55)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(advisor_keys))) as pool:
            futures = {
                pool.submit(
                    _call_single_role,
                    key,
                    roles[key],
                    market_prompt,
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
                        "content": f"Execution error: {exc}",
                        "weight": 0.0,
                    }

    # Step 2: Compile the Debate Transcript for the Arbitrator
    transcript_blocks = []
    for k in advisor_keys:
        res = advisor_results.get(k, {})
        weight_str = f" [权重: {res.get('weight', 1.0)}]" if res.get('weight') is not None else ""
        transcript_blocks.append(
            f"=== 【{res.get('role_name', k)}】研判意见（模型：{res.get('model_used', 'default')}{weight_str}）===\n"
            f"{res.get('content', '（无发言）')}\n"
        )
    compiled_debate = "\n".join(transcript_blocks) if transcript_blocks else "（无其他参谋发言，请独立决策）"

    # Step 3: Chief Arbitrator Final Verdict based on consensus protocol
    arb_model_id = arbitrator_spec.get("model_id") or ""
    override_model = None
    override_url = None
    override_key = None
    override_format = None
    override_effort = arbitrator_spec.get("reasoning_effort") or "high"
    arb_temperature = float(arbitrator_spec.get("temperature", 0.2))

    if arb_model_id:
        cfg = load_llm_config(mask_keys=False)
        for item in cfg.get("models", []):
            if item.get("id") == arb_model_id:
                override_model = item.get("model")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                if not arbitrator_spec.get("reasoning_effort"):
                    override_effort = item.get("reasoning_effort", "high")
                break

    consensus_instructions = {
        "strict": (
            "【当前委员会裁决准则：一票否决制 (VETO_PROTECTION)】\n"
            "- 胜率与本金安全高于一切！\n"
            "- 只要任何参谋（特别是风控官或数理官）提出量价背离、盘口脆弱、大级别逆势或潜在陷阱，必须坚决执行一票否决，判定为 WAIT 观望！\n"
            "- 只有在各参谋无反对意见且具备高度顺势共识时，方可批准小仓位顺势入场。"
        ),
        "weighted": (
            "【当前委员会裁决准则：加权共识制 (WEIGHTED_MAJORITY)】\n"
            "- 综合参考各位参谋发言附带的权重数值。\n"
            "- 只有当顺势方向的加权支持度超过 60% 且未发生严重致命逻辑硬伤时，方可批准开仓。\n"
            "- 若分歧较大或双方势均力敌，应保守选择 WAIT 观望；若开单，须遵照风控建议缩减保证金与杠杆。"
        ),
        "aggressive": (
            "【当前委员会裁决准则：动能突破优先制 (ALPHA_HUNTER)】\n"
            "- 重点关注动量进攻官、舆情与巨鲸大单流向。\n"
            "- 若一阶速度 v 与二阶加速度 a 确认强突破，即使存在局部小幅分歧，也允许批准小仓顺势试探发单，但必须严格配置云端 OCO 止损。"
        ),
    }.get(consensus_mode, "strict")

    advisors_list_str = "、".join([roles[k].get("name", k) for k in advisor_keys]) or "相关参谋"
    arbitrator_system_prompt = (
        f"{original_system_prompt}\n\n"
        "====================================================\n"
        f"【特别授权：你现在是 R20 多模型决策委员会的{arbitrator_spec.get('name', '首席仲裁官')}】\n"
        f"{arbitrator_spec.get('prompt', '')}\n\n"
        f"{consensus_instructions}\n"
        f"你必须权衡各专家参谋（{advisors_list_str}）的争辩记录，去伪存真，做出最终全局决策，并严格履行输出契约！"
    )

    arbitrator_user_prompt = (
        "【市场基础数据与多周期因子】\n"
        f"{market_prompt}\n\n"
        "【各专家参谋现场辩论实录】\n"
        f"{compiled_debate}\n\n"
        "====================================================\n"
        "请作为首席仲裁官做出最终决策！\n"
        "要求：\n"
        f"1. 在 macro_assessment 中明确说明共识模式（{consensus_mode}）下的裁决考量。\n"
        "2. 在各标的的 reasoning 中写出仲裁理由（采纳了谁的观点，驳回了谁）。\n"
        "3. 严格输出标准 JSON 格式，顶层必须包含 decisions, position_management, macro_assessment 三个键！"
    )

    # Ensure arbitrator has at least 20s or remaining budget
    rem_time = max(20.0, timeout - (time.time() - t_start))
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

    # Inject discussion transcript alongside the decision for frontend audit
    brain_output["council_transcript"] = council_transcript
    return brain_output, council_transcript
