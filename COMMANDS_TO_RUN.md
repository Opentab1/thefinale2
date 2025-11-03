# Commands to Run on Your Raspberry Pi 5

Copy and paste these commands into your Pi's terminal and send me the output.

## Quick One-Liner Diagnostic (Run this first):

```bash
cd /workspace && bash pi_diagnostic_commands.sh
```

---

## OR Run These Commands Individually:

### 1. Check if dependencies are installed on your Pi:
```bash
python3 -m pip list | grep -E "(numpy|shazam|sound|bme280|blinka)"
```

### 2. Check what's currently running:
```bash
ps aux | grep -E "(python|pulse)" | grep -v grep
```

### 3. Check logs for errors:
```bash
tail -100 /var/log/pulse/hub.log 2>/dev/null || echo "No log file"
```

### 4. Check if BME280 temperature sensor is detected:
```bash
sudo i2cdetect -y 1
```
*(Should show something at 0x76 or 0x77)*

### 5. Check if microphone is detected:
```bash
arecord -l
```

### 6. Test if BME280 can be read:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace/services')
from sensors.bme280_reader import BME280Reader
sensor = BME280Reader(address=0x76)
data = sensor.read_sensor()
print(f"Temp: {data.get('temperature_f')}°F, Humidity: {data.get('humidity')}%")
EOF
```

### 7. Check dashboard API:
```bash
curl http://localhost:8080/api/sensors/current | python3 -m json.tool
```

### 8. Check what Python is being used:
```bash
which python3
python3 --version
ls -la /workspace/venv 2>/dev/null || echo "No venv"
```

### 9. Check config file:
```bash
cat /workspace/config/config.yaml
```

### 10. Try installing dependencies directly on your Pi:
```bash
cd /workspace
python3 -m pip install numpy sounddevice shazamio "aiohttp<4.0.0" adafruit-blinka adafruit-circuitpython-bme280
sudo apt-get install -y portaudio19-dev libportaudio2
```

---

## After Running Commands:

**Please paste back the output from ALL commands above** so I can:
1. See what's actually installed on your Pi
2. See what errors are in the logs
3. Check if the hardware is detected
4. Identify the exact issue preventing song detection and temperature readings
5. Fix it properly in the git repo

---

## Quick Test After Installing:

```bash
cd /workspace
python3 verify_fixes.py
```

This will verify all components are working correctly.
