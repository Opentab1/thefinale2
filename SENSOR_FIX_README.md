# Pulse Sensor Fix - Complete Guide

## Problem Summary

After starting Pulse, these features work:
- ✅ People detection
- ✅ Live camera  
- ✅ Lux level (light sensor)

But these don't work:
- ❌ Temperature (BME280)
- ❌ dB reader (audio level)
- ❌ Song detection

## Root Causes Identified

1. **Missing Python libraries**: `pyaudio`, `sounddevice`, `shazamio`, `adafruit-bme280`
2. **Missing system tools**: `i2c-tools`, `alsa-utils`
3. **I2C interface**: May not be enabled for BME280
4. **Audio configuration**: ALSA not configured for USB microphone

## Quick Fix (Recommended)

Run the comprehensive fix script:

```bash
sudo bash /workspace/fix_sensors.sh
```

This script will:
1. Install all system dependencies (i2c-tools, alsa-utils, audio libraries)
2. Enable I2C interface for BME280 sensor
3. Configure ALSA for audio input
4. Install all Python dependencies
5. Run comprehensive diagnostics
6. Report what's working and what needs attention

**Time required**: ~5-10 minutes

## After Running the Fix

### If I2C was just enabled (first time setup):
```bash
sudo reboot
```

### Test sensors individually:
```bash
python3 /workspace/test_sensors_comprehensive.py
```

### Start Pulse system:
```bash
bash /workspace/start_pulse.sh
```

## Manual Testing (Optional)

### Test BME280 Temperature Sensor

1. Check I2C connection:
```bash
sudo i2cdetect -y 1
```
Expected: See `76` or `77` in the grid

2. Test Python library:
```bash
python3 -c "import adafruit_bme280; print('BME280 library: OK')"
```

3. Test sensor reading:
```bash
cd /workspace
python3 << 'EOF'
import sys
sys.path.insert(0, '/workspace/services')
from sensors.bme280_reader import BME280Reader

sensor = BME280Reader()
data = sensor.read_sensor()
print(f"Temperature: {data['temperature_f']:.1f}°F")
print(f"Humidity: {data['humidity']:.1f}%")
EOF
```

### Test Audio (dB Reader)

1. List audio devices:
```bash
arecord -l
```
Expected: See at least one capture device

2. Test recording:
```bash
arecord -d 5 -f cd test.wav
aplay test.wav
```

3. Test Python library:
```bash
python3 -c "import pyaudio; print('PyAudio: OK')"
python3 -c "import sounddevice; print('sounddevice: OK')"
```

4. Test audio monitoring:
```bash
cd /workspace
python3 << 'EOF'
import sys
import time
sys.path.insert(0, '/workspace/services')
from sensors.mic_song_detect import AudioMonitor

monitor = AudioMonitor()
monitor.start_monitoring()
time.sleep(10)
print(f"dB level: {monitor.get_current_db():.1f} dB")
monitor.stop_monitoring()
EOF
```

### Test Song Detection

1. Check ShazamIO library:
```bash
python3 -c "import shazamio; print('ShazamIO: OK')"
```

2. Song detection runs automatically when audio monitor is active
   - Requires music playing
   - Requires internet connection
   - Checks every 30 seconds

## Troubleshooting

### BME280 Not Detected

**Symptoms**: `i2cdetect -y 1` shows empty grid

**Solutions**:
1. Check wiring:
   - VCC → 3.3V (Pin 1)
   - GND → GND (Pin 6)
   - SDA → GPIO2 (Pin 3)
   - SCL → GPIO3 (Pin 5)

2. Verify I2C is enabled:
```bash
ls /dev/i2c* # Should show /dev/i2c-1
```

3. Check boot config:
```bash
grep "i2c_arm=on" /boot/firmware/config.txt
# or
grep "i2c_arm=on" /boot/config.txt
```

4. If not enabled, add to boot config:
```bash
echo "dtparam=i2c_arm=on" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

### Audio Not Working

**Symptoms**: No audio devices in `arecord -l`

**Solutions**:
1. Check USB microphone is connected:
```bash
lsusb
```

2. Check for USB audio device:
```bash
cat /proc/asound/cards
```

3. Set USB mic as default:
```bash
# Edit /etc/asound.conf and ensure it's set to hw:1,0
# (or appropriate card number from arecord -l)
```

4. Add user to audio group:
```bash
sudo usermod -a -G audio $USER
# Log out and back in
```

### Song Detection Not Working

**Symptoms**: Audio monitor works but no songs detected

**Possible causes**:
1. **No music playing**: Song detection needs actual music
2. **No internet**: ShazamIO requires internet to identify songs
3. **Volume too low**: Make sure music is audible to microphone
4. **Wrong audio device**: Monitor might be using wrong input

**Test internet connection**:
```bash
ping -c 3 google.com
```

**Check dashboard logs**:
```bash
tail -f /var/log/pulse/hub.log | grep -i song
```

### Permissions Issues

If you get permission errors:

```bash
# Add your user to required groups
sudo usermod -a -G i2c,spi,gpio,audio $USER

# Set proper file permissions
sudo chown -R $USER:$USER /workspace
sudo chmod -R 755 /workspace

# Reboot to apply group changes
sudo reboot
```

## System Requirements

### Hardware
- Raspberry Pi (3, 4, or 5)
- BME280 sensor (I2C connected)
- USB microphone
- Internet connection (for song detection)

### Software
- Raspberry Pi OS (Bookworm or later)
- Python 3.11+
- I2C interface enabled
- Internet connection

## Verification Checklist

After running the fix, verify:

- [ ] `sudo i2cdetect -y 1` shows BME280 (76 or 77)
- [ ] `arecord -l` shows audio capture device
- [ ] `python3 -c "import adafruit_bme280"` works
- [ ] `python3 -c "import pyaudio"` works
- [ ] `python3 -c "import shazamio"` works
- [ ] Temperature shows on dashboard
- [ ] dB level shows on dashboard
- [ ] Song detection works when music plays

## Support

If issues persist:

1. Run diagnostics:
```bash
python3 /workspace/test_sensors_comprehensive.py
```

2. Check logs:
```bash
tail -f /var/log/pulse/hub.log
```

3. Check hardware connections
4. Verify all dependencies installed
5. Reboot and try again

## Expected Output When Working

Dashboard should show:
- **Temperature**: 65-80°F (typical room temp)
- **Humidity**: 30-60% (typical indoor)
- **dB Level**: 30-40 dB (quiet room), 60-80 dB (with music)
- **Song**: Title and artist when music plays

Logs should show:
```
✓ BME280 initialized successfully at 0x76
✓ Audio stream opened successfully
🔊 Audio: 45.3 dB (Peak: 62.1 dB)
🎵 Song detected: Example Song - Artist Name
```
