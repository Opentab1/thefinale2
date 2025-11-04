#!/bin/bash
# Quick test script for sensors on RPi

echo "=========================================="
echo "Quick Sensor Test"
echo "=========================================="
echo ""

echo "1. Testing BME280 (Temperature)..."
python3 -c "
import sys
sys.path.insert(0, '/workspace/services')
from sensors.bme280_reader import BME280Reader
try:
    reader = BME280Reader()
    data = reader.read_sensor()
    if data and data.get('temperature_f'):
        print(f'  ✅ Temperature: {data[\"temperature_f\"]:.1f}°F')
        print(f'  ✅ Humidity: {data[\"humidity\"]:.1f}%')
    else:
        print('  ❌ No data from BME280')
except Exception as e:
    print(f'  ❌ Error: {e}')
"
echo ""

echo "2. Testing Audio Monitor (dB)..."
python3 -c "
import sys
import time
sys.path.insert(0, '/workspace/services')
from sensors.mic_song_detect import AudioMonitor
try:
    monitor = AudioMonitor()
    monitor.start_monitoring()
    print('  Waiting 5 seconds for audio stream...')
    time.sleep(5)
    db = monitor.get_current_db()
    if db is not None and db >= 0:
        print(f'  ✅ dB reading: {db:.1f} dB')
    else:
        print('  ⚠️  dB reading: None (stream may not be active)')
    monitor.stop_monitoring()
except Exception as e:
    print(f'  ❌ Error: {e}')
"
echo ""

echo "3. Checking ShazamIO (Song Detection)..."
python3 -c "
try:
    from shazamio import Shazam
    print('  ✅ ShazamIO is installed')
except ImportError:
    print('  ❌ ShazamIO not installed')
    print('     Install with: pip install shazamio aiohttp')
"
echo ""

echo "4. Checking I2C (for BME280)..."
if command -v i2cdetect &> /dev/null; then
    echo "  Running i2cdetect -y 1..."
    sudo i2cdetect -y 1 | grep -E "76|77" && echo "  ✅ BME280 detected" || echo "  ⚠️  BME280 not found at 0x76 or 0x77"
else
    echo "  ⚠️  i2cdetect not found"
fi
echo ""

echo "5. Checking Audio Devices..."
if command -v arecord &> /dev/null; then
    echo "  Audio devices:"
    arecord -l 2>/dev/null | head -5 || echo "  ⚠️  No audio devices found"
else
    echo "  ⚠️  arecord not found"
fi
echo ""

echo "=========================================="
echo "Test Complete"
echo "=========================================="
echo ""
echo "For detailed diagnostics, run:"
echo "  python3 /workspace/test_non_working_sensors.py"
echo ""
