"""Single-owner R20 Gateway delivery worker."""
from __future__ import annotations
import fcntl
import os
import signal
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from r20_gateway.channels import NotificationChannelAdapter
from r20_gateway.publisher import DB_PATH
from r20_gateway.scheduler import GatewayScheduler
from r20_gateway.store import GatewayStore

ROOT = Path(__file__).resolve().parents[1]
from r20_gateway.pidfile import PID_FILE

LOCK_FILE = ROOT / "data" / ".r20_gateway.lock"
LOG_FILE = ROOT / "logs" / "r20_gateway.log"
BJ_TZ = timezone(timedelta(hours=8))
RUNNING = True


def log(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def stop(*_: object) -> None:
    global RUNNING
    RUNNING = False


def format_message(row: dict[str, object]) -> str:
    created = str(row.get("created_at", ""))
    # Format cleaner timestamp if ISO format
    if "T" in created:
        created = created.replace("T", " ")[:19]
    title = str(row.get("title", "")).strip()
    body = str(row.get("message", "")).strip()
    return f"【R20 Quantum】{title}\n⏱️ 时间：{created}\n━━━━━━━━━━━━━━\n{body}"


def run() -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = LOCK_FILE.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("gateway worker already running; exiting")
        return
    # 审计风暴修复：抢到锁者自我登记为权威 PID（唯一确知「我持锁」的实体）。
    # supervisor 旧实现对注定秒退的子进程盲写 PID 文件 → 文件长期指向死 pid，
    # 活体持锁者反而不可见，每 10s 重生一次（logs/r20_gateway.log 948 条）。
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
        os.chmod(PID_FILE, 0o600)
    except OSError:
        pass
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    store = GatewayStore(DB_PATH)
    store.recover_processing()
    _adopted = store.recover_stale_job_runs()
    if _adopted:
        log(f"收编僵尸 running 作业行 {_adopted} 条（→ interrupted）")
    scheduler = GatewayScheduler(store)
    scheduler.initialize_migration_baseline()
    log("gateway worker started with scheduler ownership")
    while RUNNING:
        # 审计#4(2026-09-13)·tick 饥饿修复：旧循环一次批量领 20 条投递并**串行**
        # HTTP 发送（webhook 卡死时每发可达超时秒级），期间 scheduler.tick() 无人喂——
        # 有积压时交易周期任务可被投递重试饿死数分钟。现每轮至多发 1 条，发完立即
        # 回到循环顶 tick；积压只影响投递速率，不再波及排程。配合 claim_due 租约
        # 老化（#11），崩溃遗留 processing 行过 120s 也可被本循环重领。
        launched = scheduler.tick()
        for job_name in launched:
            log(f"scheduled job={job_name}")
        deliveries = store.claim_due(1)
        if not deliveries:
            time.sleep(1)
            continue
        delivery = deliveries[0]
        try:
            result = NotificationChannelAdapter(str(delivery["channel"])).send(format_message(delivery))
            if result.success:
                store.complete(int(delivery["id"]), result.status, result.detail)
                log(f"{result.status} event={delivery['event_id']} channel={delivery['channel']} detail={result.detail}")
            else:
                store.fail(int(delivery["id"]), int(delivery["attempts"]), result.detail)
                log(f"delivery failed event={delivery['event_id']} channel={delivery['channel']} detail={result.detail}")
        except Exception as exc:
            store.fail(int(delivery["id"]), int(delivery["attempts"]), str(exc))
            log(f"delivery exception event={delivery['event_id']} channel={delivery['channel']} type={type(exc).__name__}")
    scheduler.shutdown()
    log("gateway worker stopped")


if __name__ == "__main__":
    run()
