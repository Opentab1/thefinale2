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
curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/pulse/main/install.sh | sudo bash
```

⏱️ **Installation takes ~15-20 minutes**

What it does:
- ✓ Updates system packages
- ✓ Installs dependencies
- ✓ Sets up Pulse software
- ✓ Configures services
- ✓ Tests hardware
- ✓ Reboots system

### Step 3: Complete Setup Wizard

After reboot, a setup wizard automatically opens.

**Fill in:**
1. **Venue name** (e.g., "Joe's Bar")
2. **Timezone** (select from dropdown)
3. **Smart integrations** (skip if you don't have them yet)
4. **Automation limits** (use defaults or customize)

Click **"Complete Setup"** → System reboots again

### Step 4: Dashboard Auto-Launches

The dashboard opens automatically at `http://localhost:8080`

**You're done!** 🎉

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

### Dashboard won't load
```bash
sudo systemctl status pulse-dashboard
sudo systemctl restart pulse-dashboard
```

### Check logs
```bash
tail -f /var/log/pulse/hub.log
tail -f /var/log/pulse/dashboard.log
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
