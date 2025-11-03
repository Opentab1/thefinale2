# 🚀 Fresh Pi Quick Start

## For Brand New SD Card

After flashing Raspberry Pi OS, run **ONE COMMAND**:

```bash
curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
```

## What Happens Automatically

1. **Installation (15-20 min)** - Installs everything automatically
2. **First Reboot** - System reboots
3. **Setup Wizard** - Opens at `http://localhost:9090`
4. **Click Through** - Takes 2-3 minutes
5. **Final Reboot** - System reboots again
6. **Dashboard Live** - Opens at `http://<your-pi-ip>:8080`

## Total Time: ~25 minutes (only 2 minutes of clicking)

**No coding. No configuration files. Just one command and a wizard.**

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
