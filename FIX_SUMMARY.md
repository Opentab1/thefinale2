# Quick Fix Summary - DB Reader & Song Detection

## Issues Diagnosed

### 1. DB Reader Cutting Out
**Problem**: The dashboard API's `broadcast_sensor_data()` loop was crashing on database exceptions without recovery, causing the DB reader to stop updating the UI.

**Root Cause**: 
- Weak error handling in broadcast loop
- No retry logic for database connection failures
- Database lock timeouts not handled properly

### 2. Song Detection Not Working
**Problem**: Song detection via ShazamIO was failing silently or not initializing properly.

**Root Cause**:
- Missing or improperly configured audio libraries
- Poor error handling in song detection initialization
- Audio device detection issues
- Missing ShazamIO library or its dependencies

## Fixes Applied

### Database & API Fixes

1. **Enhanced Broadcast Loop Error Recovery** (`dashboard/api/server.py`)
   - Added consecutive error tracking
   - Automatic database reconnection after 10 consecutive failures
   - Better error logging with attempt counts
   - Graceful degradation on database query failures

2. **Database Connection Retry Logic** (`services/storage/db.py`)
   - Added retry mechanism with exponential backoff
   - 10-second timeout on connections
   - Handles SQLite database lock gracefully
   - Up to 3 retry attempts on lock errors

### Song Detection Fixes

1. **Robust Audio Monitor Initialization** (`services/sensors/mic_song_detect.py`)
   - Early validation of ShazamIO availability
   - Graceful fallback when song detection unavailable
   - Better async error handling
   - Improved logging for troubleshooting

2. **Enhanced Hub Initialization** (`services/hub/main.py`)
   - Explicit song detector status checking
   - Detailed initialization logging
   - Graceful continuation without audio if initialization fails
   - Better error messages for troubleshooting

### Installation & Repair Scripts

1. **`install_audio_deps.sh`** - Installs/repairs all audio dependencies
   - System-level audio libraries (portaudio, ALSA)
   - Python audio packages (numpy, sounddevice, pyaudio)
   - ShazamIO and dependencies
   - Audio device detection test
   - ShazamIO installation verification

2. **`quick_fix.sh`** - One-command fix for both issues
   - Optionally stops running system
   - Installs/updates audio dependencies
   - Validates database integrity
   - Verifies all required libraries
   - Provides clear next steps

## How to Apply the Fix

### Quick Method (Recommended)
```bash
./quick_fix.sh
```

This will:
1. Install all dependencies
2. Verify database integrity
3. Check audio library installation
4. Provide status report

### Manual Method

1. Install audio dependencies:
```bash
./install_audio_deps.sh
```

2. Restart the Pulse system:
```bash
./start_pulse.sh
```

## Verification

After applying fixes, verify:

1. **DB Reader Working**:
   - Dashboard loads and shows data
   - Values update every 5 seconds
   - No "connection lost" errors

2. **Song Detection Working**:
   - Check logs for "✅ ShazamIO library available"
   - Look for "🎵 Song detection will run every 30 seconds"
   - Play music near microphone and wait 30-60 seconds
   - Song info should appear in dashboard

## Expected Behavior

### DB Reader
- Continuous updates every 5 seconds
- Auto-recovery after database errors
- Maximum 10 consecutive errors before reconnection attempt
- Graceful degradation if hub unavailable

### Song Detection
- Attempts every 30 seconds (configurable via `SONG_DETECT_INTERVAL_SEC`)
- 20-second timeout per attempt
- Non-blocking (runs in background thread)
- Logs detected songs to console and database
- Falls back to music controller if mic detection fails

## Troubleshooting

### DB Reader Still Cutting Out
1. Check database file permissions:
   ```bash
   ls -la /opt/pulse/data/pulse.db
   ```

2. Check for disk space:
   ```bash
   df -h
   ```

3. Monitor dashboard logs:
   ```bash
   journalctl -f | grep -i "database\|broadcast"
   ```

### Song Detection Still Not Working
1. Verify audio device:
   ```bash
   arecord -l
   ```

2. Test microphone:
   ```bash
   arecord -d 3 test.wav && aplay test.wav
   ```

3. Check installed packages:
   ```bash
   pip3 list | grep -E "shazam|pyaudio|sounddevice|numpy"
   ```

4. Check audio monitor logs:
   ```bash
   journalctl -f | grep -i "audio\|song\|shazam"
   ```

## Technical Details

### Database Connection Pool
- Timeout: 10 seconds
- Max retries: 3
- Retry delay: 0.1s with exponential backoff
- Row factory: sqlite3.Row (dict-like access)

### Audio Processing
- Sample rate: 44100 Hz
- Channels: Mono (1)
- Buffer size: 2048 samples
- Rolling buffer: 5 seconds for song detection
- dB update interval: 2 seconds
- Song detection interval: 30 seconds (configurable)

### Error Recovery
- Database: Auto-reconnect after 10 failures
- Audio: Watchdog thread restarts monitoring on crash
- Song detection: Isolated in background thread with timeout

## Configuration

### Environment Variables

```bash
# Audio monitoring
export SONG_DETECT_INTERVAL_SEC=30        # Song detection frequency
export DB_UPDATE_INTERVAL_SEC=2.0         # dB reading frequency
export PULSE_MIC_DEVICE_INDEX=0           # Force specific audio device

# Dashboard
export PULSE_SIO_MODE=threading           # SocketIO async mode
```

## Files Modified

- `dashboard/api/server.py` - Enhanced broadcast loop
- `services/storage/db.py` - Added retry logic
- `services/sensors/mic_song_detect.py` - Better error handling
- `services/hub/main.py` - Improved initialization
- `install_audio_deps.sh` - NEW - Audio dependency installer
- `quick_fix.sh` - NEW - One-command fix script

## Next Steps

1. Apply the fix using `./quick_fix.sh`
2. Restart the system
3. Monitor logs for 2-3 minutes
4. Verify all sensors working in dashboard
5. Test song detection with music

If issues persist, check the troubleshooting section above.
