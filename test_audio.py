#!/usr/bin/env python3
"""
Test Audio Monitor and Song Detection
"""
import sys
import time
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_audio():
    """Test audio monitor and song detection"""
    print("=" * 60)
    print("Testing Audio Monitor & Song Detection")
    print("=" * 60)
    
    try:
        from services.sensors.mic_song_detect import AudioMonitor
        
        print("\n✓ AudioMonitor module imported successfully")
        print("Initializing audio monitor...")
        
        monitor = AudioMonitor()
        print("✓ Audio monitor initialized")
        
        print("\nStarting audio monitoring...")
        monitor.start_monitoring()
        print("✓ Monitoring started")
        
        print("\n" + "=" * 60)
        print("Monitoring audio for 20 seconds...")
        print("Make some noise to test the dB readings!")
        print("=" * 60)
        
        for i in range(10):
            time.sleep(2)
            stats = monitor.get_stats()
            current_db = stats.get('current_db', 0)
            peak_db = stats.get('peak_db', 0)
            song = stats.get('current_song', {})
            
            print(f"\n[{i*2:2d}s] dB: {current_db:.1f} (peak: {peak_db:.1f})")
            
            if song and song.get('title') != 'Unknown':
                print(f"      🎵 Song: {song.get('title')} - {song.get('artist')}")
        
        print("\n" + "=" * 60)
        print("Audio monitoring test complete!")
        print("=" * 60)
        
        # Final stats
        final_stats = monitor.get_stats()
        print(f"\nFinal Statistics:")
        print(f"  Peak dB: {final_stats['peak_db']:.1f}")
        print(f"  Current Song: {final_stats['current_song'].get('title', 'Unknown')}")
        
        if final_stats['peak_db'] > 0:
            print("\n✓ SUCCESS: Audio sensor is working!")
            if final_stats['current_song'].get('title') != 'Unknown':
                print("✓ SUCCESS: Song detection is working!")
            else:
                print("\n⚠ WARNING: Song detection didn't detect any songs")
                print("  This is normal if no music was playing during the test")
                print("  Song detection uses ShazamIO and requires:")
                print("    1. pip install shazamio")
                print("    2. Audible music playing nearby")
                print("    3. Internet connection for Shazam API")
        else:
            print("\n⚠ WARNING: No audio detected")
            print("  Check microphone connection and permissions")
        
        monitor.stop_monitoring()
        monitor.cleanup()
        
        return final_stats['peak_db'] > 0
        
    except ImportError as e:
        print(f"\n✗ ERROR: Failed to import audio modules")
        print(f"  {e}")
        print("\nTroubleshooting:")
        print("  1. Install dependencies:")
        print("     pip install numpy pyaudio sounddevice")
        print("  2. For song detection:")
        print("     pip install shazamio")
        print("  3. Test audio device:")
        print("     arecord -l  # List devices")
        print("     arecord -d 3 test.wav  # Record 3 seconds")
        return False
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        print(f"  Type: {type(e).__name__}")
        print("\nTroubleshooting:")
        print("  1. Check microphone connection: arecord -l")
        print("  2. Test recording: arecord -d 3 test.wav")
        print("  3. Check permissions: sudo usermod -a -G audio $USER")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_audio()
    sys.exit(0 if success else 1)
