#!/bin/bash
# BME280 Dashboard Diagnostic Script

echo "=================================================="
echo "BME280 SENSOR DASHBOARD DIAGNOSTIC"
echo "=================================================="
echo ""

echo "1. Checking I2C Bus for BME280..."
echo "   Looking for address 0x76 or 0x77:"
sudo i2cdetect -y 1
echo ""

echo "2. Testing BME280 Direct Read..."
echo "   (This will take a few seconds)"
timeout 10 sudo python3 /workspace/services/sensors/bme280_reader.py 2>&1 | head -20
echo ""

echo "3. Checking if Hub Service is Running..."
ps aux | grep -E "hub/main.py|services/hub" | grep -v grep
if [ $? -eq 0 ]; then
    echo "   ✓ Hub is running"
else
    echo "   ✗ Hub is NOT running"
fi
echo ""

echo "4. Checking Dashboard API..."
if curl -s http://localhost:8080/api/sensors/current > /dev/null 2>&1; then
    echo "   ✓ Dashboard API is responding"
    echo "   Current sensor data from API:"
    curl -s http://localhost:8080/api/sensors/current | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"   Temperature: {data.get('temperature_f', 'N/A')}°F\"); print(f\"   Humidity: {data.get('humidity', 'N/A')}%\")"
else
    echo "   ✗ Dashboard API is NOT responding"
fi
echo ""

echo "5. Checking Database for Recent BME280 Data..."
if [ -f /opt/pulse/data/pulse.db ]; then
    echo "   Last 3 environment readings:"
    sqlite3 /opt/pulse/data/pulse.db "SELECT datetime(timestamp, 'localtime') as time, temperature, humidity FROM environment_log ORDER BY timestamp DESC LIMIT 3;" 2>/dev/null || echo "   ✗ No data or database error"
else
    echo "   ✗ Database not found at /opt/pulse/data/pulse.db"
fi
echo ""

echo "6. Checking Hub Logs for BME280 Activity..."
if [ -f /var/log/pulse/hub.log ]; then
    echo "   Recent BME280 log entries:"
    sudo tail -20 /var/log/pulse/hub.log | grep -i bme | tail -5
else
    echo "   ✗ Hub log not found at /var/log/pulse/hub.log"
fi
echo ""

echo "=================================================="
echo "DIAGNOSIS COMPLETE"
echo "=================================================="
echo ""
echo "INTERPRETATION:"
echo "- If I2C shows 76/77: Sensor is detected ✓"
echo "- If direct read works: Sensor hardware is good ✓"  
echo "- If API shows null: Hub may not be reading sensor"
echo "- If database is empty: Data not being stored"
echo ""
