# Post-Installation Setup Guide

After running `install.sh`, you **MUST** complete these steps for full functionality.

## 🔴 CRITICAL: Required After Installation

### 1. Reboot Your Raspberry Pi
The installation script enables I2C and other hardware interfaces, but they require a reboot to take effect.

```bash
sudo reboot
```

**Why?** The BME280 temperature sensor requires I2C to be enabled. The installer modifies `/boot/config.txt` to enable it, but changes only take effect after reboot.

---

## ✅ Verify Installation After Reboot

### Check I2C is Enabled:
```bash
ls /dev/i2c-* 
# Should show: /dev/i2c-1
```

### Check BME280 Sensor is Detected:
```bash
sudo i2cdetect -y 1
# Should show "76" or "77" in the grid
```

### Verify Python Dependencies:
```bash
cd /opt/pulse
source venv/bin/activate
python3 << 'EOF'
# Test BME280 libraries
import adafruit_bme280
print("✅ BME280 libraries installed")

# Test audio libraries
import numpy, sounddevice
print("✅ Audio libraries installed")

# Test song detection
from shazamio import Shazam
print("✅ ShazamIO installed")
EOF
```

### Test Temperature Sensor:
```bash
cd /opt/pulse
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/pulse/services')
from sensors.bme280_reader import BME280Reader
sensor = BME280Reader(address=0x76)
data = sensor.read_sensor()
print(f"✅ Temperature: {data['temperature_f']:.1f}°F")
print(f"✅ Humidity: {data['humidity']:.1f}%")
EOF
```

---

## 🐛 Troubleshooting

### Problem: "No such file or directory: /dev/i2c-1"

**Solution:** I2C is not enabled. The installer should have enabled it, but if not:

```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
sudo reboot
```

Or manually add to `/boot/config.txt`:
```bash
echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
sudo reboot
```

### Problem: "ModuleNotFoundError: No module named 'adafruit_bme280'"

**Solution:** Dependencies not installed. Install them:

```bash
cd /opt/pulse
source venv/bin/activate
pip install -r requirements.txt
```

Or specifically:
```bash
pip install adafruit-blinka adafruit-circuitpython-bme280
```

### Problem: "ModuleNotFoundError: No module named 'shazamio'"

**Solution:** Song detection dependencies missing:

```bash
pip install shazamio sounddevice numpy "aiohttp<4.0.0"
```

### Problem: Temperature still shows `null` on dashboard

**Checklist:**
1. ✅ I2C enabled? → `ls /dev/i2c-1`
2. ✅ BME280 detected? → `sudo i2cdetect -y 1`
3. ✅ Libraries installed? → `python3 -c "import adafruit_bme280"`
4. ✅ Hub running? → `systemctl status pulse-hub.service`
5. ✅ BME280 wired correctly? → Check SDA/SCL connections

### Problem: Song detection not working

**Checklist:**
1. ✅ ShazamIO installed? → `python3 -c "from shazamio import Shazam"`
2. ✅ Audio device available? → `arecord -l`
3. ✅ Microphone permissions? → User in `audio` group
4. ✅ Hub logs showing audio? → `tail -f /var/log/pulse/hub.log | grep Audio`

---

## 🚀 Start Pulse System

After verifying everything works:

```bash
# Start services
sudo systemctl start pulse-hub.service
sudo systemctl start pulse-dashboard.service

# Enable services to start on boot
sudo systemctl enable pulse-hub.service
sudo systemctl enable pulse-dashboard.service

# Check status
systemctl status pulse-hub.service
systemctl status pulse-dashboard.service

# View logs
journalctl -u pulse-hub.service -f
```

Or use the manual start script:
```bash
cd /opt/pulse
./start_pulse.sh
```

---

## 📊 Dashboard Access

After services start:
- **Web UI**: http://raspberry-pi-ip:8080
- **API**: http://raspberry-pi-ip:8080/api/sensors/current

---

## 📝 What Should Work After Setup

### Temperature & Humidity:
- 🌡️ Real-time temperature readings in °F and °C
- 💧 Humidity percentage
- 🔄 Updates every 30 seconds
- 📈 Historical trends and graphs

### Song Detection:
- 🎵 Automatic song detection every 30 seconds
- 🎵 Song title and artist displayed
- 🎵 Song history logged to database
- 🎵 No API keys required (uses ShazamIO)

### Audio Monitoring:
- 🔊 Real-time decibel (dB) levels
- 📊 Peak dB tracking
- 🎚️ Audio level meters on dashboard

### People Counting:
- 👥 Real-time occupancy count
- 📥 Entry/exit tracking
- 📷 Live camera snapshot
- 📊 Traffic statistics

---

## 🆘 Still Having Issues?

Run the diagnostic script:
```bash
cd /opt/pulse
bash diagnose_temp_only.sh
```

Or check the comprehensive troubleshooting guide:
```bash
cat /opt/pulse/TROUBLESHOOTING.md
```

---

## 📦 Installed Dependencies Reference

The `requirements.txt` includes:

**Temperature Sensor:**
- `Adafruit-Blinka>=8.0.0` - Raspberry Pi GPIO/I2C support
- `adafruit-circuitpython-bme280==2.6.23` - BME280 sensor library

**Song Detection:**
- `shazamio>=0.4.0` - Song recognition
- `aiohttp<4.0.0` - HTTP client for ShazamIO

**Audio Processing:**
- `numpy==1.26.4` - Numerical processing
- `sounddevice==0.4.6` - Audio capture
- `librosa>=0.10.2` - Audio analysis

**System:**
- `i2c-tools` (apt package) - I2C utilities
- `portaudio19-dev` (apt package) - Audio I/O

All of these are automatically installed by `install.sh` and `requirements.txt`.
