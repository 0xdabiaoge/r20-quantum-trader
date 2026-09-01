"""Public publisher API for strategy and scheduler processes."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from r20_backend.notifications import enabled_channels
from r20_gateway.events import GatewayEvent
from r20_gateway.store import GatewayStore

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "r20_gateway.db"


def publish(
    event_type: str,
    title: str,
    message: str,
    payload: dict[str, Any] | None = None,
    priority: int = 50,
    channels: list[str] | None = None,
) -> str:
    event = GatewayEvent(event_type=event_type, title=title, message=message, payload=payload or {}, priority=priority)
    targets = enabled_channels() if channels is None else channels
    return GatewayStore(DB_PATH).publish(event, targets)
