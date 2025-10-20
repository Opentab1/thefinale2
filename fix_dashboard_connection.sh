#!/bin/bash
# Quick fix to switch from separate services to unified service

echo "========================================================================"
echo "PULSE DASHBOARD FIX"
echo "Switching to unified service so dashboard can see sensor data"
echo "========================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Must run as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

echo -e "${CYAN}Step 1: Stopping old services...${NC}"
systemctl stop pulse-hub.service 2>/dev/null || true
systemctl stop pulse-dashboard.service 2>/dev/null || true
systemctl disable pulse-hub.service 2>/dev/null || true
systemctl disable pulse-dashboard.service 2>/dev/null || true
echo -e "${GREEN}✓ Old services stopped${NC}"
echo ""

echo -e "${CYAN}Step 2: Installing unified service...${NC}"
cp /opt/pulse/services/systemd/pulse.service /etc/systemd/system/
systemctl daemon-reload
echo -e "${GREEN}✓ Service file installed${NC}"
echo ""

echo -e "${CYAN}Step 3: Enabling and starting unified service...${NC}"
systemctl enable pulse.service
systemctl start pulse.service
echo -e "${GREEN}✓ Unified service started${NC}"
echo ""

echo -e "${CYAN}Step 4: Checking status...${NC}"
sleep 3
systemctl status pulse.service --no-pager -l | head -15
echo ""

echo "========================================================================"
echo -e "${GREEN}FIX APPLIED!${NC}"
echo "========================================================================"
echo ""
echo "The dashboard should now show sensor data."
echo "Wait 30 seconds for first readings, then check:"
echo ""
echo -e "${CYAN}Dashboard: ${NC}http://localhost:8080"
echo ""
echo "To check logs:"
echo "  sudo journalctl -u pulse -f"
echo ""
echo "To check status:"
echo "  sudo systemctl status pulse"
echo ""
