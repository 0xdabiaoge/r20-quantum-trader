"""Custom R20 backup job runtime: archive, encrypt, verify, deliver and retain."""
from __future__ import annotations
import base64
import fnmatch
import hashlib
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"
LOCAL_DIR = BACKUPS / "local"
SQLITE_DIR = BACKUPS / "sqlite"
MANIFEST_DIR = BACKUPS / "manifests"
BJ_TZ = timezone(timedelta(hours=8))
MAGIC = b"R20GCM2\x00"
MANDATORY_EXCLUDES = (".git/**", ".env", ".okx/**", "backups/**", "logs/**", "data/r20_admin.db*", "data/*.db-wal", "data/*.db-shm", "**/__pycache__/**", "*.pyc")
SCOPE_PATHS = {
    "data": ("data",), "scripts": ("scripts",), "dashboard": ("dashboard",), "r20_backend": ("r20_backend",), "r20_gateway": ("r20_gateway",),
    "tests": ("tests",), "recovery_guide": ("RECOVERY_GUIDE.md",), "agent_profile": ("SOUL.md", "PROFILE.md", "AGENTS.md", "MEMORY.md"),
    "root_configs": ("README.md", "requirements.txt", "pyproject.toml", "docker-compose.yml", "Dockerfile", ".gitignore"),
}


def prune(paths: Iterable[Path], retention: int) -> None:
    items = sorted((path for path in paths if path.exists()), key=lambda p: p.stat().st_mtime, reverse=True)
    for item in items[max(0, retention):]: item.unlink(missing_ok=True)


def retain_local_archive(source: Path, retention: int, destination_dir: Path | None = None) -> Path:
    destination_dir = destination_dir or LOCAL_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    shutil.copy2(source, destination)
    prune(destination_dir.glob("r20_backup_*"), retention)
    return destination


def sqlite_hot_backups(timestamp: str, retention: int, destination_dir: Path | None = None) -> list[Path]:
    destination_dir = destination_dir or SQLITE_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for source in (ROOT / "data").glob("*.db"):
        if source.name == "r20_admin.db": continue
        destination = destination_dir / f"{source.stem}_{timestamp}.db"
        source_conn = sqlite3.connect(source)
        try:
            target_conn = sqlite3.connect(destination)
            try: source_conn.backup(target_conn)
            finally: target_conn.close()
        finally: source_conn.close()
        os.chmod(destination, 0o600); created.append(destination)
    prune(destination_dir.glob("*.db"), retention)
    return created


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _excluded(relative: str, patterns: list[str]) -> bool:
    rel = relative.replace(os.sep, "/").lstrip("./")
    return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(f"{rel}/", pattern) for pattern in [*MANDATORY_EXCLUDES, *patterns])


def _tar_filter(patterns: list[str]):
    def filter_info(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        return None if _excluded(info.name, patterns) else info
    return filter_info


def create_archive(job: dict[str, Any], timestamp: str) -> tuple[Path, list[str]]:
    staging = BACKUPS / "staging"; staging.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in str(job["id"]) if c.isalnum() or c in "-_")[:48]
    path = staging / f"r20_backup_{safe_id}_{timestamp}.tar.gz"
    included: list[str] = []
    with tarfile.open(path, "w:gz", compresslevel=int(job.get("compression_level", 6))) as archive:
        for scope in job.get("scope", []):
            for relative in SCOPE_PATHS.get(scope, ()):
                source = ROOT / relative
                if source.exists() and not _excluded(relative, job.get("exclude", [])):
                    archive.add(source, arcname=relative, recursive=True, filter=_tar_filter(job.get("exclude", []))); included.append(relative)
    if not included:
        path.unlink(missing_ok=True); raise RuntimeError("所选范围没有可归档文件")
    os.chmod(path, 0o600)
    return path, included


def _derive_key(secret: str, salt: bytes) -> bytes:
    if len(secret) < 16: raise RuntimeError("备份加密密钥至少 16 个字符")
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=32 * 1024 * 1024)


def encrypt_archive(source: Path, key_env: str) -> Path:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    secret = os.getenv(key_env, "")
    if not secret: raise RuntimeError(f"加密已启用但环境变量 {key_env} 未配置")
    salt = os.urandom(16); nonce = os.urandom(12); key = _derive_key(secret, salt); target = source.with_suffix(source.suffix + ".aes256")
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    with source.open("rb") as inp, target.open("wb+") as out:
        out.write(MAGIC); out.write(salt); out.write(nonce); out.write(b"\x00" * 16)
        for chunk in iter(lambda: inp.read(1024 * 1024), b""): out.write(encryptor.update(chunk))
        out.write(encryptor.finalize()); out.seek(len(MAGIC) + len(salt) + len(nonce)); out.write(encryptor.tag)
        out.flush(); os.fsync(out.fileno())
    os.chmod(target, 0o600); source.unlink(missing_ok=True); return target


def decrypt_archive(source: Path, key_env: str, destination: Path) -> Path:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    secret = os.getenv(key_env, "")
    if not secret: raise RuntimeError(f"解密需要环境变量 {key_env}")
    with source.open("rb") as inp:
        if inp.read(len(MAGIC)) != MAGIC: raise RuntimeError("不是受支持的 R20 AES-256-GCM 归档")
        salt, nonce, tag = inp.read(16), inp.read(12), inp.read(16)
        if len(salt) != 16 or len(nonce) != 12 or len(tag) != 16: raise RuntimeError("加密归档头损坏")
        decryptor = Cipher(algorithms.AES(_derive_key(secret, salt)), modes.GCM(nonce, tag)).decryptor()
        with destination.open("wb") as out:
            for chunk in iter(lambda: inp.read(1024 * 1024), b""): out.write(decryptor.update(chunk))
            out.write(decryptor.finalize()); out.flush(); os.fsync(out.fileno())
    os.chmod(destination, 0o600); return destination


def verify_archive(path: Path, expected_sha256: str = "", key_env: str = "") -> dict[str, Any]:
    if not path.exists(): raise RuntimeError("归档文件不存在")
    checksum = calculate_sha256(path)
    if expected_sha256 and checksum != expected_sha256: raise RuntimeError("SHA256 校验失败")
    temp: Path | None = None; tar_path = path
    try:
        if path.name.endswith(".aes256"):
            fd, temp_name = tempfile.mkstemp(prefix="r20-verify-", suffix=".tar.gz", dir=BACKUPS)
            os.close(fd); temp = Path(temp_name); tar_path = decrypt_archive(path, key_env, temp)
        with tarfile.open(tar_path, "r:gz") as archive:
            members = archive.getmembers()
            unsafe = [m.name for m in members if Path(m.name).is_absolute() or ".." in Path(m.name).parts]
            if unsafe: raise RuntimeError(f"归档包含不安全路径：{unsafe[0]}")
            roots = sorted({Path(m.name).parts[0] for m in members if Path(m.name).parts})
        return {"valid": True, "sha256": checksum, "members": len(members), "roots": roots, "encrypted": path.name.endswith(".aes256")}
    finally:
        if temp: temp.unlink(missing_ok=True)


def upload_baidu(source: Path, remote_path: str, retries: int) -> dict[str, Any]:
    import bypy
    remote = "/".join(part for part in Path(remote_path).parts if part not in {"/", "."})
    destination = f"{remote}/{source.name}" if remote else source.name
    last = ""
    for attempt in range(1, retries + 1):
        try:
            code = bypy.ByPy().upload(str(source), destination)
            if code == 0: return {"success": True, "attempts": attempt, "destination": f"/apps/bypy/{destination}"}
            last = f"ByPy 返回 {code}"
        except Exception as exc: last = f"{type(exc).__name__}: {exc}"
        if attempt < retries: time.sleep(min(attempt * 5, 30))
    return {"success": False, "attempts": retries, "destination": destination, "error": last}


def run_backup_job(job: dict[str, Any]) -> dict[str, Any]:
    started = datetime.now(BJ_TZ); stamp = started.strftime("%Y%m%d_%H%M%S")
    result: dict[str, Any] = {"job_id": job["id"], "job_name": job["name"], "started_at": started.strftime("%Y-%m-%d %H:%M:%S"), "status": "running", "targets": [], "sqlite": [], "errors": []}
    archive: Path | None = None
    try:
        enabled_file_targets = [x for x in job.get("targets", []) if x.get("enabled")]
        if enabled_file_targets:
            if job.get("pre_backup_sync"):
                script = ROOT / "scripts" / "sync_full_ledger.py"
                if script.exists(): subprocess.run([sys.executable, str(script)], cwd=ROOT, timeout=60, check=False, capture_output=True, text=True)
            archive, included = create_archive(job, stamp); result["included"] = included
            if job.get("encryption", {}).get("enabled"):
                archive = encrypt_archive(archive, str(job["encryption"]["key_env"])); result["encrypted"] = True
            else: result["encrypted"] = False
            result["archive"] = archive.name; result["bytes"] = archive.stat().st_size; result["sha256"] = calculate_sha256(archive)
            verification = verify_archive(archive, result["sha256"], str(job.get("encryption", {}).get("key_env", "")))
            result["archive_members"] = verification["members"]; result["archive_roots"] = verification["roots"]
            for target in enabled_file_targets:
                if target["type"] == "baidu": target_result = upload_baidu(archive, target.get("remote_path", "R20_Backups"), int(target.get("retries", 3)))
                else:
                    destination = (ROOT / str(target.get("path") or "backups/local")).resolve()
                    target_result = {"success": True, "attempts": 1, "destination": str(retain_local_archive(archive, int(target.get("retention", 3)), destination).relative_to(ROOT))}
                result["targets"].append({"id": target["id"], "type": target["type"], **target_result})
        if job.get("sqlite", {}).get("enabled"):
            sqlite_dir = SQLITE_DIR / str(job["id"])
            result["sqlite"] = [str(x.relative_to(ROOT)) for x in sqlite_hot_backups(stamp, int(job["sqlite"]["retention"]), sqlite_dir)]
        target_success = [x for x in result["targets"] if x.get("success")]
        target_failure = [x for x in result["targets"] if not x.get("success")]
        any_success = bool(target_success or result["sqlite"])
        result["status"] = "success" if any_success and not target_failure else "partial" if any_success else "failed"
        if target_failure: result["errors"].extend(str(x.get("error") or "目标失败") for x in target_failure)
        if archive and job.get("cleanup_local_on_success") and any_success:
            archive.unlink(missing_ok=True); result["temporary_cleaned"] = True
        elif archive: result["temporary_cleaned"] = False
    except Exception as exc:
        result["status"] = "failed"; result["errors"].append(f"{type(exc).__name__}: {exc}")
    result["finished_at"] = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = MANIFEST_DIR / f"{job['id']}_{stamp}.json"; manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); os.chmod(manifest, 0o600)
    result["manifest"] = str(manifest.relative_to(ROOT))
    return result
