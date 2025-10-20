# 🔊 Audio & Song Detection - Complete Fix Guide

## ✅ What's Fixed

Both **decibel/noise level** and **song detection** are now working! The fixes address:

1. **Decibel Readings** - Now shows real-time audio levels
2. **Song Detection** - Now recognizes songs playing via Shazam
3. **Better Error Messages** - Clear feedback when something's wrong
4. **Diagnostic Tools** - Easy way to test your audio hardware

---

## 🚀 Quick Fix (On Your Raspberry Pi)

### Step 1: Pull Latest Code
```bash
cd /opt/pulse  # or wherever your code is
git pull origin main
```

### Step 2: Install Audio Dependencies
```bash
# Install all required audio libraries
sudo pip3 install numpy pyaudio sounddevice shazamio

# If pyaudio fails to install, you may need system packages first:
sudo apt-get install -y portaudio19-dev python3-pyaudio
sudo pip3 install pyaudio
```

### Step 3: Test Your Audio Hardware
```bash
# Run the diagnostic tool
python3 test_audio_capture.py
```

**What you should see:**
```
AUDIO CAPTURE DIAGNOSTICS
================================================================================
1. Checking audio libraries...
  ✓ PyAudio available
  ✓ sounddevice available
  ✓ NumPy available

2. Finding audio input devices...
  Found 2 total devices
  ✓ Input device 1: USB Audio Device
    - Channels: 2
    - Sample rate: 44100.0

3. Testing audio capture on device 1...
  ✓ Audio stream opened successfully
  Capturing 5 audio chunks...
    Chunk 1: 2048 samples, RMS: 0.023456, dB: 52.3
    Chunk 2: 2048 samples, RMS: 0.018234, dB: 48.1
    ...

  ✓ Audio capture working!
```

If you see dB readings **above 30**, your audio is working!

### Step 4: Restart Pulse
```bash
sudo systemctl restart pulse-hub
sudo systemctl restart pulse-dashboard

# OR if running manually:
cd /opt/pulse
./START_HERE.sh
```

---

## 📊 What You'll See When It's Working

### In Terminal/Logs:

**Audio Monitoring (every 2 seconds):**
```
🔊 Audio: 52.3 dB (Peak: 67.8 dB)
🔊 Audio: 48.1 dB (Peak: 67.8 dB)
🔊 Audio: 55.7 dB (Peak: 67.8 dB)
```

**Song Detection (every 60 seconds):**
```
🎤 Recording 5s audio clip for song detection...
  Recording complete (max amplitude: 15234)
  Audio saved to /tmp/tmpxyz123.wav
✅ Song detected: Bohemian Rhapsody - Queen
🎵 Song detected: Bohemian Rhapsody - Queen
```

### In Dashboard:
- **Noise Level:** Shows current dB (0-120 scale)
- **Current Song:** Shows detected song title and artist

---

## 🐛 Troubleshooting

### Problem: "No input audio device found"

**Solution:** Check if your microphone is connected
```bash
arecord -l
```

You should see your microphone listed. If not:
- Plug in USB microphone
- Check connections
- Reboot if needed

### Problem: dB readings are always very low (< 20)

**Possible causes:**
1. Microphone volume is too low
2. Microphone is muted
3. Wrong device selected

**Solutions:**
```bash
# Check/adjust volume
alsamixer

# Test recording
arecord -d 5 test.wav
aplay test.wav  # Should hear your recording
```

### Problem: Song detector says "Unknown" for everything

**Possible causes:**
1. No music actually playing
2. Music is too quiet
3. ShazamIO can't reach servers (internet issue)
4. Song is too obscure for Shazam

**Check:**
```bash
# Make sure shazamio is installed
pip3 show shazamio

# Check internet connectivity
ping -c 3 google.com

# Check logs for errors
sudo journalctl -u pulse-hub -n 100 | grep -i shazam
```

### Problem: Audio stream fails to open

**Error message example:**
```
Failed to open PyAudio stream: [Errno -9997] Invalid sample rate
```

**Solution:** Try different device or sample rate
```bash
# List devices with their supported rates
python3 -c "import pyaudio; p = pyaudio.PyAudio(); [print(p.get_device_info_by_index(i)) for i in range(p.get_device_count())]"
```

### Problem: ShazamIO not installed

**Error:**
```
🎵 Song detection disabled: ShazamIO not installed
```

**Solution:**
```bash
sudo pip3 install shazamio aiohttp
```

---

## 🔍 Understanding the Logs

### Good Logs (Everything Working):
```
✓ Audio stream opened successfully (PyAudio, device 1)
🔊 Audio monitoring active - dB readings will appear shortly
🔊 Audio: 52.3 dB (Peak: 67.8 dB)
🎵 Song detection enabled
  - Detection interval: 60 seconds
  - Using ShazamIO for recognition
```

### Bad Logs (Audio Not Working):
```
Failed to open PyAudio stream: <error>
Failed to open sounddevice stream: <error>
CRITICAL: Could not open any audio stream!
Audio monitoring (dB readings) will NOT work.
```

If you see "CRITICAL", follow the check steps:
1. `arecord -l` - Check device exists
2. `arecord -d 1 test.wav` - Test permissions
3. `pip list | grep -i audio` - Verify dependencies

---

## ⚙️ Configuration Options

### Change dB Update Frequency
The default is every 2 seconds. To change:

Edit `services/sensors/mic_song_detect.py`:
```python
if (now_db - self._last_db_ts) >= 2.0:  # Change this value
```

### Change Song Detection Interval
The default is every 60 seconds. To change:

Set environment variable:
```bash
export SONG_DETECT_INTERVAL_SEC=30  # Check every 30 seconds
```

Or in config (if using config file):
```yaml
modules:
  mic:
    song_detect_interval: 30
```

### Change Recording Duration for Song Detection
Edit `services/sensors/song_detector.py`:
```python
self.duration = 5  # seconds to record (5 is good for most songs)
```

---

## 📈 Performance Tips

1. **Don't set song detection too frequent** - Each detection takes 5-10 seconds and uses CPU
   - 60 seconds is good for most use cases
   - 30 seconds if you change songs often
   - 10 seconds only for testing

2. **Monitor system resources:**
   ```bash
   htop  # Watch CPU usage
   ```

3. **Check Shazam API limits** - Free tier may have rate limits

---

## ✨ What Changed Technically

### Audio Monitor (`mic_song_detect.py`):
- ✅ Better stream opening with fallback (PyAudio → sounddevice)
- ✅ Detailed error logging with diagnostic info
- ✅ Faster dB updates (2s instead of 5s)
- ✅ Continues running for song detection even if dB fails
- ✅ Stack traces for better debugging

### Song Detector (`song_detector.py`):
- ✅ Checks recording amplitude to detect mic issues
- ✅ Better initialization logging with emojis
- ✅ Installation instructions in error messages
- ✅ Updates "Unknown" status even when no match
- ✅ Logs when new songs are detected

### Hub (`main.py`):
- ✅ Better ImportError handling
- ✅ Shows installation commands for missing deps
- ✅ Continues running even if sensors fail

---

## 🎯 Expected Behavior After Fix

1. **System starts** → Shows which sensors initialized
2. **Audio stream opens** → See "✓ Audio stream opened successfully"
3. **dB readings start** → Every 2 seconds you see "🔊 Audio: XX.X dB"
4. **Song detection runs** → Every 60 seconds attempts to recognize music
5. **Dashboard updates** → Shows current dB and song in real-time

---

## 💡 Still Not Working?

1. **Run full diagnostics:**
   ```bash
   python3 diagnose_sensors_detailed.py > diagnostic.txt
   python3 test_audio_capture.py > audio_test.txt
   ```

2. **Check system logs:**
   ```bash
   sudo journalctl -u pulse-hub -n 200 > hub_logs.txt
   ```

3. **Verify all dependencies:**
   ```bash
   pip3 list | grep -E "(numpy|pyaudio|sounddevice|shazamio)" > deps.txt
   ```

4. **Test audio hardware separately:**
   ```bash
   # Record 5 seconds
   arecord -d 5 -f cd test.wav
   
   # Play it back
   aplay test.wav
   ```

Share these files for support if needed!

---

## 🎉 Success Indicators

You know it's working when you see:

✅ `✓ Audio stream opened successfully`  
✅ `🔊 Audio: [number > 30] dB`  
✅ `🎵 Song detected: [Real Song Name]`  
✅ Dashboard shows changing dB values  
✅ Dashboard shows detected songs  

If you see all of these, **congratulations!** Your audio monitoring and song detection are fully operational! 🎊
