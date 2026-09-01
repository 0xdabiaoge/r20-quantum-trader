# R20 Quantum Trader v5.4.2 Standalone Deployment

v5.4.2 removes the runtime dependency on QwenPaw. The product is now composed of:

- `r20_backend.app`: standalone FastAPI control plane and read-only monitoring API.
- `r20_backend.scheduler`: standalone scheduler for the 15-minute trader, 60-second factor refresh, 10-minute news refresh, daily reports, evolution review, and nightly backup.
- `scripts/`: strategy and execution modules, run as isolated Python processes.
- `.env`: only source for LLM, OKX, and optional notification credentials.

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
chmod 600 .env
```

Set `LLM_*` and `OKX_*` credentials in `.env`. Never commit this file.

Before the first launch, set a random `R20_SETUP_TOKEN` in `.env`. Open `/admin`, enter it to unlock the setup page, then set a permanent administrator token. The page never displays configured secret values. `.env` is written atomically and set to permission mode `0600`.

The standalone backend uses `OKX_*` for native read-only REST calls. Existing strategy execution remains on the local OKX CLI bridge during this migration phase; move that bridge's credentials to the target host before enabling the scheduler.

## Run Locally

Terminal 1:

```sh
. .venv/bin/activate
python -m uvicorn r20_backend.app:app --host 0.0.0.0 --port 8080
```

Terminal 2:

```sh
. .venv/bin/activate
python -m r20_backend.scheduler
```

The backend exposes only read-only control-plane endpoints:

- `GET /api/v1/health`
- `GET /api/v1/status`
- `GET /api/v1/cache/{decisions|factors|ledger|sentiment|self-improvement}`
- `GET /api/v1/market/{instId}`
- `GET /api/v1/account/positions`

No HTTP trade-trigger endpoint is exposed except the separately enabled, confirmation-protected manual close action. The admin console also supports a protected update check and `git pull --ff-only`; it refuses to update a dirty worktree and never restarts services automatically.

## QwenPaw Container Coexistence

When `www.r20.cn` is already reverse-proxied into a QwenPaw container, keep QwenPaw on its existing port and let the R20 standalone gateway own port `8080`. `r20_backend.app` mounts the existing dashboard at `/`, while `/admin` and `/api/v1/*` remain R20-native routes. This preserves the hostname, reverse-proxy rules, dashboard paths, QwenPaw process, and QwenPaw backup layout.

Add the `[program:r20-backend]` block from the container supervisor configuration and restart the container during a maintenance window so supervisord adopts it. Do not run the legacy `dashboard.app` Uvicorn process at the same time as `r20_backend.app`.

## systemd

Copy `deploy/r20-quantum.service` and `deploy/r20-scheduler.service` to `/etc/systemd/system/`, update `WorkingDirectory` and `EnvironmentFile`, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now r20-quantum r20-scheduler
```

Before enabling `r20-scheduler`, disable the old QwenPaw cron jobs to prevent duplicate execution. Do not run both schedulers simultaneously.
