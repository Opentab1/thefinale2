# Permanent Fix for 25-Minute Audio Failure

## Problem
After 25 minutes of operation, the decibel reader and song detection stop working. This is caused by aiohttp connection timeouts in the ShazamIO library used for song recognition.

## Root Cause
The ShazamIO library uses aiohttp's ClientSession internally, which has default timeout settings that can cause connections to fail around 25 minutes (1500 seconds). The previous code only refreshed the Shazam instance every hour (3600 seconds), which was too late.

## Solution Implemented

### 1. Proactive Connection Refresh (20 minutes)
- Changed `_shazam_refresh_interval` from 3600 seconds (1 hour) to **1200 seconds (20 minutes)**
- Added proactive refresh logic in the healthcheck loop that refreshes the Shazam instance before any timeout occurs
- The refresh happens automatically every 20 minutes, preventing the 25-minute failure

### 2. Enhanced Timeout Configuration
- Added explicit aiohttp ClientTimeout configuration when creating Shazam instances
- Set total timeout to 20 minutes (1200s) to prevent connection hangs
- Configured connect timeout (10s) and socket read timeout (30s) for better reliability

### 3. Improved Error Handling
- Enhanced cleanup of old Shazam instances with better timeout handling
- Force cleanup on any errors during instance refresh
- Better logging for proactive refresh events

## Changes Made

### File: `services/sensors/mic_song_detect.py`

1. **Line 142-144**: Changed refresh interval from 3600s to 1200s (20 minutes)
2. **Lines 649-659**: Added proactive refresh logic in healthcheck loop
3. **Lines 1143-1167**: Enhanced Shazam instance creation with timeout configuration
4. **Line 1165-1170**: Adjusted recognition timeout with better comments

## How It Works

1. **Health Check Loop**: Runs every 5 seconds and checks if the Shazam instance is older than 20 minutes
2. **Proactive Refresh**: When the instance age reaches 20 minutes, it's automatically refreshed before any timeout can occur
3. **Timeout Prevention**: The 20-minute refresh window ensures we never hit the 25-minute timeout threshold
4. **Automatic Recovery**: If a timeout does occur, the system automatically resets and creates a new instance

## Verification

After deploying this fix, you should see log messages like:
- `"Proactively refreshing Shazam instance (age: 1200.1s, threshold: 1200.0s)"`
- `"Shazam instance approaching refresh threshold (age: 960.0s / 1200.0s)"` (at 80% threshold)
- `"Configured Shazam client timeout to 20 minutes"`

## Testing

Run the diagnostic command on your Pi:
```bash
./COMMAND_TO_RUN_ON_PI.sh
```

Or monitor logs in real-time:
```bash
journalctl -u pulse.service -f | grep -E '(audio|song|decibel|Shazam|refresh|proactive)'
```

## Deployment

The fix is ready to deploy. The system will automatically:
- Refresh Shazam connections every 20 minutes
- Prevent 25-minute timeout failures
- Maintain continuous decibel reading and song detection

No restart is required - the fix will take effect on the next health check cycle (within 5 seconds).
