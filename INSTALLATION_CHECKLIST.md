# ✅ RPI 5 INSTALLATION CHECKLIST

**Quick reference for fresh SD card setup**

Print this or keep it on your phone while installing!

---

## 🎯 GOAL

Install branch: `cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d`  
Target commit: `ad7257f` (Nov 7, 2025)

---

## 📋 PRE-INSTALL

```bash
□ Fresh Raspberry Pi OS installed
□ sudo apt update && sudo apt upgrade -y
□ sudo apt install -y git python3 python3-pip python3-venv \
    build-essential cmake pkg-config libatlas-base-dev \
    libopenblas-dev python3-dev python3-numpy \
    portaudio19-dev libportaudio2 ffmpeg i2c-tools
□ sudo raspi-config nonint do_i2c 0
□ sudo raspi-config nonint do_camera 0
□ sudo reboot
```

---

## 📦 INSTALLATION STEPS

### 1. Clone Repo
```bash
□ sudo mkdir -p /opt/pulse
□ sudo chown pi:pi /opt/pulse
□ cd /opt/pulse
□ git clone https://github.com/Opentab1/finale2.git .
□ git checkout cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d
□ git log --oneline -1   # Verify: ad7257f
```

### 2. Python Setup
```bash
□ cd /opt/pulse
□ python3 -m venv venv
□ source venv/bin/activate
□ pip install --upgrade pip
□ pip install -r requirements.txt
□ pip install sounddevice shazamio
```

### 3. Create Directories
```bash
□ mkdir -p /opt/pulse/data
□ mkdir -p /var/log/pulse
□ sudo chown -R pi:pi /opt/pulse
□ sudo chown -R pi:pi /var/log/pulse
```

### 4. Test Hardware
```bash
□ arecord -l                    # Audio device found?
□ libcamera-still -o test.jpg   # Camera works?
```

### 5. Install Services
```bash
□ cd /opt/pulse
□ bash install_separate_services.sh
```

### 6. Verify Services
```bash
□ sudo systemctl status pulse-audio      # Active?
□ sudo systemctl status pulse-camera     # Active?
□ sudo systemctl status pulse-hub-main   # Active?
```

### 7. Check Logs
```bash
□ sudo journalctl -u pulse-audio -n 20   # No errors?
□ sudo journalctl -u pulse-camera -n 20  # No errors?
□ sudo journalctl -u pulse-hub-main -n 20 # No errors?
```

### 8. Verify Cache Files
```bash
□ ls -lh /opt/pulse/data/people_cache.json  # Exists?
□ cat /opt/pulse/data/people_cache.json     # Has data?
```

---

## ✅ SUCCESS INDICATORS

**Audio Service Logs Should Show:**
```
✅ Decibel detection enabled
✅ Song detection enabled
🔊 dB reading: XX.X dB
🎵 Song detected: Title - Artist
```

**Camera Service Logs Should Show:**
```
🎥 CAMERA SERVICE RUNNING
📁 Cache updated: occupancy=X, entries=Y, exits=Z
```

**Hub Service Logs Should Show:**
```
👥 People from cache: occupancy=X, entries=Y, exits=Z
🔊 dB from cache: XX.X dB
🎵 Song from cache: Title - Artist
```

---

## 🆘 QUICK FIXES

**Audio won't start:**
```bash
source /opt/pulse/venv/bin/activate
pip install sounddevice shazamio numpy
sudo systemctl restart pulse-audio
```

**Camera won't start:**
```bash
libcamera-still --list-cameras
sudo raspi-config nonint do_camera 0
sudo reboot
```

**Cache files missing:**
```bash
sudo chown -R pi:pi /opt/pulse/data
sudo systemctl restart pulse-camera pulse-hub-main
```

**Dashboard shows zeros:**
```bash
sudo cp /opt/pulse/services/systemd/pulse-hub-main.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart pulse-hub-main
```

---

## 📱 USEFUL COMMANDS

**View all service status:**
```bash
systemctl status pulse-audio pulse-camera pulse-hub-main
```

**Follow all logs:**
```bash
# Terminal 1:
sudo journalctl -u pulse-audio -f

# Terminal 2:
sudo journalctl -u pulse-camera -f

# Terminal 3:
sudo journalctl -u pulse-hub-main -f
```

**Restart everything:**
```bash
sudo systemctl restart pulse.service
```

**Check commit:**
```bash
cd /opt/pulse && git log --oneline -1
```

---

## 🎯 VERIFICATION ONE-LINER

```bash
cd /opt/pulse && \
git log --oneline -1 && \
systemctl is-active pulse-audio pulse-camera pulse-hub-main && \
ls -1 run_*.py | wc -l
```

**Expected output:**
```
ad7257f Fix: Change cache logging from debug to info for visibility
active
active
active
3
```

---

## 📊 FILES THAT SHOULD EXIST

```bash
✅ /opt/pulse/run_audio_service.py
✅ /opt/pulse/run_camera_service.py
✅ /opt/pulse/run_hub_service.py
✅ /opt/pulse/services/sensors/simple_decibel_detector.py
✅ /opt/pulse/services/sensors/simple_song_detector.py
✅ /opt/pulse/install_separate_services.sh
✅ /etc/systemd/system/pulse-audio.service
✅ /etc/systemd/system/pulse-camera.service
✅ /etc/systemd/system/pulse-hub-main.service
✅ /opt/pulse/data/people_cache.json (after services start)
```

---

## ✨ DONE!

When everything works:
- [ ] All 3 services active
- [ ] No errors in logs
- [ ] Cache file exists and updates
- [ ] Dashboard shows live data
- [ ] System stable for 1+ hour

**You're good to go! 🎉**
