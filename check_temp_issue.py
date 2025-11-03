#!/usr/bin/env python3
"""
Quick diagnostic to check why temperature isn't displaying
Run this on your Raspberry Pi where Pulse is running
"""

import sys
import time

print("="*60)
print("TEMPERATURE DISPLAY DIAGNOSTIC")
print("="*60)

# Test 1: Check if BME280 can be imported
print("\n1. Checking BME280 dependencies...")
try:
    from services.sensors.bme280_reader import BME280Reader
    print("   ✓ BME280Reader module imported successfully")
except Exception as e:
    print(f"   ✗ Failed to import BME280Reader: {e}")
    sys.exit(1)

# Test 2: Initialize sensor
print("\n2. Initializing BME280 sensor...")
try:
    sensor = BME280Reader()
    print(f"   ✓ Sensor initialized at address {hex(sensor.address)}")
except Exception as e:
    print(f"   ✗ Failed to initialize sensor: {e}")
    print("\nTroubleshooting:")
    print("  - Run: sudo i2cdetect -y 1")
    print("  - Check if sensor is connected")
    print("  - Try address 0x76 or 0x77")
    sys.exit(1)

# Test 3: Read sensor directly
print("\n3. Reading sensor data...")
try:
    data = sensor.read_sensor()
    print(f"   ✓ Sensor read successful!")
    print(f"     Temperature: {data.get('temperature_f')}°F")
    print(f"     Humidity: {data.get('humidity')}%")
    print(f"     Pressure: {data.get('pressure')} hPa")
except Exception as e:
    print(f"   ✗ Failed to read sensor: {e}")
    sys.exit(1)

# Test 4: Check cached values
print("\n4. Checking cached values (what hub reads)...")
cached = sensor.get_all_readings()
print(f"   Temperature: {cached.get('temperature_f')}")
print(f"   Humidity: {cached.get('humidity')}")

if cached.get('temperature_f') is None:
    print("\n   ⚠ WARNING: Cached temperature is None!")
    print("   This is why your dashboard shows no temperature.")
    print("\n   Solution: Call read_sensor() before get_all_readings()")
else:
    print("\n   ✓ Cached values look good!")

# Test 5: Check API endpoint
print("\n5. Checking dashboard API...")
try:
    import requests
    response = requests.get('http://localhost:8080/api/sensors/current', timeout=5)
    data = response.json()
    print(f"   API Response:")
    print(f"     Temperature: {data.get('temperature_f')}")
    print(f"     Humidity: {data.get('humidity')}")
    
    if data.get('temperature_f') is None:
        print("\n   ✗ API is returning None for temperature!")
        print("   The hub is not getting temperature data from BME280.")
    else:
        print("\n   ✓ API has temperature data!")
except Exception as e:
    print(f"   ⚠ Could not check API: {e}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
