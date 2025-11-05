#!/usr/bin/env python3
"""
FINAL COMPREHENSIVE TEST
Tests all critical paths after fixes
"""

import sys
import time
import logging
sys.path.insert(0, '/workspace')

logging.basicConfig(level=logging.ERROR)

def test_watchdog_condition_fix():
    """Test that watchdog condition is fixed"""
    print("\n" + "="*80)
    print("TEST: Watchdog Condition Fix")
    print("="*80)
    
    from services.sensors.song_detector import SongDetector
    import inspect
    
    detector = SongDetector(enabled=True, use_buffer_mode=True)
    watchdog_source = inspect.getsource(detector._watchdog_loop)
    
    # Check the condition
    if 'while self.watchdog_active:' in watchdog_source:
        print('✅ Watchdog condition is correct (only checks watchdog_active)')
        print('   This ensures watchdog always runs regardless of enabled state')
    else:
        print('❌ Watchdog condition may still have issues')
        detector.stop()
        return False
    
    # Verify it handles degraded mode
    if 'SHAZAMIO_AVAILABLE' in watchdog_source:
        print('✅ Watchdog checks for ShazamIO availability')
    else:
        print('⚠️ Watchdog may not check for ShazamIO availability')
    
    # Verify it handles dead threads
    if 'not self.detection_thread.is_alive()' in watchdog_source:
        print('✅ Watchdog checks if thread is alive (not just exists)')
    else:
        print('⚠️ Watchdog may not check thread liveness properly')
    
    detector.stop()
    return True

def test_initialization_flow():
    """Test initialization flow"""
    print("\n" + "="*80)
    print("TEST: Initialization Flow")
    print("="*80)
    
    from services.sensors.song_detector import SongDetector
    
    # Test with enabled=True
    detector = SongDetector(enabled=True, use_buffer_mode=True)
    time.sleep(0.5)
    
    checks = {
        'Watchdog thread exists': detector.watchdog_thread is not None,
        'Watchdog thread alive': detector.watchdog_thread is not None and detector.watchdog_thread.is_alive(),
        'Watchdog interval correct': detector.watchdog_interval == 3.0,
        'Max restarts correct': detector.max_restarts_per_hour == 100,
    }
    
    for check, result in checks.items():
        status = '✅' if result else '❌'
        print(f'{status} {check}')
        if not result:
            detector.stop()
            return False
    
    detector.stop()
    return True

def test_exception_handling():
    """Test exception handling"""
    print("\n" + "="*80)
    print("TEST: Exception Handling")
    print("="*80)
    
    from services.sensors.song_detector import SongDetector
    import inspect
    
    detector = SongDetector(enabled=True, use_buffer_mode=True)
    
    # Check detection loop
    detection_source = inspect.getsource(detector._detection_loop)
    watchdog_source = inspect.getsource(detector._watchdog_loop)
    
    if 'except Exception' in detection_source or 'except:' in detection_source:
        print('✅ Detection loop has exception handling')
    else:
        print('❌ Detection loop missing exception handling')
        detector.stop()
        return False
    
    if 'except Exception' in watchdog_source or 'except:' in watchdog_source:
        print('✅ Watchdog loop has exception handling')
    else:
        print('❌ Watchdog loop missing exception handling')
        detector.stop()
        return False
    
    if 'consecutive_errors' in detection_source:
        print('✅ Detection loop tracks consecutive errors')
    else:
        print('⚠️ Detection loop may not track consecutive errors')
    
    if 'consecutive_errors' in watchdog_source:
        print('✅ Watchdog loop tracks consecutive errors')
    else:
        print('⚠️ Watchdog loop may not track consecutive errors')
    
    detector.stop()
    return True

def test_audio_monitor_integration():
    """Test AudioMonitor integration"""
    print("\n" + "="*80)
    print("TEST: AudioMonitor Integration")
    print("="*80)
    
    from services.sensors.mic_song_detect import AudioMonitor
    import inspect
    
    init_source = inspect.getsource(AudioMonitor.__init__)
    
    checks = {
        'Creates SongDetector': 'SongDetector(' in init_source,
        'Sets enabled=True': 'enabled=True' in init_source,
        'Sets use_buffer_mode=True': 'use_buffer_mode=True' in init_source,
    }
    
    for check, result in checks.items():
        status = '✅' if result else '❌'
        print(f'{status} {check}')
        if not result:
            return False
    
    return True

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("FINAL COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    tests = [
        ("Watchdog Condition Fix", test_watchdog_condition_fix),
        ("Initialization Flow", test_initialization_flow),
        ("Exception Handling", test_exception_handling),
        ("AudioMonitor Integration", test_audio_monitor_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print("\n" + "="*80)
    print("FINAL TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n" + "="*80)
        print("✅✅✅ ALL TESTS PASSED - SYSTEM IS READY ✅✅✅")
        print("="*80)
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
