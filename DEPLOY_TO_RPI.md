# Deploy Sensor Fixes to Raspberry Pi

## ✅ All Python Libraries Installed Successfully

The following packages are now installed:
- ✅ numpy
- ✅ pyaudio  
- ✅ sounddevice
- ✅ shazamio
- ✅ adafruit_bme280
- ✅ smbus2
- ✅ RPi.GPIO

## 🚀 Testing on Your Raspberry Pi

Since you're on the RPi, let's test the actual sensors now:

### Quick Test Script

Run this command on your RPi:

```bash
python3 /workspace/test_sensors_quick.py
```

This will test:
1. **BME280 Temperature Sensor** (should show temp/humidity if wired correctly)
2. **Audio Devices** (should list your USB microphone)
3. **Audio Monitoring** (should capture dB levels)
4. **Song Detection** (will work when music is playing)

### Expected Output on Real Pi

On actual Raspberry Pi hardware, you should see:

```
✓✓✓ BME280 WORKING! ✓✓✓
Temperature: 72.3°F
Humidity: 45.2%

✓ Audio input devices available

✓✓✓ AUDIO MONITORING WORKING! ✓✓✓
Current dB: 42.5

✓✓✓ ALL SENSORS WORKING! ✓✓✓
```

### Start the System

Once sensors test successfully:

```bash
bash /workspace/start_pulse.sh
```

Then open dashboard at: **http://localhost:8080**

You should now see:
- 🌡️ **Temperature**: Live readings from BME280
- 🔊 **dB Level**: Real-time audio levels
- 🎵 **Song Detection**: Songs identified when music plays (requires internet)

## 🔧 Troubleshooting (If Needed)

### BME280 Not Working

1. Check I2C is enabled:
```bash
sudo i2cdetect -y 1
```
Should show `76` or `77`

2. If empty grid, enable I2C:
```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
sudo reboot
```

3. Verify wiring:
- VCC → Pin 1 (3.3V)
- GND → Pin 6 (Ground)
- SDA → Pin 3 (GPIO2)
- SCL → Pin 5 (GPIO3)

### Audio Not Working

1. List audio devices:
```bash
arecord -l
```

2. If no devices shown:
- Check USB microphone is connected
- Try different USB port
- Check: `lsusb` to see if USB device detected

3. Test recording:
```bash
arecord -d 3 test.wav
aplay test.wav
```

### Song Detection Not Working

1. Check internet connection:
```bash
ping -c 3 google.com
```

2. Song detection requires:
- Music playing (audible to microphone)
- Active internet connection
- ~30 seconds to identify (runs every 30s)

3. Check logs:
```bash
tail -f /var/log/pulse/hub.log | grep -i song
```

## 📊 What's Fixed

### Before (Not Working)
- ❌ Temperature: Missing `adafruit_bme280` library
- ❌ dB Reader: Missing `pyaudio` and `sounddevice` libraries
- ❌ Song Detection: Missing `shazamio` library

### After (Should Work)
- ✅ Temperature: BME280 library installed + I2C enabled
- ✅ dB Reader: Audio libraries installed + ALSA configured
- ✅ Song Detection: ShazamIO installed + asyncio integration

## 🎯 Success Criteria

When everything works, your dashboard will show:

```
┌─────────────────────────────────────┐
│ Pulse Dashboard                      │
├─────────────────────────────────────┤
│ 👥 People: 3                         │
│ 🌡️  Temp: 72.3°F (22.4°C)          │
│ 💧 Humidity: 45.2%                   │
│ 💡 Light: 450 lux                    │
│ 🔊 Sound: 52.3 dB                    │
│ 🎵 Song: Example Song - Artist       │
└─────────────────────────────────────┘
```

And logs will show:
```
✓ BME280 initialized successfully at 0x76
✓ Audio stream opened successfully
🔊 Audio: 52.3 dB (Peak: 68.1 dB)
🎵 Song detected: Example Song - Artist Name
```

## 🔄 If You Need to Reinstall

The fix is now part of the repository. To reinstall on a fresh system:

```bash
cd /workspace
sudo bash fix_sensors_v2.sh
```

## 📝 Files Added/Modified

- `fix_sensors.sh` - Original comprehensive fix script
- `fix_sensors_v2.sh` - Improved version (works in VM and Pi)
- `test_sensors_quick.py` - Quick diagnostic script
- `test_sensors_comprehensive.py` - Detailed diagnostic script  
- `SENSOR_FIX_README.md` - Complete troubleshooting guide
- `DEPLOY_TO_RPI.md` - This file

All changes committed to branch: `cursor/fix-non-functional-sensor-readings-4f53`
