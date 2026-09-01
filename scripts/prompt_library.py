"""R20 prompt-style library. Python callers still construct and send prompts directly."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_FILE = ROOT / "data" / "prompt_library.json"

PRESETS: dict[str, dict[str, Any]] = {
    "stable": {
        "id": "stable",
        "name": "稳健",
        "description": "重视信号一致性、回撤控制与等待质量，当前默认风格。",
        "editable": False,
        "trading_system": """【交易风格：稳健】\n仅在 P0 硬约束允许的候选中偏好高质量证据共振。要求 4H 方向、1H 结构、1H 微积分动力学、定积分能量、概率风险与量能资金形成可解释链条；证据冲突或缺失时 WAIT。保证金优先位于允许区间中低部，不为提高频率降低置信度。""",
        "trading_user": """【稳健裁决偏好】\n优先确认趋势延续，不猜测拐点。非 WAIT 决策必须引用具体 1H v/a/j/I、E/A、延续或击穿估计概率及 VaR/CVaR；新闻未知不是市场平稳证据，弱共振或肥尾风险扩张时 WAIT。""",
        "evolution_system": """【稳健复盘风格】\n优先识别回撤、过度交易、追价和低质量入场，但只使用真实可观测证据。小样本、数理快照缺失或因果不可辨时 NO_CHANGE；任何记忆都不得成为绕过硬风控的新阈值。""",
        "evolution_user": """【稳健进化任务】\n评估信号一致性、风险预算、手续费、入场与退出质量；只有多个独立样本支持时才沉淀新经验，否则保留旧记忆并提出需要补充的证据。""",
    },
    "aggressive": {
        "id": "aggressive",
        "name": "激进",
        "description": "提高高质量趋势与突破机会的参与度，但不放宽任何硬风控。",
        "editable": False,
        "trading_system": """【交易风格：激进】\n所有 P0 硬约束、OCO 与 JSON 契约保持不变。仅对 4H/1H 同向、1H 动力学与积分能量扩张、概率风险可接受且量能共振的机会提高参与度；可使用允许区间较高的保证金和杠杆，但不得逆势补仓、追逐失速行情或牺牲 R:R。""",
        "trading_user": """【激进裁决偏好】\n对证据链完整的强趋势果断决策，必须引用具体 1H v/a/j/I、E/A、方向估计概率及 VaR/CVaR。15M 只优化执行；高 jerk、肥尾或证据不一致时仍必须 WAIT。""",
        "evolution_system": """【激进复盘风格】\n复盘时同时识别错失强趋势、过早止盈和仓位利用不足，也必须审查追价、过度杠杆和假突破损失；任何进化建议不得削弱硬风控。""",
        "evolution_user": """【激进进化任务】\n重点比较高动能机会的参与率、趋势利润捕获、加仓时机与错失成本，同时检查激进参与是否造成尾部亏损扩大。""",
    },
}

EMPTY_CUSTOM = {
    "id": "custom",
    "name": "自定义",
    "description": "管理员自定义风格附加层。",
    "editable": True,
    "trading_system": "",
    "trading_user": "",
    "evolution_system": "",
    "evolution_user": "",
}


def _default() -> dict[str, Any]:
    return {"version": 1, "active_style": "stable", "custom": dict(EMPTY_CUSTOM)}


def load_library() -> dict[str, Any]:
    payload = _default()
    try:
        raw = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            payload.update(raw)
            payload["custom"] = {**EMPTY_CUSTOM, **(raw.get("custom") or {})}
    except (OSError, json.JSONDecodeError):
        pass
    if payload.get("active_style") not in {"stable", "aggressive", "custom"}:
        payload["active_style"] = "stable"
    return payload


def save_library(payload: dict[str, Any]) -> None:
    normalized = _default()
    normalized["active_style"] = payload.get("active_style", "stable")
    normalized["custom"] = {**EMPTY_CUSTOM, **(payload.get("custom") or {})}
    LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".prompt-library-", suffix=".tmp", dir=LIBRARY_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, LIBRARY_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def active_profile() -> dict[str, Any]:
    library = load_library()
    style = library["active_style"]
    return dict(library["custom"] if style == "custom" else PRESETS[style])


def all_profiles() -> list[dict[str, Any]]:
    library = load_library()
    return [dict(PRESETS["stable"]), dict(PRESETS["aggressive"]), dict(library["custom"])]


def append_layer(base: str, layer: str, label: str) -> str:
    layer = (layer or "").strip()
    return base if not layer else f"{base.rstrip()}\n\n======================= 【{label}】 =======================\n{layer}"
