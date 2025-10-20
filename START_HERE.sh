#!/bin/bash
set -euo pipefail

# ==============================================================================
# PULSE SYSTEM - MAIN STARTUP SCRIPT
# ==============================================================================
# This script will:
# 1. Start the Pulse Hub with FULL debug output to terminal
# 2. Start the Dashboard API server
# 3. Open the user-friendly web interface in browser
# 
# You will see EXACTLY what is happening with all sensors in the terminal!
# ==============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

clear

echo -e "${PURPLE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   ██████╗ ██╗   ██╗██╗     ███████╗███████╗    ███████╗██╗   ██╗███████╗ ║
║   ██╔══██╗██║   ██║██║     ██╔════╝██╔════╝    ██╔════╝╚██╗ ██╔╝██╔════╝ ║
║   ██████╔╝██║   ██║██║     ███████╗█████╗      ███████╗ ╚████╔╝ ███████╗ ║
║   ██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝      ╚════██║  ╚██╔╝  ╚════██║ ║
║   ██║     ╚██████╔╝███████╗███████║███████╗    ███████║   ██║   ███████║ ║
║   ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝    ╚══════╝   ╚═╝   ╚══════╝ ║
║                                                                           ║
║                    Smart Venue Automation System                         ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo ""
echo -e "${WHITE}Starting Pulse System with Debug Output...${NC}"
echo ""

# Auto-detect Pulse installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Try to find Pulse installation
if [ -d "$SCRIPT_DIR/services" ]; then
    WORKSPACE_DIR="$SCRIPT_DIR"
elif [ -d "/workspace/services" ]; then
    WORKSPACE_DIR="/workspace"
elif [ -d "/opt/pulse/services" ]; then
    WORKSPACE_DIR="/opt/pulse"
elif [ -d "$HOME/pulse/services" ]; then
    WORKSPACE_DIR="$HOME/pulse"
else
    echo -e "${RED}Error: Cannot find Pulse installation${NC}"
    echo "Please run this script from the Pulse directory"
    exit 1
fi

echo -e "${GREEN}Found Pulse at: $WORKSPACE_DIR${NC}"
cd "$WORKSPACE_DIR"

# Determine Python executable
if [ -f "$WORKSPACE_DIR/venv/bin/python3" ]; then
    PYTHON="$WORKSPACE_DIR/venv/bin/python3"
    echo -e "${GREEN}✓ Found virtual environment${NC}"
elif [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON="/opt/pulse/venv/bin/python3"
    echo -e "${GREEN}✓ Found virtual environment at /opt/pulse${NC}"
else
    PYTHON="python3"
    echo -e "${YELLOW}⚠ Using system Python${NC}"
fi

echo -e "${CYAN}Python: ${NC}$PYTHON"
echo ""

# Create necessary directories
echo -e "${CYAN}Setting up directories...${NC}"
mkdir -p /var/log/pulse
mkdir -p /opt/pulse/data
mkdir -p "$WORKSPACE_DIR/data"
echo -e "${GREEN}✓ Directories ready${NC}"
echo ""

# Kill any existing processes
echo -e "${CYAN}Checking for existing processes...${NC}"
if pkill -0 -f "python.*hub/main.py" 2>/dev/null; then
    echo -e "${YELLOW}  Stopping existing hub...${NC}"
    pkill -f "python.*hub/main.py" || true
    sleep 1
fi
if pkill -0 -f "python.*dashboard/api/server.py" 2>/dev/null; then
    echo -e "${YELLOW}  Stopping existing dashboard...${NC}"
    pkill -f "python.*dashboard/api/server.py" || true
    sleep 1
fi
echo -e "${GREEN}✓ Ready to start${NC}"
echo ""

# Set environment
export PYTHONPATH="$WORKSPACE_DIR:$WORKSPACE_DIR/services"
export PULSE_DEBUG=1

# Function to open browser after delay
open_browser() {
    sleep 5  # Wait for services to start
    
    echo ""
    echo -e "${CYAN}Opening web dashboard...${NC}"
    
    if command -v chromium-browser >/dev/null 2>&1; then
        chromium-browser --new-window http://localhost:8080 >/dev/null 2>&1 &
    elif command -v chromium >/dev/null 2>&1; then
        chromium --new-window http://localhost:8080 >/dev/null 2>&1 &
    elif command -v firefox >/dev/null 2>&1; then
        firefox http://localhost:8080 >/dev/null 2>&1 &
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:8080 >/dev/null 2>&1 &
    else
        echo -e "${YELLOW}⚠ No browser found. Please open http://localhost:8080 manually${NC}"
    fi
}

# Cleanup function
cleanup() {
    echo ""
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Shutting down Pulse System...${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    
    pkill -f "python.*hub/main.py" || true
    pkill -f "python.*dashboard/api/server.py" || true
    pkill -f "python.*run_pulse_system.py" || true
    
    echo -e "${GREEN}✓ All processes stopped${NC}"
    echo -e "${WHITE}Goodbye!${NC}"
    echo ""
    exit 0
}

trap cleanup SIGINT SIGTERM

# Open browser in background
(open_browser) &

# Display info
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${WHITE}SYSTEM INFORMATION${NC}"
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}Dashboard URL:    ${NC}http://localhost:8080"
echo -e "${CYAN}API Endpoint:     ${NC}http://localhost:8080/api/status"
echo -e "${CYAN}Log Directory:    ${NC}/var/log/pulse/"
echo -e "${CYAN}Data Directory:   ${NC}/opt/pulse/data/"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the system${NC}"
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo ""

# Start the integrated system
echo -e "${WHITE}Starting Pulse Hub and Dashboard...${NC}"
echo ""

exec $PYTHON "$WORKSPACE_DIR/run_pulse_system.py"
