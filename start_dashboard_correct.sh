#!/bin/bash
# Start the correct dashboard with real sensor readings

echo "=========================================="
echo "Starting Pulse Dashboard with Real Sensors"
echo "=========================================="
echo ""

# Stop any existing dashboard
echo "Stopping any existing dashboard..."
pkill -f 'python.*dashboard' 2>/dev/null || true
sleep 2

echo "Starting dashboard with real sensor integration..."
echo ""
echo "Dashboard will be available at:"
echo "  http://localhost:8080"
echo ""
echo "Sensor readings:"
echo "  - Temperature (BME280)"
echo "  - Humidity (BME280)"
echo "  - Sound Level (Microphone)"
echo "  - Light Level (Light Sensor)"
echo "  - Song Detection (ShazamIO - requires internet & music)"
echo ""
echo "Press Ctrl+C to stop"
echo "=========================================="
echo ""

# Start the dashboard with real sensors
cd /workspace
python3 -u rpi/simple_local_dashboard.py
