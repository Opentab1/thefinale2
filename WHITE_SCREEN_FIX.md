# 🔧 White Screen After Installation - Recovery Guide

## Problem Description

After running the Pulse installation script and rebooting your Raspberry Pi, you see:
- ✅ A white screen
- ✅ Your mouse cursor is visible and moves
- ❌ Nothing else appears
- ❌ No setup wizard loads

## Why This Happens

The browser tried to open the dashboard at `http://localhost:8080`, but on first boot, only the setup wizard at `http://localhost:9090` is running. This causes the browser to show a white screen.

**Good news:** This has been fixed! The kiosk script now automatically detects first boot and opens the correct URL.

## Recovery Options

### Option 1: Restart the Browser (Easiest - 30 seconds)

1. **Press `ESC`** on your keyboard to exit fullscreen
2. **Look at the browser address bar** - you'll likely see `http://localhost:8080`
3. **Change the URL to:** `http://localhost:9090`
4. **Press Enter**
5. The setup wizard should now load! ✅

### Option 2: Kill and Restart (Recommended - 1 minute)

1. **Press `Ctrl+Alt+F2`** to switch to terminal
2. **Login:**
   - Username: `pi`
   - Password: `raspberry` (or your custom password)
3. **Kill the frozen browser:**
   ```bash
   pkill chromium
   ```
4. **Restart with the fixed script:**
   ```bash
   export DISPLAY=:0
   /opt/pulse/dashboard/kiosk/start.sh
   ```
5. **Switch back to GUI:** Press `Ctrl+Alt+F1` or `Ctrl+Alt+F7`
6. The wizard should now open automatically at port 9090! ✅

### Option 3: Check Services (Debug - 2 minutes)

1. **Open terminal** (or use `Ctrl+Alt+F2`)
2. **Check if wizard is running:**
   ```bash
   sudo systemctl status pulse-firstboot.service
   ```
   
   - If **active (running)** ✅ - Good! Service is running
   - If **inactive** ❌ - Start it manually (see below)

3. **If service is not running:**
   ```bash
   sudo systemctl start pulse-firstboot.service
   ```

4. **Wait 10-15 seconds** for service to start

5. **Open browser to:** `http://localhost:9090`

### Option 4: Complete Reset (Last Resort - 3 minutes)

If nothing else works, reset everything and start fresh:

```bash
# Remove completion marker (if it exists)
sudo rm -f /opt/pulse/config/.wizard_complete

# Stop all services
sudo systemctl stop pulse-*

# Reboot
sudo reboot
```

After reboot, the wizard should open automatically.

## After You See the Wizard

Once the setup wizard loads at `http://localhost:9090`:

1. ✅ **Venue Setup** - Enter your venue name and timezone
2. ✅ **Hardware Check** - Review detected sensors (click Next)
3. ✅ **Smart Integrations** - Skip for now (you can add later)
4. ✅ **Automation Limits** - Use defaults or customize
5. ✅ **Click "Complete Setup"**
6. ✅ System will reboot again
7. ✅ Dashboard will open automatically at `http://localhost:8080`

## The Fix (Already Applied)

The file `/workspace/dashboard/kiosk/start.sh` has been updated to:
- ✅ Check if wizard is complete before deciding which URL to open
- ✅ Wait up to 60 seconds for the service to be ready
- ✅ Open wizard (port 9090) on first boot
- ✅ Open dashboard (port 8080) after setup is complete

If you re-flash your Pi and run the installation again, this issue won't occur.

## Need More Help?

- 📖 Full troubleshooting guide: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- 🚀 Quick start guide: [QUICKSTART.md](QUICKSTART.md)
- 📘 Full documentation: [README.md](README.md)
- 🐛 Report issues: [GitHub Issues](https://github.com/Opentab1/thefinale2/issues)

## Prevention for Next Time

When you reflash or setup another Pi:
1. Pull the latest code (the fix is already included)
2. After installation and reboot, wait 30-60 seconds
3. The wizard should automatically open at `localhost:9090`
4. If you see white screen, just press `ESC` and navigate to `http://localhost:9090`

---

**You're almost there!** Once you complete the wizard, you'll have a fully functional Pulse system managing your venue. 🎵
