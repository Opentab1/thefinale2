# 🔧 TROUBLESHOOTING QUICK REFERENCE

**Fast fixes for common installation problems**

---

## 🚨 EMERGENCY DIAGNOSTICS

### One-Command Health Check
```bash
#!/bin/bash
echo "=== PULSE HEALTH CHECK ===" && \
cd /opt/pulse && git log --oneline -1 && \
echo "" && echo "Services:" && \
systemctl is-active pulse-audio pulse-camera pulse-hub-main && \
echo "" && echo "Cache files:" && \
ls -lh /opt/pulse/data/people_cache.json 2>&1 && \
echo "" && echo "Recent errors:" && \
sudo journalctl -u pulse-audio --since "5 min ago" | grep -i error | tail -3 && \
sudo journalctl -u pulse-camera --since "5 min ago" | grep -i error | tail -3 && \
sudo journalctl -u pulse-hub-main --since "5 min ago" | grep -i error | tail -3
```

---

## 🎯 PROBLEM → SOLUTION

### ❌ Problem: "git clone" permission denied

**Symptoms:**
```
Permission denied (publickey)
fatal: Could not read from remote repository
```

**Solution:**
```bash
# Use HTTPS instead of SSH
cd /opt/pulse
rm -rf *
git clone https://github.com/Opentab1/finale2.git .
```

---

### ❌ Problem: Wrong branch/commit

**Symptoms:**
```bash
git log --oneline -1
# Shows something other than: ad7257f
```

**Solution:**
```bash
cd /opt/pulse
git fetch origin
git checkout cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d
git pull origin cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d
git log --oneline -1
# Should now show: ad7257f
```

---

### ❌ Problem: pip install fails

**Symptoms:**
```
error: externally-managed-environment
```

**Solution:**
```bash
# Use virtual environment (correct way)
cd /opt/pulse
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# If venv creation fails, install venv
sudo apt install python3-venv
```

---

### ❌ Problem: sounddevice installation fails

**Symptoms:**
```
error: Failed building wheel for sounddevice
```

**Solution:**
```bash
# Install system dependencies first
sudo apt install -y portaudio19-dev libportaudio2 python3-dev

# Then try again
source /opt/pulse/venv/bin/activate
pip install sounddevice
```

---

### ❌ Problem: Audio service fails - "No audio input device"

**Symptoms:**
```bash
sudo journalctl -u pulse-audio -n 20
# Shows: sounddevice.PortAudioError: No input device
```

**Solution:**
```bash
# List audio devices
arecord -l

# If no devices found, check hardware connection
# If USB mic, try different USB port

# If device exists, set default in ALSA
sudo nano /etc/asound.conf

# Add:
defaults.pcm.card 0
defaults.ctl.card 0

# Restart service
sudo systemctl restart pulse-audio
```

---

### ❌ Problem: Camera service fails - "Failed to allocate camera"

**Symptoms:**
```bash
sudo journalctl -u pulse-camera -n 20
# Shows: libcamera error or camera busy
```

**Solution:**
```bash
# Check if camera enabled
sudo raspi-config nonint do_camera 0

# Check if camera detected
libcamera-still --list-cameras

# Kill any process using camera
sudo pkill libcamera

# Check if another service is using it
ps aux | grep camera

# Restart camera service
sudo systemctl restart pulse-camera
```

---

### ❌ Problem: Service won't start - "No such file or directory"

**Symptoms:**
```bash
sudo systemctl status pulse-audio
# Shows: ExecStart=/opt/pulse/venv/bin/python3: No such file
```

**Solution:**
```bash
# Virtual environment not created properly
cd /opt/pulse
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install sounddevice shazamio

# Restart service
sudo systemctl restart pulse-audio
```

---

### ❌ Problem: Service starts then immediately fails

**Symptoms:**
```bash
sudo systemctl status pulse-audio
# Shows: Active: failed (Result: exit-code)
```

**Solution:**
```bash
# Check the actual error
sudo journalctl -u pulse-audio -n 50

# Common issues:
# 1. Missing Python module
source /opt/pulse/venv/bin/activate
pip install <missing_module>

# 2. Permission issue
sudo chown -R pi:pi /opt/pulse
sudo chown -R pi:pi /var/log/pulse

# 3. Wrong Python path in service file
systemctl cat pulse-audio | grep ExecStart
# Should be: /opt/pulse/venv/bin/python3

# Restart
sudo systemctl restart pulse-audio
```

---

### ❌ Problem: Cache file not created

**Symptoms:**
```bash
ls /opt/pulse/data/people_cache.json
# No such file or directory
```

**Solution:**
```bash
# 1. Check directory exists and has permissions
sudo mkdir -p /opt/pulse/data
sudo chown -R pi:pi /opt/pulse/data
sudo chmod 755 /opt/pulse/data

# 2. Check camera service is running
sudo systemctl status pulse-camera
# Should be: Active (running)

# 3. Watch logs to see if it's trying to write
sudo journalctl -u pulse-camera -f
# Should see: "📁 Cache updated: ..."

# 4. If not writing, restart service
sudo systemctl restart pulse-camera

# 5. Wait 10 seconds and check again
sleep 10
ls -lh /opt/pulse/data/people_cache.json
```

---

### ❌ Problem: Dashboard shows zeros for everything

**Symptoms:**
- Dashboard loads
- All values show 0 or "Unknown"
- No real data displayed

**Solution:**
```bash
# 1. Check if hub service has environment variables
systemctl cat pulse-hub-main | grep PULSE_DISABLE

# Should show:
# Environment="PULSE_DISABLE_AUDIO=1"
# Environment="PULSE_DISABLE_CAMERA=1"

# If missing:
sudo cp /opt/pulse/services/systemd/pulse-hub-main.service /etc/systemd/system/
sudo systemctl daemon-reload

# 2. Check cache files exist
ls -lh /opt/pulse/data/people_cache.json
cat /opt/pulse/data/people_cache.json

# 3. Check hub logs for cache reading
sudo journalctl -u pulse-hub-main -n 50 | grep cache
# Should see: "👥 People from cache: ..."

# 4. Restart hub
sudo systemctl restart pulse-hub-main

# 5. Check API directly
curl http://localhost:8000/api/sensors | python3 -m json.tool
```

---

### ❌ Problem: Service keeps restarting every few seconds

**Symptoms:**
```bash
sudo systemctl status pulse-audio
# Shows: Activating... Deactivating... over and over
```

**Solution:**
```bash
# This means the service is crashing on startup

# 1. Check logs for the actual error
sudo journalctl -u pulse-audio -n 100 | less
# Look for Python traceback or error message

# 2. Try running manually to see error
cd /opt/pulse
source venv/bin/activate
python3 run_audio_service.py
# Will show error directly

# 3. Common fixes:
# - Missing dependency: pip install <package>
# - Wrong path: Check paths in run_audio_service.py
# - Permission issue: sudo chown -R pi:pi /opt/pulse

# 4. After fixing, restart
sudo systemctl restart pulse-audio
```

---

### ❌ Problem: "Module not found" error

**Symptoms:**
```bash
sudo journalctl -u pulse-audio -n 20
# Shows: ModuleNotFoundError: No module named 'sounddevice'
```

**Solution:**
```bash
# Wrong Python or venv not activated in service

# 1. Check service file Python path
systemctl cat pulse-audio | grep ExecStart

# Should be: /opt/pulse/venv/bin/python3 (with venv)

# 2. If wrong, fix service file
sudo nano /etc/systemd/system/pulse-audio.service

# ExecStart should be:
# ExecStart=/opt/pulse/venv/bin/python3 /opt/pulse/run_audio_service.py

# 3. Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart pulse-audio
```

---

### ❌ Problem: "ImportError: libportaudio.so.2"

**Symptoms:**
```
ImportError: libportaudio.so.2: cannot open shared object file
```

**Solution:**
```bash
# Missing system library
sudo apt install -y portaudio19-dev libportaudio2

# Restart service
sudo systemctl restart pulse-audio
```

---

### ❌ Problem: Services won't stop

**Symptoms:**
```bash
sudo systemctl stop pulse-audio
# Hangs or takes forever
```

**Solution:**
```bash
# Force kill
sudo pkill -9 -f run_audio_service.py
sudo pkill -9 -f run_camera_service.py
sudo pkill -9 -f run_hub_service.py

# Then start fresh
sudo systemctl start pulse.service
```

---

### ❌ Problem: Logs say "Cache file not found"

**Symptoms:**
```bash
sudo journalctl -u pulse-hub-main | grep cache
# Shows: Could not read people cache: [Errno 2] No such file
```

**Solution:**
```bash
# This is normal if camera service not running yet

# 1. Check camera service status
sudo systemctl status pulse-camera

# 2. If stopped, start it
sudo systemctl start pulse-camera

# 3. Wait 10 seconds for cache to be created
sleep 10

# 4. Verify cache exists
ls -lh /opt/pulse/data/people_cache.json

# 5. Check hub logs again
sudo journalctl -u pulse-hub-main -n 10
# Should now see: "👥 People from cache: ..."
```

---

### ❌ Problem: Database errors

**Symptoms:**
```bash
sudo journalctl -u pulse-hub-main | grep -i database
# Shows: OperationalError: no such table
```

**Solution:**
```bash
# Database not initialized

cd /opt/pulse
source venv/bin/activate
python3 << EOF
from storage.db import PulseDB
db = PulseDB()
print("✓ Database initialized")
EOF

# Restart services
sudo systemctl restart pulse-hub-main
```

---

## 🔄 NUCLEAR OPTION: Complete Reinstall

If nothing works, start fresh:

```bash
# 1. Stop and disable services
sudo systemctl stop pulse.service
sudo systemctl disable pulse-audio pulse-camera pulse-hub-main pulse.service

# 2. Remove service files
sudo rm /etc/systemd/system/pulse-*.service
sudo systemctl daemon-reload

# 3. Delete installation
sudo rm -rf /opt/pulse

# 4. Start from Step 1 of installation guide
# See: FRESH_RPI5_INSTALLATION_GUIDE.md
```

---

## 📱 USEFUL DIAGNOSTIC COMMANDS

### Check Everything at Once
```bash
cd /opt/pulse && \
echo "=== GIT STATUS ===" && git log --oneline -1 && \
echo "" && echo "=== SERVICE STATUS ===" && \
systemctl is-active pulse-audio pulse-camera pulse-hub-main && \
echo "" && echo "=== FILES ===" && \
ls -lh run_*.py && \
echo "" && echo "=== CACHE ===" && \
ls -lh data/*.json && \
echo "" && echo "=== RECENT ERRORS ===" && \
sudo journalctl -u pulse-audio --since "10 min ago" | grep -i "error\|failed" | tail -3
```

### Watch All Logs Simultaneously
```bash
# Install multitail if not present
sudo apt install -y multitail

# Watch all 3 logs at once
sudo multitail \
  -l "journalctl -u pulse-audio -f" \
  -l "journalctl -u pulse-camera -f" \
  -l "journalctl -u pulse-hub-main -f"
```

### Test Services Manually (Debug Mode)
```bash
# Stop systemd services
sudo systemctl stop pulse.service

# Run manually to see errors directly
cd /opt/pulse
source venv/bin/activate

# Terminal 1: Audio
python3 run_audio_service.py

# Terminal 2: Camera
python3 run_camera_service.py

# Terminal 3: Hub
python3 run_hub_service.py

# Ctrl+C to stop when done debugging
```

### Check Resource Usage
```bash
# CPU and memory usage
ps aux | grep -E "run_audio|run_camera|run_hub"

# Systemd resource limits
systemctl show pulse-audio -p MemoryLimit
systemctl show pulse-camera -p MemoryLimit
systemctl show pulse-hub-main -p MemoryMax
```

---

## 📞 STILL STUCK?

### Information to Gather

Before asking for help, gather this info:

```bash
# 1. System info
cat /etc/os-release
uname -a

# 2. Git status
cd /opt/pulse
git log --oneline -1
git status

# 3. Service status
systemctl status pulse-audio pulse-camera pulse-hub-main

# 4. Logs (last 50 lines of each)
sudo journalctl -u pulse-audio -n 50 > audio_logs.txt
sudo journalctl -u pulse-camera -n 50 > camera_logs.txt
sudo journalctl -u pulse-hub-main -n 50 > hub_logs.txt

# 5. File check
ls -la /opt/pulse/run_*.py
ls -la /opt/pulse/data/
ls -la /etc/systemd/system/pulse-*.service

# 6. Python environment
source /opt/pulse/venv/bin/activate
pip list | grep -E "sounddevice|shazamio|numpy"
```

Share all the above output for faster troubleshooting!

---

## ✅ SUCCESS CHECKLIST

System is working when ALL of these are true:

```bash
□ git log shows: ad7257f
□ All 3 services show: active (running)
□ /opt/pulse/data/people_cache.json exists and updates
□ Logs show: "👥 People from cache", "🔊 dB from cache"
□ No continuous errors in any log
□ Dashboard shows live data (not zeros)
□ Services stay running for 1+ hour
```

**If all checked, you're good! 🎉**
