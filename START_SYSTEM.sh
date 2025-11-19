#!/bin/bash
# Pulse System - Quick Start Script

echo "========================================"
echo "   🏠 PULSE SYSTEM - STARTING"
echo "========================================"
echo ""

cd /workspace

# Check if hub is already running
if pgrep -f "run_hub_service.py" > /dev/null; then
    echo "✓ Hub service is already running"
else
    echo "Starting hub service..."
    source venv/bin/activate
    python run_hub_service.py > logs/hub.log 2>&1 &
    HUB_PID=$!
    echo $HUB_PID > hub.pid
    echo "✓ Hub service started (PID: $HUB_PID)"
fi

echo ""
echo "Waiting for services to initialize..."
sleep 3

# Check if dashboard is responding
if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "✓ Dashboard API is responding"
else
    echo "✗ Dashboard API not responding yet (may need more time)"
fi

echo ""
echo "========================================"
echo "   ✓ PULSE SYSTEM IS RUNNING"
echo "========================================"
echo ""
echo "📊 Dashboard:  http://localhost:8080"
echo "🔌 API Status: http://localhost:8080/api/status"
echo ""
echo "📝 Logs:       tail -f logs/hub.log"
echo "🛑 Stop:       pkill -f run_hub_service.py"
echo ""
echo "Current Mock Data:"
echo "  👥 People: 5 occupancy, 12 entries"
echo "  🔊 Sound: 72.5 dB"
echo "  🎵 Song: Test Song by Test Artist"
echo ""
echo "To update data, edit files in: /workspace/data/"
echo "========================================"
