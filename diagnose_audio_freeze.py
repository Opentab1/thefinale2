#!/usr/bin/env python3
"""
Diagnostic script to identify audio monitoring freeze issues
Run this on your RPI while the system is experiencing the freeze
"""

import subprocess
import time
import json
import sys

def run_cmd(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

print("=" * 80)
print("AUDIO MONITORING DIAGNOSTIC TOOL")
print("=" * 80)
print()

# 1. Check if the process is running
print("1. CHECKING PULSE SERVICE STATUS...")
print("-" * 80)
status = run_cmd("systemctl status pulse-hub.service --no-pager -l | tail -20")
print(status)
print()

# 2. Check for Python processes
print("2. CHECKING PYTHON PROCESSES...")
print("-" * 80)
processes = run_cmd("ps aux | grep -E '(pulse|mic_song)' | grep -v grep")
print(processes)
print()

# 3. Check recent logs for audio issues
print("3. RECENT AUDIO LOGS (last 50 lines)...")
print("-" * 80)
logs = run_cmd("journalctl -u pulse-hub.service -n 50 --no-pager")
print(logs)
print()

# 4. Check for hanging threads
print("4. CHECKING FOR THREAD ISSUES...")
print("-" * 80)
pid = run_cmd("pgrep -f 'pulse.*hub' | head -1")
if pid and pid != "ERROR":
    thread_info = run_cmd(f"ps -T -p {pid} | wc -l")
    print(f"Process {pid} has {thread_info} threads")
    thread_details = run_cmd(f"ps -T -p {pid}")
    print(thread_details)
else:
    print("Pulse hub process not found!")
print()

# 5. Check file descriptors (potential leak)
print("5. CHECKING FILE DESCRIPTOR USAGE...")
print("-" * 80)
if pid and pid != "ERROR":
    fd_count = run_cmd(f"ls -1 /proc/{pid}/fd 2>/dev/null | wc -l")
    print(f"Process {pid} has {fd_count} open file descriptors")
    fd_details = run_cmd(f"ls -l /proc/{pid}/fd 2>/dev/null | grep -E '(socket|pipe)' | wc -l")
    print(f"  - {fd_details} sockets/pipes")
else:
    print("Cannot check FDs - process not found")
print()

# 6. Check network connections (for Shazam API)
print("6. CHECKING NETWORK CONNECTIONS...")
print("-" * 80)
if pid and pid != "ERROR":
    connections = run_cmd(f"lsof -p {pid} -a -i | grep -v LISTEN")
    if connections:
        print(connections)
    else:
        print("No active network connections")
else:
    print("Cannot check connections - process not found")
print()

# 7. Check audio device status
print("7. CHECKING AUDIO DEVICE STATUS...")
print("-" * 80)
audio_devices = run_cmd("arecord -l")
print(audio_devices)
print()

# 8. Test audio recording
print("8. TESTING AUDIO RECORDING (3 seconds)...")
print("-" * 80)
test_result = run_cmd("timeout 3 arecord -d 1 -f S16_LE -r 44100 /tmp/test_audio.wav 2>&1 && echo 'SUCCESS' || echo 'FAILED'")
print(test_result)
print()

# 9. Check memory usage
print("9. CHECKING MEMORY USAGE...")
print("-" * 80)
memory = run_cmd("free -h")
print(memory)
if pid and pid != "ERROR":
    proc_mem = run_cmd(f"ps -p {pid} -o %mem,rss,vsz,cmd --no-headers")
    print(f"\nPulse process memory: {proc_mem}")
print()

# 10. Check for specific error patterns in logs
print("10. CHECKING FOR KNOWN ERROR PATTERNS...")
print("-" * 80)
error_patterns = [
    ("Resource leak warnings", "journalctl -u pulse-hub.service --since '10 minutes ago' | grep -i 'leak\\|unclosed\\|resource'"),
    ("Audio stream errors", "journalctl -u pulse-hub.service --since '10 minutes ago' | grep -i 'stream\\|audio.*error\\|failed.*read'"),
    ("Song detection errors", "journalctl -u pulse-hub.service --since '10 minutes ago' | grep -i 'shazam\\|song.*detect\\|recognition'"),
    ("Timeout/hanging", "journalctl -u pulse-hub.service --since '10 minutes ago' | grep -i 'timeout\\|hang\\|stall\\|stuck'"),
    ("AsyncIO errors", "journalctl -u pulse-hub.service --since '10 minutes ago' | grep -i 'asyncio\\|event.*loop\\|coroutine'"),
]

for pattern_name, cmd in error_patterns:
    result = run_cmd(cmd)
    if result and result != "ERROR" and len(result) > 0:
        print(f"\n{pattern_name}:")
        print(result[:500])  # Limit output
print()

# 11. Check timestamps of last activity
print("11. CHECKING LAST AUDIO ACTIVITY TIMESTAMPS...")
print("-" * 80)
last_db = run_cmd("journalctl -u pulse-hub.service --since '20 minutes ago' | grep '🔊 Audio:' | tail -5")
if last_db:
    print("Recent dB readings:")
    print(last_db)
else:
    print("⚠️ NO RECENT dB READINGS FOUND - This confirms the freeze!")

last_song = run_cmd("journalctl -u pulse-hub.service --since '30 minutes ago' | grep '🎵\\|Song detected' | tail -3")
if last_song:
    print("\nRecent song detections:")
    print(last_song)
else:
    print("\n⚠️ NO RECENT SONG DETECTIONS")
print()

print("=" * 80)
print("DIAGNOSTIC COMPLETE")
print("=" * 80)
print()
print("NEXT STEPS:")
print("1. Copy this output and share with the developer")
print("2. If you see 'NO RECENT dB READINGS', the freeze is confirmed")
print("3. Check for error patterns above to identify root cause")
print("4. The fix will be applied to /workspace/services/sensors/mic_song_detect.py")
print()
