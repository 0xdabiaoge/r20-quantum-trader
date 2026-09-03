"""Multi-Agent Council Decision Engine for R20 Quantum Trader.

Architecture:
  Market Data (Snapshot)
           │
           ├─► Alpha Officer (进攻官)   ─┐
           ├─► Risk Officer (风控官)    ─┼─► Concurrent Debate (asyncio.gather / threads)
           └─► Quant Officer (数理官)   ─┘
                         │
                         ▼
             Chief Arbitrator (首席仲裁官)
                         │
                         ▼
        1. Standard Trading JSON (for ai_brain_trader发单)
        2. Council Discussion Transcript (for 前台推演审计展示)

Safety:
  - Fail-to-Fast: If council fails or times out, seamlessly falls back
    to single-model inference.
  - Zero-breakage: ai_brain_trader continues to receive the identical dict schema.
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
    },
    "arbitrator": {
        "id": "arbitrator",
        "name": "首席仲裁官 (Chief Arbitrator)",
        "role_title": "综合裁决 / 契约落地",
        "description": "权衡三位参谋的激辩，按确定性与加权逻辑出具最终决策，并强制输出标准交易 JSON。",
        "prompt": (
            "【角色：R20 首席仲裁官兼执行官】\n"
            "你负责听取「动量进攻官」、「保守风控官」与「量化数理官」三方的辩论意见，做出最终裁决。\n"
            "裁决准则：\n"
            "1. 若动量官强烈做多但风控官指出量价背离且数理官未确认，必须采纳风控官意见选择观望（WAIT）。\n"
            "2. 只有当动量官与数理官高度共识、且风控官未提出致命一票否决时，方可批准开仓，但须根据风控官意见动态调整保证金杠杆。\n"
            "3. 必须在 reasoning 中简明总结三方争辩核心（如「采纳进攻官方向，但遵照风控官意见缩减首仓」）。\n"
            "4. 最终必须且只能输出严格符合原有交易契约的 JSON 格式，不得包含任何其他文本！"
        ),
        "weight": 1.0,
    },
}


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
                if isinstance(data, dict) and "roles" in data:
                    return data
        except Exception:
            pass

    default_config: Dict[str, Any] = {
        "enabled": False,  # Off by default (speed-first)
        "timeout_seconds": 60.0,
        "roles": {
            "alpha": {
                **DEFAULT_PRESET_TEMPLATES["alpha"],
                "model_id": "",  # Empty means use active default LLM
            },
            "risk": {
                **DEFAULT_PRESET_TEMPLATES["risk"],
                "model_id": "",
            },
            "quant": {
                **DEFAULT_PRESET_TEMPLATES["quant"],
                "model_id": "",
            },
            "arbitrator": {
                **DEFAULT_PRESET_TEMPLATES["arbitrator"],
                "model_id": "",
            },
        },
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _atomic_write_json(COUNCIL_CONFIG_FILE, default_config)
    return default_config


def save_council_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and persist council configuration."""
    if not isinstance(config, dict):
        raise ValueError("Council config must be a dict")
    config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _atomic_write_json(COUNCIL_CONFIG_FILE, config)
    return config


def reset_role_template(role_id: str) -> Dict[str, Any]:
    """Reset a specific role to its factory default template."""
    if role_id not in DEFAULT_PRESET_TEMPLATES:
        raise ValueError(f"Unknown role id: {role_id}")
    config = load_council_config()
    target = DEFAULT_PRESET_TEMPLATES[role_id]
    current_model = config.get("roles", {}).get(role_id, {}).get("model_id", "")
    config.setdefault("roles", {})[role_id] = {
        **target,
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
    override_effort = "medium"

    if model_id:
        cfg = load_llm_config(mask_keys=False)
        for item in cfg.get("models", []):
            if item.get("id") == model_id:
                override_model = item.get("model")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                override_effort = item.get("reasoning_effort", "medium")
                break

    prompt_content = role_spec.get("prompt", "")
    messages = [
        {"role": "system", "content": prompt_content},
        {
            "role": "user",
            "content": (
                "【市场实时数据输入】\n"
                f"{market_prompt}\n\n"
                "请严格以你的专家角色进行研判。输出一段精炼的评估报告（包含各标的倾向：BUY_LONG / SELL_SHORT / WAIT，置信度及最核心理由）。"
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
            temperature=0.3,
            timeout=timeout,
        )
        return {
            "role_id": role_id,
            "role_name": role_spec.get("name", role_id),
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
            "role_name": role_spec.get("name", role_id),
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
    """Execute the full Council deliberation workflow.

    Returns:
      (brain_output_dict, council_transcript_dict)
    """
    from r20_backend.llm_manager import execute_llm_request, get_active_llm_runtime, load_llm_config

    config = load_council_config()
    roles = config.get("roles", {})
    t_start = time.time()

    # Step 1: Deliberate concurrently among advisors (Alpha, Risk, Quant)
    advisor_keys = ["alpha", "risk", "quant"]
    advisor_results: Dict[str, Dict[str, Any]] = {}

    # Allocate ~55% of the total budget to the concurrent advisors stage (min 15s)
    member_timeout = max(15.0, timeout * 0.55)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                _call_single_role,
                key,
                roles.get(key, DEFAULT_PRESET_TEMPLATES.get(key, {})),
                market_prompt,
                member_timeout,
            ): key
            for key in advisor_keys
            if key in roles or key in DEFAULT_PRESET_TEMPLATES
        }
        for fut in concurrent.futures.as_completed(futures):
            key = futures[fut]
            try:
                advisor_results[key] = fut.result()
            except Exception as exc:
                advisor_results[key] = {
                    "role_id": key,
                    "status": "error",
                    "content": f"Execution error: {exc}",
                    "weight": 0.0,
                }

    # Step 2: Compile the Debate Transcript for the Arbitrator
    transcript_blocks = []
    for k in advisor_keys:
        res = advisor_results.get(k, {})
        transcript_blocks.append(
            f"=== 【{res.get('role_name', k)}】研判意见（模型：{res.get('model_used', 'default')}）===\n"
            f"{res.get('content', '（无发言）')}\n"
        )
    compiled_debate = "\n".join(transcript_blocks)

    # Step 3: Chief Arbitrator Final Verdict & Strict JSON Synthesis
    arbitrator_spec = roles.get("arbitrator", DEFAULT_PRESET_TEMPLATES["arbitrator"])
    arb_model_id = arbitrator_spec.get("model_id") or ""
    override_model = None
    override_url = None
    override_key = None
    override_format = None
    override_effort = "high"

    if arb_model_id:
        cfg = load_llm_config(mask_keys=False)
        for item in cfg.get("models", []):
            if item.get("id") == arb_model_id:
                override_model = item.get("model")
                override_url = item.get("base_url")
                override_key = item.get("api_key")
                override_format = item.get("api_format")
                override_effort = item.get("reasoning_effort", "high")
                break

    arbitrator_system_prompt = (
        f"{original_system_prompt}\n\n"
        "====================================================\n"
        "【特别授权：你现在是 R20 多模型决策委员会的首席仲裁官】\n"
        f"{arbitrator_spec.get('prompt', '')}\n"
        "你必须权衡下方三位专家参谋的争辩记录，去伪存真，做出最终全局决策，并严格履行输出契约！"
    )

    arbitrator_user_prompt = (
        "【市场基础数据与多周期因子】\n"
        f"{market_prompt}\n\n"
        "【各专家参谋现场辩论实录】\n"
        f"{compiled_debate}\n\n"
        "====================================================\n"
        "请作为首席仲裁官做出最终决策！\n"
        "要求：\n"
        "1. 在 macro_assessment 中提炼宏观大势并点明委员会共识/分歧。\n"
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
        temperature=0.2,
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
        "total_duration_ms": int((time.time() - t_start) * 1000),
        "arbitrator": {
            "role_name": arbitrator_spec.get("name", "首席仲裁官"),
            "model_used": override_model or get_active_llm_runtime().get("model", "default"),
            "latency_ms": latency,
            "reasoning": reasoning,
        },
        "advisors": advisor_results,
    }

    # Inject the discussion transcript alongside the decision for frontend audit
    brain_output["council_transcript"] = council_transcript
    return brain_output, council_transcript
