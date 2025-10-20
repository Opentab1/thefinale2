# 🚀 How to Start Pulse System

## Quick Start

To start the Pulse system with **full debug output** visible in the terminal **AND** the web dashboard in your browser:

```bash
./START_HERE.sh
```

That's it! This will:

1. ✅ Start the Pulse Hub with **detailed debug logging** to the terminal
2. ✅ Start the Dashboard API server
3. ✅ Automatically open your browser to http://localhost:8080
4. ✅ Show you **exactly** what each sensor is doing in real-time

## What You'll See

### In the Terminal

You will see detailed, color-coded output showing:

- 🎥 **Camera/People Counter** - Detection status, current count, entries/exits
- 🎤 **Microphone** - Decibel levels, song detection results
- 🌡️ **BME280 Sensor** - Temperature, humidity, pressure readings
- 💡 **Light Sensor** - Light level measurements in lux
- 🔄 **System Status** - Every 30 seconds, full status update

Example output:
```
════════════════════════════════════════════════════════════════════════════════
STATUS UPDATE #1
════════════════════════════════════════════════════════════════════════════════
Hub Running: True

SENSOR READINGS:
  👥 Occupancy: 3 people
  📊 Entries: 5 | Exits: 2
  🌡️  Temperature: 72.5°F
  💧 Humidity: 45.2%
  💡 Light Level: 450.0 lux
  🔊 Noise Level: 65.3 dB
  🎵 Now Playing: Song Title - Artist Name

MODULE STATUS:
  Camera: ✓ Active
  Microphone: ✓ Active
  BME280: ✓ Active
  Light Sensor: ✓ Active
  Pan/Tilt: ✓ Active
════════════════════════════════════════════════════════════════════════════════
```

### In the Browser

The web dashboard at http://localhost:8080 will show:
- Real-time occupancy count
- Environmental readings (temp, humidity, light, sound)
- Current music playing
- System health status
- Live camera feed (if available)

## Alternative Startup Methods

### Method 1: Dual Terminal Mode
Opens two separate terminal windows - one for Hub, one for Dashboard:
```bash
./start_pulse_dual.sh
```

### Method 2: Single Terminal with Colors
Hub in foreground, Dashboard in background:
```bash
./start_pulse.sh
```

### Method 3: Manual Testing
Test just the hub:
```bash
cd /workspace
export PYTHONPATH=/workspace:/workspace/services
python3 services/hub/main.py
```

Test just the dashboard:
```bash
cd /workspace
export PYTHONPATH=/workspace:/workspace/services
python3 dashboard/api/server.py
```

## Stopping the System

Press **Ctrl+C** in the terminal where you started the system.

Or manually:
```bash
pkill -f "python.*hub/main.py"
pkill -f "python.*dashboard/api/server.py"
```

## Troubleshooting

### If a sensor is not working:

1. **Check the terminal output** - It will show detailed error messages
2. **Check the config** - Edit `/workspace/config/config.yaml`
3. **Check hardware** - Make sure sensors are connected
4. **Check logs** - `/var/log/pulse/hub.log` and `/var/log/pulse/hub-error.log`

### Common Issues:

**Camera not working:**
- Check if camera is connected: `ls /dev/video*`
- Check picamera2: `python3 -c "from picamera2 import Picamera2"`

**Microphone not working:**
- Check audio devices: `arecord -l`
- Test recording: `arecord -d 5 test.wav`

**BME280 not working:**
- Check I2C connection: `i2cdetect -y 1`
- Should see device at 0x76 or 0x77

**Song detection not working:**
- Requires internet connection for Shazam API
- Check if shazamio is installed: `pip list | grep shazamio`

### Debug Mode

For even more verbose output, set:
```bash
export PULSE_DEBUG=1
./START_HERE.sh
```

## Log Files

All logs are stored in `/var/log/pulse/`:
- `hub.log` - Main hub log
- `hub-error.log` - Hub errors only
- `dashboard.log` - Dashboard API log

## Configuration

Edit `/workspace/config/config.yaml` to:
- Enable/disable modules
- Adjust sensor update intervals
- Configure smart home integrations
- Set automation policies

## System Requirements

- Python 3.9+
- Camera (Raspberry Pi Camera or USB webcam)
- Microphone (USB or built-in)
- BME280 sensor (optional, I2C)
- Light sensor or camera for brightness detection
- Internet connection (for song detection)

## Next Steps

Once the system is running:
1. **Watch the terminal** - See exactly what's happening
2. **Open the dashboard** - http://localhost:8080
3. **Test each sensor** - Move around, make noise, change lighting
4. **Check readings** - Verify all sensors are reporting correctly

If something isn't working, the terminal output will tell you exactly what and why!

---

**Need Help?** Check the terminal output first - it shows detailed error messages and status for every component.
