#!/bin/bash
# Verification script for DB Reader & Song Detection Fix

echo "========================================="
echo "DB Reader & Song Detection Fix Verification"
echo "========================================="
echo ""

echo "✓ Checking if files were modified..."
if grep -q "_shazam_refresh_interval = 1800.0" services/sensors/mic_song_detect.py; then
    echo "  ✓ Shazam refresh interval updated to 30 minutes (1800s)"
else
    echo "  ✗ Shazam refresh interval NOT updated"
    exit 1
fi

if grep -q "_shazam_max_detections = 20" services/sensors/mic_song_detect.py; then
    echo "  ✓ Detection count limit added (20 detections)"
else
    echo "  ✗ Detection count limit NOT added"
    exit 1
fi

if grep -q "force_shazam_refresh" services/sensors/mic_song_detect.py; then
    echo "  ✓ Error recovery mechanism added"
else
    echo "  ✗ Error recovery mechanism NOT added"
    exit 1
fi

if grep -q "Cancel all pending tasks" services/sensors/mic_song_detect.py; then
    echo "  ✓ Improved event loop cleanup in mic_song_detect.py"
else
    echo "  ✗ Event loop cleanup NOT improved in mic_song_detect.py"
    exit 1
fi

if grep -q "Cancel any pending tasks" services/sensors/song_detector.py; then
    echo "  ✓ Improved event loop cleanup in song_detector.py"
else
    echo "  ✗ Event loop cleanup NOT improved in song_detector.py"
    exit 1
fi

echo ""
echo "✓ Checking Python syntax..."
if python3 -m py_compile services/sensors/mic_song_detect.py 2>/dev/null; then
    echo "  ✓ mic_song_detect.py syntax valid"
else
    echo "  ✗ mic_song_detect.py has syntax errors"
    exit 1
fi

if python3 -m py_compile services/sensors/song_detector.py 2>/dev/null; then
    echo "  ✓ song_detector.py syntax valid"
else
    echo "  ✗ song_detector.py has syntax errors"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ All verification checks passed!"
echo "========================================="
echo ""
echo "Summary of Changes:"
echo "-------------------"
echo "1. Reduced Shazam refresh interval: 60min → 30min"
echo "2. Added detection count limit: refresh after 20 detections"
echo "3. Improved event loop cleanup to prevent resource leaks"
echo "4. Added automatic error recovery for connection issues"
echo "5. Enhanced cleanup in song_detector.py"
echo ""
echo "Expected Result:"
echo "  ✓ Song detection will run indefinitely (no 35-minute stop)"
echo "  ✓ Automatic recovery from connection errors"
echo "  ✓ Stable memory and resource usage"
echo ""
echo "Next Steps:"
echo "  1. Restart the pulse system"
echo "  2. Monitor for 2+ hours to verify continuous operation"
echo "  3. Check logs for Shazam refresh messages (~every 30 min)"
echo ""
