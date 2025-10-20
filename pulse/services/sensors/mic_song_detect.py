#!/usr/bin/env python3
import asyncio
import json
import random
from pathlib import Path
from datetime import datetime

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'
DATA_DIR = Path('/opt/pulse/data/sensors')
SONG_FILE = DATA_DIR / 'song.json'
AUDIO_LEVEL_FILE = DATA_DIR / 'audio_level.txt'

def _read_hardware_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text())
    except Exception:
        return {}

def _module_present(status: dict, module: str) -> bool:
    """Return True if hardware module is present, supporting old and new schemas.

    Defaults to True when unknown so the simulation continues in dev.
    """
    # New schema: { "modules": { "mic": { "present": true } } }
    try:
        modules = status.get('modules') or {}
        mod = modules.get(module) or {}
        if isinstance(mod, dict) and 'present' in mod:
            return bool(mod.get('present'))
    except Exception:
        pass
    # Old schema: { "mic": true } or null/undefined when unknown
    value = status.get(module)
    if value is None:
        return True
    return bool(value)

async def has_mic() -> bool:
    status = _read_hardware_status()
    return _module_present(status, 'mic')

# Sample songs for demo
SAMPLE_SONGS = [
    {"title": "Bohemian Rhapsody", "artist": "Queen"},
    {"title": "Hotel California", "artist": "Eagles"},
    {"title": "Billie Jean", "artist": "Michael Jackson"},
    {"title": "Sweet Child O' Mine", "artist": "Guns N' Roses"},
    {"title": "Smells Like Teen Spirit", "artist": "Nirvana"},
    {"title": "Wonderwall", "artist": "Oasis"},
    {"title": "Mr. Brightside", "artist": "The Killers"},
    {"title": "Don't Stop Believin'", "artist": "Journey"},
    {"title": "September", "artist": "Earth, Wind & Fire"},
    {"title": "Uptown Funk", "artist": "Mark Ronson ft. Bruno Mars"},
]

async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    song_index = 0
    song_duration = 0
    
    while True:
        has_audio = await has_mic()
        
        if has_audio:
            # Simulate audio level (decibels)
            hour = datetime.now().hour
            
            # Louder during peak hours
            if 18 <= hour <= 23:
                base_db = random.uniform(75, 88)
            elif 12 <= hour < 18:
                base_db = random.uniform(65, 78)
            else:
                base_db = random.uniform(50, 65)
            
            # Add variations
            db_level = base_db + random.uniform(-3, 3)
            AUDIO_LEVEL_FILE.write_text(f"{db_level:.1f}")
            
            # Song detection (simulate detecting a new song every 3-4 minutes)
            song_duration += 3
            
            if song_duration >= random.randint(180, 240):  # 3-4 minutes
                song_duration = 0
                song_index = (song_index + 1) % len(SAMPLE_SONGS)
            
            # Randomly "detect" or "not detect" song (85% detection rate)
            detected = random.random() < 0.85
            
            if detected and song_duration < 200:  # Don't detect at end of song
                song_data = {
                    "title": SAMPLE_SONGS[song_index]["title"],
                    "artist": SAMPLE_SONGS[song_index]["artist"],
                    "detected": True,
                    "timestamp": datetime.now().isoformat()
                }
                print(f"[Mic] 🎵 Detected: {song_data['title']} by {song_data['artist']}, Audio: {db_level:.1f}dB")
            else:
                song_data = {
                    "title": "No song detected",
                    "artist": "",
                    "detected": False,
                    "timestamp": datetime.now().isoformat()
                }
                print(f"[Mic] No song detected, Audio: {db_level:.1f}dB")
            
            SONG_FILE.write_text(json.dumps(song_data, indent=2))
        else:
            # No microphone available
            AUDIO_LEVEL_FILE.write_text("0.0")
            song_data = {
                "title": "No song detected",
                "artist": "",
                "detected": False,
                "timestamp": datetime.now().isoformat()
            }
            SONG_FILE.write_text(json.dumps(song_data, indent=2))
            print("[Mic] Microphone not available")
        
        await asyncio.sleep(3)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
