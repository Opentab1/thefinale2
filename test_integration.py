#!/usr/bin/env python3
"""
Test script to verify AI people counter and song detection integration
"""

import logging
import sys
import os
import time

# Add pulse to path
sys.path.insert(0, '/workspace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_person_detector():
    """Test person detector initialization"""
    logger.info("Testing person detector...")
    try:
        from services.sensors.detector.person_detector import PersonDetector
        detector = PersonDetector(confidence_threshold=0.5, model_type="hog")
        logger.info("✓ Person detector initialized successfully")
        logger.info(f"  Available models: {list(detector.models.keys())}")
        logger.info(f"  Current model: {detector.model_type}")
        detector.cleanup()
        return True
    except Exception as e:
        logger.error(f"✗ Person detector failed: {e}")
        return False

def test_person_tracker():
    """Test person tracker initialization"""
    logger.info("Testing person tracker...")
    try:
        from services.sensors.tracker.person_tracker import PersonTracker
        tracker = PersonTracker(confidence_threshold=0.5, min_detection_frames=5)
        logger.info("✓ Person tracker initialized successfully")
        logger.info(f"  Entry count: {tracker.entry_count}")
        logger.info(f"  Exit count: {tracker.exit_count}")
        return True
    except Exception as e:
        logger.error(f"✗ Person tracker failed: {e}")
        return False

def test_people_counter():
    """Test integrated people counter"""
    logger.info("Testing integrated people counter...")
    try:
        from services.sensors.camera_people import PeopleCounter
        counter = PeopleCounter(use_ai_hat=False, model_type="hog")
        logger.info("✓ People counter initialized successfully")
        logger.info(f"  Model type: {counter.model_type}")
        logger.info(f"  Confidence threshold: {counter.confidence_threshold}")
        stats = counter.get_traffic_stats()
        logger.info(f"  Initial stats: {stats}")
        counter.stop_counting()
        return True
    except Exception as e:
        logger.error(f"✗ People counter failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_song_detector():
    """Test song detector initialization"""
    logger.info("Testing song detector...")
    try:
        from services.sensors.song_detector import SongDetector
        detector = SongDetector(enabled=True, detection_interval=60)
        logger.info("✓ Song detector initialized successfully")
        logger.info(f"  Enabled: {detector.enabled}")
        song = detector.get_latest_song()
        logger.info(f"  Latest song: {song}")
        detector.stop()
        return True
    except Exception as e:
        logger.error(f"✗ Song detector failed: {e}")
        return False

def test_audio_monitor():
    """Test integrated audio monitor"""
    logger.info("Testing integrated audio monitor...")
    try:
        from services.sensors.mic_song_detect import AudioMonitor
        # Don't start monitoring, just initialize
        monitor = AudioMonitor()
        logger.info("✓ Audio monitor initialized successfully")
        logger.info(f"  Sample rate: {monitor.sample_rate}")
        logger.info(f"  Device index: {monitor.device_index}")
        stats = monitor.get_stats()
        logger.info(f"  Initial stats: {stats}")
        monitor.cleanup()
        return True
    except Exception as e:
        logger.error(f"✗ Audio monitor failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    logger.info("="*60)
    logger.info("Pulse 1.0 - AI Integration Test Suite")
    logger.info("Testing party_box integration")
    logger.info("="*60)
    
    results = {
        "Person Detector": test_person_detector(),
        "Person Tracker": test_person_tracker(),
        "People Counter (Integrated)": test_people_counter(),
        "Song Detector": test_song_detector(),
        "Audio Monitor (Integrated)": test_audio_monitor(),
    }
    
    logger.info("="*60)
    logger.info("Test Results Summary:")
    logger.info("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info("="*60)
    
    all_passed = all(results.values())
    if all_passed:
        logger.info("All tests passed! Integration successful.")
        return 0
    else:
        logger.error("Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
