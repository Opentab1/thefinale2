#!/usr/bin/env python3
import asyncio
import json
import random
from pathlib import Path
from datetime import datetime

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'
DATA_DIR = Path('/opt/pulse/data/sensors')
BME_FILE = DATA_DIR / 'bme280.json'

async def has_sensor() -> bool:
    try:
        status = json.loads(STATUS_FILE.read_text())
        return bool(status.get('bme280'))
    except Exception:
        return False

async def read_loop():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Baseline temperature and humidity
    base_temp = 72.0
    base_humidity = 45.0
    
    while True:
        has_bme = await has_sensor()
        
        if has_bme:
            # Simulate realistic temperature variations
            hour = datetime.now().hour
            
            # Warmer during busy hours
            if 18 <= hour <= 23:
                temp = base_temp + random.uniform(2, 5)
                humidity = base_humidity + random.uniform(5, 15)
            # Moderate during day
            elif 12 <= hour < 18:
                temp = base_temp + random.uniform(0, 3)
                humidity = base_humidity + random.uniform(0, 10)
            # Cooler at night
            else:
                temp = base_temp - random.uniform(0, 2)
                humidity = base_humidity + random.uniform(-5, 5)
            
            # Add small variations
            temp += random.uniform(-0.5, 0.5)
            humidity += random.uniform(-2, 2)
            humidity = max(20, min(80, humidity))
            
            data = {
                'temperature': round(temp, 1),
                'humidity': round(humidity, 1),
                'pressure': round(1013.25 + random.uniform(-5, 5), 2),
                'timestamp': datetime.now().isoformat()
            }
            
            BME_FILE.write_text(json.dumps(data, indent=2))
            print(f"[BME280] Temp: {data['temperature']}°F, Humidity: {data['humidity']}%")
        else:
            # Write default values
            data = {
                'temperature': base_temp,
                'humidity': base_humidity,
                'pressure': 1013.25,
                'timestamp': datetime.now().isoformat()
            }
            BME_FILE.write_text(json.dumps(data, indent=2))
            print("[BME280] Sensor not available, using defaults")
        
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(read_loop())
    except KeyboardInterrupt:
        pass
