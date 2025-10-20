#!/usr/bin/env python3
"""
Quick audio capture test to diagnose audio issues
"""

import sys
import time

print("="*80)
print("AUDIO CAPTURE DIAGNOSTICS")
print("="*80)

# Test 1: Check if we can import audio libraries
print("\n1. Checking audio libraries...")
try:
    import pyaudio
    print("  ✓ PyAudio available")
    PYAUDIO_OK = True
except:
    print("  ✗ PyAudio not available")
    PYAUDIO_OK = False

try:
    import sounddevice as sd
    print("  ✓ sounddevice available")
    SD_OK = True
except:
    print("  ✗ sounddevice not available")
    SD_OK = False

try:
    import numpy as np
    print("  ✓ NumPy available")
    NUMPY_OK = True
except:
    print("  ✗ NumPy not available")
    NUMPY_OK = False
    sys.exit(1)

if not PYAUDIO_OK and not SD_OK:
    print("\n✗ No audio backend available!")
    sys.exit(1)

# Test 2: Find audio devices
print("\n2. Finding audio input devices...")
if PYAUDIO_OK:
    p = pyaudio.PyAudio()
    device_count = p.get_device_count()
    print(f"  Found {device_count} total devices")
    
    input_devices = []
    for i in range(device_count):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append(i)
                print(f"  ✓ Input device {i}: {info['name']}")
                print(f"    - Channels: {info['maxInputChannels']}")
                print(f"    - Sample rate: {info['defaultSampleRate']}")
        except:
            pass
    
    if not input_devices:
        print("  ✗ No input devices found!")
        p.terminate()
        sys.exit(1)
    
    # Test 3: Try to capture audio
    print(f"\n3. Testing audio capture on device {input_devices[0]}...")
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            input_device_index=input_devices[0],
            frames_per_buffer=2048
        )
        print("  ✓ Audio stream opened successfully")
        
        # Capture a few chunks
        print("  Capturing 5 audio chunks...")
        for i in range(5):
            audio_bytes = stream.read(2048, exception_on_overflow=False)
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Calculate RMS
            audio_float = audio_data.astype(np.float32) / 32768.0
            rms = np.sqrt(np.mean(audio_float ** 2))
            db = 20 * np.log10(rms + 1e-10) + 94
            db = max(0, min(120, db))
            
            print(f"    Chunk {i+1}: {len(audio_data)} samples, RMS: {rms:.6f}, dB: {db:.1f}")
            time.sleep(0.1)
        
        stream.stop_stream()
        stream.close()
        print("\n  ✓ Audio capture working!")
        
    except Exception as e:
        print(f"  ✗ Audio capture failed: {e}")
        import traceback
        traceback.print_exc()
    
    p.terminate()

elif SD_OK:
    print("\n3. Testing with sounddevice...")
    try:
        devices = sd.query_devices()
        input_devs = [i for i, d in enumerate(devices) if d['max_input_channels'] > 0]
        
        if not input_devs:
            print("  ✗ No input devices!")
            sys.exit(1)
        
        device_idx = input_devs[0]
        print(f"  Using device {device_idx}: {devices[device_idx]['name']}")
        
        # Capture test
        print("  Capturing 2 seconds of audio...")
        recording = sd.rec(int(2 * 44100), samplerate=44100, channels=1, dtype='int16', device=device_idx)
        sd.wait()
        
        # Calculate dB
        audio_float = recording.flatten().astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        db = 20 * np.log10(rms + 1e-10) + 94
        db = max(0, min(120, db))
        
        print(f"  ✓ Captured {len(recording)} samples")
        print(f"  ✓ RMS: {rms:.6f}, dB: {db:.1f}")
        
    except Exception as e:
        print(f"  ✗ sounddevice test failed: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("If you see dB readings above, your audio hardware is working!")
print("If dB is very low (< 30), try making some noise and run again.")
print("="*80)
