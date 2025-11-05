#!/bin/bash
# Deploy audio fix to Pi - run this on your Pi

set -e

echo "=========================================="
echo "DEPLOYING AUDIO FIX TO PI"
echo "=========================================="
echo ""

INSTALL_DIR="/opt/pulse"
WORKSPACE_DIR="/workspace"

# Check if we're on the Pi (has /opt/pulse)
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ ERROR: /opt/pulse not found!"
    echo "   This script must be run on your Raspberry Pi"
    echo "   Install directory: $INSTALL_DIR"
    exit 1
fi

echo "1. Checking service status..."
systemctl status pulse-hub --no-pager -l | head -15 || echo "Service check failed"
echo ""

echo "2. Checking if service is running..."
if systemctl is-active --quiet pulse-hub; then
    echo "   ✅ pulse-hub is running"
    SERVICE_RUNNING=true
else
    echo "   ❌ pulse-hub is NOT running"
    SERVICE_RUNNING=false
fi
echo ""

echo "3. Checking for log files..."
if [ -d "/var/log/pulse" ]; then
    echo "   ✅ Log directory exists"
    ls -lh /var/log/pulse/ 2>/dev/null || echo "   (empty)"
else
    echo "   ⚠️  Log directory doesn't exist - creating..."
    mkdir -p /var/log/pulse
    chown pi:pi /var/log/pulse
fi
echo ""

echo "4. Checking Python process..."
ps aux | grep -E "pulse-hub|main.py" | grep -v grep || echo "   No pulse-hub process found"
echo ""

echo "5. Checking if hub service file exists..."
if [ -f "$INSTALL_DIR/services/hub/main.py" ]; then
    echo "   ✅ Hub service found at $INSTALL_DIR/services/hub/main.py"
    
    # Backup existing file
    echo "   📦 Backing up existing file..."
    cp -f "$INSTALL_DIR/services/hub/main.py" "$INSTALL_DIR/services/hub/main.py.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Check if we have the fixed version in workspace
    if [ -f "$WORKSPACE_DIR/services/hub/main.py" ]; then
        echo "   📥 Copying fixed version from workspace..."
        cp -f "$WORKSPACE_DIR/services/hub/main.py" "$INSTALL_DIR/services/hub/main.py"
        echo "   ✅ Fixed version deployed"
    else
        echo "   ⚠️  Fixed version not in workspace - will apply patch..."
        
        # Apply the watchdog fix directly
        if ! grep -q "CRITICAL FIX: Audio monitoring watchdog" "$INSTALL_DIR/services/hub/main.py"; then
            echo "   🔧 Applying watchdog fix..."
            
            # Create a Python script to apply the fix
            python3 << 'PYTHON_FIX'
import re
import sys

file_path = "/opt/pulse/services/hub/main.py"

try:
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if fix already applied
    if "CRITICAL FIX: Audio monitoring watchdog" in content:
        print("   ✅ Watchdog fix already present")
        sys.exit(0)
    
    # Add watchdog tracking after stop_event
    if "# State" in content and "self.stop_event = Event()" in content:
        # Find the stop_event line and add watchdog after it
        pattern = r'(self\.stop_event = Event\(\))'
        replacement = r'\1\n        \n        # CRITICAL FIX: Audio monitoring watchdog tracking\n        self._audio_last_db_reading = None\n        self._audio_last_db_timestamp = None\n        self._audio_stall_count = 0\n        self._audio_max_stall_before_restart = 3  # Restart after 3 consecutive stalls'
        content = re.sub(pattern, replacement, content)
        print("   ✅ Added watchdog tracking variables")
    else:
        print("   ⚠️  Could not find insertion point for watchdog variables")
    
    # Add watchdog logic in _collect_sensor_data
    if 'if self.audio_monitor:' in content and 'data["noise_db"]' in content:
        # Find the audio_monitor section
        audio_section_pattern = r'(if self\.audio_monitor:.*?logger\.debug\("No song detected via audio monitor)'
        
        # Check if watchdog already exists
        if "CRITICAL FIX: Watchdog to detect and restart stalled audio monitoring" not in content:
            # Insert watchdog code before the song detection log
            watchdog_code = '''
            # CRITICAL FIX: Watchdog to detect and restart stalled audio monitoring
            now = time.time()
            
            # Check if dB readings are updating (they should update every 2 seconds)
            if current_db is not None and current_db != self._audio_last_db_reading:
                # dB reading changed - audio monitoring is working
                self._audio_last_db_reading = current_db
                self._audio_last_db_timestamp = now
                self._audio_stall_count = 0
            elif current_db is not None:
                # dB reading is the same - check if it's stale
                if self._audio_last_db_timestamp is None:
                    self._audio_last_db_timestamp = now
                elif (now - self._audio_last_db_timestamp) > 60.0:  # No change for 60 seconds = stalled
                    self._audio_stall_count += 1
                    logger.warning(
                        f"⚠️ Audio monitoring appears stalled (dB unchanged for {now - self._audio_last_db_timestamp:.1f}s, "
                        f"stall_count={self._audio_stall_count})"
                    )
                    
                    # Force restart if repeatedly stalled
                    if self._audio_stall_count >= self._audio_max_stall_before_restart:
                        logger.error(
                            f"🚨 CRITICAL: Audio monitoring stalled {self._audio_stall_count} times - "
                            "FORCING COMPLETE RESTART!"
                        )
                        try:
                            self.audio_monitor.stop_monitoring()
                            time.sleep(2)
                            self.audio_monitor.start_monitoring()
                            logger.info("✅ Audio monitoring restarted successfully")
                            self._audio_stall_count = 0
                            self._audio_last_db_timestamp = time.time()
                        except Exception as restart_error:
                            logger.error(f"❌ Failed to restart audio monitoring: {restart_error}", exc_info=True)
            elif self._audio_last_db_timestamp is None:
                # First reading - initialize
                self._audio_last_db_reading = current_db
                self._audio_last_db_timestamp = now
            else:
                # No dB reading at all - check if it's been too long
                age = now - self._audio_last_db_timestamp if self._audio_last_db_timestamp else 0
                if age > 120.0:  # No dB reading for 2 minutes = critical failure
                    self._audio_stall_count += 1
                    logger.error(
                        f"🚨 CRITICAL: No dB readings for {age:.1f}s (stall_count={self._audio_stall_count})"
                    )
                    
                    if self._audio_stall_count >= self._audio_max_stall_before_restart:
                        logger.error("🚨 FORCING COMPLETE AUDIO MONITOR RESTART!")
                        try:
                            self.audio_monitor.stop_monitoring()
                            time.sleep(2)
                            self.audio_monitor.start_monitoring()
                            logger.info("✅ Audio monitoring restarted after complete failure")
                            self._audio_stall_count = 0
                            self._audio_last_db_timestamp = time.time()
                        except Exception as restart_error:
                            logger.error(f"❌ Failed to restart audio monitoring: {restart_error}", exc_info=True)
            
            '''
            
            # Insert before the song detection logging
            pattern = r'(            # Log song detection status for debugging)'
            replacement = watchdog_code + r'\1'
            content = re.sub(pattern, replacement, content, count=1)
            
            # Also need to change current_db assignment
            pattern = r'(            data\["noise_db"\] = self\._sanitize_environment_value\(self\.audio_monitor\.get_current_db\(\)\))'
            replacement = r'            current_db = self._sanitize_environment_value(self.audio_monitor.get_current_db())\n            data["noise_db"] = current_db'
            content = re.sub(pattern, replacement, content, count=1)
            
            print("   ✅ Added watchdog logic")
        else:
            print("   ✅ Watchdog logic already present")
    else:
        print("   ⚠️  Could not find audio_monitor section to patch")
    
    # Write the fixed file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("   ✅ Fix applied successfully")
    
except Exception as e:
    print(f"   ❌ Error applying fix: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_FIX

        else
            echo "   ✅ Watchdog fix already present"
        fi
    fi
else
    echo "   ❌ Hub service file not found!"
    exit 1
fi
echo ""

echo "6. Restarting service..."
systemctl restart pulse-hub
sleep 5

echo ""
echo "7. Checking service status after restart..."
if systemctl is-active --quiet pulse-hub; then
    echo "   ✅ Service is running"
else
    echo "   ❌ Service failed to start!"
    echo ""
    echo "   Checking logs:"
    journalctl -u pulse-hub -n 30 --no-pager || echo "   No logs found"
    exit 1
fi

echo ""
echo "8. Waiting 15 seconds for initialization..."
sleep 15

echo ""
echo "9. Checking for audio activity..."
AUDIO_COUNT=$(journalctl -u pulse-hub --since "15 seconds ago" --no-pager | grep -c "Audio:" || echo "0")
if [ "$AUDIO_COUNT" -gt 0 ]; then
    echo "   ✅ Audio monitoring is working! ($AUDIO_COUNT log entries)"
else
    echo "   ⚠️  No audio logs yet"
    echo ""
    echo "   Recent logs:"
    journalctl -u pulse-hub --since "15 seconds ago" --no-pager | tail -20
fi

echo ""
echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "To monitor:"
echo "  sudo journalctl -u pulse-hub -f | grep -E '(Audio|Song|CRITICAL|stalled)'"
echo ""
echo "To view all logs:"
echo "  sudo journalctl -u pulse-hub --no-pager | tail -100"
echo ""
