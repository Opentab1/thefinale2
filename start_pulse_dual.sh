#!/bin/bash
set -euo pipefail

# Pulse System Startup Script - Dual Terminal Mode
# This script opens TWO terminals: one for Hub, one for Dashboard

echo "=========================================="
echo "PULSE SYSTEM STARTUP - DUAL TERMINAL MODE"
echo "=========================================="
echo ""

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Set working directory
PULSE_DIR="/workspace"
cd "$PULSE_DIR"

# Ensure directories exist
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

# Check if we have a terminal emulator available
if command -v gnome-terminal >/dev/null 2>&1; then
    TERMINAL="gnome-terminal"
    TERM_CMD="--"
elif command -v xterm >/dev/null 2>&1; then
    TERMINAL="xterm"
    TERM_CMD="-e"
elif command -v lxterminal >/dev/null 2>&1; then
    TERMINAL="lxterminal"
    TERM_CMD="-e"
else
    echo -e "${RED}No terminal emulator found. Falling back to single terminal mode.${NC}"
    exec bash "$PULSE_DIR/start_pulse.sh"
    exit 0
fi

echo -e "${CYAN}Using terminal: $TERMINAL${NC}"

# Create wrapper scripts for colored output
cat > /tmp/pulse_hub_runner.sh << 'EOFHUB'
#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

PULSE_DIR="/workspace"
cd "$PULSE_DIR"

# Determine Python
if [ -f "$PULSE_DIR/venv/bin/python3" ]; then
    PYTHON="$PULSE_DIR/venv/bin/python3"
elif [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON="/opt/pulse/venv/bin/python3"
else
    PYTHON="python3"
fi

export PYTHONPATH="$PULSE_DIR:$PULSE_DIR/services"

echo -e "${PURPLE}=========================================="
echo -e "PULSE HUB - DEBUG CONSOLE"
echo -e "==========================================${NC}"
echo ""

$PYTHON services/hub/main.py 2>&1 | while IFS= read -r line; do
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

echo ""
echo -e "${RED}Hub process terminated. Press Enter to close.${NC}"
read
EOFHUB

cat > /tmp/pulse_dashboard_runner.sh << 'EOFDASH'
#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

PULSE_DIR="/workspace"
cd "$PULSE_DIR"

# Determine Python
if [ -f "$PULSE_DIR/venv/bin/python3" ]; then
    PYTHON="$PULSE_DIR/venv/bin/python3"
elif [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON="/opt/pulse/venv/bin/python3"
else
    PYTHON="python3"
fi

export PYTHONPATH="$PULSE_DIR:$PULSE_DIR/services"

echo -e "${PURPLE}=========================================="
echo -e "PULSE DASHBOARD API - DEBUG CONSOLE"
echo -e "==========================================${NC}"
echo ""

$PYTHON dashboard/api/server.py 2>&1 | while IFS= read -r line; do
    if [[ $line == *"ERROR"* ]]; then
        echo -e "${RED}$line${NC}"
    elif [[ $line == *"WARNING"* ]]; then
        echo -e "${YELLOW}$line${NC}"
    elif [[ $line == *"✓"* ]] || [[ $line == *"started"* ]] || [[ $line == *"Running"* ]]; then
        echo -e "${GREEN}$line${NC}"
    elif [[ $line == *"="* ]]; then
        echo -e "${PURPLE}$line${NC}"
    else
        echo "$line"
    fi
done

echo ""
echo -e "${RED}Dashboard process terminated. Press Enter to close.${NC}"
read
EOFDASH

chmod +x /tmp/pulse_hub_runner.sh
chmod +x /tmp/pulse_dashboard_runner.sh

# Start Hub terminal
echo -e "${CYAN}Opening Hub terminal...${NC}"
if [ "$TERMINAL" = "gnome-terminal" ]; then
    gnome-terminal --title="Pulse Hub - Debug Console" -- bash /tmp/pulse_hub_runner.sh &
else
    $TERMINAL $TERM_CMD "bash /tmp/pulse_hub_runner.sh" &
fi
sleep 1

# Start Dashboard terminal
echo -e "${CYAN}Opening Dashboard terminal...${NC}"
if [ "$TERMINAL" = "gnome-terminal" ]; then
    gnome-terminal --title="Pulse Dashboard - Debug Console" -- bash /tmp/pulse_dashboard_runner.sh &
else
    $TERMINAL $TERM_CMD "bash /tmp/pulse_dashboard_runner.sh" &
fi
sleep 3

# Open browser
echo -e "${CYAN}Opening browser...${NC}"
if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser http://localhost:8080 >/dev/null 2>&1 &
elif command -v chromium >/dev/null 2>&1; then
    chromium http://localhost:8080 >/dev/null 2>&1 &
elif command -v firefox >/dev/null 2>&1; then
    firefox http://localhost:8080 >/dev/null 2>&1 &
else
    echo -e "${YELLOW}No browser found${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo -e "PULSE SYSTEM STARTED"
echo -e "==========================================${NC}"
echo -e "${CYAN}Dashboard URL: ${NC}http://localhost:8080"
echo -e "${CYAN}Hub Terminal: ${NC}Check the 'Pulse Hub' window"
echo -e "${CYAN}Dashboard Terminal: ${NC}Check the 'Pulse Dashboard' window"
echo ""
echo -e "${YELLOW}To stop: Close the terminal windows or run:${NC}"
echo -e "${YELLOW}  pkill -f 'python.*hub/main.py'${NC}"
echo -e "${YELLOW}  pkill -f 'python.*dashboard/api/server.py'${NC}"
echo ""
