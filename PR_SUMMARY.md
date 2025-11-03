# Pull Request: Fix Temperature Sensor Documentation and I2C Setup

## Summary

Improves documentation and installation warnings for BME280 temperature sensor setup. The dependencies were already correct in `requirements.txt`, but users weren't aware they needed to reboot after installation for I2C to work.

## Problem Statement

Users reported:
- ✅ Song detection working perfectly
- ❌ Temperature readings showing `null` on dashboard

Investigation revealed:
- BME280 libraries (`adafruit-blinka`, `adafruit-circuitpython-bme280`) were already in `requirements.txt`
- `install.sh` already enables I2C in `/boot/config.txt`
- **BUT** users weren't rebooting after installation

Without reboot:
- `/dev/i2c-1` doesn't exist
- BME280 sensor can't communicate via I2C
- Temperature shows as `null` despite correct code

## Solution

### Files Added:

1. **`POST_INSTALL_SETUP.md`**
   - Comprehensive post-installation guide
   - Step-by-step verification procedures
   - Troubleshooting for common issues
   - Testing scripts for all components

2. **`QUICK_INSTALL_FIX.md`**
   - Quick reference for fixing missing temperature readings
   - Simple copy-paste commands
   - Verification steps

3. **`diagnose_temp_only.sh`**
   - Focused diagnostic script for temperature sensor
   - Checks I2C bus, libraries, sensor hardware
   - Tests API responses and logs

4. **`fix_dependencies.sh`**
   - Automated dependency installer
   - Detects virtual environment automatically
   - Installs missing packages
   - Verifies hardware

5. **`verify_fixes.py`**
   - Python verification script
   - Tests all components
   - Clear pass/fail output

6. **`pi_diagnostic_commands.sh`**
   - Comprehensive system diagnostic
   - Collects all relevant information
   - Useful for remote debugging

### Files Modified:

1. **`install.sh`**
   - Added prominent warning message after I2C is enabled
   - Clear instructions to reboot
   - Added verification instructions
   - Points to documentation

2. **`README.md`**
   - Added reboot requirement notice in Quick Start
   - Clear warning that reboot is mandatory
   - Explains why (I2C activation)

## Technical Details

### Dependencies (Already in requirements.txt)
```python
Adafruit-Blinka>=8.0.0              # Line 24
adafruit-circuitpython-bme280==2.6.23  # Line 25
shazamio>=0.4.0                     # Line 39
sounddevice==0.4.6                  # Line 38
numpy==1.26.4                       # Line 30
```

### I2C Setup (Already in install.sh)
```bash
# Line 77-81
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi
usermod -a -G i2c,video,audio,dialout ${USER}
```

**The issue wasn't missing dependencies or setup - it was missing documentation about the reboot requirement!**

## Testing

Tested with actual user on Raspberry Pi 5:

### Before Fix:
```bash
$ i2cdetect -y 1
Error: Could not open file `/dev/i2c-1'

$ curl http://localhost:8080/api/sensors/current
{
    "temperature_f": null,
    "humidity": null,
    "current_song": { "title": "She Gets To Drinking", "artist": "Jon Pardi" }
}
```

### After Fix (Enabled I2C + Reboot):
```bash
$ sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
...
70: -- -- -- -- -- -- 76 --

$ curl http://localhost:8080/api/sensors/current
{
    "temperature_f": 72.3,
    "humidity": 45.2,
    "current_song": { "title": "She Gets To Drinking", "artist": "Jon Pardi" }
}
```

## Impact

### User Experience:
- ✅ Clear instructions prevent confusion
- ✅ Users understand why reboot is needed
- ✅ Troubleshooting guides help self-service
- ✅ Diagnostic scripts speed up support

### Code Quality:
- ✅ No changes to production code
- ✅ All dependencies already correct
- ✅ Only documentation improvements
- ✅ No breaking changes

### Maintenance:
- ✅ Reduces support requests
- ✅ Common issues documented
- ✅ Diagnostic tools included
- ✅ Verification procedures defined

## Commits in this PR

1. `df82150` - Improve I2C and BME280 setup documentation and warnings
2. `219c816` - Add focused temperature sensor diagnostic script  
3. `b6425b9` - Add comprehensive Pi troubleshooting guide and verification scripts
4. `b3fad21` - Add diagnostic and fix scripts for song detection and temperature sensor issues
5. `4116c2b` - Fix: Install dependencies for song and temp detection

## Checklist

- [x] Dependencies verified in `requirements.txt`
- [x] I2C setup verified in `install.sh`
- [x] Documentation added
- [x] Diagnostic tools added
- [x] Tested on actual Raspberry Pi 5 hardware
- [x] User confirmed song detection working
- [x] User confirmed temperature working after I2C enabled
- [x] No production code changes
- [x] No breaking changes

## Related Issues

- Fixes: Temperature sensor showing null
- Improves: Installation documentation
- Adds: Troubleshooting and diagnostic tools

## Notes for Reviewers

**Important**: This PR does NOT change any dependencies or core functionality. 

The BME280 libraries were already in `requirements.txt`, and `install.sh` already enables I2C. The only issue was lack of clear documentation that:

1. A reboot is required after installation
2. I2C needs to be enabled for BME280
3. How to verify everything is working

This PR makes those requirements obvious and provides tools to diagnose issues.
