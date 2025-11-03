#!/bin/bash
#
# PULSE Temperature Dashboard Fix Script
# This script fixes the temperature display issue by:
# 1. Building the dashboard UI
# 2. Restarting services
# 3. Verifying everything works
#

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     PULSE TEMPERATURE DASHBOARD FIX                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠️  Warning: Not detected as Raspberry Pi, but continuing..."
else
    MODEL=$(cat /proc/device-tree/model)
    echo "✓ Detected: $MODEL"
fi

echo ""
echo "Step 1: Building Dashboard UI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /workspace/dashboard/ui

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
else
    echo "✓ npm dependencies already installed"
fi

# Build the UI
echo "Building React UI with Vite..."
npm run build

if [ -d "build" ] && [ -f "build/index.html" ]; then
    echo "✓ Dashboard UI built successfully"
    echo "  Output: /workspace/dashboard/ui/build/"
else
    echo "✗ Dashboard UI build failed!"
    exit 1
fi

echo ""
echo "Step 2: Checking BME280 Sensor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if I2C is enabled
if ! command -v i2cdetect &> /dev/null; then
    echo "⚠️  i2c-tools not found, installing..."
    sudo apt-get update && sudo apt-get install -y i2c-tools
fi

# Detect BME280
echo "Scanning I2C bus for BME280 sensor..."
if sudo i2cdetect -y 1 | grep -q "76\|77"; then
    echo "✓ BME280 sensor detected on I2C bus"
else
    echo "⚠️  Warning: BME280 sensor not detected on I2C bus"
    echo "   Check your wiring and make sure I2C is enabled"
    echo "   Run: sudo raspi-config -> Interface Options -> I2C -> Enable"
fi

echo ""
echo "Step 3: Testing Sensor Reading"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /workspace
python3 /workspace/test_temperature_dashboard.py

echo ""
echo "Step 4: Restarting Services"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if services exist
if systemctl list-unit-files | grep -q "pulse-hub.service"; then
    echo "Stopping existing services..."
    sudo systemctl stop pulse-hub.service 2>/dev/null || true
    sudo systemctl stop pulse-dashboard.service 2>/dev/null || true
    
    sleep 2
    
    echo "Starting services..."
    sudo systemctl start pulse-hub.service
    sudo systemctl start pulse-dashboard.service
    
    sleep 3
    
    # Check status
    if systemctl is-active --quiet pulse-hub.service; then
        echo "✓ pulse-hub.service is running"
    else
        echo "✗ pulse-hub.service failed to start"
        echo "  Check logs: sudo journalctl -u pulse-hub.service -n 50"
    fi
    
    if systemctl is-active --quiet pulse-dashboard.service; then
        echo "✓ pulse-dashboard.service is running"
    else
        echo "✗ pulse-dashboard.service failed to start"
        echo "  Check logs: sudo journalctl -u pulse-dashboard.service -n 50"
    fi
else
    echo "⚠️  Systemd services not installed"
    echo "   You can run the system manually with:"
    echo "   python3 /workspace/run_pulse_system.py"
fi

echo ""
echo "Step 5: Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait a moment for services to initialize
sleep 5

# Test API endpoint
echo "Testing API endpoint..."
if curl -s http://localhost:8080/api/sensors/current | grep -q "temperature_f"; then
    TEMP=$(curl -s http://localhost:8080/api/sensors/current | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('temperature_f', 'None'))")
    if [ "$TEMP" != "None" ] && [ "$TEMP" != "null" ]; then
        echo "✓✓✓ API is returning temperature data: ${TEMP}°F"
    else
        echo "⚠️  API is responding but temperature is None"
        echo "   This might mean the hub is still initializing (wait 30 seconds)"
    fi
else
    echo "⚠️  API endpoint not responding"
    echo "   Check if dashboard service is running"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                     FIX COMPLETE!                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Your dashboard should now be available at:"
echo "   http://localhost:8080"
echo ""
echo "   Or from another device on your network:"
echo "   http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "🔄 If temperature still shows 0 or blank:"
echo "   1. Wait 30 seconds for sensor to initialize"
echo "   2. Refresh your browser (Ctrl+F5 / Cmd+Shift+R)"
echo "   3. Check browser console for errors (F12)"
echo ""
echo "📋 View logs:"
echo "   Hub:       sudo journalctl -u pulse-hub.service -f"
echo "   Dashboard: sudo journalctl -u pulse-dashboard.service -f"
echo ""
