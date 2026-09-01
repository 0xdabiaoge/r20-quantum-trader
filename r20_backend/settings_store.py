"""Safe local .env configuration persistence for the R20 admin plane."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import Mapping
from .config import ROOT, refresh_settings

ENV_FILE = ROOT / ".env"
MANAGED_KEYS = {
    "OKX_BASE_URL",
    "OKX_API_KEY",
    "OKX_SECRET_KEY",
    "OKX_PASSPHRASE",
    "OKX_IS_SIMULATED",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "R20_NOTIFICATION_WEBHOOK",
    "R20_SETUP_TOKEN",
    "R20_ADMIN_TOKEN",
    "R20_MANUAL_CLOSE_ENABLED",
}


def mask(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * 8}{value[-visible:]}"


def update_env(values: Mapping[str, str | bool | None]) -> None:
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    remaining = {key: value for key, value in values.items() if key in MANAGED_KEYS and value is not None}
    result: list[str] = []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            result.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key not in remaining:
            result.append(line)
            continue
        value = remaining.pop(key)
        result.append(f"{key}={str(value)}")
    if remaining:
        if result and result[-1]:
            result.append("")
        result.extend(f"{key}={str(value)}" for key, value in remaining.items())

    fd, temp_path = tempfile.mkstemp(prefix=".r20-env-", dir=ENV_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(result) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, ENV_FILE)
        os.chmod(ENV_FILE, 0o600)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    for key, value in values.items():
        if key in MANAGED_KEYS and value is not None:
            os.environ[key] = str(value)
    refresh_settings()
