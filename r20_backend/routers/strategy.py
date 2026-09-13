"""Prompt studio, Council Pro, policy snapshots, self-evolution memory, and interceptor routes."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Header, HTTPException

from r20_backend.config import refresh_settings
from r20_backend.audit import record as audit_record
from r20_backend.dependencies import (
    ROOT, DATA_DIR, PROMPT_OVERRIDE_FILE,
    require_admin_header, require_superadmin,
)
from r20_backend.prompt_views import EVOLUTION_USER_TEMPLATE, TRADING_USER_TEMPLATE, rendered_snapshots
from r20_backend.schemas import (
    CouncilConfigUpdateRequest,
    CouncilApplySuiteRequest,
    CouncilResetRoleRequest,
    CouncilImportRequest,
    CouncilTestRequest,
    InterceptorToggleRequest,
    InterceptorCodeRequest,
    InterceptorCreateRequest,
    InterceptorReorderRequest,
    InterceptorTestRequest,
    PolicyArchiveRequest,
    PolicyRestoreRequest,
    PromptLibraryUpdate,
    PromptProfileCreateRequest,
    PromptProfileUpdateRequest,
    PromptImportRequest,
    PromptRollbackRequest,
    PromptOverrideRequest,
)
from scripts.prompt_library import (
    active_profile, activate_profile, all_profiles, apply_module_layout,
    create_profile, delete_profile, export_profile, get_profile, import_profile,
    load_library, pipeline_view, profile_history, rollback_profile, save_library, update_profile, validate_profile,
)

router = APIRouter(tags=["strategy"])


# ============================================================================
# MULTI-AGENT COUNCIL
# ============================================================================

@router.get("/api/v1/admin/council/config")
def admin_get_council_config(x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_admin_header(x_r20_session=x_r20_session)
    from r20_backend.council_manager import load_council_config, get_available_presets, get_preset_suites
    cfg = load_council_config()
    cfg["available_presets"] = get_available_presets()
    cfg["available_suites"] = get_preset_suites()
    return cfg


@router.put("/api/v1/admin/council/config")
def admin_update_council_config(payload: CouncilConfigUpdateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.council_manager import save_council_config
    saved = save_council_config({
        "enabled": payload.enabled,
        "consensus_mode": payload.consensus_mode,
        "timeout_seconds": payload.timeout_seconds,
        "roles": payload.roles,
    })
    audit_record("council.config.update", "success", {
        "actor": actor["username"],
        "enabled": payload.enabled,
        "consensus_mode": payload.consensus_mode,
        "timeout_seconds": payload.timeout_seconds,
    })
    return {"status": "ok", "config": saved}


@router.post("/api/v1/admin/council/apply-suite")
def admin_apply_council_suite(payload: CouncilApplySuiteRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.council_manager import apply_preset_suite
    try:
        saved = apply_preset_suite(payload.suite_id)
        audit_record("council.suite.apply", "success", {"actor": actor["username"], "suite_id": payload.suite_id})
        return {"status": "ok", "suite_id": payload.suite_id, "config": saved}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/v1/admin/council/reset-role")
def admin_reset_council_role(payload: CouncilResetRoleRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.council_manager import reset_role_template
    saved = reset_role_template(payload.role_id)
    audit_record("council.role.reset", "success", {"actor": actor["username"], "role_id": payload.role_id})
    return {"status": "ok", "role_id": payload.role_id, "config": saved}


@router.get("/api/v1/admin/council/export")
def admin_export_council_config(x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_admin_header(x_r20_session=x_r20_session)
    from r20_backend.council_manager import export_council_config
    return export_council_config()


@router.post("/api/v1/admin/council/import")
def admin_import_council_config(payload: CouncilImportRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.council_manager import import_council_config
    try:
        result = import_council_config(payload.payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_record("council.config.import", "success", {
        "actor": actor["username"],
        "roles": result.get("roles"),
        "backup_file": result.get("backup_file"),
    })
    return {"status": "ok", **result}


@router.post("/api/v1/admin/council/test")
def admin_test_council_debate(payload: CouncilTestRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_admin_header(x_r20_session=x_r20_session)
    from r20_backend.council_manager import execute_council_debate, load_council_config
    from scripts.instrument_pool import load_instruments
    c_cfg = load_council_config()

    if payload.mock_market_prompt:
        test_market = payload.mock_market_prompt
    else:
        active_insts = load_instruments()
        symbols = [x.get("instId", "") for x in active_insts]
        factor_snap_file = ROOT / "data" / "factor_library_snapshot.json"
        factor_data = {}
        if factor_snap_file.is_file():
            try:
                factor_data = json.loads(factor_snap_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        lines = [
            "======================= 【推演基准与资金持仓】 =======================",
            "【推演基准时间】: 2026-09-05 08:30:00 (北京时间)",
            "【当前账户可用资金】: 1,450.00 USDT (总资产 2,280.00 USDT)",
            "【账户持仓概况】: 当前总持仓 1/6 (已占用保证金 150.00 USDT)",
            "【当前活动在途持仓明细】:",
            "- 标的: BTC-USDT-SWAP | 方向: BUY_LONG 3x | 开仓均价: 77200.0 | 当前标记价: 78250.0 | 持仓量: 10张 | 未结浮盈: +35.00 U (ROI: +23.3%) | 动态止损线: 76800.0",
            "【当前在途挂单列表】:",
            "- [挂单ID: ord_10283] SOL-USDT-SWAP | 限价买多 15张 @ 98.20 | 挂单时间: 2026-09-05 07:15:00 | 附带云端止盈: 105.0 / 止损: 94.5",
            "",
            "======================= 【市场全要素动力学与微结构实时快照 (6大主力标的)】 =======================",
        ]
        for sym in symbols:
            f = factor_data.get(sym, {})
            c_px = float(f.get("close") or f.get("price") or 0.0)
            v_val = f.get("v_1h", 0.05)
            a_val = f.get("a_1h", 0.12)
            adx_val = f.get("adx_1h", 22.5)
            cmf_val = f.get("cmf_1h", 0.08)
            smart_val = f.get("smart_money_long_ratio", 68.0)
            atr_val = f.get("atr_1h", c_px * 0.015)
            lines.append(
                f"- {sym}: 现价 ${c_px}, 1H动能 v={v_val:+.4f}, a={a_val:+.4f}, ADX={adx_val:.1f}, "
                f"1H ATR={atr_val:.4f}, CMF={cmf_val:+.2f}, 聪明钱多头={smart_val:.1f}%"
            )
        test_market = "\n".join(lines)

    from scripts.prompt_library import active_profile, compile_modules, apply_module_layout
    try:
        prof = active_profile()
        sys_mods = prof.get("pipelines", {}).get("trading_system", [])
        test_sys = apply_module_layout(compile_modules(sys_mods), {}, "trading_system", "委员会测试", context={"market_matrix": test_market, "profile_name": prof.get("name", "")}) if sys_mods else "你是 R20 Quantum Trader 首席量化官，执行多空对称顺势战法与 2.0x ATR 宽止损。"
    except Exception:
        test_sys = "你是一个遵循多空对称顺势、1.8~2.2x ATR 宽止损与 0.8R 保本锁利的量化交易系统。"

    try:
        brain_output, transcript = execute_council_debate(
            market_prompt=test_market,
            original_system_prompt=test_sys,
            timeout=float(c_cfg.get("timeout_seconds", 60.0)),
        )
        return {
            "status": "ok",
            "brain_output": brain_output,
            "transcript": transcript,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
        }


# =========================================================================
# Physical Risk Interceptor Plugins API
# =========================================================================

@router.get("/api/v1/admin/interceptors")
def admin_list_interceptors(x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_admin_header(x_r20_session=x_r20_session)
    from r20_backend.interceptor_manager import list_plugins
    return {"plugins": list_plugins()}


@router.get("/api/v1/admin/interceptors/{filename}")
def admin_get_interceptor(filename: str, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_admin_header(x_r20_session=x_r20_session)
    from r20_backend.interceptor_manager import get_plugin_detail
    try:
        return get_plugin_detail(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/api/v1/admin/interceptors/{filename}/toggle")
def admin_toggle_interceptor(filename: str, payload: InterceptorToggleRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.interceptor_manager import toggle_plugin
    res = toggle_plugin(filename, payload.enabled)
    audit_record("interceptor.toggle", "success", {"actor": actor["username"], "filename": filename, "enabled": payload.enabled})
    return res


@router.put("/api/v1/admin/interceptors/{filename}/code")
def admin_save_interceptor_code(filename: str, payload: InterceptorCodeRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.interceptor_manager import save_plugin_code
    try:
        res = save_plugin_code(filename, payload.code)
        audit_record("interceptor.code.update", "success", {"actor": actor["username"], "filename": filename})
        return res
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/api/v1/admin/interceptors")
def admin_create_interceptor(payload: InterceptorCreateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.interceptor_manager import create_plugin
    try:
        res = create_plugin(payload.filename, payload.code)
        audit_record("interceptor.create", "success", {"actor": actor["username"], "filename": payload.filename})
        return res
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.delete("/api/v1/admin/interceptors/{filename}")
def admin_delete_interceptor(filename: str, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.interceptor_manager import delete_plugin
    try:
        delete_plugin(filename)
        audit_record("interceptor.delete", "success", {"actor": actor["username"], "filename": filename})
        return {"deleted": True, "filename": filename}
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/api/v1/admin/interceptors/reorder")
def admin_reorder_interceptors(payload: InterceptorReorderRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.interceptor_manager import reorder_plugins
    res = reorder_plugins(payload.pipeline_order)
    audit_record("interceptor.reorder", "success", {"actor": actor["username"]})
    return {"plugins": res}


@router.post("/api/v1/admin/interceptors/test")
def admin_test_interceptors(payload: InterceptorTestRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_admin_header(x_r20_session=x_r20_session)
    from r20_backend.interceptor_manager import run_sandbox_test
    return run_sandbox_test(payload.scenario)


# =========================================================================
# Unified Policy Snapshot & Version Control API
# =========================================================================

@router.get("/api/v1/admin/policy/current-snapshot")
def admin_get_policy_current_snapshot(
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token, x_r20_session)
    from r20_backend.policy_snapshot import capture_full_strategy_package, generate_policy_snapshot, package_identity
    try:
        snapshot = generate_policy_snapshot()
        # 审计 P0-3：四单元 policy_hash 看不到风控/路由——只差风控的两个归档会同 hash，
        # 「● 当前正在运行」若只比 policy_hash 就会同时点亮两个版本（UI 谎报）。
        # 这里补一个整包标识，前端据此精确判定哪一份真的在运行。
        try:
            package_hash = package_identity(capture_full_strategy_package().get("package") or {})
        except Exception:
            package_hash = ""
        return {
            "ok": True,
            "policy_version": snapshot.get("policy_version"),
            "policy_hash": snapshot.get("policy_hash"),
            "package_hash": package_hash,
            "snapshot": snapshot,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取策略快照失败: {exc}")


@router.get("/api/v1/admin/policy/archives")
def admin_get_policy_archives(
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token, x_r20_session)
    from r20_backend.policy_snapshot import load_archive_index
    try:
        archives = load_archive_index()
        return {"ok": True, "archives": archives}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取策略归档列表失败: {exc}")


@router.post("/api/v1/admin/policy/archive")
def admin_archive_policy(
    payload: PolicyArchiveRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.policy_snapshot import archive_current_policy
    author = actor.get("username", "admin")
    try:
        entry = archive_current_policy(name=payload.name, description=payload.description, author=author)
        audit_record("policy.archive", "success", {
            "actor": actor["username"], "name": payload.name,
            "policy_hash": entry.get("policy_hash"), "package_hash": entry.get("package_hash"),
        })
        return {"ok": True, "entry": entry}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建策略归档失败: {exc}")


@router.post("/api/v1/admin/policy/restore")
def admin_restore_policy(
    payload: PolicyRestoreRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    from r20_backend.policy_snapshot import restore_archived_policy
    try:
        # 审计 P0-4(2026-09-13)：此处原写 `payload` 的 hash 属性——PolicyRestoreRequest
        # 只有 policy_hash 字段（pydantic 不产生该属性），于是**回滚已把 6 个存储全部
        # 改完之后**在审计行抛 AttributeError，被下方 except 兜成 HTTP 500
        # 「恢复策略版本失败」：管理员看到失败、系统实际已回滚、policy.restore 审计
        # 永不落库。改用真实字段并按同族路由补 actor。
        p_hash = payload.policy_hash or ""
        res = restore_archived_policy(policy_hash=p_hash)
        audit_record("policy.restore", "success", {
            "actor": actor["username"], "policy_hash": p_hash,
            "target_policy_hash": res.get("target_policy_hash", p_hash),
        })
        return {"ok": True, **res}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"恢复策略版本失败: {exc}")


@router.delete("/api/v1/admin/policy/archive/{policy_hash}")
def admin_delete_policy_archive(
    policy_hash: str,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if not policy_hash or not re.match(r"^[a-zA-Z0-9_-]+$", policy_hash):
        raise HTTPException(status_code=400, detail=f"无效的策略哈希标识: {policy_hash}")
    from r20_backend.policy_snapshot import delete_archived_policy
    try:
        res = delete_archived_policy(policy_hash=policy_hash)
        audit_record("policy.delete", "success", {"actor": actor["username"], "policy_hash": policy_hash})
        return {"ok": True, **res}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除策略归档失败: {exc}")


# =========================================================================
# Prompt Studio & Library API
# =========================================================================

@router.get("/api/v1/prompt-library")
@router.get("/api/v1/admin/prompt-library")
def prompt_library(x_r20_session: str | None = Header(default=None, alias="X-R20-Session"), x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    from scripts.ai_brain_trader import SYSTEM_PROMPT
    from scripts.self_improvement_engine import EVOLUTION_SYSTEM_PROMPT
    try:
        library = load_library()
        profile = active_profile()
        return {
            "active_style": library["active_style"],
            "active_profile_id": library["active_profile_id"],
            "profiles": [{**item, "pipeline_views": {
                "trading_system": pipeline_view(SYSTEM_PROMPT, item, "trading_system"),
                "trading_user": pipeline_view(TRADING_USER_TEMPLATE, item, "trading_user"),
                "evolution_system": pipeline_view(EVOLUTION_SYSTEM_PROMPT, item, "evolution_system"),
                "evolution_user": pipeline_view(EVOLUTION_USER_TEMPLATE, item, "evolution_user"),
            }} for item in all_profiles()],
            "base_templates": {
                "trading_system": SYSTEM_PROMPT,
                "trading_user": TRADING_USER_TEMPLATE,
                "evolution_system": EVOLUTION_SYSTEM_PROMPT,
                "evolution_user": EVOLUTION_USER_TEMPLATE,
            },
            "pipelines": {
                "trading_system": pipeline_view(SYSTEM_PROMPT, profile, "trading_system"),
                "trading_user": pipeline_view(TRADING_USER_TEMPLATE, profile, "trading_user"),
                "evolution_system": pipeline_view(EVOLUTION_SYSTEM_PROMPT, profile, "evolution_system"),
                "evolution_user": pipeline_view(EVOLUTION_USER_TEMPLATE, profile, "evolution_user"),
            },
            "preview_mode": "template_only_not_runtime",
            "effective_templates": {
                "trading_system": apply_module_layout(SYSTEM_PROMPT, profile, "trading_system", "交易 System"),
                "trading_user": apply_module_layout(TRADING_USER_TEMPLATE, profile, "trading_user", "交易 User"),
                "evolution_system": apply_module_layout(EVOLUTION_SYSTEM_PROMPT, profile, "evolution_system", "自进化 System"),
                "evolution_user": apply_module_layout(EVOLUTION_USER_TEMPLATE, profile, "evolution_user", "自进化 User"),
            },
            "snapshots": rendered_snapshots(),
            "template_variables": __import__("scripts.prompt_library", fromlist=["TEMPLATE_VARIABLES_METADATA"]).TEMPLATE_VARIABLES_METADATA,
            "transport": "python-direct",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取提示词库失败: {exc}")


@router.put("/api/v1/admin/prompt-library")
def update_prompt_library(
    payload: PromptLibraryUpdate,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    refresh_settings()
    actor = require_superadmin(x_r20_session)
    try:
        library = load_library()
        library["active_style"] = payload.active_style
        library["custom"] = {
            "id": "custom", "name": "自定义", "description": "管理员自定义风格附加层。", "editable": True,
            "trading_system": payload.trading_system.strip(), "trading_user": payload.trading_user.strip(),
            "evolution_system": payload.evolution_system.strip(), "evolution_user": payload.evolution_user.strip(),
        }
        save_library(library)
        audit_record("prompt.library.update", "success", {
            "actor": actor.get("username", "admin"),
            "active_style": payload.active_style,
            "custom_characters": sum(len(getattr(payload, key)) for key in ("trading_system", "trading_user", "evolution_system", "evolution_user"))
        })
        return {"saved": True, "active_style": payload.active_style, "restart_note": "下一次 Python 交易主脑与自进化进程自动读取选中风格。"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新提示词库失败: {exc}")


@router.get("/api/v1/admin/prompt-profiles")
def prompt_profiles(x_r20_session: str | None = Header(default=None, alias="X-R20-Session"), x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token, x_r20_session)
    try:
        library = load_library()
        prompts_mod = __import__("scripts.prompt_library", fromlist=["ALLOWED_VARIABLES", "TEMPLATE_VARIABLES_METADATA"])
        return {
            "active_profile_id": library["active_profile_id"],
            "profiles": all_profiles(),
            "allowed_variables": sorted(list(prompts_mod.ALLOWED_VARIABLES)),
            "template_variables": prompts_mod.TEMPLATE_VARIABLES_METADATA,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取提示词方案列表失败: {exc}")


@router.post("/api/v1/admin/prompt-profiles")
def create_prompt_profile_api(
    payload: PromptProfileCreateRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        profile = create_profile(payload.name, payload.description, payload.source_id)
        audit_record("prompt.profile.create", "success", {"actor": actor["username"], "profile_id": profile["id"]})
        return {"profile": profile}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"创建提示词方案失败: {exc}") from exc


@router.put("/api/v1/admin/prompt-profiles/{profile_id}")
def update_prompt_profile_api(
    profile_id: str,
    payload: PromptProfileUpdateRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if not profile_id or not re.match(r"^[a-zA-Z0-9_-]+$", profile_id):
        raise HTTPException(status_code=400, detail=f"无效的提示词方案标识: {profile_id}")
    changes = {k: v for k, v in payload.model_dump(exclude={"note"}, exclude_unset=True).items() if v is not None}
    try:
        profile = update_profile(profile_id, changes, payload.note)
        audit_record("prompt.profile.update", "success", {"actor": actor["username"], "profile_id": profile_id})
        return {"profile": profile, "validation": validate_profile(profile)}
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新提示词方案失败: {exc}") from exc


@router.post("/api/v1/admin/prompt-profiles/{profile_id}/activate")
def activate_prompt_profile_api(
    profile_id: str,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if not profile_id or not re.match(r"^[a-zA-Z0-9_-]+$", profile_id):
        raise HTTPException(status_code=400, detail=f"无效的提示词方案标识: {profile_id}")
    try:
        profile = activate_profile(profile_id)
        audit_record("prompt.profile.activate", "success", {"actor": actor["username"], "profile_id": profile_id})
        return {"active_profile_id": profile_id, "profile": profile}
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启用提示词方案失败: {exc}") from exc


@router.delete("/api/v1/admin/prompt-profiles/{profile_id}")
def delete_prompt_profile_api(
    profile_id: str,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if not profile_id or not re.match(r"^[a-zA-Z0-9_-]+$", profile_id):
        raise HTTPException(status_code=400, detail=f"无效的提示词方案标识: {profile_id}")
    try:
        delete_profile(profile_id)
        audit_record("prompt.profile.delete", "success", {"actor": actor["username"], "profile_id": profile_id})
        return {"deleted": True}
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"删除提示词方案失败: {exc}") from exc


@router.post("/api/v1/admin/prompt-profiles/validate")
def validate_prompt_profile_api(
    payload: PromptProfileUpdateRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token, x_r20_session)
    try:
        return validate_profile({k: v for k, v in payload.model_dump(exclude={"note"}).items() if v is not None})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"提示词方案校验失败: {exc}") from exc


@router.get("/api/v1/admin/prompt-profiles/{profile_id}/history")
def prompt_profile_history_api(
    profile_id: str,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token, x_r20_session)
    if not profile_id or not re.match(r"^[a-zA-Z0-9_-]+$", profile_id):
        raise HTTPException(status_code=400, detail=f"无效的提示词方案标识: {profile_id}")
    try:
        return {"history": profile_history(profile_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取方案历史失败: {exc}") from exc


@router.post("/api/v1/admin/prompt-profiles/{profile_id}/rollback")
def rollback_prompt_profile_api(
    profile_id: str,
    payload: PromptRollbackRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if not profile_id or not re.match(r"^[a-zA-Z0-9_-]+$", profile_id):
        raise HTTPException(status_code=400, detail=f"无效的提示词方案标识: {profile_id}")
    try:
        profile = rollback_profile(profile_id, payload.revision_id)
        audit_record("prompt.profile.rollback", "success", {"actor": actor["username"], "profile_id": profile_id, "revision_id": payload.revision_id})
        return {"profile": profile}
    except ValueError as exc:
        if "不存在" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"回滚提示词方案失败: {exc}") from exc


@router.get("/api/v1/admin/prompt-profiles/{profile_id}/export")
def export_prompt_profile_api(
    profile_id: str,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token, x_r20_session)
    if not profile_id or not re.match(r"^[a-zA-Z0-9_-]+$", profile_id):
        raise HTTPException(status_code=400, detail=f"无效的提示词方案标识: {profile_id}")
    try:
        return export_profile(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导出提示词方案失败: {exc}") from exc


@router.post("/api/v1/admin/prompt-profiles/import")
def import_prompt_profile_api(
    payload: PromptImportRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        profile = import_profile(payload.payload, payload.name_override)
        audit_record("prompt.profile.import", "success", {"actor": actor["username"], "profile_id": profile["id"]})
        return {"profile": profile}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"导入提示词方案失败: {exc}") from exc


@router.get("/api/v1/admin/prompts")
def prompt_override(
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    try:
        from scripts.ai_brain_trader import SYSTEM_PROMPT, get_effective_system_prompt
        content = PROMPT_OVERRIDE_FILE.read_text(encoding="utf-8") if PROMPT_OVERRIDE_FILE.exists() else ""
        # 审计 P1-3：这里必须与推演时**同一条代码路径**（模块布局 → 之后追加覆盖层）。
        # 旧实现返回 SYSTEM_PROMPT + 覆盖层，而推演侧布局会把覆盖层丢掉 —— 接口在骗人。
        effective = get_effective_system_prompt()
        return {
            "content": content,
            "enabled": bool(content.strip()),
            "base_prompt": SYSTEM_PROMPT,
            "effective_prompt": effective,
            "override_applied": bool(content.strip()) and content.strip() in effective,
            "path": str(PROMPT_OVERRIDE_FILE),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取提示词覆盖配置失败: {exc}")


@router.put("/api/v1/admin/prompts")
def update_prompt_override(
    payload: PromptOverrideRequest,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
    x_r20_admin_token: str | None = Header(default=None)
) -> dict[str, Any]:
    refresh_settings()
    actor = require_superadmin(x_r20_session)
    try:
        content = payload.content.strip()
        if content:
            temp = PROMPT_OVERRIDE_FILE.with_suffix(".tmp")
            temp.write_text(content + "\n", encoding="utf-8")
            os.replace(temp, PROMPT_OVERRIDE_FILE)
        elif PROMPT_OVERRIDE_FILE.exists():
            PROMPT_OVERRIDE_FILE.unlink()
        audit_record("prompt.update", "success", {
            "actor": actor.get("username", "admin"),
            "enabled": bool(content),
            "characters": len(content)
        })
        return {"saved": True, "enabled": bool(content), "restart_note": "下一次 AI 推演循环将自动叠加此提示词覆盖层。"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新提示词覆盖失败: {exc}")


# =========================================================================
# AI 记忆心法 API：唯一定义在 r20_backend/app.py（test_self_evolution_safety 与
# test_memory_routes_isolated 以 app.py 源码为 AST 契约，且其路由注册先于本 router，
# 拆分时误留的同实现死副本已于 2026-09-13 移除——再在此处添加将成死代码并触发
# FastAPI 重复 Operation ID 告警）。
