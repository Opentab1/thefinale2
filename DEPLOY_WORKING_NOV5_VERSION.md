# ✅ DEPLOY EXACT NOV 5-7 WORKING VERSION

**Branch:** `cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d`  
**Commit:** `ad7257f`  
**Status:** THIS IS WHAT WORKED FOR YOU

---

## 🚀 COMMANDS FOR YOUR RASPBERRY PI

Copy and paste these **EXACT** commands you used before:

### STEP 1: Get the Working Code
```bash
cd /opt/pulse && git fetch origin && git checkout cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d && git log --oneline -1
```
**Expected output:** `ad7257f Fix: Change cache logging from debug to info for visibility`

### STEP 2: Activate venv and Install Dependencies
```bash
source venv/bin/activate && pip install sounddevice shazamio
```

### STEP 3: Link Camera Libraries
```bash
ln -sf /usr/lib/python3/dist-packages/libcamera /opt/pulse/venv/lib/python3.13/site-packages/ && ln -sf /usr/lib/python3/dist-packages/_libcamera.cpython-313-aarch64-linux-gnu.so /opt/pulse/venv/lib/python3.13/site-packages/ && ln -sf /usr/lib/python3/dist-packages/pykms /opt/pulse/venv/lib/python3.13/site-packages/
```

### STEP 4: Install Separate Services (THE KEY!)
```bash
bash install_separate_services.sh
```

### STEP 5: Build Dashboard
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt install -y nodejs
```

```bash
cd /opt/pulse/dashboard/ui && npm install && npm run build
```

```bash
sudo systemctl restart pulse-hub-main
```

### STEP 6: Verify Everything Works
```bash
systemctl is-active pulse-audio pulse-camera pulse-hub-main && sudo journalctl -u pulse-audio -n 20 && sudo journalctl -u pulse-camera -n 20 && sudo journalctl -u pulse-hub-main -n 20 && hostname -I
```

---

## ✅ EXPECTED SUCCESS INDICATORS

**Git commit:** `ad7257f`  
**Services:** All 3 show `active`  
**IP address:** Displayed at end  
**Camera logs:** Show "Camera started"  
**Hub logs:** Show sensor readings  
**Audio logs:** Show "Song detection loop started"

---

## 📋 WHAT THIS VERSION HAS

1. ✅ simple_song_detector.py (296 lines - Nov 5th)
2. ✅ simple_decibel_detector.py (216 lines - Nov 5th)
3. ✅ run_audio_service.py (165 lines - Nov 5th)
4. ✅ install_separate_services.sh (the installer)
5. ✅ Cache file communication (hub reads from cache)
6. ✅ Separate services (fault isolation)
7. ✅ Correct logging (info level, not debug)

---

## 🎯 THIS WILL WORK BECAUSE:

- This is the EXACT branch you used Nov 5-7
- This is commit ad7257f that worked
- This has the install script
- This has all the Nov 5-7 fixes
- Files are 296, 216, 165 lines (correct)

---

**RUN THOSE COMMANDS ON YOUR PI NOW!** 🚀
