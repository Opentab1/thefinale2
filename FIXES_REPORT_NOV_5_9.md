# Fixes from November 5-9, 2025

## 🔍 Summary
Found 2 major fixes during Nov 5-9:
1. **Temperature Reader Fix** (Nov 4)
2. **People Detection Fix** (Nov 5-7)

---

## 1️⃣ TEMPERATURE READER FIX

### 📅 Date: November 4, 2025
### 🔗 Commit: `a077924ccf37ada28ba0b0656cdf66c3958aa04c`

### ❌ Problem
After system startup, temperature (BME280 sensor) was not working.

### 🔍 Root Causes
1. **Missing Python libraries**: `adafruit_bme280`, `pyaudio`, `sounddevice`, `shazamio`
2. **Missing system tools**: `i2c-tools`, `alsa-utils`, `portaudio19-dev`
3. **I2C interface** not enabled on Raspberry Pi
4. **ALSA audio** not configured for USB microphone

### ✅ Solution
Created comprehensive fix scripts that:
- Install all required Python packages
- Enable I2C interface for BME280
- Configure ALSA for audio input
- Create diagnostic tools for verification

### 📋 Files Created
- `fix_sensors.sh` - Full installation with hardware checks
- `fix_sensors_v2.sh` - Universal version (works in VM and RPi)
- `test_sensors_quick.py` - Quick diagnostic tool
- `SENSOR_FIX_README.md` - Complete troubleshooting guide
- `DEPLOY_TO_RPI.md` - Deployment instructions

### 🔧 EXACT COMMANDS TO FIX TEMPERATURE READER

```bash
# Option 1: Run the comprehensive fix script (RECOMMENDED)
cd /workspace
sudo bash fix_sensors_v2.sh

# Option 2: Manual installation
sudo apt-get update
sudo apt-get install -y i2c-tools python3-smbus alsa-utils portaudio19-dev

# Enable I2C interface
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable

# Install Python dependencies
pip3 install adafruit-blinka adafruit-circuitpython-bme280 smbus2

# Test the sensor
python3 /workspace/test_sensors_quick.py

# If I2C was just enabled, reboot
sudo reboot

# Start the system
bash /workspace/start_pulse.sh
```

### 🧪 Verification Commands
```bash
# Check I2C connection (should show 76 or 77)
sudo i2cdetect -y 1

# Test BME280 directly
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace/services')
from sensors.bme280_reader import BME280Reader
sensor = BME280Reader()
data = sensor.read_sensor()
print(f"Temperature: {data['temperature_f']:.1f}°F")
print(f"Humidity: {data['humidity']:.1f}%")
EOF
```

---

## 2️⃣ PEOPLE DETECTION FIX

### 📅 Date: November 5-7, 2025
### 🔗 Main Commits:
- `c8ed29f` (Nov 5) - Add inter-process communication via cache files
- `3dd1711` (Nov 7) - Add camera cache file for inter-process communication
- `90ad393` (Nov 7) - Add environment variables to hub service file

### ❌ Problem
- Camera service collected people count data but stored only in memory (separate process)
- Hub service couldn't access it (different process)
- Dashboard showed no occupancy data (occupancy=0)

### 🔍 Root Cause
After separating services for fault isolation (to prevent camera crashes from killing the entire system), the hub and camera services ran in separate processes. They couldn't share memory, so occupancy data was invisible to the dashboard.

### ✅ Solution: Cache File Inter-Process Communication

The fix used cache files to share data between separate services:

1. **Camera service** writes people count to cache file every 5 seconds:
   - File: `/opt/pulse/data/people_cache.json`
   - Contains: `{"occupancy": X, "entries": Y, "exits": Z, "timestamp": T}`

2. **Hub service** reads cache file when camera is running as separate service:
   - Checks if `PULSE_DISABLE_CAMERA=1` (separate service mode)
   - Reads from `/opt/pulse/data/people_cache.json`
   - Returns data to dashboard

3. **Environment variables** tell hub to use cache files:
   - `PULSE_DISABLE_AUDIO=1` - Read audio data from cache
   - `PULSE_DISABLE_CAMERA=1` - Read camera data from cache

### 📋 Files Modified
- `run_camera_service.py` - Write people cache every 5 seconds
- `services/hub/main.py` - Read cache when camera disabled
- `services/systemd/pulse-hub-main.service` - Add environment variables

### 🔧 EXACT COMMANDS TO FIX PEOPLE DETECTION

```bash
# Pull the fixes from git
cd /opt/pulse
git pull

# Copy updated service file with environment variables
sudo cp services/systemd/pulse-hub-main.service /etc/systemd/system/
sudo systemctl daemon-reload

# Restart both services
sudo systemctl restart pulse-camera.service
sudo systemctl restart pulse-hub-main.service

# Verify services are running
sudo systemctl status pulse-camera.service
sudo systemctl status pulse-hub-main.service
```

### 🧪 Verification Commands
```bash
# Check if cache file is being created
ls -lh /opt/pulse/data/people_cache.json

# Watch cache file updates in real-time
watch -n 1 cat /opt/pulse/data/people_cache.json

# Check logs for cache reading
sudo journalctl -u pulse-hub-main.service -f | grep -i "people\|cache"

# Expected log output:
# 📁 Cache updated: occupancy=3, entries=12, exits=9
# 👥 People from cache: occupancy=3, entries=12, exits=9
```

### 🗂️ Cache File Format
```json
{
  "occupancy": 3,
  "entries": 12,
  "exits": 9,
  "timestamp": 1730998765.123
}
```

---

## 🎯 QUICK FIX COMMANDS (TL;DR)

### For Temperature Reader:
```bash
cd /workspace
sudo bash fix_sensors_v2.sh
sudo reboot  # if I2C was just enabled
```

### For People Detection:
```bash
cd /opt/pulse
git pull
sudo cp services/systemd/pulse-hub-main.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart pulse-camera.service
sudo systemctl restart pulse-hub-main.service
```

---

## 📊 Architecture Context

### Before Fix (Nov 5): Monolithic Service
```
┌─────────────────────────────────────┐
│     Single Process (pulse.service)   │
│  ┌────────┬────────┬──────────────┐  │
│  │ Camera │ Audio  │ Hub/Sensors  │  │
│  └────────┴────────┴──────────────┘  │
│  Problem: Camera crash = ALL DIE ☠️  │
└─────────────────────────────────────┘
```

### After Fix (Nov 7): Separate Services with Cache Files
```
┌──────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│ pulse-camera.    │    │ pulse-audio.     │    │ pulse-hub-main.    │
│ service          │    │ service          │    │ service            │
│                  │    │                  │    │                    │
│ People Counter   │    │ Audio Detector   │    │ Dashboard +        │
│                  │    │ Song Detection   │    │ Environmental      │
│       ↓          │    │       ↓          │    │ Sensors            │
│ people_cache.json│    │ decibel_cache.   │    │       ↑            │
│                  │    │ json             │    │   Reads cache      │
│                  │    │ song_cache.json  │    │   files ←──────────┤
└──────────────────┘    └──────────────────┘    └────────────────────┘
   ↓ Restarts alone       ↓ Restarts alone         Keeps running! ✅
   Camera crash           Audio issue              Dashboard works! ✅
```

---

## 🎬 Implementation Timeline

**November 5, 2025:**
- `3f52591` - Implement separate services for fault isolation
- `c8ed29f` - Add audio cache files (decibel_cache.json, song_cache.json)

**November 7, 2025:**
- `3dd1711` - Add camera cache file (people_cache.json)
- `90ad393` - Add environment variables to hub service file
- `ad7257f` - Change cache logging from debug to info for visibility

**Result:** All 3 data streams (audio, song, people) now use cache-based communication ✅

---

## 🔗 Related Fixes (Context)

### November 4, 2025: Database & Song Detection Improvements
Multiple commits improved temperature display and song detection reliability:
- Added retry logic for database connections
- Enhanced BME280 error recovery
- Improved song detection timeout handling
- Better activity tracking to prevent false watchdog triggers

These fixes ensured that once temperature data was collected, it would reliably reach the dashboard.

---

## 📝 Notes

1. **Temperature fix** addresses the sensor initialization and dependency issues
2. **People detection fix** solves the inter-process communication problem
3. Both fixes are **independent** but complement the overall system stability
4. The cache file approach proved reliable and is used for all sensor data now

---

**Report Generated:** 2025-11-17
**Git Branch:** cursor/investigate-detection-issue-fixes-in-git-history-0667
**Repository:** /workspace
