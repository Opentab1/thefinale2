#!/bin/bash
# Comprehensive diagnostic for db reader and song detection failures

echo "=========================================="
echo "DIAGNOSTIC: dB Reader & Song Detection"
echo "=========================================="
echo ""

echo "1. Checking service status..."
sudo systemctl status pulse-hub --no-pager -l | head -20
echo ""

echo "2. Checking if service is enabled..."
systemctl is-enabled pulse-hub 2>/dev/null || echo "Service not enabled"
echo ""

echo "3. Checking service logs (last 50 lines)..."
sudo journalctl -u pulse-hub -n 50 --no-pager | tail -30
echo ""

echo "4. Checking for errors in system logs..."
sudo journalctl -u pulse-hub --since "1 hour ago" --no-pager | grep -i "error\|exception\|traceback\|failed\|critical" | tail -20
echo ""

echo "5. Checking if log files exist..."
ls -lh /var/log/pulse/ 2>/dev/null || echo "Log directory doesn't exist"
echo ""

echo "6. Checking Python process..."
ps aux | grep -E "pulse-hub|main.py" | grep -v grep
echo ""

echo "7. Checking audio device..."
arecord -l 2>/dev/null || echo "arecord not available"
echo ""

echo "8. Checking Python dependencies..."
python3 -c "import numpy, pyaudio, sounddevice, shazamio; print('All dependencies OK')" 2>&1 || echo "Missing dependencies!"
echo ""

echo "9. Checking service file location..."
ls -lh /etc/systemd/system/pulse-hub.service 2>/dev/null || echo "Service file not found"
echo ""

echo "10. Checking if AudioMonitor can import..."
python3 -c "import sys; sys.path.insert(0, '/opt/pulse'); from services.sensors.mic_song_detect import AudioMonitor; print('AudioMonitor import OK')" 2>&1
echo ""

echo "=========================================="
echo "DIAGNOSTIC COMPLETE"
echo "=========================================="
