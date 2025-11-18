# 🚀 PULSE DIAGNOSTICS - QUICK START GUIDE

## ⚡ TL;DR - Start Here

You need to run ONE script on your Raspberry Pi to diagnose all issues.

### Step 1: Copy Script to Pi (Run on your local machine)
```bash
scp /workspace/REMOTE_DIAGNOSTICS_SCRIPT.sh pi@10.40.43.12:~/
```

### Step 2: Run Diagnostic (Run on the Pi via SSH)
```bash
ssh pi@10.40.43.12
chmod +x ~/REMOTE_DIAGNOSTICS_SCRIPT.sh
sudo ~/REMOTE_DIAGNOSTICS_SCRIPT.sh
```

### Step 3: Share Results
```bash
# On the Pi, find the report file:
ls -lh /tmp/pulse_diagnostic_*.txt

# View it:
cat /tmp/pulse_diagnostic_*.txt

# Copy it back to your machine:
scp pi@10.40.43.12:/tmp/pulse_diagnostic_*.txt ./
```

### Step 4: Share with Engineer
Send the diagnostic output file content (paste in chat or attach file)

---

## 📋 What the Script Does (READ-ONLY, 100% Safe)

The script will:
- ✅ Check hardware (BME280, microphone, camera, USB devices)
- ✅ Check system health (temperature, power, throttling)
- ✅ Check Pulse installation and services
- ✅ Collect recent logs
- ✅ Test sensors (BME280 read, mic record, camera capture)
- ✅ Review cache files

**It makes ZERO changes** - purely diagnostic!

**Runtime:** 2-3 minutes

---

## 🔍 What to Look For While It Runs

### ✅ Good Signs:
- `✅ BME280 sensor detected at address 0x76 or 0x77`
- `✅ No throttling detected - power and temperature OK`
- `✅ Audio recording device(s) found`
- `✅ Internet connectivity OK`

### ❌ Bad Signs (Call Out If You See These):
- `❌ THROTTLING DETECTED` → Power supply issue! Use official RPi5 27W adapter
- `❌ BME280 sensor NOT detected` → Check I2C wiring
- `❌ NO audio recording devices found` → USB mic not detected
- `❌ NO internet connectivity` → Shazam API will fail

---

## 💬 Questions to Answer (While Waiting for Script)

### Critical Questions:
1. **Is there a camera connected?** (Yes/No, and what type?)
2. **When was the unit last updated?** (Date if known, or "unknown")
3. **What are the exact symptoms?**
   - Song detection: Never works? Works sometimes? Specific error messages?
   - People counting: Never works? Inaccurate counts? Camera crashes?
   - BME280: Works fine? Occasional failures?

### Helpful Context:
4. **Failure frequency:** Every 10 minutes? Random? Only during peak hours?
5. **Recent changes:** Any updates to software, hardware, network, power supply?
6. **Power supply:** Official Raspberry Pi 27W adapter or third-party?

---

## 🎯 What Happens Next

### After I Receive Diagnostic:
1. **Analyze output** (1 hour)
2. **Confirm root cause** (30 min)
3. **Propose fixes** with exact commands (30 min)
4. **Get your approval** before making ANY changes
5. **Deploy fixes** (2-3 hours)
6. **Monitor for 48 hours** to ensure stability

### Most Likely Fixes (Based on Code Analysis):
- ✅ Update to latest code (Nov 2024 audio fix may not be deployed)
- ✅ Download missing model files for people counting
- ✅ Fix service configuration
- ✅ Add network retry logic

**All fixes are minimal, surgical, and have rollback procedures.**

---

## 📞 Communication

### Send Me:
1. ✅ Full diagnostic output (paste or attach)
2. ✅ Answers to critical questions above
3. ✅ Any photos of hardware setup (if possible)
4. ✅ Recent error messages you've seen (if any)

### I'll Send You:
1. ✅ Root cause analysis
2. ✅ Fix plan with exact commands
3. ✅ Deployment checklist
4. ✅ Rollback procedure

---

## ⚠️ Important Notes

### DO NOT (Until I Review Diagnostic):
- ❌ Don't restart services
- ❌ Don't update code
- ❌ Don't change configuration
- ❌ Don't reboot the Pi

### Why?
The diagnostic captures the current state. Changes will hide problems and make diagnosis harder.

### If System is Critical:
If the unit is completely non-functional and venue needs it NOW, you can:
```bash
# Emergency restart (won't hurt, but will clear diagnostic info)
sudo systemctl restart pulse.service
```

But then re-run the diagnostic after a few hours of operation to capture the failure pattern.

---

## 📊 Expected Timeline

```
TODAY:
├─ You: Run diagnostic (3 min)
├─ You: Share output + answers (5 min)
├─ Me: Analyze (1 hour)
├─ Me: Propose fixes (30 min)
└─ You: Approve fixes

TODAY/TOMORROW:
├─ Me: Deploy fixes (2-3 hours)
└─ Start 48-hour monitoring

2-3 DAYS:
└─ Final report + go-live approval
```

**Total time to working system:** 4-24 hours (depending on root cause complexity)

---

## 🆘 Troubleshooting the Diagnostic Script

### If Script Fails:

**"Permission denied":**
```bash
chmod +x ~/REMOTE_DIAGNOSTICS_SCRIPT.sh
```

**"sudo: command not found":**
Run without sudo:
```bash
./REMOTE_DIAGNOSTICS_SCRIPT.sh
```
(Some commands will fail, but most will work)

**"No such file or directory":**
```bash
# Check script was copied:
ls -lh ~/REMOTE_DIAGNOSTICS_SCRIPT.sh

# If not there, re-copy from your machine
```

**Script hangs on camera test:**
Press Ctrl+C after 30 seconds and continue. The script will recover.

---

## ✅ Checklist Before Running

- [ ] Pi is powered on and accessible via SSH
- [ ] You have sudo access (user: pi, or root)
- [ ] Venue/network is allowing SSH connections
- [ ] You have 5 minutes to monitor the script output
- [ ] You can copy the result file back to your machine

---

**Ready? Run the diagnostic now! ⚡**

If you have ANY issues running the script, just manually run these 3 commands and share output:

```bash
# Command 1: System health
vcgencmd get_throttled && vcgencmd measure_temp && free -h

# Command 2: Hardware detection  
lsusb && i2cdetect -y 1 && arecord -l

# Command 3: Service status
sudo systemctl status pulse-audio pulse-camera pulse-environmental pulse-hub-main
```

That's enough for initial diagnosis!
