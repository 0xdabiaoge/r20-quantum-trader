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
from typing import Any, Dict, List

from r20_backend.llm.capabilities import _detect_capabilities, _detect_reasoning_type
from r20_backend.llm.policy import (
    DEFAULT_PROVIDERS,
    DEFAULT_REQUEST_ATTEMPTS,
    MAX_FALLBACK_MODELS,
    MAX_REQUEST_ATTEMPTS,
    MIN_REQUEST_ATTEMPTS,
)
from r20_backend.llm.providers import _resolve_active_provider_id
from r20_backend.llm.util import _atomic_write_json


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
