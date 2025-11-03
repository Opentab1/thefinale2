#!/usr/bin/env python3
"""
Audio Monitor Diagnostic Test
Tests microphone, dB readings, and song detection
"""

import sys
import logging
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, '/opt/pulse')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_audio_devices():
    """List available audio devices"""
    print("\n" + "="*60)
    print("TEST 1: Audio Devices")
    print("="*60)
    
    # Check with arecord
    import subprocess
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        print("\nAudio devices (arecord -l):")
        print(result.stdout)
        if result.returncode != 0:
            print("ERROR:", result.stderr)
            return False
    except Exception as e:
        print(f"✗ Could not list audio devices: {e}")
        return False
    
    return True

def test_audio_dependencies():
    """Check if audio dependencies are installed"""
    print("\n" + "="*60)
    print("TEST 2: Audio Dependencies")
    print("="*60)
    
    # Check NumPy
    try:
        import numpy as np
        print("✓ NumPy installed:", np.__version__)
    except ImportError:
        print("✗ NumPy NOT installed")
        print("  Install with: pip install numpy")
        return False
    
    # Check PyAudio
    try:
        import pyaudio
        print("✓ PyAudio installed:", pyaudio.__version__)
    except ImportError:
        print("⚠ PyAudio NOT installed (optional)")
    
    # Check sounddevice
    try:
        import sounddevice as sd
        print("✓ sounddevice installed:", sd.__version__)
    except ImportError:
        print("⚠ sounddevice NOT installed (optional)")
    
    # Check ShazamIO
    try:
        import shazamio
        print("✓ ShazamIO installed")
    except ImportError:
        print("⚠ ShazamIO NOT installed (song detection will not work)")
    
    return True

def test_audio_monitor_init():
    """Test if AudioMonitor can initialize"""
    print("\n" + "="*60)
    print("TEST 3: AudioMonitor Initialization")
    print("="*60)
    
    try:
        from services.sensors.mic_song_detect import AudioMonitor
        
        print("Creating AudioMonitor instance...")
        monitor = AudioMonitor()
        
        print(f"✓ AudioMonitor created successfully")
        print(f"  Device index: {monitor.device_index}")
        print(f"  Sample rate: {monitor.sample_rate}")
        print(f"  Chunk size: {monitor.chunk_size}")
        print(f"  Song detector: {'Available' if monitor.song_detector else 'Not available'}")
        
        return monitor
        
    except Exception as e:
        print(f"✗ Failed to create AudioMonitor: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_audio_monitor_run(monitor):
    """Test if AudioMonitor can actually run"""
    print("\n" + "="*60)
    print("TEST 4: AudioMonitor Running Test (30 seconds)")
    print("="*60)
    
    try:
        print("Starting audio monitoring...")
        monitor.start_monitoring()
        
        print("Monitoring for 30 seconds...")
        for i in range(6):
            time.sleep(5)
            stats = monitor.get_stats()
            print(f"  [{i*5}s] dB: {stats['current_db']:.1f} | Peak: {stats['peak_db']:.1f}")
            
            song = stats.get('current_song', {})
            if song.get('title') != 'Unknown':
                print(f"        Song: {song['title']} - {song['artist']}")
        
        print("\n✓ Audio monitor ran for 30 seconds successfully")
        
        monitor.stop_monitoring()
        return True
        
    except Exception as e:
        print(f"\n✗ Audio monitor failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║  PULSE AUDIO MONITOR DIAGNOSTIC                         ║")
    print("╚" + "="*58 + "╝")
    
    # Run tests
    test1 = test_audio_devices()
    test2 = test_audio_dependencies()
    
    if not test1 or not test2:
        print("\n" + "="*60)
        print("FAILED: Prerequisites not met")
        print("="*60)
        return
    
    monitor = test_audio_monitor_init()
    if not monitor:
        print("\n" + "="*60)
        print("FAILED: Could not initialize AudioMonitor")
        print("="*60)
        return
    
    test4 = test_audio_monitor_run(monitor)
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"Audio Devices:         {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"Dependencies:          {'✓ PASS' if test2 else '✗ FAIL'}")
    print(f"AudioMonitor Init:     {'✓ PASS' if monitor else '✗ FAIL'}")
    print(f"AudioMonitor Running:  {'✓ PASS' if test4 else '✗ FAIL'}")
    print("="*60)
    
    if test1 and test2 and monitor and test4:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("Audio monitor is working correctly")
    else:
        print("\n⚠ SOME TESTS FAILED")
        print("Check the output above for specific errors")
    
    print()

if __name__ == "__main__":
    main()
