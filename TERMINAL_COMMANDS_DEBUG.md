# Terminal Commands to Debug Sensors

## 🚀 Quick Start - Run This First

```bash
bash /workspace/fix_and_test_sensors.sh
```

This comprehensive test will:
- ✅ Check all Python dependencies
- ✅ Test temperature sensor (BME280)
- ✅ Test audio/microphone
- ✅ Test song detection
- ✅ Show dashboard status
- ✅ Provide specific fixes for any issues

---

## 🔍 Individual Sensor Tests

### 1. Test Temperature Sensor (BME280)

```bash
python3 /workspace/test_temperature.py
```

**What it does:**
- Tests BME280 sensor connection
- Reads temperature, humidity, pressure
- Runs continuous reading test for 10 seconds

**Expected output:**
```
SUCCESS! Sensor is working:
  Temperature: 72.5°F (22.5°C)
  Humidity: 45.2%
  Pressure: 1013.25 hPa
```

---

### 2. Test Audio & Song Detection

```bash
python3 /workspace/test_audio.py
```

**What it does:**
- Tests microphone connection
- Monitors dB levels for 20 seconds
- Tests song detection (if music is playing)

**Expected output:**
```
[0s] dB: 65.3 (peak: 72.1)
[2s] dB: 68.2 (peak: 72.1)
🎵 Song: Sweet Caroline - Neil Diamond
```

**Note:** Make some noise during the test to see dB readings!

---

### 3. Test All Sensors Together

```bash
bash /workspace/test_all_sensors.sh
```

Comprehensive test of all sensors with troubleshooting info.

---

## 🎯 Start Dashboard with Correct Settings

### Stop any running dashboard and start the correct one:

```bash
# One-liner to restart with correct dashboard
pkill -f 'python.*dashboard' && python3 /workspace/rpi/simple_local_dashboard.py
```

### Or use the helper script:

```bash
bash /workspace/start_dashboard_correct.sh
```

Then open your browser to: **http://localhost:8080**

---

## 🔧 System Diagnostics

### Check I2C devices (for temperature & light sensors)

```bash
sudo i2cdetect -y 1
```

**Expected output:** Should show devices at 0x76 or 0x77 (BME280)
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
70: -- -- -- -- -- -- 76 --
```

**If empty:** Enable I2C
```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
sudo reboot
```

---

### Check Audio Devices (for microphone)

```bash
arecord -l
```

**Expected output:**
```
**** List of CAPTURE Hardware Devices ****
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
```

**Test recording:**
```bash
arecord -d 3 test.wav  # Record 3 seconds
aplay test.wav         # Play it back
```

---

### Check Python Dependencies

```bash
python3 << 'EOF'
packages = [
    ("numpy", "NumPy"),
    ("pyaudio", "PyAudio"),
    ("sounddevice", "sounddevice"),
    ("adafruit_bme280", "BME280 Sensor"),
    ("board", "Adafruit Blinka"),
    ("shazamio", "Song Detection"),
]

for module, name in packages:
    try:
        __import__(module)
        print(f"✓ {name}")
    except ImportError:
        print(f"✗ {name} - MISSING")
EOF
```

---

## 📦 Install Missing Dependencies

### Install all sensor dependencies:

```bash
pip3 install numpy pyaudio sounddevice \
    adafruit-circuitpython-bme280 adafruit-blinka \
    shazamio
```

### Or install individually:

```bash
# Audio
pip3 install numpy pyaudio sounddevice

# Temperature/Humidity
pip3 install adafruit-circuitpython-bme280 adafruit-blinka

# Song Detection
pip3 install shazamio
```

---

## 🐛 Troubleshooting Specific Issues

### Temperature shows 0

**Diagnosis:**
```bash
# Check I2C
sudo i2cdetect -y 1

# Test sensor directly
python3 /workspace/test_temperature.py
```

**Fixes:**
1. Enable I2C: `sudo raspi-config` → Interface Options → I2C
2. Install packages: `pip3 install adafruit-circuitpython-bme280`
3. Check wiring (SDA, SCL, 3.3V, GND)
4. Try alternate I2C address (0x77 instead of 0x76)

---

### No sound/dB readings

**Diagnosis:**
```bash
# List audio devices
arecord -l

# Test recording
arecord -d 3 test.wav
```

**Fixes:**
1. Install packages: `pip3 install pyaudio sounddevice`
2. Add user to audio group: `sudo usermod -a -G audio $USER` (requires logout)
3. Check USB connection if using USB mic
4. Check audio device permissions

---

### Song detection not working

**Requirements:**
- ✅ Internet connection (Shazam API needs internet)
- ✅ Music playing nearby
- ✅ ShazamIO installed: `pip3 install shazamio`
- ⏱️ Takes ~30 seconds to detect a song

**Test:**
```bash
# Make sure ShazamIO is installed
python3 -c "import shazamio; print('✓ ShazamIO installed')"

# Test with music playing
python3 /workspace/test_audio.py
# Let it run for at least 30 seconds with music playing
```

---

## 📊 Manual Sensor Reading

### Read temperature directly in Python:

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace')
from services.sensors.bme280_reader import BME280Reader

sensor = BME280Reader()
data = sensor.read_sensor()

print(f"Temperature: {data['temperature_f']:.1f}°F")
print(f"Humidity: {data['humidity']:.1f}%")
print(f"Pressure: {data['pressure']:.2f} hPa")
EOF
```

---

### Read audio levels directly in Python:

```bash
python3 << 'EOF'
import sys
import time
sys.path.insert(0, '/workspace')
from services.sensors.mic_song_detect import AudioMonitor

monitor = AudioMonitor()
monitor.start_monitoring()

print("Monitoring audio for 10 seconds...")
for i in range(5):
    time.sleep(2)
    stats = monitor.get_stats()
    print(f"dB: {stats['current_db']:.1f}")
    song = stats['current_song']
    if song['title'] != 'Unknown':
        print(f"Song: {song['title']} - {song['artist']}")

monitor.cleanup()
EOF
```

---

## ✅ What Should Work on Dashboard

When everything is working, your dashboard should show:

| Metric | Source | Notes |
|--------|--------|-------|
| **Sound Level** | USB Microphone | Should show 40-90 dB with normal noise |
| **Light Level** | Light Sensor (I2C) | 0-1000+ lux depending on lighting |
| **Temperature** | BME280 (I2C) | Should show room temperature |
| **Humidity** | BME280 (I2C) | Should show 20-80% typically |
| **Now Playing** | ShazamIO | Requires internet & music playing |
| **Comfort Score** | Calculated | Based on above metrics |

---

## 🎯 Command Summary

| Task | Command |
|------|---------|
| **Test all sensors** | `bash /workspace/fix_and_test_sensors.sh` |
| **Test temperature** | `python3 /workspace/test_temperature.py` |
| **Test audio** | `python3 /workspace/test_audio.py` |
| **Start dashboard** | `bash /workspace/start_dashboard_correct.sh` |
| **Check I2C** | `sudo i2cdetect -y 1` |
| **Check audio** | `arecord -l` |
| **Install deps** | `pip3 install numpy pyaudio sounddevice adafruit-circuitpython-bme280 shazamio` |

---

## 📝 Files Created

All diagnostic and fix files are in `/workspace/`:

- `test_temperature.py` - Test BME280 sensor
- `test_audio.py` - Test microphone and song detection  
- `test_all_sensors.sh` - Comprehensive sensor test
- `fix_and_test_sensors.sh` - Complete diagnostic with dependency install
- `start_dashboard_correct.sh` - Start dashboard with real sensors
- `SENSOR_DEBUG_GUIDE.md` - Detailed troubleshooting guide (this file)
- `TERMINAL_COMMANDS_DEBUG.md` - Quick command reference

---

## 🚨 Need Help?

1. **Run the comprehensive test first:**
   ```bash
   bash /workspace/fix_and_test_sensors.sh
   ```

2. **Check the detailed guide:**
   ```bash
   cat /workspace/SENSOR_DEBUG_GUIDE.md
   ```

3. **View dashboard logs:**
   ```bash
   python3 /workspace/rpi/simple_local_dashboard.py
   # Watch the console output for sensor readings and errors
   ```
