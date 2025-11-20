#!/bin/bash
# Nov 5th Installation Verification Script
# Run this on your Raspberry Pi to verify everything is correct

echo "========================================================================"
echo "NOV 5TH CODE VERIFICATION"
echo "========================================================================"
echo ""

# Check 1: Line counts
echo "✓ CHECK 1: File Line Counts"
echo "------------------------------------------------------------------------"
echo -n "simple_song_detector.py: "
wc -l services/sensors/simple_song_detector.py | awk '{print $1 " lines (should be 296)"}'

echo -n "simple_decibel_detector.py: "
wc -l services/sensors/simple_decibel_detector.py | awk '{print $1 " lines (should be 216)"}'

echo -n "run_audio_service.py: "
wc -l run_audio_service.py | awk '{print $1 " lines (should be 165)"}'
echo ""

# Check 2: Verify Nov 5th code (no my additions)
echo "✓ CHECK 2: Verify Pure Nov 5th Code (No Recent Additions)"
echo "------------------------------------------------------------------------"
echo -n "attempt_time present: "
if grep -q "attempt_time" services/sensors/simple_song_detector.py; then
    echo "❌ FOUND (should NOT be present)"
else
    echo "✅ NOT FOUND (correct)"
fi

echo -n "total_attempts present: "
if grep -q "total_attempts" services/sensors/simple_song_detector.py; then
    echo "❌ FOUND (should NOT be present)"
else
    echo "✅ NOT FOUND (correct)"
fi

echo -n "backoff logic present: "
if grep -q "backoff" services/sensors/simple_song_detector.py; then
    echo "❌ FOUND (should NOT be present)"
else
    echo "✅ NOT FOUND (correct)"
fi
echo ""

# Check 3: Verify Nov 5th features ARE present
echo "✓ CHECK 3: Verify Nov 5th Features Present"
echo "------------------------------------------------------------------------"
echo -n "party_box approach: "
if grep -q "party_box" services/sensors/simple_song_detector.py; then
    echo "✅ FOUND (correct)"
else
    echo "❌ NOT FOUND (should be present)"
fi

echo -n "shazamio import: "
if grep -q "from shazamio import Shazam" services/sensors/simple_song_detector.py; then
    echo "✅ FOUND (correct - will change to RapidAPI)"
else
    echo "❌ NOT FOUND (should be present)"
fi

echo -n "cache file writing: "
if grep -q "json.dump" run_audio_service.py; then
    echo "✅ FOUND (correct - Nov 5th has cache writing)"
else
    echo "❌ NOT FOUND (should be present)"
fi
echo ""

# Check 4: Git status
echo "✓ CHECK 4: Git Branch and Status"
echo "------------------------------------------------------------------------"
git branch --show-current
git log --oneline -1
echo ""

# Check 5: Service status
echo "✓ CHECK 5: Service Status"
echo "------------------------------------------------------------------------"
systemctl is-active pulse-audio
systemctl is-enabled pulse-audio
echo ""

# Check 6: Check for errors in logs (last 50 lines)
echo "✓ CHECK 6: Recent Log Errors (last 50 lines)"
echo "------------------------------------------------------------------------"
ERROR_COUNT=$(journalctl -u pulse-audio -n 50 --no-pager | grep -i "error\|failed\|critical" | wc -l)
if [ $ERROR_COUNT -eq 0 ]; then
    echo "✅ No errors found in last 50 log lines"
else
    echo "⚠️  Found $ERROR_COUNT error lines in logs:"
    journalctl -u pulse-audio -n 50 --no-pager | grep -i "error\|failed\|critical"
fi
echo ""

# Check 7: Verify dependencies installed
echo "✓ CHECK 7: Python Dependencies"
echo "------------------------------------------------------------------------"
cd /opt/pulse
source venv/bin/activate 2>/dev/null || echo "⚠️  venv not found, checking system python"

echo -n "sounddevice: "
python3 -c "import sounddevice; print('✅ installed')" 2>/dev/null || echo "❌ NOT installed"

echo -n "shazamio: "
python3 -c "from shazamio import Shazam; print('✅ installed')" 2>/dev/null || echo "❌ NOT installed"

echo -n "numpy: "
python3 -c "import numpy; print('✅ installed')" 2>/dev/null || echo "❌ NOT installed"
echo ""

# Check 8: Check if threads are running
echo "✓ CHECK 8: Detection Threads Status"
echo "------------------------------------------------------------------------"
LAST_LOG=$(journalctl -u pulse-audio -n 100 --no-pager | tail -20)

if echo "$LAST_LOG" | grep -q "Song detection loop started"; then
    echo "✅ Song detection thread started"
else
    echo "⚠️  Song detection thread start not found in recent logs"
fi

if echo "$LAST_LOG" | grep -q "Decibel detection loop started"; then
    echo "✅ Decibel detection thread started"
else
    echo "⚠️  Decibel detection thread start not found in recent logs"
fi
echo ""

# Summary
echo "========================================================================"
echo "VERIFICATION SUMMARY"
echo "========================================================================"
echo ""
echo "If all checks show ✅ then Nov 5th code is installed correctly."
echo "Next step: Give your RapidAPI key to change from shazamio to RapidAPI."
echo ""
