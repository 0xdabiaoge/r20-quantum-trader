# R20 Quantum Trader v6.1.0 Preview Standalone Deployment

v6.1.0-preview removes the runtime dependency on QwenPaw. The product is now composed of:

- `r20_backend.app`: standalone FastAPI control plane and read-only monitoring API.
- `r20_gateway.worker`: the R20-native, single-owner scheduler and durable notification-delivery worker for the 15-minute trader, 60-second factor refresh, 10-minute news refresh, daily reports, evolution review, and nightly backup.
- `scripts/`: strategy and execution modules, run as isolated Python processes.
- `.env` + encrypted R20 Secret Store: LLM, optional OKX API Key, and notification credentials.
- Official `okx` CLI: required by the strategy execution path. CLI OAuth is an optional local credential source and is bound to the Linux service user's `HOME`.

## Install

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm install -g @okx_ai/okx-trade-cli@^1.4.4
cp env.example .env
chmod 600 .env
python scripts/r20_okx_setup.py  # read-only preflight; READY is required
```

Set `LLM_*` and `OKX_*` credentials in `.env`. Never commit this file.

Before the first launch, set a random `R20_SETUP_TOKEN` in `.env`. Open `/admin`, enter it to unlock the setup page, then set a permanent administrator token. The page never displays configured secret values. `.env` is written atomically and set to permission mode `0600`.

R20 does not execute QwenPaw Skills. The strategy process calls the official `okx` CLI directly, while the control plane prefers signed OKX V5 requests when an environment-specific API Key is configured and otherwise uses safe CLI fallback paths.

Choose one credential model:

1. **Environment-specific API Key (recommended for servers):** create separate LIVE and DEMO keys, configure them in `/admin`, never grant withdrawal permission, and bind the key to the server IP where possible.
2. **CLI OAuth (personal single-user deployment):** as the same Linux user that runs both services, run `okx config show --json`, `okx auth status --json`, explicitly choose `global` / `eea` / `us` / `tr`, then run `okx auth login --manual --site <site>`. Complete the browser device flow and run `python scripts/r20_okx_setup.py`.

Never copy or publish another installation's `~/.okx/`; it contains machine-local authorization state. Both services must use the same `User`, `HOME`, and a `PATH` containing the `okx` binary. The supplied systemd units use the dedicated `r20` user and `/home/r20`; adjust both units together if your deployment user differs.

## Run Locally

Terminal 1:

```sh
. .venv/bin/activate
python -m uvicorn r20_backend.app:app --host 0.0.0.0 --port 8080
```

Terminal 2:

```sh
. .venv/bin/activate
python -m r20_gateway.worker
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

Copy `deploy/r20-quantum.service` and `deploy/r20-gateway.service` to `/etc/systemd/system/`, update `WorkingDirectory` and `EnvironmentFile`, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now r20-quantum r20-gateway
```

Before enabling `r20-gateway`, disable the old QwenPaw cron jobs to prevent duplicate execution. Do not run both schedulers simultaneously. The current Gateway worker owns the scheduler; the legacy `r20_backend.scheduler` and `deploy/r20-scheduler.service` are retained only for compatibility and must not run alongside it.

Before starting the Gateway, verify dependency visibility under the exact service identity:

```sh
sudo -u r20 env HOME=/home/r20 PATH=/opt/r20-quantum-trader/.venv/bin:/usr/local/bin:/usr/bin:/bin \
  /opt/r20-quantum-trader/.venv/bin/python /opt/r20-quantum-trader/scripts/r20_okx_setup.py
```

If this is not `READY`, keep the Gateway stopped. Do not solve it by copying a developer's `.okx` directory.
