# Quick Restart Script for Audio & DB Components

## Problem
The song detection and database reader worked for ~5 minutes then stopped responding.

## Solution
Use this script to quickly restart just the audio monitoring and database components without a full system reboot.

## How to Use on Your Raspberry Pi 5

### Option 1: Quick Run (Recommended)
```bash
cd /workspace
./restart_audio_and_db.sh
```

### Option 2: If copied to /opt/pulse
```bash
cd /opt/pulse
./restart_audio_and_db.sh
```

## What This Script Does

1. **Stops the Pulse service** - Gracefully stops the main Pulse system
2. **Cleans up stuck processes** - Kills any lingering Python processes related to:
   - Main Pulse system (`run_pulse_system.py`)
   - Hub orchestrator (`services/hub/main.py`) 
   - Audio monitor (`mic_song_detect.py`)
   - Song detector (`song_detector.py`)
3. **Restarts the Pulse service** - Starts everything fresh
4. **Verifies startup** - Checks that components are running and shows recent logs

## Why This Works

The db_reader (PulseDB) and song_detection (SongDetector) are both components that run within the main Pulse Hub process. Restarting the service:
- Recreates the database connection (fixes db_reader issues)
- Restarts the AudioMonitor with fresh SongDetector threads (fixes song detection)
- Clears any stuck async event loops or thread deadlocks
- Re-initializes all watchdog threads

## Monitoring After Restart

### Watch live logs:
```bash
sudo journalctl -u pulse.service -f
```

### Check service status:
```bash
sudo systemctl status pulse.service
```

### View recent errors:
```bash
sudo journalctl -u pulse.service -n 100 --no-pager
```

## Troubleshooting

### If the script fails:
1. Check if service exists: `sudo systemctl list-units | grep pulse`
2. Check if running manually: `ps aux | grep pulse`
3. Try manual restart: `sudo systemctl restart pulse.service`

### If issues persist:
The system has a built-in health monitor that should auto-restart failed components. Check the logs to see if there are deeper issues:
```bash
sudo journalctl -u pulse.service -n 200 | grep -i "error\|warning\|restart"
```

## Technical Details

### Components Restarted:
- **PulseDB** (`services/storage/db.py`) - Database connection and operations
- **AudioMonitor** (`services/sensors/mic_song_detect.py`) - Microphone monitoring
- **SongDetector** (`services/sensors/song_detector.py`) - Song recognition via Shazam
- **Watchdog Threads** - Health monitoring and auto-recovery
- **Event Loops** - Async operations for song detection

### Health Monitoring:
After restart, the system's built-in `_audio_health_monitor` will:
- Check dB readings every 15 seconds
- Monitor song detector threads
- Auto-restart if issues detected
- Rate-limit restarts to prevent loops (max 10/hour)

## When to Use This Script

✅ **Use when:**
- Song detection stops working
- Database reads/writes fail
- Audio monitoring freezes
- After ~5 minutes of operation and things stop

❌ **Don't use when:**
- System is working fine
- You need a full reboot
- Hardware sensors are disconnected

---

**Quick Command Reference:**
```bash
# Restart components (run this one!)
./restart_audio_and_db.sh

# Watch logs live
sudo journalctl -u pulse.service -f

# Check if working
sudo systemctl status pulse.service
```
