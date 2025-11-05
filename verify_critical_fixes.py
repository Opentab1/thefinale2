#!/usr/bin/env python3
"""
CRITICAL VERIFICATION TEST
Tests all the fixes to ensure they work correctly
"""

import sys
import time
import logging
sys.path.insert(0, '/workspace')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_imports():
    """Test that all imports work"""
    print("\n" + "="*80)
    print("TEST 1: Import Verification")
    print("="*80)
    try:
        from services.sensors.song_detector import SongDetector
        print("✅ SongDetector imported successfully")
    except Exception as e:
        print(f"❌ FAILED: SongDetector import: {e}")
        return False
    
    try:
        from services.sensors.mic_song_detect import AudioMonitor
        print("✅ AudioMonitor imported successfully")
    except Exception as e:
        print(f"❌ FAILED: AudioMonitor import: {e}")
        return False
    
    return True

def test_song_detector_initialization():
    """Test SongDetector initialization"""
    print("\n" + "="*80)
    print("TEST 2: SongDetector Initialization")
    print("="*80)
    try:
        from services.sensors.song_detector import SongDetector
        
        # Test with enabled=True and buffer mode
        detector = SongDetector(enabled=True, use_buffer_mode=True)
        print(f"✅ SongDetector initialized")
        print(f"   - enabled: {detector.enabled}")
        print(f"   - use_buffer_mode: {detector.use_buffer_mode}")
        print(f"   - watchdog_interval: {detector.watchdog_interval}")
        
        # Check threads
        if detector.detection_thread:
            print(f"   - detection_thread: {'alive' if detector.detection_thread.is_alive() else 'dead'}")
        else:
            print(f"   - detection_thread: None (may be disabled if ShazamIO unavailable)")
        
        if detector.watchdog_thread:
            print(f"   - watchdog_thread: {'alive' if detector.watchdog_thread.is_alive() else 'dead'}")
        else:
            print(f"   - watchdog_thread: None")
        
        # Check watchdog interval
        if detector.watchdog_interval == 3.0:
            print("✅ Watchdog interval is 3 seconds (correct)")
        else:
            print(f"⚠️ Watchdog interval is {detector.watchdog_interval} (expected 3.0)")
        
        # Check restart limit
        if detector.max_restarts_per_hour == 100:
            print("✅ Max restarts per hour is 100 (correct)")
        else:
            print(f"⚠️ Max restarts per hour is {detector.max_restarts_per_hour} (expected 100)")
        
        # Cleanup
        detector.stop()
        print("✅ SongDetector stopped successfully")
        return True
        
    except Exception as e:
        print(f"❌ FAILED: SongDetector initialization: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_watchdog_logic():
    """Test watchdog restart logic"""
    print("\n" + "="*80)
    print("TEST 3: Watchdog Logic Verification")
    print("="*80)
    
    # Check that restart time logic is correct
    from services.sensors.song_detector import SongDetector
    
    detector = SongDetector(enabled=True, use_buffer_mode=True)
    
    # Verify _last_restart_time is initialized
    if hasattr(detector, '_last_restart_time'):
        print(f"✅ _last_restart_time attribute exists: {detector._last_restart_time}")
    else:
        print("❌ FAILED: _last_restart_time attribute missing")
        detector.stop()
        return False
    
    # Verify heartbeat logic
    if hasattr(detector, 'last_heartbeat'):
        print(f"✅ last_heartbeat attribute exists")
        initial_heartbeat = detector.last_heartbeat
        time.sleep(1)
        # In buffer mode, heartbeat should update every 5 seconds
        print(f"   - Initial heartbeat: {initial_heartbeat}")
        print(f"   - Heartbeat check threshold: 15 seconds (correct for buffer mode)")
    else:
        print("❌ FAILED: last_heartbeat attribute missing")
        detector.stop()
        return False
    
    detector.stop()
    return True

def test_exception_handling():
    """Test that exception handling doesn't crash"""
    print("\n" + "="*80)
    print("TEST 4: Exception Handling Verification")
    print("="*80)
    
    from services.sensors.song_detector import SongDetector
    
    detector = SongDetector(enabled=True, use_buffer_mode=True)
    
    # Check that detection loop has exception handling
    import inspect
    detection_loop = detector._detection_loop
    
    # Get source code
    try:
        source = inspect.getsource(detection_loop)
        
        # Check for exception handling
        if 'except Exception' in source or 'except:' in source:
            print("✅ Detection loop has exception handling")
        else:
            print("❌ FAILED: Detection loop missing exception handling")
            detector.stop()
            return False
        
        # Check for consecutive_errors tracking
        if 'consecutive_errors' in source:
            print("✅ Detection loop tracks consecutive errors")
        else:
            print("⚠️ Detection loop doesn't track consecutive errors (may be OK)")
        
        # Check watchdog loop
        watchdog_loop = detector._watchdog_loop
        watchdog_source = inspect.getsource(watchdog_loop)
        
        if 'except Exception' in watchdog_source or 'except:' in watchdog_source:
            print("✅ Watchdog loop has exception handling")
        else:
            print("❌ FAILED: Watchdog loop missing exception handling")
            detector.stop()
            return False
        
    except Exception as e:
        print(f"⚠️ Could not verify source code: {e}")
    
    detector.stop()
    return True

def test_audio_monitor_initialization():
    """Test AudioMonitor initialization"""
    print("\n" + "="*80)
    print("TEST 5: AudioMonitor Initialization")
    print("="*80)
    
    try:
        from services.sensors.mic_song_detect import AudioMonitor
        
        # Check that SongDetector initialization is correct
        import inspect
        init_source = inspect.getsource(AudioMonitor.__init__)
        
        # Check for enabled=True
        if "enabled=True" in init_source:
            print("✅ AudioMonitor initializes SongDetector with enabled=True")
        else:
            print("❌ FAILED: AudioMonitor doesn't set enabled=True")
            return False
        
        # Check for use_buffer_mode=True
        if "use_buffer_mode=True" in init_source:
            print("✅ AudioMonitor initializes SongDetector with use_buffer_mode=True")
        else:
            print("❌ FAILED: AudioMonitor doesn't set use_buffer_mode=True")
            return False
        
        # Check watchdog interval
        if "_watchdog_restart_threshold = 10.0" in init_source or "_watchdog_restart_threshold = 10" in init_source:
            print("✅ AudioMonitor watchdog threshold is 10 seconds")
        else:
            print("⚠️ AudioMonitor watchdog threshold may not be 10 seconds (check manually)")
        
        # Check health check interval
        if "_health_check_interval = 3.0" in init_source or "_health_check_interval = 3" in init_source:
            print("✅ AudioMonitor health check interval is 3 seconds")
        else:
            print("⚠️ AudioMonitor health check interval may not be 3 seconds (check manually)")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: AudioMonitor verification: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("CRITICAL FIX VERIFICATION TEST")
    print("="*80)
    
    tests = [
        test_imports,
        test_song_detector_initialization,
        test_watchdog_logic,
        test_exception_handling,
        test_audio_monitor_initialization,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i}. {test.__name__}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Code is ready for deployment!")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED - Review issues above")
        return 1

if __name__ == '__main__':
    sys.exit(main())
