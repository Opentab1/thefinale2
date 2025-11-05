#!/usr/bin/env python3
"""
Comprehensive diagnostic for dB reader and song detector
Run this to identify exactly what's failing
"""

import sys
import logging
import time
from pathlib import Path

# Add path
sys.path.insert(0, '/opt/pulse')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("="*80)
print("COMPREHENSIVE dB READER & SONG DETECTOR DIAGNOSTIC")
print("="*80)
print()

# Test 1: Check dependencies
print("[TEST 1] Checking dependencies...")
print("-" * 80)
try:
    import numpy as np
    print(f"✓ NumPy: {np.__version__}")
except ImportError as e:
    print(f"✗ NumPy: NOT INSTALLED - {e}")
    sys.exit(1)

try:
    import sounddevice as sd
    print(f"✓ sounddevice: {sd.__version__}")
except ImportError as e:
    print(f"✗ sounddevice: NOT INSTALLED - {e}")

try:
    import pyaudio
    print(f"✓ PyAudio: {pyaudio.__version__}")
except ImportError as e:
    print(f"⚠ PyAudio: NOT INSTALLED - {e}")

try:
    from shazamio import Shazam
    print("✓ ShazamIO: Available")
except ImportError as e:
    print(f"✗ ShazamIO: NOT INSTALLED - {e}")
    print("  Install with: pip install shazamio aiohttp")

print()

# Test 2: Check audio devices
print("[TEST 2] Checking audio devices...")
print("-" * 80)
try:
    devices = sd.query_devices()
    print(f"Found {len(devices)} audio devices:")
    input_devices = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append(i)
            print(f"  [{i}] {dev['name']} - {dev['max_input_channels']} input channels")
    if not input_devices:
        print("  ✗ NO INPUT DEVICES FOUND!")
    else:
        print(f"  ✓ Found {len(input_devices)} input device(s)")
except Exception as e:
    print(f"✗ Error querying devices: {e}")

print()

# Test 3: Import AudioMonitor
print("[TEST 3] Importing AudioMonitor...")
print("-" * 80)
try:
    from services.sensors.mic_song_detect import AudioMonitor
    print("✓ AudioMonitor imported successfully")
except Exception as e:
    print(f"✗ Failed to import AudioMonitor: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 4: Initialize AudioMonitor
print("[TEST 4] Initializing AudioMonitor...")
print("-" * 80)
try:
    monitor = AudioMonitor()
    print(f"✓ AudioMonitor initialized")
    print(f"  - Device index: {monitor.device_index}")
    print(f"  - Sample rate: {monitor.sample_rate}")
    print(f"  - Chunk size: {monitor.chunk_size}")
    print(f"  - Song detector: {'Available' if monitor.song_detector else 'NOT AVAILABLE'}")
    
    if monitor.song_detector:
        print(f"  - Song detector enabled: {monitor.song_detector.enabled}")
        print(f"  - Song detector buffer mode: {monitor.song_detector.use_buffer_mode}")
        if monitor.song_detector.enabled:
            print(f"  - Detection thread: {'Alive' if monitor.song_detector.detection_thread and monitor.song_detector.detection_thread.is_alive() else 'NOT ALIVE'}")
            print(f"  - Watchdog thread: {'Alive' if monitor.song_detector.watchdog_thread and monitor.song_detector.watchdog_thread.is_alive() else 'NOT ALIVE'}")
            print(f"  - Event loop: {'Available' if monitor.song_detector._event_loop else 'NOT CREATED'}")
            if monitor.song_detector._event_loop:
                print(f"  - Event loop closed: {monitor.song_detector._event_loop.is_closed()}")
                print(f"  - Event loop thread: {'Alive' if monitor.song_detector._event_loop_thread and monitor.song_detector._event_loop_thread.is_alive() else 'NOT ALIVE'}")
    else:
        print("  ✗ Song detector is None - check initialization logs")
        
except Exception as e:
    print(f"✗ Failed to initialize AudioMonitor: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Test 5: Start monitoring
print("[TEST 5] Starting audio monitoring...")
print("-" * 80)
try:
    monitor.start_monitoring()
    print("✓ start_monitoring() called")
    time.sleep(2)  # Give it time to initialize
    
    if monitor.running:
        print("✓ Monitoring is running")
    else:
        print("✗ Monitoring is NOT running!")
    
    if monitor._monitoring_thread:
        if monitor._monitoring_thread.is_alive():
            print("✓ Monitoring thread is alive")
        else:
            print("✗ Monitoring thread is NOT alive!")
    else:
        print("✗ Monitoring thread is None!")
        
except Exception as e:
    print(f"✗ Failed to start monitoring: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 6: Check dB readings
print("[TEST 6] Checking dB readings (10 seconds)...")
print("-" * 80)
db_readings = []
for i in range(10):
    time.sleep(1)
    db = monitor.get_current_db()
    db_readings.append(db)
    print(f"  [{i+1}s] dB: {db:.1f}")
    
    if db > 0:
        print(f"     ✓ dB reader is working!")
        break

if all(db == 0 for db in db_readings):
    print("  ✗ dB reader stuck at 0.0 - audio stream may not be working")
    print("  - Check if audio device is connected")
    print("  - Check if microphone permissions are granted")
    print("  - Check logs for audio stream errors")
else:
    max_db = max(db_readings)
    print(f"  ✓ dB reader working (peak: {max_db:.1f} dB)")

print()

# Test 7: Check audio buffer
print("[TEST 7] Checking audio buffer...")
print("-" * 80)
print(f"  - Buffer size: {monitor._audio_buffer_size}")
print(f"  - Buffer index: {monitor._buffer_index}")
print(f"  - Buffer ready: {monitor._buffer_index >= monitor._audio_buffer_size}")

# Check if buffer has actual data (not all zeros)
buffer_sum = np.sum(np.abs(monitor._audio_buffer))
if buffer_sum > 0:
    print(f"  ✓ Buffer contains audio data (sum: {buffer_sum})")
else:
    print(f"  ✗ Buffer is empty or all zeros!")
    print("  - Audio stream may not be reading data")

print()

# Test 8: Test song detection
print("[TEST 8] Testing song detection...")
print("-" * 80)
if monitor.song_detector and monitor.song_detector.enabled:
    if monitor._buffer_index >= monitor._audio_buffer_size:
        print("  Buffer is ready, attempting detection...")
        try:
            result = monitor.song_detector.detect_song_from_buffer(
                monitor._audio_buffer, 
                monitor.sample_rate
            )
            if result:
                print("  ✓ Detection started successfully")
                time.sleep(3)  # Give it time to process
                song = monitor.song_detector.get_latest_song()
                print(f"  - Latest song: {song}")
            else:
                print("  ✗ Detection returned False")
        except Exception as e:
            print(f"  ✗ Detection failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"  ⚠ Buffer not ready yet (index: {monitor._buffer_index}/{monitor._audio_buffer_size})")
else:
    print("  ✗ Song detector not available or not enabled")

print()

# Test 9: Check event loop
print("[TEST 9] Checking event loop...")
print("-" * 80)
if monitor.song_detector and monitor.song_detector.enabled:
    loop = monitor.song_detector._event_loop
    if loop:
        print(f"  ✓ Event loop exists")
        print(f"  - Closed: {loop.is_closed()}")
        print(f"  - Thread alive: {monitor.song_detector._event_loop_thread.is_alive() if monitor.song_detector._event_loop_thread else False}")
    else:
        print("  ✗ Event loop is None!")
        print("  - Event loop should be created during initialization")
        print("  - Trying to ensure event loop...")
        try:
            monitor.song_detector._ensure_event_loop()
            print("  ✓ Event loop created")
        except Exception as e:
            print(f"  ✗ Failed to create event loop: {e}")

print()

# Summary
print("="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)
print(f"dB Reader: {'WORKING' if max(db_readings) > 0 else 'NOT WORKING'}")
print(f"Song Detector: {'ENABLED' if monitor.song_detector and monitor.song_detector.enabled else 'DISABLED'}")
print(f"Audio Buffer: {'READY' if monitor._buffer_index >= monitor._audio_buffer_size else 'NOT READY'}")
print(f"Event Loop: {'AVAILABLE' if monitor.song_detector and monitor.song_detector._event_loop and not monitor.song_detector._event_loop.is_closed() else 'NOT AVAILABLE'}")
print("="*80)

# Cleanup
try:
    monitor.stop_monitoring()
except:
    pass

print("\nCheck the output above to identify the issue!")
