# 🎯 QUICK FIX - Audio & Song Detection

## Run These 4 Commands On Your Pi:

```bash
# 1. Get latest fixes
cd /opt/pulse && git pull origin main

# 2. Install dependencies
sudo pip3 install numpy pyaudio sounddevice shazamio

# 3. Test audio (should see dB readings)
python3 test_audio_capture.py

# 4. Restart Pulse
sudo systemctl restart pulse-hub pulse-dashboard
```

## ✅ You'll Know It Works When You See:

**Terminal:**
```
✓ Audio stream opened successfully
🔊 Audio: 52.3 dB (Peak: 67.8 dB)
🎵 Song detected: [Song Name] - [Artist]
```

**Dashboard:**
- Noise Level: Shows actual dB (not 0)
- Current Song: Shows real songs (not "Unknown")

## 🐛 If Still Broken:

```bash
# Check mic exists
arecord -l

# Test mic works
arecord -d 3 test.wav && aplay test.wav

# Check dependencies
pip3 list | grep -E "(numpy|pyaudio|sounddevice|shazamio)"

# View errors
sudo journalctl -u pulse-hub -n 50
```

## 📖 Full Details:
See `AUDIO_FIXES_README.md` for complete troubleshooting guide.
