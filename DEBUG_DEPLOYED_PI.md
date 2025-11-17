# 🔍 Debug Your Deployed Raspberry Pi

## Song Detection Troubleshooting Guide

Your Pi at the venue isn't detecting songs. Let's fix it!

---

## 🚀 Quick Start

**On your deployed Pi, run these commands:**

```bash
# 1. Navigate to pulse directory
cd /opt/pulse

# 2. Pull latest code (includes diagnostic tool)
git pull origin main

# 3. Activate virtual environment
source venv/bin/activate

# 4. Run diagnostic tool
python3 diagnose_song_detection.py
```

---

## 📋 What The Diagnostic Tool Checks

The tool will automatically check:

1. ✅ **Python Dependencies** - sounddevice, shazamio, numpy
2. ✅ **Audio Hardware** - Is microphone detected?
3. ✅ **Audio Recording** - Can it actually record? (5 second test)
4. ✅ **Network** - Internet connection (Shazam needs this!)
5. ✅ **Service Status** - Is pulse-audio service running?
6. ✅ **Service Logs** - Any errors in recent logs?
7. ✅ **Cache Files** - Is song data being written?
8. ✅ **Shazam API** - Can it connect to Shazam?
9. ✅ **Code Version** - Using the new working version?

---

## 🎯 Expected Output

You'll see color-coded results:

```
🎵 PULSE SONG DETECTION DIAGNOSTIC TOOL
════════════════════════════════════════════════════════════════

STEP 1: Checking Python Dependencies
────────────────────────────────────────────────────────────────
[CHECK] sounddevice library... ✓ sounddevice is installed
[CHECK] shazamio library... ✓ shazamio is installed
[CHECK] numpy library... ✓ numpy is installed

STEP 2: Checking Audio Hardware
────────────────────────────────────────────────────────────────
[CHECK] Audio devices... ✓ Audio devices found
   card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]

[CHECK] Test audio recording (5 seconds)...
ℹ Recording 5 seconds of audio...
✓ Audio recording works! (level: 2543)

... and more checks ...

DIAGNOSTIC SUMMARY
════════════════════════════════════════════════════════════════

✗ ISSUES FOUND (2):
  1. No internet - Shazam API requires internet
  2. Audio service is not running

RECOMMENDED FIXES:
────────────────────────────────────────────────────────────────
3. Start the audio service:
   sudo systemctl start pulse-audio
   sudo systemctl status pulse-audio

4. Fix internet connection - Shazam requires internet
   ping 8.8.8.8
```

---

## 🔧 Common Issues & Fixes

### Issue 1: Dependencies Missing

**Symptom:** `✗ shazamio NOT installed`

**Fix:**
```bash
cd /opt/pulse
source venv/bin/activate
pip install sounddevice shazamio numpy
sudo systemctl restart pulse-audio
```

---

### Issue 2: No Microphone Detected

**Symptom:** `✗ No audio devices found`

**Check:**
```bash
# List audio devices
arecord -l

# Should show something like:
# card 1: Device [USB Audio Device]
```

**Fix:**
- Plug in USB microphone
- Check USB connection
- Try different USB port
- Check `lsusb` to see if device is detected

---

### Issue 3: Audio Service Not Running

**Symptom:** `✗ pulse-audio service is NOT running`

**Fix:**
```bash
# Start service
sudo systemctl start pulse-audio

# Check status
sudo systemctl status pulse-audio

# View logs
sudo journalctl -u pulse-audio -f
```

---

### Issue 4: No Internet Connection

**Symptom:** `✗ No internet connection`

**Fix:**
```bash
# Test connectivity
ping 8.8.8.8

# Check WiFi
nmcli device status

# Reconnect WiFi if needed
sudo nmcli device wifi connect "YOUR_SSID" password "YOUR_PASSWORD"
```

**Important:** Shazam API requires internet! Song detection won't work offline.

---

### Issue 5: Audio Recording but Very Quiet

**Symptom:** `⚠ Audio recording works but very quiet (level: 45)`

**Fix:**
```bash
# Increase microphone gain
alsamixer
# Press F4 to select capture device
# Use arrow keys to increase capture volume
# Press Esc when done

# Save settings
sudo alsactl store
```

---

### Issue 6: Cache Files Not Being Written

**Symptom:** `✗ Song cache file does not exist`

**Fix:**
```bash
# Create data directory
sudo mkdir -p /opt/pulse/data
sudo chown pi:pi /opt/pulse/data

# Restart service
sudo systemctl restart pulse-audio

# Wait 60 seconds, then check
cat /opt/pulse/data/song_cache.json
```

---

## 📊 Manual Testing

After running diagnostics, you can manually test components:

### Test Microphone Recording
```bash
# Record 5 seconds
arecord -d 5 -f cd test.wav

# Play it back
aplay test.wav

# Should hear what was recorded
```

### Test Shazam Connection
```bash
cd /opt/pulse
source venv/bin/activate
python3 << 'EOF'
import asyncio
from shazamio import Shazam

async def test():
    shazam = Shazam()
    print("✓ Shazam API accessible")

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(test())
loop.close()
EOF
```

### Check Service Logs Live
```bash
# Watch logs in real-time
sudo journalctl -u pulse-audio -f

# Look for:
# - "Song detection enabled"
# - "Song detected: ..."
# - Any error messages
```

### Check Cache Files
```bash
# Song cache
cat /opt/pulse/data/song_cache.json

# Should show:
# {
#   "title": "Song Name",
#   "artist": "Artist Name",
#   "timestamp": 1699564821.5
# }

# Check age
ls -lh /opt/pulse/data/song_cache.json
# Should be recently modified if working
```

---

## 🎵 Testing Song Detection End-to-End

Once diagnostics pass, test the full flow:

1. **Play music** loudly near the Pi
2. **Wait 60 seconds** (detection runs every 60s)
3. **Check cache:**
   ```bash
   cat /opt/pulse/data/song_cache.json
   ```
4. **Check logs:**
   ```bash
   sudo journalctl -u pulse-audio | grep -i "song"
   ```

---

## 📝 Quick Command Reference

```bash
# Run diagnostic
python3 diagnose_song_detection.py

# Check service status
sudo systemctl status pulse-audio

# View live logs
sudo journalctl -u pulse-audio -f

# Restart service
sudo systemctl restart pulse-audio

# Check microphone
arecord -l

# Test recording
arecord -d 5 test.wav && aplay test.wav

# Check internet
ping 8.8.8.8

# View cache
cat /opt/pulse/data/song_cache.json

# Check if service is writing logs
sudo journalctl -u pulse-audio --since "5 minutes ago" | grep -i song
```

---

## 🆘 Still Not Working?

If diagnostics show everything is OK but songs still aren't detected:

1. **Check if music is loud enough:**
   - Detection needs clear audio
   - Background noise can interfere
   - Volume should be moderate to loud

2. **Verify detection interval:**
   - Song detection runs every 60 seconds
   - Wait at least 60 seconds after starting music

3. **Check Shazam can recognize the song:**
   - Not all songs are in Shazam database
   - Very obscure music might not be recognized
   - Try a popular song for testing

4. **Check service is actually running detection:**
   ```bash
   # Should see repeated "Starting song recognition" messages
   sudo journalctl -u pulse-audio --since "5 minutes ago" | grep -i "song\|shazam"
   ```

---

## 📞 Get More Help

After running diagnostics, copy the output and you'll have clear information about:
- What's working ✓
- What's broken ✗  
- What needs attention ⚠
- How to fix each issue

Share the diagnostic output if you need more help!

---

**Run the diagnostic now:**
```bash
cd /opt/pulse && python3 diagnose_song_detection.py
```
