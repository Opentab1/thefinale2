#!/bin/bash
# Run this command on your Pi to capture logs for the 25-minute audio failure

echo "=== Capturing logs for 25-minute audio failure analysis ==="
echo ""

# Capture recent logs
echo "1. Recent pulse logs (last 200 lines with audio keywords):"
if [ -f "/var/log/pulse/pulse.log" ]; then
    tail -200 /var/log/pulse/pulse.log | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|refresh|proactive)" -i
elif [ -f "/var/log/pulse/pulse-error.log" ]; then
    tail -200 /var/log/pulse/pulse-error.log | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|refresh|proactive)" -i
fi

echo ""
echo "2. System journal (last 300 lines with audio keywords):"
if systemctl is-active --quiet pulse.service 2>/dev/null; then
    journalctl -u pulse.service -n 300 --no-pager | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|refresh|proactive)" -i | tail -50
elif systemctl is-active --quiet pulse 2>/dev/null; then
    journalctl -u pulse -n 300 --no-pager | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|refresh|proactive)" -i | tail -50
fi

echo ""
echo "3. Full recent logs (last 50 lines):"
if systemctl is-active --quiet pulse.service 2>/dev/null; then
    journalctl -u pulse.service -n 50 --no-pager
elif systemctl is-active --quiet pulse 2>/dev/null; then
    journalctl -u pulse -n 50 --no-pager
fi

echo ""
echo "4. Process and connection info:"
PID=$(pgrep -f "run_pulse_system.py" | head -1)
if [ -n "$PID" ]; then
    echo "Pulse PID: $PID"
    echo "Open file descriptors: $(ls -1 /proc/$PID/fd 2>/dev/null | wc -l)"
    echo "Network connections: $(netstat -tn 2>/dev/null | grep "$PID" | wc -l)"
fi

echo ""
echo "=== To monitor in real-time, run: ==="
echo "journalctl -u pulse.service -f | grep -E '(audio|song|decibel|Shazam|refresh)'"
