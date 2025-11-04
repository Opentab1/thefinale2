#!/bin/bash
# Quick deployment script for critical audio monitoring fix
# Run this on your Raspberry Pi to deploy the fix

set -e  # Exit on error

echo "=========================================="
echo "CRITICAL AUDIO MONITORING FIX DEPLOYMENT"
echo "=========================================="
echo ""

# Check if running as root or with sudo
if [ "$EUID" -eq 0 ]; then 
    SUDO=""
else
    SUDO="sudo"
fi

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "1. Checking current service status..."
$SUDO systemctl status pulse-hub.service --no-pager || true
echo ""

echo "2. Creating backup of old file..."
if [ -f "services/sensors/mic_song_detect.py" ]; then
    $SUDO cp services/sensors/mic_song_detect.py services/sensors/mic_song_detect.py.backup.$(date +%Y%m%d_%H%M%S)
    echo "✅ Backup created"
else
    echo "⚠️  Original file not found at expected location"
fi
echo ""

echo "3. Stopping pulse-hub service..."
$SUDO systemctl stop pulse-hub.service
sleep 2
echo "✅ Service stopped"
echo ""

echo "4. Verifying fixed file is in place..."
if grep -q "CRITICAL FIX" services/sensors/mic_song_detect.py; then
    echo "✅ Fixed file detected (contains CRITICAL FIX markers)"
else
    echo "❌ WARNING: File may not contain the fix!"
    echo "Press Ctrl+C to abort or Enter to continue anyway..."
    read
fi
echo ""

echo "5. Restarting pulse-hub service..."
$SUDO systemctl restart pulse-hub.service
sleep 3
echo "✅ Service restarted"
echo ""

echo "6. Checking service status..."
if $SUDO systemctl is-active --quiet pulse-hub.service; then
    echo "✅ Service is running"
else
    echo "❌ Service failed to start!"
    $SUDO systemctl status pulse-hub.service --no-pager
    exit 1
fi
echo ""

echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Monitor logs for 5 minutes:"
echo "   sudo journalctl -u pulse-hub.service -f"
echo ""
echo "2. Look for these SUCCESS indicators:"
echo "   ✅ '🔊 Audio: XX.X dB' every 2 seconds"
echo "   ✅ '[loop:XXX]' counter increasing"
echo "   ✅ No ERROR or stuck messages"
echo ""
echo "3. Run diagnostic after 20 minutes:"
echo "   python3 /workspace/diagnose_audio_freeze.py"
echo ""
echo "4. Verify it runs for 2+ hours without stopping"
echo ""
echo "Press Ctrl+C to exit, or we'll start showing logs..."
sleep 5

echo ""
echo "=========================================="
echo "LIVE LOG MONITORING (Ctrl+C to exit)"
echo "=========================================="
$SUDO journalctl -u pulse-hub.service -f
