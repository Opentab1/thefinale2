# 🏗️ Pulse System - Code Architecture & Flow

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PULSE SYSTEM ARCHITECTURE                    │
│                    (3 Independent Services)                     │
└─────────────────────────────────────────────────────────────────┘

        ┌────────────────────────────────────────┐
        │   pulse.service (systemd target)       │
        │   Coordinates all 3 services           │
        └────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ pulse-audio  │  │ pulse-camera │  │ pulse-hub    │
│   .service   │  │   .service   │  │ -main.service│
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│run_audio_    │  │run_camera_   │  │run_hub_      │
│service.py    │  │service.py    │  │service.py    │
│(165 lines)   │  │(157 lines)   │  │(143 lines)   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        ▼                ▼                ▼
   Audio Only       Camera Only      Hub + Sensors
   
        │                │                │
        └────────┬───────┴────────────────┘
                 ▼
        ┌────────────────────────────────┐
        │  /opt/pulse/data/ (cache)      │
        │  - decibel_cache.json          │
        │  - song_cache.json             │
        │  - camera_cache.json           │
        └────────────────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────┐
        │    Dashboard (port 5000)       │
        │    React UI + Flask API        │
        └────────────────────────────────┘
```

---

## 🎯 Service #1: Audio Service

### Entry Point: `run_audio_service.py` (165 lines)

**What it does:**
- Runs audio detection ONLY
- Independent of camera and hub
- Writes data to cache files every 5 seconds

**Flow:**
```
run_audio_service.py
    │
    ├──> Initialize DecibelDetector (every 10s)
    │    └──> services/sensors/simple_decibel_detector.py (216 lines)
    │         └──> Reads microphone audio
    │         └──> Calculates dB level
    │         └──> Returns: current_db (float)
    │
    ├──> Initialize SongDetector (every 60s)
    │    └──> services/sensors/simple_song_detector.py (296 lines)
    │         └──> Records 5 seconds of audio
    │         └──> Creates FRESH event loop
    │         └──> Calls Shazam API
    │         └──> Closes event loop
    │         └──> Returns: {title, artist, timestamp}
    │
    └──> Main Loop (every 5 seconds):
         ├──> Read current dB from DecibelDetector
         ├──> Read latest song from SongDetector
         ├──> Write to /opt/pulse/data/decibel_cache.json
         ├──> Write to /opt/pulse/data/song_cache.json
         └──> Repeat forever
```

**Key Files:**
- `run_audio_service.py` - Entry point (165 lines)
- `services/sensors/simple_decibel_detector.py` - dB reading (216 lines)
- `services/sensors/simple_song_detector.py` - Song detection (296 lines)

**Cache Files Written:**
```json
// /opt/pulse/data/decibel_cache.json
{
  "db": 65.2,
  "timestamp": 1699564821.5
}

// /opt/pulse/data/song_cache.json
{
  "title": "Bohemian Rhapsody",
  "artist": "Queen",
  "timestamp": 1699564821.5
}
```

---

## 🎯 Service #2: Camera Service

### Entry Point: `run_camera_service.py` (157 lines)

**What it does:**
- Runs people counting ONLY
- Independent of audio and hub
- Writes data to cache files every 5 seconds

**Flow:**
```
run_camera_service.py
    │
    ├──> Initialize PeopleCounter
    │    └──> services/sensors/camera_people.py
    │         └──> Opens camera
    │         └──> Runs AI person detection
    │         └──> Tracks people entering/exiting
    │         └──> Returns: people_count (int)
    │
    └──> Main Loop (every 5 seconds):
         ├──> Read current count from PeopleCounter
         ├──> Write to /opt/pulse/data/camera_cache.json
         └──> Repeat forever
```

**Key Files:**
- `run_camera_service.py` - Entry point (157 lines)
- `services/sensors/camera_people.py` - People counting
- `services/sensors/person_detector.py` - AI detection
- `services/sensors/tracker/person_tracker.py` - Tracking logic

**Cache File Written:**
```json
// /opt/pulse/data/camera_cache.json
{
  "people_count": 5,
  "timestamp": 1699564821.5
}
```

**Why Separate?**
Camera crashes every 1-2 minutes due to libcamera bug. By separating it:
- Camera crash doesn't kill audio
- Camera restarts independently
- Other services keep running

---

## 🎯 Service #3: Hub Service

### Entry Point: `run_hub_service.py` (143 lines)

**What it does:**
- Orchestrates everything
- Reads cache files from audio/camera services
- Runs environmental sensors (temp, light, etc.)
- Serves dashboard API
- Stores data in database
- Runs automation rules

**Flow:**
```
run_hub_service.py
    │
    └──> Initialize PulseHub
         └──> services/hub/main.py (1,085 lines)
              │
              ├──> Initialize Environmental Sensors:
              │    ├──> BME280 (temperature/humidity/pressure)
              │    ├──> Light sensor
              │    └──> Pan/tilt controller
              │
              ├──> Initialize Controllers (if configured):
              │    ├──> HVAC (Nest thermostat)
              │    ├──> Lighting (Philips Hue)
              │    ├──> TV (CEC control)
              │    └──> Music (Spotify)
              │
              ├──> Initialize Database:
              │    └──> services/storage/db.py
              │         └──> SQLite database
              │         └──> Stores all sensor readings
              │
              ├──> Start Flask API (port 5000):
              │    └──> Serves dashboard data
              │    └──> WebSocket for real-time updates
              │
              └──> Main Data Collection Loop (every 5 seconds):
                   │
                   ├──> Check if audio/camera disabled:
                   │    └──> If PULSE_DISABLE_AUDIO=1:
                   │         └──> Read /opt/pulse/data/decibel_cache.json
                   │         └──> Read /opt/pulse/data/song_cache.json
                   │    └──> If PULSE_DISABLE_CAMERA=1:
                   │         └──> Read /opt/pulse/data/camera_cache.json
                   │
                   ├──> Read environmental sensors:
                   │    └──> Temperature, humidity, pressure
                   │    └──> Light level
                   │
                   ├──> Combine all data:
                   │    └──> {
                   │         temperature, humidity, pressure,
                   │         light_level, people_count,
                   │         db_level, current_song
                   │        }
                   │
                   ├──> Store in database
                   │
                   ├──> Send to dashboard (WebSocket)
                   │
                   ├──> Run automation rules:
                   │    ├──> If people > 0 → turn on lights
                   │    ├──> If temp > X → adjust HVAC
                   │    └──> If occupancy pattern → trigger scenes
                   │
                   └──> Repeat forever
```

**Key Files:**
- `run_hub_service.py` - Entry point (143 lines)
- `services/hub/main.py` - Main orchestrator (1,085 lines)
- `services/storage/db.py` - Database
- `services/sensors/bme280_reader.py` - Temperature sensor
- `services/sensors/light_level.py` - Light sensor
- `services/controls/*.py` - Smart home controllers

---

## 🔄 Complete Data Flow

### Step-by-Step Flow:

```
1. AUDIO SERVICE (pulse-audio.service)
   ↓
   Microphone → DecibelDetector → 65.2 dB
   Microphone → SongDetector → "Bohemian Rhapsody" by Queen
   ↓
   Write to cache files:
   - /opt/pulse/data/decibel_cache.json
   - /opt/pulse/data/song_cache.json

2. CAMERA SERVICE (pulse-camera.service)
   ↓
   Camera → PeopleCounter → 5 people
   ↓
   Write to cache file:
   - /opt/pulse/data/camera_cache.json

3. HUB SERVICE (pulse-hub-main.service)
   ↓
   Read cache files:
   - decibel_cache.json → 65.2 dB
   - song_cache.json → "Bohemian Rhapsody"
   - camera_cache.json → 5 people
   ↓
   Read direct sensors:
   - BME280 → 72°F, 45% humidity
   - Light sensor → 250 lux
   ↓
   Combine all data:
   {
     temperature: 72,
     humidity: 45,
     light: 250,
     people: 5,
     db: 65.2,
     song: "Bohemian Rhapsody by Queen"
   }
   ↓
   Store in database (SQLite)
   ↓
   Send to dashboard via WebSocket
   ↓
   Dashboard displays real-time data

4. USER VIEWS DASHBOARD
   ↓
   Browser → http://pi-ip:5000
   ↓
   React UI fetches data from Flask API
   ↓
   Displays:
   - Current temperature/humidity
   - People count
   - Decibel level
   - Current song playing
   - Light level
   - Historical graphs
```

---

## 🗂️ File Structure

```
/workspace/
│
├── run_audio_service.py       (165 lines) ← Audio service entry
├── run_camera_service.py      (157 lines) ← Camera service entry
├── run_hub_service.py         (143 lines) ← Hub service entry
├── run_pulse_system.py        ← Legacy monolithic entry
│
├── services/
│   │
│   ├── sensors/               ← All sensor code
│   │   ├── simple_decibel_detector.py   (216 lines) ✨ WORKING
│   │   ├── simple_song_detector.py      (296 lines) ✨ WORKING
│   │   ├── camera_people.py             ← People counter
│   │   ├── bme280_reader.py             ← Temperature sensor
│   │   ├── light_level.py               ← Light sensor
│   │   ├── person_detector.py           ← AI person detection
│   │   ├── tracker/
│   │   │   └── person_tracker.py        ← Person tracking
│   │   └── obsolete/
│   │       ├── mic_song_detect.py       (841 lines) ❌ OLD
│   │       └── song_detector.py         (729 lines) ❌ OLD
│   │
│   ├── hub/
│   │   └── main.py            (1,085 lines) ← Orchestrator
│   │
│   ├── storage/
│   │   └── db.py              ← Database (SQLite)
│   │
│   ├── controls/              ← Smart home controllers
│   │   ├── hvac_nest.py       ← Nest thermostat
│   │   ├── lighting_hue.py    ← Philips Hue
│   │   ├── music_spotify.py   ← Spotify
│   │   └── tv_cec.py          ← TV control
│   │
│   └── systemd/               ← Service files
│       ├── pulse.service               ← Master coordinator
│       ├── pulse-audio.service         ← Audio service
│       ├── pulse-camera.service        ← Camera service
│       └── pulse-hub-main.service      ← Hub service
│
├── dashboard/                 ← Web UI
│   ├── ui/                    ← React frontend
│   └── api/                   ← Flask backend
│
└── config/
    └── config.yaml            ← System configuration
```

---

## 💡 Key Design Principles

### 1. **Service Separation (Fault Isolation)**
```
Old: One process → Camera crash = everything dies
New: Three processes → Camera crash = only camera restarts
```

### 2. **Cache File Communication (Simple IPC)**
```
Old: Shared memory → Race conditions, complex
New: JSON cache files → Simple, reliable, debuggable
```

### 3. **Fresh Event Loops (Party Box Approach)**
```python
# OLD (BROKEN - stale after 10 min):
loop = asyncio.get_event_loop()  # Reuse same loop
result = await loop.run_until_complete(task)

# NEW (WORKING - fresh every time):
loop = asyncio.new_event_loop()  # Fresh loop
result = loop.run_until_complete(task)
loop.close()  # Close immediately
```

### 4. **Simple Code**
```
Old: 1,569 lines (complex AudioMonitor)
New: 510 lines (simple detectors)
Reduction: 67%
```

### 5. **Simple Health Monitoring**
```
Old: 300+ lines, 4 watchdogs, false positives
New: 66 lines, check every 60s, restart if dead
```

---

## 🔧 Configuration

### Environment Variables:

```bash
# For separate services mode:
PULSE_DISABLE_AUDIO=1   # Hub won't start audio (reads cache instead)
PULSE_DISABLE_CAMERA=1  # Hub won't start camera (reads cache instead)
```

### Service Files Set These:

```ini
# pulse-hub-main.service
[Service]
Environment="PULSE_DISABLE_AUDIO=1"
Environment="PULSE_DISABLE_CAMERA=1"
# Hub reads from cache files instead

# pulse-audio.service
[Service]
# No disable flags - runs audio directly
# Writes to cache files

# pulse-camera.service  
[Service]
# No disable flags - runs camera directly
# Writes to cache files
```

---

## 📊 Data Structures

### Decibel Data:
```python
{
    "db": 65.2,           # Current decibel level
    "timestamp": 1699564821.5
}
```

### Song Data:
```python
{
    "title": "Bohemian Rhapsody",
    "artist": "Queen",
    "timestamp": 1699564821.5
}
```

### People Count Data:
```python
{
    "people_count": 5,
    "timestamp": 1699564821.5
}
```

### Combined Hub Data (sent to dashboard):
```python
{
    "timestamp": "2025-11-17 15:30:00",
    "temperature": 72.5,
    "humidity": 45.0,
    "pressure": 1013.25,
    "light_level": 250,
    "people_count": 5,
    "db_level": 65.2,
    "current_song": "Bohemian Rhapsody by Queen"
}
```

---

## 🚀 How It Starts

### System Boot Sequence:

```bash
1. Raspberry Pi boots
   ↓
2. systemd starts services:
   ↓
   sudo systemctl start pulse.service
   ↓
   pulse.service (target) starts:
   ├──> pulse-audio.service
   ├──> pulse-camera.service
   └──> pulse-hub-main.service
   ↓
3. Each service runs independently:
   ├──> run_audio_service.py starts
   ├──> run_camera_service.py starts
   └──> run_hub_service.py starts
   ↓
4. Services write cache files
   ↓
5. Hub reads cache files + direct sensors
   ↓
6. Dashboard becomes available at http://pi-ip:5000
```

---

## 🎯 Summary

**What you have:**
- 3 independent services (audio, camera, hub)
- Simple, reliable code (510 lines for audio vs 1,569 old)
- Cache file communication (no complex IPC)
- Fresh event loops (party_box approach)
- Fault isolation (camera crash ≠ audio crash)
- Real-time dashboard
- Database storage
- Smart home automation

**How it works:**
1. Audio service → detects dB + songs → writes cache files
2. Camera service → counts people → writes cache files
3. Hub service → reads cache files + direct sensors → dashboard + database
4. Services run independently
5. If one crashes, others keep running
6. Dashboard always has data (max 5 seconds old)

**Why it works:**
- Simple code
- Separation of concerns
- Fresh event loops (no staleness)
- File-based IPC (reliable)
- Independent services (fault tolerance)

**Total code: ~2,000 lines of clean, working code**
