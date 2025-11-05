# Song Detector & dB Reader Stability Fix

## Problem
The song detector and dB reader were failing after just a few minutes of operation. This was caused by multiple cascading failures:

1. **Song Detector Issues:**
   - Detection thread could die without recovery
   - New event loop created for each detection (resource leak)
   - No timeout on Shazam API calls (could hang indefinitely)
   - No watchdog to detect and restart failed threads

2. **dB Reader Issues:**
   - Audio stream could get stuck without recovery
   - Health checks were present but not aggressive enough
   - No hub-level monitoring to restart services

3. **Resource Leaks:**
   - New Shazam instances created for each detection
   - Event loops not properly cleaned up
   - ClientSession objects not closed

## Solution

### 1. Song Detector (`services/sensors/song_detector.py`)

**Added Watchdog Mechanism:**
- Background watchdog thread monitors detection thread health
- Automatically restarts thread if it dies
- Heartbeat tracking to detect stuck threads
- Rate limiting to prevent restart loops

**Fixed Resource Leaks:**
- Reusable event loop in dedicated thread (instead of creating new one each time)
- Reusable Shazam instance with periodic refresh (every hour)
- Proper cleanup of event loops and Shazam clients

**Added Timeouts:**
- 15-second timeout on recognition futures
- 10-second timeout on Shazam API calls
- Automatic instance reset on timeout/error

**Enhanced Error Recovery:**
- Thread continues even after errors
- Automatic restart on thread death
- Comprehensive logging for debugging

### 2. AudioMonitor (`services/sensors/mic_song_detect.py`)

**Enhanced Cleanup:**
- Properly stops SongDetector instance during cleanup
- Ensures all resources are released

**Existing Recovery Mechanisms (Already Good):**
- Watchdog loop for audio stream health
- Health check thread for dB readings and song detection
- Automatic stream restart on failures
- Event loop heartbeat monitoring
- Stuck thread detection and kill

### 3. Hub-Level Monitoring (`services/hub/main.py`)

**Added Audio Health Monitor:**
- Dedicated thread monitoring audio services every 30 seconds
- Detects stuck dB readings (no change for 60 seconds)
- Checks song detector thread health
- Automatically restarts audio monitor on consecutive failures
- Rate limiting to prevent restart storms

**Enhanced Stop Method:**
- Properly stops SongDetector when hub stops
- Cleans up health monitor thread

## Key Improvements

1. **Multi-Layer Monitoring:**
   - SongDetector has its own watchdog
   - AudioMonitor has health checks
   - Hub has service-level monitoring
   - Three layers of protection ensure services stay running

2. **Resource Management:**
   - Reusable event loops prevent leaks
   - Reusable Shazam instances prevent connection buildup
   - Proper cleanup on all shutdown paths

3. **Timeout Protection:**
   - All async operations have timeouts
   - Stuck operations are automatically cancelled
   - Failed operations trigger recovery

4. **Automatic Recovery:**
   - Dead threads are automatically restarted
   - Stuck threads are detected and killed
   - Failed services are automatically restarted

## Testing

To verify the fixes work:

1. **Check logs for watchdog activity:**
   ```bash
   grep "Song detector watchdog\|Audio health monitor" /var/log/pulse/hub.log
   ```

2. **Monitor thread health:**
   ```python
   # Check if threads are alive
   audio_monitor.song_detector.detection_thread.is_alive()
   audio_monitor.song_detector.watchdog_thread.is_alive()
   ```

3. **Watch for automatic restarts:**
   - If a thread dies, you should see "Song detection thread died! Restarting..."
   - If dB reader gets stuck, you should see automatic restart

## Expected Behavior

- **Song Detector:** Runs continuously, detects songs every 60 seconds (or configured interval). If thread dies, watchdog restarts it within 10 seconds.

- **dB Reader:** Continuously monitors audio levels. If stream gets stuck, watchdog restarts it within 20 seconds. If multiple failures occur, hub-level monitor restarts entire audio monitor.

- **Recovery Time:** Services should recover from failures within 10-60 seconds depending on the type of failure.

## Files Modified

1. `services/sensors/song_detector.py` - Added watchdog, reusable event loop, timeouts
2. `services/hub/main.py` - Added audio health monitoring
3. `services/sensors/mic_song_detect.py` - Enhanced cleanup

## Summary

Both services now have **triple-layer protection**:
1. **Self-healing:** Each service monitors itself and recovers from failures
2. **Parent monitoring:** AudioMonitor monitors its components
3. **Hub-level monitoring:** Hub monitors all services and restarts if needed

The song detector and dB reader will now **work reliably** and recover automatically from any failures that occur.
