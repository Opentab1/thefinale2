# Pulse 1.0 - Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Raspberry Pi 5 (8GB recommended)
- Fresh install of Raspberry Pi OS (64-bit)
- Internet connection
- Display, keyboard, mouse (for initial setup)

---

## Installation

### Step 1: Open Terminal

On your Raspberry Pi, open a terminal window.

### Step 2: Run Installation Command

Copy and paste this single command:

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

If you previously experienced an install error on Python 3.13 (e.g., `BackendUnavailable: Cannot import 'setuptools.build_meta'`), re-run the command above; the installer now upgrades build tooling and pins dependencies to Python 3.13-compatible wheels.

⏱️ **Installation takes ~15-20 minutes**

What it does:
- ✓ Updates system packages
- ✓ Installs dependencies
- ✓ Sets up Pulse software
- ✓ Configures services
- ✓ Tests hardware
- ✓ Reboots system

### Step 3: Complete Setup Wizard

After reboot, **wait 30-60 seconds** for the system to start services.

The setup wizard will automatically open in your browser at `http://localhost:9090`.

**If the wizard doesn't appear:**
- Wait a bit longer (services take time to start on first boot)
- Manually open Chromium browser and go to `http://localhost:9090`
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed recovery steps

**Fill in the wizard:**
1. **Venue name** (e.g., "Joe's Bar")
2. **Timezone** (select from dropdown)
3. **Hardware check** (shows detected sensors - click Next)
4. **Smart integrations** (skip if you don't have them yet)
5. **Automation limits** (use defaults or customize)

Click **"Complete Setup"** → System reboots again

### Step 4: Dashboard Auto-Launches

After the second reboot, the dashboard opens automatically at `http://localhost:8080`.

**Wait 30-60 seconds** for services to start.

**You're done!** 🎉

💡 **Tip:** If you see a blank screen after either reboot, press `Ctrl+Alt+F2` to access the terminal and check service status with `sudo systemctl status pulse-*`

---

## First Actions

### 1. Check System Health
- Go to **Health** tab
- Verify all sensors show ✓ (green)
- Missing sensors are OK - system adapts

### 2. Try Manual Controls
- Go to **Controls** tab
- Toggle any system from **Auto** to **Manual**
- Adjust settings (lighting brightness, etc.)
- Toggle back to **Auto**

### 3. View Live Data
- Go to **Live** tab
- Watch occupancy count update
- Monitor temperature and humidity
- Check comfort index

### 4. Explore Analytics
- Go to **Analytics** tab
- View historical trends
- Change time range (24h, 48h, 7 days)

---

## Common First-Time Questions

### Q: Can I use Pulse without smart home devices?
**A:** Yes! Pulse works great with just the sensors. You'll get occupancy tracking, environmental monitoring, and analytics.

### Q: What if a sensor isn't detected?
**A:** Pulse automatically disables it and continues working. You can add sensors later without reinstalling.

### Q: How do I add Nest/Hue/Spotify later?
**A:** Go to **Settings** → **Integrations** → Enter credentials → Save

### Q: Can I turn off automation?
**A:** Yes! Click the **Safe Mode** button (top right) to disable all automation instantly.

### Q: How do I exit kiosk mode?
**A:** Press **ESC** key to exit fullscreen. Press **F11** to re-enter.

---

## Next Steps

### Connect Smart Home Devices

**Google Nest (HVAC)**
1. Create Google Cloud project
2. Enable Smart Device Management API
3. Get OAuth credentials
4. Add to `/opt/pulse/.env`

**Philips Hue (Lighting)**
1. Find bridge IP address
2. Press bridge button
3. Run: `cd /opt/pulse && venv/bin/python3 -c "from services.controls.lighting_hue import *; controller = HueLightingController('YOUR_BRIDGE_IP')"`
4. Copy username to `/opt/pulse/.env`

**Spotify (Music)**
1. Create Spotify app at developer.spotify.com
2. Get Client ID and Secret
3. Add to `/opt/pulse/.env`

### Customize Settings

Edit `/opt/pulse/config/config.yaml`:
- Change venue name
- Adjust automation limits
- Set operating hours

Restart services:
```bash
sudo systemctl restart pulse-hub pulse-dashboard
```

---

## Troubleshooting

### Wizard doesn't appear after reboot

**Quick fix:**
```bash
# Check if wizard service is running
sudo systemctl status pulse-firstboot.service

# If not running, start it
sudo systemctl start pulse-firstboot.service

# Then open browser to http://localhost:9090
```

### Dashboard won't load
```bash
sudo systemctl status pulse-dashboard
sudo systemctl restart pulse-dashboard
```

### Check logs
```bash
tail -f /var/log/pulse/hub.log
tail -f /var/log/pulse/dashboard.log
sudo journalctl -u pulse-firstboot.service -n 50
```

### Restart all services
```bash
sudo systemctl restart pulse-*
```

### Full reset (start wizard again)
```bash
sudo rm /opt/pulse/config/.wizard_complete
sudo reboot
```

**For detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)**

---

## Support

- 📖 **Full Documentation**: [README.md](README.md)
- 🐛 **Report Issues**: GitHub Issues
- 💬 **Get Help**: GitHub Discussions
- 🤝 **Contribute**: [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Hardware Expansion

### Recommended Add-Ons

**Week 1** (Core sensors)
- USB Microphone → Audio detection
- Camera → People counting

**Week 2** (Environmental)
- BME280 → Temperature/humidity
- Pan-Tilt HAT → Better camera coverage

**Week 3** (Smart home)
- Nest Thermostat → HVAC control
- Philips Hue → Lighting control

**Week 4** (Premium)
- AI Hat → Faster computer vision
- Multiple cameras → Multi-zone tracking

---

**You're all set!** Pulse is now learning about your venue and optimizing automatically. Sit back and watch it work. 🎵
