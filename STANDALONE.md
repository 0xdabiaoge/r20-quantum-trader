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

No HTTP trade-trigger endpoint is exposed. Trade execution stays inside the scheduler-launched, file-locked execution process.

## systemd

Copy `deploy/r20-quantum.service` and `deploy/r20-scheduler.service` to `/etc/systemd/system/`, update `WorkingDirectory` and `EnvironmentFile`, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now r20-quantum r20-scheduler
```

Before enabling `r20-scheduler`, disable the old QwenPaw cron jobs to prevent duplicate execution. Do not run both schedulers simultaneously.
