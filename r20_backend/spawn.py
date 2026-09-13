"""与当前解释器同身的脚本子进程（审计 2026-09-13 · python3 静默死亡修复）。

教训：trader 周期用 `subprocess.run("python3 …", shell=True, capture_output=True)`
拉 sync_full_ledger / db_manager / news_harvester——本主机根本没有 `python3`
（venv 在 .venv/bin/python，系统层无裸 python3），rc=127 被 capture_output 吞声，
**台账同步与 SQLite 维护一整天无人知晓地零执行**。规则：
1. 子进程解释器一律 `sys.executable`（与父进程同环境，依赖可见性一致）；
2. 非零退出必吼一行（含 stderr 摘要），静默失败的 shell 组合拳从此禁用。
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Optional


def run_script(script: Any, *, timeout: int = 20, label: Optional[str] = None) -> subprocess.CompletedProcess:
    """跑一个 python 脚本；返回 CompletedProcess（异常照抛，调用方定夺）。"""
    cp = subprocess.run([sys.executable, str(script)],
                        capture_output=True, text=True, timeout=timeout)
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip().replace("\n", " / ")[:200]
        print(f"[spawn] {label or script} 退出码 {cp.returncode}：{err or '无输出'}")
    return cp
