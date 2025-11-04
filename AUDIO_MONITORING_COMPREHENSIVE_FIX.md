# Audio Monitoring Comprehensive Fix

## Problem Summary
The DB reader (decibel monitoring) and song detector were stopping after approximately 4 minutes 30 seconds of operation, significantly earlier than previous runs.

## Root Causes Identified

### 1. **Silent Audio Stream Failures**
- PyAudio/sounddevice streams could close unexpectedly without raising exceptions
- The monitoring thread would remain alive but wouldn't process any audio data
- Watchdog only checked if thread was alive, not if it was actually receiving data

### 2. **Inadequate Watchdog Mechanism**
- Only detected dead threads, not stuck/blocked threads
- No detection of audio stream health
- No verification that actual audio data was being received

### 3. **Detection Event Loop Crashes**
- The dedicated asyncio event loop for Shazam could crash without restart
- No health check mechanism for the event loop
- If loop died, song detection would silently fail

### 4. **Resource Accumulation**
- Shazam ClientSession could accumulate issues over time
- Only time-based refresh, no usage-based refresh
- Could lead to degraded performance or hangs

### 5. **Broad Exception Handling**
- Many `except Exception:` blocks that swallowed critical errors
- Errors were logged but not properly recovered from
- Thread would continue in degraded state

### 6. **No Stream Read Error Handling**
- Audio stream read operations had no error handling
- If read failed, it would raise exception and kill the thread
- No attempt to detect or recover from stream errors

## Holistic Fix Implementation

### 1. Enhanced Watchdog System
```python
- Track _last_audio_data_time to detect when audio stream is dead
- Check every 10 seconds if we've received audio data in last 45 seconds
- If no audio data, force restart of monitoring thread
- Check detection event loop health and recreate if needed
- Implement consecutive failure tracking to prevent restart loops
- Add graduated retry delays (30s after 3 consecutive failures)
```

### 2. Audio Stream Health Tracking
```python
- Added _last_audio_data_time timestamp updated on every successful read
- Added _stream_healthy flag to track stream state
- Watchdog monitors audio data reception, not just thread liveness
- Stream read errors now break the loop to trigger restart
- Proper error handling around stream read operations
```

### 3. Detection Event Loop Health Check
```python
- New _is_detection_loop_healthy() method checks:
  * Thread is alive
  * Loop is not closed
  * Loop is running
- Watchdog periodically checks loop health
- Auto-recreate loop if unhealthy
- Added try-catch in loop runner to prevent silent crashes
```

### 4. Improved Resource Management
```python
- Reduced Shazam refresh interval from 3600s to 1800s (30 minutes)
- Added usage-based refresh: recreate after 50 uses
- Track _shazam_use_count to prevent resource accumulation
- Better logging of Shazam instance lifecycle
- Proper cleanup on instance replacement
```

### 5. Better Error Recovery
```python
- Stream read failures now trigger immediate restart
- Detection errors check loop health and recreate if needed
- Monitoring loop errors don't set running=False
- Let watchdog handle restart instead of giving up
- Added detailed error logging with stack traces
```

### 6. Enhanced Monitoring Thread Lifecycle
```python
- Clean up old thread before starting new one
- Initialize timestamps to prevent false alarms
- Named threads for better debugging
- Proper stop handling with timeout
- Logging at each lifecycle stage
```

### 7. Health Status API
```python
- New get_health_status() method provides:
  * Monitoring thread status
  * Stream health
  * Time since last activity/audio data
  * Detection loop health
  * Shazam instance age and usage
  * Song detection stats
```

## Key Improvements

### Reliability
- Audio stream failures are detected within 45 seconds
- Automatic restart of failed components
- No silent failures - all issues are logged
- Graceful degradation with retry logic

### Observability
- Detailed health status endpoint
- Track exact time since last audio data
- Monitor component health in real-time
- Clear logging of lifecycle events

### Resource Management
- Periodic refresh of Shazam instances
- Usage-based refresh to prevent accumulation
- Proper cleanup of old resources
- Stream lifecycle properly managed

### Resilience
- Multiple failure detection mechanisms
- Automatic restart of all components
- Graduated retry delays
- Protection against restart loops

## Testing Recommendations

### 1. Long-Running Test
```bash
# Run monitoring for at least 30 minutes
# Should see:
# - Continuous dB readings
# - Periodic song detection attempts
# - No thread deaths
# - No "no audio data" errors
```

### 2. Health Monitoring
```python
# Periodically check health status
monitor.get_health_status()
# Verify:
# - monitoring_thread_alive: True
# - stream_healthy: True
# - last_audio_data_seconds_ago: < 5
# - detection_loop_healthy: True
```

### 3. Recovery Testing
```bash
# Simulate failures:
# - Disconnect/reconnect microphone
# - Kill detection loop
# - Network interruptions during Shazam
# Should see automatic recovery
```

## Monitoring in Production

### Key Metrics to Watch
1. **last_audio_data_seconds_ago** - Should be < 5 seconds
2. **monitoring_thread_alive** - Should always be True
3. **stream_healthy** - Should be True when receiving audio
4. **detection_loop_healthy** - Should be True when song detection enabled

### Alert Thresholds
- last_audio_data_seconds_ago > 60 seconds → Critical
- monitoring_thread_alive = False → Critical
- detection_loop_healthy = False for > 5 minutes → Warning

### Log Patterns to Watch For
- "Audio stream appears dead" → Indicates automatic recovery
- "Monitoring thread failed X times" → May need investigation
- "Detection loop appears unhealthy" → Event loop issues
- "Shazam instance cleaned up" → Normal periodic refresh

## Files Modified
- `/workspace/services/sensors/mic_song_detect.py` - Core monitoring logic

## Backward Compatibility
- All existing APIs preserved
- New health status API is additive
- No breaking changes to configuration
- Existing service files work as-is

## Expected Behavior After Fix
1. **Continuous Operation**: Should run indefinitely without stopping
2. **Automatic Recovery**: Any failures trigger automatic restart within 10-45 seconds
3. **Clean Logging**: Clear indication of all lifecycle events
4. **Resource Hygiene**: Periodic cleanup prevents accumulation
5. **Health Visibility**: Real-time status available via health API
