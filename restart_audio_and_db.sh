#!/bin/bash
#
# Quick Restart Script for DB Reader and Song Detection
# 
# This script restarts ONLY the audio monitoring and database components
# of the Pulse system without a full system restart.
#

set -e

echo "======================================================================"
echo "  PULSE - Restart DB Reader & Song Detection"
echo "======================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as correct user
if [ "$EUID" -eq 0 ]; then 
    echo -e "${YELLOW}Warning: Running as root. Consider running as 'pi' user.${NC}"
fi

echo -e "${YELLOW}[1/3]${NC} Stopping Pulse service..."
sudo systemctl stop pulse.service 2>/dev/null || {
    echo -e "${YELLOW}Note: pulse.service not running or doesn't exist${NC}"
}

# Give it a moment to fully stop
sleep 2

echo -e "${YELLOW}[2/3]${NC} Cleaning up any stuck processes..."
# Kill any lingering python processes related to pulse
pkill -f "run_pulse_system.py" 2>/dev/null || true
pkill -f "services/hub/main.py" 2>/dev/null || true
pkill -f "mic_song_detect.py" 2>/dev/null || true
pkill -f "song_detector.py" 2>/dev/null || true

# Give processes time to terminate
sleep 1

echo -e "${YELLOW}[3/3]${NC} Starting Pulse service..."
sudo systemctl start pulse.service

# Wait a moment for startup
sleep 3

# Check if it started successfully
if sudo systemctl is-active --quiet pulse.service; then
    echo ""
    echo -e "${GREEN}✓ SUCCESS!${NC} Pulse service restarted"
    echo ""
    echo "Checking component status..."
    sleep 2
    
    # Check if the main process is running
    if pgrep -f "run_pulse_system.py" > /dev/null; then
        echo -e "  ${GREEN}✓${NC} Main Pulse process running"
    else
        echo -e "  ${RED}✗${NC} Main Pulse process NOT detected"
    fi
    
    # Check logs for audio monitor startup
    echo ""
    echo "Recent logs (last 20 lines):"
    echo "----------------------------------------------------------------------"
    sudo journalctl -u pulse.service -n 20 --no-pager | tail -20
    echo "----------------------------------------------------------------------"
    echo ""
    echo -e "${GREEN}Restart complete!${NC}"
    echo ""
    echo "To monitor live logs, run:"
    echo "  sudo journalctl -u pulse.service -f"
    echo ""
    echo "To check full status:"
    echo "  sudo systemctl status pulse.service"
    echo ""
else
    echo ""
    echo -e "${RED}✗ ERROR:${NC} Pulse service failed to start"
    echo ""
    echo "Check status with:"
    echo "  sudo systemctl status pulse.service"
    echo ""
    echo "View full logs with:"
    echo "  sudo journalctl -u pulse.service -n 50"
    exit 1
fi

echo "======================================================================"
