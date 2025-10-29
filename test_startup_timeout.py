#!/usr/bin/env python3
"""
Test script to verify hub startup doesn't hang
"""

import sys
import os
import logging
import time

# Setup paths
sys.path.insert(0, '/workspace')
sys.path.insert(0, '/workspace/services')
os.chdir('/workspace')

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_startup():
    """Test that the hub can initialize without hanging"""
    
    logger.info("="*80)
    logger.info("TESTING PULSE HUB STARTUP (WITH TIMEOUT PROTECTION)")
    logger.info("="*80)
    
    start_time = time.time()
    
    try:
        # Import and create hub instance
        logger.info("\n1. Importing PulseHub...")
        from services.hub.main import PulseHub
        logger.info("✓ Import successful")
        
        # Try to initialize the hub
        logger.info("\n2. Initializing PulseHub...")
        logger.info("   (This should complete within 60 seconds even if hardware is missing)")
        
        hub = PulseHub()
        
        elapsed = time.time() - start_time
        logger.info(f"\n✓ Hub initialized successfully in {elapsed:.1f} seconds")
        
        # Check what got initialized
        status = hub.get_status()
        modules = status.get('modules', {})
        
        logger.info("\n" + "="*80)
        logger.info("INITIALIZATION RESULTS")
        logger.info("="*80)
        logger.info(f"Camera:       {'✓ Active' if modules.get('camera') else '✗ Inactive'}")
        logger.info(f"Microphone:   {'✓ Active' if modules.get('mic') else '✗ Inactive'}")
        logger.info(f"BME280:       {'✓ Active' if modules.get('bme280') else '✗ Inactive'}")
        logger.info(f"Light Sensor: {'✓ Active' if modules.get('light_sensor') else '✗ Inactive'}")
        logger.info(f"Pan/Tilt:     {'✓ Active' if modules.get('pan_tilt') else '✗ Inactive'}")
        logger.info("="*80)
        
        logger.info("\n✅ TEST PASSED - Hub initialized without hanging!")
        logger.info(f"Total time: {elapsed:.1f} seconds")
        
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"\n❌ TEST FAILED - Error after {elapsed:.1f} seconds")
        logger.error(f"Error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_startup()
    sys.exit(0 if success else 1)
