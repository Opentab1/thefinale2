# White Screen Issue - Fix Summary

## Issue Reported
User ran the quick setup command on a freshly flashed Raspberry Pi. After installation completed and the system rebooted, they saw only a white screen with a cursor visible.

## Root Cause
The kiosk startup script (`dashboard/kiosk/start.sh`) was hardcoded to always open `http://localhost:8080` (the dashboard), but on first boot after installation:
- Only the setup wizard service (`pulse-firstboot.service`) is running on port 9090
- The dashboard service (`pulse-dashboard.service`) does NOT start until the wizard is completed
- This caused the browser to open a non-existent page, resulting in a white screen

## Solution Implemented

### 1. Fixed Kiosk Startup Script (`dashboard/kiosk/start.sh`)
**Changes:**
- ✅ Added smart detection to check if `/opt/pulse/config/.wizard_complete` exists
- ✅ Opens `http://localhost:9090` (wizard) on first boot
- ✅ Opens `http://localhost:8080` (dashboard) after wizard completion
- ✅ Added wait/retry logic (up to 60 seconds) for service to be ready before opening browser
- ✅ Added helpful console logging for debugging

**Code changes:**
```bash
# Before: Always opened localhost:8080
--app=http://localhost:8080

# After: Smart detection
WIZARD_COMPLETE="/opt/pulse/config/.wizard_complete"
PULSE_URL="http://localhost:8080"

if [ ! -f "$WIZARD_COMPLETE" ]; then
  PULSE_URL="http://localhost:9090"  # First boot - wizard
else
  PULSE_URL="http://localhost:8080"  # Setup complete - dashboard
fi
```

### 2. Updated Documentation

**TROUBLESHOOTING.md:**
- ✅ Added "🚨 Quick Fix: White Screen After Installation" section at the top
- ✅ Renamed existing section to clearly describe white screen symptoms
- ✅ Added 4 recovery methods with clear step-by-step instructions:
  - Method 1: Kill and restart browser (fastest)
  - Method 2: Manually open wizard
  - Method 3: Check service status
  - Method 4: Complete reset

**QUICKSTART.md:**
- ✅ Added white screen troubleshooting in Step 3
- ✅ Provided quick commands for immediate recovery

**README.md:**
- ✅ Added note about white screen issue in Setup Wizard section
- ✅ Referenced WHITE_SCREEN_FIX.md for details
- ✅ Added white screen to Common Issues section with link to fix guide

**WHITE_SCREEN_FIX.md (NEW):**
- ✅ Created comprehensive recovery guide
- ✅ Explains why the issue happens
- ✅ Provides 4 recovery options from easiest to most thorough
- ✅ Includes what to expect after wizard loads
- ✅ Documents the technical fix

## Files Modified

1. `/workspace/dashboard/kiosk/start.sh` - Core fix with smart URL detection
2. `/workspace/TROUBLESHOOTING.md` - Enhanced with white screen recovery steps
3. `/workspace/QUICKSTART.md` - Added white screen quick fix
4. `/workspace/README.md` - Referenced white screen issue and fix
5. `/workspace/WHITE_SCREEN_FIX.md` - New comprehensive recovery guide (this file)
6. `/workspace/FIX_SUMMARY_WHITE_SCREEN.md` - This summary document

## User Recovery Instructions (Immediate)

**For the user currently experiencing this issue:**

### Quick Fix (30 seconds):
1. Press `ESC` on your keyboard
2. Change browser URL to: `http://localhost:9090`
3. Press Enter
4. Complete the setup wizard

### Alternative Fix (1 minute):
1. Press `Ctrl+Alt+F2`
2. Login as `pi`
3. Run:
   ```bash
   pkill chromium
   export DISPLAY=:0
   /opt/pulse/dashboard/kiosk/start.sh
   ```
4. Press `Ctrl+Alt+F1` to return to GUI
5. Complete the setup wizard

## Prevention
This fix is now in the codebase. When users run the installation in the future:
- The correct URL (wizard) will automatically open on first boot
- The system waits for services to be ready before opening browser
- No more white screens! ✅

## Testing Recommendations
1. Test fresh installation on Raspberry Pi
2. Verify wizard opens automatically at port 9090 after first reboot
3. Complete wizard and verify dashboard opens at port 8080 after second reboot
4. Test all 4 recovery methods to ensure they work

## Status
✅ **FIXED** - All changes implemented and documented
