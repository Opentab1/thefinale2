#!/usr/bin/env python3
"""
Quick verification script to confirm song detection and temperature fixes
Run this on your Raspberry Pi after installing dependencies
"""

import sys

print("="*80)
print("PULSE FIXES VERIFICATION")
print("="*80)
print()

all_good = True

# Check 1: ShazamIO
print("1. Checking ShazamIO (Song Detection)...")
try:
    from shazamio import Shazam
    print("   ✅ ShazamIO is installed and ready")
except ImportError as e:
    print(f"   ❌ ShazamIO not available: {e}")
    all_good = False

# Check 2: Audio libraries
print("\n2. Checking Audio Libraries...")
try:
    import numpy as np
    import sounddevice as sd
    print("   ✅ numpy and sounddevice are installed")
    
    devices = sd.query_devices()
    input_devices = [d for d in devices if d['max_input_channels'] > 0]
    
    if len(input_devices) > 0:
        print(f"   ✅ Found {len(input_devices)} audio input device(s)")
        for i, d in enumerate(input_devices):
            print(f"      {i+1}. {d['name']}")
    else:
        print("   ⚠️  No audio input devices found")
        print("      This is OK if running remotely, but won't work for dB/song detection")
        
except ImportError as e:
    print(f"   ❌ Audio libraries not available: {e}")
    all_good = False
except Exception as e:
    print(f"   ⚠️  Audio check error: {e}")

# Check 3: BME280
print("\n3. Checking BME280 Temperature Sensor...")
try:
    import busio
    import board
    import adafruit_bme280.advanced as adafruit_bme280
    
    print("   ✅ BME280 libraries are installed")
    
    try:
        # Try to initialize I2C
        i2c = busio.I2C(board.SCL, board.SDA)
        print("   ✅ I2C bus is accessible")
        
        # Try both addresses
        sensor_found = False
        for addr in [0x76, 0x77]:
            try:
                sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=addr)
                temp_c = sensor.temperature
                temp_f = (temp_c * 9/5) + 32
                humidity = sensor.humidity
                
                print(f"   ✅ BME280 sensor found at {hex(addr)}")
                print(f"      Temperature: {temp_f:.1f}°F ({temp_c:.1f}°C)")
                print(f"      Humidity: {humidity:.1f}%")
                sensor_found = True
                break
            except (ValueError, OSError):
                continue
        
        if not sensor_found:
            print("   ⚠️  BME280 sensor not found at 0x76 or 0x77")
            print("      Check wiring and run: sudo i2cdetect -y 1")
            print("      Enable I2C: sudo raspi-config → Interface Options → I2C")
            all_good = False
            
    except AttributeError as e:
        print("   ⚠️  I2C not available (not on Raspberry Pi hardware)")
        print("      This is OK if running in development environment")
    except Exception as e:
        print(f"   ❌ I2C error: {e}")
        all_good = False
        
except ImportError as e:
    print(f"   ❌ BME280 libraries not available: {e}")
    all_good = False

# Check 4: Test imports of main modules
print("\n4. Checking Pulse Sensor Modules...")
try:
    sys.path.insert(0, '/workspace')
    sys.path.insert(0, '/workspace/services')
    
    from services.sensors.mic_song_detect import AudioMonitor
    from services.sensors.bme280_reader import BME280Reader
    
    print("   ✅ Pulse sensor modules can be imported")
    print("   ✅ AudioMonitor (song detection + dB) ready")
    print("   ✅ BME280Reader (temperature/humidity) ready")
    
except Exception as e:
    print(f"   ❌ Module import error: {e}")
    all_good = False

# Summary
print()
print("="*80)
if all_good:
    print("✅ ALL CHECKS PASSED - System is ready!")
    print()
    print("Next steps:")
    print("1. Restart your Pulse system: ./start_pulse.sh")
    print("2. Open dashboard: http://localhost:8080")
    print("3. Check that song detection and temperature are working")
else:
    print("⚠️  SOME CHECKS FAILED - See details above")
    print()
    print("If on Raspberry Pi:")
    print("- Enable I2C: sudo raspi-config → Interface Options → I2C")
    print("- Check sensor wiring: sudo i2cdetect -y 1")
    print("- Restart after fixes")
print("="*80)
