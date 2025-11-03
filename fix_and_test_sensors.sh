#!/bin/bash
# Complete sensor diagnostic and fix script

set -e

echo "=========================================="
echo "Pulse Sensor Debug & Fix Script"
echo "=========================================="
echo ""

# Function to install missing dependencies
install_dependencies() {
    echo "Installing missing Python dependencies..."
    
    # Core dependencies
    pip3 install -q numpy pyaudio sounddevice 2>/dev/null || true
    
    # Sensor dependencies
    pip3 install -q adafruit-circuitpython-bme280 adafruit-blinka 2>/dev/null || true
    
    # Song detection
    pip3 install -q shazamio 2>/dev/null || true
    
    echo "✓ Dependencies installed"
}

# Check if we need to install dependencies
echo "Checking dependencies..."
python3 << 'PYEOF'
import sys
missing = []
try:
    import numpy
except ImportError:
    missing.append("numpy")

try:
    import adafruit_bme280
except ImportError:
    missing.append("adafruit-circuitpython-bme280")

try:
    import shazamio
except ImportError:
    missing.append("shazamio")

if missing:
    print(f"Missing packages: {', '.join(missing)}")
    sys.exit(1)
else:
    print("✓ All required packages installed")
    sys.exit(0)
PYEOF

if [ $? -ne 0 ]; then
    echo ""
    read -p "Install missing dependencies? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_dependencies
    fi
fi

echo ""
echo "=========================================="
echo "Running Sensor Tests"
echo "=========================================="
echo ""

# Run the comprehensive test
bash /workspace/test_all_sensors.sh

echo ""
echo "=========================================="
echo "Dashboard Status"
echo "=========================================="
echo ""

# Check if dashboard is running
if lsof -i :8080 2>/dev/null | grep -q LISTEN; then
    echo "Dashboard is running on port 8080"
    echo ""
    echo "To restart with the correct dashboard:"
    echo "  1. Stop current dashboard: pkill -f 'python.*dashboard'"
    echo "  2. Start correct dashboard: python3 /workspace/rpi/simple_local_dashboard.py"
    echo ""
    echo "Or use this one-liner:"
    echo "  pkill -f 'python.*dashboard' && python3 /workspace/rpi/simple_local_dashboard.py"
else
    echo "No dashboard running on port 8080"
    echo ""
    echo "Start the dashboard with:"
    echo "  python3 /workspace/rpi/simple_local_dashboard.py"
fi

echo ""
echo "=========================================="
echo "Quick Reference"
echo "=========================================="
echo "Test temperature only:"
echo "  python3 /workspace/test_temperature.py"
echo ""
echo "Test audio only:"
echo "  python3 /workspace/test_audio.py"
echo ""
echo "Test all sensors:"
echo "  bash /workspace/test_all_sensors.sh"
echo ""
echo "View dashboard:"
echo "  http://localhost:8080"
echo "=========================================="
