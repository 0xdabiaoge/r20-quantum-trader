"""Lightweight process supervisor for the phase-one Gateway worker."""
from __future__ import annotations
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PID_FILE = ROOT / "data" / "r20_gateway.pid"
LOG_FILE = ROOT / "logs" / "r20_gateway_supervisor.log"
_stop = threading.Event()
_thread: threading.Thread | None = None


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def current_pid() -> int:
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        return pid if _alive(pid) else 0
    except (OSError, ValueError):
        return 0


def ensure_worker() -> int:
    pid = current_pid()
    if pid:
        return pid
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "r20_gateway.worker"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    return process.pid


def _run() -> None:
    while not _stop.is_set():
        ensure_worker()
        _stop.wait(10)


def start_supervisor() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    ensure_worker()
    _thread = threading.Thread(target=_run, name="r20-gateway-supervisor", daemon=True)
    _thread.start()


def stop_supervisor() -> None:
    _stop.set()
