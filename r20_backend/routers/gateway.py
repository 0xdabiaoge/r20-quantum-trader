"""Gateway scheduling, notification channels, and backup/restore management routes."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Body, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from r20_backend.config import settings, refresh_settings
from r20_backend.settings_store import update_env, remove_env, mask, mask_url, is_masked
from r20_gateway.secrets import save_secrets
from r20_backend.audit import record as audit_record
from r20_backend.notifications import _env as notification_env, diagnose_channel, test_channel
from r20_backend.dependencies import (
    ROOT, DATA_DIR, SCRIPTS_DIR, BACKUP_LOG_FILE,
    app_attr, require_admin_header, require_superadmin,
)
from r20_backend.schemas import (
    GatewayReplayRequest,
    ChannelToggleRequest,
    NotificationConfigUpdate,
    QQOpenIDCaptureStartRequest,
    NotificationTestRequest,
    NotificationScheduleUpdate,
    BackupRequest,
    BackupRestoreRequest,
    SimpleBackupUpdateRequest,
    BackupCredentialUpdateRequest,
    BackupJobCreateRequest,
    BackupJobUpdateRequest,
    BackupJobRunRequest,
    BackupJobImportRequest,
    BackupVerifyRequest,
    BackupMethodsUpdate,
)
from r20_backend.backup_store import (
    create_job as create_backup_job, delete_job as delete_backup_job, export_job as export_backup_job,
    get_job as get_backup_job, import_job as import_backup_job, list_jobs as list_backup_jobs,
    load_backup_methods, save_backup_methods, update_job as update_backup_job, validate_backup_job,
)
from r20_backend.backup_secrets import credential_status as backup_credential_status, save_credentials as save_backup_credentials
from r20_backend.schedule_store import load_schedule, save_schedule
from r20_gateway import __version__ as GATEWAY_VERSION
from r20_gateway.publisher import DB_PATH as GATEWAY_DB_PATH
from r20_gateway.scheduler import scheduler_snapshot
from r20_gateway.store import GatewayStore

router = APIRouter(tags=["gateway"])


@router.put("/api/v1/admin/channels/{channel}/toggle")
def toggle_channel(channel: str, payload: ChannelToggleRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session"), x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """通知频道开关（含开关时顺带保存凭证）；33cc95d 拆分时丢失，2026-09-13 按旧体还原。"""
    from r20_gateway.secrets import save_secrets
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    keys = {
        "qq": "R20_NOTIFY_QQ_ENABLED",
        "telegram": "R20_NOTIFY_TELEGRAM_ENABLED",
        "wechat": "R20_NOTIFY_WECHAT_ENABLED",
        "webhook": "R20_NOTIFY_WEBHOOK_ENABLED",
    }
    channel_names = {
        "qq": "QQ 官方 Bot",
        "telegram": "Telegram Bot",
        "wechat": "企业微信",
        "webhook": "通用 Webhook",
    }
    if channel not in keys:
        raise HTTPException(status_code=404, detail="未知频道")

    # If the user provided inputs while toggling, save them immediately
    # 审计修复A2：toggle 同样拒绝掩码回写（含 secrets 通道——优先级高于 .env，写坏即告警死亡）
    if channel == "wechat" and payload.wechat_webhook is not None and not is_masked(payload.wechat_webhook):
        val = payload.wechat_webhook.strip()
        if val:
            save_secrets({"R20_WECHAT_WEBHOOK": val})
            remove_env({"R20_WECHAT_WEBHOOK"})
    elif channel == "webhook" and payload.webhook_url is not None and not is_masked(payload.webhook_url):
        val = payload.webhook_url.strip()
        if val:
            save_secrets({"R20_NOTIFICATION_WEBHOOK": val})
            remove_env({"R20_NOTIFICATION_WEBHOOK"})
    elif channel == "telegram":
        if payload.telegram_bot_token is not None and payload.telegram_bot_token.strip() and not is_masked(payload.telegram_bot_token):
            save_secrets({"R20_TELEGRAM_BOT_TOKEN": payload.telegram_bot_token.strip()})
            remove_env({"R20_TELEGRAM_BOT_TOKEN"})
        tg_env = {}
        if payload.telegram_chat_id is not None:
            tg_env["R20_TELEGRAM_CHAT_ID"] = payload.telegram_chat_id.strip()
        if payload.telegram_api_base is not None:
            tg_env["R20_TELEGRAM_API_BASE"] = payload.telegram_api_base.strip()
        if tg_env:
            update_env(tg_env)
    elif channel == "qq":
        if payload.qq_client_secret is not None and payload.qq_client_secret.strip() and not is_masked(payload.qq_client_secret):
            save_secrets({"R20_QQ_CLIENT_SECRET": payload.qq_client_secret.strip()})
            remove_env({"R20_QQ_CLIENT_SECRET"})
        qq_env = {}
        if payload.qq_app_id is not None:
            qq_env["R20_QQ_APP_ID"] = payload.qq_app_id.strip()
        if payload.qq_openid is not None:
            qq_env["R20_QQ_OPENID"] = payload.qq_openid.strip()
        if qq_env:
            update_env(qq_env)

    name = channel_names.get(channel, channel)
    if payload.enabled:
        env = notification_env()
        readiness = {
            "qq": bool(env.get("R20_QQ_APP_ID") and env.get("R20_QQ_CLIENT_SECRET") and env.get("R20_QQ_OPENID")),
            "telegram": bool(env.get("R20_TELEGRAM_BOT_TOKEN") and env.get("R20_TELEGRAM_CHAT_ID")),
            "wechat": bool(env.get("R20_WECHAT_WEBHOOK")),
            "webhook": bool(env.get("R20_NOTIFICATION_WEBHOOK")),
        }
        if not readiness[channel]:
            if channel == "qq":
                if not env.get("R20_QQ_OPENID"):
                    raise HTTPException(status_code=400, detail="QQ 缺少目标用户 OpenID，请先点击「⚡ 自动获取 OpenID」向 Bot 发送消息完成绑定")
                raise HTTPException(status_code=400, detail="QQ App ID 或 Client Secret 尚未配置完整")
            elif channel == "wechat":
                raise HTTPException(status_code=400, detail="企业微信尚未配置 Webhook URL，请先填入有效 Webhook 地址再开启")
            elif channel == "webhook":
                raise HTTPException(status_code=400, detail="通用 Webhook 尚未配置 URL，请先填入有效 Webhook 地址再开启")
            elif channel == "telegram":
                raise HTTPException(status_code=400, detail="Telegram 缺少 Bot Token 或 Chat ID，请填写完整后再开启")
            raise HTTPException(status_code=400, detail=f"{name} 凭证或目标未配置完整，请先填写有效配置再开启")

    update_env({keys[channel]: "1" if payload.enabled else "0"})
    audit_record("channel.toggle", "success", {"channel": channel, "enabled": payload.enabled})
    return {"channel": channel, "enabled": payload.enabled, "message": f"{name} 通道已成功{'开启' if payload.enabled else '关闭'}"}


def _get_root() -> Path:
    return Path(app_attr("ROOT", ROOT))


@router.get("/api/v1/admin/gateway")
def gateway_status(x_r20_admin_token: str | None = Header(default=None), limit: int = 50) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    store = GatewayStore(GATEWAY_DB_PATH)
    pid_file = DATA_DIR / "r20_gateway.pid"
    pid = int(pid_file.read_text().strip()) if pid_file.exists() and pid_file.read_text().strip().isdigit() else 0
    running = False
    if pid:
        try:
            os.kill(pid, 0)
            running = True
        except OSError:
            pass
    return {"version": GATEWAY_VERSION, "running": running, "pid": pid or None, "stats": store.stats(), "event_health": store.event_health(), "deliveries": store.recent(limit), "scheduler": scheduler_snapshot(store)}


@router.post("/api/v1/admin/gateway/deliveries/{delivery_id}/replay")
def replay_gateway_delivery(delivery_id: int, payload: GatewayReplayRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    if payload.confirmation.strip().upper() != f"REPLAY {delivery_id}":
        raise HTTPException(status_code=400, detail=f"确认短语必须精确为：REPLAY {delivery_id}")
    store = GatewayStore(GATEWAY_DB_PATH)
    if not store.replay_dead(delivery_id):
        raise HTTPException(status_code=409, detail="仅允许重放当前处于 dead 状态的投递")
    audit_record("gateway.delivery.replay", "accepted", {"delivery_id": delivery_id})
    return {"accepted": True, "delivery_id": delivery_id, "status": "pending"}


@router.post("/api/v1/admin/gateway/jobs/{job_id}/run")
def run_gateway_job(
    job_id: str,
    payload: dict[str, Any] = Body(default={}),
    x_r20_admin_token: str | None = Header(default=None),
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
) -> dict[str, Any]:
    refresh_settings()
    actor = require_admin_header(x_r20_admin_token, x_r20_session)
    allowed_jobs = {
        "self_improvement": {
            "script": "self_improvement_engine.py",
            "args": ["--force"],
            "timeout": 180,
            "label": "自进化复盘",
        },
        "trader": {
            "script": "ai_factor_trader.py",
            "args": [],
            "timeout": 180,
            "label": "AI量化主脑决策",
        },
        "factor_library": {
            "script": "factor_library.py",
            "args": [],
            "timeout": 120,
            "label": "多因子矩阵计算",
        },
        "news": {
            "script": "news_sentiment_harvester.py",
            "args": [],
            "timeout": 120,
            "label": "全网情绪抓取",
        },
        "daily_briefing": {
            "script": "daily_summary_and_backup.py",
            "args": [],
            "timeout": 180,
            "label": "每日战报生成",
        },
    }
    job_cfg = allowed_jobs.get(job_id)
    if not job_cfg:
        raise HTTPException(status_code=404, detail=f"未找到网关任务：{job_id}")

    script_path = SCRIPTS_DIR / job_cfg["script"]
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"任务脚本不存在：{script_path}")

    cmd = [sys.executable, str(script_path), *job_cfg["args"]]
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=job_cfg["timeout"],
        )
    except subprocess.TimeoutExpired:
        audit_record(
            f"gateway.job.{job_id}.run",
            "timeout",
            {"actor": actor.get("username", "admin"), "timeout": job_cfg["timeout"]},
        )
        raise HTTPException(
            status_code=504,
            detail=f"任务执行超时（限时 {job_cfg['timeout']} 秒）",
        )

    audit_record(
        f"gateway.job.{job_id}.run",
        "success" if result.returncode == 0 else "failed",
        {"actor": actor.get("username", "admin"), "returncode": result.returncode},
    )
    if result.returncode != 0:
        err_detail = (
            result.stderr[-600:].strip()
            or result.stdout[-600:].strip()
            or "未知错误"
        )
        raise HTTPException(
            status_code=502,
            detail=f"任务执行异常（退出码 {result.returncode}）：{err_detail}",
        )

    return {
        "ok": True,
        "completed": True,
        "job_id": job_id,
        "detail": f"{job_cfg['label']}已顺利完成",
        "output": result.stdout[-2000:],
    }


@router.get("/api/v1/admin/notifications")
def admin_notifications(x_r20_session: str | None = Header(default=None, alias="X-R20-Session"), x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """频道配置读取：嵌套形状 + 凭证脱敏是 NotifyPage 的硬契约（拆分时曾被改写为
    扁平明文导致整页开关失效 + 明文外泄，2026-09-13 还原 @33cc95d^ 旧契约）。"""
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    env = notification_env()
    return {
        "webhook": {"enabled": env.get("R20_NOTIFY_WEBHOOK_ENABLED", "0") == "1", "url": mask_url(env.get("R20_NOTIFICATION_WEBHOOK", ""))},
        "wechat": {"enabled": env.get("R20_NOTIFY_WECHAT_ENABLED", "0") == "1", "webhook": mask_url(env.get("R20_WECHAT_WEBHOOK", ""))},
        "telegram": {"enabled": env.get("R20_NOTIFY_TELEGRAM_ENABLED", "0") == "1", "bot_token": mask(env.get("R20_TELEGRAM_BOT_TOKEN", "")), "chat_id": env.get("R20_TELEGRAM_CHAT_ID", ""), "api_base": env.get("R20_TELEGRAM_API_BASE", "")},
        "qq": {"enabled": env.get("R20_NOTIFY_QQ_ENABLED", "0") == "1", "app_id": env.get("R20_QQ_APP_ID", ""), "client_secret": mask(env.get("R20_QQ_CLIENT_SECRET", "")), "openid": env.get("R20_QQ_OPENID", "")},
    }


@router.put("/api/v1/admin/notifications")
def admin_update_notifications(
    payload: NotificationConfigUpdate,
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    current_env = notification_env()

    # 审计修复A2(2026-09-13)：GET 端返回 mask()/mask_url() 脱敏串，前端表单原样回传时
    # 掩码值=「用户未改动」，一律置 None 跳过写回（readiness 自然回退 current_env）。
    for _mf in ("webhook_url", "wechat_webhook", "telegram_bot_token", "qq_client_secret"):
        _mv = getattr(payload, _mf, None)
        if _mv is not None and is_masked(_mv):
            setattr(payload, _mf, None)

    env_update = {}
    if payload.webhook_url is not None:
        env_update["R20_NOTIFICATION_WEBHOOK"] = payload.webhook_url.strip()
    if payload.wechat_webhook is not None:
        env_update["R20_WECHAT_WEBHOOK"] = payload.wechat_webhook.strip()
    if payload.telegram_bot_token is not None:
        env_update["R20_TELEGRAM_BOT_TOKEN"] = payload.telegram_bot_token.strip()
    if payload.telegram_chat_id is not None:
        env_update["R20_TELEGRAM_CHAT_ID"] = payload.telegram_chat_id.strip()
    if payload.telegram_api_base is not None:
        env_update["R20_TELEGRAM_API_BASE"] = payload.telegram_api_base.strip()
    if payload.qq_app_id is not None:
        env_update["R20_QQ_APP_ID"] = payload.qq_app_id.strip()
    if payload.qq_client_secret is not None:
        env_update["R20_QQ_CLIENT_SECRET"] = payload.qq_client_secret.strip()
    if payload.qq_openid is not None:
        env_update["R20_QQ_OPENID"] = payload.qq_openid.strip()

    readiness = {
        "qq": bool((payload.qq_app_id or current_env.get("R20_QQ_APP_ID")) and (payload.qq_openid or current_env.get("R20_QQ_OPENID"))),
        "telegram": bool((payload.telegram_bot_token or current_env.get("R20_TELEGRAM_BOT_TOKEN")) and payload.telegram_chat_id),
        "wechat": bool(payload.wechat_webhook or current_env.get("R20_WECHAT_WEBHOOK")),
        "webhook": bool(payload.webhook_url or current_env.get("R20_NOTIFICATION_WEBHOOK")),
    }

    warnings = []
    eff_qq = payload.qq_enabled
    if payload.qq_enabled and not readiness["qq"]:
        eff_qq = False
        warnings.append("QQ 频道因缺少 OpenID 暂未开启（请点击「⚡ 自动获取 OpenID」绑定）")

    eff_tg = payload.telegram_enabled
    if payload.telegram_enabled and not readiness["telegram"]:
        eff_tg = False
        warnings.append("Telegram 频道因缺少 Token 或 Chat ID 暂未开启")

    eff_wx = payload.wechat_enabled
    if payload.wechat_enabled and not readiness["wechat"]:
        eff_wx = False
        warnings.append("企业微信频道因缺少 Webhook 暂未开启")

    eff_wh = payload.webhook_enabled
    if payload.webhook_enabled and not readiness["webhook"]:
        eff_wh = False
        warnings.append("通用 Webhook 因缺少 URL 暂未开启")

    env_update.update({
        "R20_NOTIFY_WEBHOOK_ENABLED": "1" if eff_wh else "0",
        "R20_NOTIFY_WECHAT_ENABLED": "1" if eff_wx else "0",
        "R20_NOTIFY_TELEGRAM_ENABLED": "1" if eff_tg else "0",
        "R20_NOTIFY_QQ_ENABLED": "1" if eff_qq else "0",
    })

    # 审计修复A2补充(2026-09-13)：对称性——toggle 把凭证写加密库(save_secrets)且 remove_env，
    # 而整页 PUT 曾把含密钥 webhook URL/token 明文落 .env（update_env），形成第二落盘。
    # 现同 toggle 一样分流：密钥性字段进密文库并从 env 拔除，env 只留开关与非敏感 ID。
    _secrets_put = {}
    for _attr, _key in (("webhook_url", "R20_NOTIFICATION_WEBHOOK"),
                        ("wechat_webhook", "R20_WECHAT_WEBHOOK"),
                        ("telegram_bot_token", "R20_TELEGRAM_BOT_TOKEN"),
                        ("qq_client_secret", "R20_QQ_CLIENT_SECRET")):
        _val = getattr(payload, _attr, None)
        if _val:
            _secrets_put[_key] = _val.strip()
            env_update.pop(_key, None)
    if _secrets_put:
        save_secrets(_secrets_put)
        remove_env(list(_secrets_put))
    for _k in [k for k, v in env_update.items() if not v.strip()]:
        remove_env({_k})
        del env_update[_k]

    update_env(env_update)
    refresh_settings()

    audit_record("notifications.update", "success", {
        "webhook": eff_wh,
        "wechat": eff_wx,
        "telegram": eff_tg,
        "qq": eff_qq,
        "warnings": warnings,
    })
    msg = "全部通知配置已成功保存"
    if warnings:
        msg += f"（提示：{'；'.join(warnings)}）"
    return {"saved": True, "message": msg, "warnings": warnings}


@router.post("/api/v1/admin/notifications/diagnose")
def diagnose_notification(payload: NotificationTestRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session"), x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token, x_r20_session)
    fn_diag = app_attr("diagnose_channel", diagnose_channel)
    result = fn_diag(payload.channel)
    audit_record("notifications.diagnose", "completed", {"channel": payload.channel, "status": result.get("status")})
    return {"channel": payload.channel, "result": result, "sent": False}


@router.post("/api/v1/admin/notifications/test")
def send_notification_test(payload: NotificationTestRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    if payload.confirmation.strip().upper() != f"SEND TEST {payload.channel.upper()}":
        raise HTTPException(status_code=400, detail=f"确认短语必须为：SEND TEST {payload.channel.upper()}")
    fn_test = app_attr("test_channel", test_channel)
    result = fn_test(payload.channel)
    audit_record("notifications.test", "completed", {"channel": payload.channel, "result": result})
    return {"channel": payload.channel, "result": result, "sent": True, "meaning": "远端接口已受理不等于用户客户端已读"}


@router.post("/api/v1/admin/notifications/qq/capture-openid/start")
def qq_capture_openid_start(payload: QQOpenIDCaptureStartRequest | None = None, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    from r20_backend.qq_bind import start_openid_capture
    app_id = payload.app_id if payload else None
    secret = payload.client_secret if payload else None
    timeout = payload.timeout if payload else 60
    try:
        res = start_openid_capture(app_id=app_id, client_secret=secret, timeout=timeout)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"启动 QQ OpenID 监听网关失败：{exc}") from exc
    audit_record("qq.capture_openid.start", "success", {"capture_id": res.get("capture_id"), "app_id": res.get("app_id")})
    return res


@router.get("/api/v1/admin/notifications/qq/capture-openid/{capture_id}")
def qq_capture_openid_poll(capture_id: str, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    from r20_backend.qq_bind import poll_openid_capture
    res = poll_openid_capture(capture_id)
    if res.get("status") == "captured":
        audit_record("qq.capture_openid.complete", "success", {"capture_id": capture_id, "openid": res.get("openid")})
    return res


@router.post("/api/v1/admin/notifications/qq/bind/start")
def qq_bind_start(x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    from r20_backend.qq_bind import create_bind_task
    try:
        task = create_bind_task()
    except Exception as exc:
        audit_record("qq.bind.start", "failed", {"error": str(exc)[:200]})
        raise HTTPException(status_code=502, detail=f"QQ 绑定任务创建失败：{exc}")
    qr_data_uri = ""
    try:
        import segno
        qr_data_uri = segno.make(task["connect_url"], error="M").png_data_uri(scale=6, border=2)
    except Exception:
        pass
    audit_record("qq.bind.start", "success", {"task_id": task["task_id"]})
    return {"task_id": task["task_id"], "qr_data_uri": qr_data_uri, "connect_url": task["connect_url"], "expires_in": task["expires_in"]}


@router.get("/api/v1/admin/notifications/qq/bind/{task_id}")
def qq_bind_poll(task_id: str, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    from r20_backend.qq_bind import poll_bind_task
    try:
        result = poll_bind_task(task_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=410, detail=str(exc))
    if result["status"] == "bound" or result["status"] == "awaiting_message":
        audit_record("qq.bind.complete", "success", {"app_id": result["app_id"], "status": result["status"], "openid_present": bool(result.get("openid"))})
    return result


@router.get("/api/v1/admin/notifications/schedule")
def notification_schedule(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    schedule = load_schedule()
    return {
        **schedule,
        "event_notifications": "开仓、平仓与风险事件实时推送，不受每日简报时间限制",
        "restart_note": "保存后调度器将在 60 秒内读取新时间，无需重启。",
    }


@router.put("/api/v1/admin/notifications/schedule")
def update_notification_schedule(payload: NotificationScheduleUpdate, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    normalized: list[str] = []
    for value in payload.briefing_times:
        value = value.strip()
        try:
            parsed = time.strptime(value, "%H:%M")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"无效时间：{value}；必须使用 HH:MM 24 小时格式") from exc
        canonical = f"{parsed.tm_hour:02d}:{parsed.tm_min:02d}"
        if canonical not in normalized:
            normalized.append(canonical)
    normalized.sort()
    schedule = load_schedule()
    schedule["briefing_times"] = normalized
    save_schedule(schedule)
    audit_record("notifications.schedule", "success", {"briefing_times": normalized, "timezone": "Asia/Shanghai"})
    return {**schedule, "saved": True, "restart_note": "调度器将在 60 秒内读取新时间。"}


@router.get("/api/v1/admin/backups/simple")
def simple_backup_config(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token)
    jobs = list_backup_jobs()
    job = next((x for x in jobs if x.get("id") == "nightly-default"), jobs[0] if jobs else None)
    if not job:
        raise HTTPException(status_code=404, detail="主灾备任务不存在")
    target = next((x for x in job.get("targets", []) if x.get("enabled")), None)
    if not target:
        target = next((x for x in job.get("targets", []) if x.get("type") == "local"), None)
    target_type = str((target or {}).get("type") or "local")
    auth_mode = str((target or {}).get("auth_mode") or "")
    legacy_bypy = target_type == "baidu" and auth_mode != "oauth"
    destination = "baidu_oauth" if target_type == "baidu" and not legacy_bypy else target_type if target_type in {"local","s3","oss","webdav"} else "local"
    validation = validate_backup_job(job)
    latest = None
    manifests_dir = _get_root() / "backups" / "manifests"
    for path in sorted(manifests_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:30] if manifests_dir.exists() else []:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            if item.get("job_id") == job["id"]:
                latest = item
                break
        except (OSError, json.JSONDecodeError):
            pass
    return {"job_id": job["id"], "target": target or {}, "enabled": job["enabled"], "schedule_time": job["schedule_times"][0], "destination": destination, "retention": int((target or {}).get("retention") or 3), "legacy_bypy": legacy_bypy, "migration_note": "当前为旧版 ByPy 配置，请选择新的保存位置后保存完成迁移" if legacy_bypy else "", "configured": bool((target or {}).get("credential_status",{}).get("configured")) if target else destination=="local", "validation": validation, "latest": latest, "advanced_preserved": True}


@router.put("/api/v1/admin/backups/simple")
def update_simple_backup(payload: SimpleBackupUpdateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    jobs = list_backup_jobs()
    job = next((x for x in jobs if x.get("id") == "nightly-default"), jobs[0] if jobs else None)
    if not job:
        raise HTTPException(status_code=404, detail="主灾备任务不存在")
    wanted_type = "baidu" if payload.destination == "baidu_oauth" else payload.destination
    existing = next((x for x in job.get("targets", []) if x.get("type") == wanted_type and (wanted_type != "baidu" or x.get("auth_mode") == "oauth")), None)
    if not existing:
        target_id = f"{wanted_type}-{__import__('uuid').uuid4().hex[:10]}"
        labels = {"local": "本地归档", "s3": "S3存储", "oss": "阿里云OSS", "webdav": "WebDAV/OpenList", "baidu": "百度网盘"}
        existing = {
            "id": target_id,
            "type": wanted_type,
            "label": labels.get(wanted_type, wanted_type.upper()),
            "credential_ref": f"backup:{target_id}",
            "enabled": False,
            "remote_path": "R20_Backups",
            "path": "backups/local",
            "retention": 3,
            "retries": 3,
            "auth_mode": "oauth" if wanted_type == "baidu" else "native",
        }
        job.setdefault("targets", []).append(existing)
    for target in job.get("targets", []):
        target["enabled"] = (target is existing)
    existing["retention"] = payload.retention if wanted_type == "local" else 0
    if wanted_type in {"s3", "oss", "webdav"}:
        existing["endpoint"] = payload.endpoint.strip()
    if wanted_type in {"s3", "oss"}:
        existing["bucket"] = payload.bucket.strip()
    if wanted_type == "baidu":
        existing["auth_mode"] = "oauth"
    if payload.credentials:
        save_backup_credentials(existing["credential_ref"], payload.credentials)
    job["enabled"] = payload.enabled
    job["schedule_times"] = [payload.schedule_time]
    try:
        saved = update_backup_job(job["id"], job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_record("backup.simple.update", "success", {"actor": actor["username"], "destination": payload.destination, "enabled": payload.enabled})
    return {"saved": True, "job": saved}


@router.post("/api/v1/admin/backups/simple/test")
def test_simple_backup(payload: SimpleBackupUpdateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    require_superadmin(x_r20_session)
    if payload.destination == "local":
        directory = (_get_root() / "backups" / "local").resolve()
        if not directory.is_relative_to((_get_root() / "backups").resolve()):
            raise HTTPException(status_code=400, detail="本地灾备目录无效：必须位于 backups/ 目录下")
        try:
            directory.mkdir(parents=True, exist_ok=True)
            test_file = directory / ".test_write.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"本地灾备目录不可写：{exc}")
        return {"status": "ready", "sent": False, "detail": "本地目录可写；未生成或上传归档"}

    wanted_type = "baidu" if payload.destination == "baidu_oauth" else payload.destination
    req_map = {
        "s3": {"access_key_id", "secret_access_key"},
        "oss": {"access_key_id", "secret_access_key"},
        "webdav": set(),
        "baidu": {"app_key", "app_secret", "refresh_token"},
    }
    if wanted_type not in req_map:
        raise HTTPException(status_code=400, detail=f"不支持的灾备目标：{payload.destination}")

    required = req_map[wanted_type]
    jobs = list_backup_jobs()
    job = next((x for x in jobs if x.get("id") == "nightly-default"), jobs[0] if jobs else None)
    existing = next((x for x in (job.get("targets", []) if job else []) if x.get("type") == wanted_type and (wanted_type != "baidu" or x.get("auth_mode") == "oauth")), None)
    saved_creds = {}
    if existing and existing.get("credential_ref"):
        try:
            from r20_backend.backup_secrets import load_credentials
            saved_creds = load_credentials(existing["credential_ref"])
        except Exception:
            saved_creds = {}

    target = {
        "type": wanted_type,
        "endpoint": (payload.endpoint or (existing.get("endpoint", "") if existing else "")).strip(),
        "bucket": (payload.bucket or (existing.get("bucket", "") if existing else "")).strip(),
        "auth_mode": "oauth" if wanted_type == "baidu" else "native",
    }
    combined_creds = {**saved_creds, **{k: v for k, v in (payload.credentials or {}).items() if str(v).strip()}}
    missing = sorted(key for key in required if not str(combined_creds.get(key) or "").strip())
    if missing:
        raise HTTPException(status_code=400, detail=f"连接信息不完整：{', '.join(missing)}")

    if wanted_type in {"s3", "oss", "webdav"}:
        if not target["endpoint"]:
            raise HTTPException(status_code=400, detail=f"{wanted_type.upper()} Endpoint 不能为空")
        try:
            from r20_backend.net_security import validate_outbound_url
            target["endpoint"] = validate_outbound_url(target["endpoint"])
        except (ValueError, Exception) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if wanted_type in {"s3", "oss"} and not target["bucket"]:
        raise HTTPException(status_code=400, detail=f"{wanted_type.upper()} Bucket 不能为空")

    return {"status": "ready", "sent": False, "detail": "配置格式与目标地址校验通过；未上传任何文件", "destination": payload.destination}


@router.get("/api/v1/admin/backup-target-types")
def backup_target_types(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token)
    return {"target_types": [
        {"type":"local","label":"本地归档","auth":"none","description":"项目 backups/ 内滚动保留"},
        {"type":"baidu","label":"百度网盘","auth":"oauth","description":"仅支持官方 OAuth，新配置不再提供 ByPy"},
        {"type":"s3","label":"S3 兼容存储","auth":"access-key","description":"AWS S3、R2、MinIO、COS 等 S3 兼容端点"},
        {"type":"oss","label":"阿里云 OSS","auth":"access-key","description":"官方 oss2 SDK"},
        {"type":"webdav","label":"WebDAV / NAS / OpenList","auth":"basic","description":"标准 WebDAV PUT/MKCOL"},
        {"type":"aliyundrive","label":"阿里云盘","auth":"webdav-or-oauth","description":"推荐开放平台或 OpenList WebDAV 桥接"},
        {"type":"quark","label":"夸克网盘（实验性）","auth":"webdav-or-experimental-oauth","description":"官方开放平台仍在内测，推荐 OpenList WebDAV 桥接"},
    ]}


@router.put("/api/v1/admin/backup-credentials")
def update_backup_credentials(payload: BackupCredentialUpdateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        status = save_backup_credentials(payload.credential_ref, payload.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_record("backup.credentials.update", "success", {"actor": actor["username"], "credential_ref": payload.credential_ref, "fields": status["fields"]})
    return {"saved": True, "credential_ref": payload.credential_ref, "status": status}


@router.get("/api/v1/admin/backup-jobs")
def backup_jobs_api(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token)
    manifests_dir = _get_root() / "backups" / "manifests"
    manifests = []
    for path in sorted(manifests_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:50] if manifests_dir.exists() else []:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            item["manifest_file"] = path.name
            manifests.append(item)
        except (OSError, json.JSONDecodeError):
            pass
    jobs = list_backup_jobs()
    for job in jobs:
        for target in job.get("targets", []):
            target["credential_status"] = backup_credential_status(str(target.get("credential_ref") or ""))
    return {"jobs": jobs, "validations": {job["id"]: validate_backup_job(job) for job in jobs}, "recent_manifests": manifests, "timezone": "Asia/Shanghai", "limits": {"maximum_jobs": 12}}


@router.post("/api/v1/admin/backup-jobs")
def create_backup_job_api(payload: BackupJobCreateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        job = create_backup_job(payload.name, payload.source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_record("backup.job.create", "success", {"actor": actor["username"], "job_id": job["id"]})
    return {"job": job}


@router.put("/api/v1/admin/backup-jobs/{job_id}")
def update_backup_job_api(job_id: str, payload: BackupJobUpdateRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        job = update_backup_job(job_id, payload.job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_record("backup.job.update", "success", {"actor": actor["username"], "job_id": job_id, "enabled": job["enabled"]})
    return {"job": job, "validation": validate_backup_job(job)}


@router.delete("/api/v1/admin/backup-jobs/{job_id}")
def delete_backup_job_api(job_id: str, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        delete_backup_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit_record("backup.job.delete", "success", {"actor": actor["username"], "job_id": job_id})
    return {"deleted": True}


@router.post("/api/v1/admin/backup-jobs/validate")
def validate_backup_job_api(payload: BackupJobUpdateRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token)
    return validate_backup_job(payload.job)


@router.post("/api/v1/admin/backup-jobs/{job_id}/run")
def run_backup_job_api(job_id: str, payload: BackupJobRunRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    if payload.confirmation.strip().upper() != f"BACKUP {job_id}".upper():
        raise HTTPException(status_code=400, detail=f"确认短语必须精确为：BACKUP {job_id}")
    try:
        get_backup_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    script = SCRIPTS_DIR / "nightly_backup_and_clean.py"
    result = subprocess.run([sys.executable, str(script), "--job-id", job_id], cwd=ROOT, text=True, capture_output=True, timeout=1800)
    BACKUP_LOG_FILE.parent.mkdir(exist_ok=True)
    BACKUP_LOG_FILE.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    audit_record("backup.job.run", "success" if result.returncode == 0 else "failed", {"actor": actor["username"], "job_id": job_id, "returncode": result.returncode})
    if result.returncode:
        raise HTTPException(status_code=502, detail=f"灾备任务失败：{result.stderr[-800:] or result.stdout[-800:]}")
    return {"completed": True, "output": result.stdout[-4000:]}


@router.get("/api/v1/admin/backup-jobs/{job_id}/export")
def export_backup_job_api(job_id: str, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_admin_header(x_r20_admin_token)
    try:
        return export_backup_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/v1/admin/backup-jobs/import")
def import_backup_job_api(payload: BackupJobImportRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    try:
        job = import_backup_job(payload.payload, payload.name_override)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_record("backup.job.import", "success", {"actor": actor["username"], "job_id": job["id"]})
    return {"job": job}


@router.post("/api/v1/admin/backup-jobs/verify")
def verify_backup_archive_api(payload: BackupVerifyRequest, x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    actor = require_superadmin(x_r20_session)
    candidate = (_get_root() / payload.archive_path).resolve()
    if not candidate.is_relative_to((_get_root() / "backups").resolve()):
        raise HTTPException(status_code=400, detail="只能验证项目 backups/ 目录内的归档")
    from scripts.backup_runtime import verify_archive
    try:
        result = verify_archive(candidate, payload.expected_sha256, payload.key_env)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    audit_record("backup.archive.verify", "success", {"actor": actor["username"], "archive": str(candidate.relative_to(_get_root())), "members": result["members"]})
    return result


@router.put("/api/v1/admin/backups/methods")
def update_backup_methods(payload: BackupMethodsUpdate, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    methods = {
        "baidu": {"enabled": payload.baidu_enabled, "retention": 0},
        "local": {"enabled": payload.local_enabled, "retention": payload.local_retention},
        "sqlite": {"enabled": payload.sqlite_enabled, "retention": payload.sqlite_retention},
    }
    if not any(item["enabled"] for item in methods.values()):
        raise HTTPException(status_code=400, detail="至少启用一种灾备方式")
    save_backup_methods(methods)
    audit_record("backup.methods.update", "success", {key: value["enabled"] for key, value in methods.items()})
    return {"saved": True, "methods": load_backup_methods()}


@router.get("/api/v1/admin/backups")
def backup_status(x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    backups_dir = _get_root() / "backups"
    archive_paths = list(backups_dir.glob("*.tar.gz")) + list((backups_dir / "local").glob("*.tar.gz")) if backups_dir.exists() else []
    local_archives = [{"name": str(item.relative_to(backups_dir)), "bytes": item.stat().st_size, "mtime": int(item.stat().st_mtime)} for item in archive_paths if item.is_file()]
    sqlite_files = list((backups_dir / "sqlite").glob("*.db")) + list((backups_dir / "sqlite").glob("*/*.db")) if (backups_dir / "sqlite").exists() else []
    sqlite_snapshots = [{"name": str(item.relative_to(backups_dir / "sqlite")), "bytes": item.stat().st_size, "mtime": int(item.stat().st_mtime)} for item in sqlite_files if item.is_file()]
    return {
        "schedule": "每天北京时间 02:00，由 Gateway Scheduler 执行全部已启用灾备方式",
        "script": str(SCRIPTS_DIR / "nightly_backup_and_clean.py"),
        "methods": load_backup_methods(),
        "jobs": list_backup_jobs(),
        "local_archives": sorted(local_archives, key=lambda item: item["mtime"], reverse=True),
        "sqlite_snapshots": sorted(sqlite_snapshots, key=lambda item: item["mtime"], reverse=True),
        "last_log": BACKUP_LOG_FILE.read_text(encoding="utf-8")[-4000:] if BACKUP_LOG_FILE.exists() else "尚无后台手动灾备日志",
    }


@router.post("/api/v1/admin/backups/run")
def run_backup(payload: BackupRequest, x_r20_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    refresh_settings()
    require_admin_header(x_r20_admin_token)
    if payload.confirmation.strip().upper() != "BACKUP R20":
        raise HTTPException(status_code=400, detail="确认短语必须精确为：BACKUP R20")
    script = SCRIPTS_DIR / "nightly_backup_and_clean.py"
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, text=True, capture_output=True, timeout=600)
    BACKUP_LOG_FILE.parent.mkdir(exist_ok=True)
    BACKUP_LOG_FILE.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        audit_record("backup.run", "failed", {"returncode": result.returncode})
        raise HTTPException(status_code=502, detail=f"灾备任务失败：{result.stderr[-800:] or result.stdout[-800:]}")
    audit_record("backup.run", "success", {})
    return {"completed": True, "output": result.stdout[-2500:]}


@router.get("/api/v1/admin/backups/download/{filename:path}")
def download_backup_archive(
    filename: str,
    token: str | None = Query(default=None),
    session: str | None = Query(default=None),
    x_r20_admin_token: str | None = Header(default=None),
    x_r20_session: str | None = Header(default=None, alias="X-R20-Session"),
) -> FileResponse:
    refresh_settings()
    effective_session = (
        (x_r20_session if isinstance(x_r20_session, str) else None)
        or (token if isinstance(token, str) else None)
        or (session if isinstance(session, str) else None)
    )
    effective_admin_token = x_r20_admin_token if isinstance(x_r20_admin_token, str) else None
    require_admin_header(effective_admin_token, effective_session)
    if ".." in Path(filename).parts:
        raise HTTPException(status_code=400, detail="非法文件路径：不能包含 ..")
    clean_name = Path(filename).name
    backups_dir = _get_root() / "backups"
    candidate = backups_dir / clean_name
    if not candidate.exists():
        candidate = backups_dir / "local" / clean_name
    if not candidate.exists():
        rel_candidate = (backups_dir / filename).resolve()
        if rel_candidate.is_relative_to(backups_dir.resolve()) and rel_candidate.exists():
            candidate = rel_candidate
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="备份文件不存在或已清理")
    if not candidate.resolve().is_relative_to(backups_dir.resolve()):
        raise HTTPException(status_code=400, detail="非法文件路径")
    audit_record("backup.download", "success", {"filename": clean_name})
    return FileResponse(
        path=str(candidate),
        media_type="application/gzip",
        filename=clean_name,
        headers={"Content-Disposition": f'attachment; filename="{clean_name}"'}
    )


@router.post("/api/v1/admin/backups/upload")
async def upload_backup_archive(file: UploadFile = File(...), x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    if not file.filename or not (file.filename.endswith(".tar.gz") or file.filename.endswith(".tgz")):
        raise HTTPException(status_code=400, detail="仅支持上传 .tar.gz 或 .tgz 格式备份包")
    clean_name = Path(file.filename).name
    if not clean_name or clean_name in {".", ".."} or ".." in clean_name:
        raise HTTPException(status_code=400, detail="非法文件名")
    target_dir = _get_root() / "backups" / "local"
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_path = target_dir / clean_name
    if not dest_path.resolve().is_relative_to(target_dir.resolve()):
        raise HTTPException(status_code=400, detail="非法文件上传路径")
    content = await file.read()
    dest_path.write_bytes(content)
    audit_record("backup.upload", "success", {"filename": clean_name, "bytes": len(content)})
    return {"uploaded": True, "filename": clean_name, "bytes": len(content), "path": str(dest_path.relative_to(_get_root()))}


@router.post("/api/v1/admin/backups/restore")
def restore_backup_archive(payload: BackupRestoreRequest, x_r20_admin_token: str | None = Header(default=None), x_r20_session: str | None = Header(default=None, alias="X-R20-Session")) -> dict[str, Any]:
    refresh_settings()
    require_superadmin(x_r20_session)
    if payload.confirmation.strip().upper() != "RESTORE R20":
        raise HTTPException(status_code=400, detail="确认短语必须精确为：RESTORE R20")
    if ".." in Path(payload.archive_name).parts:
        raise HTTPException(status_code=400, detail="非法归档文件名：不能包含 ..")
    clean_name = Path(payload.archive_name).name
    backups_dir = _get_root() / "backups"
    candidate = backups_dir / clean_name
    if not candidate.exists():
        candidate = backups_dir / "local" / clean_name
    if not candidate.exists():
        rel_candidate = (backups_dir / payload.archive_name).resolve()
        if rel_candidate.is_relative_to(backups_dir.resolve()) and rel_candidate.is_file():
            candidate = rel_candidate
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="指定的备份归档文件不存在")
    if not candidate.resolve().is_relative_to(backups_dir.resolve()):
        raise HTTPException(status_code=400, detail="指定的备份文件路径不合法")

    is_encrypted = candidate.name.endswith(".aes256")
    temp_decrypted: Path | None = None
    actual_tar = candidate
    if is_encrypted:
        key_env = getattr(payload, "key_env", "") or "R20_BACKUP_ENCRYPTION_KEY"
        if not key_env or not os.getenv(key_env):
            raise HTTPException(status_code=400, detail=f"恢复加密归档需要有效的加密密钥环境变量 ({key_env})")
        from scripts.backup_runtime import decrypt_archive
        fd, temp_name = tempfile.mkstemp(prefix="r20-restore-", suffix=".tar.gz", dir=backups_dir)
        os.close(fd)
        temp_decrypted = Path(temp_name)
        try:
            actual_tar = decrypt_archive(candidate, key_env, temp_decrypted)
        except Exception as exc:
            temp_decrypted.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"解密归档失败：{exc}") from exc

    import tarfile
    restored_files = []
    try:
        try:
            tar = tarfile.open(actual_tar, "r:gz")
        except (tarfile.TarError, OSError, EOFError) as exc:
            raise HTTPException(status_code=400, detail=f"无效或损坏的归档文件：{exc}") from exc

        with tar:
            members = tar.getmembers()
            for member in members:
                member_path = Path(member.name)
                if member.name.startswith("/") or member_path.is_absolute() or os.path.isabs(member.name):
                    raise HTTPException(status_code=400, detail=f"非法不安全归档路径 (绝对路径): {member.name}")
                if ".." in member_path.parts or ".." in member.name.replace("\\", "/").split("/"):
                    raise HTTPException(status_code=400, detail=f"非法不安全归档路径 (路径逃逸): {member.name}")
                dest_path = (_get_root() / member.name).resolve()
                if not dest_path.is_relative_to(_get_root().resolve()):
                    raise HTTPException(status_code=400, detail=f"非法越界归档路径: {member.name}")
                if member.issym() or member.islnk():
                    link_target = member.linkname
                    if os.path.isabs(link_target) or ".." in Path(link_target).parts:
                        raise HTTPException(status_code=400, detail=f"非法不安全符号链接: {member.name} -> {link_target}")
                    resolved_link = (_get_root() / Path(member.name).parent / link_target).resolve()
                    if not resolved_link.is_relative_to(_get_root().resolve()):
                        raise HTTPException(status_code=400, detail=f"符号链接指向项目外部: {member.name} -> {link_target}")
                if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                    raise HTTPException(status_code=400, detail=f"归档包含特殊设备节点: {member.name}")

            extract_kwargs = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
            for member in members:
                tar.extract(member, path=_get_root(), **extract_kwargs)
                restored_files.append(member.name)
    finally:
        if temp_decrypted and temp_decrypted.exists():
            temp_decrypted.unlink(missing_ok=True)

    audit_record("backup.restore", "success", {"filename": clean_name, "files_count": len(restored_files)})
    return {"restored": True, "filename": clean_name, "restored_count": len(restored_files), "sample_files": restored_files[:10]}
