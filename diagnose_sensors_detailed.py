#!/usr/bin/env python3
"""
Pulse 1.0 - Detailed Sensor Diagnostics
Run this script to check sensor functionality and dependencies
"""

import sys
import os

print("="*80)
print("PULSE SENSOR DIAGNOSTICS")
print("="*80)

# Check Python version
print(f"\n✓ Python Version: {sys.version}")

# Check dependencies
print("\n📦 CHECKING DEPENDENCIES:")
print("-"*80)

dependencies = {
    'numpy': 'NumPy',
    'cv2': 'OpenCV (opencv-python)',
    'pyaudio': 'PyAudio',
    'sounddevice': 'sounddevice',
    'smbus2': 'smbus2 (for BME280)',
    'board': 'Adafruit Blinka',
    'adafruit_bme280': 'Adafruit BME280',
}

available = {}
missing = []

for module, name in dependencies.items():
    try:
        __import__(module)
        print(f"  ✓ {name}")
        available[module] = True
    except ImportError:
        print(f"  ✗ {name} - NOT INSTALLED")
        available[module] = False
        missing.append(name)

# Test camera
print("\n📷 TESTING CAMERA:")
print("-"*80)
if available.get('cv2'):
    import cv2
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        print(f"  ✓ Camera accessible")
        print(f"  - Resolution: {w}x{h}")
        cap.release()
    else:
        print(f"  ✗ Camera not accessible or no frame")
    cap.release()
else:
    print("  ⊘ Skipped - OpenCV not installed")

# Test audio devices
print("\n🎤 TESTING AUDIO DEVICES:")
print("-"*80)
if available.get('pyaudio'):
    import pyaudio
    try:
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        print(f"  ✓ PyAudio found {device_count} audio devices")
        
        input_devices = []
        for i in range(device_count):
            try:
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    input_devices.append((i, info['name'], info['maxInputChannels']))
                    print(f"    - Input Device {i}: {info['name']} ({info['maxInputChannels']} channels)")
            except:
                pass
        
        if not input_devices:
            print("  ⚠ No input devices found!")
        
        p.terminate()
    except Exception as e:
        print(f"  ✗ PyAudio error: {e}")
elif available.get('sounddevice'):
    import sounddevice as sd
    try:
        devices = sd.query_devices()
        print(f"  ✓ sounddevice found {len(devices)} audio devices")
        
        for idx, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"    - Input Device {idx}: {device['name']} ({device['max_input_channels']} channels)")
    except Exception as e:
        print(f"  ✗ sounddevice error: {e}")
else:
    print("  ⊘ Skipped - No audio backend installed")

# Test sensors
print("\n🔬 TESTING SENSORS:")
print("-"*80)

# Add services to path
sys.path.insert(0, 'services')

# Test Light Sensor
print("\n  💡 Light Sensor:")
try:
    from sensors.light_level import LightSensor
    sensor = LightSensor()
    print("    ✓ Initialized successfully")
    print(f"    - Snapshot path: {sensor.snapshot_path}")
    print(f"    - Current reading: {sensor.get_light_level()} lux")
except ImportError as e:
    print(f"    ✗ Import failed: {e}")
except Exception as e:
    print(f"    ✗ Initialization failed: {e}")

# Test Audio Monitor
print("\n  🔊 Audio Monitor:")
try:
    from sensors.mic_song_detect import AudioMonitor
    monitor = AudioMonitor()
    print("    ✓ Initialized successfully")
    print(f"    - Device index: {monitor.device_index}")
    print(f"    - Sample rate: {monitor.sample_rate}")
    print(f"    - Current dB: {monitor.get_current_db()}")
except ImportError as e:
    print(f"    ✗ Import failed: {e}")
except Exception as e:
    print(f"    ✗ Initialization failed: {e}")

# Test BME280
print("\n  🌡️  BME280 Sensor:")
try:
    from sensors.bme280_reader import BME280Reader
    bme = BME280Reader()
    print("    ✓ Initialized successfully")
    readings = bme.read_sensor()
    if readings:
        print(f"    - Temperature: {readings.get('temperature_f')}°F")
        print(f"    - Humidity: {readings.get('humidity')}%")
        print(f"    - Pressure: {readings.get('pressure')} hPa")
except ImportError as e:
    print(f"    ✗ Import failed: {e}")
except Exception as e:
    print(f"    ✗ Initialization failed: {e}")

# Summary
print("\n"+"="*80)
print("SUMMARY:")
print("="*80)
if missing:
    print(f"\n⚠  Missing dependencies ({len(missing)}):")
    for dep in missing:
        print(f"  - {dep}")
    print(f"\n💡 Install missing dependencies:")
    print(f"   sudo pip3 install numpy opencv-python pyaudio sounddevice")
    print(f"   sudo pip3 install adafruit-blinka adafruit-circuitpython-bme280")
else:
    print("\n✓ All dependencies installed!")

print("\n" + "="*80)
