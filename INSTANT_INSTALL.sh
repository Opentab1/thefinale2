#!/bin/bash
# Pulse - INSTANT One-Command Installation
# NO wizard, NO reboot, NO configuration needed
# Just run and the dashboard appears immediately

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════╗"
echo "║    Pulse - INSTANT Installation      ║"
echo "║    Dashboard ready in 2 minutes!     ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run with sudo${NC}"
    exit 1
fi

INSTALL_DIR="/opt/pulse"
USER="pi"

echo -e "${YELLOW}[1/6] Installing system dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq \
    python3-full \
    python3-pip \
    python3-venv \
    python3-picamera2 \
    i2c-tools \
    python3-rpi.gpio \
    python3-dev \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    alsa-utils \
    sqlite3 \
    git

# Enable I2C
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
fi

# Add user to necessary groups
usermod -a -G i2c,video,audio ${USER} 2>/dev/null || true

echo -e "${YELLOW}[2/6] Setting up Pulse directory...${NC}"
# Stop any existing services
systemctl stop pulse.service 2>/dev/null || true
systemctl stop pulse-firstboot.service 2>/dev/null || true
systemctl disable pulse-firstboot.service 2>/dev/null || true

# Remove old installation
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"

# Copy files if running from local checkout, otherwise clone
if [ -f "./requirements.txt" ] && [ -f "./rpi/simple_local_dashboard.py" ]; then
    echo "Installing from local source..."
    cp -a . "$INSTALL_DIR/"
else
    echo "Cloning from GitHub..."
    git clone https://github.com/Opentab1/thefinale2.git "$INSTALL_DIR"
fi

chown -R ${USER}:${USER} "$INSTALL_DIR"

echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"
cd "$INSTALL_DIR"

# Create virtual environment
sudo -u ${USER} python3 -m venv --system-site-packages venv
sudo -u ${USER} venv/bin/pip install --quiet --upgrade pip

# Install only what we need for the simple dashboard
sudo -u ${USER} venv/bin/pip install --quiet \
    flask \
    flask-cors \
    pyyaml \
    smbus2 \
    pyaudio \
    numpy \
    requests

echo -e "${YELLOW}[4/6] Creating default configuration...${NC}"
# Create necessary directories
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/data"
mkdir -p /var/log/pulse

chown -R ${USER}:${USER} "$INSTALL_DIR"
chown -R ${USER}:${USER} /var/log/pulse

# Create minimal default config (no wizard needed)
cat > "$INSTALL_DIR/config/config.yaml" << 'EOF'
venue:
  name: "Pulse Venue"
  timezone: "America/Chicago"

modules:
  camera: true
  mic: true
  bme280: true
  light_sensor: true
  ai_hat: false
  pan_tilt: false

wizard:
  completed: true
EOF

# Mark wizard as complete so it never runs
touch "$INSTALL_DIR/config/.wizard_complete"

echo -e "${YELLOW}[5/6] Installing dashboard service...${NC}"

# Create systemd service for simple dashboard
cat > /etc/systemd/system/pulse.service << EOF
[Unit]
Description=Pulse Simple Dashboard
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
Environment="PYTHONPATH=${INSTALL_DIR}"
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/rpi/simple_local_dashboard.py
Restart=always
RestartSec=5

# Logging
StandardOutput=append:/var/log/pulse/dashboard.log
StandardError=append:/var/log/pulse/dashboard-error.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable pulse.service

echo -e "${YELLOW}[6/6] Starting dashboard...${NC}"
systemctl start pulse.service

# Wait a moment for service to start
sleep 3

# Check if service started successfully
if systemctl is-active --quiet pulse.service; then
    IP=$(hostname -I | awk '{print $1}')
    
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║          ✅ INSTALLATION COMPLETE!                    ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${CYAN}🎵 Your Pulse Dashboard is LIVE!${NC}"
    echo ""
    echo -e "${GREEN}Access your dashboard at:${NC}"
    echo -e "  ${BLUE}http://${IP}:8080${NC}"
    echo -e "  ${BLUE}http://localhost:8080${NC}"
    echo ""
    echo -e "${YELLOW}📊 What you'll see:${NC}"
    echo "  🌡️  Temperature (from BME280 sensor)"
    echo "  💧 Humidity (from BME280 sensor)"
    echo "  🔊 Sound Level (from microphone)"
    echo "  💡 Light Level (camera-based)"
    echo "  🎵 Current Song (from database)"
    echo "  😊 Comfort Score (calculated)"
    echo ""
    echo -e "${YELLOW}⏳ Note:${NC} Sensors need 30-40 seconds to warm up"
    echo ""
    echo -e "${GREEN}✅ Dashboard auto-starts on boot${NC}"
    echo -e "${GREEN}✅ Auto-restarts if it crashes${NC}"
    echo -e "${GREEN}✅ No configuration needed${NC}"
    echo ""
    echo -e "${CYAN}Useful commands:${NC}"
    echo "  Check status:  ${BLUE}sudo systemctl status pulse${NC}"
    echo "  View logs:     ${BLUE}sudo journalctl -u pulse -f${NC}"
    echo "  Restart:       ${BLUE}sudo systemctl restart pulse${NC}"
    echo ""
    echo -e "${GREEN}🚀 READY TO USE - Open the URL above!${NC}"
    echo ""
else
    echo -e "${RED}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║          ❌ SERVICE FAILED TO START                   ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "Check logs with:"
    echo "  sudo journalctl -u pulse -n 50"
    exit 1
fi
