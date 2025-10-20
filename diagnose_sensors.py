#!/usr/bin/env python3
"""
Pulse Sensor Diagnostics
Tests each sensor individually and reports status
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'services'))

print("="*80)
print("PULSE SENSOR DIAGNOSTICS")
print("="*80)
print()

results = {}

# Test 1: Camera
print("🎥 Testing Camera/People Counter...")
try:
    from services.sensors.camera_people import PeopleCounter
    counter = PeopleCounter(use_ai_hat=False)
    print("  ✓ Camera module imported successfully")
    
    # Try to detect people in a test
    import cv2
    import numpy as np
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    count, boxes, detections = counter.detect_people(test_frame)
    print(f"  ✓ Detection test passed (found {count} in blank frame)")
    
    results['camera'] = 'PASS'
except Exception as e:
    print(f"  ✗ Camera test failed: {e}")
    results['camera'] = f'FAIL: {e}'
print()

# Test 2: Microphone
print("🎤 Testing Microphone/Audio Monitor...")
try:
    from services.sensors.mic_song_detect import AudioMonitor
    monitor = AudioMonitor()
    print("  ✓ Audio module imported successfully")
    print(f"  ✓ Using audio device index: {monitor.device_index}")
    print(f"  ✓ Sample rate: {monitor.sample_rate} Hz")
    
    if monitor.song_detector:
        print("  ✓ Song detector initialized")
    else:
        print("  ⚠ Song detector not available (may need shazamio)")
    
    results['microphone'] = 'PASS'
except Exception as e:
    print(f"  ✗ Microphone test failed: {e}")
    results['microphone'] = f'FAIL: {e}'
print()

# Test 3: BME280
print("🌡️  Testing BME280 Sensor...")
try:
    from services.sensors.bme280_reader import BME280Reader
    bme = BME280Reader()
    print("  ✓ BME280 module imported successfully")
    
    # Try to read
    readings = bme.read_sensor()
    if readings:
        print(f"  ✓ Temperature: {readings.get('temperature_f')}°F")
        print(f"  ✓ Humidity: {readings.get('humidity')}%")
        print(f"  ✓ Pressure: {readings.get('pressure')} hPa")
    
    results['bme280'] = 'PASS'
except Exception as e:
    print(f"  ✗ BME280 test failed: {e}")
    results['bme280'] = f'FAIL: {e}'
print()

# Test 4: Light Sensor
print("💡 Testing Light Sensor...")
try:
    from services.sensors.light_level import LightSensor
    light = LightSensor()
    print("  ✓ Light sensor module imported successfully")
    
    # Try to calculate brightness from test frame
    import cv2
    import numpy as np
    test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    lux = light.calculate_brightness(test_frame)
    print(f"  ✓ Brightness calculation works (test: {lux} lux)")
    
    results['light_sensor'] = 'PASS'
except Exception as e:
    print(f"  ✗ Light sensor test failed: {e}")
    results['light_sensor'] = f'FAIL: {e}'
print()

# Test 5: Database
print("💾 Testing Database...")
try:
    from services.storage.db import PulseDB
    db = PulseDB()
    print("  ✓ Database module imported successfully")
    
    # Try to log something
    db.log_environment(temperature=72.0, humidity=50.0, light_level=300.0, noise_level=60.0)
    print("  ✓ Database write test passed")
    
    # Try to read
    env = db.get_latest_environment()
    if env:
        print(f"  ✓ Database read test passed")
    
    results['database'] = 'PASS'
except Exception as e:
    print(f"  ✗ Database test failed: {e}")
    results['database'] = f'FAIL: {e}'
print()

# Test 6: Song Detector
print("🎵 Testing Song Detector...")
try:
    from services.sensors.song_detector import SongDetector
    detector = SongDetector(enabled=False)  # Don't actually start it
    print("  ✓ Song detector module imported successfully")
    
    try:
        import shazamio
        print("  ✓ ShazamIO library available")
    except:
        print("  ⚠ ShazamIO not available (install with: pip install shazamio)")
    
    try:
        import sounddevice
        print("  ✓ sounddevice library available")
    except:
        print("  ⚠ sounddevice not available")
    
    results['song_detector'] = 'PASS'
except Exception as e:
    print(f"  ✗ Song detector test failed: {e}")
    results['song_detector'] = f'FAIL: {e}'
print()

# Test 7: Hardware Detection
print("🔧 Testing Hardware Detection...")
try:
    # Check for camera
    import subprocess
    camera_check = subprocess.run(['ls', '/dev/video*'], capture_output=True, text=True)
    if camera_check.returncode == 0:
        cameras = camera_check.stdout.strip().split('\n')
        print(f"  ✓ Found camera devices: {', '.join(cameras)}")
    else:
        print("  ⚠ No video devices found")
    
    # Check for audio
    audio_check = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
    if 'card' in audio_check.stdout.lower():
        print("  ✓ Audio recording device detected")
    else:
        print("  ⚠ No audio recording device found")
    
    # Check for I2C
    try:
        i2c_check = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
        if i2c_check.returncode == 0:
            if '76' in i2c_check.stdout or '77' in i2c_check.stdout:
                print("  ✓ BME280 detected on I2C bus (0x76 or 0x77)")
            else:
                print("  ⚠ I2C bus accessible but no BME280 found")
        else:
            print("  ⚠ Cannot access I2C bus")
    except FileNotFoundError:
        print("  ⚠ i2cdetect not available (install with: apt-get install i2c-tools)")
    
    results['hardware'] = 'PASS'
except Exception as e:
    print(f"  ✗ Hardware detection failed: {e}")
    results['hardware'] = f'FAIL: {e}'
print()

# Summary
print("="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)

all_pass = True
for component, status in results.items():
    if status == 'PASS':
        print(f"✓ {component.upper()}: {status}")
    else:
        print(f"✗ {component.upper()}: {status}")
        all_pass = False

print("="*80)

if all_pass:
    print("✓ ALL SYSTEMS READY!")
    print()
    print("You can now start Pulse with: ./START_HERE.sh")
    sys.exit(0)
else:
    print("⚠ SOME SYSTEMS NEED ATTENTION")
    print()
    print("Check the errors above and fix any issues before starting.")
    print("The system may still work with some sensors disabled.")
    sys.exit(1)
