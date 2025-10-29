#!/bin/bash
################################################################################
# Pulse Local Dashboard - Auto-start Installer/Starter
# - Installs dependencies into venv
# - Creates/enables a systemd service to run on boot
# - Starts the service now
################################################################################
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Setting up Pulse Local Dashboard auto-start...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$ROOT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
SERVICE_NAME="pulse-local-dashboard.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUN_USER="$(whoami)"

# 1) Install system dependencies (best-effort)
if command -v apt-get &> /dev/null; then
  echo -e "${YELLOW}Installing system packages...${NC}"
  sudo apt-get update -qq
  sudo apt-get install -y python3 python3-venv python3-pip > /dev/null 2>&1 || true
fi

# 2) Python venv + deps
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
if [ -f "$ROOT_DIR/requirements.txt" ]; then
  "$VENV_DIR/bin/pip" install --quiet -r "$ROOT_DIR/requirements.txt"
fi
# Ensure required packages exist even if not listed
"$VENV_DIR/bin/pip" install --quiet Flask paho-mqtt

# 3) Create systemd service
UNIT_CONTENT="[Unit]
Description=Pulse Local Dashboard (Flask)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PYTHON_BIN rpi/local_server.py
Restart=always
User=$RUN_USER

[Install]
WantedBy=multi-user.target
"

echo -e "${YELLOW}Writing systemd unit to ${SERVICE_PATH}...${NC}"
echo "$UNIT_CONTENT" | sudo tee "$SERVICE_PATH" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME" || sudo systemctl start "$SERVICE_NAME"

sleep 1
if systemctl is-active --quiet "$SERVICE_NAME"; then
  echo -e "${GREEN}✅ Service running. Dashboard: http://localhost:8080${NC}"
else
  echo -e "${RED}❌ Service failed to start. Check: sudo journalctl -u ${SERVICE_NAME} -f${NC}"
fi

# Also print quick manual run
echo -e "${YELLOW}Manual run (without systemd):${NC}"
echo -e "${BLUE}$PYTHON_BIN rpi/local_server.py${NC}"
