#!/bin/bash
# Temperature Sensor Quick Diagnostic

echo "=========================================="
echo "TEMPERATURE SENSOR DIAGNOSTIC"
echo "=========================================="
echo ""

echo "1. CHECK I2C BUS (BME280 should be at 0x76 or 0x77):"
sudo i2cdetect -y 1
echo ""

echo "2. CHECK BME280 PYTHON LIBRARIES:"
python3 -c "import adafruit_bme280; print('✅ BME280 libraries installed')" 2>&1
echo ""

echo "3. TEST BME280 SENSOR DIRECTLY:"
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace/services')
try:
    from sensors.bme280_reader import BME280Reader
    print("Attempting to initialize BME280...")
    sensor = BME280Reader(address=0x76)
    print("Reading sensor...")
    data = sensor.read_sensor()
    if data:
        print(f"✅ Temperature: {data.get('temperature_f')}°F")
        print(f"✅ Humidity: {data.get('humidity')}%")
        print(f"✅ Pressure: {data.get('pressure')} hPa")
    else:
        print("❌ Sensor returned no data")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
EOF
echo ""

echo "4. CHECK DASHBOARD API RESPONSE:"
curl -s http://localhost:8080/api/sensors/current | python3 -m json.tool 2>&1 | grep -A 5 -B 5 "temperature"
echo ""

echo "5. CHECK HUB LOGS FOR TEMPERATURE:"
tail -50 /var/log/pulse/hub.log 2>/dev/null | grep -i -E "(temperature|bme280|temp)" | tail -20
echo ""

echo "6. CHECK IF HUB IS RUNNING:"
ps aux | grep "hub/main.py" | grep -v grep
echo ""

echo "=========================================="
echo "DIAGNOSTIC COMPLETE - SEND THIS OUTPUT"
echo "=========================================="
