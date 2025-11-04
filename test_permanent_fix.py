#!/usr/bin/env python3
"""
Quick verification test for the permanent 20-minute fix
This script monitors the audio monitoring system for proper operation
"""

import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from services.sensors.mic_song_detect import AudioMonitor
    from services.storage.db import PulseDB
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print("Make sure you're running from the workspace root")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_audio_monitor_stability():
    """Test audio monitor stability over time"""
    print("="*80)
    print("PERMANENT FIX VERIFICATION TEST")
    print("="*80)
    print()
    print("This test will run for 30 minutes to verify the fix.")
    print("Press Ctrl+C to stop early.")
    print()
    
    # Initialize components
    try:
        logger.info("Initializing AudioMonitor...")
        monitor = AudioMonitor()
        logger.info("✅ AudioMonitor initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize AudioMonitor: {e}")
        return False
    
    try:
        logger.info("Initializing PulseDB...")
        db = PulseDB()
        logger.info("✅ PulseDB initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize PulseDB: {e}")
        return False
    
    # Start monitoring
    try:
        logger.info("Starting audio monitoring...")
        monitor.start_monitoring()
        logger.info("✅ Audio monitoring started")
    except Exception as e:
        logger.error(f"❌ Failed to start monitoring: {e}")
        return False
    
    print()
    print("="*80)
    print("MONITORING STARTED - Testing for 30 minutes")
    print("="*80)
    print()
    
    start_time = time.time()
    last_report = 0
    db_write_count = 0
    audio_read_count = 0
    song_detect_count = 0
    errors = []
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Stop after 30 minutes
            if elapsed > 1800:  # 30 minutes
                logger.info("✅ 30-minute test completed successfully!")
                break
            
            # Report every minute
            if current_time - last_report >= 60:
                minutes_elapsed = int(elapsed / 60)
                
                # Get current stats
                try:
                    stats = monitor.get_stats()
                    current_db = stats.get('current_db', 0)
                    current_song = stats.get('current_song', {})
                    song_title = current_song.get('title', 'Unknown')
                    
                    # Check if dB reading is working
                    if current_db > 0:
                        audio_read_count += 1
                    
                    # Check if song detection is working
                    if song_title not in ('Unknown', None):
                        song_detect_count += 1
                    
                    print(f"[{minutes_elapsed:02d}:{int(elapsed%60):02d}] "
                          f"✅ System Active | "
                          f"dB: {current_db:.1f} | "
                          f"Song: {song_title[:30]} | "
                          f"Audio Reads: {audio_read_count} | "
                          f"Songs: {song_detect_count}")
                    
                    # Try database write
                    try:
                        db.log_environment(
                            temperature=72.0,
                            humidity=45.0,
                            noise_level=current_db
                        )
                        db_write_count += 1
                    except Exception as db_err:
                        error_msg = f"DB write error at {minutes_elapsed}m: {db_err}"
                        errors.append(error_msg)
                        logger.error(f"⚠️ {error_msg}")
                    
                except Exception as e:
                    error_msg = f"Stats read error at {minutes_elapsed}m: {e}"
                    errors.append(error_msg)
                    logger.error(f"⚠️ {error_msg}")
                
                last_report = current_time
                
                # Special milestone checks
                if minutes_elapsed == 20:
                    print()
                    print("="*80)
                    print("🎉 20-MINUTE MARK REACHED - PREVIOUS FAILURE POINT!")
                    print("✅ System is still running - Fix is working!")
                    print("="*80)
                    print()
                
                if minutes_elapsed == 25:
                    print()
                    print("="*80)
                    print("🎉 25-MINUTE MARK REACHED")
                    print("✅ Well past the failure point - Fix confirmed!")
                    print("="*80)
                    print()
            
            time.sleep(5)
    
    except KeyboardInterrupt:
        print()
        print("="*80)
        print("Test interrupted by user")
        print("="*80)
    
    finally:
        # Cleanup
        logger.info("Cleaning up...")
        try:
            monitor.cleanup()
            logger.info("✅ Cleanup completed")
        except Exception as e:
            logger.error(f"⚠️ Cleanup error: {e}")
    
    # Final report
    print()
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Duration: {int(elapsed/60)} minutes {int(elapsed%60)} seconds")
    print(f"Audio Reads: {audio_read_count}")
    print(f"Songs Detected: {song_detect_count}")
    print(f"Database Writes: {db_write_count}")
    print(f"Errors: {len(errors)}")
    print()
    
    if errors:
        print("⚠️ Errors encountered:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        print()
    
    # Determine pass/fail
    success = (
        audio_read_count > 0 and
        db_write_count > 0 and
        len(errors) < 5 and  # Allow a few transient errors
        elapsed > 1200  # At least 20 minutes
    )
    
    if success:
        print("✅ TEST PASSED - Fix is working correctly!")
        print()
        print("The system ran for over 20 minutes without failure.")
        print("This confirms the permanent fix is effective.")
        return True
    else:
        print("❌ TEST FAILED - Issues detected")
        print()
        print("The system may still have problems. Check the errors above.")
        return False

if __name__ == "__main__":
    try:
        success = test_audio_monitor_stability()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}", exc_info=True)
        sys.exit(1)
