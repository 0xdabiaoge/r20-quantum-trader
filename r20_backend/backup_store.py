"""Persistent configuration for independent R20 backup methods."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "data" / "backup_methods.json"
DEFAULT_CONFIG = {
    "baidu": {"enabled": True, "label": "百度网盘全量灾备", "retention": 0},
    "local": {"enabled": False, "label": "本地滚动全量归档", "retention": 3},
    "sqlite": {"enabled": False, "label": "SQLite 热备快照", "retention": 7},
}


def load_backup_methods() -> dict[str, Any]:
    result = {key: dict(value) for key, value in DEFAULT_CONFIG.items()}
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for key in result:
            if isinstance(payload.get(key), dict):
                result[key].update(payload[key])
    except (OSError, json.JSONDecodeError):
        pass
    return result


def save_backup_methods(methods: dict[str, Any]) -> None:
    normalized = load_backup_methods()
    for key in normalized:
        if key in methods:
            normalized[key]["enabled"] = bool(methods[key].get("enabled", normalized[key]["enabled"]))
            retention = int(methods[key].get("retention", normalized[key]["retention"]))
            normalized[key]["retention"] = max(0, min(retention, 90))
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".backup-methods-", suffix=".tmp", dir=CONFIG_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
