#!/usr/bin/env python3
"""
Pulse Environmental Service - Standalone
Runs only environmental sensors (temperature, humidity, pressure, light)
Isolated from other services for fault tolerance
"""

import logging
import sys
import os
import json
from pathlib import Path
import time

# Auto-detect Pulse installation directory
SCRIPT_DIR = Path(__file__).resolve().parent

# Try common locations
PULSE_DIRS = [
    SCRIPT_DIR,
    Path('/workspace'),
    Path('/opt/pulse'),
    Path.home() / 'pulse',
]

PULSE_ROOT = None
for pd in PULSE_DIRS:
    if (pd / 'services' / 'sensors').exists():
        PULSE_ROOT = pd
        break

if PULSE_ROOT is None:
    print("ERROR: Cannot find Pulse installation!")
    sys.exit(1)

print(f"Found Pulse at: {PULSE_ROOT}")

# Add paths
sys.path.insert(0, str(PULSE_ROOT))
sys.path.insert(0, str(PULSE_ROOT / 'services'))
os.chdir(str(PULSE_ROOT))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def main():
    """Main entry point for environmental service"""
    logger.info("="*80)
    logger.info("🌡️  PULSE ENVIRONMENTAL SERVICE - STARTING")
    logger.info("="*80)
    logger.info("Temperature/Humidity/Pressure: Every 10 seconds")
    logger.info("Light Level: Every 10 seconds")
    logger.info("="*80)
    
    # Create necessary directories and define cache paths
    data_dir = Path("/opt/pulse/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    environmental_cache = data_dir / "environmental_cache.json"
    logger.info(f"📁 Cache file: {environmental_cache}")
    
    try:
        from services.sensors.bme280_reader import BME280Reader
        from services.sensors.light_level import LightSensor
        
        # Initialize sensors
        logger.info("Initializing environmental sensors...")
        
        # Try to initialize BME280 (temperature/humidity/pressure)
        bme280 = None
        try:
            bme280 = BME280Reader()
            logger.info("✅ BME280 (temp/humidity/pressure) initialized")
        except Exception as e:
            logger.warning(f"⚠️  BME280 not available: {e}")
        
        # Try to initialize light sensor
        light_sensor = None
        try:
            light_sensor = LightSensor()
            logger.info("✅ Light sensor initialized")
        except Exception as e:
            logger.warning(f"⚠️  Light sensor not available: {e}")
        
        if not bme280 and not light_sensor:
            logger.error("❌ No environmental sensors available! Exiting.")
            sys.exit(1)
        
        logger.info("="*80)
        logger.info("🌡️  Environmental sensors ready - starting monitoring loop")
        logger.info("="*80)
        
        # Main monitoring loop
        update_interval = 10  # seconds
        
        while True:
            try:
                # Collect environmental data
                data = {
                    "timestamp": time.time()
                }
                
                # Read BME280 if available
                if bme280:
                    try:
                        readings = bme280.read()
                        if readings:
                            data["temperature_f"] = readings.get('temperature_f')
                            data["temperature_c"] = readings.get('temperature_c')
                            data["humidity"] = readings.get('humidity')
                            data["pressure"] = readings.get('pressure')
                            logger.info(f"🌡️  Temp: {data['temperature_f']:.1f}°F, Humidity: {data['humidity']:.1f}%, Pressure: {data['pressure']:.1f} hPa")
                    except Exception as e:
                        logger.error(f"Error reading BME280: {e}")
                        data["temperature_f"] = None
                        data["temperature_c"] = None
                        data["humidity"] = None
                        data["pressure"] = None
                
                # Read light sensor if available
                if light_sensor:
                    try:
                        light_level = light_sensor.read_light_level()
                        data["light_level"] = light_level
                        logger.info(f"💡 Light: {light_level:.1f} lux")
                    except Exception as e:
                        logger.error(f"Error reading light sensor: {e}")
                        data["light_level"] = None
                
                # Write to cache file (atomic write)
                temp_file = environmental_cache.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(data, f, indent=2)
                temp_file.replace(environmental_cache)
                
                logger.info(f"💾 Cache updated: {environmental_cache}")
                
                # Wait for next update
                time.sleep(update_interval)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(update_interval)
        
    except ImportError as e:
        logger.error(f"❌ Failed to import sensor modules: {e}")
        logger.error("Make sure all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("="*80)
        logger.info("🌡️  Environmental service stopped")
        logger.info("="*80)

if __name__ == "__main__":
    main()
