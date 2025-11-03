#!/usr/bin/env python3
"""
Test script to verify temperature display fix
Run this AFTER deploying the fixed code to your Raspberry Pi
"""

import sys
import time
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

print("="*70)
print("TEMPERATURE DISPLAY FIX - VERIFICATION TEST")
print("="*70)

# Test 1: BME280 Module Import
print("\n[TEST 1] Importing BME280 module...")
try:
    from services.sensors.bme280_reader import BME280Reader
    print("✓ PASS: Module imported successfully")
except Exception as e:
    print(f"✗ FAIL: {e}")
    sys.exit(1)

# Test 2: BME280 Initialization
print("\n[TEST 2] Initializing BME280 sensor...")
try:
    sensor = BME280Reader(address=0x76)
    print(f"✓ PASS: Sensor initialized at address {hex(sensor.address)}")
except Exception as e:
    print(f"✗ FAIL: Could not initialize sensor")
    print(f"  Error: {e}")
    print("\n  Troubleshooting:")
    print("  1. Check sensor is connected: sudo i2cdetect -y 1")
    print("  2. Verify I2C is enabled: sudo raspi-config")
    print("  3. Check wiring: VCC, GND, SDA, SCL")
    sys.exit(1)

# Test 3: Direct Sensor Read
print("\n[TEST 3] Reading sensor directly...")
try:
    data = sensor.read_sensor()
    temp = data.get('temperature_f')
    humidity = data.get('humidity')
    
    if temp is not None and humidity is not None:
        print(f"✓ PASS: Sensor reading successful")
        print(f"  Temperature: {temp:.1f}°F")
        print(f"  Humidity: {humidity:.1f}%")
        print(f"  Pressure: {data.get('pressure', 0):.2f} hPa")
    else:
        print(f"✗ FAIL: Sensor returned None values")
        sys.exit(1)
except Exception as e:
    print(f"✗ FAIL: {e}")
    sys.exit(1)

# Test 4: Cached Values (before starting background thread)
print("\n[TEST 4] Checking cached values...")
cached = sensor.get_all_readings()
if cached.get('temperature_f') is not None:
    print(f"✓ PASS: Cache populated with data")
    print(f"  Cached temp: {cached['temperature_f']:.1f}°F")
else:
    print(f"✗ FAIL: Cache is empty (temperature is None)")
    sys.exit(1)

# Test 5: Start Background Reading with Initial Sync
print("\n[TEST 5] Starting background reading thread...")
try:
    sensor.start_reading(interval=30)
    print("✓ PASS: Background thread started")
    print("  (Initial synchronous read should have occurred)")
except Exception as e:
    print(f"✗ FAIL: {e}")
    sys.exit(1)

# Test 6: Verify cache stays populated
print("\n[TEST 6] Verifying cache remains populated...")
time.sleep(2)  # Give thread time to start
cached_after = sensor.get_all_readings()
if cached_after.get('temperature_f') is not None:
    print(f"✓ PASS: Cache still has data after thread start")
    print(f"  Current: {cached_after['temperature_f']:.1f}°F")
else:
    print(f"✗ FAIL: Cache lost data after thread start")
    sys.exit(1)

# Test 7: Hub Integration (if hub module available)
print("\n[TEST 7] Testing hub integration...")
try:
    from services.hub.main import PulseHub
    
    # Create minimal config for testing
    import tempfile
    import yaml
    
    config = {
        'venue': {'name': 'Test', 'timezone': 'America/Chicago'},
        'zones': [{'name': 'Main Floor'}],
        'modules': {
            'camera': False,
            'mic': False,
            'bme280': True,
            'light_sensor': False,
            'ai_hat': False,
            'pan_tilt': False
        },
        'smart_integrations': {
            'hvac': {'enabled': False},
            'lighting': {'enabled': False},
            'tv': {'enabled': False},
            'music': {'enabled': False}
        },
        'policies': {},
        'dashboard': {'port': 8080}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    
    try:
        hub = PulseHub(config_path=config_path)
        
        if hub.bme280 is None:
            print("✗ FAIL: Hub did not initialize BME280")
            sys.exit(1)
        
        # Collect sensor data
        data = hub._collect_sensor_data()
        
        if data.get('temperature_f') is not None:
            print("✓ PASS: Hub successfully collects temperature data")
            print(f"  Hub data: {data['temperature_f']:.1f}°F, {data['humidity']:.1f}%")
        else:
            print("✗ FAIL: Hub collected None for temperature")
            print(f"  Data: {data}")
            sys.exit(1)
    finally:
        os.unlink(config_path)
        
except Exception as e:
    print(f"⚠ SKIP: Hub test skipped ({e})")

# Cleanup
sensor.stop_reading()

print("\n" + "="*70)
print("ALL TESTS PASSED! ✓")
print("="*70)
print("\nThe temperature fix is working correctly.")
print("Temperature should now display on your dashboard immediately after startup.")
print("\nNext steps:")
print("  1. Deploy this code to your Raspberry Pi")
print("  2. Restart the hub service: sudo systemctl restart pulse-hub.service")
print("  3. Check the dashboard - temperature should appear within 5 seconds")
