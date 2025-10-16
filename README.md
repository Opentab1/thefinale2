# 🎵 Pulse 1.0 – AI-Driven Venue Operating System

> **Turn your bar, restaurant, or event space into an autonomous, self-optimizing venue.**

Pulse 1.0 is a complete operating system for physical venues, designed to run on a Raspberry Pi 5. It automatically manages HVAC, lighting, music, and TVs while learning from real-time data to create the perfect customer experience.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red.svg)](https://www.raspberrypi.com/products/raspberry-pi-5/)
[![Python](https://img.shields.io/badge/Python-3.11%20|%203.13-green.svg)](https://www.python.org/)

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

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

**Notes:**
- **Raspberry Pi OS Bookworm**: The installer uses `chromium` and `libopenblas-dev` (replacing the older `chromium-browser` and `libatlas-base-dev`).
- **Python 3.13 Support**: Fully compatible with Python 3.13. We removed `tflite-runtime` (no wheels for Py3.13/aarch64) and updated `numpy`, `opencv-python`, and `librosa` to compatible versions. The AI camera runs via OpenCV DNN or HAT when available.

The installer will:
- ✓ Install all dependencies
- ✓ Set up Python environment
- ✓ Build dashboard interface
- ✓ Configure systemd services
- ✓ Enable auto-login and kiosk mode
- ✓ Detect connected hardware
- ✓ Reboot automatically

### 3. Complete Setup Wizard

After reboot, the setup wizard automatically launches at `http://localhost:9090`

**Wizard Steps:**
1. **Venue Setup** – Name, timezone, operating hours
2. **Hardware Check** – Automatic detection of connected sensors
3. **Smart Integrations** – Connect Nest, Hue, Spotify (optional)
4. **Automation Limits** – Set safe ranges for automatic adjustments
5. **Complete** – System reboots and launches dashboard

### 4. Access Your Dashboard

After final reboot, the dashboard automatically opens in kiosk mode at `http://localhost:8080`

**Dashboard Tabs:**
- **Live** – Real-time metrics and comfort index
- **Analytics** – Historical trends and graphs
- **Controls** – Manual control of all systems
- **Health** – System status and module health
- **Settings** – Configuration and limits

---

## 📱 Usage

### Auto Mode vs Manual Mode

Each system (HVAC, Lighting, Music, TV) has an **Auto/Manual toggle**:

- **Auto Mode** ✅ – Pulse makes decisions based on real-time data
- **Manual Mode** ⚙️ – You control everything from the dashboard

**Global Safe Mode**: Disable all automation instantly with the top-right button.

### Controlling Systems

#### HVAC
```
• View: Current temperature, humidity, setpoint
• Control: Mode (Heat/Cool/Auto/Off), temperature setpoint
• Auto: Adjusts based on occupancy and comfort
```

#### Lighting
```
• View: All lights, brightness levels, scenes
• Control: Brightness slider, color picker, preset scenes
• Auto: Circadian rhythm with occupancy awareness
```

#### Music
```
• View: Currently playing track, volume
• Control: Play/pause, skip, volume
• Auto: Volume adjusts based on ambient noise
```

#### TV
```
• View: Connected devices
• Control: Power on/off, input selection
• Auto: Schedule-based programming
```

---

## 🔒 Safety & Limits

Pulse enforces rate limits to prevent rapid changes:

| System | Maximum Change | Time Window |
|--------|----------------|-------------|
| HVAC | ±1°F | 10 minutes |
| Lighting | ±10% | 10 minutes |
| Music | ±5% volume | 3 minutes |

All limits are configurable in Settings.

---

## 🗂️ Project Structure

```
pulse/
├── install.sh                    # One-line installer
├── requirements.txt              # Python dependencies
├── config/
│   ├── config.yaml              # Main configuration
│   └── hardware_status.json     # Module health status
├── services/
│   ├── hub/main.py              # Core orchestration
│   ├── sensors/                 # All sensor modules
│   │   ├── camera_people.py
│   │   ├── mic_song_detect.py
│   │   ├── bme280_reader.py
│   │   ├── light_level.py
│   │   ├── pan_tilt.py
│   │   └── health_monitor.py
│   ├── controls/                # Smart home controllers
│   │   ├── hvac_nest.py
│   │   ├── lighting_hue.py
│   │   ├── tv_cec.py
│   │   ├── music_spotify.py
│   │   └── music_local.py
│   ├── storage/db.py            # Database layer
│   └── systemd/                 # Service files
├── dashboard/
│   ├── api/server.py            # Flask + SocketIO backend
│   └── ui/                      # React frontend
│       ├── src/
│       │   ├── App.jsx
│       │   └── components/
│       ├── package.json
│       └── vite.config.js
└── bootstrap/wizard/
    └── server.py                # First-boot wizard
```

---

## 🔧 Configuration

### Main Config: `/opt/pulse/config/config.yaml`

```yaml
venue:
  name: "Your Venue Name"
  timezone: "America/Chicago"

modules:
  camera: true
  mic: true
  bme280: true
  light_sensor: true
  ai_hat: true
  pan_tilt: true

smart_integrations:
  hvac:
    enabled: true
    provider: "nest"
  lighting:
    enabled: true
    provider: "hue"
  music:
    enabled: true
    provider: "spotify"

policies:
  hvac:
    min_f: 67
    max_f: 75
    auto_mode: true
  lighting:
    min_pct: 20
    max_pct: 85
    auto_mode: true
  music:
    volume_min: 25
    volume_max: 70
    auto_mode: true
```

### Environment Variables: `/opt/pulse/.env`

```bash
# Google Nest / SDM
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_PROJECT_ID=your_project_id
NEST_DEVICE_ID=your_device_id

# Philips Hue
HUE_BRIDGE_IP=192.168.1.x
HUE_USERNAME=your_hue_username

# Spotify
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Security
SECRET_KEY=generated_automatically
ENCRYPTION_KEY=generated_automatically
```

---

## 🩺 Troubleshooting

### Check System Status

```bash
# View all services
sudo systemctl status pulse-*

# Check logs
tail -f /var/log/pulse/hub.log
tail -f /var/log/pulse/dashboard.log

# Test hardware
cd /opt/pulse
./venv/bin/python3 -c "from services.sensors.health_monitor import *; ..."
```

### Common Issues

**Dashboard won't load**
```bash
sudo systemctl restart pulse-dashboard
```

**Sensors not detected**
```bash
# Check I2C devices
sudo i2cdetect -y 1

# Check camera
vcgencmd get_camera
```

**HVAC/Lighting/Music not working**
1. Verify credentials in `/opt/pulse/.env`
2. Check network connectivity
3. Review API quotas/limits

### Reset to Factory Settings

```bash
cd /opt/pulse
rm config/.wizard_complete
sudo reboot
```

---

## 🚀 Advanced

### API Endpoints

The dashboard API runs on port 8080:

```bash
# Get current status
curl http://localhost:8080/api/status

# Get sensor data
curl http://localhost:8080/api/sensors/current

# Control HVAC
curl -X POST http://localhost:8080/api/hvac/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "COOL"}'

# Set lighting
curl -X POST http://localhost:8080/api/lighting/brightness \
  -H "Content-Type: application/json" \
  -d '{"light_id": 1, "brightness_pct": 75}'
```

### WebSocket Events

Connect to real-time updates:

```javascript
import io from 'socket.io-client'

const socket = io('http://localhost:8080')

socket.on('sensor_update', (data) => {
  console.log('Occupancy:', data.occupancy)
  console.log('Temperature:', data.temperature_f)
})
```

### Database Access

```bash
# Connect to database
sqlite3 /opt/pulse/data/pulse.db

# Example queries
SELECT * FROM occupancy ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM automation_log WHERE timestamp > datetime('now', '-1 hour');
```

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone repository
git clone https://github.com/Opentab1/thefinale2.git
cd thefinale2

# Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up dashboard
cd dashboard/ui
npm install
npm run dev
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Raspberry Pi Foundation for the incredible hardware
- Open source sensor libraries (picamera2, adafruit, etc.)
- Smart home API providers (Google SDM, Philips Hue, Spotify)
- The amazing Python and React communities

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

