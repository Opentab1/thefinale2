#!/usr/bin/env python3
"""
Comprehensive RapidAPI debugging script
Tests every possible failure mode
"""

import requests
import sounddevice as sd
import wave
import tempfile
import os
import hashlib

API_KEY = "de528fdc31mshb7f88b1b939f9b7p1db4cejsn1e64b438f142"
URL = "https://shazam-core.p.rapidapi.com/v1/tracks/recognize"

print("="*80)
print("🔍 RAPIDAPI COMPREHENSIVE DEBUG TEST")
print("="*80)

# TEST 1: Record audio with sounddevice
print("\n📼 TEST 1: Recording with sounddevice...")
try:
    recording = sd.rec(int(5 * 44100), samplerate=44100, channels=1, dtype='int16')
    sd.wait()
    print("✅ Recording complete")
except Exception as e:
    print(f"❌ Recording failed: {e}")
    exit(1)

# TEST 2: Save to WAV
print("\n💾 TEST 2: Saving to WAV file...")
temp_filename = "/tmp/rapidapi_test.wav"
try:
    with wave.open(temp_filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(recording.tobytes())
    
    file_size = os.path.getsize(temp_filename)
    print(f"✅ File saved: {file_size} bytes ({file_size/1024:.1f} KB)")
    
    # Calculate file hash
    with open(temp_filename, 'rb') as f:
        file_hash = hashlib.md5(f.read()).hexdigest()
    print(f"   MD5 hash: {file_hash}")
    
except Exception as e:
    print(f"❌ Save failed: {e}")
    exit(1)

# TEST 3: Verify file is readable
print("\n📖 TEST 3: Verify file is readable...")
try:
    with wave.open(temp_filename, 'rb') as wf:
        frames = wf.getnframes()
        channels = wf.getnchannels()
        rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
    print(f"✅ WAV file valid:")
    print(f"   Frames: {frames}")
    print(f"   Channels: {channels}")
    print(f"   Sample rate: {rate}")
    print(f"   Sample width: {sampwidth} bytes")
except Exception as e:
    print(f"❌ File read failed: {e}")
    exit(1)

# TEST 4: Test different upload methods
print("\n🔄 TEST 4: Testing upload methods...")

# Method A: File object with tuple
print("\n   Method A: File object with tuple...")
try:
    with open(temp_filename, 'rb') as f:
        files = {'file': ('test.wav', f, 'audio/wav')}
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": "shazam-core.p.rapidapi.com"
        }
        response = requests.post(URL, files=files, headers=headers, timeout=15.0)
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    if response.status_code != 200:
        print(f"   ❌ Failed with status {response.status_code}")
    else:
        result = response.json()
        if result.get('track'):
            print(f"   ✅ SONG DETECTED: {result['track'].get('title')}")
        else:
            print(f"   ⚠️ No song detected (track: None)")
            
except Exception as e:
    print(f"   ❌ Error: {e}")

# Method B: Read full file content first
print("\n   Method B: Read full file content...")
try:
    with open(temp_filename, 'rb') as f:
        file_content = f.read()
    
    print(f"   Content length: {len(file_content)} bytes")
    
    files = {'file': ('test.wav', file_content, 'audio/wav')}
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "shazam-core.p.rapidapi.com"
    }
    response = requests.post(URL, files=files, headers=headers, timeout=15.0)
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    if response.status_code != 200:
        print(f"   ❌ Failed with status {response.status_code}")
    else:
        result = response.json()
        if result.get('track'):
            print(f"   ✅ SONG DETECTED: {result['track'].get('title')}")
        else:
            print(f"   ⚠️ No song detected (track: None)")
            
except Exception as e:
    print(f"   ❌ Error: {e}")

# Method C: Using requests.Request for debugging
print("\n   Method C: Prepared request (inspect upload)...")
try:
    with open(temp_filename, 'rb') as f:
        file_content = f.read()
    
    files = {'file': ('test.wav', file_content, 'audio/wav')}
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "shazam-core.p.rapidapi.com"
    }
    
    req = requests.Request('POST', URL, files=files, headers=headers)
    prepared = req.prepare()
    
    print(f"   Content-Length: {prepared.headers.get('Content-Length', 'Unknown')}")
    print(f"   Content-Type: {prepared.headers.get('Content-Type', 'Unknown')}")
    
    session = requests.Session()
    response = session.send(prepared, timeout=15.0)
    
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    if response.status_code != 200:
        print(f"   ❌ Failed with status {response.status_code}")
    else:
        result = response.json()
        if result.get('track'):
            print(f"   ✅ SONG DETECTED: {result['track'].get('title')}")
        else:
            print(f"   ⚠️ No song detected (track: None)")
            
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("📊 SUMMARY")
print("="*80)
print(f"File created: {temp_filename}")
print(f"File size: {file_size} bytes")
print(f"All tests complete - check results above")
print("="*80)
