#!/bin/bash
# Test all sensors and provide diagnostic information

echo "=========================================="
echo "Pulse Sensor Diagnostics"
echo "=========================================="
echo ""

# Check Python version
echo "1. Python Version:"
python3 --version
echo ""

# Check I2C devices (for BME280 and light sensor)
echo "2. I2C Devices:"
if command -v i2cdetect &> /dev/null; then
    sudo i2cdetect -y 1 2>/dev/null || echo "   I2C bus not available or no devices found"
else
    echo "   i2c-tools not installed. Install with: sudo apt-get install i2c-tools"
fi
echo ""

# Check audio devices
echo "3. Audio Input Devices:"
if command -v arecord &> /dev/null; then
    arecord -l 2>/dev/null || echo "   No audio recording devices found"
else
    echo "   arecord not available. Install with: sudo apt-get install alsa-utils"
fi
echo ""

# Check Python dependencies
echo "4. Python Dependencies:"
python3 << 'PYEOF'
import sys
packages = [
    ("numpy", "NumPy"),
    ("pyaudio", "PyAudio"),
    ("sounddevice", "sounddevice"),
    ("adafruit_bme280", "Adafruit BME280"),
    ("board", "Adafruit Blinka"),
    ("shazamio", "ShazamIO"),
]

for module, name in packages:
    try:
        __import__(module)
        print(f"   ✓ {name}")
    except ImportError:
        print(f"   ✗ {name} - NOT INSTALLED")
PYEOF
echo ""

# Test Temperature Sensor
echo "=========================================="
echo "5. Testing Temperature Sensor (BME280)"
echo "=========================================="
python3 /workspace/test_temperature.py
TEMP_STATUS=$?
echo ""

# Test Audio Monitor
echo "=========================================="
echo "6. Testing Audio Monitor"
echo "=========================================="
python3 /workspace/test_audio.py
AUDIO_STATUS=$?
echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
if [ $TEMP_STATUS -eq 0 ]; then
    echo "✓ Temperature sensor: WORKING"
else
    echo "✗ Temperature sensor: FAILED"
fi

if [ $AUDIO_STATUS -eq 0 ]; then
    echo "✓ Audio monitor: WORKING"
else
    echo "✗ Audio monitor: FAILED"
fi
echo ""

# Provide next steps
echo "=========================================="
echo "Next Steps"
echo "=========================================="
if [ $TEMP_STATUS -eq 0 ] && [ $AUDIO_STATUS -eq 0 ]; then
    echo "✓ All sensors working! Your dashboard should show:"
    echo "  - Temperature readings"
    echo "  - dB levels"
    echo "  - Song detection (if music is playing)"
    echo ""
    echo "Make sure you're running the correct dashboard:"
    echo "  python3 /workspace/rpi/simple_local_dashboard.py"
else
    echo "Some sensors need attention. See error messages above."
fi
echo "=========================================="
