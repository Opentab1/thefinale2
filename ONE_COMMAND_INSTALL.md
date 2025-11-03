# 🚀 ONE COMMAND - Complete Pulse Installation

## What You Want

Run **ONE command** → Setup wizard appears → Click through wizard → Everything works perfectly.

## The ONE Command

On your Raspberry Pi 5, run this **ONE command**:

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

That's it! No coding, no configuration files, no manual setup.

---

## What Happens Automatically

### 1. Installation (~15-20 minutes)
The script automatically:
- ✅ Updates system packages
- ✅ Installs all dependencies (Python, Node.js, cameras, sensors)
- ✅ Clones the code from GitHub
- ✅ Sets up Python virtual environment
- ✅ Installs all Python packages
- ✅ Builds the dashboard
- ✅ Configures system services
- ✅ Detects your hardware (camera, mic, sensors)
- ✅ Sets up auto-login and kiosk mode
- ✅ Reboots automatically

### 2. After Reboot (~60 seconds)
Your Pi will:
- ✅ Boot up
- ✅ Automatically start the setup wizard
- ✅ Open browser to: **http://localhost:9090**

### 3. Setup Wizard (2-3 minutes of clicking)
You'll see a beautiful wizard where you:
1. **Venue Setup** - Enter your venue name and timezone
2. **Hardware Check** - See what sensors are detected (automatic)
3. **Smart Integrations** - Enable/skip Nest, Hue, Spotify (optional)
4. **Automation Limits** - Set safe temperature/light/volume ranges
5. **Complete** - Click "Complete Setup"

### 4. Final Reboot (~60 seconds)
The system will:
- ✅ Save your settings
- ✅ Reboot one more time
- ✅ Start all services
- ✅ Open dashboard automatically at: **http://localhost:8080**

---

## After Installation

### Your Dashboard Will Be Live At:
```
http://localhost:8080          (from the Pi itself)
http://<your-pi-ip>:8080       (from any device on your network)
```

### What You'll See:
- 🎵 **Now Playing** - Current song detection
- 🔊 **Sound Level** - Real-time decibel readings
- 💡 **Light Level** - Ambient brightness
- 🌡️ **Temperature** - From BME280 sensor
- 💧 **Humidity** - From BME280 sensor  
- 😊 **Comfort Score** - Calculated from all sensors
- 👥 **Occupancy** - AI people counting (if camera connected)

### Everything Auto-Starts:
- ✅ Dashboard runs on boot
- ✅ All sensors start automatically
- ✅ System self-heals if sensors fail
- ✅ Kiosk mode launches dashboard in fullscreen

---

## Alternative: Clone First (If Preferred)

If you want to clone the repo yourself first:

```bash
sudo git clone https://github.com/Opentab1/thefinale2.git /opt/pulse && cd /opt/pulse && sudo ./install.sh
```

This does the exact same thing, just gives you a local copy first.

---

## Total Time Investment

| Step | Time | Your Effort |
|------|------|-------------|
| Run install command | 1 second | Type one command |
| Wait for installation | 15-20 min | None - automatic |
| First reboot | 60 sec | None - automatic |
| Click through wizard | 2-3 min | Click "Next" 4 times |
| Final reboot | 60 sec | None - automatic |
| **TOTAL** | **~25 minutes** | **~2 minutes of clicking** |

---

## Useful Commands After Installation

### Check if everything is running:
```bash
sudo systemctl status pulse.service
```

### View live logs:
```bash
sudo journalctl -u pulse.service -f
```

### Restart the dashboard:
```bash
sudo systemctl restart pulse.service
```

### Reboot the Pi:
```bash
sudo reboot
```

---

## What If Something Goes Wrong?

### Installation fails:
```bash
# Check the installation log
cat /tmp/pulse_install.log
```

### Wizard doesn't appear after reboot:
```bash
# Manually start the wizard
sudo systemctl start pulse-firstboot.service

# Then open browser to: http://localhost:9090
```

### Dashboard doesn't appear after wizard:
```bash
# Check service status
sudo systemctl status pulse.service

# Check logs
sudo journalctl -u pulse.service -n 50
```

### Need to reset and start over:
```bash
sudo rm -rf /opt/pulse
sudo rm -f /etc/systemd/system/pulse*.service
sudo systemctl daemon-reload

# Then run the ONE command again
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

---

## That's It!

**No coding. No configuration files. No manual setup.**

Just run ONE command and click through a wizard. 🎉

---

## The ONE Command Again:

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

Copy, paste, press Enter, and you're done! ✨
