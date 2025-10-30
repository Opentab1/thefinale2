# 🚀 Pulse Simple Dashboard - Startup Instructions

## For Fresh Raspberry Pi Installation

After flashing a new SD card and cloning the repo, follow these steps:

### 1. **Clone the Repository**
```bash
git clone https://github.com/Opentab1/thefinale2.git /opt/pulse
cd /opt/pulse
```

### 2. **Install Dependencies** (if needed)
```bash
pip3 install flask flask-cors
```

### 3. **Install Simple Dashboard as System Service**
```bash
cd /opt/pulse
./INSTALL_SIMPLE_DASHBOARD.sh
```

This will:
- ✅ Stop old dashboard services
- ✅ Install the simple dashboard as a systemd service
- ✅ Enable auto-start on boot
- ✅ Start the dashboard immediately

### 4. **Access the Dashboard**
Open your browser to:
```
http://<your-pi-ip>:8080
```

**Note:** Sensors take 30-40 seconds to warm up and show data.

---

## Manual Start (Without Systemd)

If you prefer to run manually:

```bash
cd /opt/pulse
./start_simple_dashboard.sh
```

---

## Commands

### Check Dashboard Status
```bash
sudo systemctl status pulse.service
```

### View Live Logs
```bash
sudo journalctl -u pulse.service -f
```

### Restart Dashboard
```bash
sudo systemctl restart pulse.service
```

### Stop Dashboard
```bash
sudo systemctl stop pulse.service
```

### Disable Auto-Start
```bash
sudo systemctl disable pulse.service
```

---

## What Gets Auto-Started

After running `INSTALL_SIMPLE_DASHBOARD.sh`, the simple dashboard will:
- ✅ Start automatically on boot
- ✅ Restart automatically if it crashes
- ✅ Run on port 8080
- ✅ Show real sensor data from:
  - 🔊 Microphone (audio levels)
  - 💡 Camera (light levels)
  - 🌡️ BME280 (temp/humidity if connected)
  - 🎵 Database (current song)

---

## Troubleshooting

### Dashboard shows zeros
Wait 30-40 seconds for sensors to warm up. Light sensor especially needs time to initialize camera.

### Port 8080 already in use
```bash
sudo systemctl stop pulse.service
sudo fuser -k 8080/tcp
./start_simple_dashboard.sh
```

### Check sensor data
```bash
curl http://localhost:8080/data
```

Should return:
```json
{"comfort":100,"decibels":55.2,"humidity":0,"indoorTemp":0,"light":650,"song":"—"}
```

---

## Fresh Pi Setup Summary

**ONE COMMAND to get everything working:**
```bash
cd /opt/pulse && ./INSTALL_SIMPLE_DASHBOARD.sh
```

Then access: `http://<pi-ip>:8080` 🎉
