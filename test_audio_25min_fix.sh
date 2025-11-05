#!/bin/bash
# Test Script for 25-Minute Audio Fix
# Run this ON your Raspberry Pi to verify the fix is working

echo "=================================="
echo "🔍 TESTING 25-MIN AUDIO FIX"
echo "=================================="
echo ""

# Check if pulse-hub is running
echo "1. Checking pulse-hub service status..."
if sudo systemctl is-active --quiet pulse-hub; then
    echo "   ✅ pulse-hub is running"
    UPTIME=$(sudo systemctl show pulse-hub --property=ActiveEnterTimestamp --value)
    echo "   Started: $UPTIME"
else
    echo "   ❌ pulse-hub is NOT running!"
    exit 1
fi
echo ""

# Check for recent audio readings
echo "2. Checking for recent audio (dB) readings..."
RECENT_AUDIO=$(sudo journalctl -u pulse-hub --since "2 minutes ago" | grep -c "Audio:" || true)
if [ "$RECENT_AUDIO" -gt 0 ]; then
    echo "   ✅ Found $RECENT_AUDIO audio readings in last 2 minutes"
    echo "   Last reading:"
    sudo journalctl -u pulse-hub --since "2 minutes ago" | grep "Audio:" | tail -1
else
    echo "   ⚠️  No audio readings in last 2 minutes"
    echo "   This is OK if the system just started (<2 min ago)"
fi
echo ""

# Check for event loop heartbeat
echo "3. Checking for event loop heartbeat..."
HEARTBEAT_CODE=$(sudo journalctl -u pulse-hub --since "10 minutes ago" | grep -c "_heartbeat" || true)
if [ "$HEARTBEAT_CODE" -gt 0 ]; then
    echo "   ✅ Event loop heartbeat code is present"
else
    echo "   ⚠️  Event loop heartbeat not found - may need to wait for first heartbeat (up to 60s)"
fi
echo ""

# Check for song detection
echo "4. Checking for song detection activity..."
SONG_ACTIVITY=$(sudo journalctl -u pulse-hub --since "5 minutes ago" | grep -c "Song" || true)
if [ "$SONG_ACTIVITY" -gt 0 ]; then
    echo "   ✅ Found $SONG_ACTIVITY song detection events in last 5 minutes"
    echo "   Last event:"
    sudo journalctl -u pulse-hub --since "5 minutes ago" | grep "Song" | tail -1
else
    echo "   ⚠️  No song detection activity in last 5 minutes"
fi
echo ""

# Check for any critical errors
echo "5. Checking for critical errors..."
CRITICAL_ERRORS=$(sudo journalctl -u pulse-hub --since "10 minutes ago" | grep -c "CRITICAL.*stalled" || true)
if [ "$CRITICAL_ERRORS" -gt 0 ]; then
    echo "   ⚠️  Found $CRITICAL_ERRORS critical stall errors!"
    sudo journalctl -u pulse-hub --since "10 minutes ago" | grep "CRITICAL.*stalled"
else
    echo "   ✅ No critical stall errors"
fi
echo ""

# Check system uptime vs audio last reading
echo "6. Checking for 25-minute failure pattern..."
SERVICE_START=$(sudo systemctl show pulse-hub --property=ActiveEnterTimestampMonotonic --value)
CURRENT_TIME=$(date +%s)
if [ ! -z "$SERVICE_START" ] && [ "$SERVICE_START" != "0" ]; then
    # Get last audio reading timestamp
    LAST_AUDIO_TIME=$(sudo journalctl -u pulse-hub | grep "Audio:" | tail -1 | awk '{print $1, $2, $3}')
    if [ ! -z "$LAST_AUDIO_TIME" ]; then
        echo "   Last audio reading: $LAST_AUDIO_TIME"
        echo "   ✅ Audio monitoring is active"
    else
        echo "   ⚠️  Cannot determine last audio reading time"
    fi
else
    echo "   ⚠️  Cannot determine service start time"
fi
echo ""

echo "=================================="
echo "📊 TEST SUMMARY"
echo "=================================="
echo ""

# Count successes
CHECKS_PASSED=0
[ "$RECENT_AUDIO" -gt 0 ] && CHECKS_PASSED=$((CHECKS_PASSED + 1))
[ "$SONG_ACTIVITY" -gt 0 ] && CHECKS_PASSED=$((CHECKS_PASSED + 1))
[ "$CRITICAL_ERRORS" -eq 0 ] && CHECKS_PASSED=$((CHECKS_PASSED + 1))

echo "Passed: $CHECKS_PASSED / 3 critical checks"
echo ""

if [ "$CHECKS_PASSED" -eq 3 ]; then
    echo "✅ AUDIO SYSTEM IS HEALTHY"
    echo ""
    echo "To monitor for 25-minute failure:"
    echo "  watch -n 60 'sudo journalctl -u pulse-hub --since \"2 minutes ago\" | grep Audio | tail -5'"
    echo ""
    echo "Or monitor continuously:"
    echo "  sudo journalctl -u pulse-hub -f | grep -E '(Audio:|Song|CRITICAL|stalled|heartbeat)'"
elif [ "$CHECKS_PASSED" -ge 1 ]; then
    echo "⚠️  AUDIO SYSTEM PARTIALLY WORKING"
    echo ""
    echo "Some checks failed - system may still be starting up."
    echo "Wait 5 minutes and run this test again."
else
    echo "❌ AUDIO SYSTEM MAY HAVE ISSUES"
    echo ""
    echo "Check logs for errors:"
    echo "  sudo journalctl -u pulse-hub --since \"10 minutes ago\" | grep -E 'ERROR|CRITICAL'"
fi

echo ""
echo "=================================="
