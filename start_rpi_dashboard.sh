#!/bin/bash
# Pulse RPi Local Dashboard Startup Script
# Ensures dashboard starts with all dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Pulse RPi Local Dashboard..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3."
    exit 1
fi

# Install Flask if missing
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask dependencies..."
    pip3 install flask flask-cors --user
fi

# Kill any existing dashboard process
pkill -f "rpi/local_dashboard.py" 2>/dev/null || true
sleep 1

# Start dashboard
echo "✅ Starting dashboard on port 8080..."
nohup python3 rpi/local_dashboard.py > /tmp/pulse_dashboard.log 2>&1 &
DASHBOARD_PID=$!

sleep 2

# Verify it's running
if ps -p $DASHBOARD_PID > /dev/null; then
    echo "✅ Dashboard started successfully (PID: $DASHBOARD_PID)"
    echo ""
    echo "📊 Access your dashboard at:"
    echo "   - http://localhost:8080"
    echo "   - http://$(hostname -I | awk '{print $1}'):8080"
    echo ""
    echo "📝 Logs: tail -f /tmp/pulse_dashboard.log"
else
    echo "❌ Dashboard failed to start. Check logs:"
    cat /tmp/pulse_dashboard.log
    exit 1
fi
