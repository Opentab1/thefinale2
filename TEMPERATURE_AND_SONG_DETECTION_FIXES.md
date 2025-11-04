# Temperature and Song Detection Fixes

## Issues Addressed

### Issue 1: Temperature Not Showing on Local Dashboard
**Problem**: Temperature sensor data was not displaying on the dashboard despite other sensors working correctly.

**Root Causes**:
1. Missing debug logging to track temperature data flow
2. No verification that temperature data was being stored correctly in the database
3. Potential data propagation issues between BME280 sensor → Hub → Database → Dashboard API → UI

**Fixes Applied**:

1. **Enhanced BME280 Sensor Reading** (`services/sensors/bme280_reader.py`):
   - Added error recovery mechanism with automatic sensor reinitialization after 5 consecutive failures
   - Improved error logging throughout the reading loop
   - Added consecutive error tracking to detect sensor failures early

2. **Improved Hub Data Collection** (`services/hub/main.py`):
   - Added debug logging to track temperature values at collection time
   - Enhanced error logging when BME280 cached values are None
   - Added verification logging after direct sensor reads

3. **Enhanced Database Storage** (`services/hub/main.py`):
   - Added retry logic (3 attempts) for database writes
   - Added verification step to confirm temperature data was stored correctly
   - Added detailed debug logging for all environment data being stored

4. **Improved Database Connection Handling** (`services/storage/db.py`):
   - Added connection retry mechanism (3 attempts with 0.5s delay)
   - Implemented 10-second connection timeout to prevent hanging
   - Enabled WAL mode for better concurrent access
   - Set busy timeout to 5 seconds to handle lock contention
   - Added proper connection cleanup in finally block

5. **Enhanced Dashboard API** (`dashboard/api/server.py`):
   - Added debug logging for temperature data in broadcast and API endpoints
   - Added periodic info logging (every 1 minute) for dashboard broadcasts
   - Improved error handling with full stack traces
   - Added try-catch blocks around database reads

### Issue 2: DB Reader and Song Detection Cutting Out After 5 Minutes
**Problem**: Database reading and song detection would stop working after approximately 5 minutes of operation.

**Root Causes**:
1. Song detection async calls could hang indefinitely despite timeouts
2. ShazamIO recognition could get stuck waiting for network responses
3. Database connections could timeout or get stuck in locked state
4. Watchdog not properly detecting all failure modes

**Fixes Applied**:

1. **Improved Song Detection Timeout Handling** (`services/sensors/mic_song_detect.py`):
   - Added hard timeout using Unix signals (25 seconds) as a safety net
   - Improved asyncio task cleanup to cancel pending tasks
   - Added proper cleanup of temporary WAV files in finally block
   - Made song detection thread completely non-blocking
   - Added try-catch around song detection thread startup

2. **Enhanced Activity Tracking** (`services/sensors/mic_song_detect.py`):
   - Added `_last_activity` update in all code paths to prevent false watchdog triggers
   - Critical fix: Always update `_last_activity` even when song detection is not running
   - This prevents the watchdog from thinking the monitoring is stuck

3. **Database Connection Resilience** (`services/storage/db.py`):
   - Same improvements as listed above for Issue 1
   - These prevent database locks from causing the reader to hang

4. **Thread Safety Improvements** (`services/sensors/mic_song_detect.py`):
   - Song detection now runs in a separate daemon thread that can't block audio monitoring
   - Audio monitoring continues even if song detection hangs
   - Watchdog can now detect and restart the entire monitoring thread if needed

## Technical Details

### Temperature Data Flow
```
BME280 Sensor (I2C)
  ↓ read_sensor() every 30s
BME280Reader cached values
  ↓ get_all_readings()
Hub _collect_sensor_data()
  ↓ _store_sensor_data()
Database (environment table)
  ↓ get_latest_environment()
Dashboard API broadcast_sensor_data()
  ↓ WebSocket emit
Dashboard UI (React)
```

### Song Detection Flow
```
Audio Stream (PyAudio/sounddevice)
  ↓ continuous read
Audio Buffer (5 seconds rolling)
  ↓ every 30 seconds
Song Detection Thread (daemon)
  ↓ save to temp WAV
ShazamIO Recognition (async with timeout)
  ↓ on success
Update current_song
  ↓
Store in database (music_log)
  ↓
Dashboard displays song info
```

## Key Improvements

### Reliability
- **Retry Logic**: Database operations retry up to 3 times before failing
- **Timeout Protection**: All async operations have hard timeouts
- **Error Recovery**: BME280 automatically reinitializes after failures
- **Connection Pooling**: WAL mode enables better concurrent database access

### Observability
- **Debug Logging**: Track data flow through entire system
- **Periodic Status**: Dashboard broadcasts log status every minute
- **Error Traces**: Full stack traces for all errors
- **Verification**: Database writes are verified immediately after

### Resilience
- **Watchdog Protection**: Audio monitoring restarts if it crashes
- **Non-blocking Design**: Song detection can't block audio monitoring
- **Signal Timeouts**: Hard kill for stuck song detection threads
- **Activity Tracking**: False watchdog triggers eliminated

## Testing Recommendations

1. **Temperature Monitoring**:
   - Check logs for "BME280 cached temp" messages
   - Verify "Storing environment data" shows temperature values
   - Confirm "Temperature verified in DB" appears after storage
   - Monitor dashboard broadcast logs for temperature data

2. **Song Detection**:
   - Watch for "Running song detection from audio buffer" messages
   - Check that audio monitoring continues even if song detection times out
   - Verify watchdog doesn't trigger false restarts
   - Confirm songs appear in dashboard after detection

3. **Database Operations**:
   - Monitor for any "Database connection attempt" retry messages
   - Check that all database operations complete within timeout
   - Verify no "locked database" errors appear

## Expected Log Output

### Normal Operation (Temperature)
```
BME280 cached temp: 72.5°F, humidity: 45.2%
Storing environment data: temp=72.5, humidity=45.2, light=350, noise=55.3
Temperature verified in DB: 72.5°F
Broadcasting data from hub: temp=72.5, humidity=45.2
```

### Normal Operation (Song Detection)
```
🎵 Running song detection from audio buffer...
🔊 Audio: 62.3 dB (Peak: 75.1 dB)
✅ Song detected: Song Title - Artist Name
```

### Error Recovery (Temperature)
```
BME280 cached temperature is None - attempting direct read
Direct BME280 read successful: 72.5°F
```

### Error Recovery (Song Detection)
```
Song detection timed out (20s) - skipping
Audio monitoring thread died! Restarting...
✓ Audio stream opened successfully (PyAudio, device 1)
```

## Files Modified

1. `/workspace/services/sensors/mic_song_detect.py`
2. `/workspace/services/sensors/bme280_reader.py`
3. `/workspace/services/hub/main.py`
4. `/workspace/services/storage/db.py`
5. `/workspace/dashboard/api/server.py`

## Next Steps

If issues persist:
1. Check system logs: `journalctl -u pulse-hub -f`
2. Check dashboard logs: `journalctl -u pulse-dashboard -f`
3. Verify database isn't corrupted: `sqlite3 /opt/pulse/data/pulse.db "SELECT * FROM environment ORDER BY timestamp DESC LIMIT 10;"`
4. Check I2C connection: `sudo i2cdetect -y 1` (should show BME280 at 0x76 or 0x77)
5. Test audio device: `arecord -l` and `arecord -d 5 test.wav`
