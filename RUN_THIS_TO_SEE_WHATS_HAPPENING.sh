#!/bin/bash
# Simple command to see EXACTLY what's happening with dB reader and song detector
# This shows you real-time output so you can see if anything breaks

clear

cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════╗
║                 AUDIO SYSTEM LIVE MONITOR                            ║
║                                                                      ║
║  This shows EXACTLY what's happening with:                          ║
║    • dB Reader (audio levels)                                       ║
║    • Song Detector (music recognition)                              ║
║                                                                      ║
║  Watch for errors and you'll see exactly what's failing             ║
║                                                                      ║
║  Press Ctrl+C to stop                                               ║
╚══════════════════════════════════════════════════════════════════════╝

EOF

echo "Starting in 2 seconds..."
sleep 2

cd /workspace

# Set up environment for maximum verbosity
export PYTHONUNBUFFERED=1
export SONG_DETECT_INTERVAL_SEC=30
export DB_UPDATE_INTERVAL_SEC=2

# Run with full debug output
python3 -u << 'PYEOF'
import sys
import os
import time
import logging

sys.path.insert(0, '/workspace')

# Set up logging to show EVERYTHING
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)-5s] %(name)-20s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger('LIVE_MONITOR')

def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")

def print_status(emoji, label, value, color=""):
    print(f"{emoji} {label:20s}: {value}")

print_header("INITIALIZING AUDIO SYSTEM")

# Import and initialize
try:
    from services.sensors.mic_song_detect import AudioMonitor
    print_status("✓", "Import", "AudioMonitor loaded successfully")
    
    monitor = AudioMonitor()
    print_status("✓", "Initialization", "AudioMonitor created")
    print_status("ℹ", "Device Index", monitor.device_index if monitor.device_index else "Auto-detect")
    print_status("ℹ", "Sample Rate", f"{monitor.sample_rate} Hz")
    print_status("ℹ", "Song Detector", "Enabled" if monitor.song_detector else "Disabled")
    
except Exception as e:
    print_status("✗", "FAILED", str(e))
    import traceback
    traceback.print_exc()
    print("\n❌ Cannot start - fix the error above")
    sys.exit(1)

print_header("STARTING MONITORING")

try:
    monitor.start_monitoring()
    print_status("✓", "Monitor Status", "Started successfully")
except Exception as e:
    print_status("✗", "Start Failed", str(e))
    import traceback
    traceback.print_exc()
    sys.exit(1)

print_header("LIVE STATUS - Watching for problems...")
print("\nYou should see dB readings appear every 2 seconds")
print("Song detection will happen every 30 seconds")
print("\nIf either stops, you'll see it here immediately.\n")

# Monitor forever
iteration = 0
last_db = 0
last_db_time = time.time()
last_song = None
db_stuck_count = 0

try:
    while True:
        time.sleep(5)
        iteration += 1
        now = time.time()
        
        # Get current stats
        stats = monitor.get_stats()
        current_db = stats.get('current_db', 0)
        peak_db = stats.get('peak_db', 0)
        song = stats.get('current_song', {})
        song_stats = stats.get('song_detection', {})
        
        elapsed = int(now - time.time() + 5)
        
        print(f"\n╔═ Update #{iteration} " + "═"*60)
        
        # Check dB reader status
        if current_db != last_db:
            print(f"║ ✓ dB READER: {current_db:.1f} dB (Peak: {peak_db:.1f} dB)")
            last_db_time = now
            db_stuck_count = 0
        else:
            db_stuck_seconds = int(now - last_db_time)
            if db_stuck_seconds > 15:
                db_stuck_count += 1
                print(f"║ ⚠ dB READER: STUCK for {db_stuck_seconds}s - showing {current_db:.1f} dB")
                if db_stuck_count >= 3:
                    print(f"║ 🚨 CRITICAL: dB reader has been stuck for {db_stuck_seconds}s!")
            else:
                print(f"║ ℹ dB Reader: {current_db:.1f} dB")
        
        last_db = current_db
        
        # Check song detector status
        song_title = song.get('title', 'Unknown')
        song_artist = song.get('artist', 'Unknown')
        detection_active = song_stats.get('active', False)
        last_error = song_stats.get('last_error')
        
        if detection_active:
            print(f"║ 🎵 SONG DETECTOR: Detection in progress...")
        elif song_title and song_title != 'Unknown':
            if song_title != last_song:
                print(f"║ ✓ SONG DETECTED: '{song_title}' by {song_artist}")
                last_song = song_title
            else:
                print(f"║ ℹ Current Song: '{song_title}' by {song_artist}")
        else:
            if last_error:
                print(f"║ ⚠ SONG DETECTOR: {last_error}")
            else:
                print(f"║ ℹ Song Detector: Listening...")
        
        # Show additional stats
        if song_stats.get('last_attempt_duration_sec'):
            duration = song_stats['last_attempt_duration_sec']
            print(f"║   └─ Last detection took: {duration:.2f}s")
        
        print(f"╚" + "═"*77)
        
        # Critical alerts
        if db_stuck_count >= 4:
            print("\n" + "!"*80)
            print("🚨 ALERT: dB reader has been stuck for over 30 seconds!")
            print("This is the problem that needs to be fixed.")
            print("!"*80 + "\n")

except KeyboardInterrupt:
    print("\n\n" + "="*80)
    print("  STOPPING - User pressed Ctrl+C")
    print("="*80 + "\n")
    print("Cleaning up...")
    monitor.cleanup()
    print("✓ Cleanup complete\n")
    sys.exit(0)
    
except Exception as e:
    print("\n\n" + "="*80)
    print("  ❌ ERROR OCCURRED")
    print("="*80 + "\n")
    print(f"Error: {e}\n")
    import traceback
    traceback.print_exc()
    print("\nAttempting cleanup...")
    try:
        monitor.cleanup()
        print("✓ Cleanup complete\n")
    except:
        pass
    sys.exit(1)
PYEOF

echo ""
echo "Exited."
