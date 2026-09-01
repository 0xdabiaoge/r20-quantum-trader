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
        "trading_system": """【交易风格：稳健】\n在不改变任何硬风控和输出 Schema 的前提下，优先选择多周期结构、微积分动能、聪明钱与概率优势一致的机会。证据冲突时宁可 WAIT；开仓保证金优先位于允许区间的中低部；不要为了提高交易频率降低置信度。""",
        "trading_user": """【稳健裁决偏好】\n优先确认趋势延续而非猜测拐点。只有风险收益比、流动性和结构同时成立时才开仓；对弱共振、动能衰减或新闻方向不明的标的输出 WAIT。""",
        "evolution_system": """【稳健复盘风格】\n复盘时优先识别导致回撤、过度交易、追价和低质量入场的模式；优化建议必须可降低尾部风险，同时避免把启发式经验写成新的死板阈值。""",
        "evolution_user": """【稳健进化任务】\n重点评估信号一致性、风险预算、入场耐心、手续费损耗和止损质量，优先沉淀能够降低回撤且不牺牲主要趋势收益的经验。""",
    },
    "aggressive": {
        "id": "aggressive",
        "name": "激进",
        "description": "提高高质量趋势与突破机会的参与度，但不放宽任何硬风控。",
        "editable": False,
        "trading_system": """【交易风格：激进】\n在所有硬风控、流动性门禁、OCO 和 JSON Schema 完全不变的前提下，提高对强趋势、放量突破、聪明钱共振和正加速度扩张机会的参与度。允许在证据高度一致时使用允许区间内较高的保证金与杠杆，但严禁逆势补仓、追逐失速行情或牺牲 R:R。""",
        "trading_user": """【激进裁决偏好】\n对 4H/1H 同向、15M 放量执行、加速度与延续概率共同扩张的机会果断决策；不要因为轻微噪声错过高置信趋势，但证据不一致时仍必须 WAIT。""",
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
