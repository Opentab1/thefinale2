#!/usr/bin/env python3
"""
Pulse Audio Service - Standalone
Runs only the audio detectors (decibel + song detection)
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
    """Main entry point for audio service"""
    logger.info("="*80)
    logger.info("🎤 PULSE AUDIO SERVICE - STARTING")
    logger.info("="*80)
    logger.info("Decibel Reader: Every 10 seconds")
    logger.info("Song Detector: Every 60 seconds")
    logger.info("="*80)
    
    # Create cache directory
    cache_dir = Path("/opt/pulse/data")
    cache_dir.mkdir(parents=True, exist_ok=True)
    decibel_cache = cache_dir / "decibel_cache.json"
    song_cache = cache_dir / "song_cache.json"
    song_health = cache_dir / "song_health.json"
    logger.info(f"📁 Cache files: {decibel_cache}, {song_cache}, {song_health}")
    
    try:
        from services.sensors.simple_decibel_detector import DecibelDetector
        from services.sensors.simple_song_detector import SongDetector
        
        # Initialize detectors
        logger.info("Initializing audio detectors...")
        
        decibel_detector = DecibelDetector(enabled=True, update_interval=10)
        logger.info("✅ Decibel detector initialized")
        
        song_detector = SongDetector(enabled=True, detection_interval=60)
        logger.info("✅ Song detector initialized")
        
        logger.info("="*80)
        logger.info("🎉 AUDIO SERVICE RUNNING")
        logger.info("="*80)
        
        # Keep running and log status periodically
        last_status_log = 0
        
        while True:
            time.sleep(30)
            
            current_time = time.time()
            
            # Get latest readings
            db_reading = decibel_detector.get_latest_reading()
            song_info = song_detector.get_latest_song()
            
            # Write cache files every loop (every 30 seconds)
            try:
                with open(decibel_cache, 'w') as f:
                    json.dump(db_reading, f, indent=2)
                with open(song_cache, 'w') as f:
                    json.dump(song_info, f, indent=2)
                with open(song_health, 'w') as f:
                    json.dump(song_detector.get_health_status(), f, indent=2)
            except Exception as e:
                logger.error(f"Error writing cache files: {e}")
            
            # Log status every 5 minutes
            if current_time - last_status_log >= 300:
                
                logger.info("="*80)
                logger.info("🎤 AUDIO SERVICE STATUS")
                logger.info("="*80)
                logger.info(f"🔊 Decibel: {db_reading.get('db_value', 0):.1f} dB")
                
                if song_info.get('title') != 'Unknown':
                    logger.info(f"🎵 Song: {song_info.get('title')} - {song_info.get('artist')}")
                else:
                    logger.info("🎵 Song: None detected")
                health = song_detector.get_health_status()
                logger.info(
                    "🎵 Song health → provider=%s status=%s failures=%s last_error=%s",
                    health.get('provider'),
                    health.get('status'),
                    health.get('failure_streak'),
                    health.get('last_error'),
                )
                
                logger.info(f"✅ Decibel thread: {'Running' if decibel_detector.detection_thread and decibel_detector.detection_thread.is_alive() else 'Dead'}")
                logger.info(f"✅ Song thread: {'Running' if song_detector.detection_thread and song_detector.detection_thread.is_alive() else 'Dead'}")
                logger.info("="*80)
                
                last_status_log = current_time
        
    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("🛑 AUDIO SERVICE SHUTTING DOWN")
        logger.info("="*80)
        
        # Cleanup
        try:
            if 'decibel_detector' in locals():
                decibel_detector.stop()
                logger.info("✅ Decibel detector stopped")
        except:
            pass
        
        try:
            if 'song_detector' in locals():
                song_detector.stop()
                logger.info("✅ Song detector stopped")
        except:
            pass
        
        logger.info("✅ Audio service stopped cleanly")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in audio service: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
