#!/usr/bin/env python3
"""
Diagnostic script to identify why decibel reader and song detector stop working
Run this on your Raspberry Pi to see what's happening
"""

import sys
import time
import logging
import traceback
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_audio_monitor():
    """Test AudioMonitor and monitor its health"""
    print("=" * 80)
    print("AUDIO MONITOR DIAGNOSTIC")
    print("=" * 80)
    print()
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.mic_song_detect import AudioMonitor
        
        print("✓ Successfully imported AudioMonitor")
        print()
        
        # Initialize monitor
        print("Initializing AudioMonitor...")
        monitor = AudioMonitor()
        print("✓ AudioMonitor initialized")
        print()
        
        # Start monitoring
        print("Starting audio monitoring...")
        monitor.start_monitoring()
        print("✓ Audio monitoring started")
        print()
        
        # Monitor for 5 minutes and track what happens
        print("Monitoring for 5 minutes to catch failures...")
        print("=" * 80)
        
        start_time = time.time()
        last_db_time = None
        last_db_value = None
        db_failures = 0
        song_detection_failures = 0
        
        check_interval = 10  # Check every 10 seconds
        max_duration = 300  # 5 minutes
        
        while (time.time() - start_time) < max_duration:
            elapsed = time.time() - start_time
            
            # Check if monitoring thread is alive
            thread_alive = monitor._monitoring_thread is not None and monitor._monitoring_thread.is_alive()
            
            # Get current dB
            current_db = monitor.get_current_db()
            current_song = monitor.get_current_song()
            stats = monitor.get_song_detection_stats()
            
            # Check if dB is updating
            if current_db != last_db_value:
                last_db_time = time.time()
                last_db_value = current_db
                db_failures = 0
            else:
                if last_db_time:
                    time_since_last_db = time.time() - last_db_time
                    if time_since_last_db > 30:  # No update for 30 seconds
                        db_failures += 1
                        print(f"⚠️  [{elapsed:.0f}s] dB reading stale (no update for {time_since_last_db:.1f}s)")
                        print(f"   Monitoring thread alive: {thread_alive}")
                        print(f"   Backend: {monitor._monitoring_backend}")
                        print(f"   Last activity: {monitor._last_activity}")
                        print(f"   Last DB timestamp: {monitor._last_db_ts}")
            
            # Check song detection
            if stats.get('last_error'):
                song_detection_failures += 1
                print(f"⚠️  [{elapsed:.0f}s] Song detection error: {stats.get('last_error')}")
            
            # Print status every 30 seconds
            if int(elapsed) % 30 == 0:
                print(f"[{elapsed:.0f}s] Status:")
                print(f"  dB: {current_db:.1f} dB")
                print(f"  Song: {current_song.get('title', 'Unknown')} - {current_song.get('artist', 'Unknown')}")
                print(f"  Thread alive: {thread_alive}")
                print(f"  Backend: {monitor._monitoring_backend}")
                print(f"  Last activity: {time.time() - monitor._last_activity:.1f}s ago")
                print(f"  DB failures: {db_failures}, Song failures: {song_detection_failures}")
                print()
            
            time.sleep(check_interval)
        
        print("=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)
        print(f"Total dB failures: {db_failures}")
        print(f"Total song detection failures: {song_detection_failures}")
        print(f"Final dB: {monitor.get_current_db():.1f}")
        print(f"Thread alive: {monitor._monitoring_thread is not None and monitor._monitoring_thread.is_alive()}")
        
        # Cleanup
        monitor.stop_monitoring()
        monitor.cleanup()
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("Starting audio diagnostic...")
    print("This will run for 5 minutes to catch failures")
    print()
    
    success = check_audio_monitor()
    
    if success:
        print("\n✓ Diagnostic completed successfully")
    else:
        print("\n✗ Diagnostic failed")
        sys.exit(1)
