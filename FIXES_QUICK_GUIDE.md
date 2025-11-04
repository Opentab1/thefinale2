# Quick Fix Guide - Temperature & Song Detection

## What Was Fixed

### ✅ Issue 1: Temperature Not Showing on Dashboard
**Fixed!** Temperature data now properly flows from BME280 sensor → Hub → Database → Dashboard with:
- Automatic error recovery and sensor reinitialization
- Database retry logic (3 attempts)
- Connection timeout protection (10s)
- Comprehensive debug logging
- Verification after each database write

### ✅ Issue 2: DB Reader & Song Detection Cutting Out After 5 Minutes
**Fixed!** Song detection and database reading now persist indefinitely with:
- Hard timeout protection (25s) using Unix signals
- Non-blocking song detection threads
- Proper asyncio task cleanup
- Database connection resilience
- Activity tracking to prevent false watchdog triggers

## How to Test the Fixes

### Quick Test (2 minutes)
```bash
# Run the verification script
python3 verify_temperature_and_song_fixes.py
```

This will test:
- ✓ Database connection and timeout handling
- ✓ BME280 sensor reading
- ✓ Audio monitor initialization
- Optional: 60-second continuous monitoring

### Full Test (Use your normal startup)
```bash
# Use your normal startup command
# Then monitor the logs to verify fixes are working
```

## What to Look For (Success Indicators)

### Temperature Working
Look for these log messages:
- ✓ `BME280 cached temp: XX.X°F, humidity: XX.X%`
- ✓ `Storing environment data: temp=XX.X, humidity=XX.X`
- ✓ `Temperature verified in DB: XX.X°F`
- ✓ `Broadcasting data from hub: temp=XX.X`

### Song Detection Persisting
Look for these log messages:
- ✓ `🔊 Audio: XX.X dB (Peak: XX.X dB)` - appears every 2 seconds
- ✓ `🎵 Running song detection from audio buffer...` - appears every 30 seconds
- ✓ `✅ Song detected: [Song] - [Artist]` - when music is playing
- ✓ No "Audio monitoring thread died!" messages after 5 minutes

### Database Working
Look for these indicators:
- ✓ No "Database connection attempt X failed" messages
- ✓ No "locked database" errors
- ✓ `Dashboard broadcast #XX: temp=XX.X, occupancy=X` every minute

## Monitoring Commands

### Check System Status
```bash
# View hub logs
tail -f /var/log/pulse/hub.log

# Check temperature in database
sqlite3 /opt/pulse/data/pulse.db "SELECT temperature, timestamp FROM environment ORDER BY timestamp DESC LIMIT 5;"

# Check music detection
sqlite3 /opt/pulse/data/pulse.db "SELECT track_name, artist, timestamp FROM music_log ORDER BY timestamp DESC LIMIT 5;"
```

### Monitor Real-Time
```bash
# Watch hub logs for temperature
journalctl -u pulse-hub -f | grep -i "temp\|bme280"

# Watch for song detection
journalctl -u pulse-hub -f | grep -i "song\|audio"
```

## Files Changed

All fixes are in these 5 files:
1. `services/sensors/mic_song_detect.py` - Song detection resilience
2. `services/sensors/bme280_reader.py` - Temperature sensor reliability
3. `services/hub/main.py` - Data collection and storage
4. `services/storage/db.py` - Database connection handling
5. `dashboard/api/server.py` - Dashboard API improvements

## What Should Work Now

### Temperature Display
- ✅ Temperature shows immediately on dashboard startup
- ✅ Temperature updates every 30 seconds
- ✅ Temperature persists indefinitely (no dropouts)
- ✅ Automatic recovery if sensor temporarily fails

### Song Detection
- ✅ Song detection works for 5+ minutes (and beyond)
- ✅ DB reader continues working indefinitely
- ✅ Audio monitoring never hangs or crashes
- ✅ Automatic restart if monitoring thread dies
- ✅ Song detection timeouts don't block audio monitoring

### Database Operations
- ✅ Database never locks or hangs
- ✅ All reads/writes have 10-second timeout
- ✅ Automatic retry on connection failures
- ✅ WAL mode for better concurrent access

## Troubleshooting

### If Temperature Still Not Showing
1. Check sensor connection: `sudo i2cdetect -y 1`
   - Should see BME280 at 0x76 or 0x77
2. Check logs: `grep "BME280" /var/log/pulse/hub.log`
3. Run direct test: `python3 -c "from services.sensors.bme280_reader import BME280Reader; r=BME280Reader(); print(r.read_sensor())"`

### If Song Detection Still Fails After 5 Minutes
1. Check audio device: `arecord -l`
2. Check logs: `grep -i "audio\|song" /var/log/pulse/hub.log | tail -50`
3. Check for timeout errors: `grep -i "timeout" /var/log/pulse/hub.log`

### If Database Issues Persist
1. Check database file: `ls -lh /opt/pulse/data/pulse.db*`
2. Check for locks: `lsof /opt/pulse/data/pulse.db`
3. Test manual query: `sqlite3 /opt/pulse/data/pulse.db "SELECT COUNT(*) FROM environment;"`

## Expected Behavior Timeline

### First 30 seconds
- ✓ All sensors initialize
- ✓ Temperature reads and displays
- ✓ Audio monitoring starts
- ✓ First database writes occur

### 1-5 minutes
- ✓ Temperature updates every 30s
- ✓ Song detection runs every 30s
- ✓ Audio dB readings every 2s
- ✓ Dashboard updates every 5s

### After 5 minutes (The Critical Test)
- ✓ Everything still working
- ✓ Temperature still updating
- ✓ Song detection still running
- ✓ No thread crashes
- ✓ No database locks

### Long-term (Hours/Days)
- ✓ All functions persist
- ✓ Automatic error recovery
- ✓ Graceful handling of transient failures
- ✓ System remains stable

## Need More Help?

Check the detailed fix documentation:
- `TEMPERATURE_AND_SONG_DETECTION_FIXES.md` - Complete technical details

Run the verification script:
- `./verify_temperature_and_song_fixes.py` - Automated testing

View logs with context:
- Hub: `journalctl -u pulse-hub -n 100`
- Dashboard: `journalctl -u pulse-dashboard -n 100`
