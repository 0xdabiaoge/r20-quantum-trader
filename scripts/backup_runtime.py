"""Independent backup backends used by the nightly R20 backup job."""
from __future__ import annotations
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"
LOCAL_DIR = BACKUPS / "local"
SQLITE_DIR = BACKUPS / "sqlite"


def prune(paths: Iterable[Path], retention: int) -> None:
    items = sorted((path for path in paths if path.exists()), key=lambda p: p.stat().st_mtime, reverse=True)
    for item in items[max(0, retention):]:
        item.unlink(missing_ok=True)


def retain_local_archive(source: Path, retention: int) -> Path:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    destination = LOCAL_DIR / source.name
    shutil.copy2(source, destination)
    prune(LOCAL_DIR.glob("*.tar.gz"), retention)
    return destination


def sqlite_hot_backups(timestamp: str, retention: int) -> list[Path]:
    SQLITE_DIR.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for source in (ROOT / "data").glob("*.db"):
        destination = SQLITE_DIR / f"{source.stem}_{timestamp}.db"
        source_conn = sqlite3.connect(source)
        try:
            target_conn = sqlite3.connect(destination)
            try:
                source_conn.backup(target_conn)
            finally:
                target_conn.close()
        finally:
            source_conn.close()
        os.chmod(destination, 0o600)
        created.append(destination)
    prune(SQLITE_DIR.glob("*.db"), retention)
    return created
