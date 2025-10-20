#!/bin/bash
set -euo pipefail

# Pulse System Startup Script
# This script starts the hub with terminal debugging AND opens the dashboard

echo "=========================================="
echo "PULSE SYSTEM STARTUP"
echo "=========================================="
echo ""

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Set working directory
PULSE_DIR="/workspace"
cd "$PULSE_DIR"

# Ensure log directory exists
mkdir -p /var/log/pulse
mkdir -p /opt/pulse/data

# Kill any existing instances
echo -e "${YELLOW}Stopping any existing Pulse processes...${NC}"
pkill -f "python.*hub/main.py" || true
pkill -f "python.*dashboard/api/server.py" || true
sleep 2

# Set Python path
export PYTHONPATH="$PULSE_DIR:$PULSE_DIR/services"

# Determine Python executable
if [ -f "$PULSE_DIR/venv/bin/python3" ]; then
    PYTHON="$PULSE_DIR/venv/bin/python3"
elif [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON="/opt/pulse/venv/bin/python3"
else
    PYTHON="python3"
fi

echo -e "${GREEN}Using Python: $PYTHON${NC}"
echo ""

# Function to run hub in terminal
run_hub() {
    echo -e "${CYAN}=========================================="
    echo -e "STARTING PULSE HUB (Debug Mode)"
    echo -e "==========================================${NC}"
    echo ""
    
    cd "$PULSE_DIR"
    exec $PYTHON services/hub/main.py 2>&1 | while IFS= read -r line; do
        # Color-code the output based on log level
        if [[ $line == *"ERROR"* ]]; then
            echo -e "${RED}$line${NC}"
        elif [[ $line == *"WARNING"* ]]; then
            echo -e "${YELLOW}$line${NC}"
        elif [[ $line == *"✓"* ]] || [[ $line == *"SUCCESS"* ]]; then
            echo -e "${GREEN}$line${NC}"
        elif [[ $line == *"="* ]]; then
            echo -e "${PURPLE}$line${NC}"
        elif [[ $line == *"Starting"* ]] || [[ $line == *"Initializing"* ]]; then
            echo -e "${CYAN}$line${NC}"
        else
            echo "$line"
        fi
    done
}

# Function to run dashboard in background
run_dashboard() {
    echo -e "${CYAN}Starting Dashboard API Server...${NC}"
    cd "$PULSE_DIR"
    $PYTHON dashboard/api/server.py > /var/log/pulse/dashboard.log 2>&1 &
    DASHBOARD_PID=$!
    echo -e "${GREEN}Dashboard started (PID: $DASHBOARD_PID)${NC}"
    echo "$DASHBOARD_PID" > /tmp/pulse-dashboard.pid
}

# Function to open browser
open_browser() {
    echo -e "${CYAN}Opening browser to dashboard...${NC}"
    sleep 3  # Wait for services to start
    
    # Detect browser
    if command -v chromium-browser >/dev/null 2>&1; then
        BROWSER="chromium-browser"
    elif command -v chromium >/dev/null 2>&1; then
        BROWSER="chromium"
    elif command -v firefox >/dev/null 2>&1; then
        BROWSER="firefox"
    else
        echo -e "${YELLOW}No browser found, skipping auto-open${NC}"
        return
    fi
    
    # Open browser in background
    $BROWSER http://localhost:8080 >/dev/null 2>&1 &
    echo -e "${GREEN}Browser opened${NC}"
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}=========================================="
    echo -e "STOPPING PULSE SYSTEM"
    echo -e "==========================================${NC}"
    
    # Stop dashboard
    if [ -f /tmp/pulse-dashboard.pid ]; then
        DASHBOARD_PID=$(cat /tmp/pulse-dashboard.pid)
        if kill -0 "$DASHBOARD_PID" 2>/dev/null; then
            echo -e "${YELLOW}Stopping dashboard (PID: $DASHBOARD_PID)...${NC}"
            kill "$DASHBOARD_PID" || true
        fi
        rm -f /tmp/pulse-dashboard.pid
    fi
    
    # Stop any remaining processes
    pkill -f "python.*hub/main.py" || true
    pkill -f "python.*dashboard/api/server.py" || true
    
    echo -e "${GREEN}Pulse system stopped${NC}"
    exit 0
}

# Register cleanup handler
trap cleanup SIGINT SIGTERM EXIT

# Start dashboard in background
run_dashboard

# Open browser in background (after short delay)
(open_browser) &

echo ""
echo -e "${GREEN}=========================================="
echo -e "SYSTEM STARTUP COMPLETE"
echo -e "==========================================${NC}"
echo -e "${CYAN}Dashboard: ${NC}http://localhost:8080"
echo -e "${CYAN}Logs: ${NC}/var/log/pulse/"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Run hub in foreground with colored output
run_hub
