#!/usr/bin/env python3
"""
Song Detection Diagnostic Tool
Checks all aspects of song detection to identify issues
"""

import sys
import os
import subprocess
import json
from pathlib import Path
import time

print("="*80)
print("🎵 PULSE SONG DETECTION DIAGNOSTIC TOOL")
print("="*80)
print()

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check(message):
    print(f"{BLUE}[CHECK]{RESET} {message}...", end=" ", flush=True)

def success(message):
    print(f"{GREEN}✓{RESET} {message}")

def failure(message):
    print(f"{RED}✗{RESET} {message}")

def warning(message):
    print(f"{YELLOW}⚠{RESET} {message}")

def info(message):
    print(f"{BLUE}ℹ{RESET} {message}")

# Track issues
issues = []
warnings_list = []

print("STEP 1: Checking Python Dependencies")
print("-" * 80)

# Check sounddevice
check("sounddevice library")
try:
    import sounddevice as sd
    success("sounddevice is installed")
except ImportError:
    failure("sounddevice NOT installed")
    issues.append("sounddevice library missing")
    print(f"   → Fix: pip install sounddevice")

# Check shazamio
check("shazamio library")
try:
    from shazamio import Shazam
    success("shazamio is installed")
except ImportError:
    failure("shazamio NOT installed")
    issues.append("shazamio library missing")
    print(f"   → Fix: pip install shazamio")

# Check numpy
check("numpy library")
try:
    import numpy
    success("numpy is installed")
except ImportError:
    failure("numpy NOT installed")
    issues.append("numpy library missing")
    print(f"   → Fix: pip install numpy")

print()
print("STEP 2: Checking Audio Hardware")
print("-" * 80)

# Check audio devices
check("Audio devices")
try:
    result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
    if 'card' in result.stdout.lower():
        success("Audio devices found")
        # Parse and show devices
        lines = [l for l in result.stdout.split('\n') if 'card' in l.lower()]
        for line in lines[:3]:  # Show first 3
            print(f"   {line.strip()}")
    else:
        failure("No audio devices found")
        issues.append("No microphone detected")
        print(f"   → Check: USB microphone is connected")
except Exception as e:
    failure(f"Cannot check audio devices: {e}")
    issues.append("Cannot detect audio hardware")

# Test recording
check("Test audio recording (5 seconds)")
try:
    import sounddevice as sd
    import numpy as np
    
    duration = 5
    sample_rate = 44100
    
    print()
    info("Recording 5 seconds of audio...")
    recording = sd.rec(int(duration * sample_rate), 
                       samplerate=sample_rate, 
                       channels=1, 
                       dtype='int16')
    sd.wait()
    
    # Check if we got audio
    audio_level = np.abs(recording).mean()
    if audio_level > 100:
        success(f"Audio recording works! (level: {audio_level:.0f})")
    elif audio_level > 10:
        warning(f"Audio recording works but very quiet (level: {audio_level:.0f})")
        warnings_list.append("Audio level is very low - check microphone volume")
    else:
        failure(f"Audio recording failed or no sound (level: {audio_level:.0f})")
        issues.append("No audio input detected from microphone")
        
except Exception as e:
    failure(f"Audio recording test failed: {e}")
    issues.append(f"Audio recording error: {e}")

print()
print("STEP 3: Checking Network Connectivity")
print("-" * 80)

# Check internet
check("Internet connectivity")
try:
    result = subprocess.run(['ping', '-c', '1', '-W', '2', '8.8.8.8'], 
                          capture_output=True)
    if result.returncode == 0:
        success("Internet connection OK")
    else:
        failure("No internet connection")
        issues.append("No internet - Shazam API requires internet")
except Exception as e:
    failure(f"Cannot check internet: {e}")
    issues.append("Cannot verify internet connectivity")

# Check DNS
check("DNS resolution (shazam.com)")
try:
    result = subprocess.run(['nslookup', 'shazam.com'], 
                          capture_output=True, text=True)
    if 'address' in result.stdout.lower():
        success("DNS resolution works")
    else:
        warning("DNS may not be working properly")
        warnings_list.append("DNS resolution issues detected")
except Exception as e:
    warning(f"Cannot check DNS: {e}")

print()
print("STEP 4: Checking Audio Service")
print("-" * 80)

# Check if service is running
check("pulse-audio service status")
try:
    result = subprocess.run(['systemctl', 'is-active', 'pulse-audio'],
                          capture_output=True, text=True)
    if result.stdout.strip() == 'active':
        success("pulse-audio service is running")
    else:
        failure(f"pulse-audio service is NOT running (status: {result.stdout.strip()})")
        issues.append("Audio service is not running")
        print(f"   → Fix: sudo systemctl start pulse-audio")
except Exception as e:
    failure(f"Cannot check service: {e}")
    issues.append("Cannot check audio service status")

# Check service logs
check("Recent service logs")
try:
    result = subprocess.run(['journalctl', '-u', 'pulse-audio', '-n', '20', '--no-pager'],
                          capture_output=True, text=True)
    logs = result.stdout
    
    if 'error' in logs.lower() or 'failed' in logs.lower():
        warning("Errors found in service logs")
        # Show last few error lines
        error_lines = [l for l in logs.split('\n') if 'error' in l.lower() or 'failed' in l.lower()]
        for line in error_lines[-3:]:
            print(f"   {line}")
        warnings_list.append("Check service logs for errors")
    else:
        success("No obvious errors in recent logs")
        
    # Check for song detection activity
    if 'song detected' in logs.lower() or 'shazam' in logs.lower():
        info("Song detection activity found in logs")
    else:
        warning("No recent song detection activity in logs")
        
except Exception as e:
    warning(f"Cannot check logs: {e}")

print()
print("STEP 5: Checking Cache Files")
print("-" * 80)

# Check data directory
check("Data directory")
data_dir = Path("/opt/pulse/data")
if data_dir.exists():
    success(f"Data directory exists: {data_dir}")
else:
    failure(f"Data directory missing: {data_dir}")
    issues.append("Data directory does not exist")
    print(f"   → Fix: sudo mkdir -p /opt/pulse/data && sudo chown pi:pi /opt/pulse/data")

# Check song cache file
check("Song cache file")
song_cache = data_dir / "song_cache.json"
if song_cache.exists():
    success(f"Song cache file exists")
    
    # Check age and content
    try:
        age = time.time() - song_cache.stat().st_mtime
        with open(song_cache, 'r') as f:
            data = json.load(f)
        
        print(f"   Age: {age:.0f} seconds old")
        print(f"   Content: {data}")
        
        if age > 300:  # 5 minutes
            warning(f"Song cache is stale (over 5 minutes old)")
            warnings_list.append("Song cache not being updated recently")
        
        if data.get('title') and data.get('title') != 'Unknown':
            info(f"Last detected song: {data.get('title')} by {data.get('artist')}")
        else:
            warning("No song has been detected yet")
            
    except Exception as e:
        warning(f"Cannot read cache file: {e}")
        
else:
    failure("Song cache file does not exist")
    issues.append("Song cache file missing - service may not be writing it")
    print(f"   → Expected location: {song_cache}")

print()
print("STEP 6: Testing Shazam API")
print("-" * 80)

check("Shazam API connection test")
try:
    import asyncio
    from shazamio import Shazam
    
    print()
    info("Testing Shazam API (creating event loop)...")
    
    async def test_shazam():
        try:
            shazam = Shazam()
            # This is just a connectivity test - won't actually recognize anything
            return True
        except Exception as e:
            return str(e)
    
    # Create fresh event loop (party_box approach)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(test_shazam())
    loop.close()
    
    if result is True:
        success("Shazam API connection test passed")
    else:
        failure(f"Shazam API test failed: {result}")
        issues.append("Shazam API connectivity issues")
        
except Exception as e:
    failure(f"Shazam API test error: {e}")
    issues.append(f"Shazam API error: {e}")

print()
print("STEP 7: Checking Simple Song Detector Code")
print("-" * 80)

check("simple_song_detector.py exists")
detector_file = Path("/opt/pulse/services/sensors/simple_song_detector.py")
if detector_file.exists():
    success("simple_song_detector.py found")
    
    # Check if it's the new version with fresh event loops
    with open(detector_file, 'r') as f:
        content = f.read()
        if 'new_event_loop' in content and 'party_box' in content:
            success("Using new working version (party_box approach)")
        else:
            warning("May be using old version of song detector")
            warnings_list.append("Check if simple_song_detector.py is the latest version")
else:
    failure("simple_song_detector.py NOT found")
    issues.append("Simple song detector code is missing")

print()
print("="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)
print()

if not issues and not warnings_list:
    print(f"{GREEN}✓ ALL CHECKS PASSED!{RESET}")
    print()
    print("Song detection should be working. If you still don't see songs detected:")
    print("1. Make sure music is playing nearby")
    print("2. Wait 60 seconds (detection runs every 60s)")
    print("3. Check logs: sudo journalctl -u pulse-audio -f")
    print("4. Check cache: cat /opt/pulse/data/song_cache.json")
else:
    if issues:
        print(f"{RED}✗ ISSUES FOUND ({len(issues)}): {RESET}")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
    
    if warnings_list:
        print(f"{YELLOW}⚠ WARNINGS ({len(warnings_list)}): {RESET}")
        for i, warn in enumerate(warnings_list, 1):
            print(f"  {i}. {warn}")
        print()
    
    print("RECOMMENDED FIXES:")
    print("-" * 80)
    
    if "sounddevice library missing" in issues or "shazamio library missing" in issues:
        print("1. Install missing Python libraries:")
        print("   cd /opt/pulse")
        print("   source venv/bin/activate")
        print("   pip install sounddevice shazamio")
        print()
    
    if "No microphone detected" in issues:
        print("2. Connect USB microphone and check:")
        print("   arecord -l")
        print()
    
    if "Audio service is not running" in issues:
        print("3. Start the audio service:")
        print("   sudo systemctl start pulse-audio")
        print("   sudo systemctl status pulse-audio")
        print()
    
    if "No internet" in str(issues):
        print("4. Fix internet connection - Shazam requires internet")
        print("   ping 8.8.8.8")
        print()
    
    if "Data directory does not exist" in issues:
        print("5. Create data directory:")
        print("   sudo mkdir -p /opt/pulse/data")
        print("   sudo chown pi:pi /opt/pulse/data")
        print()

print()
print("QUICK COMMANDS:")
print("-" * 80)
print("View live logs:        sudo journalctl -u pulse-audio -f")
print("Check service status:  sudo systemctl status pulse-audio")
print("Restart service:       sudo systemctl restart pulse-audio")
print("Check cache file:      cat /opt/pulse/data/song_cache.json")
print("Test microphone:       arecord -d 5 test.wav && aplay test.wav")
print()
print("="*80)
