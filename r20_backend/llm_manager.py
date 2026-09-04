"""Unified multi-format LLM management, connection testing, and runtime dispatch.
Supports:
1. openai_chat: OpenAI Standard /chat/completions (OpenAI, Gemini OpenAI endpoint, DeepSeek, etc.)
2. openai_responses: OpenAI Structured /responses API (Responses API format)
3. claude_messages: Anthropic Claude /messages API (Claude 3.7 / 3.5 native)
"""
from __future__ import annotations
import copy
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


def _detect_capabilities(model_id: str) -> List[str]:
    m = model_id.lower()
    caps = ["chat"]
    if any(k in m for k in ["vision", "image", "flash", "gpt-4o", "gpt-5", "gemini", "claude", "grok", "muse", "vl", "omni", "multimodal"]):
        caps.append("vision")
    if not ("-r1-distill" in m or "-thinking" in m):
        caps.append("tools")
    if any(k in m for k in ["reasoner", "r1", "o1", "o3", "o4", "high", "thinking", "qwq", "deepseek-r1"]):
        caps.append("reasoning")
    return caps


def _detect_api_format(url: str, model_id: str) -> str:
    u = url.lower()
    m = model_id.lower()
    if "anthropic.com" in u or "claude" in u or "claude" in m and "messages" in u:
        return "claude_messages"
    if "responses" in u:
        return "openai_responses"
    return "openai_chat"


DEFAULT_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI",
        "type": "OpenAI",
        "group": "其他",
        "enabled": True,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://cpa.r20.cn/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "OpenAI 兼容协议端点，支持中继网关与官方直连",
        "models": [
            {
                "id": "gemini-3.8-flash-high",
                "name": "gemini-3.8-flash-high",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "当前全局生产主力主脑，支持高思考深度长思维链与百万上下文",
            },
            {
                "id": "gemini-3.7-flash-high",
                "name": "gemini-3.7-flash-high",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "Gemini 3.7 Flash 深度推演版，极速响应与强逻辑决策",
            },
            {
                "id": "gemini-3.1-flash-image",
                "name": "gemini-3.1-flash-image",
                "capabilities": ["chat", "vision"],
                "reasoning_type": "none",
                "reasoning_effort": "none",
                "context_length": 131072,
                "description": "Gemini 多模态盘口图表视觉感知模型",
            },
            {
                "id": "gpt-5.6-luna",
                "name": "gpt-5.6-luna",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1050000,
                "description": "2026 最新一代旗舰全模态智能体大模型",
            },
            {
                "id": "gpt-5.4-pro",
                "name": "gpt-5.4-pro",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1050000,
                "description": "GPT-5.4 顶级数理分析与自动化量化建模推理",
            },
            {
                "id": "o3-pro",
                "name": "o3-pro",
                "capabilities": ["chat", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 200000,
                "description": "OpenAI o3 Pro 顶级长思维链数学与因果逻辑推理",
            },
            {
                "id": "o3-mini",
                "name": "o3-mini",
                "capabilities": ["chat", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 200000,
                "description": "OpenAI o3-mini 高性价比快速推演",
            },
            {
                "id": "gpt-4.5-preview",
                "name": "gpt-4.5-preview",
                "capabilities": ["chat", "vision", "tools"],
                "reasoning_type": "none",
                "reasoning_effort": "none",
                "context_length": 128000,
                "description": "OpenAI 知识广度旗舰模型",
            },
        ],
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "type": "SiliconFlow",
        "group": "国内平台",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "硅基流动国内开源大模型高并发托管平台",
        "models": [
            {
                "id": "deepseek-ai/DeepSeek-R1",
                "name": "DeepSeek R1 满血 (671B)",
                "capabilities": ["chat", "reasoning"],
                "reasoning_type": "deepseek_reasoner",
                "reasoning_effort": "high",
                "context_length": 65536,
                "description": "纯血开源强化学习推理架构",
            },
            {
                "id": "deepseek-ai/DeepSeek-V3",
                "name": "DeepSeek V3 旗舰",
                "capabilities": ["chat", "tools"],
                "reasoning_type": "none",
                "reasoning_effort": "none",
                "context_length": 65536,
                "description": "高吞吐通用大语言模型",
            },
            {
                "id": "Qwen/Qwen2.5-72B-Instruct",
                "name": "Qwen 2.5 72B Instruct",
                "capabilities": ["chat", "tools"],
                "reasoning_type": "none",
                "reasoning_effort": "medium",
                "context_length": 131072,
                "description": "通义千问开源 72B 旗舰模型",
            },
            {
                "id": "Pro/deepseek-ai/DeepSeek-R1",
                "name": "DeepSeek R1 (企业专线)",
                "capabilities": ["chat", "reasoning"],
                "reasoning_type": "deepseek_reasoner",
                "reasoning_effort": "high",
                "context_length": 65536,
                "description": "硅基流动专线保障高并发推理",
            },
        ],
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "type": "Gemini",
        "group": "官方直连",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "Google AI Studio 官方原生/OpenAI 兼容端点",
        "models": [
            {
                "id": "gemini-3.8-flash",
                "name": "Gemini 3.8 Flash (百万上下文)",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "最新 3.8 代长思维链极速模型",
            },
            {
                "id": "gemini-3.7-flash",
                "name": "Gemini 3.7 Flash",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "Gemini 3.7 代旗舰思考模型",
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "复杂任务综合逻辑推理旗舰",
            },
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "高性价比快速多模态模型",
            },
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "type": "OpenRouter",
        "group": "聚合中继",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "全球模型路由聚合中继，汇集 400+ 最新旗舰模型",
        "models": [
            {
                "id": "google/gemini-3.8-flash",
                "name": "OpenRouter: Gemini 3.8 Flash",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1048576,
                "description": "通过 OpenRouter 路由，自动故障转移",
            },
            {
                "id": "openai/gpt-5.6-luna",
                "name": "OpenRouter: GPT-5.6 Luna",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1050000,
                "description": "2026 前沿旗舰智能体多模态模型",
            },
            {
                "id": "anthropic/claude-3.7-sonnet",
                "name": "OpenRouter: Claude 3.7 Sonnet",
                "capabilities": ["chat", "vision", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 200000,
                "description": "Claude 3.7 原生长思维链推演",
            },
            {
                "id": "deepseek/deepseek-r1-0528",
                "name": "OpenRouter: DeepSeek R1 0528",
                "capabilities": ["chat", "reasoning"],
                "reasoning_type": "deepseek_reasoner",
                "reasoning_effort": "high",
                "context_length": 163840,
                "description": "DeepSeek R1 强化更新版",
            },
            {
                "id": "z-ai/glm-5.3-flash",
                "name": "OpenRouter: GLM 5.3 Flash",
                "capabilities": ["chat", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1310720,
                "description": "智谱最新百万级超长上下文极速模型",
            },
            {
                "id": "qwen/qwen3.8-flash",
                "name": "OpenRouter: Qwen 3.8 Flash",
                "capabilities": ["chat", "tools", "reasoning"],
                "reasoning_type": "standard_effort",
                "reasoning_effort": "high",
                "context_length": 1000000,
                "description": "通义千问最新一代极速模型",
            },
        ],
    },
    {
        "id": "kelivoin",
        "name": "KelivoIN",
        "type": "中转服务",
        "group": "聚合中继",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.kelivoin.com/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "第三方高可用 AI 聚合路由中继",
        "models": [
            {"id": "gpt-5-turbo", "name": "GPT-5 Turbo", "capabilities": ["chat", "vision", "tools"], "reasoning_type": "none", "reasoning_effort": "none"},
            {"id": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
            {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
        ],
    },
    {
        "id": "tensdaq",
        "name": "Tensdaq",
        "type": "中转服务",
        "group": "聚合中继",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.tensdaq.com/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "Tensdaq AI 接口聚合平台",
        "models": [
            {"id": "deepseek-r1", "name": "DeepSeek R1", "capabilities": ["chat", "reasoning"], "reasoning_type": "deepseek_reasoner", "reasoning_effort": "high"},
            {"id": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
            {"id": "o3-pro", "name": "OpenAI o3 Pro", "capabilities": ["chat", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "DeepSeek",
        "group": "官方直连",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "DeepSeek 官方低延时直连端点",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek V3.1", "capabilities": ["chat", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "官方通用对话与函数调用模型"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (满血 671B)", "capabilities": ["chat", "reasoning"], "reasoning_type": "deepseek_reasoner", "reasoning_effort": "high", "description": "官方推理旗舰，深度思考链"},
            {"id": "deepseek-r1-0528", "name": "DeepSeek R1 0528", "capabilities": ["chat", "reasoning"], "reasoning_type": "deepseek_reasoner", "reasoning_effort": "high", "description": "最新权重增强强化学习版"},
            {"id": "deepseek-v4-flash-vision-exp", "name": "DeepSeek V4 Flash Vision Exp", "capabilities": ["chat", "vision", "reasoning"], "reasoning_type": "deepseek_reasoner", "reasoning_effort": "high", "description": "下一代多模态推理实验模型"},
        ],
    },
    {
        "id": "alhubmix",
        "name": "Alhubmix",
        "type": "中转服务",
        "group": "聚合中继",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.alhubmix.com/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "Alhubmix 聚合中转服务",
        "models": [
            {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
            {"id": "gpt-5.4-pro", "name": "GPT-5.4 Pro", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
        ],
    },
    {
        "id": "suixiang",
        "name": "随想AI中转站",
        "type": "中转服务",
        "group": "聚合中继",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.suixiang.ai/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "随想 AI 聚合中转平台",
        "models": [
            {"id": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
            {"id": "deepseek-r1", "name": "DeepSeek R1", "capabilities": ["chat", "reasoning"], "reasoning_type": "deepseek_reasoner", "reasoning_effort": "high"},
            {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high"},
        ],
    },
    {
        "id": "dashscope",
        "name": "阿里云千问",
        "type": "通义千问",
        "group": "国内平台",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "阿里云百炼大模型服务平台",
        "models": [
            {"id": "qwen-max-latest", "name": "Qwen Max Latest", "capabilities": ["chat", "vision", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "阿里百炼最高性能旗舰"},
            {"id": "qwen-plus-latest", "name": "Qwen Plus Latest", "capabilities": ["chat", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "高性价比均衡版本"},
            {"id": "qwq-32b-preview", "name": "QwQ 32B 推理预览", "capabilities": ["chat", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "阿里首款开源深度推演模型"},
            {"id": "qwen3.8-flash", "name": "Qwen 3.8 Flash", "capabilities": ["chat", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "2026 最新极速千问"},
        ],
    },
    {
        "id": "zhipu",
        "name": "智谱",
        "type": "GLM",
        "group": "国内平台",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "智谱 AI BigModel 开放平台",
        "models": [
            {"id": "glm-5.3-flash", "name": "GLM 5.3 Flash", "capabilities": ["chat", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "最新 1.3M 上下文超高速推理"},
            {"id": "glm-5", "name": "GLM 5 旗舰", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "智谱第五代通用大模型"},
            {"id": "glm-4-plus", "name": "GLM 4 Plus", "capabilities": ["chat", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "高泛化综合能力模型"},
        ],
    },
    {
        "id": "claude",
        "name": "Claude",
        "type": "Anthropic",
        "group": "官方直连",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "api_format": "claude_messages",
        "api_path": "/messages",
        "description": "Anthropic 官方原生 Messages API 直连",
        "models": [
            {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet (Thinking)", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "Anthropic 首款混合思维链模型"},
            {"id": "claude-fable-5.1", "name": "Claude Fable 5.1", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "百万上下文长篇综合推演旗舰"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet v2", "capabilities": ["chat", "vision", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "极强代码与逻辑感知"},
        ],
    },
    {
        "id": "grok",
        "name": "Grok",
        "type": "xAI",
        "group": "官方直连",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://api.x.ai/v1",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "xAI 官方 Grok 大模型接口",
        "models": [
            {"id": "grok-3", "name": "Grok 3 (最新多模态旗舰)", "capabilities": ["chat", "vision", "tools", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "xAI 顶级算力训练基座"},
            {"id": "grok-2-1212", "name": "Grok 2", "capabilities": ["chat", "vision", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "高速前沿大模型"},
        ],
    },
    {
        "id": "volcengine",
        "name": "火山引擎",
        "type": "火山引擎",
        "group": "国内平台",
        "enabled": False,
        "multi_key_enabled": False,
        "response_api_enabled": False,
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": "",
        "api_format": "openai_chat",
        "api_path": "/chat/completions",
        "description": "字节跳动火山方舟大模型服务平台",
        "models": [
            {"id": "doubao-1.5-pro-32k", "name": "豆包 1.5 Pro 32K", "capabilities": ["chat", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "高并发低成本主力模型"},
            {"id": "doubao-1.5-thinking", "name": "豆包 1.5 深度推演版", "capabilities": ["chat", "reasoning"], "reasoning_type": "standard_effort", "reasoning_effort": "high", "description": "长链推演与复杂规划"},
            {"id": "seed-2-1-turbo", "name": "Seed 2.1 Turbo", "capabilities": ["chat", "tools"], "reasoning_type": "none", "reasoning_effort": "none", "description": "ByteDance 最新代码与推理加速"},
        ],
    },
]


def init_llm_config() -> Dict[str, Any]:
    """Load or initialize clean, user-centric model configuration with multi-provider support."""
    from .config import settings

    data: Dict[str, Any] = {}
    if LLM_CONFIG_FILE.exists():
        try:
            with open(LLM_CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            data = {}

    # Extract current settings from .env / settings
    cur_url = getattr(settings, "llm_base_url", "") or os.getenv("LLM_BASE_URL") or "https://cpa.r20.cn/v1"
    cur_key = getattr(settings, "llm_api_key", "") or os.getenv("LLM_API_KEY") or ""
    cur_model = getattr(settings, "llm_model", "") or os.getenv("LLM_MODEL") or "gemini-3.8-flash-high"
    cur_effort = getattr(settings, "llm_reasoning_effort", "") or os.getenv("LLM_REASONING_EFFORT") or "high"

    existing_providers = data.get("providers", [])
    merged_providers: List[Dict[str, Any]] = []

    for dp in DEFAULT_PROVIDERS:
        pid = dp["id"]
        found = next((p for p in existing_providers if p.get("id") == pid), None)
        if found:
            p_obj = dict(dp)
            p_obj.update(found)
            if not p_obj.get("models"):
                p_obj["models"] = copy.deepcopy(dp.get("models", []))
            if pid == "openai":
                if not p_obj.get("api_key") and cur_key:
                    p_obj["api_key"] = cur_key
                if not p_obj.get("base_url"):
                    p_obj["base_url"] = cur_url
                p_obj["enabled"] = True
            merged_providers.append(p_obj)
        else:
            p_obj = copy.deepcopy(dp)
            if pid == "openai":
                if cur_key:
                    p_obj["api_key"] = cur_key
                if cur_url:
                    p_obj["base_url"] = cur_url
                p_obj["enabled"] = True
            merged_providers.append(p_obj)

    # Any custom provider added by user
    for ep in existing_providers:
        if not any(dp["id"] == ep.get("id") for dp in DEFAULT_PROVIDERS):
            merged_providers.append(ep)

    active_m_id = data.get("active_model_id") or cur_model or "gemini-3.8-flash-high"
    active_effort = data.get("active_reasoning_effort") or cur_effort or "high"

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
                "reasoning_type": m.get("reasoning_type", _detect_reasoning_type(mid)),
                "reasoning_effort": m.get("reasoning_effort") or m.get("default_effort", "high"),
                "capabilities": m.get("capabilities", _detect_capabilities(mid)),
                "context_length": m.get("context_length"),
                "description": m.get("description", ""),
            }

    # Preserve any custom models that were added by user or tests
    for m in data.get("models", []):
        mid = m.get("id")
        if mid:
            if mid in models_map:
                models_map[mid].update(m)
            else:
                models_map[mid] = m

    flat_models = list(models_map.values())
    if not any(m["id"] == active_m_id for m in flat_models) and flat_models:
        active_m_id = flat_models[0]["id"]

    config = {
        "version": "3.1",
        "active_model_id": active_m_id,
        "active_reasoning_effort": active_effort,
        "providers": merged_providers,
        "models": flat_models,
    }
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return config


# Backwards compatibility alias for app.py
LLM_PROVIDERS_FILE = LLM_CONFIG_FILE
init_llm_providers = init_llm_config


def load_llm_config(mask_keys: bool = True) -> Dict[str, Any]:
    """Return clean model configurations and configured providers matching modern client architecture."""
    config = init_llm_config()
    providers_list = config.get("providers", [])
    active_mid = config.get("active_model_id", "gemini-3.8-flash-high")
    active_effort = config.get("active_reasoning_effort", "high")

    res: Dict[str, Any] = {
        "version": config.get("version", "3.1"),
        "active_model_id": active_mid,
        "active_reasoning_effort": active_effort,
        "standard_reasoning_efforts": STANDARD_REASONING_EFFORTS,
        "supported_api_formats": SUPPORTED_API_FORMATS,
        "providers": [],
        "models": [],
        "active_provider_id": "openai",
    }

    for p in providers_list:
        pid = p.get("id", "")
        models_in_p = p.get("models", [])
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
                "is_active": m_id == active_mid,
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

    base_url = (base_url or os.getenv("LLM_BASE_URL", "https://cpa.r20.cn/v1")).rstrip("/")
    api_key = api_key or os.getenv("LLM_API_KEY", "")

    model_name = active_mid or getattr(settings, "llm_model", "gemini-3.8-flash-high")
    api_format = target_model.get("api_format") if target_model else _detect_api_format(base_url, model_name)
    reasoning_type = target_model.get("reasoning_type", "auto") if target_model else _detect_reasoning_type(model_name)

    return {
        "model": model_name,
        "name": target_model.get("name", model_name) if target_model else model_name,
        "provider_name": provider_name or "默认",
        "provider_id": provider_id or "openai",
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
        # Check providers models
        for p in config.get("providers", []):
            m_found = next((m for m in p.get("models", []) if m.get("id") == model_id), None)
            if m_found:
                target_model = {
                    "id": model_id,
                    "name": m_found.get("name", model_id),
                    "provider_id": p.get("id"),
                    "provider_name": p.get("name"),
                    "base_url": p.get("base_url"),
                    "api_key": p.get("api_key"),
                    "api_format": p.get("api_format", "openai_chat"),
                    "reasoning_type": m_found.get("reasoning_type", _detect_reasoning_type(model_id)),
                    "reasoning_effort": m_found.get("reasoning_effort", "high"),
                    "description": m_found.get("description", ""),
                }
                config.setdefault("models", []).append(target_model)
                break

    if not target_model:
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
        "active_provider_id": target_model.get("provider_id", "openai"),
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
    caps = model_data.get("capabilities") or _detect_capabilities(mid)
    ctx_len = model_data.get("context_length")

    if not mid:
        raise ValueError("模型 ID 不能为空")

    config = init_llm_config()

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
            provider_id = prov.get("id", "openai")

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
        existing["provider_id"] = provider_id or existing.get("provider_id", "openai")
        existing["provider_name"] = provider_name or existing.get("provider_name", "自定义")
        existing["base_url"] = base_url
        if api_key:
            existing["api_key"] = api_key
        existing["api_format"] = api_format
        existing["reasoning_type"] = reasoning_type
        existing["reasoning_effort"] = default_effort
        existing["capabilities"] = caps
        existing["context_length"] = ctx_len
        existing["description"] = desc
    else:
        models.append({
            "id": mid,
            "name": name,
            "provider_id": provider_id or "openai",
            "provider_name": provider_name or "自定义",
            "base_url": base_url,
            "api_key": api_key,
            "api_format": api_format,
            "reasoning_type": reasoning_type,
            "reasoning_effort": default_effort,
            "capabilities": caps,
            "context_length": ctx_len,
            "description": desc,
        })

    # Also update provider's local models array
    if prov:
        prov_models = prov.setdefault("models", [])
        p_existing = next((m for m in prov_models if m.get("id") == mid), None)
        if p_existing:
            p_existing["name"] = name
            p_existing["capabilities"] = caps
            p_existing["reasoning_type"] = reasoning_type
            p_existing["reasoning_effort"] = default_effort
            p_existing["context_length"] = ctx_len
            p_existing["description"] = desc
        else:
            prov_models.append({
                "id": mid,
                "name": name,
                "capabilities": caps,
                "reasoning_type": reasoning_type,
                "reasoning_effort": default_effort,
                "context_length": ctx_len,
                "description": desc,
            })

    _atomic_write_json(LLM_CONFIG_FILE, config)
    return {
        "model_id": mid,
        "name": name,
        "base_url": base_url,
        "api_format": api_format,
        "provider_id": provider_id or "openai",
    }


def delete_model(provider_id: str, model_id: str) -> bool:
    """Delete a custom model."""
    config = init_llm_config()
    if config.get("active_model_id") == model_id:
        raise ValueError("不能删除当前正在使用的模型；请先切换到其他模型后再删除。")

    models = config.get("models", [])
    filtered = [m for m in models if m["id"] != model_id]

    for prov in config.get("providers", []):
        if not provider_id or provider_id == "custom" or prov.get("id") == provider_id:
            prov["models"] = [m for m in prov.get("models", []) if m.get("id") != model_id]

    if len(filtered) == len(models):
        return False

    config["models"] = filtered
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return True


def upsert_provider(provider_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update an LLM provider definition."""
    pid = str(provider_data.get("id", "")).strip().lower()
    name = str(provider_data.get("name", "")).strip() or pid
    p_type = str(provider_data.get("type", "")).strip() or name
    p_group = str(provider_data.get("group", "")).strip() or "其他"
    enabled = bool(provider_data.get("enabled", False)) if "enabled" in provider_data else None
    multi_key_enabled = bool(provider_data.get("multi_key_enabled", False))
    response_api_enabled = bool(provider_data.get("response_api_enabled", False))
    base_url = str(provider_data.get("base_url", "")).strip().rstrip("/")
    api_key = str(provider_data.get("api_key", "")).strip()
    api_format = str(provider_data.get("api_format", "openai_chat")).strip()
    api_path = str(provider_data.get("api_path", "/chat/completions")).strip()
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
        existing["type"] = p_type
        existing["group"] = p_group
        if enabled is not None:
            existing["enabled"] = enabled
        existing["multi_key_enabled"] = multi_key_enabled
        existing["response_api_enabled"] = response_api_enabled
        existing["base_url"] = base_url
        if api_key:
            existing["api_key"] = api_key
        existing["api_format"] = api_format
        existing["api_path"] = api_path
        existing["description"] = desc
    else:
        providers.append({
            "id": pid,
            "name": name,
            "type": p_type,
            "group": p_group,
            "enabled": enabled if enabled is not None else False,
            "multi_key_enabled": multi_key_enabled,
            "response_api_enabled": response_api_enabled,
            "base_url": base_url,
            "api_key": api_key,
            "api_format": api_format,
            "api_path": api_path,
            "description": desc,
            "models": [],
        })
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return {"id": pid, "name": name, "base_url": base_url}


def toggle_provider(provider_id: str, enabled: Optional[bool] = None) -> Dict[str, Any]:
    """Toggle a provider's enabled/disabled state."""
    config = init_llm_config()
    providers = config.get("providers", [])
    p = next((x for x in providers if x["id"] == provider_id), None)
    if not p:
        raise ValueError(f"供应商 {provider_id} 未找到")
    if enabled is None:
        p["enabled"] = not p.get("enabled", False)
    else:
        p["enabled"] = bool(enabled)
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return {"id": provider_id, "enabled": p["enabled"]}


def clear_provider_models(provider_id: str) -> bool:
    """Clear all models under a specific provider."""
    config = init_llm_config()
    providers = config.get("providers", [])
    p = next((x for x in providers if x["id"] == provider_id), None)
    if not p:
        return False
    p["models"] = []
    config["models"] = [m for m in config.get("models", []) if m.get("provider_id") != provider_id]
    _atomic_write_json(LLM_CONFIG_FILE, config)
    return True


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
    """Fetch live models list from an OpenAI / OpenRouter / Anthropic compatible endpoint."""
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

    if not api_key:
        prov = next((p for p in config.get("providers", []) if p.get("base_url", "").rstrip("/") == cleaned_url and p.get("api_key")), None)
        if prov:
            api_key = prov.get("api_key", "")

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
        hdrs["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 R20-Quantum-Trader/6.6"
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
                    detected_caps = _detect_capabilities(m_id)
                    default_effort = "high" if detected_rtype != "none" else "auto"

                    parsed_models.append({
                        "id": m_id,
                        "name": m_name,
                        "capabilities": detected_caps,
                        "context_length": ctx,
                        "description": desc,
                        "api_format": detected_format,
                        "reasoning_type": detected_rtype,
                        "default_effort": default_effort,
                    })

                def _model_sort_key(m: Dict[str, Any]) -> Tuple[int, str]:
                    mid = m["id"].lower()
                    if any(k in mid for k in ["gemini-3", "claude-3-7", "claude-3.7", "o3", "o4", "gpt-5", "deepseek-r1", "deepseek-v4", "qwen-max", "qwq"]):
                        return (0, mid)
                    if any(k in mid for k in ["gemini-2", "claude-3-5", "claude-3.5", "o1", "gpt-4o", "qwen-2.5", "doubao"]):
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
