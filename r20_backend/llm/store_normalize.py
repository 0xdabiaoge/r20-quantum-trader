"""LLM 配置文档的**归一化与定稿**（B4 收尾抽取，从 `llm/store.py` 搬出）。

| 函数 | 内容 |
|---|---|
| `resolve_brain_provider_attribution` | 主脑供应商归属：嵌套持有者为准（显式记录 > 唯一持有 > 顶层扁平缓存），把主脑条目**钉回**其供应商（`models_map` 按 id 去重时，同名模型的 `base_url/api_key` 会静默变成另一家的） |
| `finalize_config_document` | 韧性配置解析（请求次数夹取 + 回退链去重/截断、脏数据自愈）→ 组装 `config` 文档 → 原子写盘 → 返回 |

## 安全属性

- 段体 **AST 逐字**（对拍门 `tests/test_llm_store_normalize_extraction.py`）；
- 自由名**同名 kw-only 入参** ⇒ 调用期解析，`patch.object(store, X)` 类接缝照常生效；
- `resolve_brain_provider_attribution` 会**原地修改** `flat_models` 里的 dict（设计如此）
  ⇒ 门里用 `assertIs` 钉住"改的是同一个对象"，防有人改成返回新列表（那是行为变更）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


def resolve_brain_provider_attribution(*,
        _resolve_active_provider_id,
        active_m_id,
        data,
        flat_models,
        merged_providers):
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
    return active_pid


def finalize_config_document(*,
        DEFAULT_REQUEST_ATTEMPTS,
        List,
        MAX_FALLBACK_MODELS,
        MAX_REQUEST_ATTEMPTS,
        MIN_REQUEST_ATTEMPTS,
        _atomic_write_json,
        active_effort,
        active_m_id,
        active_pid,
        config_file,
        data,
        flat_models,
        merged_providers,
        os,
        thinking_timeout):
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

