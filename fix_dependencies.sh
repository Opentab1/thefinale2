#!/bin/bash
# Quick fix script to install missing dependencies on Raspberry Pi 5
# Run this with: bash fix_dependencies.sh

set -e

echo "================================================================================"
echo "PULSE - Installing Missing Dependencies for Song Detection & Temperature"
echo "================================================================================"
echo ""

# Detect which Python to use
if [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON="/opt/pulse/venv/bin/python3"
    PIP="/opt/pulse/venv/bin/pip"
    echo "✓ Using virtual environment: /opt/pulse/venv"
elif [ -f "/workspace/venv/bin/python3" ]; then
    PYTHON="/workspace/venv/bin/python3"
    PIP="/workspace/venv/bin/pip"
    echo "✓ Using virtual environment: /workspace/venv"
else
    PYTHON="python3"
    PIP="python3 -m pip"
    echo "⚠ Using system Python (no venv found)"
fi

echo "Python: $PYTHON"
$PYTHON --version
echo ""

# Install system dependencies
echo "1. Installing system dependencies..."
echo "----------------------------------------"
sudo apt-get update -qq
sudo apt-get install -y portaudio19-dev libportaudio2 i2c-tools python3-dev build-essential
echo "✓ System dependencies installed"
echo ""

# Install Python packages
echo "2. Installing Python packages..."
echo "----------------------------------------"
$PIP install --upgrade pip setuptools wheel
echo ""

echo "Installing audio packages..."
$PIP install numpy sounddevice
echo ""

echo "Installing song detection packages..."
$PIP install shazamio "aiohttp<4.0.0"
echo ""

echo "Installing temperature sensor packages..."
$PIP install adafruit-blinka adafruit-circuitpython-bme280 adafruit-extended-bus
echo ""

echo "✓ All Python packages installed"
echo ""

# Verify installations
echo "3. Verifying installations..."
echo "----------------------------------------"
echo -n "numpy: "
$PYTHON -c "import numpy; print('✓ OK')" || echo "✗ FAILED"

echo -n "sounddevice: "
$PYTHON -c "import sounddevice; print('✓ OK')" || echo "✗ FAILED"

echo -n "shazamio: "
$PYTHON -c "from shazamio import Shazam; print('✓ OK')" || echo "✗ FAILED"

echo -n "BME280: "
$PYTHON -c "import adafruit_bme280; print('✓ OK')" || echo "✗ FAILED"

echo -n "adafruit_extended_bus: "
$PYTHON -c "import adafruit_extended_bus; print('✓ OK')" || echo "✗ FAILED"

echo ""

# Check hardware
echo "4. Checking hardware..."
echo "----------------------------------------"
echo "I2C devices (BME280 should be at 0x76 or 0x77):"
sudo i2cdetect -y 1 2>/dev/null || echo "⚠ I2C not enabled - run: sudo raspi-config"
echo ""

echo "Audio input devices:"
arecord -l 2>/dev/null || echo "⚠ No audio devices found"
echo ""

# Test sensor modules
echo "5. Testing sensor modules..."
echo "----------------------------------------"
cd /workspace

echo "Testing BME280Reader..."
$PYTHON << 'EOF'
import sys
sys.path.insert(0, '/workspace/services')
try:
    from sensors.bme280_reader import BME280Reader
    sensor = BME280Reader(address=0x76)
    data = sensor.read_sensor()
    if data and data.get('temperature_f'):
        print(f"✓ BME280 OK: {data['temperature_f']:.1f}°F, {data['humidity']:.1f}%")
    else:
        print("✗ BME280 returned no data")
except Exception as e:
    print(f"✗ BME280 Error: {e}")
EOF

echo ""
echo "Testing AudioMonitor..."
$PYTHON << 'EOF'
import sys
sys.path.insert(0, '/workspace/services')
try:
    from sensors.mic_song_detect import AudioMonitor
    audio = AudioMonitor()
    if audio.song_detector:
        print(f"✓ AudioMonitor OK (Song detector: enabled)")
    else:
        print(f"⚠ AudioMonitor initialized but song detector is None")
except Exception as e:
    print(f"✗ AudioMonitor Error: {e}")
EOF

echo ""
echo "================================================================================"
echo "INSTALLATION COMPLETE"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "1. Enable I2C if not already enabled: sudo raspi-config → Interface Options → I2C"
echo "2. Restart Pulse system: cd /workspace && ./start_pulse.sh"
echo "3. Open dashboard: http://localhost:8080"
echo ""
echo "If issues persist, run diagnostics:"
echo "  bash /workspace/pi_diagnostic_commands.sh"
echo ""
