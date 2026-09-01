"""Versioned custom backup jobs for the R20 disaster-recovery runtime."""
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
CONFIG_FILE = ROOT / "data" / "backup_methods.json"
BJ_TZ = timezone(timedelta(hours=8))
MAX_JOBS = 12
ALLOWED_SCOPES = {"data", "scripts", "dashboard", "r20_backend", "r20_gateway", "tests", "recovery_guide", "agent_profile", "root_configs"}
ALLOWED_TARGETS = {"baidu", "local"}
DEFAULT_CONFIG = {
    "baidu": {"enabled": True, "label": "百度网盘全量灾备", "retention": 0},
    "local": {"enabled": False, "label": "本地滚动全量归档", "retention": 3},
    "sqlite": {"enabled": False, "label": "SQLite 热备快照", "retention": 7},
}
DEFAULT_EXCLUDES = [".git/**", ".env", ".okx/**", "backups/**", "logs/**", "**/__pycache__/**", "*.pyc", "data/r20_admin.db*", "data/*.db-wal", "data/*.db-shm"]
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def _now() -> str:
    return datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _default_job() -> dict[str, Any]:
    return {
        "id": "nightly-default", "name": "每日全系统灾备", "description": "兼容原北京时间 02:00 灾备流程。", "enabled": True,
        "schedule_times": ["02:00"], "timezone": "Asia/Shanghai", "scope": ["data", "scripts", "dashboard", "r20_backend", "r20_gateway", "recovery_guide", "agent_profile"],
        "exclude": list(DEFAULT_EXCLUDES), "pre_backup_sync": True, "compression_level": 6, "checksum": "sha256",
        "encryption": {"enabled": False, "key_env": "R20_BACKUP_ENCRYPTION_KEY"},
        "sqlite": {"enabled": False, "retention": 7},
        "targets": [
            {"id": "baidu-default", "type": "baidu", "enabled": True, "remote_path": "R20_Backups", "retention": 0, "retries": 3},
            {"id": "local-default", "type": "local", "enabled": False, "path": "backups/local", "retention": 3, "retries": 1},
        ],
        "cleanup_local_on_success": True, "notify_on_success": True, "notify_on_failure": True,
        "created_at": _now(), "updated_at": _now(),
    }


def _default() -> dict[str, Any]:
    return {"version": 2, "jobs": [_default_job()]}


def _atomic_write(payload: dict[str, Any]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".backup-jobs-", suffix=".tmp", dir=CONFIG_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(temp_path, CONFIG_FILE); os.chmod(CONFIG_FILE, 0o600)
    finally:
        if os.path.exists(temp_path): os.unlink(temp_path)


def _normalize_target(raw: dict[str, Any]) -> dict[str, Any]:
    target_type = str(raw.get("type") or "local")
    return {
        "id": str(raw.get("id") or f"target-{uuid.uuid4().hex[:10]}"), "type": target_type, "enabled": bool(raw.get("enabled", True)),
        "remote_path": str(raw.get("remote_path") or "R20_Backups").strip()[:240], "path": str(raw.get("path") or "backups/local").strip()[:240],
        "retention": max(0, min(int(raw.get("retention", 3)), 365)), "retries": max(1, min(int(raw.get("retries", 3)), 10)),
    }


def _normalize_job(raw: dict[str, Any]) -> dict[str, Any]:
    base = _default_job(); base.update({k: v for k, v in raw.items() if k in base})
    base["id"] = str(raw.get("id") or f"backup-{uuid.uuid4().hex[:10]}")
    base["name"] = str(raw.get("name") or "自定义灾备任务").strip()[:80]
    base["description"] = str(raw.get("description") or "").strip()[:300]
    base["enabled"] = bool(raw.get("enabled", True)); base["timezone"] = "Asia/Shanghai"
    times = raw.get("schedule_times") if isinstance(raw.get("schedule_times"), list) else [raw.get("schedule_time", "02:00")]
    base["schedule_times"] = sorted(set(str(x) for x in times if TIME_RE.fullmatch(str(x)))) or ["02:00"]
    base["scope"] = [str(x) for x in raw.get("scope", base["scope"]) if str(x) in ALLOWED_SCOPES]
    base["exclude"] = [str(x).strip() for x in raw.get("exclude", base["exclude"]) if str(x).strip()][:100]
    base["compression_level"] = max(1, min(int(raw.get("compression_level", 6)), 9)); base["checksum"] = "sha256"
    encryption = raw.get("encryption") if isinstance(raw.get("encryption"), dict) else {}
    base["encryption"] = {"enabled": bool(encryption.get("enabled", False)), "key_env": str(encryption.get("key_env") or "R20_BACKUP_ENCRYPTION_KEY").strip()}
    sqlite = raw.get("sqlite") if isinstance(raw.get("sqlite"), dict) else {}
    base["sqlite"] = {"enabled": bool(sqlite.get("enabled", False)), "retention": max(1, min(int(sqlite.get("retention", 7)), 365))}
    base["targets"] = [_normalize_target(x) for x in raw.get("targets", []) if isinstance(x, dict) and str(x.get("type")) in ALLOWED_TARGETS]
    base["pre_backup_sync"] = bool(raw.get("pre_backup_sync", True)); base["cleanup_local_on_success"] = bool(raw.get("cleanup_local_on_success", True))
    base["notify_on_success"] = bool(raw.get("notify_on_success", True)); base["notify_on_failure"] = bool(raw.get("notify_on_failure", True))
    base["created_at"] = str(raw.get("created_at") or _now()); base["updated_at"] = str(raw.get("updated_at") or _now())
    return base


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    if int(raw.get("version", 1)) >= 2 and isinstance(raw.get("jobs"), list):
        return {"version": 2, "jobs": [_normalize_job(x) for x in raw["jobs"] if isinstance(x, dict)][:MAX_JOBS]}
    job = _default_job()
    methods = copy.deepcopy(DEFAULT_CONFIG)
    for key in methods:
        if isinstance(raw.get(key), dict): methods[key].update(raw[key])
    job["sqlite"] = {"enabled": bool(methods["sqlite"]["enabled"]), "retention": int(methods["sqlite"]["retention"])}
    for target in job["targets"]:
        old = methods[target["type"]]
        target["enabled"] = bool(old["enabled"]); target["retention"] = int(old["retention"])
    return {"version": 2, "jobs": [job]}


def load_backup_config() -> dict[str, Any]:
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8")); return _migrate(raw if isinstance(raw, dict) else {})
    except (OSError, json.JSONDecodeError, ValueError): return _default()


def save_backup_config(payload: dict[str, Any]) -> None:
    jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
    if not jobs: raise ValueError("至少保留一个灾备任务")
    if len(jobs) > MAX_JOBS: raise ValueError(f"灾备任务最多 {MAX_JOBS} 个")
    normalized = {"version": 2, "jobs": [_normalize_job(x) for x in jobs]}
    for job in normalized["jobs"]: validate_backup_job(job, raise_error=True)
    _atomic_write(normalized)


def validate_backup_job(job: dict[str, Any], raise_error: bool = False) -> dict[str, Any]:
    errors: list[str] = []; warnings: list[str] = []
    if not str(job.get("name") or "").strip(): errors.append("任务名称不能为空")
    if not job.get("scope") and not job.get("sqlite", {}).get("enabled"): errors.append("至少选择一个文件范围或启用 SQLite 热备")
    enabled_targets = [x for x in job.get("targets", []) if x.get("enabled")]
    if not enabled_targets and not job.get("sqlite", {}).get("enabled"): errors.append("至少启用一个备份目标或 SQLite 热备")
    enc = job.get("encryption", {})
    if enc.get("enabled") and not ENV_RE.fullmatch(str(enc.get("key_env") or "")): errors.append("加密密钥环境变量名称无效")
    for target in job.get("targets", []):
        if target.get("type") == "local":
            candidate = (ROOT / str(target.get("path") or "")).resolve()
            if not candidate.is_relative_to((ROOT / "backups").resolve()): errors.append("本地目标必须位于项目 backups/ 目录内")
        if target.get("type") == "baidu" and ".." in Path(str(target.get("remote_path") or "")).parts: errors.append("百度网盘路径不能包含 ..")
    if enc.get("enabled") and not os.getenv(str(enc.get("key_env") or "")): warnings.append("加密密钥环境变量尚未配置，任务运行时将 Fail-Closed")
    result = {"valid": not errors, "errors": list(dict.fromkeys(errors)), "warnings": warnings}
    if raise_error and errors: raise ValueError("；".join(result["errors"]))
    return result


def list_jobs() -> list[dict[str, Any]]: return copy.deepcopy(load_backup_config()["jobs"])


def get_job(job_id: str) -> dict[str, Any]:
    job = next((x for x in list_jobs() if x["id"] == job_id), None)
    if not job: raise ValueError("灾备任务不存在")
    return job


def create_job(name: str, source_id: str = "nightly-default") -> dict[str, Any]:
    config = load_backup_config()
    if len(config["jobs"]) >= MAX_JOBS: raise ValueError(f"灾备任务最多 {MAX_JOBS} 个")
    try: source = get_job(source_id)
    except ValueError: source = _default_job()
    job = _normalize_job({**source, "id": f"backup-{uuid.uuid4().hex[:10]}", "name": name, "enabled": False, "created_at": _now(), "updated_at": _now()})
    config["jobs"].append(job); save_backup_config(config); return job


def update_job(job_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    config = load_backup_config(); index = next((i for i,x in enumerate(config["jobs"]) if x["id"] == job_id), None)
    if index is None: raise ValueError("灾备任务不存在")
    job = _normalize_job({**config["jobs"][index], **changes, "id": job_id, "updated_at": _now()})
    validate_backup_job(job, raise_error=True); config["jobs"][index] = job; save_backup_config(config); return job


def delete_job(job_id: str) -> None:
    config = load_backup_config()
    if len(config["jobs"]) <= 1: raise ValueError("至少保留一个灾备任务")
    config["jobs"] = [x for x in config["jobs"] if x["id"] != job_id]
    save_backup_config(config)


def jobs_due_at(hhmm: str) -> list[dict[str, Any]]:
    return [x for x in list_jobs() if x.get("enabled") and hhmm in x.get("schedule_times", [])]


def export_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    safe = copy.deepcopy(job)
    safe["id"] = ""; safe["enabled"] = False; safe["created_at"] = ""; safe["updated_at"] = ""
    # Only the environment variable name is exported; no secret value ever enters config.
    return {"format": "r20-backup-job", "version": 1, "exported_at": _now(), "job": safe}


def import_job(payload: dict[str, Any], name_override: str = "") -> dict[str, Any]:
    if payload.get("format") != "r20-backup-job" or not isinstance(payload.get("job"), dict): raise ValueError("无效的 R20 灾备任务文件")
    config = load_backup_config()
    if len(config["jobs"]) >= MAX_JOBS: raise ValueError(f"灾备任务最多 {MAX_JOBS} 个")
    raw = copy.deepcopy(payload["job"]); raw["id"] = f"backup-{uuid.uuid4().hex[:10]}"; raw["name"] = name_override or str(raw.get("name") or "导入灾备任务"); raw["enabled"] = False; raw["created_at"] = _now(); raw["updated_at"] = _now()
    job = _normalize_job(raw); validate_backup_job(job, raise_error=True); config["jobs"].append(job); save_backup_config(config); return job


# Backward compatibility for the original three-switch API and runtime.
def load_backup_methods() -> dict[str, Any]:
    job = list_jobs()[0]
    targets = {x["type"]: x for x in job["targets"]}
    return {
        "baidu": {"enabled": bool(targets.get("baidu", {}).get("enabled")), "label": "百度网盘全量灾备", "retention": int(targets.get("baidu", {}).get("retention", 0))},
        "local": {"enabled": bool(targets.get("local", {}).get("enabled")), "label": "本地滚动全量归档", "retention": int(targets.get("local", {}).get("retention", 3))},
        "sqlite": {"enabled": bool(job["sqlite"]["enabled"]), "label": "SQLite 热备快照", "retention": int(job["sqlite"]["retention"])},
    }


def save_backup_methods(methods: dict[str, Any]) -> None:
    job = list_jobs()[0]; targets = {x["type"]: x for x in job["targets"]}
    for target_type in ("baidu", "local"):
        if target_type in methods:
            targets[target_type]["enabled"] = bool(methods[target_type].get("enabled", targets[target_type]["enabled"]))
            targets[target_type]["retention"] = max(0, min(int(methods[target_type].get("retention", targets[target_type]["retention"])), 365))
    if "sqlite" in methods:
        job["sqlite"] = {"enabled": bool(methods["sqlite"].get("enabled", job["sqlite"]["enabled"])), "retention": max(1, min(int(methods["sqlite"].get("retention", job["sqlite"]["retention"])), 365))}
    job["targets"] = list(targets.values()); update_job(job["id"], job)
