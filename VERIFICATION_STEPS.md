# Verification Steps for Reboot Fix

## Pre-Testing Setup

Ensure you have:
- [ ] Fresh Raspberry Pi 5 with Raspberry Pi OS (64-bit) installed
- [ ] Internet connection active
- [ ] Display, keyboard, mouse connected

## Test 1: Fresh Installation (Happy Path)

### Steps:
1. Open terminal on Raspberry Pi
2. Run installation command:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
   ```
3. Wait for installation to complete (~15-20 minutes)
4. System should automatically reboot

### After First Reboot:
- [ ] Wait 60 seconds for services to start
- [ ] Browser window should automatically open
- [ ] Browser should display wizard at `http://localhost:9090`
- [ ] Wizard should show Pulse logo and welcome message

### Complete Wizard:
- [ ] Enter venue name (e.g., "Test Venue")
- [ ] Select timezone
- [ ] Click "Next" through hardware detection
- [ ] Configure or skip smart integrations
- [ ] Set automation limits or use defaults
- [ ] Click "Complete Setup"
- [ ] Wizard shows "Setup Complete!" message
- [ ] System automatically reboots

### After Second Reboot:
- [ ] Wait 60 seconds for services to start
- [ ] Browser window should automatically open
- [ ] Browser should display dashboard at `http://localhost:8080`
- [ ] Dashboard shows venue name and live data

**✅ Test 1 passes if all steps complete successfully**

---

## Test 2: Manual Recovery (Wizard Doesn't Appear)

### Simulate Issue:
After first reboot, press `Ctrl+C` to stop the browser before it opens.

### Recovery Steps:
1. Check wizard service status:
   ```bash
   sudo systemctl status pulse-firstboot.service
   ```
   - [ ] Service should be "active (running)"

2. Check if wizard is accessible:
   ```bash
   curl http://localhost:9090
   ```
   - [ ] Should return HTML content (not connection refused)

3. Manually open browser:
   - [ ] Open Chromium
   - [ ] Navigate to `http://localhost:9090`
   - [ ] Wizard should appear

4. Complete wizard as in Test 1

**✅ Test 2 passes if manual recovery works**

---

## Test 3: Factory Reset

### After completing Test 1:
1. Remove wizard completion marker:
   ```bash
   sudo rm /opt/pulse/config/.wizard_complete
   ```
2. Reboot:
   ```bash
   sudo reboot
   ```

### After Reboot:
- [ ] Wait 60 seconds
- [ ] Browser should open wizard again (not dashboard)
- [ ] Wizard should work as expected

**✅ Test 3 passes if wizard reappears**

---

## Test 4: Service Conditions

### Before Wizard Completion:
```bash
sudo systemctl status pulse-firstboot.service
sudo systemctl status pulse-hub.service
sudo systemctl status pulse-dashboard.service
```

**Expected:**
- [ ] `pulse-firstboot.service` - **active (running)**
- [ ] `pulse-hub.service` - **inactive** (condition not met)
- [ ] `pulse-dashboard.service` - **inactive** (condition not met)

### After Wizard Completion:
```bash
sudo systemctl status pulse-firstboot.service
sudo systemctl status pulse-hub.service
sudo systemctl status pulse-dashboard.service
```

**Expected:**
- [ ] `pulse-firstboot.service` - **inactive** (condition not met)
- [ ] `pulse-hub.service` - **active (running)**
- [ ] `pulse-dashboard.service` - **active (running)**

**✅ Test 4 passes if service states match expectations**

---

## Test 5: Marker File Creation

### Check marker file:
```bash
# Before wizard completion
ls -la /opt/pulse/config/.wizard_complete
# Should show: No such file or directory

# After wizard completion
ls -la /opt/pulse/config/.wizard_complete
# Should show: File exists with recent timestamp

# Verify config was updated
cat /opt/pulse/config/config.yaml | grep -A 2 "wizard:"
# Should show: completed: true
```

**Expected:**
- [ ] Marker file does not exist before wizard completion
- [ ] Marker file exists after wizard completion
- [ ] Config file shows `wizard.completed: true`

**✅ Test 5 passes if marker file creation works correctly**

---

## Test 6: Kiosk URL Detection

### Test the kiosk script logic:
```bash
# Simulate first boot
sudo rm /opt/pulse/config/.wizard_complete

# Run kiosk script in background
/opt/pulse/dashboard/kiosk/start.sh &

# Check what URL it's trying to open
ps aux | grep chromium
# Should show: --app=http://localhost:9090

# Kill chromium
pkill chromium

# Create marker file
sudo touch /opt/pulse/config/.wizard_complete

# Run kiosk script again
/opt/pulse/dashboard/kiosk/start.sh &

# Check what URL it's trying to open
ps aux | grep chromium
# Should show: --app=http://localhost:8080
```

**Expected:**
- [ ] Without marker file: Opens `localhost:9090` (wizard)
- [ ] With marker file: Opens `localhost:8080` (dashboard)

**✅ Test 6 passes if URL detection works correctly**

---

## Test 7: Chromium Compatibility

### Test both Chromium commands:
```bash
# Check which chromium is available
which chromium
which chromium-browser

# Test the one that exists
chromium --version || chromium-browser --version
```

**Expected:**
- [ ] At least one chromium command works
- [ ] Kiosk script successfully launches browser

**✅ Test 7 passes if browser launches regardless of command name**

---

## Test 8: Hardware Detection

### Check hardware detection results:
```bash
cat /var/log/pulse/hardware_report.txt
```

**Expected:**
- [ ] File exists and contains JSON hardware detection results
- [ ] Wizard hardware check page displays these results

**✅ Test 8 passes if hardware detection integrates with wizard**

---

## Test 9: Log Files

### Verify logging:
```bash
ls -la /var/log/pulse/
```

**Expected logs:**
- [ ] `firstboot.log` - Wizard server logs
- [ ] `firstboot.err` - Wizard error logs
- [ ] `hub.log` - Hub service logs (after wizard complete)
- [ ] `dashboard.log` - Dashboard logs (after wizard complete)
- [ ] `hardware_report.txt` - Hardware detection results

**✅ Test 9 passes if all log files exist and contain relevant data**

---

## Test 10: Troubleshooting Guide

### Verify documentation:
- [ ] `TROUBLESHOOTING.md` exists
- [ ] Contains "Wizard doesn't appear" section
- [ ] Manual recovery steps are clear
- [ ] Commands are correct and work

**✅ Test 10 passes if documentation is helpful and accurate**

---

## Overall Test Results

**Date:** _______________
**Tester:** _______________
**Raspberry Pi Model:** _______________
**OS Version:** _______________

**Tests Passed:** _____ / 10

**Issues Found:**
```
(Describe any issues discovered during testing)
```

**Notes:**
```
(Additional observations or comments)
```

---

## Sign-Off

If all tests pass:
- [ ] Code is ready to merge to main branch
- [ ] Users will have smooth installation experience
- [ ] Wizard will appear after reboot as expected
- [ ] Recovery steps work if issues occur

**Approved by:** _______________
**Date:** _______________
