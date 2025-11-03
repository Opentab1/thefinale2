#!/usr/bin/env python3
"""
Quick diagnostic and fix script for DB reader and song detection issues
"""

import sys
import os
import sqlite3
import traceback
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("="*80)
print("QUICK DIAGNOSTIC - DB Reader & Song Detection")
print("="*80)

# 1. Check Database
print("\n1. Checking Database Connection...")
try:
    from services.storage.db import PulseDB
    db = PulseDB()
    print(f"  ✓ Database path: {db.db_path}")
    
    # Test connection
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sensor_readings")
        count = cursor.fetchone()[0]
        print(f"  ✓ Database connection OK ({count} sensor readings)")
        
    # Check if database is locked
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT 1")
            cursor.execute("COMMIT")
        print("  ✓ Database is not locked")
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print(f"  ✗ Database is LOCKED: {e}")
            print("  → Fix: Close other processes accessing the database")
        else:
            print(f"  ✗ Database error: {e}")
except Exception as e:
    print(f"  ✗ Database check failed: {e}")
    traceback.print_exc()

# 2. Check Song Detection Dependencies
print("\n2. Checking Song Detection Dependencies...")
try:
    # Check ShazamIO
    try:
        from shazamio import Shazam
        print("  ✓ ShazamIO installed")
    except ImportError:
        print("  ✗ ShazamIO NOT installed")
        print("  → Fix: pip install shazamio aiohttp")
    
    # Check sounddevice
    try:
        import sounddevice as sd
        print("  ✓ sounddevice installed")
    except ImportError:
        print("  ✗ sounddevice NOT installed")
        print("  → Fix: pip install sounddevice")
    
    # Check numpy
    try:
        import numpy as np
        print("  ✓ numpy installed")
    except ImportError:
        print("  ✗ numpy NOT installed")
        print("  → Fix: pip install numpy")
    
    # Check pyaudio
    try:
        import pyaudio
        print("  ✓ pyaudio installed")
    except ImportError:
        print("  ⚠ pyaudio not installed (optional, sounddevice is fallback)")
except Exception as e:
    print(f"  ✗ Dependency check failed: {e}")

# 3. Check Audio Monitor
print("\n3. Checking Audio Monitor...")
try:
    from services.sensors.mic_song_detect import AudioMonitor
    print("  ✓ AudioMonitor class importable")
    
    # Try to initialize
    try:
        monitor = AudioMonitor()
        print("  ✓ AudioMonitor initialized")
        print(f"  - Song detector: {'Available' if monitor.song_detector else 'Not available'}")
        print(f"  - Device index: {monitor.device_index}")
    except Exception as e:
        print(f"  ✗ AudioMonitor initialization failed: {e}")
        print(f"  → Error type: {type(e).__name__}")
except Exception as e:
    print(f"  ✗ AudioMonitor check failed: {e}")
    traceback.print_exc()

# 4. Check Network (for Shazam)
print("\n4. Checking Network Connectivity (for Shazam)...")
try:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(('api.shazam.com', 443))
    sock.close()
    if result == 0:
        print("  ✓ Can reach Shazam API (port 443)")
    else:
        print("  ✗ Cannot reach Shazam API - network issue")
except Exception as e:
    print(f"  ✗ Network check failed: {e}")

# 5. Check Database File Permissions
print("\n5. Checking Database File Permissions...")
try:
    db_path = "/opt/pulse/data/pulse.db"
    if os.path.exists(db_path):
        if os.access(db_path, os.W_OK):
            print(f"  ✓ Database file is writable: {db_path}")
        else:
            print(f"  ✗ Database file is NOT writable: {db_path}")
            print("  → Fix: Check file permissions")
    else:
        # Check if directory exists
        db_dir = os.path.dirname(db_path)
        if os.path.exists(db_dir):
            if os.access(db_dir, os.W_OK):
                print(f"  ✓ Database directory is writable: {db_dir}")
            else:
                print(f"  ✗ Database directory is NOT writable: {db_dir}")
        else:
            print(f"  ⚠ Database directory does not exist: {db_dir}")
except Exception as e:
    print(f"  ✗ Permission check failed: {e}")

print("\n" + "="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
