#!/bin/bash
# Diagnostic script to capture logs around the 25-minute audio failure

echo "=== Audio Monitor Diagnostic - 25 Minute Failure Analysis ==="
echo ""
echo "This script will capture logs to diagnose the audio failure at 25 minutes"
echo ""

# Check if pulse service is running
if systemctl is-active --quiet pulse.service; then
    echo "✓ Pulse service is running"
    SERVICE_NAME="pulse.service"
elif systemctl is-active --quiet pulse; then
    echo "✓ Pulse service is running (alternative name)"
    SERVICE_NAME="pulse"
else
    echo "⚠️  Pulse service not found in systemd"
    echo "   Checking for running Python processes..."
    ps aux | grep -E "(run_pulse|pulse)" | grep -v grep
    SERVICE_NAME=""
fi

echo ""
echo "=== Recent Pulse Logs (last 100 lines) ==="
if [ -f "/var/log/pulse/pulse.log" ]; then
    tail -100 /var/log/pulse/pulse.log | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|1500)" -i
elif [ -f "/var/log/pulse/pulse-error.log" ]; then
    tail -100 /var/log/pulse/pulse-error.log | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|1500)" -i
else
    echo "Log files not found at /var/log/pulse/"
fi

echo ""
echo "=== System Journal (last 50 lines with audio keywords) ==="
if [ -n "$SERVICE_NAME" ]; then
    journalctl -u "$SERVICE_NAME" -n 200 --no-pager | grep -E "(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error|stuck|25|1500)" -i | tail -50
fi

echo ""
echo "=== Audio Monitor Thread Status ==="
echo "Checking for audio-related processes and threads..."
ps aux | grep -E "(AudioMonitor|song|audio)" | grep -v grep | head -10

echo ""
echo "=== Network Connections (checking for hung Shazam connections) ==="
netstat -tn 2>/dev/null | grep -E "(ESTABLISHED|TIME_WAIT)" | wc -l
echo "Total established connections: $(netstat -tn 2>/dev/null | grep ESTABLISHED | wc -l)"

echo ""
echo "=== File Descriptors (checking for leaks) ==="
if [ -n "$SERVICE_NAME" ]; then
    PID=$(systemctl show "$SERVICE_NAME" --property MainPID --value)
    if [ -n "$PID" ] && [ "$PID" != "0" ]; then
        echo "Pulse PID: $PID"
        if [ -d "/proc/$PID/fd" ]; then
            echo "Open file descriptors: $(ls -1 /proc/$PID/fd 2>/dev/null | wc -l)"
        fi
    fi
fi

echo ""
echo "=== Audio Device Status ==="
arecord -l 2>/dev/null || echo "arecord not available"

echo ""
echo "=== Python Process Info ==="
ps aux | grep python | grep -E "(pulse|run_pulse)" | grep -v grep | head -5

echo ""
echo "=== Checking for 25-minute patterns in logs ==="
if [ -f "/var/log/pulse/pulse.log" ]; then
    echo "Searching for timestamps around 25 minutes..."
    # Look for patterns that might indicate the issue
    grep -E "25\.|1500|stale|timeout|hung|stuck" /var/log/pulse/pulse.log | tail -20
fi

echo ""
echo "=== Real-time Monitoring Command ==="
echo "Run this to watch logs in real-time:"
if [ -n "$SERVICE_NAME" ]; then
    echo "  journalctl -u $SERVICE_NAME -f | grep -E '(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error)'"
else
    echo "  tail -f /var/log/pulse/pulse.log | grep -E '(audio|song|decibel|dB|AudioMonitor|Shazam|timeout|error)'"
fi

echo ""
echo "=== Diagnostic Complete ==="
echo "Please run this script again when the issue occurs (at 25 minutes)"
echo "Or capture logs with: journalctl -u $SERVICE_NAME > /tmp/pulse_full_logs.txt"
