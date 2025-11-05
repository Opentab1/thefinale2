#!/usr/bin/env python3
"""
Pulse Camera Service - Standalone
Runs only the camera/people counter
Isolated from other services for fault tolerance
"""

import logging
import sys
import os
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
        
        # Keep running and log status periodically
        last_status_log = 0
        
        while True:
            time.sleep(30)
            
            current_time = time.time()
            if current_time - last_status_log >= 300:  # Log every 5 minutes
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
