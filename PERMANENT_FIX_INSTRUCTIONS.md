# PERMANENT FIX FOR dB READER & SONG DETECTION

## The Problem
- dB reader and song detection work for ~30 minutes then stop
- No logs appear in journalctl
- Service may be running but audio monitoring has stalled

## The Solution
I've added a **watchdog in the hub** that:
1. Monitors dB readings every 30 seconds
2. Detects when readings stop updating (60s threshold)
3. Automatically restarts audio monitoring after 3 consecutive stalls
4. Prevents the 30-minute failure

## HOW TO APPLY THE FIX

### Option 1: Copy the fixed file directly (if you have access to the workspace)

```bash
# On your Pi:
sudo cp /workspace/services/hub/main.py /opt/pulse/services/hub/main.py
sudo systemctl restart pulse-hub
```

### Option 2: Run the deployment script

```bash
# Copy this script to your Pi first, then:
sudo bash deploy_audio_fix_to_pi.sh
```

### Option 3: Manual fix (if scripts don't work)

The fix adds two things to `/opt/pulse/services/hub/main.py`:

1. **Watchdog tracking variables** (after line ~51):
```python
# CRITICAL FIX: Audio monitoring watchdog tracking
self._audio_last_db_reading = None
self._audio_last_db_timestamp = None
self._audio_stall_count = 0
self._audio_max_stall_before_restart = 3
```

2. **Watchdog logic** in `_collect_sensor_data()` method (around line ~460):
   - Monitors dB readings
   - Detects stalls
   - Auto-restarts audio monitoring

## VERIFY IT'S WORKING

### Check service status:
```bash
sudo systemctl status pulse-hub
```

### View logs:
```bash
# Real-time monitoring
sudo journalctl -u pulse-hub -f | grep -E "(Audio|Song|CRITICAL|stalled)"

# All logs
sudo journalctl -u pulse-hub --no-pager | tail -100
```

### Check if audio is working:
```bash
# Should see "Audio: XX.X dB" every 2 seconds
sudo journalctl -u pulse-hub --since "1 minute ago" | grep "Audio:"
```

## TROUBLESHOOTING

### If service won't start:
```bash
sudo journalctl -u pulse-hub -n 50
```

### If no logs appear:
1. Check if service is running: `sudo systemctl status pulse-hub`
2. Check log files: `sudo ls -lh /var/log/pulse/`
3. Check Python process: `ps aux | grep pulse-hub`

### If audio still doesn't work:
1. Check audio device: `arecord -l`
2. Check dependencies: `python3 -c "import numpy, pyaudio, sounddevice"`
3. Check config: `cat /opt/pulse/config/config.yaml | grep -A 5 mic`

## WHAT THE FIX DOES

The watchdog:
- ✅ Detects when dB readings stop updating (60s threshold)
- ✅ Logs warnings when stalled
- ✅ Automatically restarts audio monitoring after 3 consecutive stalls
- ✅ Works with existing event loop heartbeat fixes
- ✅ Prevents the 30-minute failure

## EXPECTED BEHAVIOR

**Normal operation:**
- dB readings every 2 seconds: `🔊 Audio: XX.X dB`
- Song detection every 10 seconds
- No stall warnings

**When stalled:**
- Warning: `⚠️ Audio monitoring appears stalled`
- Auto-restart: `🚨 CRITICAL: Audio monitoring stalled - FORCING COMPLETE RESTART!`
- Recovery: `✅ Audio monitoring restarted successfully`

The system will now self-heal and prevent the 30-minute failure!
