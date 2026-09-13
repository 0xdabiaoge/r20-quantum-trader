"""R20 Strategy Policy Snapshot & Version Control Workbench Engine.

Provides immutable snapshot fingerprinting, persistent archiving, one-click rollback,
and export/import capabilities across all 4 strategy units:
1. Prompt Profile (Prompt Studio)
2. Evolution Mind (Evolution Shield)
3. Physical Interceptors (Interceptors Plugin Pipeline)
4. Model Council (Council Desk)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore

from r20_backend.version import __version__

# ── 结构优化阶段 2（B6）：指纹/规范化/整包标识已迁至 policy/fingerprints.py ──
# 门面重导出以保持既有 `from r20_backend.policy_snapshot import X` 不变。
from r20_backend.policy.fingerprints import (
    _canon_council_config,
    _canon_evolution_memory,
    _canon_prompt_config,
    _projection_digest,
    canonical_package_projection,
    compute_file_hash,
    compute_layout_hash,
    extract_council_fingerprint,
    extract_evolution_mind_fingerprint,
    extract_interceptors_fingerprint,
    extract_prompt_profile_fingerprint,
    package_identity,
    package_restore_diff,
)
from r20_backend.policy.paths import ARCHIVE_DIR, ARCHIVE_INDEX_FILE, DATA_DIR, ROOT
from r20_backend.policy.schema import (
    DEFAULT_BASE_VERSION,
    _COUNCIL_ROLE_FIELDS,
    _PACKAGE_UNITS,
    _PROFILE_IDENTITY_FIELDS,
    _TEMPLATE_KEYS,
)

_BJ = timezone(timedelta(hours=8))

logger = logging.getLogger(__name__)
















def generate_policy_snapshot(
    root_dir: Optional[Path] = None,
    prompt_profile: Optional[Dict[str, Any]] = None,
    memory_snapshot: Optional[Dict[str, Any]] = None,
    interceptor_plugins: Optional[List[Dict[str, Any]]] = None,
    council_config: Optional[Dict[str, Any]] = None,
    plugins_dir: Optional[Path] = None,
    base_version: str = DEFAULT_BASE_VERSION,
) -> Dict[str, Any]:
    """Generates an immutable snapshot fingerprint across the 4 core strategy units."""
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


# =========================================================================
# 归档包标识（审计 P0-3，2026-09-13）
# =========================================================================
# 病灶：policy_hash 只覆盖 4 个单元（提示词/心法/拦截器/委员会），而归档包实际装 6 个
# （另含 risk_config 与 venue_routing），归档文件名却只用 policy_hash 命名 →
# **仅风控/路由不同的两个版本被判为同一版本**，第二次归档静默覆盖第一次；
# 回滚后的哈希校验也因此对风控/路由的恢复失败完全失明。
# 修复：另算一个「整包标识」用于文件命名与恢复后校验，并对易变字段做规范化
# （时间戳/评分/revision 每次写都会变，绝不能进标识，否则校验必然误报）。
















# =========================================================================
# Policy Version Workbench: Archive, Rollback, Export & Import
# =========================================================================

def _atomic_write_json(file_path: Path, data: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=file_path.parent, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        temp_name = tf.name
    os.replace(temp_name, file_path)


_process_thread_lock = threading.RLock()
_lock_tls = threading.local()


@contextmanager
def _index_lock(archive_dir: Path, shared: bool = False):
    """Reentrant thread and process file locking context for policy archive index operations."""
    with _process_thread_lock:
        if fcntl is None:
            yield
            return

        archive_dir.mkdir(parents=True, exist_ok=True)
        lock_file = archive_dir / ".index.lock"

        depth = getattr(_lock_tls, "depth", 0)
        if depth > 0:
            _lock_tls.depth = depth + 1
            try:
                yield
            finally:
                _lock_tls.depth -= 1
            return

        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
        flag = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        fcntl.flock(fd, flag)
        _lock_tls.depth = 1
        _lock_tls.fd = fd
        try:
            yield
        finally:
            _lock_tls.depth = 0
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass
            _lock_tls.fd = None


def _rebuild_index_from_archives(a_dir: Path) -> List[Dict[str, Any]]:
    """Scans all policy_*.json files in archive_dir and reconstructs index entries."""
    entries: List[Dict[str, Any]] = []
    if not a_dir.is_dir():
        return entries

    for f in a_dir.glob("policy_*.json"):
        if not f.is_file() or f.name.endswith(".tmp"):
            continue
        try:
            with open(f, "r", encoding="utf-8") as handle:
                package = json.load(handle)
            meta = package.get("metadata") or {}
            policy_hash = package.get("policy_hash") or f.stem.replace("policy_", "")
            policy_version = package.get("policy_version") or f"unknown@{policy_hash}"
            entry = {
                "policy_version": policy_version,
                "policy_hash": policy_hash,
                "name": str(meta.get("name") or f"策略归档-{policy_hash}"),
                "description": str(meta.get("description") or ""),
                "author": str(meta.get("author") or "admin"),
                "archived_at": str(
                    meta.get("archived_at")
                    or datetime.fromtimestamp(f.stat().st_mtime, _BJ).isoformat(sep=" ", timespec="seconds")
                ),
                "summary": str(package.get("summary") or ""),
                "archive_file": f.name,
            }
            entries.append(entry)
        except Exception as err:
            logger.warning("Failed to parse archive file %s during index rebuild: %s", f.name, err)

    entries.sort(key=lambda x: str(x.get("archived_at", "")), reverse=True)
    return entries


def load_archive_index(archive_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Loads metadata index of archived policies with locking and corruption recovery."""
    a_dir = archive_dir or ARCHIVE_DIR
    idx_file = a_dir / "index.json"

    with _index_lock(a_dir, shared=True):
        if not idx_file.is_file():
            reconstructed = _rebuild_index_from_archives(a_dir)
            if reconstructed:
                try:
                    save_archive_index(reconstructed, archive_dir=a_dir)
                except Exception:
                    pass
            return reconstructed

        needs_rebuild = False
        data: Any = None
        try:
            with open(idx_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    needs_rebuild = True
                else:
                    data = json.loads(content)
                    if not isinstance(data, list):
                        needs_rebuild = True
        except Exception as e:
            logger.warning("Corrupt policy archive index detected: %s", e)
            needs_rebuild = True

        if needs_rebuild:
            try:
                backup_file = a_dir / f"index.json.corrupt.{int(time.time())}"
                if idx_file.is_file():
                    os.replace(idx_file, backup_file)
                    logger.info("Backed up corrupted index to %s", backup_file.name)
            except Exception as e:
                logger.error("Failed to backup corrupt index: %s", e)

            reconstructed = _rebuild_index_from_archives(a_dir)
            try:
                save_archive_index(reconstructed, archive_dir=a_dir)
            except Exception:
                pass
            return reconstructed

        valid_entries = []
        for item in data:
            if isinstance(item, dict) and "policy_hash" in item:
                valid_entries.append(item)
        return valid_entries


def save_archive_index(index_data: List[Dict[str, Any]], archive_dir: Optional[Path] = None) -> None:
    """Saves metadata index of archived policies with atomic write and locking."""
    a_dir = archive_dir or ARCHIVE_DIR
    idx_file = a_dir / "index.json"
    with _index_lock(a_dir, shared=False):
        _atomic_write_json(idx_file, index_data)


def capture_full_strategy_package(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Captures complete runtime data payload across all 4 units for rollback/export."""
    r_dir = root_dir or ROOT
    sys_path_added = False
    scripts_dir = str(r_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
        sys_path_added = True

    try:
        try:
            from prompt_library import load_library
            prompt_full = load_library()
        except (ImportError, AttributeError):
            from prompt_library import load_prompt_config
            prompt_full = load_prompt_config()
    except Exception as e:
        logger.warning("Failed to capture prompt library: %s", e)
        prompt_full = {}

    try:
        from evolution_shield import STRUCTURED_MEMORY_FILE
        if STRUCTURED_MEMORY_FILE.is_file():
            raw_text = STRUCTURED_MEMORY_FILE.read_text(encoding="utf-8")
            memory_full = json.loads(raw_text)
        else:
            from evolution_shield import read_memory_snapshot
            memory_full = read_memory_snapshot()
    except Exception as e:
        logger.warning("Failed to capture evolution memory: %s", e)
        memory_full = {"version": "missing", "lessons": []}

    try:
        from r20_backend.interceptor_manager import load_config as load_interceptor_config
        interceptor_full = load_interceptor_config(create_if_missing=False)
    except Exception as e:
        logger.warning("Failed to capture interceptor config: %s", e)
        interceptor_full = {}

    try:
        from r20_backend.council_manager import load_council_config
        council_full = load_council_config()
    except Exception as e:
        logger.warning("Failed to capture council config: %s", e)
        council_full = {}

    try:
        from r20_backend import risk_config
        risk_full = risk_config.current_values()
    except Exception as e:
        logger.warning("Failed to capture risk config: %s", e)
        risk_full = {}

    try:
        from r20_backend.exchanges.routing_policy import _read_raw_routing
        routing_full = _read_raw_routing()
    except Exception as e:
        logger.warning("Failed to capture routing config: %s", e)
        routing_full = {}

    finally:
        if sys_path_added and scripts_dir in sys.path:
            try:
                sys.path.remove(scripts_dir)
            except ValueError:
                pass

    snapshot = generate_policy_snapshot(root_dir=r_dir)

    return {
        "format": "r20_policy_package_v1",
        "policy_version": snapshot["policy_version"],
        "policy_hash": snapshot["policy_hash"],
        "captured_at": snapshot["timestamp"],
        "summary": snapshot["summary"],
        "snapshot": snapshot,
        "package": {
            "prompt_config": prompt_full,
            "evolution_memory": memory_full,
            "interceptor_config": interceptor_full,
            "council_config": council_full,
            "risk_config": risk_full,
            "venue_routing": routing_full,
        },
    }


def archive_current_policy(
    name: str,
    description: str = "",
    author: str = "admin",
    archive_dir: Optional[Path] = None,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Archives the live strategy state into an immutable policy version package."""
    a_dir = archive_dir or ARCHIVE_DIR
    a_dir.mkdir(parents=True, exist_ok=True)

    with _index_lock(a_dir, shared=False):
        package = capture_full_strategy_package(root_dir=root_dir)
        policy_hash = package["policy_hash"]
        policy_version = package["policy_version"]
        # 审计 P0-3：文件标识改用「整包标识」——policy_hash 看不到 risk_config/venue_routing，
        # 只差风控的两个版本会同名互相覆盖。
        package_hash = package_identity(package.get("package") or {})

        safe_name = name.strip() or f"策略归档-{policy_hash}"
        archive_file = a_dir / f"policy_{package_hash or policy_hash}.json"

        package["package_hash"] = package_hash
        package["metadata"] = {
            "name": safe_name,
            "description": description.strip(),
            "author": author,
            "archived_at": datetime.now(_BJ).isoformat(sep=" ", timespec="seconds"),
            "archive_file": archive_file.name,
            "package_hash": package_hash,
        }

        _atomic_write_json(archive_file, package)

        # Update index：去重键 = 整包标识（同包重归档才替换）；无 package_hash 的历史
        # 条目退回 policy_hash 判等，保持旧行为。
        index_data = load_archive_index(archive_dir=a_dir)

        def _same_archive(item: Dict[str, Any]) -> bool:
            item_pkg = str(item.get("package_hash") or "")
            if item_pkg:
                return item_pkg == package_hash
            return str(item.get("policy_hash") or "") == policy_hash

        index_data = [item for item in index_data if not _same_archive(item)]

        entry = {
            "policy_version": policy_version,
            "policy_hash": policy_hash,
            "package_hash": package_hash,
            "name": safe_name,
            "description": description.strip(),
            "author": author,
            "archived_at": package["metadata"]["archived_at"],
            "summary": package["summary"],
            "archive_file": archive_file.name,
        }
        index_data.insert(0, entry)
        save_archive_index(index_data, archive_dir=a_dir)

        return entry


# Canonical alias
archive_policy_snapshot = archive_current_policy


def _resolve_archive_file(a_dir: Path, key: str) -> Path:
    """按标识解析归档文件：键可以是整包标识（新命名）或四单元 policy_hash（历史命名）。

    审计 P0-3 配套：文件名改由整包标识命名后，删除/回滚都必须经索引解析，否则会出现
    「索引已删、文件还在」或反过来「文件在、却报 404」的半途状态。
    """
    direct = a_dir / f"policy_{key}.json"
    if direct.is_file():
        return direct
    for item in load_archive_index(archive_dir=a_dir):
        if str(item.get("policy_hash") or "") != key and str(item.get("package_hash") or "") != key:
            continue
        candidate = a_dir / str(item.get("archive_file") or "")
        if candidate.is_file():
            return candidate
    return direct


def _review_restored_lessons(lessons: Any) -> Dict[str, Any]:
    """回滚落盘前的宪法复核（审计 P1-8b）。

    旧实现只跑 `_validate`（schema），不跑 `audit_proposed_lesson` → 策略回滚是绕过
    宪法门禁的稳定通道。回滚是管理员的显式恢复动作，不宜因某条心法不合规就整体失败，
    但必须**留痕并披露**：违规条目一律改标 RESTORED_UNREVIEWED 并在结果里点名。
    """
    report: Dict[str, Any] = {"total": 0, "flagged": [], "marked": 0}
    try:
        from evolution_shield import audit_proposed_lesson
    except Exception as exc:  # 复核器不可用 → 如实披露，绝不假装审过
        report["reviewer_error"] = str(exc)[:160]
        return report
    for item in lessons or []:
        if not isinstance(item, dict):
            continue
        report["total"] += 1
        text = str(item.get("rule_text") or "").strip()
        if not text:
            continue
        try:
            passed, reason = audit_proposed_lesson(text, sample_size=int(item.get("sample_size") or 1))
        except Exception as exc:
            passed, reason = False, f"复核异常: {exc}"
        if not passed:
            report["flagged"].append({"id": item.get("id"), "reason": reason, "rule_text": text[:80]})
            item["shield_status"] = "RESTORED_UNREVIEWED"
            item["shield_reason"] = reason
            report["marked"] += 1
        elif not item.get("shield_status"):
            item["shield_status"] = "RESTORED"
            report["marked"] += 1
    return report


def restore_archived_policy(
    policy_hash: str,
    archive_dir: Optional[Path] = None,
    root_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Atomically restores live strategy state to an archived policy version package.

    Guarantees no partial state on failure: takes a pre-restore backup snapshot
    and automatically reverts if any unit restore operation fails.
    """
    if not policy_hash or not isinstance(policy_hash, str) or not re.match(r"^[a-zA-Z0-9_-]+$", policy_hash):
        raise ValueError(f"无效的策略哈希标识: {policy_hash}")

    a_dir = archive_dir or ARCHIVE_DIR
    archive_file = _resolve_archive_file(a_dir, policy_hash)
    if not archive_file.is_file():
        raise FileNotFoundError(f"未找到归档的策略版本文件: {policy_hash}")

    with open(archive_file, "r", encoding="utf-8") as f:
        package = json.load(f)

    pkg_payload = package.get("package") or {}
    r_dir = root_dir or ROOT
    archived_package_hash = str(
        package.get("package_hash") or (package.get("metadata") or {}).get("package_hash") or "")
    # 请求键可能是整包标识（新命名）或四单元 policy_hash（历史命名）：四单元校验必须
    # 比对**归档自带的** policy_hash，否则新命名归档永远校验不过（审计 P0-3 修复配套）。
    archived_policy_hash = str(package.get("policy_hash") or policy_hash)

    # Pre-restore safety snapshot to prevent partial state on failure
    pre_restore_package = capture_full_strategy_package(root_dir=r_dir)

    memory_review: Dict[str, Any] = {}

    def _apply_package(payload: Dict[str, Any]) -> None:
        sys_path_added = False
        scripts_dir = str(r_dir / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
            sys_path_added = True

        try:
            # 1. Restore Prompt Profile
            if "prompt_config" in payload and payload["prompt_config"]:
                try:
                    from prompt_library import save_library
                    save_library(payload["prompt_config"])
                except (ImportError, AttributeError):
                    from prompt_library import save_prompt_config
                    save_prompt_config(payload["prompt_config"])

            # 2. Restore Evolution Memory
            if "evolution_memory" in payload:
                from evolution_shield import STRUCTURED_MEMORY_FILE, _memory_lock, _validate
                evo_data = payload["evolution_memory"]
                with _memory_lock():
                    if evo_data is None or (
                        isinstance(evo_data, dict)
                        and (evo_data.get("exists") is False or evo_data.get("version") == "missing")
                    ):
                        STRUCTURED_MEMORY_FILE.unlink(missing_ok=True)
                    elif isinstance(evo_data, dict) and "raw_text" in evo_data:
                        raw = str(evo_data["raw_text"])
                        parsed = json.loads(raw)
                        if isinstance(parsed, list):
                            _validate(parsed)
                            memory_review.clear()
                            memory_review.update(_review_restored_lessons(parsed))
                        elif isinstance(parsed, dict) and "lessons" in parsed:
                            if not isinstance(parsed["lessons"], list):
                                raise ValueError("Invalid lessons in envelope: must be a list")
                            _validate(parsed["lessons"])
                            memory_review.clear()
                            memory_review.update(_review_restored_lessons(parsed["lessons"]))
                        STRUCTURED_MEMORY_FILE.write_text(raw, encoding="utf-8")
                    elif isinstance(evo_data, list):
                        _validate(evo_data)
                        memory_review.clear()
                        memory_review.update(_review_restored_lessons(evo_data))
                        _atomic_write_json(STRUCTURED_MEMORY_FILE, evo_data)
                    elif isinstance(evo_data, dict):
                        lessons = evo_data.get("lessons")
                        if lessons is not None:
                            if not isinstance(lessons, list):
                                raise ValueError("Invalid lessons in evolution memory: must be a list")
                            _validate(lessons)
                        memory_review.clear()
                        memory_review.update(_review_restored_lessons(evo_data.get("lessons") or []))
                        _atomic_write_json(STRUCTURED_MEMORY_FILE, evo_data)
                    else:
                        raise ValueError(f"Unsupported evolution memory format: {type(evo_data)}")

            # 3. Restore Interceptors
            if (
                "interceptor_config" in payload
                and isinstance(payload["interceptor_config"], dict)
                and payload["interceptor_config"]
            ):
                from r20_backend.interceptor_manager import save_config as save_interceptor_config
                save_interceptor_config(payload["interceptor_config"])

            # 4. Restore Council
            if (
                "council_config" in payload
                and isinstance(payload["council_config"], dict)
                and payload["council_config"]
            ):
                from r20_backend.council_manager import save_council_config
                save_council_config(payload["council_config"])

            # 5. Restore Risk Config
            # 审计 P0-3(2026-09-13)：此处曾宽 except → logger.warning，于是「旧归档含已
            # 下架风控键 / 值越界」导致风控**整段没恢复**，接口仍返回 status=restored，
            # 而审计与四单元哈希都看不见。现改为不吞：异常上抛 → 外层回滚 + 明确报错。
            if (
                "risk_config" in payload
                and isinstance(payload["risk_config"], dict)
                and payload["risk_config"]
            ):
                from r20_backend import risk_config
                from r20_backend.settings_store import update_env
                env_updates = risk_config.normalize(payload["risk_config"])
                update_env(env_updates)

            # 6. Restore Venue Routing（同 5：不再吞异常）
            if (
                "venue_routing" in payload
                and isinstance(payload["venue_routing"], dict)
                and payload["venue_routing"]
            ):
                from r20_backend.exchanges.routing_policy import ROUTING_FILE
                _atomic_write_json(ROUTING_FILE, payload["venue_routing"])
        finally:
            if sys_path_added and scripts_dir in sys.path:
                try:
                    sys.path.remove(scripts_dir)
                except ValueError:
                    pass

    try:
        _apply_package(pkg_payload)
    except Exception as exc:
        logger.error("Error during strategy restore: %s. Reverting to pre-restore state...", exc)
        try:
            _apply_package(pre_restore_package.get("package") or {})
        except Exception as revert_exc:
            logger.critical("Failed to revert to pre-restore state: %s", revert_exc)
        raise RuntimeError(f"策略回滚失败且已恢复原状态: {exc}") from exc

    # Verify new restored snapshot
    new_snapshot = generate_policy_snapshot(root_dir=r_dir)
    if new_snapshot["policy_hash"] != archived_policy_hash:
        logger.error(
            "Restored snapshot hash mismatch: expected %s, got %s. Reverting to pre-restore state...",
            archived_policy_hash,
            new_snapshot["policy_hash"],
        )
        try:
            _apply_package(pre_restore_package.get("package") or {})
        except Exception as revert_exc:
            logger.critical("Failed to revert to pre-restore state after hash mismatch: %s", revert_exc)
        raise RuntimeError(
            f"策略回滚失败且已恢复原状态: 恢复后哈希 {new_snapshot['policy_hash']} 与目标 {archived_policy_hash} 不一致"
        )

    # 审计 P0-3：四单元哈希看不到风控/路由——它们恢复失败时上面的校验永远是绿的。
    # 现按整包规范化投影逐单元核对，任何「归档里承诺、恢复后没对上」的单元一律判定
    # 恢复失败并回滚（绝不留半套状态），并在报错里点名是哪个单元。
    new_package = capture_full_strategy_package(root_dir=r_dir)
    restore_gaps = package_restore_diff(pkg_payload, new_package.get("package") or {})
    if restore_gaps:
        logger.error("Restored package diff detected in units: %s. Reverting...", restore_gaps)
        try:
            _apply_package(pre_restore_package.get("package") or {})
        except Exception as revert_exc:
            logger.critical("Failed to revert to pre-restore state after unit diff: %s", revert_exc)
        raise RuntimeError(
            "策略回滚失败且已恢复原状态: 以下单元未恢复到归档值 — " + "、".join(restore_gaps)
        )

    # 归档未覆盖、但当前存在的键（旧包无法删除后加键）：如实披露，不谎报「全盘回滚」
    archived_risk_keys = set((canonical_package_projection(pkg_payload).get("risk_config") or {}).keys())
    current_risk_keys = set((canonical_package_projection(new_package.get("package") or {}).get("risk_config") or {}).keys())
    extra_risk_keys = sorted(current_risk_keys - archived_risk_keys)
    return {
        "status": "restored",
        "target_policy_hash": archived_policy_hash,
        "target_package_hash": archived_package_hash or None,
        "restored_snapshot": new_snapshot,
        "restored_units": [unit for unit in _PACKAGE_UNITS if pkg_payload.get(unit) not in (None, {}, [])],
        "uncovered_risk_keys": extra_risk_keys,
        # 审计 P1-8b：回滚落盘的心法也过了一遍宪法门禁，违规条目在此点名
        "memory_review": memory_review or None,
    }


# Canonical alias
restore_policy_snapshot = restore_archived_policy


def delete_archived_policy(
    policy_hash: str,
    archive_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Deletes an archived policy file and removes its metadata from index."""
    if not policy_hash or not isinstance(policy_hash, str) or not re.match(r"^[a-zA-Z0-9_-]+$", policy_hash):
        raise ValueError(f"无效的策略哈希标识: {policy_hash}")

    a_dir = archive_dir or ARCHIVE_DIR
    archive_file = _resolve_archive_file(a_dir, policy_hash)

    with _index_lock(a_dir, shared=False):
        deleted_file = False
        if archive_file.is_file():
            archive_file.unlink(missing_ok=True)
            deleted_file = True

        index_data = load_archive_index(archive_dir=a_dir)
        original_len = len(index_data)
        new_index = [item for item in index_data
                     if str(item.get("policy_hash") or "") != policy_hash
                     and str(item.get("package_hash") or "") != policy_hash]

        if len(new_index) < original_len or deleted_file:
            save_archive_index(new_index, archive_dir=a_dir)
            return {"deleted": True, "policy_hash": policy_hash}

        raise FileNotFoundError(f"未找到指定的策略归档: {policy_hash}")


# Canonical alias
delete_policy_archive = delete_archived_policy


__all__ = [
    "DEFAULT_BASE_VERSION",
    "compute_layout_hash",
    "compute_file_hash",
    "extract_prompt_profile_fingerprint",
    "extract_evolution_mind_fingerprint",
    "extract_interceptors_fingerprint",
    "extract_council_fingerprint",
    "format_policy_snapshot_summary",
    "generate_policy_snapshot",
    "get_current_policy_snapshot",
    "capture_full_strategy_package",
    "load_archive_index",
    "save_archive_index",
    "archive_current_policy",
    "archive_policy_snapshot",
    "restore_archived_policy",
    "restore_policy_snapshot",
    "delete_archived_policy",
    "delete_policy_archive",
]
