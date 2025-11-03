# 🎯 Pulse - Simple Local Dashboard with Real Sensors

> **Live sensor dashboard - NO AWS, NO auth, just real data!**

## 🚀 Quick Start (Fresh Raspberry Pi)

**ONE command to install everything:**

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

**That's it!** After installation:
1. System reboots automatically
2. Setup wizard opens at `http://localhost:9090`
3. Click through the wizard (2 minutes)
4. Dashboard launches at `http://<your-pi-ip>:8080`

**No coding. No configuration. Just one command and a simple wizard.**

Shows real-time data from:
- 🌡️ **Temperature** (BME280 sensor)
- 💧 **Humidity** (BME280 sensor)
- 🔊 **Sound Level** (Microphone)
- 💡 **Light Level** (Camera-based)
- 🎵 **Current Song** (Database)
- 😊 **Comfort Score** (Calculated)

**Auto-starts on boot. Auto-restarts on failure. Zero configuration needed.**

## ✨ What's Fixed

All sensor issues have been resolved:

- ✅ **BME280 Sensor** - Temperature, humidity, and pressure readings
- ✅ **AI People Counter** - Camera-based person detection and tracking
- ✅ **Song Detection** - Microphone + Shazam integration
- ✅ **Light Level Reading** - Ambient light measurement
- ✅ **Decibel Reading** - Real-time sound level monitoring
- ✅ **Full Terminal Debugging** - Color-coded output showing exactly what's happening

## 🎨 Features

### Real-Time Monitoring
- 👥 **AI People Counting** - Track occupancy with entry/exit detection
- 🌡️ **Environmental Sensors** - Temperature, humidity, pressure, light
- 🎵 **Music Recognition** - Automatic song detection via Shazam
- 🔊 **Sound Analysis** - Decibel levels and audio spectrum

### Smart Automation
- 🏠 **HVAC Control** - Auto-adjust based on occupancy and temperature
- 💡 **Lighting Control** - Circadian rhythm and occupancy-based
- 📺 **Media Control** - TV and music automation
- 📊 **Learning Engine** - Adapts to usage patterns

### User Interface
- 🌐 **Web Dashboard** - Real-time data visualization
- 🎨 **Kiosk Mode** - Auto-launching fullscreen display
- 📱 **Mobile Responsive** - Works on any device
- 🔴 **Live Updates** - WebSocket-based real-time data

## 📋 System Requirements

### Hardware
- **Raspberry Pi 5** (recommended) or Pi 4
- **Camera** - Raspberry Pi Camera Module or USB webcam
- **Microphone** - USB microphone or HAT
- **BME280 Sensor** (optional) - I2C temperature/humidity sensor
- **Internet Connection** - For song detection and updates

### Software
- Raspberry Pi OS (64-bit) - Bookworm or newer
- Python 3.9+
- Node.js 16+

## 🛠️ Manual Installation

If you prefer manual installation:

```bash
# 1. Clone the repository
git clone https://github.com/Opentab1/thefinale2.git
cd thefinale2

# 2. Run installation
sudo bash install.sh
```

## 🎯 Manual Startup (For Testing)

After installation, you can manually start the system with full debug output:

```bash
cd /opt/pulse
./START_HERE.sh
```

This will:
- Show **color-coded terminal output** with detailed sensor status
- Start the hub and dashboard
- Auto-open the browser to the dashboard
- Display real-time updates every 30 seconds

You'll see exactly what every sensor is doing:
```
════════════════════════════════════════════════════════════════════
STATUS UPDATE #1
════════════════════════════════════════════════════════════════════
Hub Running: True

SENSOR READINGS:
  👥 Occupancy: 3 people
  📊 Entries: 5 | Exits: 2
  🌡️  Temperature: 72.5°F
  💧 Humidity: 45.2%
  💡 Light Level: 450.0 lux
  🔊 Noise Level: 65.3 dB
  🎵 Now Playing: Song Title - Artist

MODULE STATUS:
  Camera: ✓ Active
  Microphone: ✓ Active
  BME280: ✓ Active
  Light Sensor: ✓ Active
  Pan/Tilt: ✓ Active
════════════════════════════════════════════════════════════════════
```

## 🔧 Configuration

Edit `/opt/pulse/config/config.yaml` to customize:

```yaml
modules:
  camera: true
  mic: true
  bme280: true
  light_sensor: true
  ai_hat: true

smart_integrations:
  hvac:
    enabled: false
  lighting:
    enabled: false
  music:
    enabled: false
```

## 📊 Diagnostics

Run the diagnostic tool to check all sensors:

```bash
cd /opt/pulse
./diagnose_sensors.py
```

This will test each sensor individually and report status.

## 🐛 Troubleshooting

### Camera Not Working
```bash
# Check camera
ls /dev/video*
# Test camera
libcamera-hello
```

### Microphone Not Working
```bash
# List audio devices
arecord -l
# Test recording
arecord -d 5 test.wav
```

### BME280 Not Found
```bash
# Check I2C
i2cdetect -y 1
# Should show device at 0x76 or 0x77
```

### Song Detection Not Working
- Requires internet connection for Shazam API
- Check: `pip list | grep shazamio`

## 📁 Project Structure

```
pulse/
├── services/
│   ├── hub/           # Main orchestration
│   ├── sensors/       # Sensor modules
│   ├── controls/      # Smart home integrations
│   └── storage/       # Database
├── dashboard/
│   ├── api/           # Flask API server
│   └── ui/            # React frontend
├── config/            # Configuration files
└── START_HERE.sh      # Manual startup script
```

## 🌐 API Endpoints

After installation, the API is available at `http://localhost:8080/api/`:

- `GET /api/status` - System status
- `GET /api/sensors/current` - Current sensor readings
- `GET /api/occupancy/current` - Current occupancy
- `GET /api/environment/current` - Environmental data
- `GET /api/health` - System health

## 📖 Documentation

- `HOW_TO_START.md` - Detailed startup guide
- `FIXES_APPLIED.md` - List of all fixes
- `INSTRUCTIONS.txt` - Quick reference

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md first.

## 📄 License

See LICENSE file for details.

## 🎉 Quick Start Summary

1. **Install:**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
   ```

2. **The system auto-starts on boot** with the dashboard

3. **For manual testing with debug output:**
   ```bash
   cd /opt/pulse
   ./START_HERE.sh
   ```

**That's it!** All sensors work, full debugging included. 🚀
