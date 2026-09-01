"""Shared, validated R20 trading universe configuration."""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POOL_FILE = ROOT / "data" / "instrument_pool.json"
DEFAULT_INSTRUMENTS = [
    {"instId": "BTC-USDT-SWAP", "name": "BTC", "type": "crypto", "ccy": "BTC", "base_sz": 1, "precision": 1, "ctVal": 0.01, "tickSz": "0.1", "minSz": "0.01", "risk_per_trade_usd": 15.0},
    {"instId": "ETH-USDT-SWAP", "name": "ETH", "type": "crypto", "ccy": "ETH", "base_sz": 3, "precision": 2, "ctVal": 0.1, "tickSz": "0.01", "minSz": "0.01", "risk_per_trade_usd": 15.0},
    {"instId": "SOL-USDT-SWAP", "name": "SOL", "type": "crypto", "ccy": "SOL", "base_sz": 7, "precision": 2, "ctVal": 1.0, "tickSz": "0.01", "minSz": "0.01", "risk_per_trade_usd": 15.0},
    {"instId": "DOGE-USDT-SWAP", "name": "DOGE", "type": "crypto", "ccy": "DOGE", "base_sz": 10, "precision": 4, "ctVal": 1000.0, "tickSz": "0.0001", "minSz": "0.01", "risk_per_trade_usd": 15.0},
    {"instId": "SUI-USDT-SWAP", "name": "SUI", "type": "crypto", "ccy": "SUI", "base_sz": 50, "precision": 4, "ctVal": 1.0, "tickSz": "0.0001", "minSz": "0.01", "risk_per_trade_usd": 15.0},
    {"instId": "LINK-USDT-SWAP", "name": "LINK", "type": "crypto", "ccy": "LINK", "base_sz": 64, "precision": 3, "ctVal": 1.0, "tickSz": "0.001", "minSz": "0.01", "risk_per_trade_usd": 15.0},
]


def _precision(tick_size: str) -> int:
    normalized = tick_size.rstrip("0")
    return len(normalized.split(".", 1)[1]) if "." in normalized else 0


def from_okx_instrument(raw: dict[str, Any]) -> dict[str, Any]:
    inst_id = str(raw.get("instId", "")).upper()
    base = str(raw.get("baseCcy") or inst_id.split("-", 1)[0]).upper()
    tick_size = str(raw.get("tickSz") or "0.0001")
    return {
        "instId": inst_id,
        "name": base,
        "type": "crypto",
        "ccy": base,
        "base_sz": 1,
        "precision": _precision(tick_size),
        "ctVal": float(raw.get("ctVal") or 1.0),
        "tickSz": tick_size,
        "minSz": str(raw.get("minSz") or "1"),
        "risk_per_trade_usd": 15.0,
    }


def load_instruments() -> list[dict[str, Any]]:
    if not POOL_FILE.exists():
        return [dict(item) for item in DEFAULT_INSTRUMENTS]
    try:
        payload = json.loads(POOL_FILE.read_text(encoding="utf-8"))
        instruments = payload.get("instruments", payload) if isinstance(payload, dict) else payload
        if isinstance(instruments, list) and instruments:
            return instruments
    except (OSError, json.JSONDecodeError):
        pass
    return [dict(item) for item in DEFAULT_INSTRUMENTS]


def save_instruments(instruments: list[dict[str, Any]]) -> None:
    POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".instrument-pool-", suffix=".tmp", dir=POOL_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"version": 1, "instruments": instruments}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, POOL_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
