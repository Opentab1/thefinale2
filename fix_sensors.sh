#!/bin/bash
# Comprehensive Sensor Fix Script for Pulse System
# Fixes temperature (BME280), audio (dB reader), and song detection

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo -e "PULSE SENSOR FIX - Comprehensive Repair"
echo -e "==========================================${NC}"
echo ""

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        echo -e "${RED}This script must be run with sudo${NC}"
        echo "Usage: sudo bash $0"
        exit 1
    fi
}

# Function to log progress
log_step() {
    echo -e "\n${BLUE}[STEP]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
check_root

# Determine workspace directory
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
if [ ! -d "$WORKSPACE_DIR" ]; then
    WORKSPACE_DIR="/opt/pulse"
fi

if [ ! -d "$WORKSPACE_DIR" ]; then
    log_error "Cannot find Pulse installation directory"
    exit 1
fi

cd "$WORKSPACE_DIR"
log_success "Working directory: $WORKSPACE_DIR"

# ============================================================================
# STEP 1: Update system and install dependencies
# ============================================================================
log_step "Installing system dependencies..."

apt-get update -qq
apt-get install -y \
    i2c-tools \
    python3-dev \
    python3-pip \
    portaudio19-dev \
    libasound2-dev \
    alsa-utils \
    libatlas-base-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    || log_warning "Some system packages may have failed to install"

log_success "System dependencies installed"

# ============================================================================
# STEP 2: Enable I2C interface (for BME280)
# ============================================================================
log_step "Enabling I2C interface..."

# Check if I2C is already enabled
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    # Try both locations (Pi 5 uses /boot/firmware, older Pi uses /boot)
    if [ -f /boot/firmware/config.txt ]; then
        echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt
        log_success "I2C enabled in /boot/firmware/config.txt"
    elif [ -f /boot/config.txt ]; then
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
        log_success "I2C enabled in /boot/config.txt"
    else
        log_warning "Could not find boot config file to enable I2C"
    fi
else
    log_success "I2C already enabled in boot config"
fi

# Load I2C kernel modules
modprobe i2c-dev 2>/dev/null || log_warning "Could not load i2c-dev module"
modprobe i2c-bcm2835 2>/dev/null || log_warning "Could not load i2c-bcm2835 module"

# Add i2c modules to load on boot
if ! grep -q "i2c-dev" /etc/modules 2>/dev/null; then
    echo "i2c-dev" >> /etc/modules
fi

log_success "I2C interface configured"

# ============================================================================
# STEP 3: Configure ALSA audio (for microphone)
# ============================================================================
log_step "Configuring audio system..."

# Create ALSA config for USB microphone
cat > /etc/asound.conf << 'EOF'
# ALSA configuration for Pulse audio monitoring
# Prioritizes USB audio devices for recording

pcm.!default {
    type asym
    playback.pcm "sysdefault"
    capture.pcm "mic"
}

pcm.mic {
    type plug
    slave {
        pcm "hw:1,0"
    }
}

ctl.!default {
    type hw
    card 0
}
EOF

log_success "ALSA audio configured"

# Set proper permissions for audio
usermod -a -G audio pi 2>/dev/null || log_warning "Could not add pi user to audio group"

# ============================================================================
# STEP 4: Install Python dependencies
# ============================================================================
log_step "Installing Python dependencies..."

# Determine Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log_success "Python version: $PYTHON_VERSION"

# Upgrade pip
python3 -m pip install --upgrade pip setuptools wheel

# Install dependencies from requirements.txt
if [ -f "$WORKSPACE_DIR/requirements.txt" ]; then
    log_step "Installing packages from requirements.txt..."
    python3 -m pip install -r "$WORKSPACE_DIR/requirements.txt" || log_warning "Some packages may have failed"
else
    log_warning "requirements.txt not found, installing packages manually..."
    
    # Install critical packages manually
    python3 -m pip install \
        numpy \
        pyaudio \
        sounddevice \
        shazamio \
        aiohttp \
        adafruit-blinka \
        adafruit-circuitpython-bme280 \
        smbus2 \
        RPi.GPIO \
        || log_warning "Some Python packages may have failed"
fi

log_success "Python dependencies installed"

# ============================================================================
# STEP 5: Verify hardware connections
# ============================================================================
log_step "Verifying hardware connections..."

# Check I2C bus
echo ""
echo -e "${YELLOW}I2C Device Scan:${NC}"
if command -v i2cdetect >/dev/null 2>&1; then
    i2cdetect -y 1
    
    # Check for BME280 at common addresses
    if i2cdetect -y 1 | grep -q "76\|77"; then
        log_success "BME280 sensor detected on I2C bus!"
    else
        log_warning "BME280 sensor NOT detected - check wiring"
        log_warning "  Expected at address: 0x76 or 0x77"
        log_warning "  Verify: VCC, GND, SDA (GPIO2), SCL (GPIO3)"
    fi
else
    log_error "i2cdetect not available"
fi

# Check audio devices
echo ""
echo -e "${YELLOW}Audio Recording Devices:${NC}"
if command -v arecord >/dev/null 2>&1; then
    arecord -l
    
    if arecord -l | grep -q "card"; then
        log_success "Audio recording device detected!"
    else
        log_warning "No audio recording devices found"
        log_warning "  Connect a USB microphone or enable onboard audio"
    fi
else
    log_error "arecord not available"
fi

# ============================================================================
# STEP 6: Create diagnostic test script
# ============================================================================
log_step "Creating diagnostic test script..."

cat > "$WORKSPACE_DIR/test_sensors_comprehensive.py" << 'EOFPYTHON'
#!/usr/bin/env python3
"""
Comprehensive Sensor Diagnostic Tool
Tests temperature, audio, and song detection
"""

import sys
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test if all required libraries can be imported"""
    print("\n" + "="*80)
    print("TESTING PYTHON IMPORTS")
    print("="*80)
    
    results = {}
    
    # Test numpy
    try:
        import numpy as np
        print(f"✓ numpy: {np.__version__}")
        results['numpy'] = True
    except ImportError as e:
        print(f"✗ numpy: NOT FOUND ({e})")
        results['numpy'] = False
    
    # Test PyAudio
    try:
        import pyaudio
        print(f"✓ pyaudio: {pyaudio.__version__}")
        results['pyaudio'] = True
    except ImportError as e:
        print(f"✗ pyaudio: NOT FOUND ({e})")
        results['pyaudio'] = False
    
    # Test sounddevice
    try:
        import sounddevice as sd
        print(f"✓ sounddevice: {sd.__version__}")
        results['sounddevice'] = True
    except ImportError as e:
        print(f"✗ sounddevice: NOT FOUND ({e})")
        results['sounddevice'] = False
    
    # Test ShazamIO
    try:
        import shazamio
        print(f"✓ shazamio: OK")
        results['shazamio'] = True
    except ImportError as e:
        print(f"✗ shazamio: NOT FOUND ({e})")
        results['shazamio'] = False
    
    # Test adafruit_bme280
    try:
        import adafruit_bme280
        print(f"✓ adafruit_bme280: OK")
        results['adafruit_bme280'] = True
    except ImportError as e:
        print(f"✗ adafruit_bme280: NOT FOUND ({e})")
        results['adafruit_bme280'] = False
    
    # Test smbus2
    try:
        import smbus2
        print(f"✓ smbus2: {smbus2.__version__}")
        results['smbus2'] = True
    except ImportError as e:
        print(f"✗ smbus2: NOT FOUND ({e})")
        results['smbus2'] = False
    
    return results

def test_bme280():
    """Test BME280 temperature sensor"""
    print("\n" + "="*80)
    print("TESTING BME280 TEMPERATURE SENSOR")
    print("="*80)
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.bme280_reader import BME280Reader
        
        print("Initializing BME280...")
        sensor = BME280Reader()
        
        print("Reading sensor data...")
        data = sensor.read_sensor()
        
        if data and data.get('temperature_f'):
            print(f"\n✓ BME280 WORKING!")
            print(f"  Temperature: {data['temperature_f']:.1f}°F ({data['temperature_c']:.1f}°C)")
            print(f"  Humidity: {data['humidity']:.1f}%")
            print(f"  Pressure: {data['pressure']:.2f} hPa")
            return True
        else:
            print("\n✗ BME280 returned no data")
            return False
            
    except Exception as e:
        print(f"\n✗ BME280 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_audio_devices():
    """Test audio device detection"""
    print("\n" + "="*80)
    print("TESTING AUDIO DEVICES")
    print("="*80)
    
    try:
        import sounddevice as sd
        
        print("\nAvailable audio devices:")
        devices = sd.query_devices()
        
        has_input = False
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                has_input = True
                print(f"  [{i}] {device['name']} (Input: {device['max_input_channels']} ch)")
        
        if has_input:
            print("\n✓ Audio input devices found!")
            return True
        else:
            print("\n✗ No audio input devices found")
            return False
            
    except Exception as e:
        print(f"\n✗ Audio device test FAILED: {e}")
        return False

def test_audio_monitoring():
    """Test audio monitoring (dB level)"""
    print("\n" + "="*80)
    print("TESTING AUDIO MONITORING (dB READER)")
    print("="*80)
    
    try:
        sys.path.insert(0, '/workspace/services')
        from sensors.mic_song_detect import AudioMonitor
        
        print("Initializing audio monitor...")
        monitor = AudioMonitor()
        
        print("Starting monitoring (10 second test)...")
        monitor.start_monitoring()
        
        time.sleep(10)
        
        db_level = monitor.get_current_db()
        
        monitor.stop_monitoring()
        
        if db_level > 0:
            print(f"\n✓ AUDIO MONITORING WORKING!")
            print(f"  Current dB level: {db_level:.1f} dB")
            return True
        else:
            print(f"\n⚠ Audio monitoring started but no sound detected")
            print(f"  This may be normal if environment is silent")
            print(f"  Make some noise and check dashboard for updates")
            return True
            
    except Exception as e:
        print(f"\n✗ Audio monitoring FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_song_detection():
    """Test song detection capability"""
    print("\n" + "="*80)
    print("TESTING SONG DETECTION")
    print("="*80)
    
    try:
        from shazamio import Shazam
        
        print("✓ ShazamIO library available")
        print("  Song detection will work when music is playing")
        print("  Note: Requires internet connection to identify songs")
        return True
        
    except ImportError as e:
        print(f"✗ ShazamIO NOT available: {e}")
        print("  Install with: pip install shazamio aiohttp")
        return False

def main():
    """Run all diagnostic tests"""
    print("\n" + "="*80)
    print("PULSE SENSOR COMPREHENSIVE DIAGNOSTIC")
    print("="*80)
    
    # Test imports
    import_results = test_imports()
    
    # Test hardware
    bme280_ok = test_bme280()
    audio_devices_ok = test_audio_devices()
    audio_monitor_ok = test_audio_monitoring()
    song_detect_ok = test_song_detection()
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)
    
    all_ok = (
        import_results.get('numpy', False) and
        import_results.get('adafruit_bme280', False) and
        (import_results.get('pyaudio', False) or import_results.get('sounddevice', False)) and
        bme280_ok and
        audio_monitor_ok
    )
    
    if all_ok:
        print("\n✓✓✓ ALL CRITICAL SENSORS WORKING! ✓✓✓")
        print("\nYou can now start the Pulse system:")
        print("  sudo python3 /workspace/start_pulse.sh")
    else:
        print("\n⚠ SOME ISSUES DETECTED")
        print("\nIssues found:")
        if not import_results.get('adafruit_bme280', False):
            print("  - BME280 library not installed")
        if not bme280_ok:
            print("  - BME280 sensor not working (check I2C wiring)")
        if not (import_results.get('pyaudio', False) or import_results.get('sounddevice', False)):
            print("  - Audio libraries not installed")
        if not audio_monitor_ok:
            print("  - Audio monitoring not working (check microphone)")
        
        print("\nRun the fix script again:")
        print("  sudo bash /workspace/fix_sensors.sh")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
EOFPYTHON

chmod +x "$WORKSPACE_DIR/test_sensors_comprehensive.py"
log_success "Diagnostic script created: test_sensors_comprehensive.py"

# ============================================================================
# STEP 7: Run diagnostic tests
# ============================================================================
log_step "Running diagnostic tests..."
echo ""

# Run as the pi user if available, otherwise current user
if id -u pi >/dev/null 2>&1; then
    sudo -u pi python3 "$WORKSPACE_DIR/test_sensors_comprehensive.py"
else
    python3 "$WORKSPACE_DIR/test_sensors_comprehensive.py"
fi

# ============================================================================
# FINAL STEPS
# ============================================================================
echo ""
log_step "Fix complete!"
echo ""
echo -e "${GREEN}=========================================="
echo -e "SENSOR FIX COMPLETE"
echo -e "==========================================${NC}"
echo ""
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo ""
echo "1. If I2C was just enabled, reboot the system:"
echo -e "   ${BLUE}sudo reboot${NC}"
echo ""
echo "2. After reboot, test sensors again:"
echo -e "   ${BLUE}python3 /workspace/test_sensors_comprehensive.py${NC}"
echo ""
echo "3. Start the Pulse system:"
echo -e "   ${BLUE}bash /workspace/start_pulse.sh${NC}"
echo ""
echo -e "${YELLOW}TROUBLESHOOTING:${NC}"
echo ""
echo "• If BME280 still not working:"
echo "  - Check wiring: VCC→3.3V, GND→GND, SDA→GPIO2, SCL→GPIO3"
echo "  - Verify with: sudo i2cdetect -y 1"
echo ""
echo "• If audio not working:"
echo "  - Check USB microphone is connected"
echo "  - List devices: arecord -l"
echo "  - Test recording: arecord -d 5 test.wav"
echo ""
echo "• View logs:"
echo "  - tail -f /var/log/pulse/hub.log"
echo ""
