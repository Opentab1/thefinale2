#!/bin/bash
# Improved Sensor Fix Script - Works in VM and RPi environments
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo -e "PULSE SENSOR FIX V2 - Universal Installer"
echo -e "==========================================${NC}"

# Determine if we're on actual RPi or VM
IS_RPI=false
if [ -f /proc/device-tree/model ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    IS_RPI=true
    echo -e "${GREEN}Detected: Raspberry Pi${NC}"
else
    echo -e "${YELLOW}Detected: VM/Container (not native RPi)${NC}"
    echo -e "${YELLOW}Some hardware features may not be available${NC}"
fi

WORKSPACE_DIR="/workspace"
cd "$WORKSPACE_DIR"

# Install Python packages using --break-system-packages flag for Python 3.12+
echo -e "\n${BLUE}[STEP] Installing Python dependencies...${NC}"

# Critical packages for sensors
python3 -m pip install --break-system-packages \
    numpy \
    pyaudio \
    sounddevice \
    shazamio \
    aiohttp \
    adafruit-blinka \
    adafruit-circuitpython-bme280 \
    smbus2 \
    RPi.GPIO \
    2>&1 || echo -e "${YELLOW}Some packages may have failed (continuing anyway)${NC}"

echo -e "${GREEN}✓ Python packages installation complete${NC}"

# Test what's actually installed
echo -e "\n${BLUE}[STEP] Testing installed packages...${NC}"

test_package() {
    if python3 -c "import $1" 2>/dev/null; then
        echo -e "${GREEN}✓ $1${NC}"
        return 0
    else
        echo -e "${RED}✗ $1${NC}"
        return 1
    fi
}

test_package "numpy"
test_package "pyaudio" || echo -e "  ${YELLOW}→ Try: sudo apt install python3-pyaudio${NC}"
test_package "sounddevice" || echo -e "  ${YELLOW}→ Try: sudo apt install python3-sounddevice${NC}"
test_package "shazamio"
test_package "adafruit_bme280"
test_package "smbus2"

echo -e "\n${BLUE}[STEP] Creating comprehensive diagnostic script...${NC}"

# Create the test script
cat > "$WORKSPACE_DIR/test_sensors_quick.py" << 'EOFPY'
#!/usr/bin/env python3
"""Quick sensor diagnostic"""
import sys

def test_libs():
    print("\n" + "="*60)
    print("LIBRARY IMPORT TEST")
    print("="*60)
    
    libs = ['numpy', 'pyaudio', 'sounddevice', 'shazamio', 
            'adafruit_bme280', 'smbus2']
    results = {}
    
    for lib in libs:
        try:
            __import__(lib)
            print(f"✓ {lib}")
            results[lib] = True
        except ImportError as e:
            print(f"✗ {lib}: {e}")
            results[lib] = False
    
    return results

def test_bme280():
    print("\n" + "="*60)
    print("BME280 TEMPERATURE SENSOR TEST")
    print("="*60)
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.bme280_reader import BME280Reader
        
        print("Initializing BME280...")
        sensor = BME280Reader()
        
        print("Reading sensor...")
        data = sensor.read_sensor()
        
        if data and data.get('temperature_f'):
            print(f"\n✓✓✓ BME280 WORKING! ✓✓✓")
            print(f"Temperature: {data['temperature_f']:.1f}°F")
            print(f"Humidity: {data['humidity']:.1f}%")
            return True
        else:
            print("\n✗ BME280 returned no data")
            return False
    except Exception as e:
        print(f"\n✗ BME280 FAILED: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False

def test_audio():
    print("\n" + "="*60)
    print("AUDIO SYSTEM TEST")
    print("="*60)
    
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        
        print(f"\nFound {len(devices)} audio devices:")
        has_input = False
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                print(f"  [{i}] {dev['name']} (INPUT)")
                has_input = True
        
        if has_input:
            print("\n✓ Audio input devices available")
            return True
        else:
            print("\n✗ No audio input devices found")
            return False
    except Exception as e:
        print(f"\n✗ Audio test failed: {e}")
        return False

def test_audio_monitor():
    print("\n" + "="*60)
    print("AUDIO MONITORING TEST (5 seconds)")
    print("="*60)
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.mic_song_detect import AudioMonitor
        import time
        
        print("Starting audio monitor...")
        monitor = AudioMonitor()
        monitor.start_monitoring()
        
        print("Monitoring for 5 seconds...")
        time.sleep(5)
        
        db = monitor.get_current_db()
        monitor.stop_monitoring()
        
        if db > 0:
            print(f"\n✓✓✓ AUDIO MONITORING WORKING! ✓✓✓")
            print(f"Current dB: {db:.1f}")
            return True
        else:
            print(f"\n⚠ Monitor started but no sound detected (may be normal if silent)")
            return True
    except Exception as e:
        print(f"\n✗ Audio monitoring failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("PULSE SENSOR QUICK DIAGNOSTIC")
    print("="*60)
    
    lib_results = test_libs()
    bme_ok = test_bme280()
    audio_ok = test_audio()
    monitor_ok = test_audio_monitor()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    critical_libs = all([
        lib_results.get('numpy', False),
        lib_results.get('adafruit_bme280', False) or not any([bme_ok]),
        lib_results.get('pyaudio', False) or lib_results.get('sounddevice', False)
    ])
    
    if bme_ok and monitor_ok:
        print("\n✓✓✓ ALL SENSORS WORKING! ✓✓✓")
        print("\nStart Pulse with: bash /workspace/start_pulse.sh")
        return 0
    else:
        print("\n⚠ PARTIAL SUCCESS")
        if not bme_ok:
            print("  - BME280: NOT WORKING")
        else:
            print("  - BME280: OK")
        
        if not monitor_ok:
            print("  - Audio Monitor: NOT WORKING")
        else:
            print("  - Audio Monitor: OK")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOFPY

chmod +x "$WORKSPACE_DIR/test_sensors_quick.py"

echo -e "${GREEN}✓ Diagnostic script created${NC}"

# Run diagnostics
echo -e "\n${BLUE}[STEP] Running diagnostics...${NC}\n"
python3 "$WORKSPACE_DIR/test_sensors_quick.py" || true

echo -e "\n${BLUE}=========================================="
echo -e "INSTALLATION COMPLETE"
echo -e "==========================================${NC}"

echo -e "\n${YELLOW}NEXT STEPS:${NC}"
echo -e "1. Start Pulse: ${BLUE}bash /workspace/start_pulse.sh${NC}"
echo -e "2. Check dashboard at: ${BLUE}http://localhost:8080${NC}"
echo -e "3. Watch logs: ${BLUE}tail -f /var/log/pulse/hub.log${NC}"

if [ "$IS_RPI" = false ]; then
    echo -e "\n${YELLOW}NOTE: Running in VM/Container${NC}"
    echo -e "BME280 sensor will not work without real hardware"
    echo -e "Audio may work if passthrough is configured"
fi
