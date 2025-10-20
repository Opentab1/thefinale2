#!/usr/bin/env python3
"""
Pulse System Runner
Runs both the Hub and Dashboard API in the same process for debugging
"""

import logging
import sys
import os
from pathlib import Path
from threading import Thread
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
    if (pd / 'services' / 'hub' / 'main.py').exists():
        PULSE_ROOT = pd
        break

if PULSE_ROOT is None:
    print("ERROR: Cannot find Pulse installation!")
    print(f"Searched: {[str(p) for p in PULSE_DIRS]}")
    sys.exit(1)

print(f"Found Pulse at: {PULSE_ROOT}")

# Add paths
sys.path.insert(0, str(PULSE_ROOT))
sys.path.insert(0, str(PULSE_ROOT / 'services'))
os.chdir(str(PULSE_ROOT))

# Setup detailed logging to console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def run_hub():
    """Run the hub service"""
    logger.info("="*80)
    logger.info("STARTING PULSE HUB")
    logger.info("="*80)
    
    try:
        from services.hub.main import PulseHub
        
        hub = PulseHub()
        hub.start()
        
        # Store hub instance for dashboard
        import dashboard.api.server as dashboard_server
        dashboard_server.set_hub_instance(hub)
        
        # Keep hub running
        while True:
            time.sleep(60)
            status = hub.get_status()
            
            logger.info("="*80)
            logger.info("HUB STATUS UPDATE")
            logger.info("="*80)
            logger.info(f"Running: {status['running']}")
            logger.info(f"Occupancy: {status['sensors'].get('occupancy', 0)}")
            logger.info(f"Temperature: {status['sensors'].get('temperature_f', 'N/A')}°F")
            logger.info(f"Humidity: {status['sensors'].get('humidity', 'N/A')}%")
            logger.info(f"Light Level: {status['sensors'].get('light_level', 'N/A')} lux")
            logger.info(f"Noise Level: {status['sensors'].get('noise_db', 'N/A')} dB")
            
            song = status['sensors'].get('current_song', {})
            if song and song.get('title') not in (None, 'Unknown'):
                logger.info(f"Now Playing: {song.get('title')} - {song.get('artist')}")
            
            logger.info("="*80)
            
    except Exception as e:
        logger.error(f"Hub error: {e}", exc_info=True)

def run_dashboard():
    """Run the dashboard API server"""
    # Give hub time to start first
    time.sleep(5)
    
    logger.info("="*80)
    logger.info("STARTING DASHBOARD API SERVER")
    logger.info("="*80)
    
    try:
        from dashboard.api.server import run_server
        run_server(host='0.0.0.0', port=8080, debug=False)
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)

def main():
    """Main entry point"""
    logger.info("\n" + "="*80)
    logger.info("PULSE SYSTEM - INTEGRATED STARTUP")
    logger.info("="*80)
    logger.info("Hub + Dashboard running in single process")
    logger.info("Dashboard will be available at: http://localhost:8080")
    logger.info("="*80 + "\n")
    
    # Create log directory
    os.makedirs("/var/log/pulse", exist_ok=True)
    os.makedirs("/opt/pulse/data", exist_ok=True)
    
    # Start hub in separate thread
    hub_thread = Thread(target=run_hub, daemon=True)
    hub_thread.start()
    
    # Start dashboard in main thread (blocks)
    try:
        run_dashboard()
    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("SHUTTING DOWN PULSE SYSTEM")
        logger.info("="*80)
        sys.exit(0)

if __name__ == "__main__":
    main()
