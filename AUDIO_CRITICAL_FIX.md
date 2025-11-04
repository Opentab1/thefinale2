# CRITICAL FIX: Decibel Reader and Song Detector

## Problem
The decibel reader and song detector were stopping after a few minutes of operation. This was a critical failure that prevented the system from functioning properly.

## Root Causes Identified

1. **Silent Stream Failures**: Audio streams (PyAudio/sounddevice) could close or become inactive without raising exceptions, causing the monitoring loop to silently fail.

2. **Insufficient Health Checks**: The watchdog was checking every 10 seconds with a 60+ second threshold, allowing failures to go undetected for too long.

3. **No Stream State Validation**: The code didn't check if streams were still active before attempting to read from them.

4. **Missing Failure Detection**: No tracking of successful reads vs. failed reads, so silent failures weren't detected.

5. **Conservative Recovery**: Recovery mechanisms were too slow to react to failures.

## Fixes Applied

### 1. Stream Health Tracking (CRITICAL)
- Added `_stream_active` flag to track stream state
- Added `_stream_last_successful_read` timestamp to detect when reads stop working
- Added `_stream_read_timeout` (5 seconds) to detect dead streams quickly

### 2. Enhanced Stream Validation
- **PyAudio**: Now checks `pa_stream.is_active()` before reading
- **sounddevice**: Now checks `sd_stream.active` before reading
- Validates that actual data is returned (not None or empty)
- Updates success timestamp only on successful reads

### 3. Faster Watchdog Detection
- Reduced watchdog check interval from 10 seconds to **5 seconds**
- Reduced watchdog restart threshold from 60+ seconds to **15 seconds**
- Added stream health check in watchdog that triggers if no successful read in 5 seconds
- Added periodic stream health validation (every 30 seconds)

### 4. Improved Error Recovery
- Faster detection of stream failures (5 second timeout instead of 60+ seconds)
- Immediate restart on stream inactivity detection
- Better error messages to identify failure points
- Automatic stream restart when health checks fail

### 5. Enhanced Monitoring Loop
- Tracks `last_successful_read_time` to detect when reads stop
- Forces restart if no successful read in timeout period
- Validates stream state before each read attempt
- Better error handling with immediate restart on critical failures

## Key Changes in Code

### Stream Health Tracking
```python
# Added tracking variables
self._stream_active = False
self._stream_last_successful_read = 0.0
self._stream_read_timeout = 5.0  # 5 second timeout
```

### Stream Validation Before Read
```python
# PyAudio
if not pa_stream.is_active():
    raise self.StreamRuntimeError("PyAudio stream is no longer active")

# sounddevice  
if not sd_stream.active:
    raise self.StreamRuntimeError("sounddevice stream is no longer active")
```

### Faster Watchdog
```python
# Reduced from 60s to 15s
self._watchdog_restart_threshold = max(15.0, self._song_detect_interval * 2)

# Check every 5 seconds instead of 10
self.stop_event.wait(5)
```

### Stream Health Check in Watchdog
```python
# Check if stream is dead
stream_stale = (
    self._stream_last_successful_read > 0 and
    (now - self._stream_last_successful_read) > self._stream_read_timeout
)
if stream_stale:
    # Force restart immediately
```

## Testing

### Step 1: Run Diagnostic Script
```bash
cd /workspace
python3 diagnose_audio_issue.py
```

This will run for 5 minutes and monitor the audio system for failures.

### Step 2: Monitor Logs
Watch for these log messages that indicate the fixes are working:
- `🔊 Audio monitoring active - dB readings will appear shortly`
- `🔊 Audio: XX.X dB (Peak: XX.X dB)` - should appear every 2 seconds
- If a failure is detected, you'll see: `Audio stream appears dead (no successful read for X.Xs) - forcing restart`
- Stream should automatically restart: `🔊 Audio monitoring active - dB readings will appear shortly`

### Step 3: Check System Status
```bash
# Check if audio monitor is running
ps aux | grep mic_song_detect

# Check logs for errors
tail -f /var/log/pulse/hub.log | grep -i audio
```

## Expected Behavior After Fix

1. **Decibel readings** should update every 2 seconds continuously
2. **Song detection** should run every 10 seconds (configurable)
3. **Automatic recovery**: If the stream fails, it should restart within 5-15 seconds
4. **No silent failures**: The watchdog will detect and restart failed streams quickly

## Verification Checklist

- [ ] Decibel readings appear every 2 seconds
- [ ] Song detection runs every 10 seconds
- [ ] System runs for extended periods (30+ minutes) without stopping
- [ ] If stream fails, it automatically restarts within 15 seconds
- [ ] No "Audio monitoring thread died" errors (or if they occur, thread restarts automatically)

## If Issues Persist

1. Run the diagnostic script: `python3 diagnose_audio_issue.py`
2. Check system logs: `journalctl -u pulse-mic -f` (if running as service)
3. Verify audio device: `arecord -l`
4. Test audio manually: `arecord -d 1 test.wav && aplay test.wav`

## Files Modified

- `/workspace/services/sensors/mic_song_detect.py` - All critical fixes applied

## Summary

This fix makes the audio monitoring system **much more resilient** by:
- Detecting failures **4x faster** (15s vs 60s)
- Checking stream health **2x more frequently** (5s vs 10s)
- Validating streams before each read
- Tracking successful reads to detect silent failures
- Automatically restarting failed streams immediately

The system should now run **continuously without stopping**, and if any failure occurs, it will **automatically recover within 5-15 seconds**.
