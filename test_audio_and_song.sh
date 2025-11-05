#!/bin/bash
# Test dB reader and song detector on actual hardware
# Run this on your Raspberry Pi with a microphone connected

echo "=========================================="
echo "TESTING dB READER & SONG DETECTOR"
echo "=========================================="
echo ""
echo "This test will run for 2 minutes and show:"
echo "  1. Real-time dB (decibel) readings every 2 seconds"
echo "  2. Song detection every 30 seconds"
echo ""
echo "Press Ctrl+C to stop early"
echo ""
echo "=========================================="
echo ""

cd /workspace

# Set optimal environment
export PYTHONUNBUFFERED=1
export SONG_DETECT_INTERVAL_SEC=30
export DB_UPDATE_INTERVAL_SEC=2

# Run standalone audio monitor test
python3 -u << 'PYEOF'
import sys
import time
import logging

sys.path.insert(0, '/workspace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

from services.sensors.mic_song_detect import AudioMonitor

print("Initializing audio monitor...")
try:
    monitor = AudioMonitor()
    print(f"✓ Audio device: {monitor.device_index}")
    print(f"✓ Song detector: {'Enabled' if monitor.song_detector else 'Disabled'}")
    print("")
except Exception as e:
    print(f"✗ Failed to initialize: {e}")
    sys.exit(1)

print("Starting monitoring...")
try:
    monitor.start_monitoring()
    print("✓ Monitoring active\n")
except Exception as e:
    print(f"✗ Failed to start: {e}")
    sys.exit(1)

print("="*80)
print("LIVE AUDIO MONITORING (2 minutes)")
print("="*80)
print("")

# Monitor for 2 minutes
start_time = time.time()
test_duration = 120  # 2 minutes
last_db = None
db_working = False
song_detected = False

try:
    while (time.time() - start_time) < test_duration:
        time.sleep(5)
        
        stats = monitor.get_stats()
        current_db = stats['current_db']
        peak_db = stats['peak_db']
        song = stats['current_song']
        
        elapsed = int(time.time() - start_time)
        
        # Check dB reader
        if current_db > 0 and current_db != last_db:
            db_working = True
            print(f"[{elapsed}s] ✓ dB: {current_db:.1f} dB (Peak: {peak_db:.1f} dB)")
        elif not db_working:
            print(f"[{elapsed}s] ⚠ Waiting for dB readings...")
        
        last_db = current_db
        
        # Check song detector
        if song.get('title') and song['title'] != 'Unknown':
            if not song_detected or song['title'] != getattr(test_audio_and_song, 'last_song_title', None):
                song_detected = True
                print(f"[{elapsed}s] ✓ SONG: '{song['title']}' by {song['artist']}")
                test_audio_and_song.last_song_title = song['title']
        
    print("")
    print("="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("")
    
    if db_working:
        print("✓ dB READER: WORKING")
    else:
        print("✗ dB READER: NOT WORKING - Check microphone connection")
    
    if song_detected:
        print("✓ SONG DETECTOR: WORKING")
    else:
        print("⚠ SONG DETECTOR: No songs detected (play music louder or wait longer)")
    
    print("")
    
except KeyboardInterrupt:
    print("\n\nTest stopped by user")
finally:
    monitor.cleanup()
    print("Cleanup complete")

PYEOF

echo ""
echo "Test finished!"
