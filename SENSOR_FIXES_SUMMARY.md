# Sensor Fixes Summary - Temperature, dB, and Song Detection

## Issues Fixed

### 1. Temperature Sensor (BME280)
**Problem**: Cached values might not be initialized properly, causing None values to be returned.

**Fixes Applied**:
- Added explicit cache initialization in `start_reading()` method
- Added retry logic if initial read fails
- Ensured cached values are set before background thread starts
- Better error handling and logging

**Files Modified**:
- `services/sensors/bme280_reader.py`

### 2. dB Reader (AudioMonitor)
**Problem**: `current_db` was initialized to 0.0, making it impossible to distinguish between "no stream" and "no sound detected".

**Fixes Applied**:
- Changed initial `current_db` to `None` to indicate "not initialized"
- Added `_stream_active` flag to track if audio stream is actually open
- Set `current_db = 0.0` only when stream is successfully opened
- Better logging to indicate stream status
- Improved dB calculation validation

**Files Modified**:
- `services/sensors/mic_song_detect.py`

### 3. Song Detection
**Problem**: Song detection might not be initializing properly or ShazamIO might not be available.

**Fixes Applied**:
- Enhanced ShazamIO availability checking
- Added instantiation test for ShazamIO
- Better error logging when song detector fails
- Improved song detection logging
- Better handling of song detector initialization errors

**Files Modified**:
- `services/sensors/mic_song_detect.py`

### 4. Hub Integration
**Problem**: Hub wasn't properly logging when sensor values were None, making debugging difficult.

**Fixes Applied**:
- Added better logging for None values
- Improved error handling in sensor data collection
- Better distinction between "no value" and "no data"

**Files Modified**:
- `services/hub/main.py`
- `dashboard/api/server.py`

## Testing Instructions

### Step 1: Run Diagnostic Script
First, run the diagnostic script to see what's happening:

```bash
cd /workspace
python3 test_non_working_sensors.py
```

This will test:
- BME280 temperature sensor
- AudioMonitor (dB + song detection)
- Hub integration

### Step 2: Check Logs
After running the diagnostic, check the output for:
- ✅ Green checkmarks = working
- ❌ Red X = not working
- ⚠️ Yellow warnings = needs attention

### Step 3: Test Individual Sensors

#### Test BME280:
```bash
cd /workspace
python3 -c "
from services.sensors.bme280_reader import BME280Reader
reader = BME280Reader()
data = reader.read_sensor()
print(f'Temperature: {data.get(\"temperature_f\")}°F')
print(f'Humidity: {data.get(\"humidity\")}%')
"
```

#### Test Audio Monitor:
```bash
cd /workspace
python3 -c "
from services.sensors.mic_song_detect import AudioMonitor
import time
monitor = AudioMonitor()
monitor.start_monitoring()
time.sleep(10)
print(f'dB: {monitor.get_current_db()}')
print(f'Song: {monitor.get_current_song()}')
monitor.stop_monitoring()
"
```

### Step 4: Start the System
Start the hub and dashboard to see if values appear:

```bash
cd /workspace
# If using the starter script:
./START_HERE.sh

# Or manually:
python3 run_pulse_system.py
```

### Step 5: Check Dashboard
1. Open the dashboard at `http://localhost:8080`
2. Check the Live Overview page
3. Look for:
   - Temperature value (should show °F, not "-")
   - Noise Level (should show dB, not "-")
   - Now Playing (should show song or "No song detected")

### Step 6: Check Logs
Monitor the logs for warnings:
```bash
tail -f /var/log/pulse/hub.log
```

Look for:
- "⚠️ Temperature is None" - BME280 not working
- "⚠️ Noise dB is None" - Audio stream not active
- "Song detector not available" - ShazamIO not installed

## Common Issues and Solutions

### Temperature Shows "-"
**Possible Causes**:
1. BME280 sensor not connected
2. I2C not enabled
3. Wrong I2C address

**Solutions**:
```bash
# Check I2C
sudo i2cdetect -y 1
# Should show device at 0x76 or 0x77

# Check if I2C is enabled
sudo raspi-config
# Interface Options -> I2C -> Enable

# Reboot if needed
sudo reboot
```

### dB Shows "-" or 0
**Possible Causes**:
1. No audio input device
2. Audio device permissions
3. PyAudio/sounddevice not installed

**Solutions**:
```bash
# List audio devices
arecord -l

# Test recording
arecord -d 5 test.wav
aplay test.wav

# Install dependencies
pip install pyaudio sounddevice

# Check permissions
groups
# Should include 'audio' group
```

### Song Detection Not Working
**Possible Causes**:
1. ShazamIO not installed
2. No internet connection
3. No music playing

**Solutions**:
```bash
# Install ShazamIO
pip install shazamio aiohttp

# Check internet
ping -c 3 8.8.8.8

# Test song detection manually
python3 -c "
from shazamio import Shazam
import asyncio
async def test():
    shazam = Shazam()
    print('ShazamIO is working')
asyncio.run(test())
"
```

## Files Changed

1. `services/sensors/bme280_reader.py` - Temperature initialization fix
2. `services/sensors/mic_song_detect.py` - dB and song detection fixes
3. `services/hub/main.py` - Better sensor data collection and logging
4. `dashboard/api/server.py` - Better API logging
5. `test_non_working_sensors.py` - New diagnostic script

## Next Steps

1. **Run the diagnostic script** on your RPi
2. **Share the output** so we can see what's working and what's not
3. **Test the fixes** by starting the system
4. **Verify dashboard** shows values correctly
5. **If issues persist**, we'll debug based on the diagnostic output

## Notes

- The fixes ensure proper initialization and error handling
- Better logging will help identify issues quickly
- All sensors should now properly report their status
- None values are now properly distinguished from 0 values
- The diagnostic script will help identify hardware vs software issues
