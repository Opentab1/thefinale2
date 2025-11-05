#!/bin/bash
# SIMPLE FIX - Run this on your Pi
# This script patches the hub service directly

set -e

HUB_FILE="/opt/pulse/services/hub/main.py"

echo "=========================================="
echo "APPLYING AUDIO FIX"
echo "=========================================="

# Check if file exists
if [ ! -f "$HUB_FILE" ]; then
    echo "❌ ERROR: $HUB_FILE not found!"
    echo "   Make sure pulse is installed at /opt/pulse"
    exit 1
fi

# Backup
echo "1. Backing up existing file..."
cp "$HUB_FILE" "${HUB_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

# Check if already fixed
if grep -q "CRITICAL FIX: Audio monitoring watchdog" "$HUB_FILE"; then
    echo "   ✅ Fix already applied!"
else
    echo "2. Applying watchdog fix..."
    
    # Apply fix using Python
    python3 << 'PYTHON_PATCH'
import sys
import re

file_path = "/opt/pulse/services/hub/main.py"

try:
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    watchdog_vars_added = False
    watchdog_logic_added = False
    
    while i < len(lines):
        line = lines[i]
        
        # Add watchdog variables after stop_event
        if 'self.stop_event = Event()' in line and not watchdog_vars_added:
            new_lines.append(line)
            new_lines.append('\n')
            new_lines.append('        # CRITICAL FIX: Audio monitoring watchdog tracking\n')
            new_lines.append('        self._audio_last_db_reading = None\n')
            new_lines.append('        self._audio_last_db_timestamp = None\n')
            new_lines.append('        self._audio_stall_count = 0\n')
            new_lines.append('        self._audio_max_stall_before_restart = 3  # Restart after 3 consecutive stalls\n')
            watchdog_vars_added = True
            i += 1
            continue
        
        # Add watchdog logic in audio_monitor section
        if 'if self.audio_monitor:' in line and not watchdog_logic_added:
            new_lines.append(line)
            i += 1
            
            # Find where to insert
            audio_section_start = i
            found_db_line = False
            found_song_log = False
            
            # Read ahead to find the structure
            while i < len(lines):
                if 'data["noise_db"]' in lines[i] and 'get_current_db' in lines[i]:
                    # Replace the single line with current_db assignment
                    new_lines.append('            current_db = self._sanitize_environment_value(self.audio_monitor.get_current_db())\n')
                    new_lines.append('            data["noise_db"] = current_db\n')
                    found_db_line = True
                    i += 1
                    continue
                
                if 'song_data = self.audio_monitor.get_current_song()' in lines[i]:
                    new_lines.append(line)
                    i += 1
                    continue
                
                if 'data["song_detection"]' in lines[i]:
                    new_lines.append(line)
                    i += 1
                    continue
                
                if '# Log song detection status' in lines[i] or 'logger.debug' in lines[i] and 'song' in lines[i].lower():
                    # Insert watchdog logic before this
                    new_lines.append('            \n')
                    new_lines.append('            # CRITICAL FIX: Watchdog to detect and restart stalled audio monitoring\n')
                    new_lines.append('            now = time.time()\n')
                    new_lines.append('            \n')
                    new_lines.append('            # Check if dB readings are updating (they should update every 2 seconds)\n')
                    new_lines.append('            if current_db is not None and current_db != self._audio_last_db_reading:\n')
                    new_lines.append('                # dB reading changed - audio monitoring is working\n')
                    new_lines.append('                self._audio_last_db_reading = current_db\n')
                    new_lines.append('                self._audio_last_db_timestamp = now\n')
                    new_lines.append('                self._audio_stall_count = 0\n')
                    new_lines.append('            elif current_db is not None:\n')
                    new_lines.append('                # dB reading is the same - check if it\'s stale\n')
                    new_lines.append('                if self._audio_last_db_timestamp is None:\n')
                    new_lines.append('                    self._audio_last_db_timestamp = now\n')
                    new_lines.append('                elif (now - self._audio_last_db_timestamp) > 60.0:  # No change for 60 seconds = stalled\n')
                    new_lines.append('                    self._audio_stall_count += 1\n')
                    new_lines.append('                    logger.warning(\n')
                    new_lines.append('                        f"⚠️ Audio monitoring appears stalled (dB unchanged for {now - self._audio_last_db_timestamp:.1f}s, "\n')
                    new_lines.append('                        f"stall_count={self._audio_stall_count})"\n')
                    new_lines.append('                    )\n')
                    new_lines.append('                    \n')
                    new_lines.append('                    # Force restart if repeatedly stalled\n')
                    new_lines.append('                    if self._audio_stall_count >= self._audio_max_stall_before_restart:\n')
                    new_lines.append('                        logger.error(\n')
                    new_lines.append('                            f"🚨 CRITICAL: Audio monitoring stalled {self._audio_stall_count} times - "\n')
                    new_lines.append('                            "FORCING COMPLETE RESTART!"\n')
                    new_lines.append('                        )\n')
                    new_lines.append('                        try:\n')
                    new_lines.append('                            self.audio_monitor.stop_monitoring()\n')
                    new_lines.append('                            time.sleep(2)\n')
                    new_lines.append('                            self.audio_monitor.start_monitoring()\n')
                    new_lines.append('                            logger.info("✅ Audio monitoring restarted successfully")\n')
                    new_lines.append('                            self._audio_stall_count = 0\n')
                    new_lines.append('                            self._audio_last_db_timestamp = time.time()\n')
                    new_lines.append('                        except Exception as restart_error:\n')
                    new_lines.append('                            logger.error(f"❌ Failed to restart audio monitoring: {restart_error}", exc_info=True)\n')
                    new_lines.append('            elif self._audio_last_db_timestamp is None:\n')
                    new_lines.append('                # First reading - initialize\n')
                    new_lines.append('                self._audio_last_db_reading = current_db\n')
                    new_lines.append('                self._audio_last_db_timestamp = now\n')
                    new_lines.append('            else:\n')
                    new_lines.append('                # No dB reading at all - check if it\'s been too long\n')
                    new_lines.append('                age = now - self._audio_last_db_timestamp if self._audio_last_db_timestamp else 0\n')
                    new_lines.append('                if age > 120.0:  # No dB reading for 2 minutes = critical failure\n')
                    new_lines.append('                    self._audio_stall_count += 1\n')
                    new_lines.append('                    logger.error(\n')
                    new_lines.append('                        f"🚨 CRITICAL: No dB readings for {age:.1f}s (stall_count={self._audio_stall_count})"\n')
                    new_lines.append('                    )\n')
                    new_lines.append('                    \n')
                    new_lines.append('                    if self._audio_stall_count >= self._audio_max_stall_before_restart:\n')
                    new_lines.append('                        logger.error("🚨 FORCING COMPLETE AUDIO MONITOR RESTART!")\n')
                    new_lines.append('                        try:\n')
                    new_lines.append('                            self.audio_monitor.stop_monitoring()\n')
                    new_lines.append('                            time.sleep(2)\n')
                    new_lines.append('                            self.audio_monitor.start_monitoring()\n')
                    new_lines.append('                            logger.info("✅ Audio monitoring restarted after complete failure")\n')
                    new_lines.append('                            self._audio_stall_count = 0\n')
                    new_lines.append('                            self._audio_last_db_timestamp = time.time()\n')
                    new_lines.append('                        except Exception as restart_error:\n')
                    new_lines.append('                            logger.error(f"❌ Failed to restart audio monitoring: {restart_error}", exc_info=True)\n')
                    new_lines.append('            \n')
                    watchdog_logic_added = True
                    # Continue with original line
                    new_lines.append(line)
                    i += 1
                    break
                
                new_lines.append(line)
                i += 1
            
            continue
        
        new_lines.append(line)
        i += 1
    
    # Write back
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    if watchdog_vars_added and watchdog_logic_added:
        print("   ✅ Fix applied successfully!")
        sys.exit(0)
    else:
        print("   ⚠️  Partial fix applied (vars: {}, logic: {})".format(watchdog_vars_added, watchdog_logic_added))
        sys.exit(1)

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_PATCH

    if [ $? -eq 0 ]; then
        echo "   ✅ Fix applied!"
    else
        echo "   ❌ Fix failed - check errors above"
        exit 1
    fi
fi

echo ""
echo "3. Restarting service..."
sudo systemctl restart pulse-hub
sleep 5

echo ""
echo "4. Checking status..."
if sudo systemctl is-active --quiet pulse-hub; then
    echo "   ✅ Service is running"
else
    echo "   ❌ Service failed - checking logs:"
    sudo journalctl -u pulse-hub -n 20 --no-pager
    exit 1
fi

echo ""
echo "=========================================="
echo "FIX APPLIED!"
echo "=========================================="
echo ""
echo "Monitor with:"
echo "  sudo journalctl -u pulse-hub -f | grep -E '(Audio|Song|CRITICAL|stalled)'"
echo ""
