#!/bin/bash
# Diagnostic Commands for Raspberry Pi 5
# Run these commands and paste the output back

echo "================================================================================"
echo "PULSE SYSTEM DIAGNOSTICS - Raspberry Pi 5"
echo "================================================================================"
echo ""

echo "1. SYSTEM INFO"
echo "----------------------------------------"
uname -a
python3 --version
whoami
pwd
echo ""

echo "2. CHECK PYTHON PACKAGES"
echo "----------------------------------------"
python3 -m pip list | grep -E "(numpy|shazam|sound|bme280|blinka|pyaudio)"
echo ""

echo "3. CHECK RUNNING PROCESSES"
echo "----------------------------------------"
ps aux | grep -E "(python|pulse|hub|dashboard)" | grep -v grep
echo ""

echo "4. CHECK LOG FILES"
echo "----------------------------------------"
echo "Log directory contents:"
ls -lh /var/log/pulse/ 2>/dev/null || echo "No /var/log/pulse directory"
echo ""
echo "Recent hub.log (last 50 lines):"
tail -50 /var/log/pulse/hub.log 2>/dev/null || echo "No hub.log found"
echo ""

echo "5. CHECK I2C FOR BME280 TEMPERATURE SENSOR"
echo "----------------------------------------"
echo "Checking if I2C is enabled..."
ls -l /dev/i2c-* 2>/dev/null || echo "No I2C devices found - I2C may not be enabled"
echo ""
echo "Scanning I2C bus for BME280 (should show device at 0x76 or 0x77):"
sudo i2cdetect -y 1 2>/dev/null || echo "i2cdetect not available or I2C disabled"
echo ""

echo "6. CHECK AUDIO DEVICES FOR MICROPHONE"
echo "----------------------------------------"
echo "Audio input devices:"
arecord -l 2>/dev/null || echo "arecord not available"
echo ""
echo "Python sounddevice devices:"
python3 -c "import sounddevice as sd; print(sd.query_devices())" 2>&1
echo ""

echo "7. TEST IMPORTS"
echo "----------------------------------------"
echo "Testing ShazamIO import:"
python3 -c "from shazamio import Shazam; print('✅ ShazamIO OK')" 2>&1
echo ""
echo "Testing BME280 import:"
python3 -c "import busio, board, adafruit_bme280; print('✅ BME280 libraries OK')" 2>&1
echo ""
echo "Testing numpy/sounddevice:"
python3 -c "import numpy, sounddevice; print('✅ Audio libraries OK')" 2>&1
echo ""

echo "8. TEST BME280 SENSOR DIRECTLY"
echo "----------------------------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/services')
try:
    from services.sensors.bme280_reader import BME280Reader
    print("Attempting to read BME280 sensor...")
    sensor = BME280Reader(address=0x76)
    data = sensor.read_sensor()
    if data:
        print(f"✅ Temperature: {data.get('temperature_f')}°F")
        print(f"✅ Humidity: {data.get('humidity')}%")
    else:
        print("❌ Sensor returned no data")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

echo "9. TEST AUDIO MONITOR DIRECTLY"
echo "----------------------------------------"
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/services')
try:
    from services.sensors.mic_song_detect import AudioMonitor
    print("Attempting to initialize AudioMonitor...")
    audio = AudioMonitor()
    print(f"✅ AudioMonitor initialized")
    print(f"   Song detector: {audio.song_detector is not None}")
    print(f"   Device index: {audio.device_index}")
    if audio.song_detector:
        song = audio.song_detector.get_latest_song()
        print(f"   Latest song: {song}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

echo "10. CHECK DASHBOARD API"
echo "----------------------------------------"
echo "Testing dashboard API endpoint:"
curl -s http://localhost:8080/api/sensors/current | python3 -m json.tool 2>/dev/null || echo "Dashboard API not responding"
echo ""

echo "11. CHECK CONFIG FILE"
echo "----------------------------------------"
cat /workspace/config/config.yaml 2>/dev/null || echo "Config file not found"
echo ""

echo "================================================================================"
echo "DIAGNOSTICS COMPLETE"
echo "================================================================================"
echo ""
echo "Please copy ALL the output above and paste it back so I can diagnose the issues."
