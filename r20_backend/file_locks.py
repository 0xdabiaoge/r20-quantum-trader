"""跨进程文件锁（审计③ 2026-09-13）。

多进程 RMW（读-改-写）同一个小 JSON 时，即使每次写都原子（mkstemp+replace），
「读最新→改→写最新」仍会互相覆盖丢更新（经典 lost update）。本模块提供与
scripts/evolution_shield._memory_lock、gateway worker 同路数的 flock 互斥，
锁文件与被保护文件同目录（.名字.lock），锁随内核自动释放，进程崩溃不留死锁。

用法（写者必须包整个 RMW，不能只包写那一半）：
    from r20_backend.file_locks import file_lock
    with file_lock(TARGET_JSON_PATH):
        data = load(...)
        ...merge...
        atomic_save(...)
"""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def file_lock(target_file: str | os.PathLike[str]) -> Iterator[None]:
    """对 target_file 的 RMW 取进程间互斥锁（阻塞式）。"""
    p = Path(str(target_file))
    lock_path = p.with_name("." + p.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
