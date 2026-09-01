#!/usr/bin/env python3
"""
Automated 02:00 AM Disaster Recovery & Baidu Netdisk Cloud Backup Pipeline
1. Packages full system artifacts:
   - data/ (ledgers, snapshots, adaptive config, SQLite db)
   - scripts/ (trading core, evolution engine, news harvester)
   - dashboard/ (FastAPI app & full HTML monitoring dashboard)
   - RECOVERY_GUIDE.md (full deployment & recovery guide)
2. Automatically uploads archive to Baidu Netdisk (/apps/bypy/R20_Backups/).
3. Sends status notification with download/backup confirmation.
4. Automatically deletes local .tar.gz archive after upload to save server disk space (0 overhead).
"""

import os
import tarfile
import datetime
import subprocess
import sys
import hashlib
import time
from pathlib import Path
import bypy

_BOOTSTRAP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BOOTSTRAP_ROOT not in sys.path:
    sys.path.insert(0, _BOOTSTRAP_ROOT)

from backup_runtime import retain_local_archive, sqlite_hot_backups
from r20_backend.backup_store import load_backup_methods

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
SCRIPTS_DIR = os.path.join(WORKSPACE_DIR, "scripts")
DASHBOARD_DIR = os.path.join(WORKSPACE_DIR, "dashboard")
BACKUPS_DIR = os.path.join(WORKSPACE_DIR, "backups")
GUIDE_FILE = os.path.join(WORKSPACE_DIR, "RECOVERY_GUIDE.md")

AGENT_FILES = ["SOUL.md", "PROFILE.md", "AGENTS.md", "MEMORY.md"]

os.makedirs(BACKUPS_DIR, exist_ok=True)
sys.path.append(SCRIPTS_DIR)
try:
    from qq_notifier import send_qq_message
except Exception:
    send_qq_message = None

def pre_backup_sync():
    """Sync OKX ledger and SQLite checkpoint before archiving."""
    print("🔄 [预备份] 正在执行 OKX 全量对账与数据库安全对齐...")
    try:
        sync_script = os.path.join(SCRIPTS_DIR, "sync_full_ledger.py")
        if os.path.exists(sync_script):
            subprocess.run([sys.executable, sync_script], timeout=60, check=False)
            print("✅ 账本预对账完成")
    except Exception as e:
        print(f"⚠️ 预对账异常: {e}")

def calculate_sha256(filepath: str) -> str:
    """Calculate SHA256 checksum for disaster recovery verification."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def upload_to_baidu_netdisk(local_path: str, remote_filename: str, max_retries: int = 3) -> bool:
    """Upload backup file to Baidu Netdisk via official ByPy with retries."""
    print(f"☁️ 正在上传备份包到百度网盘: {local_path} -> /apps/bypy/R20_Backups/{remote_filename}")
    bp = bypy.ByPy()
    remote_dest = f"R20_Backups/{remote_filename}"
    
    for attempt in range(1, max_retries + 1):
        try:
            res = bp.upload(local_path, remote_dest)
            if res == 0:
                print(f"🎉 [第 {attempt} 次尝试] 百度网盘云端上传成功！路径: /apps/bypy/{remote_dest}")
                return True
            else:
                print(f"⚠️ [第 {attempt} 次尝试] 百度网盘上传返回非零状态: {res}")
        except Exception as e:
            print(f"❌ [第 {attempt} 次尝试] 上传异常: {e}")
        
        if attempt < max_retries:
            time.sleep(5 * attempt)
            
    return False

def run_backup_and_cleanup():
    tz_bj = datetime.timezone(datetime.timedelta(hours=8))
    now_bj = datetime.datetime.now(tz_bj)
    date_str = now_bj.strftime("%Y-%m-%d")
    now_str = now_bj.strftime("%Y-%m-%d %H:%M:%S")

    methods = load_backup_methods()
    baidu_enabled = bool(methods["baidu"]["enabled"])
    local_enabled = bool(methods["local"]["enabled"])
    sqlite_enabled = bool(methods["sqlite"]["enabled"])

    # SQLite-only mode does not need an expensive full tar archive or OKX ledger sync.
    if baidu_enabled or local_enabled:
        pre_backup_sync()
    else:
        sqlite_copies = sqlite_hot_backups(now_bj.strftime("%Y%m%d_%H%M%S"), int(methods["sqlite"]["retention"])) if sqlite_enabled else []
        print(f"✅ SQLite-only 灾备完成，共生成 {len(sqlite_copies)} 个一致性快照。")
        return

    backup_filename = f"r20_system_backup_{date_str}.tar.gz"
    backup_path = os.path.join(BACKUPS_DIR, backup_filename)

    print(f"[{now_str}] 📦 开始执行全系统与数据归档打包...")

    # 2. Compress All Core Artifacts
    try:
        with tarfile.open(backup_path, "w:gz") as tar:
            if os.path.exists(DATA_DIR):
                tar.add(DATA_DIR, arcname="data")
            if os.path.exists(SCRIPTS_DIR):
                tar.add(SCRIPTS_DIR, arcname="scripts")
            if os.path.exists(DASHBOARD_DIR):
                tar.add(DASHBOARD_DIR, arcname="dashboard")
            if os.path.exists(GUIDE_FILE):
                tar.add(GUIDE_FILE, arcname="RECOVERY_GUIDE.md")
            
            # Archive Agent soul and workspace profile configs
            for af in AGENT_FILES:
                af_path = os.path.join(WORKSPACE_DIR, af)
                if os.path.exists(af_path):
                    tar.add(af_path, arcname=af)

        file_size_kb = round(os.path.getsize(backup_path) / 1024, 2)
        checksum_val = calculate_sha256(backup_path)
        print(f"✅ 本地全量打包完成: {backup_path} ({file_size_kb} KB, SHA256: {checksum_val[:12]}...)")
    except Exception as e:
        print(f"❌ 打包失败: {e}")
        return

    # 3. Execute enabled backup backends independently.
    upload_success = upload_to_baidu_netdisk(backup_path, backup_filename) if baidu_enabled else False
    local_copy = retain_local_archive(Path(backup_path), int(methods["local"]["retention"])) if local_enabled else None
    sqlite_copies = sqlite_hot_backups(now_bj.strftime("%Y%m%d_%H%M%S"), int(methods["sqlite"]["retention"])) if sqlite_enabled else []

    # 4. Status Notification
    ledger_file = os.path.join(DATA_DIR, "trading_ledger.json")
    trades = []
    if os.path.exists(ledger_file):
        import json
        try:
            with open(ledger_file, "r", encoding="utf-8") as f:
                trades = json.load(f)
        except Exception:
            pass

    closed_today = [t for t in trades if (t.get("action") == "平仓" or (t.get("pnl", 0) != 0 and "开仓" not in t.get("action", ""))) and date_str in str(t.get("time", ""))]
    net_pnl = sum(float(t.get("pnl", 0)) for t in closed_today)

    notify_msg = (
        f"📦 【凌晨 02:00 百度网盘灾备归档完成】\n"
        f"• 归档版本：{backup_filename}\n"
        f"• 网盘存储路径：百度网盘 /我的应用数据/bypy/R20_Backups/\n"
        f"• 包含内容：6币种AI决策引擎 + 记忆库(AI_TRADING_MEMORY.md) + 监控大屏 + 账本快照 + SQLite + Agent画像 + 恢复手册\n"
        f"• 归档包大小：{file_size_kb} KB\n"
        f"• 完整性校验：SHA256 {checksum_val[:16]}...\n"
        f"• 今日平仓盈亏：{net_pnl:+.2f} USDT\n"
        f"• 百度网盘：{'✅ 成功同步云端' if upload_success else ('⏸️ 已关闭' if not baidu_enabled else '⚠️ 上传待重试')}\n"
        f"• 本地滚动归档：{'✅ ' + str(local_copy) if local_copy else '⏸️ 已关闭'}\n"
        f"• SQLite 热备：{'✅ ' + str(len(sqlite_copies)) + ' 个数据库' if sqlite_enabled else '⏸️ 已关闭'}\n"
        f"• 临时压缩包：任务结束后清理；本地滚动归档使用独立保留策略。"
    )

    if send_qq_message:
        send_qq_message(notify_msg)

    # 5. Temporary archive is deleted when at least one enabled backend completed safely.
    backend_success = upload_success or bool(local_copy)
    if backend_success:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
                print(f"🧹 临时归档包已清理: {backup_path}")
        except Exception as e:
            print(f"清理文件失败: {e}")
    else:
        print(f"⚠️ 没有备份后端成功完成，本地保留临时包以便应急恢复: {backup_path}")

    print("🎉 每日凌晨 02:00 百度网盘灾备云上传与自动清理流程执行完毕。")

if __name__ == "__main__":
    run_backup_and_cleanup()
