# Pulse - Smart Venue Automation System

> Simple, reliable sensor monitoring and automation for Raspberry Pi

## 🚀 Quick Install

**One command to install everything:**

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

**After installation, reboot your Pi:**

```bash
sudo reboot
```

That's it! The system will start automatically on boot.

---

## 📊 What It Does

Pulse monitors your space in real-time:

- 🌡️ **Temperature & Humidity** - BME280 sensor
- 💡 **Light Level** - Camera-based light detection
- 👥 **People Count** - AI-powered person detection
- 🔊 **Sound Level** - Decibel monitoring
- 🎵 **Song Detection** - Automatic music recognition (Shazam)

Access everything from a web dashboard at `http://your-pi-ip:8080`

---

## 🏗️ Architecture

**4 Independent Services** (fault-isolated):

```
Audio Service         → Microphone, dB, song detection
Camera Service        → AI people counting
Environmental Service → Temperature, humidity, light
Hub Service          → Dashboard, database, automation
```

Each service runs independently. If one crashes, the others keep running.

---

## 📝 Installation (Detailed)

### Prerequisites

- Raspberry Pi (3, 4, or 5)
- Raspberry Pi OS (Bookworm or newer)
- Internet connection
- Optional: BME280 sensor, camera module

### Install Steps

1. **Download and run installer:**

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

2. **Reboot (required for I2C):**

```bash
sudo reboot
```

3. **Access dashboard:**

Open browser to: `http://your-pi-ip:8080`

---

## 🔧 Service Management

### Check Status

```bash
# All services
sudo systemctl status pulse.service

# Individual services
sudo systemctl status pulse-audio
sudo systemctl status pulse-camera
sudo systemctl status pulse-environmental
sudo systemctl status pulse-hub-main
```

### View Logs

```bash
# All services
sudo journalctl -u pulse-audio -u pulse-camera -u pulse-environmental -u pulse-hub-main -f

# Individual service
sudo journalctl -u pulse-audio -f
```

### Control Services

```bash
# Start all
sudo systemctl start pulse.service

# Stop all
sudo systemctl stop pulse.service

# Restart all
sudo systemctl restart pulse.service

# Restart individual service
sudo systemctl restart pulse-environmental
```

---

## 📁 Project Structure

```
/opt/pulse/
├── run_audio_service.py          # Audio service entry point
├── run_camera_service.py         # Camera service entry point
├── run_environmental_service.py  # Environmental service entry point
├── run_hub_service.py            # Hub service entry point
├── install.sh                    # Main installer
├── install_4_services.sh         # 4-service installer
│
├── services/
│   ├── sensors/                  # Sensor code
│   │   ├── simple_decibel_detector.py
│   │   ├── simple_song_detector.py
│   │   ├── bme280_reader.py
│   │   ├── camera_people.py
│   │   └── light_level.py
│   ├── hub/                      # Hub orchestrator
│   │   └── main.py
│   ├── storage/                  # Database
│   │   └── db.py
│   └── systemd/                  # Service files
│       ├── pulse-audio.service
│       ├── pulse-camera.service
│       ├── pulse-environmental.service
│       └── pulse-hub-main.service
│
├── dashboard/                    # Web UI
│   ├── ui/                       # React frontend
│   └── api/                      # Flask backend
│
└── config/
    ├── config.yaml               # Core system configuration
    └── song_detection.json       # Audio provider + RapidAPI settings
```

---

## ⚙️ Configuration

Edit `/opt/pulse/config/config.yaml` to enable/disable features:

```yaml
modules:
  camera: true          # People counting
  mic: true            # Audio detection
  bme280: true         # Temperature sensor
  light_sensor: true   # Light detection
  
smart_integrations:
  hue: false           # Philips Hue lights
  nest: false          # Nest thermostat
  spotify: false       # Spotify control
```

Song detection specifics (provider, recording duration, RapidAPI host/key) live in
`/opt/pulse/config/song_detection.json`. Set the `api_key` there or export the
environment variable referenced by `api_key_env` (defaults to `PULSE_RAPIDAPI_KEY`).

After changing config:

```bash
sudo systemctl restart pulse.service
```

---

## 🔍 Troubleshooting

### Services won't start

Check logs for errors:
```bash
sudo journalctl -u pulse-hub-main -n 50
```

### Dashboard not loading

1. Check if hub service is running:
   ```bash
   sudo systemctl status pulse-hub-main
   ```

2. Verify port 8080 is accessible:
   ```bash
   curl http://localhost:8080
   ```

### Sensors not working

1. **BME280 (temperature):**
   ```bash
   sudo i2cdetect -y 1
   # Should see 0x76 or 0x77
   ```

2. **Camera:**
   ```bash
   libcamera-hello
   # Should show camera preview
   ```

3. **Microphone:**
   ```bash
   arecord -l
   # Should list audio devices
   ```

### View all logs

```bash
sudo journalctl -u pulse-audio -u pulse-camera -u pulse-environmental -u pulse-hub-main --since "10 minutes ago"
```

---

## 🎯 Features

### Real-Time Dashboard
- Live sensor readings
- Historical graphs
- Current song playing
- People count with entry/exit tracking

### Data Storage
- SQLite database
- Automatic logging
- Query historical data

### Automation (Optional)
- HVAC control based on occupancy
- Lighting scenes
- Music automation
- Custom rules

---

## 🔐 Security Notes

- Dashboard runs on port 8080 (local network only)
- No authentication by default (for local use)
- For external access, use SSH tunnel:
  ```bash
  ssh -L 8080:localhost:8080 pi@your-pi-ip
  ```

---

## 📚 Additional Documentation

- **Architecture Details:** `CODE_ARCHITECTURE_AND_FLOW.md`
- **4-Service Setup:** `SIMPLE_4_SERVICE_ARCHITECTURE.md`
- **Audio Fix History:** `SONG_DETECTION_FIX_NOV_5-9.md`

---

## 🛠️ Advanced Installation

### Manual 4-Service Setup

If you want to set up the 4-service architecture manually:

```bash
cd /opt/pulse
source venv/bin/activate
bash install_4_services.sh
```

### Development Setup

```bash
# Clone repository
git clone https://github.com/Opentab1/thefinale2.git
cd thefinale2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run individual services
python run_audio_service.py
python run_environmental_service.py
python run_hub_service.py
```

---

## 📊 System Requirements

- **Raspberry Pi:** 3B+, 4, or 5 (recommended)
- **OS:** Raspberry Pi OS Bookworm or newer
- **RAM:** 2GB minimum, 4GB recommended
- **Storage:** 8GB SD card minimum, 32GB recommended
- **Network:** WiFi or Ethernet

### Optional Hardware
- BME280 sensor (I2C) - Temperature/humidity
- Camera module (libcamera) - People counting
- USB microphone - Audio detection
- Philips Hue bridge - Smart lighting
- Nest thermostat - HVAC control

---

## 🤝 Contributing

See `CONTRIBUTING.md` for development guidelines.

---

## 📄 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

---

## 🆘 Support

### Common Issues

1. **"No sensor data"** → Check service logs
2. **"Dashboard won't load"** → Verify hub service is running
3. **"Camera crashes"** → This is normal (libcamera bug), service auto-restarts

### Getting Help

- Check logs: `sudo journalctl -u pulse-hub-main -f`
- Review troubleshooting guide: `TROUBLESHOOTING.md`
- Check architecture docs: `CODE_ARCHITECTURE_AND_FLOW.md`

---

## ✨ Key Features

### Simple & Reliable
- Clean code (67% reduction from previous version)
- Fault-isolated services
- Auto-restart on failure
- Proven to run indefinitely

### Sensor Monitoring
- Real-time temperature, humidity, pressure
- People counting with AI
- Decibel level monitoring
- Automatic song recognition (Shazam)
- Light level detection

### Smart Home Integration
- Philips Hue lighting control
- Nest thermostat integration
- Spotify music control
- Custom automation rules

---

**Built with simplicity and reliability in mind. Each service does one thing well.**
