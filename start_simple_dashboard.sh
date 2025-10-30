#!/bin/bash
# Start Simple Local Dashboard
# NO AWS • NO Auth • Just Real Sensor Data

set -e

echo "🎵 Pulse Simple Local Dashboard"
echo "================================"
echo ""

# Kill any existing dashboards on port 8080
echo "Stopping existing dashboard..."
sudo pkill -f "dashboard" 2>/dev/null || true
sudo pkill -f "port 8080" 2>/dev/null || true
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 2

# Find the right Python and paths
if [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON="/opt/pulse/venv/bin/python3"
    cd /opt/pulse
elif [ -f "/workspace/rpi/simple_local_dashboard.py" ]; then
    PYTHON="python3"
    cd /workspace
else
    echo "❌ Cannot find dashboard. Are you on the Pi?"
    exit 1
fi

echo "Starting simple local dashboard..."
echo ""

# Start the dashboard
$PYTHON rpi/simple_local_dashboard.py &
PID=$!

sleep 3

# Check if it's running
if ps -p $PID > /dev/null; then
    echo "✅ Dashboard started successfully!"
    echo ""
    echo "📊 Access your dashboard at:"
    echo "   http://localhost:8080"
    echo "   http://$(hostname -I | awk '{print $1}'):8080"
    echo ""
    echo "📡 This dashboard reads REAL sensor data from your Pi:"
    echo "   • Temperature & Humidity (BME280)"
    echo "   • Light levels"
    echo "   • Sound/noise levels"
    echo "   • Current music (from database)"
    echo ""
    echo "💡 No AWS, no auth, no complexity - just local sensor data!"
    echo ""
    echo "To stop: sudo pkill -f simple_local_dashboard"
else
    echo "❌ Failed to start dashboard"
    exit 1
fi
