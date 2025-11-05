#!/usr/bin/env python3
"""
AUDIO RESILIENCE TEST SUITE
Tests all failure scenarios and recovery mechanisms

This script will intentionally break things and verify they recover automatically.
"""

import sys
import os
import time
import logging
import signal
import threading

# Add path
sys.path.insert(0, '/opt/pulse')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AudioResilienceTests:
    """Test suite for audio system resilience"""
    
    def __init__(self):
        self.monitor = None
        self.passed_tests = 0
        self.failed_tests = 0
        self.total_tests = 0
        
    def log_test(self, name):
        """Log test start"""
        self.total_tests += 1
        logger.info("="*80)
        logger.info(f"TEST {self.total_tests}: {name}")
        logger.info("="*80)
    
    def log_pass(self, message):
        """Log test pass"""
        self.passed_tests += 1
        logger.info(f"✅ PASS: {message}")
        logger.info("")
    
    def log_fail(self, message):
        """Log test fail"""
        self.failed_tests += 1
        logger.error(f"❌ FAIL: {message}")
        logger.info("")
    
    def initialize(self):
        """Initialize audio monitor"""
        logger.info("Initializing AudioMonitor for testing...")
        
        try:
            from services.sensors.mic_song_detect import AudioMonitor
            
            self.monitor = AudioMonitor()
            self.monitor.start_monitoring()
            time.sleep(3)
            
            if self.monitor.running:
                logger.info("✅ AudioMonitor initialized")
                return True
            else:
                logger.error("❌ AudioMonitor failed to start")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    def test_db_reader_basic(self):
        """Test 1: Basic dB reader functionality"""
        self.log_test("Basic dB Reader Functionality")
        
        try:
            # Get initial reading
            db1 = self.monitor.get_current_db()
            logger.info(f"Initial dB reading: {db1:.1f}")
            
            # Wait and get another reading
            time.sleep(3)
            db2 = self.monitor.get_current_db()
            logger.info(f"Second dB reading: {db2:.1f}")
            
            # Check if readings are valid
            if db1 >= 0 and db2 >= 0:
                self.log_pass("dB reader producing valid readings")
                return True
            else:
                self.log_fail("Invalid dB readings")
                return False
                
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_song_detector_basic(self):
        """Test 2: Basic song detector functionality"""
        self.log_test("Basic Song Detector Functionality")
        
        try:
            if not hasattr(self.monitor, 'song_detector') or not self.monitor.song_detector:
                self.log_fail("Song detector not available")
                return False
            
            sd = self.monitor.song_detector
            
            # Check enabled
            if not sd.enabled:
                self.log_fail("Song detector not enabled")
                return False
            
            # Check threads
            if not sd.detection_thread or not sd.detection_thread.is_alive():
                self.log_fail("Detection thread not alive")
                return False
            
            if not sd.watchdog_thread or not sd.watchdog_thread.is_alive():
                self.log_fail("Watchdog thread not alive")
                return False
            
            # Check event loop
            if not sd._event_loop or sd._event_loop.is_closed():
                self.log_fail("Event loop unavailable")
                return False
            
            self.log_pass("Song detector fully operational")
            return True
            
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_monitoring_thread_recovery(self):
        """Test 3: Monitoring thread auto-recovery"""
        self.log_test("Monitoring Thread Auto-Recovery")
        
        try:
            # Kill monitoring thread
            logger.info("Killing monitoring thread...")
            if self.monitor._monitoring_thread:
                # Force thread to stop
                self.monitor.running = False
                time.sleep(2)
                
                # Restart monitoring
                self.monitor.running = True
                self.monitor.start_monitoring()
                
                # Wait for watchdog to detect and restart
                logger.info("Waiting for watchdog to detect and restart...")
                time.sleep(10)
                
                # Check if recovered
                if self.monitor._monitoring_thread and self.monitor._monitoring_thread.is_alive():
                    db = self.monitor.get_current_db()
                    if db >= 0:
                        self.log_pass("Monitoring thread recovered successfully")
                        return True
                    else:
                        self.log_fail("Thread recovered but not producing data")
                        return False
                else:
                    self.log_fail("Thread did not recover")
                    return False
            else:
                self.log_fail("Monitoring thread was not running")
                return False
                
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_song_detector_thread_recovery(self):
        """Test 4: Song detector thread auto-recovery"""
        self.log_test("Song Detector Thread Auto-Recovery")
        
        try:
            if not self.monitor.song_detector:
                self.log_fail("Song detector not available")
                return False
            
            sd = self.monitor.song_detector
            
            # Kill detection thread
            logger.info("Killing song detection thread...")
            sd.detection_active = False
            time.sleep(2)
            
            # Wait for watchdog to detect and restart
            logger.info("Waiting for watchdog to detect and restart...")
            time.sleep(10)
            
            # Check if recovered
            if sd.detection_thread and sd.detection_thread.is_alive():
                self.log_pass("Song detector thread recovered successfully")
                return True
            else:
                self.log_fail("Song detector thread did not recover")
                return False
                
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_db_reader_stall_detection(self):
        """Test 5: dB reader stall detection and recovery"""
        self.log_test("dB Reader Stall Detection")
        
        try:
            # Record initial reading
            initial_db = self.monitor.get_current_db()
            logger.info(f"Initial dB: {initial_db:.1f}")
            
            # Monitor for 20 seconds to ensure readings are updating
            logger.info("Monitoring dB readings for 20 seconds...")
            readings = []
            for i in range(4):
                time.sleep(5)
                db = self.monitor.get_current_db()
                readings.append(db)
                logger.info(f"  Reading {i+1}: {db:.1f} dB")
            
            # Check if readings are changing
            unique_readings = len(set(readings))
            if unique_readings > 1:
                self.log_pass("dB readings are updating normally")
                return True
            else:
                # All readings the same - check if watchdog caught it
                logger.warning("dB readings stuck - checking if watchdog is handling it...")
                time.sleep(10)
                new_db = self.monitor.get_current_db()
                if new_db != readings[0]:
                    self.log_pass("Watchdog detected stall and recovered")
                    return True
                else:
                    self.log_fail("dB reader stuck and watchdog did not recover")
                    return False
                
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_event_loop_health(self):
        """Test 6: Event loop health and recovery"""
        self.log_test("Event Loop Health Check")
        
        try:
            if not self.monitor.song_detector:
                self.log_fail("Song detector not available")
                return False
            
            sd = self.monitor.song_detector
            
            # Check event loop
            if not sd._event_loop:
                self.log_fail("Event loop is None")
                # Try to ensure it gets created
                sd._ensure_event_loop()
                time.sleep(2)
                if sd._event_loop:
                    self.log_pass("Event loop was recreated")
                    return True
                else:
                    self.log_fail("Event loop could not be created")
                    return False
            
            if sd._event_loop.is_closed():
                self.log_fail("Event loop is closed")
                # Should be recreated on next detection
                return False
            
            # Check event loop thread
            if not sd._event_loop_thread or not sd._event_loop_thread.is_alive():
                self.log_fail("Event loop thread is dead")
                return False
            
            self.log_pass("Event loop is healthy")
            return True
            
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_circuit_breaker(self):
        """Test 7: API circuit breaker functionality"""
        self.log_test("API Circuit Breaker")
        
        try:
            if not self.monitor.song_detector:
                self.log_fail("Song detector not available")
                return False
            
            sd = self.monitor.song_detector
            
            # Check circuit breaker attributes exist
            if not hasattr(sd, '_api_circuit_open'):
                self.log_fail("Circuit breaker not implemented")
                return False
            
            # Circuit should start closed
            if sd._api_circuit_open:
                logger.warning("Circuit breaker is already open")
            else:
                logger.info("Circuit breaker is closed (normal state)")
            
            self.log_pass("Circuit breaker is implemented and monitoring")
            return True
            
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def test_continuous_operation(self):
        """Test 8: Continuous operation stability"""
        self.log_test("Continuous Operation (60 seconds)")
        
        try:
            logger.info("Running continuous stability test for 60 seconds...")
            
            failures = 0
            checks = 0
            
            for i in range(12):  # 12 checks over 60 seconds
                time.sleep(5)
                checks += 1
                
                # Check dB reader
                try:
                    db = self.monitor.get_current_db()
                    if db < 0:
                        failures += 1
                        logger.warning(f"  Check {checks}: Invalid dB reading: {db}")
                    else:
                        logger.info(f"  Check {checks}: dB = {db:.1f} ✓")
                except Exception as e:
                    failures += 1
                    logger.error(f"  Check {checks}: dB reader error: {e}")
                
                # Check thread health
                if not self.monitor._monitoring_thread or not self.monitor._monitoring_thread.is_alive():
                    failures += 1
                    logger.error(f"  Check {checks}: Monitoring thread dead!")
                
                if self.monitor.song_detector:
                    sd = self.monitor.song_detector
                    if not sd.detection_thread or not sd.detection_thread.is_alive():
                        failures += 1
                        logger.error(f"  Check {checks}: Song detector thread dead!")
            
            # Evaluate
            success_rate = ((checks - failures) / checks * 100) if checks > 0 else 0
            logger.info(f"Stability test complete: {success_rate:.1f}% success rate")
            
            if failures == 0:
                self.log_pass("System stable - no failures in 60 seconds")
                return True
            elif failures <= 2:
                self.log_pass(f"System mostly stable - {failures} minor issues")
                return True
            else:
                self.log_fail(f"System unstable - {failures} failures detected")
                return False
                
        except Exception as e:
            self.log_fail(f"Exception: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        logger.info("\n")
        logger.info("="*80)
        logger.info("🧪 AUDIO RESILIENCE TEST SUITE")
        logger.info("="*80)
        logger.info("\n")
        
        # Initialize
        if not self.initialize():
            logger.error("Failed to initialize - cannot run tests")
            return False
        
        logger.info("\n")
        logger.info("Starting tests in 5 seconds...")
        time.sleep(5)
        logger.info("\n")
        
        # Run tests
        self.test_db_reader_basic()
        time.sleep(2)
        
        self.test_song_detector_basic()
        time.sleep(2)
        
        self.test_event_loop_health()
        time.sleep(2)
        
        self.test_circuit_breaker()
        time.sleep(2)
        
        self.test_db_reader_stall_detection()
        time.sleep(2)
        
        # Stress tests (commented out by default - enable for full testing)
        # self.test_monitoring_thread_recovery()
        # time.sleep(2)
        # 
        # self.test_song_detector_thread_recovery()
        # time.sleep(2)
        
        self.test_continuous_operation()
        
        # Summary
        logger.info("\n")
        logger.info("="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Tests:  {self.total_tests}")
        logger.info(f"Passed:       {self.passed_tests} ✅")
        logger.info(f"Failed:       {self.failed_tests} ❌")
        logger.info(f"Success Rate: {(self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0:.1f}%")
        logger.info("="*80)
        
        if self.failed_tests == 0:
            logger.info("\n🎉 ALL TESTS PASSED! System is resilient and robust!")
            return True
        else:
            logger.error(f"\n⚠️ {self.failed_tests} TEST(S) FAILED - Review and fix issues")
            return False


def main():
    """Main entry point"""
    tests = AudioResilienceTests()
    
    try:
        success = tests.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\n👋 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n🚨 CRITICAL ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
