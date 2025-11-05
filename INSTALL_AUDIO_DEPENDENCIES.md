# Audio Dependencies Installation Guide

This guide ensures dB reading and song detection work on **ANY** Python version and platform.

## Automatic Installation (Recommended)

Run the comprehensive fix script:

```bash
cd /workspace  # or /opt/pulse
sudo ./fix_audio_forever.sh
```

This script:
- ✅ Detects Python version automatically
- ✅ Installs system audio packages
- ✅ Handles Python 3.13+ compatibility
- ✅ Installs ShazamIO with retry logic
- ✅ Verifies all installations
- ✅ Tests AudioMonitor functionality

## Manual Installation

### 1. System Packages

```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    libasound2-dev \
    python3-numpy \
    python3-pyaudio
```

### 2. Python Packages

For **Python 3.12 and earlier**:
```bash
pip3 install numpy sounddevice shazamio aiohttp
```

For **Python 3.13+** (audioop removed from stdlib):
```bash
pip3 install numpy sounddevice shazamio aiohttp audioop-lts
```

### 3. Raspberry Pi Specific

Add `--break-system-packages` flag:
```bash
pip3 install --break-system-packages numpy sounddevice shazamio aiohttp audioop-lts
```

## Verification

Test that everything works:

```bash
cd /opt/pulse
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from services.sensors.mic_song_detect import AudioMonitor

# Test initialization
m = AudioMonitor()
print(f"✓ Device: {m.device_index}")
print(f"✓ Song detector: {m.song_detector is not None}")

# Test monitoring (5 seconds)
m.start_monitoring()
import time
time.sleep(5)
stats = m.get_stats()
print(f"✓ dB: {stats['current_db']:.1f}")
m.cleanup()
print("✓ All working!")
EOF
```

## Troubleshooting

### Issue: "No audio backend available"

**Solution:**
```bash
pip3 install --break-system-packages sounddevice pyaudio
```

### Issue: "No module named 'audioop'" (Python 3.13+)

**Solution:**
```bash
pip3 install --break-system-packages audioop-lts
```

### Issue: "No module named 'shazamio'"

**Solution:**
```bash
pip3 install --break-system-packages shazamio aiohttp
```

### Issue: "Audio device busy"

**Solution:**
```bash
# Kill processes using audio
sudo fuser -k /dev/snd/*

# Restart PulseAudio
pulseaudio --kill
pulseaudio --start
```

### Issue: dB readings stuck at 0.0

**Causes:**
1. Microphone not connected
2. Wrong audio device selected
3. PulseAudio/PipeWire conflict

**Solution:**
```bash
# Check available devices
arecord -l

# Test recording
arecord -d 3 test.wav
aplay test.wav
rm test.wav
```

## Python Version Compatibility

| Python Version | audioop Source | Notes |
|----------------|----------------|-------|
| 3.11 and earlier | stdlib | No extra packages needed |
| 3.12 | stdlib | No extra packages needed |
| 3.13+ | audioop-lts | **Must install audioop-lts** |

## Dependencies Explained

### Core Audio
- **numpy** - Fast audio processing
- **sounddevice** - Cross-platform audio I/O
- **pyaudio** - Alternative audio backend

### Song Detection
- **shazamio** - Shazam API client
- **aiohttp** - Async HTTP for Shazam
- **audioop-lts** - Audio operations (Python 3.13+)

### System Libraries
- **portaudio19-dev** - PortAudio development files
- **libasound2-dev** - ALSA development files

## Success Indicators

When everything is working, you should see:

```
✓ AudioMonitor imports successfully
✓ AudioMonitor initialized
  - Device index: 2
  - Song detector: Enabled
✓ dB: 54.3
```

## Still Having Issues?

Run the diagnostic:
```bash
cd /opt/pulse
python3 -c "
import sys
sys.path.insert(0, '.')

# Check imports
try:
    import numpy
    print('✓ numpy')
except ImportError as e:
    print(f'✗ numpy: {e}')

try:
    import sounddevice
    print('✓ sounddevice')
except ImportError as e:
    print(f'✗ sounddevice: {e}')

try:
    import shazamio
    print('✓ shazamio')
except ImportError as e:
    print(f'✗ shazamio: {e}')

# Check AudioMonitor
try:
    from services.sensors.mic_song_detect import AudioMonitor
    print('✓ AudioMonitor')
except ImportError as e:
    print(f'✗ AudioMonitor: {e}')
"
```

Report any `✗` marks and the error messages.
