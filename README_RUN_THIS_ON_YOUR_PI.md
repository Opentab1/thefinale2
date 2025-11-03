# 🚨 RUN THESE COMMANDS ON YOUR RASPBERRY PI 5 🚨

Your song detection and temperature sensor are not working because dependencies are missing.

## ⚡ QUICK FIX (Run on your Pi):

### Option 1: Automated Fix (RECOMMENDED)
```bash
cd /workspace
bash fix_dependencies.sh
```

This will:
- ✅ Install all missing Python packages (numpy, sounddevice, shazamio, BME280 libraries)
- ✅ Install system dependencies (PortAudio, I2C tools)
- ✅ Test all components
- ✅ Show you what's working and what needs attention

---

### Option 2: Run Diagnostics First (to see what's wrong)
```bash
cd /workspace
bash pi_diagnostic_commands.sh > diagnostic_output.txt
cat diagnostic_output.txt
```

**Then paste the entire output back to me** and I'll tell you exactly what to fix.

---

## 🔍 What I Need From You:

Run **ONE** of these commands on your Raspberry Pi and send me the output:

### Quick Diagnostic:
```bash
cd /workspace && bash pi_diagnostic_commands.sh
```

### Or manual check:
```bash
# Check installed packages
python3 -m pip list | grep -E "(numpy|shazam|sound|bme280|blinka)"

# Check running processes
ps aux | grep python | grep -v grep

# Check logs
tail -50 /var/log/pulse/hub.log

# Check I2C for temperature sensor
sudo i2cdetect -y 1

# Check microphone
arecord -l

# Test dashboard API
curl http://localhost:8080/api/sensors/current | python3 -m json.tool
```

---

## 📦 What's Been Fixed in the Repo:

I've committed these files to your git repo:

1. **`fix_dependencies.sh`** - Automated installer for all missing dependencies
2. **`pi_diagnostic_commands.sh`** - Comprehensive diagnostic script  
3. **`verify_fixes.py`** - Verification script to test components
4. **`FIXES_APPLIED_SONG_TEMP.md`** - Detailed documentation
5. **`COMMANDS_TO_RUN.md`** - Step-by-step command guide

---

## 🎯 Expected Results After Fix:

### Song Detection:
- 🎵 Detects songs every 30 seconds
- 🎵 Shows "Now Playing" on dashboard
- 🎵 Uses ShazamIO (no API key needed)

### Temperature Sensor:
- 🌡️ Shows temperature in °F
- 💧 Shows humidity %
- 🔄 Updates every 30 seconds

### Audio Monitoring:
- 🔊 Shows real-time dB levels
- 📊 Peak dB tracking

---

## 🐛 Common Issues & Solutions:

### "No module named 'shazamio'"
```bash
python3 -m pip install shazamio aiohttp
```

### "No module named 'adafruit_bme280'"
```bash
python3 -m pip install adafruit-blinka adafruit-circuitpython-bme280
```

### "PortAudio library not found"
```bash
sudo apt-get install -y portaudio19-dev libportaudio2
```

### "I2C device not found" (Temperature sensor)
```bash
# Enable I2C
sudo raspi-config
# → Interface Options → I2C → Yes

# Check if sensor is detected
sudo i2cdetect -y 1
# Should show "76" or "77" in the grid
```

### "No audio input devices"
```bash
# Check if microphone is connected
arecord -l

# Test recording
arecord -d 5 test.wav
aplay test.wav
```

---

## 📝 After Running Commands:

1. **Copy ALL the output** from the diagnostic script
2. **Paste it back to me** in the chat
3. I'll tell you **exactly** what's wrong and how to fix it
4. We'll fix it both **on your Pi** and **in the git repo**

---

## 🔄 After Fixes Are Applied:

```bash
# Restart the Pulse system
cd /workspace
./start_pulse.sh

# Open dashboard in browser
http://localhost:8080

# Verify fixes worked
python3 verify_fixes.py
```

---

## ❓ Still Not Working?

If you run the commands and paste the output back to me, I can:
- ✅ See exactly what's installed vs. what's missing
- ✅ See any error messages in the logs
- ✅ Check if hardware (BME280, microphone) is detected
- ✅ Identify the root cause
- ✅ Give you the exact commands to fix it
- ✅ Update the git repo with permanent fixes

---

## 🚀 TL;DR - Just Run This:

```bash
cd /workspace
bash fix_dependencies.sh
./start_pulse.sh
```

Then check your dashboard at http://localhost:8080

**If still broken, run diagnostics and send me the output:**
```bash
cd /workspace
bash pi_diagnostic_commands.sh
```
