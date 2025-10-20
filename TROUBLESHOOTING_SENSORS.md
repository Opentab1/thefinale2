# 🔧 Sensor Troubleshooting Guide

## Problem: Light Level and Decibel Readings Show 0

If your light level and decibel sensors are reading 0, it means the Python dependencies are not installed on your system.

## ✅ Quick Fix (Run on your Raspberry Pi)

### Step 1: Pull Latest Code
```bash
cd /opt/pulse
git pull origin main
```

### Step 2: Run Diagnostics
```bash
python3 diagnose_sensors_detailed.py
```

This will show you exactly which dependencies are missing.

### Step 3: Install Missing Dependencies

**For Light Sensor:**
```bash
sudo pip3 install opencv-python numpy
```

**For Audio/Decibel Sensor:**
```bash
sudo pip3 install numpy pyaudio sounddevice
```

**Install ALL at once:**
```bash
sudo pip3 install numpy opencv-python pyaudio sounddevice
```

### Step 4: Restart the System
```bash
sudo systemctl restart pulse-hub
sudo systemctl restart pulse-dashboard
```

Or if running manually:
```bash
cd /opt/pulse
./START_HERE.sh
```

## 📊 What You Should See

After installing dependencies, when you run the diagnostic:

```
📦 CHECKING DEPENDENCIES:
--------------------------------------------------------------------------------
  ✓ NumPy
  ✓ OpenCV (opencv-python)
  ✓ PyAudio
  ✓ sounddevice
  ...

📷 TESTING CAMERA:
--------------------------------------------------------------------------------
  ✓ Camera accessible
  - Resolution: 1920x1080

🎤 TESTING AUDIO DEVICES:
--------------------------------------------------------------------------------
  ✓ PyAudio found 2 audio devices
    - Input Device 1: USB Audio Device (2 channels)

🔬 TESTING SENSORS:
--------------------------------------------------------------------------------

  💡 Light Sensor:
    ✓ Initialized successfully
    - Current reading: 342.5 lux

  🔊 Audio Monitor:
    ✓ Initialized successfully
    - Device index: 1
    - Current dB: 45.2
```

## 🐛 Still Having Issues?

### Check if running as correct user
```bash
whoami  # Should show 'pi' or your username
```

### Check Python version
```bash
python3 --version  # Should be 3.9 or higher
```

### Verify camera access
```bash
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.read()[0] else 'Camera FAIL'); cap.release()"
```

### Verify audio device
```bash
arecord -l  # Lists audio recording devices
```

### Check system logs
```bash
sudo journalctl -u pulse-hub -n 50 --no-pager
```

Look for error messages like:
- `✗ Light sensor dependencies missing`
- `✗ Audio monitor dependencies missing`

## 💡 Common Issues

### Issue: "No module named 'cv2'"
**Solution:** `sudo pip3 install opencv-python`

### Issue: "No module named 'pyaudio'"
**Solution:** `sudo pip3 install pyaudio`

### Issue: "No module named 'numpy'"
**Solution:** `sudo pip3 install numpy`

### Issue: Camera works but light level still 0
**Possible causes:**
1. Camera is busy (being used by people counter)
2. Snapshot file doesn't exist yet
3. Check logs: `sudo journalctl -u pulse-hub -f`

**Solution:** The sensor will automatically fall back to direct camera access after 5 check cycles (default 30s * 5 = 2.5 minutes).

### Issue: Audio device exists but dB still 0
**Possible causes:**
1. Audio device is muted or volume is 0
2. Wrong device selected

**Solution:** 
```bash
# Check volume
alsamixer

# Test audio recording
arecord -d 5 test.wav
aplay test.wav
```

## 🎯 Next Steps

Once dependencies are installed:

1. Sensors will automatically start working
2. Light readings will show in lux (0-1000)
3. Audio readings will show in dB (0-120)
4. Dashboard will display real-time data

**Live readings appear in the terminal:**
```
💡 Light level: 456.3 lux (Moderate) [snapshot]
🔊 Audio: 52.1 dB (Peak: 78.5 dB)
```

## 📞 Still Need Help?

If sensors still don't work after following this guide:

1. Run the diagnostic and save output: `python3 diagnose_sensors_detailed.py > diagnostic.txt`
2. Check system logs: `sudo journalctl -u pulse-hub -n 100 > logs.txt`
3. Share both files for support

The fix is now in GitHub - just pull the latest code, install dependencies, and restart!
