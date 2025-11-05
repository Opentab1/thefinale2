#!/usr/bin/env python3
"""
Comprehensive diagnostic for db reader and song detector
Shows exactly what's happening so we can fix it permanently
"""

import sys
import time
import logging
import traceback
from pathlib import Path
from datetime import datetime

# Add services to path
sys.path.insert(0, str(Path(__file__).parent / "services"))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def check_dependencies():
    """Check if all required dependencies are installed"""
    print_section("CHECKING DEPENDENCIES")
    
    deps = {
        'numpy': 'NumPy (required for audio processing)',
        'pyaudio': 'PyAudio (audio backend)',
        'sounddevice': 'sounddevice (audio backend fallback)',
        'shazamio': 'ShazamIO (song detection)',
        'aiohttp': 'aiohttp (required by ShazamIO)',
    }
    
    missing = []
    for module, desc in deps.items():
        try:
            __import__(module)
            print(f"✓ {desc}")
        except ImportError:
            print(f"✗ {desc} - MISSING")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
    else:
        print("\n✓ All dependencies available")
    
    return len(missing) == 0

def check_audio_devices():
    """Check if audio input devices are available"""
    print_section("CHECKING AUDIO DEVICES")
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        
        if input_devices:
            print(f"✓ Found {len(input_devices)} input device(s):")
            for i, dev in enumerate(input_devices):
                default = " (DEFAULT)" if dev == sd.default.device[0] else ""
                print(f"  [{i}] {dev['name']}{default}")
        else:
            print("✗ No input devices found!")
            print("  Run: arecord -l  (to list ALSA devices)")
            return False
    except Exception as e:
        print(f"✗ Error checking devices: {e}")
        return False
    
    return True

def test_audio_monitor_init():
    """Test AudioMonitor initialization"""
    print_section("TESTING AUDIO MONITOR INITIALIZATION")
    
    try:
        from sensors.mic_song_detect import AudioMonitor
        
        print("Creating AudioMonitor instance...")
        monitor = AudioMonitor()
        print("✓ AudioMonitor created successfully")
        
        print(f"\nDevice index: {monitor.device_index}")
        print(f"Sample rate: {monitor.sample_rate}")
        print(f"Chunk size: {monitor.chunk_size}")
        print(f"Song detector available: {monitor.song_detector is not None}")
        
        if monitor.song_detector is None:
            print("\n⚠️  Song detector is None - checking why...")
            try:
                from sensors.song_detector import SongDetector
                print("✓ SongDetector class can be imported")
            except Exception as e:
                print(f"✗ Cannot import SongDetector: {e}")
                traceback.print_exc()
        
        return monitor
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        traceback.print_exc()
        return None

def test_monitor_start(monitor, duration=30):
    """Test starting the monitor and watch for failures"""
    print_section(f"TESTING AUDIO MONITOR START (watching for {duration}s)")
    
    if monitor is None:
        print("✗ Cannot test - monitor is None")
        return False
    
    try:
        print("Starting monitor...")
        monitor.start_monitoring()
        print("✓ Monitor started")
        
        start_time = time.time()
        last_db_time = 0
        last_song_time = 0
        db_readings = 0
        song_detections = 0
        errors = []
        
        print(f"\nMonitoring for {duration} seconds...")
        print("Watching for:")
        print("  - dB readings (should appear every ~2 seconds)")
        print("  - Song detection attempts (should appear every ~10 seconds)")
        print("  - Any errors or failures")
        print("\n")
        
        while time.time() - start_time < duration:
            time.sleep(1)
            elapsed = time.time() - start_time
            
            # Check dB readings
            current_db = monitor.get_current_db()
            if current_db > 0 and time.time() - last_db_time > 1.5:
                db_readings += 1
                last_db_time = time.time()
                print(f"[{elapsed:5.1f}s] 🔊 dB: {current_db:.1f} (Peak: {monitor.get_peak_db():.1f})")
            
            # Check song detection
            song = monitor.get_current_song()
            stats = monitor.get_song_detection_stats()
            
            if stats.get('active'):
                if time.time() - last_song_time > 5:
                    print(f"[{elapsed:5.1f}s] 🎵 Song detection ACTIVE (started: {stats.get('last_attempt_started_at')})")
                    last_song_time = time.time()
            
            if stats.get('last_error') and stats.get('last_error') not in errors:
                errors.append(stats.get('last_error'))
                print(f"[{elapsed:5.1f}s] ⚠️  Song detection error: {stats.get('last_error')}")
            
            # Check if monitoring thread is alive
            if monitor._monitoring_thread is None or not monitor._monitoring_thread.is_alive():
                print(f"[{elapsed:5.1f}s] 🚨 CRITICAL: Monitoring thread died!")
                break
            
            # Check if health thread is alive
            if monitor._health_thread is None or not monitor._health_thread.is_alive():
                print(f"[{elapsed:5.1f}s] ⚠️  Health thread died!")
            
            # Check for stale dB readings
            if monitor._last_db_ts > 0:
                db_age = time.time() - monitor._last_db_ts
                if db_age > 10 and elapsed > 5:
                    print(f"[{elapsed:5.1f}s] ⚠️  WARNING: No dB readings for {db_age:.1f}s")
        
        print(f"\n--- Summary after {duration}s ---")
        print(f"dB readings received: {db_readings}")
        print(f"Song detection attempts: {song_detections}")
        print(f"Errors encountered: {len(errors)}")
        if errors:
            print("Errors:")
            for err in errors:
                print(f"  - {err}")
        
        # Final status check
        stats = monitor.get_stats()
        print(f"\nFinal status:")
        print(f"  Current dB: {stats['current_db']:.1f}")
        print(f"  Peak dB: {stats['peak_db']:.1f}")
        print(f"  Song: {stats['current_song']['title']} - {stats['current_song']['artist']}")
        print(f"  Detection active: {stats['song_detection'].get('active', False)}")
        print(f"  Last error: {stats['song_detection'].get('last_error', 'None')}")
        
        # Check thread status
        print(f"\nThread status:")
        print(f"  Monitoring thread alive: {monitor._monitoring_thread is not None and monitor._monitoring_thread.is_alive()}")
        print(f"  Health thread alive: {monitor._health_thread is not None and monitor._health_thread.is_alive()}")
        print(f"  Detection loop thread alive: {monitor._detection_loop_thread is not None and monitor._detection_loop_thread.is_alive() if monitor._detection_loop_thread else False}")
        
        monitor.stop_monitoring()
        print("\n✓ Monitor stopped")
        
        return db_readings > 0
        
    except Exception as e:
        print(f"✗ Error during monitoring: {e}")
        traceback.print_exc()
        try:
            monitor.stop_monitoring()
        except:
            pass
        return False

def check_systemd_services():
    """Check systemd service status"""
    print_section("CHECKING SYSTEMD SERVICES")
    
    import subprocess
    
    services = ['pulse-hub', 'pulse-health']
    
    for service in services:
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service],
                capture_output=True,
                text=True,
                timeout=2
            )
            status = result.stdout.strip()
            if status == 'active':
                print(f"✓ {service} is active")
                
                # Check recent logs
                log_result = subprocess.run(
                    ['journalctl', '-u', service, '-n', '20', '--no-pager'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                logs = log_result.stdout
                if 'error' in logs.lower() or 'exception' in logs.lower() or 'failed' in logs.lower():
                    print(f"  ⚠️  Errors found in logs:")
                    for line in logs.split('\n')[-10:]:
                        if any(word in line.lower() for word in ['error', 'exception', 'failed']):
                            print(f"    {line}")
            else:
                print(f"✗ {service} is {status}")
        except Exception as e:
            print(f"⚠️  Could not check {service}: {e}")

def main():
    print("\n" + "="*80)
    print("  DB READER & SONG DETECTOR DIAGNOSTIC")
    print("  This will show exactly what's happening")
    print("="*80)
    
    # Step 1: Check dependencies
    deps_ok = check_dependencies()
    if not deps_ok:
        print("\n⚠️  Fix missing dependencies first!")
        return
    
    # Step 2: Check audio devices
    devices_ok = check_audio_devices()
    if not devices_ok:
        print("\n⚠️  No audio devices found!")
        return
    
    # Step 3: Check systemd services
    check_systemd_services()
    
    # Step 4: Test initialization
    monitor = test_audio_monitor_init()
    if monitor is None:
        print("\n✗ Cannot proceed - AudioMonitor failed to initialize")
        return
    
    # Step 5: Test running
    success = test_monitor_start(monitor, duration=30)
    
    # Final verdict
    print_section("DIAGNOSTIC SUMMARY")
    if success:
        print("✓ Audio monitor appears to be working")
    else:
        print("✗ Audio monitor has issues - see details above")
    
    print("\n" + "="*80)
    print("  Diagnostic complete - review output above for issues")
    print("="*80 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
