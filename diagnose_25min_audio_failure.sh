#!/bin/bash
# Emergency Diagnostic for 25-Minute Audio Failure
# Run this on your Pi to capture detailed logs

echo "=================================="
echo "🚨 AUDIO FAILURE DIAGNOSTIC (25min)"
echo "=================================="
echo ""

# Capture current timestamp
echo "Current time: $(date)"
echo ""

# Show pulse service status
echo "--- PULSE SERVICE STATUS ---"
sudo systemctl status pulse-hub --no-pager -l || echo "pulse-hub service not found"
echo ""

# Get last 500 lines of pulse logs (covers ~30 minutes of activity)
echo "--- PULSE LOGS (Last 500 lines with audio/song context) ---"
sudo journalctl -u pulse-hub -n 500 --no-pager | grep -E "(Audio|Song|dB|monitoring|watchdog|health|stalled|timeout|freeze|stuck|restart|CRITICAL|ERROR|WARNING)" || echo "No audio-related logs found"
echo ""

# Check for the specific time window around 25 minutes
echo "--- FULL PULSE LOGS (Last 30 minutes) ---"
sudo journalctl -u pulse-hub --since "30 minutes ago" --no-pager -l
echo ""

# Check process threads
echo "--- PULSE PROCESS THREADS ---"
PULSE_PID=$(pgrep -f "run_pulse_system.py" | head -1)
if [ ! -z "$PULSE_PID" ]; then
    echo "Pulse PID: $PULSE_PID"
    ps -T -p $PULSE_PID || echo "Cannot show threads"
    echo ""
    echo "Thread count: $(ps -T -p $PULSE_PID | wc -l)"
    echo ""
    echo "Open files: $(lsof -p $PULSE_PID 2>/dev/null | wc -l)"
else
    echo "Pulse process not running!"
fi
echo ""

# Check for network connections (Shazam API)
echo "--- NETWORK CONNECTIONS (Shazam API) ---"
if [ ! -z "$PULSE_PID" ]; then
    lsof -p $PULSE_PID -a -i 2>/dev/null | grep -E "ESTABLISHED|CLOSE_WAIT|TIME_WAIT" | head -20
else
    echo "No pulse process found"
fi
echo ""

# Check system resources
echo "--- SYSTEM RESOURCES ---"
echo "Memory:"
free -h
echo ""
echo "File descriptor limits:"
ulimit -n
cat /proc/sys/fs/file-nr
echo ""

# Check audio device
echo "--- AUDIO DEVICE STATUS ---"
arecord -l
echo ""

# Look for specific patterns in recent logs
echo "--- ERROR PATTERN ANALYSIS ---"
echo "Shazam timeouts:"
sudo journalctl -u pulse-hub --since "30 minutes ago" --no-pager | grep -c "timeout" || echo "0"
echo ""
echo "Audio restart requests:"
sudo journalctl -u pulse-hub --since "30 minutes ago" --no-pager | grep -c "restart" || echo "0"
echo ""
echo "Song detection stuck:"
sudo journalctl -u pulse-hub --since "30 minutes ago" --no-pager | grep -c "stuck" || echo "0"
echo ""
echo "Stream failures:"
sudo journalctl -u pulse-hub --since "30 minutes ago" --no-pager | grep -c "StreamRuntimeError\|StreamInitError" || echo "0"
echo ""

# Check if detection loop is healthy
echo "--- DETECTION LOOP HEALTH ---"
sudo journalctl -u pulse-hub --since "30 minutes ago" --no-pager | grep -E "detection loop|event loop" | tail -20
echo ""

echo "=================================="
echo "✅ Diagnostic complete!"
echo "=================================="
echo ""
echo "Please share this entire output so I can identify the exact failure."
