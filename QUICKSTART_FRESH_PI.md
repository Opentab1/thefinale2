# 🚀 Fresh Pi Quick Start

## For Brand New SD Card

After flashing Raspberry Pi OS, run **ONE COMMAND**:

```bash
git clone https://github.com/Opentab1/thefinale2.git /opt/pulse && cd /opt/pulse && ./INSTALL_SIMPLE_DASHBOARD.sh
```

## What This Does

1. Clones the repo to `/opt/pulse`
2. Installs simple dashboard as system service
3. Enables auto-start on boot
4. Starts dashboard immediately

## Access Dashboard

Open browser to: `http://<your-pi-ip>:8080`

Wait 30-40 seconds for sensors to warm up.

## What You'll See

- 🌡️ Temperature: Real data from BME280
- 💧 Humidity: Real data from BME280
- 🔊 Sound: Real-time microphone levels
- 💡 Light: Camera-based brightness
- 🎵 Song: Current track playing
- 😊 Comfort: Calculated score

All updating live every 2 seconds!

## That's It!

No AWS setup. No authentication. No configuration files.

Just clone and run. Everything works automatically.

## Need to Restart?

```bash
sudo systemctl restart pulse.service
```

## View Logs

```bash
sudo journalctl -u pulse.service -f
```

---

**Guaranteed to work on fresh Pi. One command. Done.** ✅
