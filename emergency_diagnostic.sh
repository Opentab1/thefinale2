#!/bin/bash
# Emergency Diagnostic - Find out what's broken

echo "========================================================================"
echo "PULSE EMERGENCY DIAGNOSTICS"
echo "========================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}1. Checking running processes...${NC}"
echo "----------------------------------------"
ps aux | grep -E "(pulse|hub|dashboard)" | grep -v grep || echo "No Pulse processes running"
echo ""

echo -e "${CYAN}2. Checking systemd services...${NC}"
echo "----------------------------------------"
systemctl status pulse-hub.service --no-pager -l | head -20
echo ""
systemctl status pulse-dashboard.service --no-pager -l | head -20
echo ""

echo -e "${CYAN}3. Checking recent hub logs...${NC}"
echo "----------------------------------------"
journalctl -u pulse-hub -n 50 --no-pager
echo ""

echo -e "${CYAN}4. Checking Python installation...${NC}"
echo "----------------------------------------"
if [ -f /opt/pulse/venv/bin/python3 ]; then
    echo "✓ Virtual environment exists"
    /opt/pulse/venv/bin/python3 --version
else
    echo "✗ Virtual environment NOT found"
fi
echo ""

echo -e "${CYAN}5. Checking critical dependencies...${NC}"
echo "----------------------------------------"
if [ -f /opt/pulse/venv/bin/pip ]; then
    /opt/pulse/venv/bin/pip list | grep -E "(numpy|opencv|pyaudio|sounddevice|shazamio)"
else
    echo "✗ Cannot check - venv not found"
fi
echo ""

echo -e "${CYAN}6. Testing sensor imports...${NC}"
echo "----------------------------------------"
cd /opt/pulse
/opt/pulse/venv/bin/python3 << 'PYEOF'
import sys
sys.path.insert(0, '/opt/pulse')
sys.path.insert(0, '/opt/pulse/services')

print("Testing imports...")
try:
    import numpy
    print("  ✓ numpy")
except Exception as e:
    print(f"  ✗ numpy: {e}")

try:
    import cv2
    print("  ✓ opencv (cv2)")
except Exception as e:
    print(f"  ✗ opencv: {e}")

try:
    import pyaudio
    print("  ✓ pyaudio")
except Exception as e:
    print(f"  ✗ pyaudio: {e}")

try:
    import sounddevice
    print("  ✓ sounddevice")
except Exception as e:
    print(f"  ✗ sounddevice: {e}")

try:
    from sensors.light_level import LightSensor
    print("  ✓ LightSensor module")
except Exception as e:
    print(f"  ✗ LightSensor: {e}")

try:
    from sensors.mic_song_detect import AudioMonitor
    print("  ✓ AudioMonitor module")
except Exception as e:
    print(f"  ✗ AudioMonitor: {e}")
PYEOF
echo ""

echo -e "${CYAN}7. Checking file permissions...${NC}"
echo "----------------------------------------"
ls -la /opt/pulse/services/hub/main.py
ls -la /opt/pulse/START_HERE.sh
echo ""

echo -e "${CYAN}8. Checking log files...${NC}"
echo "----------------------------------------"
if [ -f /var/log/pulse/hub.log ]; then
    echo "Last 30 lines of hub.log:"
    tail -30 /var/log/pulse/hub.log
else
    echo "✗ No hub.log found"
fi
echo ""

echo "========================================================================"
echo "DIAGNOSTIC COMPLETE"
echo "========================================================================"
echo ""
echo "Copy this output and share it for troubleshooting"
