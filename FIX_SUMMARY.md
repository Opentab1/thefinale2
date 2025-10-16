# Fix: Reboot After Quick Start - Wizard Not Appearing

## Problem

After running the installation command and rebooting, the setup wizard was not appearing. Users were left with a blank screen or no browser window, making it impossible to complete the initial setup.

## Root Cause

The kiosk startup script (`dashboard/kiosk/start.sh`) was always trying to open the dashboard at `http://localhost:8080`, even on first boot when the wizard should be displayed at `http://localhost:9090`.

The wizard completion detection logic was missing, causing:
1. Browser to try loading the dashboard before wizard was complete
2. Dashboard service wouldn't start (requires wizard completion marker)
3. User stuck at blank screen with no indication of what to do

## Changes Made

### 1. Fixed Kiosk Start Script (`dashboard/kiosk/start.sh`)
- Added detection of wizard completion marker file (`/opt/pulse/config/.wizard_complete`)
- Opens wizard URL (`http://localhost:9090`) on first boot
- Opens dashboard URL (`http://localhost:8080`) after wizard completion
- Added wait loop to ensure service is ready before opening browser
- Added logging to help debug startup issues

### 2. Fixed Wizard Server (`bootstrap/wizard/server.py`)
- Added proper marker file creation when wizard is completed
- Created default config file if none exists on first boot
- Fixed `load_config()` to handle missing config gracefully
- Improved hardware detection to use actual detection results
- Added better logging for debugging

### 3. Created Troubleshooting Guide (`TROUBLESHOOTING.md`)
- Comprehensive guide for common issues
- Specific section for "wizard doesn't appear" issue
- Manual recovery steps for users stuck after reboot
- Service management commands
- Diagnostic tools and procedures
- Factory reset instructions

### 4. Updated Quick Start Guide (`QUICKSTART.md`)
- Clarified what to expect after reboot (60 second wait)
- Added troubleshooting tips for first boot issues
- Referenced detailed troubleshooting guide
- Added manual recovery steps inline

## Testing Recommendations

When testing this fix on an actual Raspberry Pi:

1. **Fresh Installation Test:**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Opentab1/thefinale2/main/install.sh | sudo bash
   ```
   - Verify installation completes
   - Verify automatic reboot occurs
   - **Expected:** After reboot, wait 60s, wizard opens at localhost:9090
   - Complete wizard
   - Verify second reboot
   - **Expected:** After second reboot, dashboard opens at localhost:8080

2. **Recovery Test:**
   ```bash
   sudo rm /opt/pulse/config/.wizard_complete
   sudo reboot
   ```
   - **Expected:** Wizard appears again after reboot

3. **Service Verification:**
   ```bash
   # Before wizard completion
   sudo systemctl status pulse-firstboot.service  # Should be active
   sudo systemctl status pulse-dashboard.service  # Should be inactive (condition not met)
   
   # After wizard completion
   sudo systemctl status pulse-firstboot.service  # Should be inactive (condition not met)
   sudo systemctl status pulse-dashboard.service  # Should be active
   ```

## Files Modified

- `dashboard/kiosk/start.sh` - Fixed URL detection logic
- `bootstrap/wizard/server.py` - Fixed marker file creation and config handling
- `QUICKSTART.md` - Updated with better expectations and troubleshooting
- `TROUBLESHOOTING.md` - **NEW** - Comprehensive troubleshooting guide
- `FIX_SUMMARY.md` - **NEW** - This document

## Backward Compatibility

These changes are fully backward compatible:
- Existing installations with wizard complete will continue to work
- The marker file check is the same as before
- Only the kiosk script behavior changed (improved)
- Wizard server changes only affect first-boot scenario

## User Impact

**Before Fix:**
- User runs install command
- System reboots
- Blank screen or browser error
- No indication of what to do next
- Frustrated user

**After Fix:**
- User runs install command
- System reboots
- Wizard automatically opens in browser
- User completes setup intuitively
- Dashboard launches as expected
- Happy user 🎉

## Related Issues

This fix resolves the issue described in branch name: `cursor/troubleshoot-reboot-after-quick-start-f582`
