# QUICK FIX FOR YOUR PI

## Step 1: Check what's wrong

Run these commands on your Pi:

```bash
# Check if service is running
sudo systemctl status pulse-hub

# Check if service file exists
ls -lh /opt/pulse/services/hub/main.py

# Check Python process
ps aux | grep pulse-hub

# Check for any errors
sudo journalctl -u pulse-hub --since "1 hour ago" --no-pager | tail -50
```

## Step 2: If service is NOT running, start it

```bash
sudo systemctl start pulse-hub
sudo systemctl status pulse-hub
```

## Step 3: Apply the fix

Copy and paste this entire block into your Pi terminal:

```bash
cat > /tmp/fix_audio.py << 'ENDPYTHON'
#!/usr/bin/env python3
import sys
import re

file_path = "/opt/pulse/services/hub/main.py"

# Backup
import shutil
from datetime import datetime
backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy2(file_path, backup_path)
print(f"Backed up to: {backup_path}")

with open(file_path, 'r') as f:
    content = f.read()

# Check if already fixed
if "CRITICAL FIX: Audio monitoring watchdog" in content:
    print("✅ Fix already applied!")
    sys.exit(0)

# Add watchdog variables
if "self.stop_event = Event()" in content and "_audio_last_db_reading" not in content:
    content = content.replace(
        "self.stop_event = Event()",
        """self.stop_event = Event()

        # CRITICAL FIX: Audio monitoring watchdog tracking
        self._audio_last_db_reading = None
        self._audio_last_db_timestamp = None
        self._audio_stall_count = 0
        self._audio_max_stall_before_restart = 3  # Restart after 3 consecutive stalls"""
    )
    print("✅ Added watchdog variables")

# Add watchdog logic
if 'if self.audio_monitor:' in content and 'CRITICAL FIX: Watchdog to detect' not in content:
    # Find the pattern to replace
    pattern = r'(if self\.audio_monitor:\s+data\["noise_db"\] = self\._sanitize_environment_value\(self\.audio_monitor\.get_current_db\(\)\))'
    
    replacement = '''if self.audio_monitor:
            current_db = self._sanitize_environment_value(self.audio_monitor.get_current_db())
            data["noise_db"] = current_db'''
    
    content = re.sub(pattern, replacement, content)
    
    # Add watchdog logic before song detection logging
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
    
    # Insert before song detection logging
    pattern = r'(            # Log song detection status for debugging)'
    replacement = watchdog_code + r'\1'
    content = re.sub(pattern, replacement, content, count=1)
    print("✅ Added watchdog logic")

# Write back
with open(file_path, 'w') as f:
    f.write(content)

print("✅ Fix applied successfully!")
ENDPYTHON

sudo python3 /tmp/fix_audio.py
sudo systemctl restart pulse-hub
sleep 5
sudo systemctl status pulse-hub
```

## Step 4: Verify it's working

```bash
# Watch logs in real-time
sudo journalctl -u pulse-hub -f | grep -E "(Audio|Song|CRITICAL|stalled)"

# Or view recent logs
sudo journalctl -u pulse-hub --since "1 minute ago" | grep Audio
```

## If service won't start

Check for errors:
```bash
sudo journalctl -u pulse-hub -n 50 --no-pager
```

Check if Python can import:
```bash
cd /opt/pulse
python3 -c "from services.hub.main import PulseHub; print('Import OK')"
```
