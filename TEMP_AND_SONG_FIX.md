# Temperature and Song Detection Fix

## Issues Fixed

### 1. Temperature Not Displaying on Dashboard

**Problem**: Temperature readings were showing as "-" or None on the dashboard.

**Root Cause**: The BME280 sensor was using cached values from a background thread, but if the cache wasn't populated or the thread failed, values would be None.

**Fix Applied**:
- Added fallback logic to perform a direct sensor read if cached values are None
- Added better error handling and logging
- Ensures temperature is always attempted to be read, even if cache fails

**Location**: `services/hub/main.py` - `_collect_sensor_data()` method

### 2. Song Detection Not Working

**Problem**: Song detection was not identifying songs playing.

**Root Cause**: Multiple potential issues:
- ShazamIO library might not be properly initialized
- Song detection might be failing silently
- No clear logging to diagnose why detection isn't working

**Fix Applied**:
- Added explicit ShazamIO availability check during initialization
- Added better error handling for ImportError when ShazamIO is missing
- Added debug logging to show:
  - When song detection is attempted
  - Why detection might fail (buffer not ready, ShazamIO unavailable, etc.)
  - Shazam API response details
- Improved logging for song detection status

**Locations**: 
- `services/hub/main.py` - Added logging for song detection status
- `services/sensors/mic_song_detect.py` - Improved initialization and error handling

## What to Check

1. **Temperature Issue**:
   - Check if BME280 sensor is properly connected (I2C)
   - Verify sensor is initialized: Look for "✓ BME280 initialized successfully" in logs
   - Check logs for "BME280 cached temperature is None" warnings
   - If temperature is still None, check I2C connection: `sudo i2cdetect -y 1`

2. **Song Detection Issue**:
   - Check if ShazamIO is installed: `pip list | grep shazamio`
   - If not installed: `pip install shazamio aiohttp`
   - Check logs for:
     - "✅ ShazamIO library available - song detection will work"
     - "🎵 Running song detection from audio buffer..."
     - "✅ Song detected: ..."
   - Ensure internet connection is available (Shazam requires internet)
   - Check if audio buffer is ready: Look for "Audio buffer not ready" messages

## Testing

After restarting the hub service, you should see:
- Temperature readings appearing on the dashboard
- Song detection attempting every 30 seconds
- Better logging to diagnose any remaining issues

## Next Steps

If issues persist:
1. Check system logs: `journalctl -u pulse-hub.service -n 100`
2. Verify dependencies: `pip list | grep -E "(shazamio|adafruit-circuitpython-bme280)"`
3. Test BME280 directly: `python3 -c "from services.sensors.bme280_reader import BME280Reader; r = BME280Reader(); print(r.read_sensor())"`
4. Check audio device: `arecord -l` to verify microphone is detected
