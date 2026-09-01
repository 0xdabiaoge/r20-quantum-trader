"""SQLite-backed durable event and per-channel delivery queue."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from r20_gateway.events import GatewayEvent

BJ_TZ = timezone(timedelta(hours=8))
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  priority INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deliveries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL REFERENCES events(event_id),
  channel TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TEXT NOT NULL,
  last_error TEXT NOT NULL DEFAULT '',
  delivered_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(event_id, channel)
);
CREATE INDEX IF NOT EXISTS idx_deliveries_due ON deliveries(status, next_attempt_at);
"""


class GatewayStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def publish(self, event: GatewayEvent, channels: list[str]) -> str:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event.event_id, event.event_type, event.title, event.message, json.dumps(event.payload, ensure_ascii=False), event.priority, event.created_at),
            )
            for channel in channels:
                connection.execute(
                    "INSERT OR IGNORE INTO deliveries(event_id, channel, next_attempt_at, created_at) VALUES (?, ?, ?, ?)",
                    (event.event_id, channel, event.created_at, event.created_at),
                )
        return event.event_id

    def claim_due(self, limit: int = 20) -> list[dict[str, Any]]:
        now = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT d.id, d.channel, d.attempts, e.* FROM deliveries d
                   JOIN events e ON e.event_id=d.event_id
                   WHERE d.status IN ('pending','retry') AND d.next_attempt_at<=?
                   ORDER BY e.priority DESC, d.id ASC LIMIT ?""",
                (now, limit),
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                marks = ",".join("?" for _ in ids)
                connection.execute(f"UPDATE deliveries SET status='processing' WHERE id IN ({marks})", ids)
            return [dict(row) for row in rows]

    def complete(self, delivery_id: int) -> None:
        now = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as connection:
            connection.execute("UPDATE deliveries SET status='delivered', delivered_at=?, last_error='' WHERE id=?", (now, delivery_id))

    def fail(self, delivery_id: int, attempts: int, error: str, max_attempts: int = 6) -> None:
        new_attempts = attempts + 1
        status = "dead" if new_attempts >= max_attempts else "retry"
        delay = min(3600, 30 * (2 ** min(new_attempts - 1, 7)))
        next_at = (datetime.now(BJ_TZ) + timedelta(seconds=delay)).strftime("%Y-%m-%d %H:%M:%S")
        with self.connect() as connection:
            connection.execute(
                "UPDATE deliveries SET status=?, attempts=?, next_attempt_at=?, last_error=? WHERE id=?",
                (status, new_attempts, next_at, error[:1000], delivery_id),
            )

    def recover_processing(self) -> None:
        with self.connect() as connection:
            connection.execute("UPDATE deliveries SET status='retry' WHERE status='processing'")

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute("SELECT status, COUNT(*) count FROM deliveries GROUP BY status").fetchall()
        result = {"pending": 0, "processing": 0, "retry": 0, "delivered": 0, "dead": 0}
        result.update({row["status"]: row["count"] for row in rows})
        return result

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT d.id, d.channel, d.status, d.attempts, d.last_error, d.delivered_at,
                          e.event_id, e.event_type, e.title, e.message, e.priority, e.created_at
                   FROM deliveries d JOIN events e ON e.event_id=d.event_id
                   ORDER BY d.id DESC LIMIT ?""",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [dict(row) for row in rows]
