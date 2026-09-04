"""Unified multi-format LLM management, connection testing, and runtime dispatch.
Supports:
1. openai_chat: OpenAI Standard /chat/completions (OpenAI, Gemini OpenAI endpoint, DeepSeek, etc.)
2. openai_responses: OpenAI Structured /responses API (Responses API format)
3. claude_messages: Anthropic Claude /messages API (Claude 3.7 / 3.5 native)
"""
from __future__ import annotations
import json
import os
import re
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LLM_CONFIG_FILE = DATA_DIR / "llm_models.json"
LEGACY_PROVIDERS_FILE = DATA_DIR / "llm_providers.json"

SUPPORTED_API_FORMATS = [
    {"id": "openai_chat", "name": "OpenAI Chat (/chat/completions)", "desc": "标准 ChatML 对话格式，兼容 OpenAI/Gemini/DeepSeek/中继"},
    {"id": "openai_responses", "name": "OpenAI Responses (/responses)", "desc": "OpenAI 最新 Complete Responses API 结构化接口"},
    {"id": "claude_messages", "name": "Claude Messages (/messages)", "desc": "Anthropic Claude 原生 Messages API，支持原生 CoT 思考"},
]

STANDARD_REASONING_EFFORTS = ["high", "medium", "low", "minimal", "none", "auto"]

DEFAULT_PROVIDERS = [
    {
        "id": "openrouter",
        "name": "OpenRouter (全球聚合路由)",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "全球模型路由聚合中继，汇集 OpenAI、Anthropic、Google、DeepSeek 等 400+ 旗舰大模型，支持一键动态拉取全量模型",
    },
    {
        "id": "opencode",
        "name": "OpenCode (AI开放云平台)",
        "base_url": "https://api.opencode.cn/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "聚合国内外多家公司旗舰大模型，支持一键拉取平台模型列表",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek 官方直连",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "DeepSeek V3 / R1 官方高性价比推理端点",
    },
    {
        "id": "anthropic",
        "name": "Anthropic 官方直连",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "api_format": "claude_messages",
        "description": "Claude 3.7 / 3.5 官方原生 Messages 协议直连，支持长思维链推演",
    },
    {
        "id": "google",
        "name": "Google AI Studio",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "Google Gemini 官方 OpenAI 兼容接口，百万级超长上下文",
    },
    {
        "id": "openai",
        "name": "OpenAI 官方直连",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "OpenAI 官方 ChatGPT/o3/o4/GPT-4o 旗舰直连",
    },
    {
        "id": "dashscope",
        "name": "阿里云百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "阿里通义千问 Qwen Max / QwQ 官方兼容端点",
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow (硅基流动)",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "国内主流开源大模型高并发托管平台",
    },
    {
        "id": "custom",
        "name": "R20 自定义网关 / 中继",
        "base_url": "https://cpa.r20.cn/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "description": "当前生产环境配置的主力代理与自定义中继",
    },
]

FLAGSHIP_PRESETS = [
    {
        "label": "Gemini 3.8 Flash (生产推荐)",
        "id": "gemini-3.8-flash-high",
        "name": "Gemini 3.8 Flash (高思维链)",
        "api_format": "openai_chat",
        "base_url": "https://cpa.r20.cn/v1",
        "provider": "Google Gemini / CPA代理",
        "provider_id": "custom",
        "effort": "high",
        "desc": "当前生产主力模型，百万超长上下文，支持高深度长思维链",
    },
    {
        "label": "Claude 3.7 Sonnet (Thinking)",
        "id": "claude-3-7-sonnet-20250219",
        "name": "Claude 3.7 Sonnet (Thinking CoT)",
        "api_format": "claude_messages",
        "base_url": "https://api.anthropic.com/v1",
        "provider": "Anthropic 官方",
        "provider_id": "anthropic",
        "effort": "high",
        "desc": "Anthropic 旗舰长链推演模型，极高代码与波段推理决策胜率",
    },
    {
        "label": "OpenAI o3 顶级数理逻辑",
        "id": "o3",
        "name": "OpenAI o3 顶级数理推理",
        "api_format": "openai_responses",
        "base_url": "https://api.openai.com/v1",
        "provider": "OpenAI 官方",
        "provider_id": "openai",
        "effort": "high",
        "desc": "OpenAI 新一代数理逻辑顶峰，多阶微积分与因果推演旗舰",
    },
    {
        "label": "DeepSeek V3.1 / R1 满血",
        "id": "deepseek-reasoner",
        "name": "DeepSeek R1 满血推理 (671B)",
        "api_format": "openai_chat",
        "base_url": "https://api.deepseek.com/v1",
        "provider": "DeepSeek 官方",
        "provider_id": "deepseek",
        "effort": "high",
        "desc": "纯血开源强化学习推理架构，极高性价比与因果微结构穿透力",
    },
    {
        "label": "通义千问 Qwen Max Latest",
        "id": "qwen-max-latest",
        "name": "通义千问 Qwen Max Latest",
        "api_format": "openai_chat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "provider": "阿里云百炼",
        "provider_id": "dashscope",
        "effort": "high",
        "desc": "阿里最强大模型，超高中文金融理解与量化因子综合感知",
    },
    {
        "label": "OpenRouter 聚合旗舰",
        "id": "google/gemini-3.8-flash",
        "name": "OpenRouter: Gemini 3.8 Flash",
        "api_format": "openai_chat",
        "base_url": "https://openrouter.ai/api/v1",
        "provider": "OpenRouter 聚合",
        "provider_id": "openrouter",
        "effort": "high",
        "desc": "通过 OpenRouter 路由接入，自动故障转移与全球低延时",
    },
    {
        "label": "OpenCode 旗舰直连",
        "id": "deepseek-ai/DeepSeek-V3",
        "name": "OpenCode: DeepSeek V3 旗舰",
        "api_format": "openai_chat",
        "base_url": "https://api.opencode.cn/v1",
        "provider": "OpenCode 平台",
        "provider_id": "opencode",
        "effort": "high",
        "desc": "OpenCode 开发者平台直连，聚合多厂商高并发旗舰大模型",
    },
]


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


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * 8}{value[-visible:]}"


def _detect_reasoning_type(model_id: str) -> str:
    m = model_id.lower()
    if "deepseek-reasoner" in m or "deepseek-r1" in m or "-r1" in m:
        return "deepseek_reasoner"
    if (
        m.startswith(("o1", "o3", "o4"))
        or "/o1" in m or "/o3" in m or "/o4" in m
        or "gemini" in m
        or "claude-3-7" in m
        or "claude-3.7" in m
        or "qwq" in m
    ):
        return "standard_effort"
    if "chat" in m or "gpt-4o" in m or "gpt-3" in m or "qwen" in m or "llama" in m:
        return "none"
    return "auto"


def _detect_api_format(url: str, model_id: str) -> str:
    u = url.lower()
    m = model_id.lower()
    if "anthropic.com" in u or "claude" in u or "claude" in m and "messages" in u:
        return "claude_messages"
    if "responses" in u:
        return "openai_responses"
    return "openai_chat"


def init_llm_config() -> Dict[str, Any]:
    """Load or initialize clean, user-centric model configuration with multi-provider support."""
    from .config import settings

    if LLM_CONFIG_FILE.exists():
        try:
            with open(LLM_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "models" in data and isinstance(data["models"], list):
                    if "providers" not in data or not isinstance(data.get("providers"), list):
                        data["providers"] = [dict(p) for p in DEFAULT_PROVIDERS]
                        active_m = data["models"][0] if data["models"] else None
                        if active_m:
                            cust = next((p for p in data["providers"] if p["id"] == "custom"), None)
                            if cust:
                                cust["base_url"] = active_m.get("base_url") or cust["base_url"]
                                cust["api_key"] = active_m.get("api_key") or ""
                        _atomic_write_json(LLM_CONFIG_FILE, data)
                    return data
        except Exception:
            pass

    # Check migration from legacy llm_providers.json if present
    migrated_models = []
    active_m_id = "gemini-3.8-flash-high"
    active_effort = "high"

    if LEGACY_PROVIDERS_FILE.exists():
        try:
            with open(LEGACY_PROVIDERS_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
                active_pid = old.get("active_provider_id", "")
                active_m_id = old.get("active_model_id") or active_m_id
                active_effort = old.get("active_reasoning_effort") or active_effort
                for p in old.get("providers", []):
                    p_url = p.get("base_url", "")
                    p_key = p.get("api_key", "")
                    p_name = p.get("name", "")
                    for m in p.get("models", []):
                        mid = m.get("id")
                        if not mid:
                            continue
                        if p_key or p.get("id") == active_pid or mid == active_m_id:
                            migrated_models.append({
                                "id": mid,
                                "name": m.get("name") or mid,
                                "provider_name": p_name or "默认供应商",
                                "base_url": p_url,
                                "api_key": p_key,
                                "api_format": _detect_api_format(p_url, mid),
                                "reasoning_type": m.get("reasoning_type", _detect_reasoning_type(mid)),
                                "reasoning_effort": m.get("default_effort", active_effort),
                                "description": m.get("description", ""),
                            })
        except Exception:
            pass

    # If empty, extract current settings from .env / settings
    if not migrated_models:
        cur_url = getattr(settings, "llm_base_url", "") or os.getenv("LLM_BASE_URL") or "https://cpa.r20.cn/v1"
        cur_key = getattr(settings, "llm_api_key", "") or os.getenv("LLM_API_KEY") or ""
        cur_model = getattr(settings, "llm_model", "") or os.getenv("LLM_MODEL") or "gemini-3.8-flash-high"
        cur_effort = getattr(settings, "llm_reasoning_effort", "") or os.getenv("LLM_REASONING_EFFORT") or "high"
        active_m_id = cur_model
        active_effort = cur_effort

        migrated_models.append({
            "id": cur_model,
            "name": f"{cur_model} (当前生产模型)",
            "provider_name": "自定义网关/代理",
            "base_url": cur_url,
            "api_key": cur_key,
            "api_format": _detect_api_format(cur_url, cur_model),
            "reasoning_type": _detect_reasoning_type(cur_model),
            "reasoning_effort": cur_effort if cur_effort in STANDARD_REASONING_EFFORTS else "high",
            "description": "当前运行环境配置的主力模型",
        })

    # Ensure active model is in list
    if not any(m["id"] == active_m_id for m in migrated_models):
        active_m_id = migrated_models[0]["id"]

    init_providers = [dict(p) for p in DEFAULT_PROVIDERS]
    cust_prov = next((p for p in init_providers if p["id"] == "custom"), None)
    if cust_prov and migrated_models:
        cust_prov["base_url"] = migrated_models[0].get("base_url") or cust_prov["base_url"]
        cust_prov["api_key"] = migrated_models[0].get("api_key") or ""

    config = {
        "version": "3.0",
        "active_model_id": active_m_id,
        "active_reasoning_effort": active_effort,
        "providers": init_providers,
        "models": migrated_models,
    }
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return config


# Backwards compatibility alias for app.py
LLM_PROVIDERS_FILE = LLM_CONFIG_FILE
init_llm_providers = init_llm_config


def load_llm_config(mask_keys: bool = True) -> Dict[str, Any]:
    """Return clean model configurations and configured providers."""
    config = init_llm_config()
    providers_list = config.get("providers", [])

    res: Dict[str, Any] = {
        "version": config.get("version", "3.0"),
        "active_model_id": config.get("active_model_id", "gemini-3.8-flash-high"),
        "active_reasoning_effort": config.get("active_reasoning_effort", "high"),
        "standard_reasoning_efforts": STANDARD_REASONING_EFFORTS,
        "supported_api_formats": SUPPORTED_API_FORMATS,
        "flagship_presets": FLAGSHIP_PRESETS,
        "providers": [],
        "models": [],
        "active_provider_id": "custom",
    }

    # Format providers list
    for p in providers_list:
        pid = p.get("id", "")
        p_base = p.get("base_url", "").rstrip("/")
        m_count = sum(
            1 for m in config.get("models", [])
            if m.get("provider_id") == pid or (not m.get("provider_id") and m.get("base_url", "").rstrip("/") == p_base)
        )
        p_copy = {
            "id": pid,
            "name": p.get("name", pid),
            "base_url": p.get("base_url", ""),
            "api_format": p.get("api_format", "openai_chat"),
            "description": p.get("description", ""),
            "has_key": bool(p.get("api_key")),
            "models_count": m_count,
        }
        if mask_keys:
            p_copy["api_key_masked"] = mask_secret(p.get("api_key", ""))
        else:
            p_copy["api_key"] = p.get("api_key", "")
        res["providers"].append(p_copy)

    # Format models list
    for m in config.get("models", []):
        m_pid = m.get("provider_id", "")
        p_entry = next((p for p in providers_list if p.get("id") == m_pid), None)
        if not p_entry:
            m_base = m.get("base_url", "").rstrip("/")
            p_entry = next((p for p in providers_list if p.get("base_url", "").rstrip("/") == m_base), None)
            if p_entry:
                m_pid = p_entry.get("id")

        m_key = m.get("api_key", "")
        has_key = bool(m_key or (p_entry and p_entry.get("api_key")))

        m_copy = {
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "provider_id": m_pid or "custom",
            "provider_name": m.get("provider_name") or (p_entry.get("name") if p_entry else "自定义"),
            "base_url": m.get("base_url", "") or (p_entry.get("base_url", "") if p_entry else ""),
            "api_format": m.get("api_format", "openai_chat"),
            "reasoning_type": m.get("reasoning_type", "auto"),
            "reasoning_effort": m.get("reasoning_effort", "high"),
            "description": m.get("description", ""),
            "has_key": has_key,
        }
        if mask_keys:
            m_copy["api_key_masked"] = mask_secret(m_key) if m_key else (mask_secret(p_entry.get("api_key", "")) if p_entry and p_entry.get("api_key") else "")
        else:
            m_copy["api_key"] = m_key
        res["models"].append(m_copy)

    return res


def get_active_llm_runtime() -> Dict[str, Any]:
    """Retrieve active LLM credentials and configuration for runtime execution."""
    from .config import settings
    config = init_llm_config()
    active_mid = config.get("active_model_id", "")
    active_effort = config.get("active_reasoning_effort", "high")

    target_model = next((m for m in config.get("models", []) if m["id"] == active_mid), None)

    base_url = target_model.get("base_url") if target_model else getattr(settings, "llm_base_url", "")
    api_key = target_model.get("api_key") if target_model else getattr(settings, "llm_api_key", "")
    provider_id = target_model.get("provider_id", "") if target_model else ""
    provider_name = target_model.get("provider_name", "") if target_model else "默认"

    # If api_key or base_url missing in model, inherit from provider
    if target_model:
        t_base = target_model.get("base_url", "").rstrip("/")
        prov = next(
            (
                p for p in config.get("providers", [])
                if p.get("id") == provider_id or (t_base and p.get("base_url", "").rstrip("/") == t_base)
            ),
            None,
        )
        if prov:
            if not api_key:
                api_key = prov.get("api_key", "")
            if not base_url:
                base_url = prov.get("base_url", "")
            if not provider_name or provider_name == "自定义":
                provider_name = prov.get("name", provider_name)
            if not provider_id:
                provider_id = prov.get("id", "custom")

    base_url = (base_url or os.getenv("LLM_BASE_URL", "https://cpa.r20.cn/v1")).rstrip("/")
    api_key = api_key or os.getenv("LLM_API_KEY", "")

    model_name = active_mid or getattr(settings, "llm_model", "gemini-3.8-flash-high")
    api_format = target_model.get("api_format") if target_model else _detect_api_format(base_url, model_name)
    reasoning_type = target_model.get("reasoning_type", "auto") if target_model else _detect_reasoning_type(model_name)

    return {
        "model": model_name,
        "name": target_model.get("name", model_name) if target_model else model_name,
        "provider_name": provider_name or "默认",
        "provider_id": provider_id or "custom",
        "base_url": base_url,
        "api_key": api_key,
        "api_format": api_format,
        "reasoning_effort": active_effort,
        "reasoning_type": reasoning_type,
    }


def activate_provider_model(provider_id: str, model_id: str, reasoning_effort: Optional[str] = None) -> Dict[str, Any]:
    """One-click switch to activate a model. Updates config, .env, and encrypted store."""
    from .settings_store import update_env
    from .config import refresh_settings
    try:
        from r20_gateway.secrets import save_secrets
    except ImportError:
        save_secrets = None

    config = init_llm_config()
    target_model = next((m for m in config.get("models", []) if m["id"] == model_id), None)
    if not target_model:
        # Create minimal entry if missing
        target_model = {
            "id": model_id,
            "name": model_id,
            "provider_name": "自定义",
            "base_url": os.getenv("LLM_BASE_URL", "https://cpa.r20.cn/v1"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "api_format": "openai_chat",
            "reasoning_type": _detect_reasoning_type(model_id),
            "reasoning_effort": "high",
            "description": "一键激活时自动收录",
        }
        config.setdefault("models", []).append(target_model)

    effort = reasoning_effort or target_model.get("reasoning_effort") or "high"
    if effort not in STANDARD_REASONING_EFFORTS:
        effort = "auto"

    config["active_model_id"] = model_id
    config["active_reasoning_effort"] = effort
    _atomic_write_json(LLM_CONFIG_FILE, config)

    # Sync to .env and secrets
    base_url = target_model.get("base_url", "")
    api_key = target_model.get("api_key", "")
    m_pid = target_model.get("provider_id")
    if m_pid:
        prov = next((p for p in config.get("providers", []) if p.get("id") == m_pid), None)
        if prov:
            if not api_key:
                api_key = prov.get("api_key", "")
            if not base_url:
                base_url = prov.get("base_url", "")

    base_url = (base_url or os.getenv("LLM_BASE_URL", "https://cpa.r20.cn/v1")).rstrip("/")

    env_values = {
        "LLM_BASE_URL": base_url,
        "LLM_MODEL": model_id,
        "LLM_REASONING_EFFORT": effort,
    }
    if api_key:
        env_values["LLM_API_KEY"] = api_key
        if save_secrets:
            save_secrets({"LLM_API_KEY": api_key})

    update_env(env_values)
    refresh_settings()

    return {
        "success": True,
        "active_model_id": model_id,
        "active_model_name": target_model.get("name"),
        "active_reasoning_effort": effort,
        "base_url": base_url,
        "api_format": target_model.get("api_format", "openai_chat"),
        "provider_name": target_model.get("provider_name", "自定义"),
        "active_provider_id": target_model.get("provider_id", "custom"),
        "active_provider_name": target_model.get("provider_name", "自定义"),
    }


def upsert_model(provider_id: str, model_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update a custom model definition."""
    mid = str(model_data.get("id", "")).strip()
    name = str(model_data.get("name", "")).strip() or mid
    base_url = str(model_data.get("base_url", "")).strip().rstrip("/")
    api_key = str(model_data.get("api_key", "")).strip()
    api_format = str(model_data.get("api_format", "openai_chat")).strip()
    provider_name = str(model_data.get("provider_name", "")).strip()
    reasoning_type = str(model_data.get("reasoning_type", "auto")).strip()
    default_effort = str(model_data.get("default_effort") or model_data.get("reasoning_effort", "high")).strip()
    desc = str(model_data.get("description", "")).strip()

    if not mid:
        raise ValueError("模型 ID 不能为空")

    config = init_llm_config()

    # Look up provider if provider_id given
    prov = None
    if provider_id and provider_id != "custom":
        prov = next((p for p in config.get("providers", []) if p["id"] == provider_id), None)
    if not prov and provider_name:
        prov = next((p for p in config.get("providers", []) if p.get("name") == provider_name), None)

    if prov:
        if not base_url:
            base_url = prov.get("base_url", "")
        if not api_key and prov.get("api_key"):
            api_key = prov.get("api_key", "")
        if not provider_name:
            provider_name = prov.get("name", "自定义")
        if not provider_id:
            provider_id = prov.get("id", "custom")

    if not base_url or not base_url.startswith(("http://", "https://")):
        active = get_active_llm_runtime()
        base_url = active.get("base_url", "https://api.openai.com/v1")

    valid_formats = [f["id"] for f in SUPPORTED_API_FORMATS]
    if api_format not in valid_formats:
        api_format = _detect_api_format(base_url, mid)

    models = config.setdefault("models", [])
    existing = next((m for m in models if m["id"] == mid), None)

    if existing:
        existing["name"] = name
        existing["provider_id"] = provider_id or existing.get("provider_id", "custom")
        existing["provider_name"] = provider_name or existing.get("provider_name", "自定义")
        existing["base_url"] = base_url
        if api_key:
            existing["api_key"] = api_key
        existing["api_format"] = api_format
        existing["reasoning_type"] = reasoning_type
        existing["reasoning_effort"] = default_effort
        existing["description"] = desc
    else:
        models.append({
            "id": mid,
            "name": name,
            "provider_id": provider_id or "custom",
            "provider_name": provider_name or "自定义",
            "base_url": base_url,
            "api_key": api_key,
            "api_format": api_format,
            "reasoning_type": reasoning_type,
            "reasoning_effort": default_effort,
            "description": desc,
        })

    _atomic_write_json(LLM_CONFIG_FILE, config)
    return {
        "model_id": mid,
        "name": name,
        "base_url": base_url,
        "api_format": api_format,
        "provider_id": provider_id or "custom",
    }


def delete_model(provider_id: str, model_id: str) -> bool:
    """Delete a custom model."""
    config = init_llm_config()
    if config.get("active_model_id") == model_id:
        raise ValueError("不能删除当前正在使用的模型；请先切换到其他模型后再删除。")

    models = config.get("models", [])
    filtered = [m for m in models if m["id"] != model_id]
    if len(filtered) == len(models):
        return False

    config["models"] = filtered
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return True


def upsert_provider(provider_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update an LLM provider definition."""
    pid = str(provider_data.get("id", "")).strip().lower()
    name = str(provider_data.get("name", "")).strip() or pid
    base_url = str(provider_data.get("base_url", "")).strip().rstrip("/")
    api_key = str(provider_data.get("api_key", "")).strip()
    api_format = str(provider_data.get("api_format", "openai_chat")).strip()
    desc = str(provider_data.get("description", "")).strip()

    if not pid:
        pid = re.sub(r"[^a-zA-Z0-9_\-]", "", name.lower()) or f"prov-{int(time.time())}"

    if not base_url or not base_url.startswith(("http://", "https://")):
        raise ValueError("供应商 Base URL 必须以 http:// 或 https:// 开头")

    config = init_llm_config()
    providers = config.setdefault("providers", [])
    existing = next((p for p in providers if p["id"] == pid), None)
    if existing:
        existing["name"] = name
        existing["base_url"] = base_url
        if api_key:
            existing["api_key"] = api_key
        existing["api_format"] = api_format
        existing["description"] = desc
    else:
        providers.append({
            "id": pid,
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "api_format": api_format,
            "description": desc,
        })
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return {"id": pid, "name": name, "base_url": base_url}


def delete_provider(provider_id: str) -> bool:
    """Delete a provider definition."""
    config = init_llm_config()
    providers = config.get("providers", [])
    filtered = [p for p in providers if p["id"] != provider_id]
    if len(filtered) == len(providers):
        return False
    config["providers"] = filtered
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return True


def fetch_remote_models(
    base_url: str = "",
    api_key: str = "",
    provider_id: Optional[str] = None,
    timeout: float = 12.0,
) -> Dict[str, Any]:
    """Fetch live models list from an OpenAI / OpenRouter / OpenCode / Anthropic compatible endpoint."""
    cleaned_url = str(base_url or "").strip().rstrip("/")
    config = init_llm_config()

    if not cleaned_url and provider_id:
        prov = next((p for p in config.get("providers", []) if p["id"] == provider_id), None)
        if prov:
            cleaned_url = prov.get("base_url", "").strip().rstrip("/")
            if not api_key:
                api_key = prov.get("api_key", "")

    if not cleaned_url:
        active = get_active_llm_runtime()
        cleaned_url = active.get("base_url", "").strip().rstrip("/")
        if not api_key:
            api_key = active.get("api_key", "")

    if not cleaned_url or not cleaned_url.startswith(("http://", "https://")):
        return {
            "ok": False,
            "error": "Base URL 格式无效，必须以 http:// 或 https:// 开头",
            "recommendation": "请填写有效的供应商 Base URL",
        }

    # If api_key not provided, inherit from matching provider if available
    if not api_key:
        prov = next((p for p in config.get("providers", []) if p.get("base_url", "").rstrip("/") == cleaned_url and p.get("api_key")), None)
        if prov:
            api_key = prov.get("api_key", "")

    # Endpoints to probe
    endpoints = []
    if "anthropic.com" in cleaned_url:
        ep = f"{cleaned_url}/models" if not cleaned_url.endswith("/v1") else f"{cleaned_url}/models"
        hdrs = {"x-api-key": api_key, "anthropic-version": "2023-06-01"} if api_key else {}
        endpoints.append((ep, hdrs))
    elif cleaned_url.endswith("/v1"):
        endpoints.append((f"{cleaned_url}/models", {"Authorization": f"Bearer {api_key}"} if api_key else {}))
        endpoints.append((f"{cleaned_url[:-3]}/models", {"Authorization": f"Bearer {api_key}"} if api_key else {}))
    elif cleaned_url.endswith("/models"):
        endpoints.append((cleaned_url, {"Authorization": f"Bearer {api_key}"} if api_key else {}))
    else:
        endpoints.append((f"{cleaned_url}/v1/models", {"Authorization": f"Bearer {api_key}"} if api_key else {}))
        endpoints.append((f"{cleaned_url}/models", {"Authorization": f"Bearer {api_key}"} if api_key else {}))

    last_err = ""
    for ep, hdrs in endpoints:
        hdrs["User-Agent"] = "R20-Quantum-Trader/6.6 (Model-Fetch)"
        req = urllib.request.Request(ep, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                raw_list = data.get("data") if isinstance(data, dict) and "data" in data else data.get("models", data if isinstance(data, list) else [])
                if not isinstance(raw_list, list):
                    continue

                parsed_models = []
                for item in raw_list:
                    if isinstance(item, str):
                        m_id = item
                        m_name = item
                        ctx = None
                        desc = ""
                    elif isinstance(item, dict):
                        m_id = str(item.get("id", "")).strip()
                        if not m_id:
                            continue
                        m_name = str(item.get("name") or item.get("display_name") or m_id).strip()
                        ctx = item.get("context_length") or item.get("max_tokens")
                        desc = str(item.get("description") or "").strip()
                    else:
                        continue

                    detected_format = _detect_api_format(cleaned_url, m_id)
                    detected_rtype = _detect_reasoning_type(m_id)
                    default_effort = "high" if detected_rtype != "none" else "auto"

                    parsed_models.append({
                        "id": m_id,
                        "name": m_name,
                        "context_length": ctx,
                        "description": desc,
                        "api_format": detected_format,
                        "reasoning_type": detected_rtype,
                        "default_effort": default_effort,
                    })

                # Sort models: priority for flagship keywords
                def _model_sort_key(m: Dict[str, Any]) -> Tuple[int, str]:
                    mid = m["id"].lower()
                    if any(k in mid for k in ["gemini-3", "claude-3-7", "claude-3.7", "o3", "o4", "deepseek-r1", "deepseek-v3", "qwen-max", "qwq"]):
                        return (0, mid)
                    if any(k in mid for k in ["gemini-2", "claude-3-5", "claude-3.5", "o1", "gpt-4o", "qwen-2.5"]):
                        return (1, mid)
                    return (2, mid)

                parsed_models.sort(key=_model_sort_key)

                return {
                    "ok": True,
                    "endpoint_used": ep,
                    "total": len(parsed_models),
                    "models": parsed_models,
                }
        except urllib.error.HTTPError as exc:
            last_err = f"HTTP {exc.code}"
            if exc.code == 401:
                return {
                    "ok": False,
                    "error": "供应商身份验证失败 (HTTP 401 Unauthorized)",
                    "recommendation": "请先在此供应商填入正确的 API Key 后再拉取模型",
                }
        except Exception as exc:
            last_err = str(exc)

    return {
        "ok": False,
        "error": f"拉取失败: {last_err or '未响应模型列表'}",
        "recommendation": "请检查 Base URL 是否正确，或供应商是否支持 /models 端点查询",
    }



def build_request_spec(
    model: str,
    messages: List[Dict[str, str]],
    base_url: str,
    api_key: str = "",
    api_format: str = "openai_chat",
    reasoning_effort: str = "high",
    temperature: Optional[float] = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
    reasoning_type: str = "auto",
    max_tokens: int = 4096,
) -> Tuple[str, Dict[str, str], Dict[str, Any]]:
    """Build endpoint URL, headers, and request payload according to the specific API protocol format."""
    cleaned_url = base_url.rstrip("/")
    m_lower = model.lower()
    rtype = reasoning_type if reasoning_type != "auto" else _detect_reasoning_type(model)
    effort = (reasoning_effort or "auto").strip().lower()

    # Protocol 1: Anthropic Claude Messages API
    if api_format == "claude_messages":
        if not cleaned_url.endswith("/messages"):
            endpoint = f"{cleaned_url}/messages" if cleaned_url.endswith("/v1") else f"{cleaned_url}/v1/messages"
        else:
            endpoint = cleaned_url

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "R20-Quantum-Trader/5.4 (Claude-Messages)",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            headers["x-api-key"] = api_key

        # Separate system message
        system_chunks = [m["content"] for m in messages if m.get("role") == "system"]
        chat_messages = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") != "system"]

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": chat_messages,
        }
        if system_chunks:
            payload["system"] = "\n\n".join(system_chunks)

        if effort in ("high", "medium", "low"):
            budget_map = {"high": 16000, "medium": 8000, "low": 2048}
            budget = budget_map[effort]
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
            payload["max_tokens"] = budget + max_tokens
        elif effort == "none":
            payload["thinking"] = {"type": "disabled"}
            if temperature is not None:
                payload["temperature"] = temperature
        else:
            if temperature is not None:
                payload["temperature"] = temperature

        return endpoint, headers, payload

    # Protocol 2: OpenAI Responses API (/responses)
    elif api_format == "openai_responses":
        if not cleaned_url.endswith("/responses"):
            endpoint = f"{cleaned_url}/responses" if cleaned_url.endswith("/v1") else f"{cleaned_url}/v1/responses"
        else:
            endpoint = cleaned_url

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "R20-Quantum-Trader/5.4 (OpenAI-Responses)",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: Dict[str, Any] = {
            "model": model,
            "input": messages,
        }
        if response_format and response_format.get("type") == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
        if effort in ("high", "medium", "low", "minimal"):
            payload["reasoning"] = {"effort": effort}

        return endpoint, headers, payload

    # Protocol 3: OpenAI Chat Completions (/chat/completions, Default)
    else:
        if not cleaned_url.endswith("/chat/completions"):
            endpoint = f"{cleaned_url}/chat/completions" if cleaned_url.endswith("/v1") else f"{cleaned_url}/v1/chat/completions"
        else:
            endpoint = cleaned_url

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "R20-Quantum-Trader/5.4 (OpenAI-Chat)",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        # Temperature handling for reasoning models vs normal models
        is_reasoning_model = (
            rtype in ("deepseek_reasoner", "standard_effort")
            or m_lower.startswith(("o1", "o3", "o4"))
            or "reasoner" in m_lower
            or "-r1" in m_lower
        )
        if not is_reasoning_model:
            if temperature is not None:
                payload["temperature"] = temperature
        else:
            if "gemini" in m_lower and temperature is not None:
                payload["temperature"] = temperature

        # Standard reasoning effort parameter
        if rtype == "standard_effort" or (rtype == "auto" and ("gemini" in m_lower or m_lower.startswith(("o1", "o3", "o4")))):
            if effort in ("low", "medium", "high", "minimal"):
                payload["reasoning_effort"] = effort
            elif effort == "none" and "gemini" in m_lower:
                payload["reasoning_effort"] = "none"

        if response_format and rtype != "deepseek_reasoner":
            payload["response_format"] = response_format

        return endpoint, headers, payload


def build_chat_payload(
    model: str,
    messages: List[Dict[str, str]],
    reasoning_effort: str = "high",
    temperature: Optional[float] = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
    reasoning_type: str = "auto",
) -> Dict[str, Any]:
    """Compatibility wrapper for standard chat payload generation."""
    _, _, payload = build_request_spec(
        model=model,
        messages=messages,
        base_url="https://api.openai.com/v1",
        api_format="openai_chat",
        reasoning_effort=reasoning_effort,
        temperature=temperature,
        response_format=response_format,
        reasoning_type=reasoning_type,
    )
    return payload


def execute_llm_request(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    api_format: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    temperature: Optional[float] = 0.2,
    response_format: Optional[Dict[str, Any]] = None,
    timeout: float = 50.0,
) -> Tuple[str, str, Dict[str, Any], int]:
    """Unified executor for LLM calls across all 3 protocols.
    Returns: (content, reasoning_content, usage_dict, latency_ms)
    """
    runtime = get_active_llm_runtime()
    target_model = model or runtime.get("model") or "gemini-3.8-flash-high"
    target_url = base_url or runtime.get("base_url") or "https://cpa.r20.cn/v1"
    target_key = api_key if api_key is not None else runtime.get("api_key", "")
    target_format = api_format or runtime.get("api_format") or _detect_api_format(target_url, target_model)
    target_effort = reasoning_effort or runtime.get("reasoning_effort") or "high"
    target_rtype = runtime.get("reasoning_type", "auto")

    endpoint, headers, payload = build_request_spec(
        model=target_model,
        messages=messages,
        base_url=target_url,
        api_key=target_key,
        api_format=target_format,
        reasoning_effort=target_effort,
        temperature=temperature,
        response_format=response_format,
        reasoning_type=target_rtype,
    )

    t0 = time.perf_counter()
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )

    try:
        resp_handle = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        err_b = ""
        try:
            err_b = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass

        # Adaptive fallback retry on rejected parameter
        if exc.code == 400 and any(kw in err_b.lower() for kw in ["reasoning_effort", "temperature", "response_format", "invalid parameter"]):
            fallback_payload = {
                "model": target_model,
                "messages": messages,
            }
            fb_req = urllib.request.Request(
                endpoint,
                data=json.dumps(fallback_payload).encode("utf-8"),
                headers=headers,
            )
            resp_handle = urllib.request.urlopen(fb_req, timeout=timeout)
        else:
            raise

    with resp_handle as resp:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        body_bytes = resp.read()
        res_json = json.loads(body_bytes.decode("utf-8", errors="replace"))

    content = ""
    reasoning_content = ""
    usage = res_json.get("usage", {})

    # Protocol 1: Claude Messages Response
    if target_format == "claude_messages":
        text_chunks = [c.get("text", "") for c in res_json.get("content", []) if c.get("type") == "text"]
        thinking_chunks = [c.get("thinking", "") for c in res_json.get("content", []) if c.get("type") == "thinking"]
        content = "".join(text_chunks).strip()
        reasoning_content = "\n".join(thinking_chunks).strip()
        if not usage:
            usage = {
                "total_tokens": res_json.get("usage", {}).get("input_tokens", 0) + res_json.get("usage", {}).get("output_tokens", 0)
            }

    # Protocol 2: OpenAI Responses Response
    elif target_format == "openai_responses":
        content = str(res_json.get("output_text") or "").strip()
        if not content:
            for item in res_json.get("output", []):
                if item.get("type") == "message":
                    for part in item.get("content", []):
                        if part.get("type") == "output_text" or "text" in part:
                            content += str(part.get("text", ""))
                elif item.get("type") == "reasoning":
                    reasoning_content += str(item.get("content") or item.get("summary") or "")
        content = content.strip()
        reasoning_content = reasoning_content.strip()

    # Protocol 3: OpenAI Chat Completions Response
    else:
        msg = res_json.get("choices", [{}])[0].get("message", {})
        content = str(msg.get("content", "")).strip()
        reasoning_content = str(msg.get("reasoning_content") or "").strip()

    return content, reasoning_content, usage, latency_ms


def test_llm_connection(
    base_url: str,
    api_key: str,
    model: str,
    api_format: str = "openai_chat",
    reasoning_effort: str = "auto",
    reasoning_type: str = "auto",
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """Execute a real diagnostic ping across any of the 3 API formats."""
    cleaned_url = str(base_url or "").strip().rstrip("/")
    if not cleaned_url.startswith(("http://", "https://")):
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": 0,
            "model": model,
            "error": "Base URL 格式无效，必须以 http:// 或 https:// 开头",
            "recommendation": "请检查并填写正确的服务 Base URL，例如 https://cpa.r20.cn/v1",
        }

    test_messages = [
        {"role": "user", "content": "Ping test for connection. Please respond with exactly the single word: PONG"}
    ]

    endpoint, headers, payload = build_request_spec(
        model=model,
        messages=test_messages,
        base_url=cleaned_url,
        api_key=api_key,
        api_format=api_format,
        reasoning_effort=reasoning_effort,
        temperature=0.1,
        reasoning_type=reasoning_type,
    )

    t0 = time.perf_counter()
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            status_code = resp.getcode()
            body_bytes = resp.read()
            res_json = json.loads(body_bytes.decode("utf-8", errors="replace"))

            content = ""
            reasoning_content = ""
            usage = res_json.get("usage", {})

            if api_format == "claude_messages":
                content = "".join(c.get("text", "") for c in res_json.get("content", []) if c.get("type") == "text")
                reasoning_content = "\n".join(c.get("thinking", "") for c in res_json.get("content", []) if c.get("type") == "thinking")
            elif api_format == "openai_responses":
                content = str(res_json.get("output_text") or "")
                for item in res_json.get("output", []):
                    if item.get("type") == "reasoning":
                        reasoning_content += str(item.get("content") or item.get("summary") or "")
            else:
                msg = res_json.get("choices", [{}])[0].get("message", {})
                content = str(msg.get("content", ""))
                reasoning_content = str(msg.get("reasoning_content") or "")

            content = content.strip()
            reasoning_tokens = (
                usage.get("completion_tokens_details", {}).get("reasoning_tokens")
                or usage.get("output_tokens_details", {}).get("reasoning_tokens")
                or usage.get("reasoning_tokens")
                or (len(reasoning_content.split()) if reasoning_content else None)
            )

            format_label = next((f["name"] for f in SUPPORTED_API_FORMATS if f["id"] == api_format), api_format)

            return {
                "ok": True,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "model": model,
                "api_format": api_format,
                "api_format_name": format_label,
                "endpoint": endpoint,
                "response_preview": content[:120] if content else "(响应成功，返回空正文)",
                "reasoning_detected": bool(reasoning_content),
                "reasoning_tokens": reasoning_tokens,
                "total_tokens": usage.get("total_tokens") or (usage.get("input_tokens", 0) + usage.get("output_tokens", 0)),
                "payload_sent": {k: v for k, v in payload.items() if k not in ("messages", "input")},
                "compatibility_note": f"协议 {api_format} 连接与解析成功" + (" · 已捕获链式推演输出" if reasoning_content else ""),
            }

    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        status_code = exc.code
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass

        # Adaptive fallback retry
        is_param_conflict = any(kw in err_body.lower() for kw in [
            "reasoning_effort", "temperature", "unrecognized request argument", "unknown parameter", "invalid parameter"
        ])
        if is_param_conflict and api_format == "openai_chat":
            try:
                fb_payload = {"model": model, "messages": test_messages}
                fb_req = urllib.request.Request(endpoint, data=json.dumps(fb_payload).encode("utf-8"), headers=headers)
                t1 = time.perf_counter()
                with urllib.request.urlopen(fb_req, timeout=timeout) as fb_resp:
                    fb_latency = int((time.perf_counter() - t1) * 1000)
                    fb_body = fb_resp.read().decode("utf-8", errors="replace")
                    fb_json = json.loads(fb_body)
                    fb_msg = fb_json.get("choices", [{}])[0].get("message", {})
                    return {
                        "ok": True,
                        "status_code": 200,
                        "latency_ms": fb_latency,
                        "model": model,
                        "api_format": api_format,
                        "endpoint": endpoint,
                        "response_preview": str(fb_msg.get("content", ""))[:120] or "OK",
                        "warning": f"上游服务拒绝了参数 ({err_body[:80]}…)，系统已自适应去除冲突参数并测试成功",
                        "compatibility_note": "模型不支持自定义 reasoning_effort 或 temperature 参数；实际调用将自动去除",
                    }
            except Exception:
                pass

        rec = "请核对配置"
        if status_code == 401:
            rec = "API Key 认证失败，请检查密钥是否正确或是否已过期"
        elif status_code == 404:
            rec = f"端点未找到 (404)，请检查 API 格式协议是否选对（如 Anthropic 需选 Claude Messages，OpenAI 选 Chat 或 Responses），以及 Base URL 路径是否正确"
        elif status_code == 429:
            rec = "请求频次超限或账户配额/余额不足 (429 Rate Limit)"
        elif status_code in (500, 502, 503):
            rec = "上游大模型服务暂时不可用或内部服务故障"

        return {
            "ok": False,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "model": model,
            "api_format": api_format,
            "endpoint": endpoint,
            "error": f"HTTP {status_code}: {err_body[:240]}",
            "recommendation": rec,
        }

    except urllib.error.URLError as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": latency_ms,
            "model": model,
            "api_format": api_format,
            "endpoint": endpoint,
            "error": f"网络连接失败: {exc.reason}",
            "recommendation": "无法连接到该 Base URL，请检查网络通畅度、DNS 解析或代理网关配置",
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": latency_ms,
            "model": model,
            "api_format": api_format,
            "endpoint": endpoint,
            "error": f"测试执行异常: {str(exc)}",
            "recommendation": "发生未预期的连接错误，请检查输入配置格式",
        }
