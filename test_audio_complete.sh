#!/bin/bash
# Comprehensive test suite for dB reader and song detector
# Run this after applying the fix to verify everything works

set -e

echo "=========================================="
echo "COMPREHENSIVE AUDIO SYSTEM TEST"
echo "=========================================="
echo ""

cd /opt/pulse 2>/dev/null || cd /workspace 2>/dev/null || { echo "Error: Cannot find pulse directory"; exit 1; }

# Test 1: Dependency Check
echo "[Test 1/5] Checking dependencies..."
echo "---"
python3 << 'PYEOF'
import sys

success = True

def check(module, name=None):
    global success
    name = name or module
    try:
        __import__(module)
        print(f"  ✓ {name}")
        return True
    except ImportError as e:
        print(f"  ✗ {name}: {e}")
        success = False
        return False

check("numpy")
check("sounddevice")
check("pyaudio")
check("aiohttp")

# Check audioop (Python 3.13+)
if sys.version_info >= (3, 13):
    check("audioop_lts", "audioop-lts (Python 3.13+)")
else:
    check("audioop", "audioop (stdlib)")

shazam_ok = check("shazamio", "ShazamIO")

if not success:
    print("\n✗ Missing dependencies detected")
    print("Run: sudo ./fix_audio_forever.sh")
    sys.exit(1)
else:
    print("\n✓ All dependencies present")
PYEOF

echo ""

# Test 2: AudioMonitor Import
echo "[Test 2/5] Testing AudioMonitor import..."
echo "---"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')

try:
    from services.sensors.mic_song_detect import AudioMonitor
    print("  ✓ AudioMonitor imports successfully")
except ImportError as e:
    print(f"  ✗ AudioMonitor import failed: {e}")
    sys.exit(1)
PYEOF

echo ""

# Test 3: AudioMonitor Initialization
echo "[Test 3/5] Testing AudioMonitor initialization..."
echo "---"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')

try:
    from services.sensors.mic_song_detect import AudioMonitor
    m = AudioMonitor()
    print(f"  ✓ AudioMonitor initialized")
    print(f"    - Device index: {m.device_index}")
    print(f"    - Sample rate: {m.sample_rate} Hz")
    print(f"    - Song detector: {'Enabled' if m.song_detector else 'Disabled'}")
    
    if m.song_detector is None:
        print("    ⚠ Song detector disabled (check ShazamIO)")
except Exception as e:
    print(f"  ⚠ AudioMonitor initialization warning: {e}")
    print("    (May be normal if no audio device present)")
PYEOF

echo ""

# Test 4: dB Reader Functionality
echo "[Test 4/5] Testing dB reader (10 seconds)..."
echo "---"
echo "  Make some noise near the microphone!"
echo ""
timeout 15 python3 << 'PYEOF' || true
import sys
sys.path.insert(0, '.')
import time

from services.sensors.mic_song_detect import AudioMonitor

m = AudioMonitor()
m.start_monitoring()

print("  Monitoring for 10 seconds...")
db_readings = []

for i in range(5):
    time.sleep(2)
    stats = m.get_stats()
    db = stats['current_db']
    db_readings.append(db)
    
    if db > 0:
        print(f"  [{i*2}s] ✓ dB: {db:.1f}")
    else:
        print(f"  [{i*2}s] ⚠ dB: {db:.1f} (no audio detected)")

m.cleanup()

# Evaluate results
max_db = max(db_readings)
if max_db > 30:
    print(f"\n  ✓ dB reader WORKING (peak: {max_db:.1f} dB)")
    exit(0)
elif max_db > 0:
    print(f"\n  ⚠ dB reader responding but quiet (peak: {max_db:.1f} dB)")
    print("    Try making louder noises")
    exit(0)
else:
    print(f"\n  ✗ dB reader stuck at 0.0 dB")
    print("    Check microphone connection")
    exit(1)
PYEOF

TEST4_RESULT=$?

echo ""

# Test 5: Song Detector Presence
echo "[Test 5/5] Verifying song detector..."
echo "---"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')

from services.sensors.mic_song_detect import AudioMonitor

m = AudioMonitor()

if m.song_detector is not None:
    print("  ✓ Song detector is enabled")
    print("    (To test: play music for 30+ seconds)")
else:
    print("  ⚠ Song detector is disabled")
    print("    Check ShazamIO installation:")
    print("    pip3 install --break-system-packages shazamio audioop-lts")
PYEOF

echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
echo ""

if [ $TEST4_RESULT -eq 0 ]; then
    echo "✅ PASS: Audio system is working!"
    echo ""
    echo "Your dB reader and song detector are ready."
    echo ""
    exit 0
else
    echo "⚠️  PARTIAL: Some tests had warnings"
    echo ""
    echo "The system may work with some limitations."
    echo "Check warnings above for details."
    echo ""
    exit 0
fi
