# 🎯 Pulse - Smart Venue Automation System

> **All sensor capabilities are fixed and working!** Full debugging output included.

## 🚀 Quick Install (Raspberry Pi)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/products/raspberry-pi-5/)
[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-green.svg)](https://www.python.org/)

---

## ✨ Features

### 🧠 **Intelligent Automation**
- **HVAC Control**: Automatically adjusts temperature based on occupancy, time, and comfort metrics
- **Smart Lighting**: Circadian rhythm-based lighting with automatic scene selection
- **Music Management**: Dynamic volume and playlist adjustment based on ambient noise and crowd energy
- **TV Control**: Scheduled content with event awareness

### 📊 **Real-Time Sensing**
- **People Counting**: Computer vision-based occupancy tracking with entry/exit detection
- **Audio Monitoring**: Song detection and decibel level measurement
- **Environmental Sensors**: Temperature, humidity, pressure, and light level monitoring
- **Comfort Index**: Real-time calculation of venue comfort based on multiple factors

### 🎛️ **Full Control Dashboard**
- **Live Overview**: Real-time metrics and current conditions
- **Analytics**: Historical trends and data visualization
- **Manual Controls**: Override automation for any system
- **Auto/Manual Toggle**: Switch between autonomous and manual modes per system
- **System Health**: Module status and resource monitoring

### 🔧 **Self-Healing Architecture**
- Automatic hardware detection on startup
- Graceful degradation when sensors fail
- Continuous health monitoring with auto-recovery
- Modular design - every component is optional

### 🚀 **Zero-Touch Setup**
- One-line installation command
- Interactive setup wizard on first boot
- Auto-launch dashboard in kiosk mode
- No coding required after installation

---

## 🛠️ Hardware Requirements

### Required
- **Raspberry Pi 5 (8 GB)** – Core compute + display
- **Power Supply** – Official USB-C power adapter
- **MicroSD Card** – 32GB+ for Raspberry Pi OS

### Recommended Sensors
| Component | Purpose | Link |
|-----------|---------|------|
| **Waveshare Pan-Tilt HAT** | Camera motion control | [Amazon](https://www.amazon.com/Waveshare-Pan-Tilt-HAT-Raspberry-Intensity/dp/B07PPV122Z/) |
| **USB Microphone** | Audio detection | [Amazon](https://www.amazon.com/dp/B071WH7FC6) |
| **BME280 Sensor** | Temperature/humidity/pressure | [Amazon](https://www.amazon.com/dp/B088HJHJXG) |
| **AI Hat for Pi 5** | Hardware accelerated vision | [Official Site](https://www.raspberrypi.com/products/ai-hat/) |

### Optional Smart Home Integrations
- **Google Nest Thermostat** (HVAC control)
- **Philips Hue Bridge + Bulbs** (lighting control)
- **TVs with HDMI-CEC** (TV control)
- **Spotify Premium** (music streaming)

---

## ⚡ Quick Start

### 1. Prepare Your Raspberry Pi

1. **Flash Raspberry Pi OS (64-bit)** to your microSD card using [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Boot your Pi and ensure it's connected to the internet
3. Open a terminal

### 2. Install Pulse (One Command)

**One-line installation:**

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

Notes:
- Raspberry Pi OS Bookworm: the installer uses `chromium` and `libopenblas-dev` (replacing the older `chromium-browser` and `libatlas-base-dev`).
- Python compatibility: installer supports Python 3.11–3.13 on aarch64 and upgrades `pip`, `setuptools`, and `wheel` to ensure binary wheels are used.
- If you previously saw a pip error like `BackendUnavailable: Cannot import 'setuptools.build_meta'` or builds for `numpy` on Python 3.13, this has been resolved by pinning wheels compatible with Python 3.13 and upgrading build tooling during install.

This will:
- ✅ Install all dependencies
- ✅ Set up the system with **all sensor fixes**
- ✅ Configure auto-start on boot
- ✅ Launch the setup wizard

After installation, the system boots directly into the dashboard with full functionality.

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

---

## 📞 Support

- **Documentation**: [GitHub Wiki](https://github.com/Opentab1/thefinale2/wiki)
- **Issues**: [GitHub Issues](https://github.com/Opentab1/thefinale2/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Opentab1/thefinale2/discussions)

---

## 🗺️ Roadmap

### v1.1 (Coming Soon)
- [ ] Multi-zone support
- [ ] Mobile app (iOS/Android)
- [ ] Advanced ML models for predictive automation
- [ ] Integration with more smart home platforms
- [ ] Cloud sync for multi-location venues

### v2.0 (Future)
- [ ] Voice control integration
- [ ] Customer analytics dashboard
- [ ] Revenue optimization features
- [ ] Staff scheduling integration

---

<p align="center">
  <strong>Built with ❤️ for venue owners who want to focus on their customers, not their systems.</strong>
</p>

<p align="center">
  Made with 🎵 Pulse
</p>
