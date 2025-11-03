#!/usr/bin/env python3
"""
Quick diagnostic test for BME280 temperature sensor
Run this on your Raspberry Pi 5 to test if sensor is working
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_bme280_direct():
    """Test BME280 sensor directly"""
    print("\n" + "="*60)
    print("TEST 1: Direct BME280 Sensor Test")
    print("="*60)
    
    try:
        from services.sensors.bme280_reader import BME280Reader
        
        print("✓ BME280Reader module imported successfully")
        
        # Try to initialize sensor
        print("Initializing BME280 sensor...")
        sensor = BME280Reader(address=0x76)
        print(f"✓ BME280 sensor initialized at address {hex(sensor.address)}")
        
        # Try to read sensor
        print("Reading sensor data...")
        data = sensor.read_sensor()
        
        if data and data.get("temperature_f") is not None:
            print("\n✓✓✓ SENSOR READING SUCCESSFUL! ✓✓✓")
            print(f"  Temperature: {data['temperature_f']:.1f}°F ({data['temperature_c']:.1f}°C)")
            print(f"  Humidity: {data['humidity']:.1f}%")
            print(f"  Pressure: {data['pressure']:.2f} hPa")
            print(f"  Altitude: {data['altitude']:.1f} m")
            return True
        else:
            print("✗ Sensor returned no data or invalid data")
            return False
            
    except Exception as e:
        print(f"✗ Error testing BME280: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hub_instance():
    """Test if hub instance can collect sensor data"""
    print("\n" + "="*60)
    print("TEST 2: Hub Sensor Data Collection")
    print("="*60)
    
    try:
        from services.hub.main import PulseHub
        
        print("Creating PulseHub instance...")
        hub = PulseHub()
        
        if hub.bme280 is None:
            print("✗ BME280 sensor not initialized in hub")
            return False
        
        print("✓ Hub has BME280 sensor initialized")
        
        # Collect sensor data
        print("Collecting sensor data from hub...")
        data = hub._collect_sensor_data()
        
        print("\nHub collected data:")
        print(f"  Temperature: {data.get('temperature_f', 'None')}°F")
        print(f"  Humidity: {data.get('humidity', 'None')}%")
        print(f"  Occupancy: {data.get('occupancy', 0)} people")
        
        if data.get('temperature_f') is not None:
            print("\n✓✓✓ HUB COLLECTING TEMPERATURE DATA! ✓✓✓")
            return True
        else:
            print("\n✗ Hub is NOT collecting temperature data (returns None)")
            return False
            
    except Exception as e:
        print(f"✗ Error testing hub: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoint():
    """Test if API endpoint returns temperature"""
    print("\n" + "="*60)
    print("TEST 3: Dashboard API Endpoint")
    print("="*60)
    
    try:
        import requests
        
        print("Testing API endpoint at http://localhost:8080/api/sensors/current")
        response = requests.get("http://localhost:8080/api/sensors/current", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✓ API responded successfully")
            print(f"  Temperature: {data.get('temperature_f', 'None')}°F")
            print(f"  Humidity: {data.get('humidity', 'None')}%")
            
            if data.get('temperature_f') is not None:
                print("\n✓✓✓ API RETURNING TEMPERATURE DATA! ✓✓✓")
                return True
            else:
                print("\n✗ API returns None for temperature")
                return False
        else:
            print(f"✗ API returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API - is the dashboard server running?")
        print("  Start it with: sudo systemctl start pulse-dashboard")
        return False
    except Exception as e:
        print(f"✗ Error testing API: {e}")
        return False

def check_services():
    """Check if services are running"""
    print("\n" + "="*60)
    print("SYSTEM STATUS CHECK")
    print("="*60)
    
    import subprocess
    
    services = [
        'pulse-hub.service',
        'pulse-dashboard.service'
    ]
    
    for service in services:
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True,
                text=True
            )
            status = result.stdout.strip()
            if status == 'active':
                print(f"✓ {service}: RUNNING")
            else:
                print(f"✗ {service}: {status.upper()}")
        except Exception as e:
            print(f"? {service}: Cannot check ({e})")

if __name__ == "__main__":
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║  PULSE TEMPERATURE DASHBOARD DIAGNOSTIC                 ║")
    print("╚" + "="*58 + "╝")
    
    # Check services first
    check_services()
    
    # Run tests
    test1 = test_bme280_direct()
    test2 = test_hub_instance()
    test3 = test_api_endpoint()
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"Direct BME280 Sensor:      {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"Hub Data Collection:       {'✓ PASS' if test2 else '✗ FAIL'}")
    print(f"API Endpoint:              {'✓ PASS' if test3 else '✗ FAIL'}")
    print("="*60)
    
    if test1 and not test3:
        print("\n📋 DIAGNOSIS: Sensor works but data isn't reaching the dashboard")
        print("   → The hub service may not be running properly")
        print("   → Try: sudo systemctl restart pulse-hub && sudo systemctl restart pulse-dashboard")
    elif not test1:
        print("\n📋 DIAGNOSIS: BME280 sensor cannot be read")
        print("   → Check sensor wiring and I2C connection")
        print("   → Run: sudo i2cdetect -y 1")
        print("   → Expected to see sensor at 0x76 or 0x77")
    elif test1 and test2 and test3:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        print("   Temperature data should be visible on dashboard")
        print("   If not, try refreshing your browser")
    
    print()
