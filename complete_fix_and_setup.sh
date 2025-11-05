#!/bin/bash
# Complete fix - handles missing service and applies audio fix

set -e

echo "=========================================="
echo "COMPLETE FIX: Service Setup + Audio Fix"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

INSTALL_DIR="/opt/pulse"

echo "1. Checking if pulse is installed..."
if [ ! -d "$INSTALL_DIR" ]; then
    echo "   ❌ /opt/pulse not found!"
    echo "   Please install pulse first or check installation directory"
    exit 1
fi
echo "   ✅ Pulse found at $INSTALL_DIR"

echo ""
echo "2. Checking for service files..."
SERVICE_FILE="/etc/systemd/system/pulse-hub.service"
if [ -f "$SERVICE_FILE" ]; then
    echo "   ✅ Service file exists"
else
    echo "   ⚠️  Service file not found - checking for template..."
    
    # Look for service files in the install directory
    if [ -f "$INSTALL_DIR/services/systemd/pulse-hub.service" ]; then
        echo "   📥 Found service template, installing..."
        cp "$INSTALL_DIR/services/systemd/pulse-hub.service" "$SERVICE_FILE"
        systemctl daemon-reload
        systemctl enable pulse-hub
        echo "   ✅ Service installed and enabled"
    else
        echo "   ❌ Service template not found!"
        echo "   Creating basic service file..."
        
        cat > "$SERVICE_FILE" << 'EOFSERVICE'
[Unit]
Description=Pulse Hub - Main Orchestration Service
After=network.target
Requires=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/pulse
Environment="PYTHONPATH=/opt/pulse"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/pulse/.venv/bin/python3 -u /opt/pulse/services/hub/main.py
Restart=always
RestartSec=10
TimeoutStartSec=30

# Logging
StandardOutput=append:/var/log/pulse/hub.log
StandardError=append:/var/log/pulse/hub-error.log

# Resource limits
MemoryLimit=512M

[Install]
WantedBy=multi-user.target
EOFSERVICE
        
        systemctl daemon-reload
        systemctl enable pulse-hub
        echo "   ✅ Service file created and enabled"
    fi
fi

echo ""
echo "3. Ensuring log directory exists..."
mkdir -p /var/log/pulse
chown pi:pi /var/log/pulse
echo "   ✅ Log directory ready"

echo ""
echo "4. Applying audio monitoring watchdog fix..."
python3 << 'ENDPYTHON'
import sys
import os
import re
import shutil
from datetime import datetime

file_path = "/opt/pulse/services/hub/main.py"

if not os.path.exists(file_path):
    print(f"   ❌ ERROR: {file_path} not found!")
    sys.exit(1)

# Backup
backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(file_path, backup_path)
print(f"   ✅ Backed up to: {os.path.basename(backup_path)}")

with open(file_path, 'r') as f:
    content = f.read()

if "CRITICAL FIX: Audio monitoring watchdog" in content:
    print("   ✅ Fix already applied!")
    sys.exit(0)

# Add watchdog variables
if "_audio_last_db_reading" not in content:
    content = content.replace(
        "self.stop_event = Event()",
        """self.stop_event = Event()

        # CRITICAL FIX: Audio monitoring watchdog tracking
        self._audio_last_db_reading = None
        self._audio_last_db_timestamp = None
        self._audio_stall_count = 0
        self._audio_max_stall_before_restart = 3  # Restart after 3 consecutive stalls"""
    )
    print("   ✅ Added watchdog variables")

# Add watchdog logic  
if 'CRITICAL FIX: Watchdog to detect' not in content:
    # Change single line to use current_db variable
    old_pattern = r'(\s+)data\["noise_db"\] = self\._sanitize_environment_value\(self\.audio_monitor\.get_current_db\(\)\)'
    new_replacement = r'\1current_db = self._sanitize_environment_value(self.audio_monitor.get_current_db())\n\1data["noise_db"] = current_db'
    content = re.sub(old_pattern, new_replacement, content)
    
    # Add watchdog before song logging
    watchdog = '''
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
    
    # Insert before song detection logging
    pattern = r'(            # Log song detection status for debugging)'
    replacement = watchdog + r'\1'
    content = re.sub(pattern, replacement, content, count=1)
    print("   ✅ Added watchdog logic")

with open(file_path, 'w') as f:
    f.write(content)

print("   ✅ Fix applied successfully!")
ENDPYTHON

if [ $? -ne 0 ]; then
    echo "   ❌ Fix failed!"
    exit 1
fi

echo ""
echo "5. Starting service..."
systemctl start pulse-hub
sleep 5

echo ""
echo "6. Checking service status..."
if systemctl is-active --quiet pulse-hub; then
    echo "   ✅ Service is running!"
else
    echo "   ❌ Service failed to start"
    echo ""
    echo "   Checking logs:"
    journalctl -u pulse-hub -n 30 --no-pager || echo "   No logs found"
    echo ""
    echo "   Checking file logs:"
    tail -30 /var/log/pulse/hub-error.log 2>/dev/null || echo "   No error log"
    exit 1
fi

echo ""
echo "7. Waiting 15 seconds for initialization..."
sleep 15

echo ""
echo "8. Checking for audio activity..."
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
echo "SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "Monitor with:"
echo "  sudo journalctl -u pulse-hub -f | grep -E '(Audio|Song|CRITICAL|stalled)'"
echo ""
echo "View all logs:"
echo "  sudo journalctl -u pulse-hub --no-pager | tail -100"
echo ""
echo "Check file logs:"
echo "  sudo tail -f /var/log/pulse/hub.log"
echo "  sudo tail -f /var/log/pulse/hub-error.log"
echo ""
