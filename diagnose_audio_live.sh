#!/bin/bash
# Live diagnostic for dB reader and song detector
# Shows real-time output so we can see exactly what's failing

echo "=========================================="
echo "AUDIO DIAGNOSTICS - LIVE MONITORING"
echo "=========================================="
echo ""
echo "This will show you exactly what's happening with:"
echo "  1. dB (decibel) Reader - audio level monitoring"
echo "  2. Song Detector - music recognition"
echo ""
echo "Watch for errors and we'll fix them permanently."
echo ""
echo "=========================================="
echo ""

# Change to workspace directory
cd /workspace

# Set environment variables for debugging
export PYTHONUNBUFFERED=1
export PULSE_MIC_DEVICE_INDEX=""  # Auto-detect
export SONG_DETECT_INTERVAL_SEC=30  # Detect songs every 30 seconds
export DB_UPDATE_INTERVAL_SEC=2  # Update dB every 2 seconds

# Run the audio monitor standalone with full debug logging
python3 -u << 'PYEOF'
import sys
import os
import time
import logging

# Add to path
sys.path.insert(0, '/workspace')

# Configure logging to show everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

print("="*80)
print("STARTING AUDIO MONITOR DIAGNOSTIC")
print("="*80)
print("")

# Import the AudioMonitor
try:
    from services.sensors.mic_song_detect import AudioMonitor
    print("✓ AudioMonitor imported successfully")
except ImportError as e:
    print(f"✗ FAILED to import AudioMonitor: {e}")
    print("\nDependencies needed:")
    print("  pip install numpy pyaudio sounddevice shazamio aiohttp")
    sys.exit(1)

print("")
print("="*80)
print("INITIALIZING AUDIO MONITOR")
print("="*80)
print("")

# Initialize the monitor
try:
    monitor = AudioMonitor()
    print("✓ AudioMonitor initialized successfully")
except Exception as e:
    print(f"✗ FAILED to initialize AudioMonitor: {e}")
    import traceback
    traceback.print_exc()
    print("\nTroubleshooting:")
    print("  1. Check audio device: arecord -l")
    print("  2. Test recording: arecord -d 1 test.wav")
    print("  3. Install dependencies: pip install numpy pyaudio sounddevice shazamio")
    sys.exit(1)

print("")
print("="*80)
print("STARTING MONITORING - WATCH FOR dB READINGS AND SONG DETECTION")
print("="*80)
print("")

# Start monitoring
try:
    monitor.start_monitoring()
    print("✓ Monitoring started")
    print("")
    print("LIVE STATUS (updates every 5 seconds):")
    print("-" * 80)
    print("")
except Exception as e:
    print(f"✗ FAILED to start monitoring: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Monitor and display status
iteration = 0
last_db = 0
last_song = None
no_db_count = 0
no_song_count = 0

try:
    while True:
        time.sleep(5)
        iteration += 1
        
        # Get current stats
        stats = monitor.get_stats()
        current_db = stats.get('current_db', 0)
        peak_db = stats.get('peak_db', 0)
        song = stats.get('current_song', {})
        detection_stats = stats.get('song_detection', {})
        
        print(f"\n[{iteration}] Status Update:")
        print("-" * 80)
        
        # dB Reader Status
        if current_db != last_db or current_db > 0:
            print(f"  ✓ dB READER WORKING: {current_db:.1f} dB (Peak: {peak_db:.1f} dB)")
            no_db_count = 0
        else:
            no_db_count += 1
            if no_db_count >= 3:
                print(f"  ✗ dB READER STUCK: No readings for {no_db_count * 5}s (still showing {current_db:.1f} dB)")
            else:
                print(f"  ⚠ dB Reader: {current_db:.1f} dB (unchanged)")
        
        last_db = current_db
        
        # Song Detector Status
        song_title = song.get('title', 'Unknown')
        song_artist = song.get('artist', 'Unknown')
        detection_active = detection_stats.get('active', False)
        last_error = detection_stats.get('last_error')
        last_success = detection_stats.get('last_success_at')
        
        if detection_active:
            print(f"  🎵 SONG DETECTOR: Detection in progress...")
        elif song_title and song_title != 'Unknown':
            print(f"  ✓ SONG DETECTOR WORKING: '{song_title}' by {song_artist}")
            if last_success:
                print(f"     Last detected: {last_success}")
        else:
            if last_error:
                print(f"  ⚠ SONG DETECTOR: No song detected (Error: {last_error})")
            else:
                print(f"  ⚠ SONG DETECTOR: No song detected yet (listening...)")
        
        # Show detection stats
        if detection_stats.get('last_attempt_duration_sec'):
            print(f"     Last detection took: {detection_stats['last_attempt_duration_sec']:.2f}s")
        
        print("-" * 80)
        
        # Alert on problems
        if no_db_count >= 6:
            print("\n" + "!"*80)
            print("CRITICAL: dB reader has been stuck for over 30 seconds!")
            print("This is the problem we need to fix.")
            print("!"*80 + "\n")

except KeyboardInterrupt:
    print("\n\nStopping diagnostic...")
    monitor.cleanup()
    print("✓ Cleanup complete")
    sys.exit(0)
except Exception as e:
    print(f"\n\n✗ ERROR during monitoring: {e}")
    import traceback
    traceback.print_exc()
    try:
        monitor.cleanup()
    except:
        pass
    sys.exit(1)
PYEOF
