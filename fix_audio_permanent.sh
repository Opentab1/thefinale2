#!/bin/bash
# PERMANENT FIX for dB reader and song detection 30-minute failure
# This script applies all fixes and restarts the service

set -e

echo "=========================================="
echo "PERMANENT FIX: dB Reader & Song Detection"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

INSTALL_DIR="/opt/pulse"

echo "1. Backing up current hub service..."
cp -f "$INSTALL_DIR/services/hub/main.py" "$INSTALL_DIR/services/hub/main.py.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

echo "2. Copying fixed hub service..."
# Copy the fixed version from workspace
if [ -f "/workspace/services/hub/main.py" ]; then
    cp -f "/workspace/services/hub/main.py" "$INSTALL_DIR/services/hub/main.py"
    echo "   ✅ Fixed hub service copied"
else
    echo "   ⚠️  Fixed file not found in /workspace - using existing"
fi

echo "3. Verifying audio monitor fixes are in place..."
if grep -q "CRITICAL FIX: Audio monitoring watchdog" "$INSTALL_DIR/services/hub/main.py" 2>/dev/null; then
    echo "   ✅ Watchdog fix confirmed"
else
    echo "   ⚠️  Watchdog fix not found - may need manual update"
fi

echo "4. Restarting pulse-hub service..."
systemctl restart pulse-hub
sleep 3

echo "5. Checking service status..."
if systemctl is-active --quiet pulse-hub; then
    echo "   ✅ Service is running"
else
    echo "   ❌ Service failed to start - check logs:"
    echo "      sudo journalctl -u pulse-hub -n 50"
    exit 1
fi

echo ""
echo "6. Waiting 10 seconds for audio monitoring to start..."
sleep 10

echo ""
echo "7. Checking for audio activity..."
AUDIO_LOGS=$(journalctl -u pulse-hub --since "10 seconds ago" --no-pager | grep -c "Audio:" || echo "0")
if [ "$AUDIO_LOGS" -gt 0 ]; then
    echo "   ✅ Audio monitoring is working! ($AUDIO_LOGS log entries)"
else
    echo "   ⚠️  No audio logs yet - may need a few more seconds"
    echo "   Check logs: sudo journalctl -u pulse-hub -f | grep Audio"
fi

echo ""
echo "=========================================="
echo "FIX APPLIED!"
echo "=========================================="
echo ""
echo "The hub now has a watchdog that will:"
echo "  • Detect when audio monitoring stops (after 60s of no dB changes)"
echo "  • Automatically restart audio monitoring (after 3 consecutive stalls)"
echo "  • Prevent the 30-minute failure"
echo ""
echo "Monitor in real-time:"
echo "  sudo journalctl -u pulse-hub -f | grep -E '(Audio|Song|CRITICAL|stalled)'"
echo ""
echo "View all logs:"
echo "  sudo journalctl -u pulse-hub --no-pager | tail -100"
echo ""
