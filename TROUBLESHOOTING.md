# Pulse 1.0 - Troubleshooting Guide

## 🚨 Quick Fix: White Screen After Installation

**Problem:** After running the quick setup and rebooting, you see only a white screen with a cursor.

**Quick Solution:**
1. Press `Ctrl+Alt+F2` to get to terminal
2. Login as `pi`
3. Run: `pkill chromium`
4. Run: `export DISPLAY=:0 && /opt/pulse/dashboard/kiosk/start.sh`
5. The wizard should now open at `http://localhost:9090`

**Or simply:** Press `ESC`, then manually navigate Chromium to `http://localhost:9090`

See detailed recovery steps below ⬇️

---

## Installation and First Boot Issues

### Issue: White Screen After Installation Reboot

**Symptoms:**
- Installation completes successfully and system reboots
- After reboot, you see a white screen with only a cursor visible
- The browser appears to be running but shows nothing
- Setup wizard is not accessible

**Root Cause:**
The kiosk mode browser was trying to open the dashboard (`localhost:8080`) before the setup wizard was completed. Only the setup wizard (`localhost:9090`) is running on first boot, causing the browser to load a blank page.

**Solution:**

This issue has been **FIXED** in the latest version. The fixes include:

1. **Smart Kiosk Detection**: The kiosk start script now checks if the wizard has been completed and opens the correct URL:
   - First boot: Opens `http://localhost:9090` (Setup Wizard)
   - After setup: Opens `http://localhost:8080` (Dashboard)

2. **Wait/Retry Logic**: The script now waits up to 60 seconds for the service to be ready before opening the browser.

3. **Proper Service Coordination**: Services are properly configured:
   - `pulse-firstboot.service` runs ONLY when wizard is NOT complete
   - `pulse-hub.service` and `pulse-dashboard.service` run ONLY when wizard IS complete

**Manual Recovery Steps:**

If you're currently stuck with a white screen after installation:

**Method 1: Kill and Restart the Browser (Fastest)**

1. **Switch to terminal:**
   - Press `Ctrl+Alt+F2` on your keyboard
   - Login with username: `pi` (default password: `raspberry` unless you changed it)

2. **Kill the frozen browser:**
   ```bash
   pkill chromium
   ```

3. **Restart the kiosk with the fixed script:**
   ```bash
   export DISPLAY=:0
   /opt/pulse/dashboard/kiosk/start.sh
   ```

   The wizard should now open automatically at `http://localhost:9090`

4. **Switch back to GUI:**
   - Press `Ctrl+Alt+F1` or `Ctrl+Alt+F7`

**Method 2: Manually Open the Wizard**

1. **Exit fullscreen mode:**
   - Press `ESC` key (if the white screen is in fullscreen)
   
2. **Open Chromium manually:**
   - Open Chromium browser (if not already open)
   - Type in address bar: `http://localhost:9090`
   - The setup wizard should load

3. **Complete the wizard:**
   - Fill in venue information
   - Follow wizard steps
   - Click "Complete Setup"
   - System will reboot and open dashboard correctly

**Method 3: Check Service Status**

1. **Check if wizard is running:**
   ```bash
   sudo systemctl status pulse-firstboot.service
   ```

2. **Check the logs:**
   ```bash
   sudo journalctl -u pulse-firstboot.service -n 50
   ```

3. **If wizard service is not running, start it:**
   ```bash
   sudo systemctl start pulse-firstboot.service
   ```

4. **Wait 10 seconds, then open browser to:**
   ```
   http://localhost:9090
   ```

**Method 4: Complete Reset (Last Resort)**

If nothing else works, reset and start over:

```bash
# Remove wizard completion marker (if it exists)
sudo rm -f /opt/pulse/config/.wizard_complete

# Stop all pulse services
sudo systemctl stop pulse-*

# Reboot
sudo reboot
```

After reboot, the wizard should open automatically at `localhost:9090`.

---

## Common Issues

### Dashboard Won't Load

**Check service status:**
```bash
sudo systemctl status pulse-dashboard
sudo systemctl status pulse-hub
```

**Restart services:**
```bash
sudo systemctl restart pulse-dashboard
sudo systemctl restart pulse-hub
```

**Check logs:**
```bash
tail -f /var/log/pulse/dashboard.log
tail -f /var/log/pulse/hub.log
```

### Sensors Not Detected

**Check hardware detection results:**
```bash
cat /var/log/pulse/hardware_report.txt
```

**Manually test hardware:**
```bash
cd /opt/pulse
source venv/bin/activate
python3 -c "from services.sensors.health_monitor import *; monitor = HealthMonitor(); print(monitor.test_all_modules())"
```

**Check I2C devices (for BME280, light sensor):**
```bash
sudo i2cdetect -y 1
```

**Check camera:**
```bash
vcgencmd get_camera
libcamera-hello --list-cameras
```

### HVAC/Lighting/Music Not Working

**Verify credentials:**
```bash
cat /opt/pulse/.env
```

**Check service logs:**
```bash
tail -f /var/log/pulse/hub.log | grep -i "hvac\|lighting\|music"
```

**Test connection manually:**
```bash
cd /opt/pulse
source venv/bin/activate
python3 -c "from services.controls.lighting_hue import *; controller = HueLightingController(); print(controller.get_status())"
```

### Kiosk Mode Not Starting

**Check autostart configuration:**
```bash
cat /home/pi/.config/lxsession/LXDE-pi/autostart
```

**Manually test kiosk script:**
```bash
/opt/pulse/dashboard/kiosk/start.sh
```

**Check for display errors:**
```bash
export DISPLAY=:0
xset q
```

---

## Service Management

### Check All Pulse Services

```bash
sudo systemctl status pulse-*
```

### Restart All Services

```bash
sudo systemctl restart pulse-hub pulse-dashboard pulse-firstboot
```

### View Service Logs

```bash
# Hub service
journalctl -u pulse-hub.service -f

# Dashboard service
journalctl -u pulse-dashboard.service -f

# First boot wizard
journalctl -u pulse-firstboot.service -f
```

### Disable/Enable Services

```bash
# Disable a service
sudo systemctl disable pulse-dashboard

# Enable a service
sudo systemctl enable pulse-dashboard

# Stop a service
sudo systemctl stop pulse-dashboard

# Start a service
sudo systemctl start pulse-dashboard
```

---

## Configuration Files

### Main Configuration
`/opt/pulse/config/config.yaml`

### Environment Variables
`/opt/pulse/.env`

### Service Files
`/etc/systemd/system/pulse-*.service`

### Logs
`/var/log/pulse/`

---

## Factory Reset

To completely reset Pulse and run the setup wizard again:

```bash
# Remove wizard completion marker
sudo rm /opt/pulse/config/.wizard_complete

# Stop all services
sudo systemctl stop pulse-*

# Clear configuration (optional)
sudo rm /opt/pulse/config/config.yaml

# Clear logs (optional)
sudo rm -rf /var/log/pulse/*

# Reboot
sudo reboot
```

The setup wizard will automatically appear after reboot.

---

## Network Issues

### Can't Access Dashboard Remotely

The dashboard is bound to `localhost` by default for security. To access from another device:

1. **Find your Pi's IP address:**
   ```bash
   hostname -I
   ```

2. **Update the dashboard server to bind to all interfaces:**
   Edit `/opt/pulse/dashboard/api/server.py` and change:
   ```python
   app.run(host='0.0.0.0', port=8080)
   ```

3. **Restart the dashboard:**
   ```bash
   sudo systemctl restart pulse-dashboard
   ```

4. **Access from another device:**
   Open browser to `http://<PI_IP_ADDRESS>:8080`

---

## Performance Issues

### High CPU Usage

**Check which service is consuming CPU:**
```bash
top
# Press Shift+P to sort by CPU
```

**Common causes:**
- Camera processing (people detection)
- Music detection (audio analysis)

**Reduce camera processing:**
Edit `/opt/pulse/config/config.yaml`:
```yaml
modules:
  camera: false  # Disable camera temporarily
```

### Low Memory

**Check memory usage:**
```bash
free -h
```

**Increase swap space:**
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change CONF_SWAPSIZE=100 to CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## Getting Help

If you're still having issues:

1. **Check the logs** - Most issues have useful error messages in the logs
2. **Search GitHub Issues** - Someone may have had the same problem
3. **Create a new issue** - Include:
   - Raspberry Pi model and OS version
   - Pulse version
   - Steps to reproduce
   - Relevant log output
   - Hardware connected

**Gather diagnostic information:**
```bash
# Create diagnostic report
cat > /tmp/pulse-diagnostic.txt << EOF
=== Pulse Diagnostic Report ===
Date: $(date)

=== System Info ===
$(uname -a)
$(cat /proc/cpuinfo | grep Model)

=== Pulse Services ===
$(sudo systemctl status pulse-* --no-pager)

=== Hardware Detection ===
$(cat /var/log/pulse/hardware_report.txt 2>/dev/null || echo "Not found")

=== Recent Logs ===
$(tail -n 50 /var/log/pulse/*.log 2>/dev/null || echo "No logs found")

=== Config ===
$(cat /opt/pulse/config/config.yaml 2>/dev/null || echo "Not found")
EOF

cat /tmp/pulse-diagnostic.txt
```

---

## Advanced Debugging

### Enable Debug Logging

Edit service files to enable debug output:
```bash
sudo nano /etc/systemd/system/pulse-hub.service
```

Add to `[Service]` section:
```ini
Environment="LOG_LEVEL=DEBUG"
```

Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart pulse-hub
```

### Test Individual Components

```bash
cd /opt/pulse
source venv/bin/activate

# Test camera
python3 services/sensors/camera_people.py

# Test microphone
python3 services/sensors/mic_song_detect.py

# Test BME280
python3 services/sensors/bme280_reader.py

# Test health monitor
python3 services/sensors/health_monitor.py
```

### Database Access

```bash
# Open database
sqlite3 /opt/pulse/data/pulse.db

# Useful queries
SELECT * FROM occupancy ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM automation_log WHERE timestamp > datetime('now', '-1 hour');
SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 20;

# Exit
.quit
```

---

**Need more help?** Visit the [GitHub Discussions](https://github.com/Opentab1/thefinale2/discussions) or create an [issue](https://github.com/Opentab1/thefinale2/issues).
