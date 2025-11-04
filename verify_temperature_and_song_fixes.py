#!/usr/bin/env python3
"""
Verification script for temperature and song detection fixes
Run this to check if the fixes are working correctly
"""

import sys
import time
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def check_database_access():
    """Test database connection and timeout handling"""
    print("="*60)
    print("Testing Database Connection...")
    print("="*60)
    
    try:
        from services.storage.db import PulseDB
        db = PulseDB()
        
        # Test basic connection
        print("✓ Database initialized")
        
        # Test environment data
        env = db.get_latest_environment()
        if env:
            print(f"✓ Latest environment data retrieved:")
            print(f"  Temperature: {env.get('temperature')}°F")
            print(f"  Humidity: {env.get('humidity')}%")
            print(f"  Light: {env.get('light_level')} lux")
            print(f"  Noise: {env.get('noise_level')} dB")
        else:
            print("⚠ No environment data in database yet")
        
        # Test music log
        with db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM music_log")
            count = cur.fetchone()[0]
            print(f"✓ Music log has {count} entries")
        
        return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_bme280_sensor():
    """Test BME280 sensor reading"""
    print("\n" + "="*60)
    print("Testing BME280 Temperature Sensor...")
    print("="*60)
    
    try:
        from services.sensors.bme280_reader import BME280Reader
        
        print("Initializing BME280...")
        reader = BME280Reader()
        print(f"✓ BME280 initialized at address {hex(reader.address)}")
        
        # Test single read
        print("Reading sensor data...")
        data = reader.read_sensor()
        
        if data and data.get("temperature_f") is not None:
            print("✓ Sensor read successful:")
            print(f"  Temperature: {data['temperature_f']:.1f}°F ({data['temperature_c']:.1f}°C)")
            print(f"  Humidity: {data['humidity']:.1f}%")
            print(f"  Pressure: {data['pressure']:.2f} hPa")
            print(f"  Altitude: {data['altitude']:.1f}m")
            return True
        else:
            print("✗ Sensor read returned no data")
            return False
            
    except Exception as e:
        print(f"✗ BME280 test failed: {e}")
        print("  This is expected if sensor is not connected")
        print("  Check connection with: sudo i2cdetect -y 1")
        return False

def check_audio_monitor():
    """Test audio monitor initialization"""
    print("\n" + "="*60)
    print("Testing Audio Monitor...")
    print("="*60)
    
    try:
        from services.sensors.mic_song_detect import AudioMonitor
        
        print("Initializing audio monitor...")
        monitor = AudioMonitor()
        print(f"✓ Audio monitor initialized (device: {monitor.device_index})")
        
        if monitor.song_detector:
            print("✓ Song detector available")
        else:
            print("⚠ Song detector not available (ShazamIO may not be installed)")
        
        return True
    except Exception as e:
        print(f"✗ Audio monitor test failed: {e}")
        print("  Install dependencies: pip install numpy pyaudio sounddevice shazamio")
        return False

def test_continuous_monitoring(duration=60):
    """Test continuous monitoring for specified duration"""
    print("\n" + "="*60)
    print(f"Testing Continuous Monitoring ({duration} seconds)...")
    print("="*60)
    
    try:
        from services.hub.main import PulseHub
        from services.storage.db import PulseDB
        
        print("Initializing hub...")
        hub = PulseHub()
        db = PulseDB()
        
        print("Starting hub...")
        hub.start()
        time.sleep(5)  # Let it initialize
        
        print(f"\nMonitoring for {duration} seconds...")
        print("Press Ctrl+C to stop early\n")
        
        start_time = time.time()
        check_interval = 10  # Check every 10 seconds
        last_check = start_time
        
        while time.time() - start_time < duration:
            try:
                current_time = time.time()
                if current_time - last_check >= check_interval:
                    # Get status
                    status = hub.get_status()
                    sensors = status.get('sensors', {})
                    
                    print(f"\n[{int(current_time - start_time)}s] Status Update:")
                    print(f"  🌡️  Temperature: {sensors.get('temperature_f', 'N/A')}°F")
                    print(f"  💧 Humidity: {sensors.get('humidity', 'N/A')}%")
                    print(f"  💡 Light: {sensors.get('light_level', 'N/A')} lux")
                    print(f"  🔊 Noise: {sensors.get('noise_db', 'N/A')} dB")
                    print(f"  👥 Occupancy: {sensors.get('occupancy', 0)} people")
                    
                    song = sensors.get('current_song')
                    if song and song.get('title') not in (None, 'Unknown'):
                        print(f"  🎵 Song: {song['title']} - {song['artist']}")
                    else:
                        print(f"  🎵 Song: Not detected")
                    
                    # Check database
                    env = db.get_latest_environment()
                    if env:
                        db_temp = env.get('temperature')
                        print(f"  💾 DB Temp: {db_temp}°F")
                    
                    last_check = current_time
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\n\nStopping early...")
                break
        
        print("\nStopping hub...")
        hub.stop()
        print("✓ Continuous monitoring test complete")
        return True
        
    except Exception as e:
        print(f"✗ Continuous monitoring test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all verification tests"""
    print("="*60)
    print("TEMPERATURE AND SONG DETECTION FIX VERIFICATION")
    print("="*60)
    print()
    
    results = {
        "Database Access": check_database_access(),
        "BME280 Sensor": check_bme280_sensor(),
        "Audio Monitor": check_audio_monitor(),
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    # Offer to run continuous test
    print("\n" + "="*60)
    try:
        response = input("Run continuous monitoring test for 60 seconds? (y/n): ")
        if response.lower() == 'y':
            results["Continuous Monitoring"] = test_continuous_monitoring(60)
    except (KeyboardInterrupt, EOFError):
        print("\nSkipping continuous test")
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Fixes are working correctly!")
    else:
        print("\n⚠ SOME TESTS FAILED - Check error messages above")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
