#!/usr/bin/env python3
import asyncio
import json
import random
from pathlib import Path
from datetime import datetime

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'
DATA_DIR = Path('/opt/pulse/data/sensors')
CAMERA_DIR = Path('/opt/pulse/data/camera')
PEOPLE_COUNT_FILE = DATA_DIR / 'people_count.txt'
CAMERA_STATUS_FILE = DATA_DIR / 'camera_active.txt'

async def has_camera() -> bool:
    try:
        status = json.loads(STATUS_FILE.read_text())
        return bool(status.get('camera'))
    except Exception:
        return False

async def main():
    # Ensure data directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CAMERA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Simulate people count that varies throughout the day
    base_count = 15
    
    while True:
        has_cam = await has_camera()
        
        # Write camera status
        CAMERA_STATUS_FILE.write_text('true' if has_cam else 'false')
        
        if has_cam:
            # Simulate realistic occupancy variations
            hour = datetime.now().hour
            
            # More people during evening hours (6pm-11pm)
            if 18 <= hour <= 23:
                people = random.randint(25, 65)
            # Moderate during afternoon (12pm-6pm)
            elif 12 <= hour < 18:
                people = random.randint(15, 40)
            # Fewer during morning/late night
            else:
                people = random.randint(5, 20)
            
            # Add some randomness
            people += random.randint(-3, 3)
            people = max(0, people)
            
            PEOPLE_COUNT_FILE.write_text(str(people))
            print(f"[Camera] Detected {people} people in venue")
        else:
            PEOPLE_COUNT_FILE.write_text('0')
            print("[Camera] Camera not available, count: 0")
        
        await asyncio.sleep(5)  # Update every 5 seconds

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
