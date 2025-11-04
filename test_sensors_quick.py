#!/usr/bin/env python3
"""Quick sensor diagnostic"""
import sys

def test_libs():
    print("\n" + "="*60)
    print("LIBRARY IMPORT TEST")
    print("="*60)
    
    libs = ['numpy', 'pyaudio', 'sounddevice', 'shazamio', 
            'adafruit_bme280', 'smbus2']
    results = {}
    
    for lib in libs:
        try:
            __import__(lib)
            print(f"✓ {lib}")
            results[lib] = True
        except ImportError as e:
            print(f"✗ {lib}: {e}")
            results[lib] = False
    
    return results

def test_bme280():
    print("\n" + "="*60)
    print("BME280 TEMPERATURE SENSOR TEST")
    print("="*60)
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.bme280_reader import BME280Reader
        
        print("Initializing BME280...")
        sensor = BME280Reader()
        
        print("Reading sensor...")
        data = sensor.read_sensor()
        
        if data and data.get('temperature_f'):
            print(f"\n✓✓✓ BME280 WORKING! ✓✓✓")
            print(f"Temperature: {data['temperature_f']:.1f}°F")
            print(f"Humidity: {data['humidity']:.1f}%")
            return True
        else:
            print("\n✗ BME280 returned no data")
            return False
    except Exception as e:
        print(f"\n✗ BME280 FAILED: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False

def test_audio():
    print("\n" + "="*60)
    print("AUDIO SYSTEM TEST")
    print("="*60)
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        
        print(f"\nFound {len(devices)} audio devices:")
        has_input = False
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                print(f"  [{i}] {dev['name']} (INPUT)")
                has_input = True
        
        if has_input:
            print("\n✓ Audio input devices available")
            return True
        else:
            print("\n✗ No audio input devices found")
            return False
    except Exception as e:
        print(f"\n✗ Audio test failed: {e}")
        return False

def test_audio_monitor():
    print("\n" + "="*60)
    print("AUDIO MONITORING TEST (5 seconds)")
    print("="*60)
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.mic_song_detect import AudioMonitor
        import time
        
        print("Starting audio monitor...")
        monitor = AudioMonitor()
        monitor.start_monitoring()
        
        print("Monitoring for 5 seconds...")
        time.sleep(5)
        
        db = monitor.get_current_db()
        monitor.stop_monitoring()
        
        if db > 0:
            print(f"\n✓✓✓ AUDIO MONITORING WORKING! ✓✓✓")
            print(f"Current dB: {db:.1f}")
            return True
        else:
            print(f"\n⚠ Monitor started but no sound detected (may be normal if silent)")
            return True
    except Exception as e:
        print(f"\n✗ Audio monitoring failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("PULSE SENSOR QUICK DIAGNOSTIC")
    print("="*60)
    
    lib_results = test_libs()
    bme_ok = test_bme280()
    audio_ok = test_audio()
    monitor_ok = test_audio_monitor()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    critical_libs = all([
        lib_results.get('numpy', False),
        lib_results.get('adafruit_bme280', False) or not any([bme_ok]),
        lib_results.get('pyaudio', False) or lib_results.get('sounddevice', False)
    ])
    
    if bme_ok and monitor_ok:
        print("\n✓✓✓ ALL SENSORS WORKING! ✓✓✓")
        print("\nStart Pulse with: bash /workspace/start_pulse.sh")
        return 0
    else:
        print("\n⚠ PARTIAL SUCCESS")
        if not bme_ok:
            print("  - BME280: NOT WORKING")
        else:
            print("  - BME280: OK")
        
        if not monitor_ok:
            print("  - Audio Monitor: NOT WORKING")
        else:
            print("  - Audio Monitor: OK")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
