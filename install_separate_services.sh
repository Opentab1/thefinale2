#!/bin/bash
#
# Install Pulse Separate Services
# This script installs the separate audio, camera, and hub services
#

set -e  # Exit on error

echo "=========================================="
echo "Pulse Separate Services Installer"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "ERROR: Do not run as root. Run as the 'pi' user with sudo when needed."
   exit 1
fi

# Detect installation directory
if [ -d "/opt/pulse" ]; then
    PULSE_DIR="/opt/pulse"
elif [ -d "$HOME/pulse" ]; then
    PULSE_DIR="$HOME/pulse"
else
    echo "ERROR: Cannot find Pulse installation!"
    exit 1
fi

echo "Found Pulse at: $PULSE_DIR"
cd "$PULSE_DIR"

echo ""
echo "Step 1: Stopping old service..."
sudo systemctl stop pulse.service || true

echo ""
echo "Step 2: Installing service files..."
sudo cp services/systemd/pulse-audio.service /etc/systemd/system/
sudo cp services/systemd/pulse-camera.service /etc/systemd/system/
sudo cp services/systemd/pulse-hub-main.service /etc/systemd/system/
sudo cp services/systemd/pulse.service /etc/systemd/system/

echo ""
echo "Step 3: Reloading systemd..."
sudo systemctl daemon-reload

echo ""
echo "Step 4: Enabling services..."
sudo systemctl enable pulse-audio.service
sudo systemctl enable pulse-camera.service
sudo systemctl enable pulse-hub-main.service
sudo systemctl enable pulse.service

echo ""
echo "Step 5: Starting services..."
sudo systemctl start pulse-audio.service
sudo systemctl start pulse-camera.service
sudo systemctl start pulse-hub-main.service

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "=========================================="
echo ""
echo "Service Status:"
echo "  Audio:  systemctl status pulse-audio"
echo "  Camera: systemctl status pulse-camera"
echo "  Hub:    systemctl status pulse-hub-main"
echo ""
echo "View Logs:"
echo "  Audio:  sudo journalctl -u pulse-audio -f"
echo "  Camera: sudo journalctl -u pulse-camera -f"
echo "  Hub:    sudo journalctl -u pulse-hub-main -f"
echo ""
echo "Control All Services:"
echo "  Start:   sudo systemctl start pulse.service"
echo "  Stop:    sudo systemctl stop pulse.service"
echo "  Restart: sudo systemctl restart pulse.service"
echo "  Status:  sudo systemctl status pulse.service"
echo ""
echo "Benefits:"
echo "  ✅ Camera crashes won't affect audio"
echo "  ✅ Audio crashes won't affect camera"
echo "  ✅ Each service restarts independently"
echo "  ✅ Better fault isolation"
echo ""

# Make the script executable
chmod +x "$PULSE_DIR/install_separate_services.sh"

echo "=========================================="
