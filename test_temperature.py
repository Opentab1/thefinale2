#!/usr/bin/env python3
"""
Test BME280 Temperature Sensor
"""
import sys
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_bme280():
    """Test BME280 sensor"""
    print("=" * 60)
    print("Testing BME280 Temperature/Humidity Sensor")
    print("=" * 60)
    
    try:
        from services.sensors.bme280_reader import BME280Reader
        
        print("\n✓ BME280 module imported successfully")
        print("Initializing sensor...")
        
        sensor = BME280Reader()
        print("✓ Sensor initialized")
        
        print("\nReading sensor data...")
        data = sensor.read_sensor()
        
        if data:
            print("\n" + "=" * 60)
            print("SUCCESS! Sensor is working:")
            print("=" * 60)
            print(f"  Temperature: {data.get('temperature_f', 0):.1f}°F ({data.get('temperature_c', 0):.1f}°C)")
            print(f"  Humidity: {data.get('humidity', 0):.1f}%")
            print(f"  Pressure: {data.get('pressure', 0):.2f} hPa")
            print(f"  Altitude: {data.get('altitude', 0):.1f} m")
            print("=" * 60)
            
            # Test continuous reading
            print("\nTesting continuous reading for 10 seconds...")
            sensor.start_reading(interval=2)
            
            import time
            for i in range(5):
                time.sleep(2)
                readings = sensor.get_all_readings()
                print(f"  [{i+1}/5] Temp: {readings['temperature_f']:.1f}°F, Humidity: {readings['humidity']:.1f}%")
            
            sensor.stop_reading()
            print("\n✓ Continuous reading test passed!")
            
            return True
        else:
            print("\n✗ ERROR: Sensor returned no data")
            return False
            
    except ImportError as e:
        print(f"\n✗ ERROR: Failed to import BME280 module")
        print(f"  {e}")
        print("\nTroubleshooting:")
        print("  1. Install dependencies: pip install adafruit-circuitpython-bme280")
        print("  2. Enable I2C: sudo raspi-config -> Interface Options -> I2C")
        print("  3. Check I2C devices: sudo i2cdetect -y 1")
        return False
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        print(f"  Type: {type(e).__name__}")
        print("\nTroubleshooting:")
        print("  1. Check sensor wiring")
        print("  2. Verify I2C address: sudo i2cdetect -y 1")
        print("  3. Check sensor power")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_bme280()
    sys.exit(0 if success else 1)
