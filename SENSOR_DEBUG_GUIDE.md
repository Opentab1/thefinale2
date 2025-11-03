# Pulse Sensor Debugging Guide

## Quick Start - Run All Tests

To test all sensors and get a complete diagnostic:

```bash
bash /workspace/fix_and_test_sensors.sh
```

This will:
1. Check all dependencies
2. Test temperature sensor (BME280)
3. Test audio monitor and dB readings
4. Test song detection
5. Show which dashboard is running
6. Provide next steps

---

## Individual Sensor Tests

### Test Temperature Sensor Only

```bash
python3 /workspace/test_temperature.py
```

**What it checks:**
- BME280 sensor connection via I2C
- Temperature reading (°F and °C)
- Humidity reading
- Pressure reading
- Continuous reading capability

**Expected output:**
```
Temperature: 72.5°F (22.5°C)
Humidity: 45.2%
Pressure: 1013.25 hPa
```

**Troubleshooting:**
- If failed, check I2C: `sudo i2cdetect -y 1`
- Enable I2C: `sudo raspi-config` → Interface Options → I2C → Enable
- Install dependencies: `pip3 install adafruit-circuitpython-bme280`

---

### Test Audio & Song Detection

```bash
python3 /workspace/test_audio.py
```

**What it checks:**
- Audio device detection
- dB level monitoring
- Song detection (ShazamIO)

**Expected output:**
```
[0s] dB: 65.3 (peak: 72.1)
[2s] dB: 68.2 (peak: 72.1)
[4s] dB: 70.1 (peak: 72.1)
      🎵 Song: Sweet Caroline - Neil Diamond
```

**Troubleshooting:**
- List audio devices: `arecord -l`
- Test recording: `arecord -d 3 test.wav && aplay test.wav`
- Install dependencies: `pip3 install numpy pyaudio sounddevice shazamio`
- Add user to audio group: `sudo usermod -a -G audio $USER`

---

## Dashboard Issues

### Problem: Dashboard shows 0 for temperature

**Diagnosis:**
```bash
# Check if BME280 sensor is detected
sudo i2cdetect -y 1

# Should show device at 0x76 or 0x77:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 70: -- -- -- -- -- -- 76 --
```

**Fix:**
1. Enable I2C if not enabled:
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options → I2C → Enable
   sudo reboot
   ```

2. Install dependencies:
   ```bash
   pip3 install adafruit-circuitpython-bme280 adafruit-blinka
   ```

3. Test the sensor:
   ```bash
   python3 /workspace/test_temperature.py
   ```

---

### Problem: No song detection

**Diagnosis:**
```bash
# Check if ShazamIO is installed
python3 -c "import shazamio; print('ShazamIO installed')"
```

**Fix:**
1. Install ShazamIO:
   ```bash
   pip3 install shazamio
   ```

2. Ensure internet connection (required for Shazam API):
   ```bash
   ping -c 3 google.com
   ```

3. Test with music playing:
   ```bash
   python3 /workspace/test_audio.py
   # Play music nearby during the test
   ```

**Note:** Song detection requires:
- Internet connection (Shazam API)
- Audible music playing
- ~30 seconds to detect a song

---

### Problem: Dashboard shows wrong data

**Check which dashboard is running:**
```bash
ps aux | grep python | grep dashboard
```

**You should be running:**
```bash
/workspace/rpi/simple_local_dashboard.py  # ← CORRECT (real sensors)
```

**NOT:**
```bash
/workspace/rpi/local_dashboard.py  # ← WRONG (fake/simulated data)
```

**Fix:**
```bash
# Stop any running dashboard
pkill -f 'python.*dashboard'

# Start the correct dashboard
python3 /workspace/rpi/simple_local_dashboard.py
```

---

## System Checks

### Check I2C devices (temperature sensor)
```bash
sudo i2cdetect -y 1
```

### Check audio devices (microphone)
```bash
arecord -l
```

### Check Python packages
```bash
python3 << 'EOF'
import sys
packages = [
    "numpy", "pyaudio", "sounddevice", 
    "adafruit_bme280", "board", "shazamio"
]
for pkg in packages:
    try:
        __import__(pkg)
        print(f"✓ {pkg}")
    except ImportError:
        print(f"✗ {pkg} - NOT INSTALLED")
EOF
```

### Install all dependencies
```bash
pip3 install numpy pyaudio sounddevice \
    adafruit-circuitpython-bme280 adafruit-blinka \
    shazamio
```

---

## Manual Sensor Reading

### Read temperature directly
```bash
python3 << 'EOF'
from services.sensors.bme280_reader import BME280Reader
sensor = BME280Reader()
data = sensor.read_sensor()
print(f"Temp: {data['temperature_f']:.1f}°F")
print(f"Humidity: {data['humidity']:.1f}%")
EOF
```

### Read audio levels directly
```bash
python3 << 'EOF'
from services.sensors.mic_song_detect import AudioMonitor
import time
monitor = AudioMonitor()
monitor.start_monitoring()
time.sleep(5)
stats = monitor.get_stats()
print(f"dB: {stats['current_db']:.1f}")
print(f"Song: {stats['current_song']['title']}")
monitor.cleanup()
EOF
```

---

## Quick Reference

| Issue | Command |
|-------|---------|
| Test all sensors | `bash /workspace/fix_and_test_sensors.sh` |
| Test temperature | `python3 /workspace/test_temperature.py` |
| Test audio | `python3 /workspace/test_audio.py` |
| Check I2C | `sudo i2cdetect -y 1` |
| Check audio devices | `arecord -l` |
| Restart dashboard | `pkill -f dashboard && python3 /workspace/rpi/simple_local_dashboard.py` |
| View dashboard | Open browser to `http://localhost:8080` |

---

## Expected Dashboard Readings

When everything is working correctly, you should see:

| Metric | Expected Value | Source |
|--------|---------------|--------|
| **Sound Level** | 40-90 dB | USB Microphone |
| **Light Level** | 0-1000 lux | Light sensor (I2C) |
| **Temperature** | 60-80°F | BME280 (I2C) |
| **Humidity** | 20-80% | BME280 (I2C) |
| **Now Playing** | Song name | ShazamIO (requires internet & music) |
| **Comfort Score** | 0-100 | Calculated from above |

---

## Still Having Issues?

1. **Check logs:** The dashboard prints sensor readings to console
   ```bash
   # Run dashboard in foreground to see logs
   python3 /workspace/rpi/simple_local_dashboard.py
   ```

2. **Check hardware connections:**
   - BME280: Connected to I2C pins (SDA/SCL)
   - Microphone: USB connected
   - Light sensor: Connected to I2C

3. **Check permissions:**
   ```bash
   # Add user to required groups
   sudo usermod -a -G i2c,audio,video $USER
   # Logout and login for changes to take effect
   ```

4. **Reboot if needed:**
   ```bash
   sudo reboot
   ```
