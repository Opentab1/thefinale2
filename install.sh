#!/bin/bash
# Pulse 1.0 - One-Line Installation Script
# For Raspberry Pi 5 with Raspberry Pi OS (64-bit)

set -e
set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║      Pulse 1.0 Installation          ║"
echo "║  Autonomous Venue Operating System    ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    echo -e "${RED}Error: This installer requires a Raspberry Pi${NC}"
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run with sudo${NC}"
    exit 1
fi

INSTALL_DIR="/opt/pulse"
LOG_DIR="/var/log/pulse"
USER="pi"

echo -e "${YELLOW}[1/10] Updating system packages...${NC}"
apt-get update -qq
apt-get upgrade -y -qq

echo -e "${YELLOW}[2/10] Installing dependencies...${NC}"
# Base and build dependencies (ensure wheels/sdists build on Python 3.13, aarch64)
apt-get install -y \
    git \
    wget \
    python3-full \
    python3-pip \
    python3-venv \
    python3-dev \
    nodejs \
    npm \
    ffmpeg \
    v4l-utils \
    pulseaudio \
    alsa-utils \
    python3-picamera2 \
    libopenblas-dev \
    libportaudio2 \
    portaudio19-dev \
    libsndfile1 \
    i2c-tools \
    python3-libgpiod \
    chromium \
    unclutter \
    cec-utils \
    libcec-dev \
    libcap-dev \
    libsndfile1 \
    libgl1 \
    libglib2.0-0 \
    sqlite3 \
    python3-rpi.gpio \
    wget \
    2>&1 | tee -a /tmp/pulse_install.log

# Enable I2C
echo -e "${YELLOW}[3/10] Configuring hardware interfaces...${NC}"
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi

# Enable camera
if ! grep -q "^camera_auto_detect=1" /boot/config.txt; then
    echo "camera_auto_detect=1" >> /boot/config.txt
fi

# Add user to necessary groups
usermod -a -G i2c,video,audio,dialout ${USER}

echo -e "${YELLOW}[4/10] Cloning Pulse repository...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists, stopping services first..."
    systemctl stop pulse.service 2>/dev/null || true
    systemctl stop pulse-hub.service 2>/dev/null || true
    systemctl stop pulse-dashboard.service 2>/dev/null || true
    systemctl stop pulse-health.service 2>/dev/null || true
    sleep 2
    echo "Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
# If this script is run from a local checkout (with expected files), use it; otherwise clone from GitHub
if [ -f "./requirements.txt" ] && [ -d "./services/systemd" ] && [ -d "./dashboard/ui" ]; then
    echo "Using local source to install."
    cp -a . "$INSTALL_DIR/"
else
    echo "Cloning repository from GitHub..."
    git clone https://github.com/Opentab1/thefinale2.git "$INSTALL_DIR"
fi

chown -R ${USER}:${USER} "$INSTALL_DIR"

echo -e "${YELLOW}[5/10] Setting up Python virtual environment...${NC}"
cd "$INSTALL_DIR"
PY_BIN="python3"
# Prefer Python 3.11 on Raspberry Pi due to wider wheel support (e.g., tflite-runtime)
if command -v python3.11 >/dev/null 2>&1; then
    PY_BIN="python3.11"
else
    # Try to install python3.11 if available in repo
    if apt-cache policy python3.11 | grep -q Candidate; then
        echo "Installing python3.11 for compatibility..."
        apt-get install -y python3.11 python3.11-venv || true
        if command -v python3.11 >/dev/null 2>&1; then
            PY_BIN="python3.11"
        fi
    fi
fi

sudo -u ${USER} ${PY_BIN} -m venv --system-site-packages venv
sudo -u ${USER} venv/bin/pip install --upgrade pip
# Install build dependencies first
sudo -u ${USER} venv/bin/pip install setuptools wheel

# Attempt to install OS-provided tflite runtime when available (Python <3.12)
if apt-cache policy python3-tflite-runtime | grep -q Candidate; then
    echo "Installing python3-tflite-runtime from apt..."
    apt-get install -y python3-tflite-runtime || true
fi

sudo -u ${USER} venv/bin/pip install -r requirements.txt

# Ensure Python can import local services package when running under systemd
if ! grep -q "^export PYTHONPATH=/opt/pulse" /home/${USER}/.profile 2>/dev/null; then
  echo 'export PYTHONPATH=/opt/pulse' >> /home/${USER}/.profile
fi

echo -e "${YELLOW}[6/10] Installing Node.js dashboard...${NC}"
cd "$INSTALL_DIR/dashboard/ui"
sudo -u ${USER} npm install
sudo -u ${USER} npm run build

echo -e "${YELLOW}[7/10] Creating directories and setting permissions...${NC}"
mkdir -p "$LOG_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/models"
mkdir -p "$INSTALL_DIR/music"
mkdir -p "$INSTALL_DIR/config"

chown -R ${USER}:${USER} "$LOG_DIR"
chown -R ${USER}:${USER} "$INSTALL_DIR"

# Populate default MobileNetSSD model if missing
if [ ! -f "$INSTALL_DIR/models/MobileNetSSD_deploy.prototxt" ]; then
  echo "Fetching MobileNetSSD prototxt..."
  sudo -u ${USER} wget -q -O "$INSTALL_DIR/models/MobileNetSSD_deploy.prototxt" \
    https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt || true
fi
# Caffemodel is large; attempt to fetch if available from mirror user controls
if [ ! -f "$INSTALL_DIR/models/MobileNetSSD_deploy.caffemodel" ]; then
  echo "Attempting to fetch MobileNetSSD caffemodel (optional)..."
  sudo -u ${USER} wget -q -O "$INSTALL_DIR/models/MobileNetSSD_deploy.caffemodel" \
    https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel || true
fi

# Set executable permissions for all startup scripts
chmod +x "$INSTALL_DIR/dashboard/kiosk/start.sh"
chmod +x "$INSTALL_DIR/install.sh"
chmod +x "$INSTALL_DIR/START_HERE.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/RUN_ME.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/start-pulse-anywhere" 2>/dev/null || true
chmod +x "$INSTALL_DIR/run_pulse_system.py" 2>/dev/null || true
chmod +x "$INSTALL_DIR/diagnose_sensors.py" 2>/dev/null || true

# Populate AI model files (MobileNet-SSD) if missing
SSD_PROTO="$INSTALL_DIR/models/MobileNetSSD_deploy.prototxt"
SSD_MODEL="$INSTALL_DIR/models/MobileNetSSD_deploy.caffemodel"
if [ ! -f "$SSD_PROTO" ]; then
  echo "Fetching MobileNet-SSD prototxt..."
  wget -nv -O "$SSD_PROTO" "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt" || true
fi
if [ ! -f "$SSD_MODEL" ]; then
  echo "Fetching MobileNet-SSD caffemodel (this may take a moment)..."
  wget -nv -O "$SSD_MODEL" "https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel" || true
fi

if [ -f "$SSD_PROTO" ] && [ -f "$SSD_MODEL" ]; then
  echo "MobileNet-SSD model present."
else
  echo "Warning: MobileNet-SSD files missing. People counter will fall back to HOG."
fi

echo -e "${YELLOW}[8/10] Installing systemd services...${NC}"

# Remove old service files completely
echo "Removing old service files..."
rm -f /etc/systemd/system/pulse-hub.service
rm -f /etc/systemd/system/pulse-dashboard.service

# Only copy the new services we want to use
echo "Installing new unified services..."
cp "$INSTALL_DIR/services/systemd/pulse.service" /etc/systemd/system/
cp "$INSTALL_DIR/services/systemd/pulse-firstboot.service" /etc/systemd/system/
cp "$INSTALL_DIR/services/systemd/pulse-health.service" /etc/systemd/system/

# Stop and disable old separate services if they exist
systemctl stop pulse-hub.service 2>/dev/null || true
systemctl stop pulse-dashboard.service 2>/dev/null || true
systemctl disable pulse-hub.service 2>/dev/null || true
systemctl disable pulse-dashboard.service 2>/dev/null || true

systemctl daemon-reload

# Enable the new unified service
systemctl enable pulse.service || true
systemctl enable pulse-firstboot.service || true
systemctl enable pulse-health.service || true

echo -e "${YELLOW}[9/10] Configuring auto-login and kiosk mode...${NC}"

# Configure auto-login
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${USER} --noclear %I \$TERM
EOF

# Configure autostart
mkdir -p /home/${USER}/.config/autostart
# Ensure LXDE session config directory exists before appending
mkdir -p /home/${USER}/.config/lxsession/LXDE-pi
cat > /home/${USER}/.config/autostart/pulse-dashboard.desktop << EOF
[Desktop Entry]
Type=Application
Name=Pulse Dashboard
Exec=/opt/pulse/dashboard/kiosk/start.sh
X-GNOME-Autostart-enabled=true
EOF

chown -R ${USER}:${USER} /home/${USER}/.config

# Disable screen sleep
cat >> /home/${USER}/.config/lxsession/LXDE-pi/autostart << EOF
@xset s off
@xset -dpms
@xset s noblank
EOF

echo -e "${YELLOW}[10/10] Downloading AI detection models...${NC}"

# Download person detection models
if [ -f "$INSTALL_DIR/services/sensors/download_models.sh" ]; then
    bash "$INSTALL_DIR/services/sensors/download_models.sh"
fi

echo -e "${YELLOW}[11/11] Running hardware detection...${NC}"

# Run hardware detection
cd "$INSTALL_DIR"
sudo -u ${USER} venv/bin/python3 << 'PYEOF'
import sys
sys.path.insert(0, '/opt/pulse')

from services.sensors.health_monitor import *
import json

monitor = HealthMonitor()
monitor.register_test("camera", test_camera)
monitor.register_test("mic", test_microphone)
monitor.register_test("bme280", test_bme280)
monitor.register_test("pan_tilt", test_pan_tilt)
monitor.register_test("ai_hat", test_ai_hat)
monitor.register_test("light_sensor", test_light_sensor)

results = monitor.test_all_modules()

print("\n" + "="*50)
print("Hardware Detection Results:")
print("="*50)
for module, status in results.items():
    symbol = "✓" if status else "✗"
    print(f"{symbol} {module}: {'OK' if status else 'Not Found'}")
print("="*50)

# Save report
with open('/var/log/pulse/hardware_report.txt', 'w') as f:
    json.dump(results, f, indent=2)
PYEOF

echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   Installation Complete!                                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BLUE}All Sensor Fixes Installed:${NC}"
echo "✓ BME280 sensor (temperature/humidity/pressure)"
echo "✓ AI people counter (camera detection)"
echo "✓ Song detection (microphone + Shazam)"
echo "✓ Light level reading"
echo "✓ Decibel reading"
echo "✓ Full terminal debugging with color-coded output"
echo ""
echo -e "${BLUE}Manual Startup Option:${NC}"
echo "If you want to test manually before rebooting:"
echo "  cd /opt/pulse"
echo "  ./START_HERE.sh"
echo ""
echo "This will show full debug output in the terminal!"
echo ""
echo -e "${BLUE}System Services:${NC}"
echo "The Pulse system runs as a unified service:"
echo "  sudo systemctl status pulse"
echo "  sudo systemctl restart pulse"
echo "  sudo journalctl -u pulse -f"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Review hardware detection: cat /var/log/pulse/hardware_report.txt"
echo "2. System will reboot and launch setup wizard"
echo "3. Complete wizard at http://localhost:9090"
echo "4. Dashboard will auto-launch at http://localhost:8080"
echo ""
echo -e "${YELLOW}Rebooting in 10 seconds... (Ctrl+C to cancel)${NC}"
sleep 10

# Start wizard now so kiosk can reach it even before reboot
echo "Starting setup wizard service..."
systemctl restart pulse-firstboot.service || true
systemctl restart pulse.service || true

reboot
