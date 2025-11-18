#!/bin/bash
################################################################################
# PULSE UNIT REMOTE DIAGNOSTIC SCRIPT
# Version: 1.0
# Date: 2025-11-18
# Purpose: Complete forensic-grade diagnostic for live venue Pulse unit
# Target: Raspberry Pi 5 @ 10.40.43.12
# 
# ⚠️ CRITICAL: This script is READ-ONLY - makes NO changes to the system
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Output file
REPORT_FILE="/tmp/pulse_diagnostic_$(date +%Y%m%d_%H%M%S).txt"

echo "========================================================================="
echo "PULSE UNIT FORENSIC DIAGNOSTIC - START"
echo "Date: $(date)"
echo "Report will be saved to: $REPORT_FILE"
echo "========================================================================="

# Function to log to both stdout and file
log() {
    echo -e "$1" | tee -a "$REPORT_FILE"
}

log_section() {
    log "\n${BLUE}=========================================================================${NC}"
    log "${BLUE}$1${NC}"
    log "${BLUE}=========================================================================${NC}"
}

log_success() {
    log "${GREEN}✅ $1${NC}"
}

log_error() {
    log "${RED}❌ $1${NC}"
}

log_warning() {
    log "${YELLOW}⚠️  $1${NC}"
}

################################################################################
# 1. SYSTEM INFORMATION & HARDWARE VERIFICATION
################################################################################
log_section "1. SYSTEM INFORMATION & HARDWARE VERIFICATION"

log "\n--- Basic System Info ---"
log "Hostname: $(hostname)"
log "Kernel: $(uname -a)"
log "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
log "Uptime: $(uptime -p)"
log "Current time: $(date)"

log "\n--- CPU & Temperature ---"
log "CPU Temperature: $(vcgencmd measure_temp)"
log "CPU Info:"
cat /proc/cpuinfo | grep -E "Model|Hardware|Revision" | tee -a "$REPORT_FILE"

log "\n--- Throttling Status (Power/Heat Issues) ---"
THROTTLE=$(vcgencmd get_throttled)
log "Throttle status: $THROTTLE"
if [[ "$THROTTLE" == *"0x0"* ]]; then
    log_success "No throttling detected - power and temperature OK"
else
    log_error "THROTTLING DETECTED - This WILL cause failures!"
    log "Throttle codes: 0x1=Under-voltage, 0x2=ARM freq capped, 0x4=Throttled, 0x8=Soft temp limit"
fi

log "\n--- Memory Usage ---"
free -h | tee -a "$REPORT_FILE"

log "\n--- Disk Usage ---"
df -h | tee -a "$REPORT_FILE"

log "\n--- USB Devices (Microphone Detection) ---"
lsusb | tee -a "$REPORT_FILE"
USB_MIC_COUNT=$(lsusb | grep -i "audio\|microphone" | wc -l)
if [ "$USB_MIC_COUNT" -gt 0 ]; then
    log_success "USB audio device detected"
else
    log_warning "No USB audio device detected in lsusb"
fi

log "\n--- I2C Devices (BME280 Detection) ---"
i2cdetect -y 1 | tee -a "$REPORT_FILE"
if i2cdetect -y 1 | grep -E "(76|77)"; then
    log_success "BME280 sensor detected at address 0x76 or 0x77"
else
    log_error "BME280 sensor NOT detected on I2C bus"
fi

log "\n--- Audio Devices (arecord) ---"
arecord -l | tee -a "$REPORT_FILE"
AUDIO_CARD_COUNT=$(arecord -l | grep "card" | wc -l)
if [ "$AUDIO_CARD_COUNT" -gt 0 ]; then
    log_success "Audio recording device(s) found: $AUDIO_CARD_COUNT"
else
    log_error "NO audio recording devices found - mic detection will fail"
fi

log "\n--- Camera Detection ---"
if command -v libcamera-hello &> /dev/null; then
    log "Camera detection (libcamera):"
    timeout 5 libcamera-hello --list-cameras 2>&1 | head -20 | tee -a "$REPORT_FILE" || log_warning "Camera detection timed out or failed"
else
    log_warning "libcamera-hello not found - cannot test camera"
fi

log "\n--- AI HAT Detection ---"
if [ -e "/dev/hailo0" ]; then
    log_success "Hailo AI HAT detected at /dev/hailo0"
elif [ -e "/dev/apex_0" ]; then
    log_success "Google Coral AI HAT detected at /dev/apex_0"
else
    log_warning "No AI accelerator detected (will use CPU fallback)"
fi

log "\n--- Network Status ---"
log "IP Addresses:"
ip -4 addr show | grep inet | tee -a "$REPORT_FILE"
log "\nNetwork connectivity:"
if ping -c 3 -W 2 8.8.8.8 &> /dev/null; then
    log_success "Internet connectivity OK (ping 8.8.8.8 successful)"
else
    log_error "NO internet connectivity - Shazam API will fail"
fi

log "\n--- Recent System Errors (dmesg) ---"
dmesg --time-format iso | grep -i "error\|fail\|warn" | tail -50 | tee -a "$REPORT_FILE"

################################################################################
# 2. PULSE INSTALLATION VERIFICATION
################################################################################
log_section "2. PULSE INSTALLATION VERIFICATION"

log "\n--- Pulse Directory Structure ---"
PULSE_DIR="/opt/pulse"
if [ -d "$PULSE_DIR" ]; then
    log_success "Pulse directory exists: $PULSE_DIR"
    log "Directory size: $(du -sh $PULSE_DIR 2>/dev/null)"
    log "\nDirectory listing:"
    ls -la "$PULSE_DIR" | tee -a "$REPORT_FILE"
else
    log_error "Pulse directory NOT found at $PULSE_DIR"
    log "Checking alternate location /workspace..."
    if [ -d "/workspace" ]; then
        PULSE_DIR="/workspace"
        log_success "Found Pulse at /workspace"
    else
        log_error "Cannot find Pulse installation!"
        exit 1
    fi
fi

log "\n--- Critical Files Check ---"
CRITICAL_FILES=(
    "$PULSE_DIR/run_audio_service.py"
    "$PULSE_DIR/run_camera_service.py"
    "$PULSE_DIR/run_environmental_service.py"
    "$PULSE_DIR/run_hub_service.py"
    "$PULSE_DIR/services/sensors/simple_song_detector.py"
    "$PULSE_DIR/services/sensors/simple_decibel_detector.py"
    "$PULSE_DIR/services/sensors/camera_people.py"
    "$PULSE_DIR/services/sensors/bme280_reader.py"
    "$PULSE_DIR/config/config.yaml"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        log_success "Found: $file"
    else
        log_error "MISSING: $file"
    fi
done

log "\n--- Git Repository Status ---"
cd "$PULSE_DIR"
if [ -d ".git" ]; then
    log "Git branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'Cannot determine')"
    log "Git commit: $(git rev-parse HEAD 2>/dev/null || echo 'Cannot determine')"
    log "Git remote: $(git remote -v 2>/dev/null || echo 'No remotes')"
    log "\nGit status:"
    git status --short | tee -a "$REPORT_FILE"
    log "\nRecent commits:"
    git log --oneline -10 | tee -a "$REPORT_FILE"
else
    log_warning "Not a git repository"
fi

log "\n--- Python Environment ---"
log "System Python: $(python3 --version)"
if [ -d "$PULSE_DIR/venv" ]; then
    log_success "Virtual environment exists"
    log "Venv Python: $($PULSE_DIR/venv/bin/python3 --version)"
    log "\nInstalled packages (key ones):"
    $PULSE_DIR/venv/bin/pip list | grep -E "sounddevice|shazamio|opencv|numpy|pyaudio|librosa" | tee -a "$REPORT_FILE"
else
    log_warning "No virtual environment found at $PULSE_DIR/venv"
fi

log "\n--- Configuration File ---"
if [ -f "$PULSE_DIR/config/config.yaml" ]; then
    log "Configuration:"
    cat "$PULSE_DIR/config/config.yaml" | tee -a "$REPORT_FILE"
else
    log_error "Configuration file missing!"
fi

################################################################################
# 3. SERVICE STATUS & LOGS
################################################################################
log_section "3. SERVICE STATUS & LOGS"

log "\n--- Systemd Services ---"
SERVICES=("pulse-audio" "pulse-camera" "pulse-environmental" "pulse-hub-main" "pulse.service")

for service in "${SERVICES[@]}"; do
    log "\n=== $service ==="
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        log_success "Service $service is ACTIVE"
        systemctl status "$service" --no-pager -l | head -30 | tee -a "$REPORT_FILE"
    else
        log_error "Service $service is NOT ACTIVE"
        systemctl status "$service" --no-pager -l 2>&1 | head -30 | tee -a "$REPORT_FILE" || log "Service not found"
    fi
done

log "\n--- Process List (Pulse-related) ---"
ps aux | grep -E "python.*pulse|run_.*service" | grep -v grep | tee -a "$REPORT_FILE"

log "\n--- Recent Logs (Last 200 Lines) ---"
for service in "${SERVICES[@]}"; do
    log "\n--- Logs for $service (last 200 lines) ---"
    journalctl -u "$service" -n 200 --no-pager 2>/dev/null | tee -a "$REPORT_FILE" || log "No logs available for $service"
done

log "\n--- Error Logs (Last 50 Errors/Warnings) ---"
for service in "${SERVICES[@]}"; do
    log "\n--- Errors/Warnings in $service ---"
    journalctl -u "$service" -p warning --no-pager -n 50 2>/dev/null | tee -a "$REPORT_FILE" || log "No errors found"
done

################################################################################
# 4. REAL-TIME SENSOR TESTS
################################################################################
log_section "4. REAL-TIME SENSOR TESTS"

log "\n--- BME280 Test Read ---"
if [ -f "$PULSE_DIR/venv/bin/python3" ]; then
    log "Testing BME280 sensor..."
    $PULSE_DIR/venv/bin/python3 -c "
import sys
sys.path.insert(0, '$PULSE_DIR')
sys.path.insert(0, '$PULSE_DIR/services')
try:
    from services.sensors.bme280_reader import BME280Reader
    reader = BME280Reader()
    data = reader.read()
    print(f'✅ BME280 READ SUCCESS:')
    print(f'  Temperature: {data.get(\"temperature_f\", \"N/A\")}°F')
    print(f'  Humidity: {data.get(\"humidity\", \"N/A\")}%')
    print(f'  Pressure: {data.get(\"pressure_hpa\", \"N/A\")} hPa')
except Exception as e:
    print(f'❌ BME280 READ FAILED: {e}')
    import traceback
    traceback.print_exc()
" 2>&1 | tee -a "$REPORT_FILE"
fi

log "\n--- USB Microphone Test Record ---"
log "Recording 2-second test audio sample..."
TEST_AUDIO="/tmp/pulse_mic_test_$(date +%s).wav"
if timeout 10 arecord -d 2 -f cd -t wav "$TEST_AUDIO" 2>&1 | tee -a "$REPORT_FILE"; then
    log_success "Audio recording successful: $TEST_AUDIO"
    log "File size: $(ls -lh $TEST_AUDIO | awk '{print $5}')"
    
    # Test sounddevice (used by audio services)
    log "\n--- Testing sounddevice library ---"
    $PULSE_DIR/venv/bin/python3 -c "
import sounddevice as sd
print('Available audio devices:')
print(sd.query_devices())
print('\nDefault input device:')
print(sd.query_devices(kind='input'))
" 2>&1 | tee -a "$REPORT_FILE"
else
    log_error "Audio recording FAILED"
fi

log "\n--- Camera Frame Capture Test ---"
log "Attempting to capture a test frame..."
$PULSE_DIR/venv/bin/python3 -c "
import sys
import cv2
try:
    # Try picamera2 first
    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        config = camera.create_video_configuration(main={'size': (640, 480), 'format': 'RGB888'})
        camera.configure(config)
        camera.start()
        frame = camera.capture_array()
        camera.stop()
        print(f'✅ PICAMERA2 CAPTURE SUCCESS: {frame.shape}')
        sys.exit(0)
    except Exception as e:
        print(f'⚠️ Picamera2 not available: {e}')
    
    # Try USB camera
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()
        if ret:
            print(f'✅ USB CAMERA CAPTURE SUCCESS: {frame.shape}')
        else:
            print('❌ USB camera opened but cannot read frames')
    else:
        print('❌ Cannot open camera (index 0)')
except Exception as e:
    print(f'❌ CAMERA CAPTURE FAILED: {e}')
    import traceback
    traceback.print_exc()
" 2>&1 | tee -a "$REPORT_FILE"

################################################################################
# 5. CACHE FILES & RECENT DATA
################################################################################
log_section "5. CACHE FILES & RECENT DATA"

log "\n--- Cache Directory Contents ---"
CACHE_DIR="/opt/pulse/data"
if [ -d "$CACHE_DIR" ]; then
    log "Cache directory: $CACHE_DIR"
    ls -lah "$CACHE_DIR" | tee -a "$REPORT_FILE"
    
    log "\n--- Decibel Cache ---"
    if [ -f "$CACHE_DIR/decibel_cache.json" ]; then
        cat "$CACHE_DIR/decibel_cache.json" | tee -a "$REPORT_FILE"
    else
        log_warning "No decibel cache file found"
    fi
    
    log "\n--- Song Cache ---"
    if [ -f "$CACHE_DIR/song_cache.json" ]; then
        cat "$CACHE_DIR/song_cache.json" | tee -a "$REPORT_FILE"
    else
        log_warning "No song cache file found"
    fi
    
    log "\n--- People Cache ---"
    if [ -f "$CACHE_DIR/people_cache.json" ]; then
        cat "$CACHE_DIR/people_cache.json" | tee -a "$REPORT_FILE"
    else
        log_warning "No people cache file found"
    fi
else
    log_warning "Cache directory not found: $CACHE_DIR"
fi

################################################################################
# 6. STRESS TEST PREPARATION
################################################################################
log_section "6. STRESS TEST READINESS"

log "\n--- System Resource Baseline ---"
log "Load average: $(cat /proc/loadavg)"
log "CPU usage: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
log "Memory available: $(free -h | awk '/^Mem:/ {print $7}')"
log "Swap usage: $(free -h | awk '/^Swap:/ {print $3}')"

log "\n--- Thread Counts (Current) ---"
for service in pulse-audio pulse-camera pulse-environmental pulse-hub-main; do
    PID=$(pgrep -f "run_.*service.py|$service" | head -1)
    if [ -n "$PID" ]; then
        THREADS=$(ps -T -p "$PID" 2>/dev/null | wc -l)
        log "$service (PID $PID): $((THREADS - 1)) threads"
    else
        log "$service: Not running"
    fi
done

################################################################################
# 7. SUMMARY & RECOMMENDATIONS
################################################################################
log_section "7. DIAGNOSTIC SUMMARY"

log "\n${GREEN}=== DIAGNOSTIC COMPLETE ===${NC}"
log "Report saved to: $REPORT_FILE"
log "\nTo view the full report:"
log "  cat $REPORT_FILE"
log "\nTo copy report to your local machine:"
log "  scp pi@10.40.43.12:$REPORT_FILE ."

log "\n${YELLOW}=== NEXT STEPS ===${NC}"
log "1. Review the report for any RED errors"
log "2. Check service logs for failure patterns"
log "3. Verify hardware detection (BME280, microphone, camera)"
log "4. Run targeted tests based on findings"
log "5. DO NOT make changes until root cause is identified"

echo ""
echo "========================================================================="
echo "PULSE UNIT FORENSIC DIAGNOSTIC - COMPLETE"
echo "========================================================================="
