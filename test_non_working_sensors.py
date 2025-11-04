#!/usr/bin/env python3
"""
Diagnostic script to test temperature, dB, and song detection sensors
Run this on your RPi to see what's happening with these sensors
"""

import sys
import time
import logging
from pathlib import Path

# Add services to path
sys.path.insert(0, str(Path(__file__).parent / 'services'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_bme280():
    """Test BME280 temperature sensor"""
    logger.info("="*80)
    logger.info("TESTING BME280 TEMPERATURE SENSOR")
    logger.info("="*80)
    
    try:
        from sensors.bme280_reader import BME280Reader
        
        logger.info("Initializing BME280...")
        reader = BME280Reader(address=0x76)
        
        logger.info("Testing direct read...")
        data = reader.read_sensor()
        logger.info(f"Direct read result: {data}")
        
        if data and data.get("temperature_f") is not None:
            logger.info(f"✅ BME280 WORKING: {data['temperature_f']:.1f}°F, {data['humidity']:.1f}%")
            
            logger.info("Testing cached values...")
            reader.start_reading(interval=5)
            time.sleep(6)
            
            cached = reader.get_all_readings()
            logger.info(f"Cached values: {cached}")
            
            if cached.get("temperature_f") is not None:
                logger.info(f"✅ Cached values WORKING: {cached['temperature_f']:.1f}°F")
            else:
                logger.error("❌ Cached values are None - background thread may not be working")
            
            reader.stop_reading()
            return True
        else:
            logger.error("❌ BME280 read returned no data")
            return False
            
    except Exception as e:
        logger.error(f"❌ BME280 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_audio_monitor():
    """Test AudioMonitor for dB and song detection"""
    logger.info("\n" + "="*80)
    logger.info("TESTING AUDIO MONITOR (dB + Song Detection)")
    logger.info("="*80)
    
    try:
        from sensors.mic_song_detect import AudioMonitor
        
        logger.info("Initializing AudioMonitor...")
        monitor = AudioMonitor()
        
        logger.info("Starting audio monitoring...")
        monitor.start_monitoring()
        
        # Wait for audio stream to start
        logger.info("Waiting 10 seconds for audio stream to initialize...")
        time.sleep(10)
        
        # Check dB
        logger.info("Checking dB level...")
        db = monitor.get_current_db()
        logger.info(f"Current dB: {db}")
        
        if db > 0:
            logger.info(f"✅ dB READER WORKING: {db:.1f} dB")
        else:
            logger.warning(f"⚠️  dB is 0 - may need audio input or device not detected")
        
        # Check song detection
        logger.info("Checking song detection...")
        song = monitor.get_current_song()
        logger.info(f"Current song: {song}")
        
        if song and song.get("title") not in (None, "Unknown"):
            logger.info(f"✅ SONG DETECTION WORKING: {song['title']} - {song['artist']}")
        else:
            logger.warning("⚠️  No song detected yet - this may be normal if no music is playing")
            logger.info("   Song detection runs every 30 seconds, checking ShazamIO availability...")
            
            # Check if ShazamIO is available
            try:
                from shazamio import Shazam
                logger.info("✅ ShazamIO library is available")
            except ImportError:
                logger.error("❌ ShazamIO not installed - song detection will not work")
                logger.error("   Install with: pip install shazamio aiohttp")
        
        # Wait a bit more and check again
        logger.info("Waiting 35 more seconds for song detection attempt...")
        time.sleep(35)
        
        song2 = monitor.get_current_song()
        if song2 and song2.get("title") not in (None, "Unknown"):
            logger.info(f"✅ Song detected after wait: {song2['title']} - {song2['artist']}")
        else:
            logger.warning("⚠️  Still no song detected - may need music playing or ShazamIO issue")
        
        # Get stats
        stats = monitor.get_stats()
        logger.info(f"\nAudio Stats: {stats}")
        
        monitor.stop_monitoring()
        monitor.cleanup()
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ AUDIO MONITOR FAILED - Missing dependencies: {e}")
        logger.error("   Install with: pip install numpy pyaudio sounddevice")
        return False
    except Exception as e:
        logger.error(f"❌ AUDIO MONITOR FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_hub_integration():
    """Test how hub collects sensor data"""
    logger.info("\n" + "="*80)
    logger.info("TESTING HUB SENSOR DATA COLLECTION")
    logger.info("="*80)
    
    try:
        from hub.main import PulseHub
        
        logger.info("Initializing hub...")
        hub = PulseHub()
        
        logger.info("Starting hub...")
        hub.start()
        
        # Wait for sensors to initialize
        logger.info("Waiting 15 seconds for sensors to initialize...")
        time.sleep(15)
        
        # Get sensor data
        logger.info("Collecting sensor data from hub...")
        sensor_data = hub._collect_sensor_data()
        
        logger.info("\nSensor Data from Hub:")
        logger.info(f"  Temperature: {sensor_data.get('temperature_f')}")
        logger.info(f"  Humidity: {sensor_data.get('humidity')}")
        logger.info(f"  Noise dB: {sensor_data.get('noise_db')}")
        logger.info(f"  Song: {sensor_data.get('current_song')}")
        logger.info(f"  Light: {sensor_data.get('light_level')}")
        logger.info(f"  Occupancy: {sensor_data.get('occupancy')}")
        
        # Check what's None
        issues = []
        if sensor_data.get('temperature_f') is None:
            issues.append("Temperature is None")
        if sensor_data.get('noise_db') is None or sensor_data.get('noise_db') == 0:
            issues.append("Noise dB is None or 0")
        if not sensor_data.get('current_song') or sensor_data.get('current_song', {}).get('title') in (None, 'Unknown'):
            issues.append("Song detection not working")
        
        if issues:
            logger.warning(f"\n⚠️  Issues found: {', '.join(issues)}")
        else:
            logger.info("\n✅ All sensors returning data!")
        
        hub.stop()
        return len(issues) == 0
        
    except Exception as e:
        logger.error(f"❌ HUB TEST FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting sensor diagnostics...")
    logger.info("This will test temperature, dB reader, and song detection\n")
    
    results = {}
    
    # Test each sensor
    results['bme280'] = test_bme280()
    results['audio'] = test_audio_monitor()
    results['hub'] = test_hub_integration()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("="*80)
    logger.info(f"BME280 (Temperature): {'✅ PASS' if results['bme280'] else '❌ FAIL'}")
    logger.info(f"Audio Monitor (dB + Song): {'✅ PASS' if results['audio'] else '❌ FAIL'}")
    logger.info(f"Hub Integration: {'✅ PASS' if results['hub'] else '❌ FAIL'}")
    logger.info("="*80)
