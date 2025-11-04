#!/usr/bin/env python3
"""
Test script to verify audio monitoring health and continuous operation
"""

import sys
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from services.sensors.mic_song_detect import AudioMonitor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_audio_health_continuous(duration_minutes=10, check_interval_seconds=15):
    """
    Test audio monitoring for continuous operation
    
    Args:
        duration_minutes: How long to run the test
        check_interval_seconds: How often to check health
    """
    logger.info("="*80)
    logger.info(f"AUDIO HEALTH TEST - Running for {duration_minutes} minutes")
    logger.info("="*80)
    
    try:
        # Initialize monitor
        logger.info("Initializing AudioMonitor...")
        monitor = AudioMonitor()
        
        # Start monitoring
        logger.info("Starting audio monitoring...")
        monitor.start_monitoring()
        
        # Wait a bit for initialization
        time.sleep(3)
        
        # Run health checks
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        check_count = 0
        failures = []
        
        logger.info("\nStarting health checks...")
        logger.info("-" * 80)
        
        while time.time() < end_time:
            check_count += 1
            elapsed_minutes = (time.time() - start_time) / 60
            
            # Get health status
            health = monitor.get_health_status()
            
            # Log health status
            logger.info(f"\n[Check #{check_count} at {elapsed_minutes:.1f} minutes]")
            logger.info(f"  Monitoring Active: {health['monitoring_active']}")
            logger.info(f"  Thread Alive: {health['monitoring_thread_alive']}")
            logger.info(f"  Stream Healthy: {health['stream_healthy']}")
            logger.info(f"  Last Audio Data: {health['last_audio_data_seconds_ago']}s ago")
            logger.info(f"  Last Activity: {health['last_activity_seconds_ago']}s ago")
            logger.info(f"  Detection Loop Healthy: {health['detection_loop_healthy']}")
            logger.info(f"  Current dB: {health['current_db']:.1f}")
            logger.info(f"  Peak dB: {health['peak_db']:.1f}")
            
            # Check for issues
            issues = []
            
            if not health['monitoring_active']:
                issues.append("Monitoring not active")
            
            if not health['monitoring_thread_alive']:
                issues.append("Monitoring thread dead")
            
            if health['last_audio_data_seconds_ago'] and health['last_audio_data_seconds_ago'] > 60:
                issues.append(f"No audio data for {health['last_audio_data_seconds_ago']:.1f}s")
            
            if health['song_detector_enabled'] and not health['detection_loop_healthy']:
                issues.append("Detection loop unhealthy")
            
            if issues:
                logger.error(f"  ❌ ISSUES DETECTED: {', '.join(issues)}")
                failures.append({
                    'time': elapsed_minutes,
                    'check': check_count,
                    'issues': issues,
                    'health': health
                })
            else:
                logger.info(f"  ✅ All health checks passed")
            
            # Get current song if available
            song = monitor.get_current_song()
            if song and song.get('title') not in (None, 'Unknown'):
                logger.info(f"  🎵 Current Song: {song['title']} - {song['artist']}")
            
            logger.info("-" * 80)
            
            # Wait for next check
            time.sleep(check_interval_seconds)
        
        # Final summary
        total_minutes = (time.time() - start_time) / 60
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Runtime: {total_minutes:.1f} minutes")
        logger.info(f"Total Health Checks: {check_count}")
        logger.info(f"Failed Checks: {len(failures)}")
        
        if failures:
            logger.error("\n❌ TEST FAILED - Issues detected:")
            for failure in failures:
                logger.error(f"  - At {failure['time']:.1f} min (check #{failure['check']}): {', '.join(failure['issues'])}")
        else:
            logger.info("\n✅ TEST PASSED - No issues detected!")
            logger.info("Audio monitoring ran continuously for the entire duration")
        
        # Cleanup
        logger.info("\nCleaning up...")
        monitor.cleanup()
        
        return len(failures) == 0
        
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user")
        if 'monitor' in locals():
            monitor.cleanup()
        return False
    except Exception as e:
        logger.error(f"\n\nTest failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if 'monitor' in locals():
            monitor.cleanup()
        return False


def test_quick_health_check():
    """Quick 30-second health check"""
    logger.info("Running quick health check (30 seconds)...")
    
    try:
        monitor = AudioMonitor()
        monitor.start_monitoring()
        time.sleep(5)  # Let it initialize
        
        health = monitor.get_health_status()
        
        logger.info("\nHealth Status:")
        for key, value in health.items():
            logger.info(f"  {key}: {value}")
        
        # Check critical metrics
        success = True
        if not health['monitoring_thread_alive']:
            logger.error("❌ Monitoring thread is not alive")
            success = False
        
        if health['last_audio_data_seconds_ago'] and health['last_audio_data_seconds_ago'] > 10:
            logger.error(f"❌ No audio data for {health['last_audio_data_seconds_ago']}s")
            success = False
        
        if success:
            logger.info("\n✅ Quick health check PASSED")
        else:
            logger.error("\n❌ Quick health check FAILED")
        
        monitor.cleanup()
        return success
        
    except Exception as e:
        logger.error(f"Quick health check failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test audio monitoring health")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in minutes (default: 10)")
    parser.add_argument("--interval", type=int, default=15, help="Health check interval in seconds (default: 15)")
    parser.add_argument("--quick", action="store_true", help="Run quick 30-second test")
    
    args = parser.parse_args()
    
    if args.quick:
        success = test_quick_health_check()
    else:
        success = test_audio_health_continuous(
            duration_minutes=args.duration,
            check_interval_seconds=args.interval
        )
    
    sys.exit(0 if success else 1)
