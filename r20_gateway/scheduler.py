"""Gateway-owned scheduler running existing jobs in isolated subprocesses."""
from __future__ import annotations
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any

from r20_backend.schedule_store import load_schedule
from r20_gateway.store import GatewayStore

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BJ_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class JobSpec:
    name: str
    script: str
    interval_seconds: int | None = None
    timeout_seconds: int = 600
    schedule_key: str = ""
    default_times: tuple[str, ...] = ()


JOBS = (
    JobSpec("trader", "ai_factor_trader.py", 15 * 60, 840),
    JobSpec("factor_library", "factor_library.py", 60, 55),
    JobSpec("news", "news_sentiment_harvester.py", 10 * 60, 300),
    JobSpec("daily_briefing", "daily_summary_and_backup.py", None, 600, "briefing_times", ("08:00", "20:00")),
    JobSpec("self_improvement", "self_improvement_engine.py", None, 1200, "self_improvement_time", ("20:00",)),
    JobSpec("nightly_backup", "nightly_backup_and_clean.py", None, 1800, "backup_time", ("02:00",)),
)


def scheduler_snapshot(store: GatewayStore) -> dict[str, Any]:
    schedule = load_schedule()
    now = datetime.now(BJ_TZ)
    jobs = []
    for spec in JOBS:
        raw = store.get_state(f"job.last.{spec.name}")
        try:
            last = datetime.fromisoformat(raw) if raw else None
        except ValueError:
            last = None
        value = schedule.get(spec.schedule_key) if spec.schedule_key else None
        times = tuple(str(item) for item in value) if isinstance(value, list) else ((str(value),) if isinstance(value, str) else spec.default_times)
        jobs.append({
            "name": spec.name,
            "script": spec.script,
            "last_scheduled_at": last.isoformat() if last else "",
            "schedule": f"每 {spec.interval_seconds // 60} 分钟" if spec.interval_seconds else "、".join(times),
            "timezone": "Asia/Shanghai",
            "overdue": bool(spec.interval_seconds and last and (now - last).total_seconds() > spec.interval_seconds * 2),
        })
    return {"jobs": jobs, "recent_runs": store.job_runs(30)}


class GatewayScheduler:
    def __init__(self, store: GatewayStore, max_workers: int = 3):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="r20-job")
        self.running: dict[str, Future[None]] = {}

    def _last_at(self, name: str) -> datetime | None:
        raw = self.store.get_state(f"job.last.{name}")
        try:
            return datetime.fromisoformat(raw) if raw else None
        except ValueError:
            return None

    def initialize_migration_baseline(self, now: datetime | None = None) -> None:
        now = now or datetime.now(BJ_TZ)
        for spec in JOBS:
            if not self.store.get_state(f"job.last.{spec.name}"):
                self.store.set_state(f"job.last.{spec.name}", now.isoformat())

    def _scheduled_times(self, spec: JobSpec, schedule: dict[str, Any]) -> tuple[str, ...]:
        value = schedule.get(spec.schedule_key)
        if isinstance(value, list):
            return tuple(str(item) for item in value)
        if isinstance(value, str):
            return (value,)
        return spec.default_times

    def due(self, spec: JobSpec, now: datetime, schedule: dict[str, Any]) -> bool:
        last = self._last_at(spec.name)
        if spec.interval_seconds:
            return not last or (now - last).total_seconds() >= spec.interval_seconds
        minute = now.strftime("%H:%M")
        if minute not in self._scheduled_times(spec, schedule):
            return False
        return not last or last.date() != now.date() or last.strftime("%H:%M") != minute

    def _execute(self, spec: JobSpec) -> None:
        run_id = self.store.begin_job(spec.name)
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / spec.script)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=spec.timeout_seconds,
            )
            detail = (result.stderr if result.returncode else result.stdout)[-2000:]
            self.store.finish_job(run_id, result.returncode, detail)
        except subprocess.TimeoutExpired as exc:
            self.store.finish_job(run_id, 124, f"timeout after {spec.timeout_seconds}s: {exc}")
        except Exception as exc:
            self.store.finish_job(run_id, 1, f"{type(exc).__name__}: {exc}")

    def tick(self, now: datetime | None = None) -> list[str]:
        now = now or datetime.now(BJ_TZ)
        self.running = {name: future for name, future in self.running.items() if not future.done()}
        schedule = load_schedule()
        launched: list[str] = []
        for spec in JOBS:
            if spec.name in self.running or not self.due(spec, now, schedule):
                continue
            self.store.set_state(f"job.last.{spec.name}", now.isoformat())
            self.running[spec.name] = self.executor.submit(self._execute, spec)
            launched.append(spec.name)
        return launched

    def status(self) -> dict[str, Any]:
        schedule = load_schedule()
        result = []
        now = datetime.now(BJ_TZ)
        for spec in JOBS:
            last = self._last_at(spec.name)
            result.append({
                "name": spec.name,
                "script": spec.script,
                "running": spec.name in self.running and not self.running[spec.name].done(),
                "last_scheduled_at": last.isoformat() if last else "",
                "schedule": f"每 {spec.interval_seconds // 60} 分钟" if spec.interval_seconds else "、".join(self._scheduled_times(spec, schedule)),
                "timezone": "Asia/Shanghai",
                "overdue": bool(spec.interval_seconds and last and (now - last).total_seconds() > spec.interval_seconds * 2),
            })
        return {"jobs": result, "recent_runs": self.store.job_runs(30)}

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)
