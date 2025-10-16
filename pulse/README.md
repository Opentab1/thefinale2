# Pulse 1.0 (Skeleton)

This repository contains a runnable skeleton for Pulse on Raspberry Pi 5.

- One-line install (replace <ORG>/<REPO>):

```bash
curl -fsSL https://raw.githubusercontent.com/<ORG>/<REPO>/main/install.sh | sudo bash
```

- Services: FastAPI hub, Node dashboard API, React UI, sensor daemons, health monitor.
- Kiosk: Chromium launches to `http://localhost:8080` on boot.

Dev quickstart:
- Hub: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && CONFIG_FILE=./config/config.yaml uvicorn services.hub.main:app --host 0.0.0.0 --port 7000`
- UI: `cd dashboard/ui && npm install && npm run build`
- API: `cd dashboard/api && npm install && node server.js`

Systemd units are in `services/systemd/` and are installed by `install.sh`.
