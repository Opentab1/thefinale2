#!/usr/bin/env python3
"""
Test script to verify song detector and database stability fixes
Run this for several hours to ensure components stay alive
"""

import logging
import time
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.sensors.mic_song_detect import AudioMonitor
from services.storage.db import PulseDB
from services.sensors.system_watchdog import SystemWatchdog

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_audio_monitor_stability(duration_minutes: int = 60):
    """Test audio monitor stability for extended period"""
    logger.info("="*80)
    logger.info(f"TESTING AUDIO MONITOR STABILITY FOR {duration_minutes} MINUTES")
    logger.info("="*80)
    
    try:
        monitor = AudioMonitor()
        monitor.start_monitoring()
        
        start_time = time.time()
        last_report = start_time
        iteration = 0
        
        while (time.time() - start_time) < (duration_minutes * 60):
            time.sleep(10)
            iteration += 1
            
            # Get stats
            stats = monitor.get_stats()
            current_db = stats.get('current_db', 0)
            song = stats.get('current_song', {})
            song_stats = stats.get('song_detection', {})
            
            # Check for failures
            age_since_db = time.time() - monitor._last_db_ts if monitor._last_db_ts else 999
            
            # Report every 5 minutes
            if (time.time() - last_report) >= 300:
                elapsed = (time.time() - start_time) / 60
                logger.info("="*80)
                logger.info(f"📊 STATUS REPORT - {elapsed:.1f} minutes elapsed")
                logger.info(f"  🔊 Current dB: {current_db:.1f}")
                logger.info(f"  ⏱️  Last dB reading: {age_since_db:.1f}s ago")
                logger.info(f"  🎵 Current song: {song.get('title', 'Unknown')}")
                logger.info(f"  📈 Song detection errors: {song_stats.get('last_error', 'None')}")
                logger.info(f"  ✅ Iterations: {iteration}")
                logger.info("="*80)
                last_report = time.time()
            
            # Check for stuck state
            if age_since_db > 45:
                logger.error(f"⚠️ PROBLEM DETECTED: No dB reading for {age_since_db:.1f}s!")
                logger.error("  Audio monitor may be stuck - this should have been caught by watchdog")
                return False
        
        logger.info("="*80)
        logger.info("✅ AUDIO MONITOR STABILITY TEST PASSED")
        logger.info(f"  Ran for {duration_minutes} minutes without failures")
        logger.info("="*80)
        
        monitor.cleanup()
        return True
        
    except Exception as e:
        logger.error(f"❌ AUDIO MONITOR TEST FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_database_stability(num_operations: int = 1000):
    """Test database connection pool stability"""
    logger.info("="*80)
    logger.info(f"TESTING DATABASE STABILITY ({num_operations} OPERATIONS)")
    logger.info("="*80)
    
    try:
        db = PulseDB()
        
        start_time = time.time()
        failures = 0
        
        for i in range(num_operations):
            try:
                # Perform various operations
                if i % 5 == 0:
                    db.log_environment(
                        temperature=70.0 + (i % 10),
                        humidity=45.0,
                        noise_level=60.0
                    )
                elif i % 5 == 1:
                    db.log_occupancy("TestZone", i % 20)
                elif i % 5 == 2:
                    db.get_latest_environment()
                elif i % 5 == 3:
                    db.log_music("Test Song", "Test Artist", 50)
                else:
                    db.log_automation("test", "action", "reason")
                
                # Report progress
                if (i + 1) % 100 == 0:
                    pool_stats = db.get_pool_stats()
                    elapsed = time.time() - start_time
                    ops_per_sec = (i + 1) / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"  📊 Progress: {i+1}/{num_operations} ops "
                        f"({ops_per_sec:.1f} ops/sec) | "
                        f"Pool: {pool_stats['available_connections']}/{pool_stats['pool_size']} | "
                        f"Failures: {failures}"
                    )
                
            except Exception as e:
                failures += 1
                logger.error(f"  ⚠️ Operation {i+1} failed: {e}")
                if failures > 10:
                    logger.error(f"  ❌ Too many failures ({failures}), aborting test")
                    return False
        
        elapsed = time.time() - start_time
        logger.info("="*80)
        logger.info("✅ DATABASE STABILITY TEST PASSED")
        logger.info(f"  Completed {num_operations} operations in {elapsed:.1f}s")
        logger.info(f"  Average: {num_operations/elapsed:.1f} ops/sec")
        logger.info(f"  Failures: {failures}")
        logger.info(f"  Pool stats: {db.get_pool_stats()}")
        logger.info("="*80)
        
        db.close_all_connections()
        return True
        
    except Exception as e:
        logger.error(f"❌ DATABASE TEST FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_watchdog_functionality():
    """Test system watchdog monitoring"""
    logger.info("="*80)
    logger.info("TESTING SYSTEM WATCHDOG FUNCTIONALITY")
    logger.info("="*80)
    
    try:
        watchdog = SystemWatchdog(check_interval=5.0)
        
        # Create dummy components
        test_healthy = True
        
        def check_dummy():
            return test_healthy
        
        def restart_dummy():
            logger.info("  🔄 Dummy component restarted")
        
        watchdog.register_component("dummy", check_dummy, restart_dummy, 
                                    check_interval=5.0, failure_threshold=2)
        watchdog.start()
        
        # Let it run for 30 seconds (should be healthy)
        logger.info("  ⏱️  Running for 30 seconds (healthy state)...")
        time.sleep(30)
        
        status = watchdog.get_status()
        dummy_stats = status['components']['dummy']
        
        if dummy_stats['status'] != 'healthy':
            logger.error(f"  ❌ Expected healthy, got: {dummy_stats['status']}")
            return False
        
        logger.info(f"  ✅ Component healthy: {dummy_stats}")
        
        # Make it unhealthy
        logger.info("  ⚠️  Simulating component failure...")
        test_healthy = False
        
        # Wait for watchdog to detect and restart (should take ~10-15 seconds)
        time.sleep(20)
        
        status = watchdog.get_status()
        dummy_stats = status['components']['dummy']
        
        if dummy_stats['total_restarts'] < 1:
            logger.error(f"  ❌ Watchdog did not restart component: {dummy_stats}")
            return False
        
        logger.info(f"  ✅ Watchdog detected failure and restarted: {dummy_stats}")
        
        watchdog.stop()
        
        logger.info("="*80)
        logger.info("✅ WATCHDOG FUNCTIONALITY TEST PASSED")
        logger.info("="*80)
        return True
        
    except Exception as e:
        logger.error(f"❌ WATCHDOG TEST FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all stability tests"""
    logger.info("="*80)
    logger.info("PULSE STABILITY TEST SUITE")
    logger.info("="*80)
    
    tests = [
        ("Watchdog Functionality", test_watchdog_functionality),
        ("Database Stability (1000 ops)", lambda: test_database_stability(1000)),
        ("Audio Monitor Stability (5 min)", lambda: test_audio_monitor_stability(5)),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n\n🧪 Starting test: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results[test_name] = False
        
        time.sleep(2)  # Brief pause between tests
    
    # Print summary
    logger.info("\n\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"  {status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n🎉 ALL TESTS PASSED - SYSTEM IS STABLE!")
    else:
        logger.error("\n⚠️ SOME TESTS FAILED - CHECK LOGS ABOVE")
    
    logger.info("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
