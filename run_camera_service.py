#!/usr/bin/env python3
"""
Pulse Camera Service - Standalone
Runs only the camera/people counter
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
    """Main entry point for camera service"""
    logger.info("="*80)
    logger.info("📷 PULSE CAMERA SERVICE - STARTING")
    logger.info("="*80)
    logger.info("People Counter: Continuous detection")
    logger.info("="*80)
    
    # Create cache file path
    data_dir = Path("/opt/pulse/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    people_cache = data_dir / "people_cache.json"
    logger.info(f"📁 Cache file: {people_cache}")
    
    try:
        from services.sensors.camera_people import PeopleCounter
        
        # Initialize camera
        logger.info("Initializing camera/people counter...")
        
        # Check for AI HAT
        use_ai_hat = os.path.exists("/dev/hailo0")
        logger.info(f"AI HAT: {'Detected' if use_ai_hat else 'Not found (using CPU fallback)'}")
        
        people_counter = PeopleCounter(use_ai_hat=use_ai_hat)
        logger.info("✅ People counter initialized")
        
        # Start counting
        people_counter.start_counting()
        logger.info("✅ People counter started")
        
        logger.info("="*80)
        logger.info("🎉 CAMERA SERVICE RUNNING")
        logger.info("="*80)
        
        # Keep running, write cache files, and log status periodically
        last_status_log = 0
        last_cache_write = 0
        
        while True:
            time.sleep(2)  # Check every 2 seconds for cache updates
            
            current_time = time.time()
            
            # Write cache file every 5 seconds
            if current_time - last_cache_write >= 5:
                try:
                    # Get current data
                    current_count = people_counter.get_current_count()
                    stats = people_counter.get_traffic_stats()
                    
                    # Write people cache
                    cache_data = {
                        "occupancy": current_count,
                        "entries": stats.get('entry_count', 0),
                        "exits": stats.get('exit_count', 0),
                        "timestamp": current_time
                    }
                    
                    with open(people_cache, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                    
                    logger.debug(f"📁 Cache updated: occupancy={current_count}, entries={cache_data['entries']}, exits={cache_data['exits']}")
                    last_cache_write = current_time
                    
                except Exception as cache_err:
                    logger.error(f"Error writing cache file: {cache_err}")
            
            # Log status every 5 minutes
            if current_time - last_status_log >= 300:
                # Get current count
                current_count = people_counter.get_current_count()
                stats = people_counter.get_traffic_stats()
                
                logger.info("="*80)
                logger.info("📷 CAMERA SERVICE STATUS")
                logger.info("="*80)
                logger.info(f"👥 Current occupancy: {current_count}")
                logger.info(f"📊 Total entries: {stats.get('entry_count', 0)}")
                logger.info(f"📊 Total exits: {stats.get('exit_count', 0)}")
                logger.info("="*80)
                
                last_status_log = current_time
        
    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("🛑 CAMERA SERVICE SHUTTING DOWN")
        logger.info("="*80)
        
        # Cleanup
        try:
            if 'people_counter' in locals():
                people_counter.stop_counting()
                logger.info("✅ People counter stopped")
        except:
            pass
        
        logger.info("✅ Camera service stopped cleanly")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in camera service: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
