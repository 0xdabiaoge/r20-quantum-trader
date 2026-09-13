"""LLM 配置库的读写与规范化（llm_models.json）。

**薄壳 + 核心**（结构优化阶段 2 / B4）：路径常量留在 llm_manager.py，
由薄壳在调用时解析后传入 —— 测试对该常量的 patch 与直接赋值因此仍然生效。
本模块不 import llm_manager（无循环依赖）。
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from r20_backend.llm.capabilities import (
    _detect_api_format,
    _detect_capabilities,
    _detect_reasoning_type,
)
from r20_backend.llm.policy import (
    DEFAULT_PROVIDERS,
    DEFAULT_REQUEST_ATTEMPTS,
    MAX_FALLBACK_MODELS,
    MAX_REQUEST_ATTEMPTS,
    MIN_REQUEST_ATTEMPTS,
    STANDARD_REASONING_EFFORTS,
    SUPPORTED_API_FORMATS,
)
from r20_backend.llm.providers import _resolve_active_provider_id
from r20_backend.llm.util import _atomic_write_json, mask_secret


def init_llm_config(config_file: Path) -> Dict[str, Any]:
    """Load or initialize clean, user-centric model configuration with multi-provider support."""
    from ..config import settings

    data: Dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            data = {}

    # Extract current settings from .env / settings
    # 安全约束：不再内置任何私有中继网关作为静默默认，出口地址必须由用户显式配置。
    cur_url = getattr(settings, "llm_base_url", "") or os.getenv("LLM_BASE_URL") or ""
    cur_key = getattr(settings, "llm_api_key", "") or os.getenv("LLM_API_KEY") or ""
    cur_model = getattr(settings, "llm_model", "") or os.getenv("LLM_MODEL") or ""
    cur_effort = getattr(settings, "llm_reasoning_effort", "") or os.getenv("LLM_REASONING_EFFORT") or "high"

    existing_providers = data.get("providers", [])
    merged_providers: List[Dict[str, Any]] = []

    # 默认供应商只在「首次播种」时注入。播种完成后配置里落下 defaults_seeded 标记，
    # 此后用户删除的默认供应商绝不复活；openai 的 enabled 也只在播种时强制打开，
    # 之后尊重用户自己的开关。老配置文件（无标记）视为首次：合并一次并落标记，升级无感。
    seed_defaults = not data.get("defaults_seeded")
    default_by_id = {dp["id"]: dp for dp in DEFAULT_PROVIDERS}
    # (ignore legacy hardcoded providers from older versions)
    legacy_ids = {
        "siliconflow", "openrouter", "kelivoin", "tensdaq", "deepseek",
        "alhubmix", "suixiang", "dashscope", "zhipu", "grok", "volcengine"
    }

    for found in existing_providers:
        pid = found.get("id")
        if not pid or pid in legacy_ids:
            continue
        dp = default_by_id.get(pid)
        if dp:
            p_obj = copy.deepcopy(dp)
            p_obj.update(found)
            # Never overwrite models with global defaults if provider was already configured
            if "models" in found:
                p_obj["models"] = list(found.get("models", []))
            if pid == "openai":
                if not p_obj.get("api_key") and cur_key:
                    p_obj["api_key"] = cur_key
                if not p_obj.get("base_url"):
                    p_obj["base_url"] = cur_url
                if seed_defaults:
                    p_obj["enabled"] = True
            merged_providers.append(p_obj)
        else:
            merged_providers.append(found)

    if seed_defaults:
        have_ids = {p.get("id") for p in merged_providers}
        for dp in DEFAULT_PROVIDERS:
            if dp["id"] in have_ids:
                continue
            p_obj = copy.deepcopy(dp)
            if dp["id"] == "openai":
                if cur_key:
                    p_obj["api_key"] = cur_key
                if cur_url:
                    p_obj["base_url"] = cur_url
                p_obj["enabled"] = True
            merged_providers.append(p_obj)

    active_m_id = data.get("active_model_id") or cur_model or ""
    active_effort = data.get("active_reasoning_effort") or cur_effort or "high"
    cur_timeout = getattr(settings, "llm_thinking_timeout", 120.0) or float(os.getenv("LLM_THINKING_TIMEOUT", os.getenv("LLM_TIMEOUT_SECONDS", "120.0")))
    raw_timeout = data.get("thinking_timeout")
    thinking_timeout = float(raw_timeout) if raw_timeout is not None else float(cur_timeout or 120.0)

    models_map: Dict[str, Dict[str, Any]] = {}
    for p in merged_providers:
        p_id = p.get("id", "")
        p_name = p.get("name", p_id)
        p_base = p.get("base_url", "")
        p_key = p.get("api_key", "")
        p_fmt = p.get("api_format", "openai_chat")
        for m in p.get("models", []):
            mid = m.get("id", "")
            if not mid:
                continue
            models_map[mid] = {
                "id": mid,
                "name": m.get("name", mid),
                "provider_id": p_id,
                "provider_name": p_name,
                "base_url": m.get("base_url") or p_base,
                "api_key": m.get("api_key") or p_key,
                "api_format": m.get("api_format") or p_fmt,
                "api_path": m.get("api_path") or p.get("api_path", ""),
                "reasoning_type": m.get("reasoning_type", _detect_reasoning_type(mid)),
                "reasoning_effort": m.get("reasoning_effort") or m.get("default_effort", "high"),
                "capabilities": m.get("capabilities", _detect_capabilities(mid)),
                "context_length": m.get("context_length"),
                "description": m.get("description", ""),
            }

    # Preserve any custom models that were added by user or tests
    prov_by_id = {p.get("id"): p for p in merged_providers}
    for m in data.get("models", []):
        mid = m.get("id")
        if mid:
            if mid in models_map:
                fresh = models_map[mid]
                merged = dict(m)
                # 供应商凭据是唯一权威源：历史快照键/地址不得覆盖供应商当前值
                if fresh.get("api_key"):
                    merged["api_key"] = fresh["api_key"]
                if fresh.get("base_url"):
                    merged["base_url"] = fresh["base_url"]
                fresh.update(merged)
            else:
                entry = dict(m)
                prov = prov_by_id.get(entry.get("provider_id"))
                if prov:
                    # 顶层扁平模型同样按 provider_id 重挂供应商当前凭据——
                    # 否则轮换密钥后旧快照键永久粘住，模型必须删掉重加才能恢复
                    if prov.get("api_key"):
                        entry["api_key"] = prov["api_key"]
                    if prov.get("base_url"):
                        entry["base_url"] = prov["base_url"]
                    if not entry.get("api_format"):
                        entry["api_format"] = prov.get("api_format", "openai_chat")
                models_map[mid] = entry

    flat_models = list(models_map.values())
    if not any(m["id"] == active_m_id for m in flat_models) and flat_models:
        active_m_id = flat_models[0]["id"]

    # ── 主脑供应商归属：嵌套持有者为准（显式记录 > 唯一持有 > 顶层扁平缓存归属）──
    # models_map 按 id 去重（后出现的供应商覆盖先出现的），多供应商挂同名模型时
    # 顶层缓存的 base_url/api_key 会静默变成另一家的——必须把主脑条目钉回其供应商。
    raw_active_pid = str(data.get("active_provider_id") or "").strip()
    active_pid = _resolve_active_provider_id(
        {
            "active_model_id": active_m_id,
            "active_provider_id": raw_active_pid,
            "providers": merged_providers,
            "models": flat_models,
        }
    )
    if active_pid and active_m_id:
        ap = next((p for p in merged_providers if str(p.get("id", "")) == active_pid), None)
        if ap:
            for m in flat_models:
                if m.get("id") != active_m_id:
                    continue
                m["provider_id"] = active_pid
                m["provider_name"] = ap.get("name", active_pid)
                if ap.get("base_url"):
                    m["base_url"] = ap["base_url"]
                if ap.get("api_key"):
                    m["api_key"] = ap["api_key"]
                if not m.get("api_format"):
                    m["api_format"] = ap.get("api_format", "openai_chat")
                break

    # ── 韧性配置解析：请求次数 + 回退模型链（脏数据自愈）──
    raw_attempts = data.get("request_attempts")
    try:
        env_attempts = int(os.getenv("LLM_REQUEST_ATTEMPTS", "") or 0)
    except ValueError:
        env_attempts = 0
    try:
        request_attempts = int(raw_attempts) if raw_attempts is not None else (env_attempts or DEFAULT_REQUEST_ATTEMPTS)
    except (TypeError, ValueError):
        request_attempts = DEFAULT_REQUEST_ATTEMPTS
    request_attempts = max(MIN_REQUEST_ATTEMPTS, min(MAX_REQUEST_ATTEMPTS, request_attempts))

    known_model_ids = {m["id"] for m in flat_models}
    raw_fallbacks = data.get("fallback_model_ids")
    fallback_model_ids: List[str] = []
    if isinstance(raw_fallbacks, list):
        for fid in raw_fallbacks:
            fid = str(fid or "").strip()
            if not fid or fid == active_m_id or fid not in known_model_ids:
                continue
            if fid not in fallback_model_ids:
                fallback_model_ids.append(fid)
    fallback_model_ids = fallback_model_ids[:MAX_FALLBACK_MODELS]

    config = {
        "version": "3.2",
        "defaults_seeded": True,
        "active_model_id": active_m_id,
        "active_provider_id": active_pid,
        "active_reasoning_effort": active_effort,
        "thinking_timeout": thinking_timeout,
        "request_attempts": request_attempts,
        "fallback_model_ids": fallback_model_ids,
        "providers": merged_providers,
        "models": flat_models,
    }
    _atomic_write_json(config_file, config)
    return config


def load_llm_config(config: Dict[str, Any], mask_keys: bool = True) -> Dict[str, Any]:
    """Return clean model configurations and configured providers matching modern client architecture."""
    providers_list = config.get("providers", [])
    active_mid = config.get("active_model_id", "")
    active_pid = _resolve_active_provider_id(config)
    active_effort = config.get("active_reasoning_effort", "high")

    res: Dict[str, Any] = {
        "version": config.get("version", "3.2"),
        "active_model_id": active_mid,
        "active_reasoning_effort": active_effort,
        "thinking_timeout": config.get("thinking_timeout", 120.0),
        "request_attempts": config.get("request_attempts", DEFAULT_REQUEST_ATTEMPTS),
        "fallback_model_ids": config.get("fallback_model_ids", []),
        "max_request_attempts": MAX_REQUEST_ATTEMPTS,
        "max_fallback_models": MAX_FALLBACK_MODELS,
        "standard_reasoning_efforts": STANDARD_REASONING_EFFORTS,
        "supported_api_formats": SUPPORTED_API_FORMATS,
        "providers": [],
        "models": [],
        "active_provider_id": active_pid or (config.get("active_provider_id") or ""),
    }

    for p in providers_list:
        pid = p.get("id", "")
        # ONLY return models that are explicitly registered under this specific provider
        models_in_p = list(p.get("models", []))
        formatted_p_models = []
        for m in models_in_p:
            m_id = m.get("id", "")
            formatted_p_models.append({
                "id": m_id,
                "name": m.get("name") or m_id,
                "capabilities": m.get("capabilities") or _detect_capabilities(m_id),
                "reasoning_type": m.get("reasoning_type") or _detect_reasoning_type(m_id),
                "reasoning_effort": m.get("reasoning_effort") or "high",
                "context_length": m.get("context_length"),
                "description": m.get("description", ""),
                # 同名模型挂多家供应商时，主脑徽标只打给归属供应商的那一份；
                # 归属无法判定（active_pid 为空）时保留全打，避免误导为"没启用"
                "is_active": bool(m_id == active_mid and (not active_pid or pid == active_pid)),
            })

        p_copy = {
            "id": pid,
            "name": p.get("name", pid),
            "type": p.get("type", p.get("name", pid)),
            "group": p.get("group", "其他"),
            "enabled": bool(p.get("enabled", False)),
            "multi_key_enabled": bool(p.get("multi_key_enabled", False)),
            "response_api_enabled": bool(p.get("response_api_enabled", False)),
            "base_url": p.get("base_url", ""),
            "api_format": p.get("api_format", "openai_chat"),
            "api_path": p.get("api_path", "/chat/completions"),
            "description": p.get("description", ""),
            "has_key": bool(p.get("api_key")),
            "models_count": len(models_in_p),
            "models": formatted_p_models,
        }
        if mask_keys:
            p_copy["api_key_masked"] = mask_secret(p.get("api_key", ""))
        else:
            p_copy["api_key"] = p.get("api_key", "")
        res["providers"].append(p_copy)

    # Flattened models for backward compatibility
    for m in config.get("models", []):
        m_pid = m.get("provider_id", "openai")
        p_entry = next((p for p in providers_list if p.get("id") == m_pid), None)
        m_key = m.get("api_key", "")
        has_key = bool(m_key or (p_entry and p_entry.get("api_key")))

        m_copy = {
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "provider_id": m_pid,
            "provider_name": m.get("provider_name") or (p_entry.get("name") if p_entry else "自定义"),
            "base_url": m.get("base_url", "") or (p_entry.get("base_url", "") if p_entry else ""),
            "api_format": m.get("api_format", "openai_chat"),
            "reasoning_type": m.get("reasoning_type", "auto"),
            "reasoning_effort": m.get("reasoning_effort", "high"),
            "capabilities": m.get("capabilities") or _detect_capabilities(m["id"]),
            "context_length": m.get("context_length"),
            "description": m.get("description", ""),
            "has_key": has_key,
            "is_active": m["id"] == active_mid,
        }
        if mask_keys:
            m_copy["api_key_masked"] = mask_secret(m_key) if m_key else (mask_secret(p_entry.get("api_key", "")) if p_entry and p_entry.get("api_key") else "")
        else:
            m_copy["api_key"] = m_key
        res["models"].append(m_copy)

    return res


def get_active_llm_runtime(config: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve active LLM credentials and configuration for runtime execution."""
    from ..config import settings
    active_mid = config.get("active_model_id", "")
    active_effort = config.get("active_reasoning_effort", "high")

    target_model = next((m for m in config.get("models", []) if m["id"] == active_mid), None)

    base_url = target_model.get("base_url") if target_model else getattr(settings, "llm_base_url", "")
    api_key = target_model.get("api_key") if target_model else getattr(settings, "llm_api_key", "")
    provider_id = target_model.get("provider_id", "") if target_model else ""
    provider_name = target_model.get("provider_name", "") if target_model else "默认"
    prov_api_path = str((target_model or {}).get("api_path", "") or "")

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
                provider_id = prov.get("id", "openai")
            if not prov_api_path:
                prov_api_path = str(prov.get("api_path", "") or "")

    base_url = (base_url or os.getenv("LLM_BASE_URL", "")).rstrip("/")
    if not base_url:
        raise RuntimeError(
            "LLM 出口未配置：请在 .env 设置 LLM_BASE_URL，或在后台「LLM Providers」中选择/新建供应商。"
            "出于数据流向透明要求，系统不再内置任何默认第三方中继网关。"
        )
    api_key = api_key or os.getenv("LLM_API_KEY", "")

    model_name = active_mid or getattr(settings, "llm_model", "") or os.getenv("LLM_MODEL", "")
    api_format = target_model.get("api_format") if target_model else _detect_api_format(base_url, model_name)
    reasoning_type = target_model.get("reasoning_type", "auto") if target_model else _detect_reasoning_type(model_name)
    thinking_timeout = float(
        target_model.get("thinking_timeout")
        if target_model and target_model.get("thinking_timeout")
        else config.get("thinking_timeout")
        or os.getenv("LLM_THINKING_TIMEOUT")
        or os.getenv("LLM_TIMEOUT_SECONDS")
        or getattr(settings, "llm_thinking_timeout", 120.0)
    )

    return {
        "model": model_name,
        "name": target_model.get("name", model_name) if target_model else model_name,
        "provider_name": provider_name or "默认",
        "provider_id": provider_id or "openai",
        "base_url": base_url,
        "api_key": api_key,
        "api_format": api_format,
        "api_path": prov_api_path,
        "reasoning_effort": active_effort,
        "reasoning_type": reasoning_type,
        "thinking_timeout": thinking_timeout,
        "request_attempts": config.get("request_attempts", DEFAULT_REQUEST_ATTEMPTS),
        "fallback_model_ids": config.get("fallback_model_ids", []),
    }


def resolve_model_runtime(config: Dict[str, Any], model_id: str) -> Optional[Dict[str, Any]]:
    """Resolve a configured model (e.g. a fallback) into a callable runtime spec.
    Returns None when the model is unknown or has no usable endpoint."""
    target = next((m for m in config.get("models", []) if m.get("id") == model_id), None)
    if not target:
        return None
    base_url = (target.get("base_url") or "").rstrip("/")
    api_key = target.get("api_key") or ""
    if not api_key or not base_url:
        prov = next((p for p in config.get("providers", []) if p.get("id") == target.get("provider_id")), None)
        if prov:
            base_url = base_url or (prov.get("base_url") or "").rstrip("/")
            api_key = api_key or prov.get("api_key", "")
    if not base_url:
        return None
    mid = target.get("id", model_id)
    api_format = target.get("api_format") or _detect_api_format(base_url, mid)
    reasoning_type = target.get("reasoning_type") or _detect_reasoning_type(mid)
    effort = target.get("reasoning_effort") or target.get("default_effort") or "high"
    try:
        thinking_timeout = float(target.get("thinking_timeout") or config.get("thinking_timeout") or 120.0)
    except (TypeError, ValueError):
        thinking_timeout = float(config.get("thinking_timeout") or 120.0)
    return {
        "model": mid,
        "name": target.get("name", mid),
        "provider_id": target.get("provider_id", ""),
        "provider_name": target.get("provider_name", "自定义"),
        "base_url": base_url,
        "api_key": api_key,
        "api_format": api_format,
        "api_path": str(target.get("api_path", "") or ""),
        "reasoning_effort": effort if effort in STANDARD_REASONING_EFFORTS else "high",
        "reasoning_type": reasoning_type,
        "thinking_timeout": thinking_timeout,
    }
