# 🎯 Pulse Local Dashboard (RPi 5)

**Beautiful, local-only dashboard. No AWS, no login, no cloud.**

---

## ✨ Features

- 🏠 **100% Local** — Runs on `http://localhost:8080`
- 🎨 **Beautiful UI** — Tailwind-style design with gradients
- 📊 **Real-time Data** — Decibels, Light, Temp, Humidity, Song, Comfort
- 🚀 **Auto-start on Boot** — Systemd service included
- ⚡ **1-line Install** — Just run the script

---

## 📦 Installation

```bash
./install_local_dashboard.sh
```

That's it! Dashboard will open automatically.

---

## 🔧 Manual Setup (if needed)

```bash
# Install Flask
pip3 install flask

# Run dashboard
python3 rpi/local_dashboard.py

# Access at http://localhost:8080
```

---

## 🎮 Usage

### Access Dashboard
```bash
# On the Pi itself
http://localhost:8080

# From another device on same network
http://<pi-ip-address>:8080
```

### Systemd Control
```bash
# Check status
sudo systemctl status pulse-local-dashboard

# Start/Stop/Restart
sudo systemctl start pulse-local-dashboard
sudo systemctl stop pulse-local-dashboard
sudo systemctl restart pulse-local-dashboard

# Enable/Disable auto-start
sudo systemctl enable pulse-local-dashboard
sudo systemctl disable pulse-local-dashboard

# View logs
sudo journalctl -u pulse-local-dashboard -f
```

---

## 📁 Files Created

- `rpi/local_dashboard.py` — Flask server with simulated data
- `rpi/templates/index.html` — Beautiful UI (already existed)
- `rpi/pulse-local-dashboard.service` — Systemd service
- `install_local_dashboard.sh` — 1-line installer

---

## 🔌 Integration with Real Sensors

The dashboard currently uses **simulated data**. To connect real sensors:

1. Replace the `update_data()` function in `rpi/local_dashboard.py`
2. Import your sensor modules
3. Read from actual sensors instead of `random` values

Example:
```python
def update_data():
    global data
    while True:
        data = {
            "decibels": read_microphone(),
            "light": read_light_sensor(),
            "indoorTemp": read_temperature(),
            "humidity": read_humidity(),
            "song": get_current_song(),
            "comfort": calculate_comfort()
        }
        time.sleep(2)
```

---

## 🎨 UI Preview

The dashboard shows:
- **Current Song** — Large card at top
- **Crowd Energy** — Decibel meter with bar
- **Comfort** — Score out of 100
- **Light** — Lux reading with bar
- **Temperature** — Indoor temp in °F
- **Humidity** — Percentage with bar
- **Status** — Live/Offline indicator

---

## 🚀 Kiosk Mode (Full Screen)

To launch in kiosk mode on boot:

```bash
# Edit the service file
sudo nano /etc/systemd/system/pulse-local-dashboard.service

# Or use the browser auto-open in install script
```

The installer already tries to open Chromium in kiosk mode!

---

## 🐛 Troubleshooting

### Dashboard won't start
```bash
sudo systemctl status pulse-local-dashboard
sudo journalctl -u pulse-local-dashboard -f
```

### Port 8080 already in use
```bash
# Check what's using port 8080
sudo lsof -i :8080

# Kill the process
sudo kill -9 <PID>

# Or change port in rpi/local_dashboard.py
app.run(host='0.0.0.0', port=XXXX)
```

### Flask not found
```bash
pip3 install flask
# or
sudo pip3 install flask
```

---

## 🎯 No AWS Required

This dashboard is **completely independent** of the AWS/Cognito setup. It:
- ✅ Runs locally on the Pi
- ✅ No authentication needed
- ✅ No internet required
- ✅ No cloud dependencies
- ✅ Works offline

The AWS sync can still run in the background if configured, but this dashboard doesn't need it.

---

## 📝 Notes

- Default port: **8080**
- Default user: **pi**
- Auto-starts on boot via systemd
- Uses simulated data (customize as needed)
- Beautiful gradient UI with live updates every 2 seconds

---

**Enjoy your local Pulse Dashboard! 🎉**
