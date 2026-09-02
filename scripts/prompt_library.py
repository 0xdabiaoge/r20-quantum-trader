"""Versioned prompt profile library used directly by Python trading processes."""
from __future__ import annotations
import copy
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_FILE = ROOT / "data" / "prompt_library.json"
BJ_TZ = timezone(timedelta(hours=8))
TEMPLATE_KEYS = ("trading_system", "trading_user", "evolution_system", "evolution_user")
ALLOWED_VARIABLES = {"strategy_version", "timezone", "active_instruments", "profile_name"}
MAX_TEMPLATE_CHARS = 12_000
MAX_PROFILE_CHARS = 32_000
MAX_REVISIONS = 100
MAX_MODULES_PER_PIPELINE = 40
_SECTION_RE = re.compile(r"(?m)(?=^={0,30}\s*【[^\n】]+】[^\n]*$)")

PRESETS: dict[str, dict[str, Any]] = {
    "stable": {
        "id": "stable", "name": "稳健", "description": "重视信号一致性、回撤控制与等待质量，当前默认风格。", "editable": False,
        "trading_system": """【交易风格：稳健】\n仅在 P0 硬约束允许的候选中偏好高质量证据共振。要求 4H 方向、1H 结构、1H 微积分动力学、定积分能量、概率风险与量能资金形成可解释链条；证据冲突或缺失时 WAIT。保证金优先位于允许区间中低部，不为提高频率降低置信度。""",
        "trading_user": """【稳健裁决偏好】\n优先确认趋势延续，不猜测拐点。非 WAIT 决策必须引用具体 1H v/a/j/I、E/A、延续或击穿估计概率及 VaR/CVaR；新闻未知不是市场平稳证据，弱共振或肥尾风险扩张时 WAIT。""",
        "evolution_system": """【稳健复盘风格】\n优先识别回撤、过度交易、追价和低质量入场，但只使用真实可观测证据。小样本、数理快照缺失或因果不可辨时 NO_CHANGE；任何记忆都不得成为绕过硬风控的新阈值。""",
        "evolution_user": """【稳健进化任务】\n评估信号一致性、风险预算、手续费、入场与退出质量；只有多个独立样本支持时才沉淀新经验，否则保留旧记忆并提出需要补充的证据。""",
    },
    "aggressive": {
        "id": "aggressive", "name": "激进", "description": "提高高质量趋势与突破机会的参与度，但不放宽任何硬风控。", "editable": False,
        "trading_system": """【交易风格：激进】\n所有 P0 硬约束、OCO 与 JSON 契约保持不变。仅对 4H/1H 同向、1H 动力学与积分能量扩张、概率风险可接受且量能共振的机会提高参与度；可使用允许区间较高的保证金和杠杆，但不得逆势补仓、追逐失速行情或牺牲 R:R。""",
        "trading_user": """【激进裁决偏好】\n对证据链完整的强趋势果断决策，必须引用具体 1H v/a/j/I、E/A、方向估计概率及 VaR/CVaR。15M 只优化执行；高 jerk、肥尾或证据不一致时仍必须 WAIT。""",
        "evolution_system": """【激进复盘风格】\n复盘时同时识别错失强趋势、过早止盈和仓位利用不足，也必须审查追价、过度杠杆和假突破损失；任何进化建议不得削弱硬风控。""",
        "evolution_user": """【激进进化任务】\n重点比较高动能机会的参与率、趋势利润捕获、加仓时机与错失成本，同时检查激进参与是否造成尾部亏损扩大。""",
    },
}

EMPTY_CUSTOM = {
    "id": "custom-default", "name": "自定义方案", "description": "用自然语言调整策略，硬风控始终由系统锁定。", "editable": True,
    "enabled": True, "created_at": "", "updated_at": "", "editor_mode": "simple",
    "simple_policy": {"strategy": "", "review_focus": "", "participation": "balanced", "evidence": "strict", "risk_budget": "middle"},
    "trading_system": "", "trading_user": "", "evolution_system": "", "evolution_user": "",
}

_FORBIDDEN = (
    (re.compile(r"(?is)(忽略|绕过|取消|覆盖).{0,24}(P0|硬风控|风险门禁|OCO|JSON|止损|保证金上限)"), "不得要求忽略或覆盖 P0 与执行层硬约束"),
    (re.compile(r"(?is)(允许|可以).{0,20}(逆势补仓|无止损|跳过OCO|突破持仓上限)"), "不得放宽逆势补仓、OCO、止损或持仓上限"),
    (re.compile(r"(?is)ignore.{0,30}(system|risk|safety|json|oco)"), "不得要求忽略系统、风险、安全或 JSON 契约"),
    (re.compile(r"(?i)(sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{16,}|api[_ -]?key\s*[:=]\s*\S+)"), "提示词中禁止写入 API Key 或密钥"),
)
_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _now() -> str:
    return datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temp_path): os.unlink(temp_path)


def _default() -> dict[str, Any]:
    return {"version": 2, "active_profile_id": "stable", "profiles": {}, "revisions": []}


def _module(module: dict[str, Any], index: int = 0) -> dict[str, Any]:
    return {"id":str(module.get("id") or f"module-{uuid.uuid4().hex[:10]}")[:80],"title":str(module.get("title") or f"模块 {index+1}").strip()[:100],"content":str(module.get("content") or "").strip()[:MAX_TEMPLATE_CHARS],"enabled":bool(module.get("enabled",True)),"locked":bool(module.get("locked",False)),"source":str(module.get("source") or "custom")[:40]}


def text_to_modules(text: str, source: str = "legacy", locked: bool = False) -> list[dict[str, Any]]:
    chunks=[chunk.strip() for chunk in _SECTION_RE.split(str(text or "")) if chunk.strip()]
    if not chunks and str(text or "").strip(): chunks=[str(text).strip()]
    result=[]
    for i,chunk in enumerate(chunks):
        first=chunk.splitlines()[0].strip(" =") if chunk.splitlines() else f"模块 {i+1}"
        title=(re.search(r"【([^】]+)】",first).group(1) if re.search(r"【([^】]+)】",first) else first)[:100]
        result.append(_module({"title":title,"content":chunk,"locked":locked,"source":source},i))
    return result


def compile_modules(modules: list[dict[str, Any]]) -> str:
    return "\n\n".join(render_variables(str(item.get("content") or "")) for item in modules if item.get("enabled",True) and str(item.get("content") or "").strip()).strip()


def base_template_modules(text: str, pipeline: str) -> list[dict[str, Any]]:
    modules=text_to_modules(text,"base",locked=False)
    locked_patterns = {
        "trading_system": ("决策优先级", "输出与审计纪律"),
        "trading_user": ("当前决策时间戳", "全网实时重大快讯", "账户当前持仓", "在途未成交", "长期记忆", "行情、技术指标", "六币种原生行情", "推演与决策任务"),
        "evolution_system": ("不可覆盖", "输出", "JSON"),
        "evolution_user": ("当前认知复盘基准时间", "历史长期记忆库", "实盘战绩与历史交易台账"),
    }.get(pipeline, ())
    for module in modules:
        module["locked"] = any(token in module["title"] for token in locked_patterns)
    return modules


def _clean_pipelines(raw: Any, legacy: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    source=raw if isinstance(raw,dict) else {}
    result={}
    for key in TEMPLATE_KEYS:
        modules=source.get(key) if isinstance(source.get(key),list) else text_to_modules(str(legacy.get(key) or ""),"legacy")
        result[key]=[_module(item,i) for i,item in enumerate(modules[:MAX_MODULES_PER_PIPELINE]) if isinstance(item,dict)]
    return result


def _clean_profile(raw: dict[str, Any], profile_id: str | None = None) -> dict[str, Any]:
    now = _now()
    result = copy.deepcopy(EMPTY_CUSTOM)
    result.update({key: raw.get(key, result.get(key)) for key in result})
    result["id"] = profile_id or str(raw.get("id") or f"custom-{uuid.uuid4().hex[:10]}")
    result["name"] = str(result.get("name") or "自定义方案").strip()[:60]
    result["description"] = str(result.get("description") or "").strip()[:240]
    result["editable"] = True
    result["enabled"] = bool(result.get("enabled", True))
    result["editor_mode"] = str(raw.get("editor_mode") or ("advanced" if any(raw.get(k) for k in TEMPLATE_KEYS) else "simple"))
    if result["editor_mode"] not in {"simple", "advanced"}: result["editor_mode"] = "simple"
    policy = raw.get("simple_policy") if isinstance(raw.get("simple_policy"), dict) else {}
    result["simple_policy"] = {
        "strategy": str(policy.get("strategy") or "").strip()[:8000], "review_focus": str(policy.get("review_focus") or "").strip()[:4000],
        "participation": str(policy.get("participation") or "balanced"), "evidence": str(policy.get("evidence") or "strict"), "risk_budget": str(policy.get("risk_budget") or "middle"),
    }
    result["created_at"] = str(result.get("created_at") or now)
    result["updated_at"] = str(result.get("updated_at") or now)
    for key in TEMPLATE_KEYS: result[key] = str(result.get(key) or "").strip()
    if result["editor_mode"] == "simple" and not isinstance(raw.get("pipelines"), dict):
        result["pipelines"] = {}
    else:
        result["pipelines"] = _clean_pipelines(raw.get("pipelines"), result)
        if isinstance(raw.get("pipelines"), dict):
            for key in TEMPLATE_KEYS: result[key] = compile_modules(result["pipelines"][key])
        result["editor_mode"] = "modules"
    return result


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    if int(raw.get("version", 1)) >= 2 and isinstance(raw.get("profiles"), dict):
        payload = _default(); payload.update(raw)
        payload["profiles"] = {str(k): _clean_profile(v, str(k)) for k, v in raw.get("profiles", {}).items() if isinstance(v, dict)}
        payload["revisions"] = list(raw.get("revisions", []))[-MAX_REVISIONS:]
        return payload
    custom = _clean_profile(raw.get("custom") or {}, "custom-default")
    active_style = str(raw.get("active_style") or "stable")
    return {"version": 2, "active_profile_id": active_style if active_style in PRESETS else custom["id"], "profiles": {custom["id"]: custom}, "revisions": []}


def load_library() -> dict[str, Any]:
    try:
        raw = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
        payload = _migrate(raw if isinstance(raw, dict) else {})
    except (OSError, json.JSONDecodeError, ValueError):
        payload = _default()
    active = str(payload.get("active_profile_id") or "stable")
    if active not in PRESETS and active not in payload["profiles"]:
        active = "stable"
    payload["active_profile_id"] = active
    # Backward compatibility for old API/tests.
    payload["active_style"] = active if active in PRESETS else "custom"
    payload["custom"] = copy.deepcopy(payload["profiles"].get(active) or payload["profiles"].get("custom-default") or EMPTY_CUSTOM)
    return payload


def save_library(payload: dict[str, Any]) -> None:
    # Accept the v1 shape used by older admin clients. If a caller changed only
    # active_style/custom while active_profile_id still equals the persisted value,
    # treat it as an intentional legacy update.
    legacy_update = "profiles" not in payload
    if not legacy_update and "active_style" in payload:
        try:
            persisted_raw = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
            persisted_active = _migrate(persisted_raw).get("active_profile_id", "stable")
        except (OSError, json.JSONDecodeError, ValueError):
            persisted_active = "stable"
        requested_style = str(payload.get("active_style") or "stable")
        mapped_active = requested_style if requested_style in PRESETS else "custom"
        current_mapped = payload.get("active_profile_id") if payload.get("active_profile_id") in PRESETS else "custom"
        legacy_update = payload.get("active_profile_id", "stable") == persisted_active and mapped_active != current_mapped
    if legacy_update:
        existing = load_library()
        legacy_custom = copy.deepcopy(payload.get("custom") or existing.get("custom") or {})
        if any(legacy_custom.get(key) for key in TEMPLATE_KEYS): legacy_custom["editor_mode"] = "advanced"
        custom = _clean_profile(legacy_custom, "custom-default")
        existing["profiles"][custom["id"]] = custom
        style = str(payload.get("active_style") or "stable")
        existing["active_profile_id"] = style if style in PRESETS else custom["id"]
        payload = existing
    normalized = _migrate(payload)
    normalized.pop("active_style", None); normalized.pop("custom", None)
    _atomic_write(LIBRARY_FILE, normalized)


def resolve_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Compile ordered module pipelines while preserving V2 simple-profile compatibility."""
    resolved = copy.deepcopy(profile)
    if isinstance(resolved.get("pipelines"),dict) and any(resolved["pipelines"].get(key) for key in TEMPLATE_KEYS):
        for key in TEMPLATE_KEYS: resolved[key]=compile_modules(resolved["pipelines"].get(key,[]))
        return resolved
    if resolved.get("editor_mode") != "simple": return resolved
    policy = resolved.get("simple_policy") or {}; strategy = str(policy.get("strategy") or "").strip(); review = str(policy.get("review_focus") or "").strip()
    participation = {"conservative":"稳健参与，证据不足时等待", "balanced":"均衡参与高质量机会", "active":"积极参与证据完整的趋势机会"}.get(policy.get("participation"), "均衡参与高质量机会")
    evidence = {"strict":"要求多周期、动力学、能量与概率风险严格共振", "balanced":"允许轻微证据分歧但必须可解释", "trend":"趋势与动力学优先，风险异常仍等待"}.get(policy.get("evidence"), "要求多周期、动力学、能量与概率风险严格共振")
    risk = {"low":"优先使用允许风险区间低位", "middle":"优先使用允许风险区间中位", "high":"强信号可使用允许风险区间高位但绝不突破硬上限"}.get(policy.get("risk_budget"), "优先使用允许风险区间中位")
    resolved["trading_system"] = f"【用户策略偏好·简单模式】\n{participation}；{evidence}；{risk}。\n{strategy}".strip()
    resolved["trading_user"] = ""
    resolved["evolution_system"] = f"【用户复盘关注·简单模式】\n围绕用户策略检查执行一致性，不得修改 P0、OCO、JSON 契约或风险硬门禁。\n{review or strategy}".strip()
    resolved["evolution_user"] = ""
    return resolved


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    name = str(profile.get("name") or "").strip()
    if not 1 <= len(name) <= 60: errors.append("方案名称长度必须为 1-60")
    pipelines = profile.get("pipelines") if isinstance(profile.get("pipelines"),dict) else {}
    module_total = 0
    for pipeline, modules in pipelines.items():
        if pipeline not in TEMPLATE_KEYS or not isinstance(modules,list): errors.append(f"无效消息管线：{pipeline}"); continue
        if len(modules)>MAX_MODULES_PER_PIPELINE: errors.append(f"{pipeline} 模块数不得超过 {MAX_MODULES_PER_PIPELINE}")
        seen=set()
        for module in modules:
            module_id=str(module.get("id") or "")
            if not module_id or module_id in seen: errors.append(f"{pipeline} 模块 ID 缺失或重复")
            seen.add(module_id)
            value=str(module.get("content") or ""); module_total += len(value)
            if module.get("source")=="base" and module.get("locked"): continue
            for pattern,message in _FORBIDDEN:
                for match in pattern.finditer(value):
                    prefix=value[max(0,match.start()-12):match.start()]
                    if re.search(r"(不得|严禁|禁止|不可).{0,10}$",prefix): continue
                    errors.append(f"{pipeline}/{module.get('title','模块')}：{message}"); break
    policy = profile.get("simple_policy") if isinstance(profile.get("simple_policy"), dict) else {}
    if profile.get("editor_mode") == "simple":
        strategy = str(policy.get("strategy") or ""); review = str(policy.get("review_focus") or "")
        if not strategy.strip(): warnings.append("简单策略说明为空，将仅使用选择项和系统基础提示词")
        for label,value in (("策略说明",strategy),("复盘重点",review)):
            for pattern,message in _FORBIDDEN:
                if pattern.search(value): errors.append(f"{label}：{message}")
        if policy.get("participation","balanced") not in {"conservative","balanced","active"}: errors.append("参与风格无效")
        if policy.get("evidence","strict") not in {"strict","balanced","trend"}: errors.append("证据要求无效")
        if policy.get("risk_budget","middle") not in {"low","middle","high"}: errors.append("风险预算无效")
    total = 0
    for key in TEMPLATE_KEYS:
        value = "" if pipelines else str(profile.get(key) or "")
        total += len(value)
        if len(value) > MAX_TEMPLATE_CHARS: errors.append(f"{key} 超过 {MAX_TEMPLATE_CHARS} 字符")
        unknown = sorted(set(_VAR_RE.findall(value)) - ALLOWED_VARIABLES)
        if unknown: errors.append(f"{key} 包含未知变量：{', '.join(unknown)}")
        for pattern, message in _FORBIDDEN:
            for match in pattern.finditer(value):
                prefix = value[max(0, match.start() - 12):match.start()]
                if re.search(r"(不得|严禁|禁止|不可).{0,10}$", prefix):
                    continue
                errors.append(f"{key}：{message}")
                break
    if total > MAX_PROFILE_CHARS: errors.append(f"四类模板合计不得超过 {MAX_PROFILE_CHARS} 字符")
    if not total and not pipelines and profile.get("editor_mode") != "simple": warnings.append("当前方案四类附加模板均为空，将只使用基础提示词")
    return {"valid": not errors, "errors": list(dict.fromkeys(errors)), "warnings": warnings, "characters": module_total if pipelines else total}


def _revision(profile: dict[str, Any], action: str, note: str = "") -> dict[str, Any]:
    return {"id": f"rev-{uuid.uuid4().hex[:12]}", "profile_id": profile["id"], "action": action, "note": str(note)[:240], "created_at": _now(), "snapshot": copy.deepcopy(profile)}


def create_profile(name: str, description: str = "", source_id: str = "stable", note: str = "创建方案") -> dict[str, Any]:
    library = load_library()
    source = get_profile(source_id)
    profile = _clean_profile({**source, "id": f"custom-{uuid.uuid4().hex[:10]}", "name": name, "description": description, "editor_mode": "simple", "simple_policy": {"strategy": "", "review_focus": "", "participation": "balanced", "evidence": "strict", "risk_budget": "middle"}, "created_at": _now(), "updated_at": _now()})
    check = validate_profile(profile)
    if not check["valid"]: raise ValueError("；".join(check["errors"]))
    library["profiles"][profile["id"]] = profile
    library["revisions"].append(_revision(profile, "create", note))
    save_library(library)
    return profile


def update_profile(profile_id: str, changes: dict[str, Any], note: str = "更新方案") -> dict[str, Any]:
    if profile_id in PRESETS: raise ValueError("内置预设不可编辑，请先复制为自定义方案")
    library = load_library()
    if profile_id not in library["profiles"]: raise ValueError("提示词方案不存在")
    current = library["profiles"][profile_id]
    accepted = {k: v for k, v in changes.items() if k in {"name", "description", "enabled", "editor_mode", "simple_policy", "pipelines", *TEMPLATE_KEYS}}
    flat_updates = [key for key in TEMPLATE_KEYS if key in accepted]
    if "pipelines" not in accepted and flat_updates:
        accepted["pipelines"] = copy.deepcopy(current.get("pipelines") or {})
        for key in flat_updates: accepted["pipelines"][key] = text_to_modules(str(accepted[key] or ""), "legacy")
        accepted["editor_mode"] = "modules"
    elif "editor_mode" not in accepted and any(str(accepted.get(key) or "").strip() for key in TEMPLATE_KEYS): accepted["editor_mode"] = "advanced"
    updated = _clean_profile({**current, **accepted, "updated_at": _now()}, profile_id)
    check = validate_profile(updated)
    if not check["valid"]: raise ValueError("；".join(check["errors"]))
    library["profiles"][profile_id] = updated
    library["revisions"].append(_revision(updated, "update", note))
    library["revisions"] = library["revisions"][-MAX_REVISIONS:]
    save_library(library)
    return updated


def delete_profile(profile_id: str) -> None:
    if profile_id in PRESETS: raise ValueError("内置预设不可删除")
    library = load_library()
    if profile_id == library["active_profile_id"]: raise ValueError("当前启用方案不能删除，请先切换方案")
    if profile_id not in library["profiles"]: raise ValueError("提示词方案不存在")
    del library["profiles"][profile_id]
    save_library(library)


def activate_profile(profile_id: str) -> dict[str, Any]:
    library = load_library()
    profile = get_profile(profile_id)
    if not profile.get("enabled", True): raise ValueError("该方案已停用")
    library["active_profile_id"] = profile_id
    save_library(library)
    return profile


def get_profile(profile_id: str) -> dict[str, Any]:
    if profile_id in PRESETS: return copy.deepcopy(PRESETS[profile_id])
    profile = load_library()["profiles"].get(profile_id)
    if not profile: raise ValueError("提示词方案不存在")
    return copy.deepcopy(profile)


def profile_history(profile_id: str) -> list[dict[str, Any]]:
    return [copy.deepcopy(x) for x in reversed(load_library()["revisions"]) if x.get("profile_id") == profile_id]


def rollback_profile(profile_id: str, revision_id: str) -> dict[str, Any]:
    library = load_library()
    revision = next((x for x in library["revisions"] if x.get("id") == revision_id and x.get("profile_id") == profile_id), None)
    if not revision: raise ValueError("历史版本不存在")
    restored = _clean_profile({**revision["snapshot"], "updated_at": _now()}, profile_id)
    library["profiles"][profile_id] = restored
    library["revisions"].append(_revision(restored, "rollback", f"回滚到 {revision_id}"))
    save_library(library)
    return restored


def export_profile(profile_id: str) -> dict[str, Any]:
    profile = get_profile(profile_id)
    return {"format": "r20-prompt-profile", "version": 3, "exported_at": _now(), "profile": {k: profile.get(k) for k in ("name", "description", "editor_mode", "pipelines", "simple_policy", *TEMPLATE_KEYS)}}


def import_profile(payload: dict[str, Any], name_override: str = "") -> dict[str, Any]:
    if payload.get("format") != "r20-prompt-profile" or not isinstance(payload.get("profile"), dict): raise ValueError("无效的 R20 提示词方案文件")
    source = payload["profile"]
    if isinstance(source.get("pipelines"), dict) and any(source.get("pipelines", {}).values()):
        profile=create_profile(name_override or str(source.get("name") or "导入方案"),str(source.get("description") or ""),"stable","导入模块方案")
        return update_profile(profile["id"],{"editor_mode":"modules","pipelines":source["pipelines"]},"导入模板构成")
    if source.get("editor_mode") == "simple" or (not source.get("editor_mode") and source.get("simple_policy")):
        profile = create_profile(name_override or str(source.get("name") or "导入方案"), str(source.get("description") or ""), "stable", "导入简单方案")
        return update_profile(profile["id"], {"editor_mode": "simple", "simple_policy": source.get("simple_policy") or {}}, "导入简单策略")
    return create_profile(name_override or str(source.get("name") or "导入方案"), str(source.get("description") or ""), "stable", "导入方案") if not any(source.get(k) for k in TEMPLATE_KEYS) else _import_with_templates(source, name_override)


def _import_with_templates(source: dict[str, Any], name_override: str) -> dict[str, Any]:
    profile = create_profile(name_override or str(source.get("name") or "导入方案"), str(source.get("description") or ""), "stable", "导入方案")
    return update_profile(profile["id"], {key: source.get(key, "") for key in TEMPLATE_KEYS}, "导入模板内容")


def active_profile() -> dict[str, Any]:
    return resolve_profile(get_profile(load_library()["active_profile_id"]))


def all_profiles() -> list[dict[str, Any]]:
    library = load_library()
    return [copy.deepcopy(PRESETS["stable"]), copy.deepcopy(PRESETS["aggressive"]), *[copy.deepcopy(x) for x in library["profiles"].values()]]


def _variable_context(profile_name: str = "") -> dict[str, str]:
    instruments = "BTC,ETH,SOL,DOGE,SUI,LINK"
    try:
        from scripts.instrument_pool import load_instrument_pool
        instruments = ",".join(str(x.get("name") or x.get("instId") or "") for x in load_instrument_pool())
    except Exception:
        pass
    return {"strategy_version": os.getenv("R20_VERSION", "6.0.0-preview"), "timezone": "Asia/Shanghai", "active_instruments": instruments, "profile_name": profile_name}


def render_variables(text: str, context: dict[str, str] | None = None) -> str:
    values = {**_variable_context(), **(context or {})}
    return _VAR_RE.sub(lambda m: str(values.get(m.group(1), m.group(0))), text or "")


def _trading_user_parent_groups(base_modules: list[dict[str, Any]], layout_titles: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Associate nested live-value modules with the preceding editor-visible section."""
    groups: dict[str, list[dict[str, Any]]] = {}
    current_parent = ""
    for module in base_modules:
        title = module["title"]
        if title in layout_titles:
            current_parent = title
            groups.setdefault(title, []).append(module)
        elif current_parent:
            groups[current_parent].append(module)
    return groups


def apply_module_layout(base: str, profile: dict[str, Any], pipeline: str, label: str) -> str:
    """Build a real message from base sections plus ordered profile modules.

    Modules whose source is ``base`` reference the live base section by id; custom
    and legacy modules carry editable content. Locked base modules stay visible.
    Trading-user runtime sections may contain many nested ``【...】`` labels. Those
    live values are merged back into their parent editor slot instead of being
    appended out of order or replaced by static placeholder text.
    """
    base_modules = base_template_modules(base, pipeline)
    layout = ((profile.get("pipelines") or {}).get(pipeline) if isinstance(profile.get("pipelines"), dict) else None)
    if not isinstance(layout, list) or not any(item.get("source") == "base" for item in layout):
        custom = text_to_modules(str(profile.get(pipeline) or ""), "custom")
        return compile_modules(base_modules + custom)

    base_by_title = {item["title"]: item for item in base_modules}
    layout_titles = {str(item.get("title") or "") for item in layout if item.get("source") == "base"}
    runtime_groups = _trading_user_parent_groups(base_modules, layout_titles) if pipeline == "trading_user" else {}
    output: list[dict[str, Any]] = []
    matched: set[str] = set()

    for item in layout:
        if item.get("source") != "base":
            if item.get("enabled", True):
                output.append(item)
            continue

        title = str(item.get("title") or "")
        live = base_by_title.get(title)
        if not live:
            continue

        group = runtime_groups.get(title, [live])
        matched.update(module["title"] for module in group)
        if not (live.get("locked") or item.get("enabled", True)):
            continue

        if pipeline == "trading_user" and live.get("locked"):
            content = compile_modules(group)
        else:
            content = live["content"] if live.get("locked") else str(item.get("content") or live["content"])
        output.append({**live, "content": content})

    # Fail closed: preserve every live value that an older layout does not know.
    output.extend(module for module in base_modules if module["title"] not in matched)
    return compile_modules(output)


def pipeline_view(base: str, profile: dict[str, Any], pipeline: str) -> list[dict[str, Any]]:
    base_modules=base_template_modules(base,pipeline)
    current=((profile.get("pipelines") or {}).get(pipeline) if isinstance(profile.get("pipelines"),dict) else [])
    if isinstance(current,list) and any(item.get("source")=="base" for item in current): return copy.deepcopy(current)
    return base_modules + text_to_modules(str(profile.get(pipeline) or ""),"custom")


def append_layer(base: str, layer: str, label: str) -> str:
    layer = render_variables((layer or "").strip(), {"profile_name": label})
    return base if not layer else f"{base.rstrip()}\n\n======================= 【{label}】 =======================\n{layer}"
