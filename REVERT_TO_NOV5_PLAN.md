# 🔄 REVERT TO NOV 5TH WORKING VERSION - EXECUTION PLAN

**Goal:** Get back to EXACT Nov 5th working code, verify on RPi, THEN switch API

---

## 📊 CURRENT STATUS

**Current Branch:** `cursor/debug-critical-song-detection-on-rpi-c103`  
**Current Commit:** `24f4d4a` (has my recent changes)  
**Nov 5th Commit:** `c2a2f0f` (working version)  

**Current Code:** 371 lines (includes bug fixes + enhancements)  
**Nov 5th Code:** 296 lines (original working version)  

**Difference:** 75 lines added (my bug fix + stats tracking)

---

## 🎯 WHAT WILL CHANGE

### Files to Revert:
1. **`services/sensors/simple_song_detector.py`**
   - Remove my bug fix (attempt_time parameter)
   - Remove 24/7 tracking (stats, counters)
   - Remove backoff logic
   - Back to simple 296-line version

### What Stays:
- Everything else (no other changes needed)
- Same detection interval (will set to 90s later)
- Same architecture

---

## 📋 EXECUTION STEPS

### STEP 1: Revert to Nov 5th (LOCAL)
**Commands I'll run (WITH YOUR PERMISSION):**
```bash
cd /workspace
git checkout c2a2f0f -- services/sensors/simple_song_detector.py
git add services/sensors/simple_song_detector.py
git commit -m "revert: Back to Nov 5th working song detector for RapidAPI testing"
```

**Result:** `simple_song_detector.py` now matches Nov 5th exactly

---

### STEP 2: Push to GitHub
**Commands I'll run:**
```bash
git push origin cursor/debug-critical-song-detection-on-rpi-c103
```

**Result:** Code available on GitHub for RPi to pull

---

### STEP 3: You Verify on RPi
**Commands YOU run on your Raspberry Pi:**
```bash
# Navigate to pulse directory
cd /opt/pulse

# Pull the changes
git fetch origin
git checkout cursor/debug-critical-song-detection-on-rpi-c103
git pull origin cursor/debug-critical-song-detection-on-rpi-c103

# Verify the file changed
ls -lh services/sensors/simple_song_detector.py
# Should show recent timestamp

# Check line count (should be 296 lines)
wc -l services/sensors/simple_song_detector.py
# Should show: 296

# Verify it's the Nov 5th version
grep "last_attempt_time" services/sensors/simple_song_detector.py
# Should return NOTHING (that was my addition)

# Verify Nov 5th working code
head -20 services/sensors/simple_song_detector.py
# Should show original comments about party_box
```

**Result:** You confirm file reverted to Nov 5th

---

### STEP 4: Restart Service on RPi
**Commands YOU run:**
```bash
# Restart the audio service
sudo systemctl restart pulse-audio

# Check it's running
sudo systemctl status pulse-audio

# Watch logs to confirm it starts
sudo journalctl -u pulse-audio -f
# Press Ctrl+C after seeing "Song detection loop started"
```

**Result:** Nov 5th version running on RPi

---

### STEP 5: You Give Me API Key
**Once verified, you paste API key here:**
```
My RapidAPI key is: XXXXXXXXXXXXX
```

---

### STEP 6: I Modify for RapidAPI
**What I'll change (ONLY THESE):**
1. Replace shazamio import with requests
2. Modify `_recognize_song()` to call RapidAPI
3. Add your API key
4. Set detection_interval default to 90 seconds

**Lines changed:** ~30 lines out of 296 (10% of file)

---

### STEP 7: You Test with 100 Free Requests
**Run test phases as planned**

---

## ✅ VERIFICATION CHECKLIST

### After I Revert (Before RPi):
- [ ] File is 296 lines (not 371)
- [ ] No `last_attempt_time` in code
- [ ] No `attempt_time` parameter
- [ ] No backoff logic
- [ ] No stats tracking
- [ ] Matches commit c2a2f0f exactly

### After You Pull on RPi:
- [ ] `wc -l` shows 296 lines
- [ ] `grep "last_attempt_time"` returns nothing
- [ ] File timestamp is recent (today)
- [ ] Service restarts successfully
- [ ] Logs show "Song detection loop started"

### After I Add RapidAPI:
- [ ] Still ~296 lines (minimal changes)
- [ ] Has `import requests`
- [ ] Has RapidAPI URL and headers
- [ ] Has your API key
- [ ] detection_interval = 90
- [ ] Everything else unchanged

---

## 🚫 WHAT I WILL NOT CHANGE

- Detection loop logic
- Thread management
- File recording
- Event loop approach (fresh loops)
- Temporary file cleanup
- Lock mechanism
- Any other services/files

**ONLY the API call changes from shazamio to RapidAPI.**

---

## 📊 BEFORE vs AFTER (Song Detector)

### Current (371 lines):
- Has my bug fix
- Has 24/7 tracking
- Has backoff logic
- More complex

### Nov 5th (296 lines):
- Simple version
- Proven to work
- No extra features
- Clean

### With RapidAPI (~296 lines):
- Nov 5th base
- Only API call changed
- 90-second interval
- Ready to test

---

## ⚠️ IMPORTANT NOTES

1. **This will remove my bug fix** - That's OK! Nov 5th worked without it.
2. **This will remove stats tracking** - That's OK! We'll add back if needed after testing.
3. **This is temporary** - Once we verify RapidAPI works, we can add features back.
4. **API switch is easy** - Only ~30 lines change, rest stays same.

---

## 🎯 YOUR DECISION

**Do you want me to:**

**YES → Execute STEP 1 & 2** (revert and push)
- I'll revert to Nov 5th
- Push to GitHub
- You pull on RPi and verify
- Then give me API key

**NO → Ask questions first**
- What concerns do you have?
- What do you want to verify?

---

## 💪 WHY THIS WILL WORK

1. **Nov 5th worked** → We know it can detect songs
2. **Only API changes** → Everything else stays proven
3. **RapidAPI is better** → No rate limits (on paid tier)
4. **Easy to test** → 100 free requests to validate

**The API switch is literally just changing WHERE we send the audio file.**

---

**READY? Tell me "YES, REVERT TO NOV 5TH" and I'll execute STEP 1 & 2 immediately.** 🚀
