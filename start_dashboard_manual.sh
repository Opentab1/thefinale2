#!/bin/bash
#
# Manual Dashboard Starter
# Use this if systemd services are not set up
#

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Starting Pulse Dashboard (Manual Mode)                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Create required directories
sudo mkdir -p /var/log/pulse
sudo mkdir -p /opt/pulse/data
sudo chmod 777 /var/log/pulse /opt/pulse/data

# Kill any existing instances
pkill -f "run_pulse_system.py" 2>/dev/null || true
sleep 2

cd /workspace

echo "Starting Pulse System (Hub + Dashboard)..."
echo "Dashboard will be available at: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the system
python3 /workspace/run_pulse_system.py
