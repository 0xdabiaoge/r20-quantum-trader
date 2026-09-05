"""Unified Policy Snapshot generator and immutable decision tracer.

Four Strategy Units:
1. Prompt Library & Layout (Profile ID, Profile Name, Layout Hash, Editor Mode)
2. Structured Self-Evolution Mind (Version hash, Enabled lessons count, Total lessons)
3. Physical Risk Interceptor Plugins (Pipeline order, Filename hashes, Enabled plugins)
4. Multi-Agent Model Council (Enabled, Consensus mode, Active roles & bound models)

Generates a deterministic immutable policy snapshot fingerprint:
- policy_hash: 8-hex sha256
- policy_version: e.g. "v7.3.0@3f8a1c9e"
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_VERSION = "v7.3.0"


def compute_layout_hash(profile: Dict[str, Any]) -> str:
    """Computes a deterministic hash of the prompt profile layout and module contents."""
    if not isinstance(profile, dict):
        return "empty"

    summary_parts: List[str] = [
        str(profile.get("id", "")).strip(),
        str(profile.get("name", "")).strip(),
        str(profile.get("editor_mode", "")).strip(),
    ]

    pipelines = profile.get("pipelines")
    pipeline_keys = ("trading_system", "trading_user", "evolution_system", "evolution_user")
    has_pipeline_modules = (
        isinstance(pipelines, dict)
        and any(isinstance(pipelines.get(k), list) and len(pipelines[k]) > 0 for k in pipeline_keys)
    )

    if has_pipeline_modules and isinstance(pipelines, dict):
        for key in pipeline_keys:
            mods = pipelines.get(key) or []
            if isinstance(mods, list):
                for m in mods:
                    if isinstance(m, dict):
                        m_id = str(m.get("id", "")).strip()
                        m_enabled = "1" if m.get("enabled", True) else "0"
                        m_content = str(m.get("content", "")).strip()
                        c_hash = hashlib.sha256(m_content.encode("utf-8")).hexdigest()[:8]
                        summary_parts.append(f"{key}:{m_id}:{m_enabled}:{c_hash}")
    else:
        for key in pipeline_keys:
            val = str(profile.get(key, "")).strip()
            if val:
                c_hash = hashlib.sha256(val.encode("utf-8")).hexdigest()[:8]
                summary_parts.append(f"{key}:{c_hash}")
        simple_policy = profile.get("simple_policy")
        if isinstance(simple_policy, dict):
            sp_dump = json.dumps(simple_policy, sort_keys=True)
            sp_hash = hashlib.sha256(sp_dump.encode("utf-8")).hexdigest()[:8]
            summary_parts.append(f"sp:{sp_hash}")

    canon_str = "|".join(summary_parts)
    return hashlib.sha256(canon_str.encode("utf-8")).hexdigest()[:8]


def extract_prompt_profile_fingerprint(
    profile: Optional[Dict[str, Any]] = None,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extracts immutable fingerprint of the currently active prompt profile."""
    prof = profile
    if prof is None:
        try:
            sys_path_added = False
            scripts_dir = str((root_dir or ROOT) / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
                sys_path_added = True
            from prompt_library import active_profile
            prof = active_profile()
        except Exception:
            prof = {
                "id": "stable",
                "name": "全维度波段强化版",
                "editor_mode": "modules",
            }
        finally:
            if sys_path_added and scripts_dir in sys.path:
                try:
                    sys.path.remove(scripts_dir)
                except ValueError:
                    pass

    p_id = str(prof.get("id", "stable"))
    p_name = str(prof.get("name", "全维度波段强化版"))
    editor_mode = str(prof.get("editor_mode", "modules"))
    layout_hash = compute_layout_hash(prof)

    return {
        "active_profile_id": p_id,
        "active_profile_name": p_name,
        "editor_mode": editor_mode,
        "layout_hash": layout_hash,
    }


def extract_evolution_mind_fingerprint(
    memory_snapshot: Optional[Dict[str, Any]] = None,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extracts immutable fingerprint of the structured self-evolution mind."""
    snap = memory_snapshot
    if snap is None:
        try:
            sys_path_added = False
            scripts_dir = str((root_dir or ROOT) / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
                sys_path_added = True
            from evolution_shield import read_memory_snapshot
            snap = read_memory_snapshot()
        except Exception:
            snap = {"exists": False, "version": "missing", "lessons": []}
        finally:
            if sys_path_added and scripts_dir in sys.path:
                try:
                    sys.path.remove(scripts_dir)
                except ValueError:
                    pass

    version = str(snap.get("version", "missing"))
    lessons = snap.get("lessons") or []
    if not isinstance(lessons, list):
        lessons = []
    enabled_count = len([l for l in lessons if isinstance(l, dict) and l.get("enabled", True)])
    total_count = len(lessons)

    return {
        "version": version,
        "enabled_count": enabled_count,
        "total_count": total_count,
    }


def extract_interceptors_fingerprint(
    plugins: Optional[List[Dict[str, Any]]] = None,
    plugins_dir: Optional[Path] = None,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extracts immutable fingerprint of enabled physical risk interceptor plugins."""
    raw_plugins = plugins
    p_dir = plugins_dir or ((root_dir or ROOT) / "plugins" / "interceptors")

    if raw_plugins is None:
        try:
            from r20_backend.interceptor_manager import list_plugins
            raw_plugins = list_plugins(create_if_missing=False)
        except Exception:
            raw_plugins = []

    if not isinstance(raw_plugins, list):
        raw_plugins = []

    enabled_list = [p for p in raw_plugins if isinstance(p, dict) and p.get("enabled", True)]
    pipeline_info: List[Dict[str, Any]] = []

    for idx, p in enumerate(enabled_list):
        fn = str(p.get("filename", f"plugin_{idx}.py"))
        if p.get("file_hash"):
            fh = str(p["file_hash"])[:8]
        elif p.get("code"):
            fh = hashlib.sha256(str(p["code"]).encode("utf-8")).hexdigest()[:8]
        else:
            fp = p_dir / fn if fn else None
            if fp and fp.is_file():
                try:
                    fh = hashlib.sha256(fp.read_bytes()).hexdigest()[:8]
                except Exception:
                    fh = "error"
            else:
                fh = "missing"
        pipeline_info.append({
            "order": idx,
            "filename": fn,
            "file_hash": fh,
        })

    raw_hash_str = "|".join(f"{item['order']}:{item['filename']}:{item['file_hash']}" for item in pipeline_info)
    plugins_hash = hashlib.sha256(raw_hash_str.encode("utf-8")).hexdigest()[:8]

    return {
        "plugins_hash": plugins_hash,
        "enabled_count": len(enabled_list),
        "total_count": len(raw_plugins),
        "enabled_plugins": [item["filename"] for item in pipeline_info],
        "pipeline": pipeline_info,
    }


def extract_council_fingerprint(
    council_cfg: Optional[Dict[str, Any]] = None,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Extracts immutable fingerprint of the multi-agent council configuration."""
    c_cfg = council_cfg
    if c_cfg is None:
        try:
            from r20_backend.council_manager import load_council_config
            c_cfg = load_council_config()
        except Exception:
            c_cfg = {"enabled": False, "consensus_mode": "standard", "roles": {}}

    if not isinstance(c_cfg, dict):
        c_cfg = {"enabled": False, "consensus_mode": "standard", "roles": {}}

    enabled = bool(c_cfg.get("enabled", False))
    mode = str(c_cfg.get("consensus_mode", "standard")).strip().lower()
    roles = c_cfg.get("roles") or {}
    if not isinstance(roles, dict):
        roles = {}

    active_roles = sorted([
        r_id for r_id, r in roles.items()
        if isinstance(r, dict) and r.get("enabled", True)
    ])
    role_models = {
        r_id: str(roles[r_id].get("model_id", "") or "")
        for r_id in active_roles
    }

    canon_council = json.dumps(
        {
            "enabled": enabled,
            "consensus_mode": mode,
            "active_roles": active_roles,
            "role_models": role_models,
        },
        sort_keys=True,
    )
    council_hash = hashlib.sha256(canon_council.encode("utf-8")).hexdigest()[:8]

    return {
        "enabled": enabled,
        "consensus_mode": mode,
        "active_roles": active_roles,
        "role_models": role_models,
        "council_hash": council_hash,
    }


def generate_policy_snapshot(
    *,
    root_dir: Optional[Path] = None,
    prompt_profile: Optional[Dict[str, Any]] = None,
    memory_snapshot: Optional[Dict[str, Any]] = None,
    interceptor_plugins: Optional[List[Dict[str, Any]]] = None,
    council_config: Optional[Dict[str, Any]] = None,
    plugins_dir: Optional[Path] = None,
    base_version: str = DEFAULT_BASE_VERSION,
) -> Dict[str, Any]:
    """Generates an immutable snapshot fingerprint across the 4 core strategy units.

    Deterministic hashing ensures that any change in prompt layout, evolution lessons,
    interceptor plugins, or council configuration produces a unique policy_hash and policy_version.
    """
    prompt_info = extract_prompt_profile_fingerprint(prompt_profile, root_dir=root_dir)
    evolution_info = extract_evolution_mind_fingerprint(memory_snapshot, root_dir=root_dir)
    interceptor_info = extract_interceptors_fingerprint(
        interceptor_plugins, plugins_dir=plugins_dir, root_dir=root_dir
    )
    council_info = extract_council_fingerprint(council_config, root_dir=root_dir)

    canonical_fingerprint = {
        "prompt_profile": {
            "id": prompt_info["active_profile_id"],
            "layout_hash": prompt_info["layout_hash"],
            "editor_mode": prompt_info["editor_mode"],
        },
        "evolution_mind": {
            "version": evolution_info["version"],
            "enabled_count": evolution_info["enabled_count"],
        },
        "physical_interceptors": {
            "plugins_hash": interceptor_info["plugins_hash"],
            "enabled_plugins": interceptor_info["enabled_plugins"],
        },
        "model_council": {
            "enabled": council_info["enabled"],
            "consensus_mode": council_info["consensus_mode"],
            "active_roles": council_info["active_roles"],
            "role_models": council_info["role_models"],
        },
    }

    canon_bytes = json.dumps(canonical_fingerprint, sort_keys=True, separators=(",", ":")).encode("utf-8")
    policy_hash = hashlib.sha256(canon_bytes).hexdigest()[:8]
    policy_version = f"{base_version}@{policy_hash}"

    mind_ver_short = evolution_info["version"][:8] if evolution_info["version"] != "missing" else "missing"
    summary = (
        f"Policy[{policy_version}] "
        f"prompt:{prompt_info['active_profile_id']}#{prompt_info['layout_hash']} "
        f"mind:{mind_ver_short}({evolution_info['enabled_count']}) "
        f"interceptors:{interceptor_info['plugins_hash']}({interceptor_info['enabled_count']}) "
        f"council:{'on' if council_info['enabled'] else 'off'}({council_info['consensus_mode']})"
    )

    return {
        "policy_version": policy_version,
        "policy_hash": policy_hash,
        "base_version": base_version,
        "timestamp": int(time.time()),
        "summary": summary,
        "units": {
            "prompt_profile": prompt_info,
            "evolution_mind": evolution_info,
            "physical_interceptors": interceptor_info,
            "model_council": council_info,
        },
    }


def get_current_policy_snapshot() -> Dict[str, Any]:
    """Convenience accessor for live current policy snapshot."""
    return generate_policy_snapshot()


def format_policy_snapshot_summary(snapshot: Dict[str, Any]) -> str:
    """Formats a concise single-line summary of a policy snapshot."""
    return str(snapshot.get("summary") or snapshot.get("policy_version") or "unknown_policy")
