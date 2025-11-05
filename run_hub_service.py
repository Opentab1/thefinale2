#!/usr/bin/env python3
"""
Pulse Hub Service - Standalone
Runs hub coordination, dashboard, and environmental sensors
(Audio and Camera run as separate services)
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

# Disable audio and camera in hub (they run as separate services)
os.environ['PULSE_DISABLE_AUDIO'] = '1'
os.environ['PULSE_DISABLE_CAMERA'] = '1'

def run_hub():
    """Run the hub service"""
    logger.info("="*80)
    logger.info("🏠 STARTING PULSE HUB")
    logger.info("="*80)
    logger.info("Note: Audio and Camera run as separate services")
    logger.info("This service handles:")
    logger.info("  - Temperature/Humidity (BME280)")
    logger.info("  - Light Level")
    logger.info("  - Database logging")
    logger.info("  - Dashboard API")
    logger.info("  - Smart home controls")
    logger.info("="*80)
    
    try:
        from services.hub.main import PulseHub
        
        hub = PulseHub()
        hub.start()
        
        # Store hub instance for dashboard
        import dashboard.api.server as dashboard_server
        dashboard_server.set_hub_instance(hub)
        
        # Keep hub running with status updates
        while True:
            time.sleep(60)
            status = hub.get_status()
            
            logger.info("="*80)
            logger.info("🏠 HUB STATUS UPDATE")
            logger.info("="*80)
            logger.info(f"Running: {status['running']}")
            logger.info(f"Temperature: {status['sensors'].get('temperature_f', 'N/A')}°F")
            logger.info(f"Humidity: {status['sensors'].get('humidity', 'N/A')}%")
            logger.info(f"Light Level: {status['sensors'].get('light_level', 'N/A')} lux")
            logger.info("="*80)
            
    except Exception as e:
        logger.error(f"Hub error: {e}", exc_info=True)
        raise

def run_dashboard():
    """Run the dashboard API server"""
    # Give hub time to start first
    time.sleep(5)
    
    logger.info("="*80)
    logger.info("🌐 STARTING DASHBOARD API SERVER")
    logger.info("="*80)
    logger.info("Dashboard available at: http://0.0.0.0:8080")
    logger.info("="*80)
    
    try:
        from dashboard.api.server import run_server
        run_server(host='0.0.0.0', port=8080, debug=False)
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        raise

def main():
    """Main entry point"""
    logger.info("\n" + "="*80)
    logger.info("🏠 PULSE HUB SERVICE - INTEGRATED STARTUP")
    logger.info("="*80)
    logger.info("Hub + Dashboard + Environmental Sensors")
    logger.info("(Audio and Camera are separate services)")
    logger.info("="*80 + "\n")
    
    # Create necessary directories
    os.makedirs("/var/log/pulse", exist_ok=True)
    os.makedirs("/opt/pulse/data", exist_ok=True)
    
    # Start hub in separate thread
    hub_thread = Thread(target=run_hub, daemon=True, name="HubThread")
    hub_thread.start()
    
    # Start dashboard in main thread (blocks)
    try:
        run_dashboard()
    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("🛑 SHUTTING DOWN HUB SERVICE")
        logger.info("="*80)
        sys.exit(0)

if __name__ == "__main__":
    main()
