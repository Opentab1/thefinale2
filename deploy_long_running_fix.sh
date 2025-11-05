#!/bin/bash
# Deploy Long-Running Stability Fix to Raspberry Pi
# Fixes the 10-hour failure issue with db reader and song detector

set -e  # Exit on error

echo "=========================================================================="
echo "LONG-RUNNING STABILITY FIX DEPLOYMENT"
echo "=========================================================================="
echo ""
echo "This script fixes the issue where db reader and song detector stop"
echo "working after ~10 hours of continuous operation."
echo ""
echo "Changes:"
echo "  - Automatic hourly counter reset (prevents accumulation)"
echo "  - Increased timeout thresholds (reduces false positives)"
echo "  - Counter decay mechanism (faster recovery)"
echo "  - Circuit breaker auto-decay (prevents permanent disable)"
echo "  - Reduced wait times (5-10 min instead of 60 min)"
echo ""
echo "=========================================================================="
echo ""

# Check if running on Pi
if [ ! -f /opt/pulse/services/hub/main.py ]; then
    echo "❌ ERROR: /opt/pulse not found. Are you running this on your Pi?"
    echo ""
    echo "If you're on your development machine, copy these files to your Pi:"
    echo "  scp services/sensors/song_detector.py pi@your-pi:/opt/pulse/services/sensors/"
    echo "  scp services/sensors/mic_song_detect.py pi@your-pi:/opt/pulse/services/sensors/"
    echo "  scp services/hub/main.py pi@your-pi:/opt/pulse/services/hub/"
    echo ""
    exit 1
fi

# Backup current files
echo "📦 Creating backups..."
BACKUP_DIR="/opt/pulse/backups/long-running-fix-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp /opt/pulse/services/sensors/song_detector.py "$BACKUP_DIR/" 2>/dev/null || true
cp /opt/pulse/services/sensors/mic_song_detect.py "$BACKUP_DIR/" 2>/dev/null || true
cp /opt/pulse/services/hub/main.py "$BACKUP_DIR/" 2>/dev/null || true
echo "✓ Backups saved to: $BACKUP_DIR"
echo ""

# Check if fixes are already applied
echo "🔍 Checking if fixes are already applied..."
if grep -q "restart_count_reset_time" /opt/pulse/services/sensors/song_detector.py 2>/dev/null; then
    echo "✓ Fixes already applied!"
    echo ""
    read -p "Do you want to restart services anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting without restart."
        exit 0
    fi
else
    echo "⚠️  Fixes not yet applied. Please deploy updated files first."
    echo ""
    echo "Run these commands from your development machine:"
    echo "  cd /workspace"
    echo "  scp services/sensors/song_detector.py pi@your-pi:/opt/pulse/services/sensors/"
    echo "  scp services/sensors/mic_song_detect.py pi@your-pi:/opt/pulse/services/sensors/"
    echo "  scp services/hub/main.py pi@your-pi:/opt/pulse/services/hub/"
    echo ""
    read -p "Have you copied the files? Continue with restart? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Deploy files and run this script again."
        exit 1
    fi
fi

echo ""
echo "🔄 Restarting services..."

# Stop services gracefully
echo "  Stopping pulse-hub..."
sudo systemctl stop pulse-hub 2>/dev/null || echo "    (pulse-hub not running)"

echo "  Stopping pulse-audio..."
sudo systemctl stop pulse-audio 2>/dev/null || echo "    (pulse-audio not running)"

# Wait for clean shutdown
echo "  Waiting for clean shutdown..."
sleep 3

# Start services
echo "  Starting pulse-hub..."
sudo systemctl start pulse-hub

echo "  Starting pulse-audio..."
sudo systemctl start pulse-audio 2>/dev/null || echo "    (pulse-audio service not found - may be part of hub)"

# Wait for initialization
echo "  Waiting for initialization..."
sleep 5

# Check status
echo ""
echo "📊 Service Status:"
echo "=========================================================================="
sudo systemctl status pulse-hub --no-pager -l | head -20
echo ""

# Verify fixes are working
echo "🧪 Verifying fixes..."
echo "=========================================================================="

# Check for new log patterns
echo "Looking for restart counter reset logic in logs..."
if journalctl -u pulse-hub --since "2 minutes ago" | grep -q "restart_count_reset_time\|restart counter"; then
    echo "✓ New code is running"
else
    echo "⚠️  Can't confirm new code yet (may need to wait for first hour)"
fi

# Check thread health
echo ""
echo "Checking thread health..."
if journalctl -u pulse-hub --since "1 minute ago" | grep -q "Song detection\|Audio monitoring"; then
    echo "✓ Audio services active"
else
    echo "⚠️  Audio services may still be initializing..."
fi

echo ""
echo "=========================================================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=========================================================================="
echo ""
echo "Next steps:"
echo "  1. Monitor logs: tail -f /var/log/pulse/hub.log"
echo "  2. Watch for hourly counter resets (every 60 minutes)"
echo "  3. Verify db readings appear every 2 seconds"
echo "  4. Verify song detection runs every 10 seconds"
echo "  5. Let system run for 24+ hours to confirm stability"
echo ""
echo "Key improvements:"
echo "  ✓ Restart counters reset every hour automatically"
echo "  ✓ Timeouts increased (60s heartbeat, 30s watchdog)"
echo "  ✓ Counters decay on limit (5-10 min recovery, not 60 min)"
echo "  ✓ Circuit breaker auto-decays (temporary issues don't disable permanently)"
echo ""
echo "Monitor for success:"
echo "  • System runs 24+ hours without stopping"
echo "  • See 'Resetting restart counter' messages every hour"
echo "  • False-positive restarts reduced significantly"
echo "  • Services recover in <10 minutes if issues occur"
echo ""
echo "=========================================================================="
echo "Good luck! Your system should now run indefinitely! 🎉"
echo "=========================================================================="
