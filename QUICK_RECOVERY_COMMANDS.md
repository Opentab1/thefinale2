# 🚀 QUICK RECOVERY COMMANDS

## Step 1: Check Your RPI 5 Status (Do This First!)

**SSH into your RPI 5 and run:**

```bash
cd /opt/pulse

# What commit are you on?
git log --oneline -1

# What branch?
git branch

# Do you have the new files?
ls -la run_audio_service.py run_camera_service.py run_hub_service.py

# Are the separate services running?
systemctl status pulse-audio.service pulse-camera.service pulse-hub-main.service
```

**Copy the output and report back!**

---

## Step 2: Recovery Options (Choose One After Step 1)

### ⭐ Option A: Your RPI Already Has It (Most Likely)

If Step 1 shows the files exist and services are running:

```bash
# Just verify everything works
systemctl status pulse.service

# Check logs
sudo journalctl -u pulse-audio -n 50
sudo journalctl -u pulse-camera -n 50
sudo journalctl -u pulse-hub-main -n 50

# You're good! No recovery needed!
```

### ⭐ Option B: Pull the Working Branch

If your RPI isn't on the right branch:

```bash
cd /opt/pulse

# Save any local changes
git stash

# Fetch and checkout working branch
git fetch origin
git checkout cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d
git pull origin cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d

# Install separate services
bash install_separate_services.sh

# Verify
systemctl status pulse.service
```

### Option C: Merge to Main First (Safer)

**In your workspace (not RPI):**

```bash
# Checkout main
git checkout main

# Merge working branch
git merge origin/cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d

# Push to GitHub
git push origin main
```

**Then on your RPI:**

```bash
cd /opt/pulse
git checkout main
git pull origin main
bash install_separate_services.sh
systemctl status pulse.service
```

---

## Step 3: Verify Everything Works

```bash
# Check all services
sudo systemctl status pulse-audio.service
sudo systemctl status pulse-camera.service
sudo systemctl status pulse-hub-main.service

# Watch audio logs (should see dB readings every 10s, songs every 60s)
sudo journalctl -u pulse-audio -f

# Test fault isolation - stop camera
sudo systemctl stop pulse-camera

# Audio should still be running!
sudo systemctl status pulse-audio

# Restart camera
sudo systemctl start pulse-camera
```

---

## 🆘 If Something Goes Wrong

```bash
# Stop all services
sudo systemctl stop pulse.service

# Check what's installed
ls -la /etc/systemd/system/pulse-*.service

# View logs for errors
sudo journalctl -u pulse-audio --no-pager -n 100
sudo journalctl -u pulse-camera --no-pager -n 100
sudo journalctl -u pulse-hub-main --no-pager -n 100

# Restart everything
sudo systemctl daemon-reload
sudo systemctl restart pulse.service
```

---

## 📋 Key Files to Check

These should exist on your working RPI:

```bash
# Service runners
/opt/pulse/run_audio_service.py
/opt/pulse/run_camera_service.py
/opt/pulse/run_hub_service.py

# Simple detectors
/opt/pulse/services/sensors/simple_decibel_detector.py
/opt/pulse/services/sensors/simple_song_detector.py

# Systemd services
/etc/systemd/system/pulse-audio.service
/etc/systemd/system/pulse-camera.service
/etc/systemd/system/pulse-hub-main.service

# Installer
/opt/pulse/install_separate_services.sh
```

---

## 🎯 Working Branch Info

**Branch:** `cursor/debug-and-stabilize-audio-features-on-raspberry-pi-702d`

**Key Commits:**
- `3f525912` - Implement separate services (Nov 5, 21:22:18)
- `2f9be33e` - Remove old watchdog code (Nov 5, 18:29:56)
- `f2b17d1d` - Update hub to use simple detectors (Nov 5, 18:26:09)

**Total Changes:**
- ✅ 10 new files created
- ✅ 2 old files removed (1,569 lines)
- ✅ 3 files modified
- ✅ Net: -1,057 lines (simpler!)

---

## 💡 Quick Status Check

Run this one-liner on your RPI:

```bash
echo "=== PULSE STATUS ===" && \
git log --oneline -1 && \
echo "" && \
systemctl is-active pulse-audio pulse-camera pulse-hub-main && \
echo "" && \
ls -1 run_*.py 2>/dev/null | wc -l && echo "service runners found"
```

Expected output if working:
```
=== PULSE STATUS ===
ad7257f (or similar Nov 5-7 commit)

active
active  
active

3 service runners found
```
