#!/bin/bash
# Complete Update Script - Fixes All Sensors

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "========================================================================"
echo "PULSE COMPLETE UPDATE - FIX ALL SENSORS"
echo "========================================================================"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

echo -e "${CYAN}Step 1: Stopping all services...${NC}"
systemctl stop pulse.service 2>/dev/null || true
systemctl stop pulse-hub.service 2>/dev/null || true
systemctl stop pulse-dashboard.service 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Services stopped${NC}"
echo ""

echo -e "${CYAN}Step 2: Updating code from GitHub...${NC}"
cd /opt/pulse
sudo -u pi git fetch origin
sudo -u pi git reset --hard origin/main
sudo -u pi git pull origin main
echo -e "${GREEN}✓ Code updated to latest${NC}"
echo ""

echo -e "${CYAN}Step 3: Updating Python dependencies...${NC}"
sudo -u pi /opt/pulse/venv/bin/pip install --upgrade pip
sudo -u pi /opt/pulse/venv/bin/pip install -r requirements.txt --upgrade
echo -e "${GREEN}✓ Dependencies updated${NC}"
echo ""

echo -e "${CYAN}Step 4: Installing unified service...${NC}"
cp /opt/pulse/services/systemd/pulse.service /etc/systemd/system/
systemctl daemon-reload
systemctl disable pulse-hub.service 2>/dev/null || true
systemctl disable pulse-dashboard.service 2>/dev/null || true
systemctl enable pulse.service
echo -e "${GREEN}✓ Unified service installed${NC}"
echo ""

echo -e "${CYAN}Step 5: Starting Pulse...${NC}"
systemctl start pulse.service
sleep 3
echo -e "${GREEN}✓ Pulse started${NC}"
echo ""

echo -e "${CYAN}Step 6: Checking status...${NC}"
systemctl status pulse.service --no-pager -l | head -15
echo ""

echo "========================================================================"
echo -e "${GREEN}UPDATE COMPLETE!${NC}"
echo "========================================================================"
echo ""
echo "Wait 30 seconds for all sensors to initialize, then check:"
echo ""
echo -e "${CYAN}Dashboard:${NC} http://localhost:8080"
echo ""
echo "Expected sensor data:"
echo "  ✓ Light Level - Real lux values"
echo "  ✓ Decibel - Real dB readings (every 2 seconds)"
echo "  ✓ Temperature - From BME280 at 0x77"
echo "  ✓ Humidity - From BME280"
echo "  ✓ Song Detection - Every 30 seconds"
echo ""
echo "To check logs:"
echo "  sudo journalctl -u pulse -f"
echo ""
echo "To check sensor readings:"
echo "  tail -50 /var/log/pulse/pulse.log | grep -E 'Audio:|Light level:|Temperature:|Song'"
echo ""
