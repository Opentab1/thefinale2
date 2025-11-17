#!/bin/bash
#
# Install Pulse 4-Service Architecture
# Simple, clean, fault-isolated services
#

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "          Pulse 4-Service Architecture Installer"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "This will install 4 independent services:"
echo "  1. Audio Service       (mic, dB, song detection)"
echo "  2. Camera Service      (people counting)"
echo "  3. Environmental Service (temp, humidity, light)"
echo "  4. Hub Service         (dashboard, database, automation)"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "ERROR: Do not run as root. Run as the 'pi' user."
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

echo "✓ Found Pulse at: $PULSE_DIR"
cd "$PULSE_DIR"

# Stop old services
echo ""
echo "Stopping old services..."
sudo systemctl stop pulse.service 2>/dev/null || true
sudo systemctl stop pulse-audio.service 2>/dev/null || true
sudo systemctl stop pulse-camera.service 2>/dev/null || true
sudo systemctl stop pulse-environmental.service 2>/dev/null || true
sudo systemctl stop pulse-hub-main.service 2>/dev/null || true
echo "✓ Old services stopped"

# Create data directory
echo ""
echo "Creating data directory..."
sudo mkdir -p /opt/pulse/data
sudo chown pi:pi /opt/pulse/data
echo "✓ Data directory ready: /opt/pulse/data"

# Install service files
echo ""
echo "Installing service files..."
sudo cp services/systemd/pulse-audio.service /etc/systemd/system/
sudo cp services/systemd/pulse-camera.service /etc/systemd/system/
sudo cp services/systemd/pulse-environmental.service /etc/systemd/system/
sudo cp services/systemd/pulse-hub-main.service /etc/systemd/system/
sudo cp services/systemd/pulse.service /etc/systemd/system/
echo "✓ Service files installed"

# Reload systemd
echo ""
echo "Reloading systemd..."
sudo systemctl daemon-reload
echo "✓ Systemd reloaded"

# Enable services
echo ""
echo "Enabling services..."
sudo systemctl enable pulse-audio.service
sudo systemctl enable pulse-camera.service
sudo systemctl enable pulse-environmental.service
sudo systemctl enable pulse-hub-main.service
sudo systemctl enable pulse.service
echo "✓ Services enabled"

# Start services
echo ""
echo "Starting services..."
sudo systemctl start pulse-audio.service
sleep 2
sudo systemctl start pulse-camera.service
sleep 2
sudo systemctl start pulse-environmental.service
sleep 2
sudo systemctl start pulse-hub-main.service
sleep 2

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "                  ✅ Installation Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Service Status:"
echo "  Audio:         sudo systemctl status pulse-audio"
echo "  Camera:        sudo systemctl status pulse-camera"
echo "  Environmental: sudo systemctl status pulse-environmental"
echo "  Hub:           sudo systemctl status pulse-hub-main"
echo ""
echo "📝 View Logs:"
echo "  Audio:         sudo journalctl -u pulse-audio -f"
echo "  Camera:        sudo journalctl -u pulse-camera -f"
echo "  Environmental: sudo journalctl -u pulse-environmental -f"
echo "  Hub:           sudo journalctl -u pulse-hub-main -f"
echo ""
echo "🔄 Control All Services:"
echo "  Start:   sudo systemctl start pulse.service"
echo "  Stop:    sudo systemctl stop pulse.service"
echo "  Restart: sudo systemctl restart pulse.service"
echo "  Status:  sudo systemctl status pulse.service"
echo ""
echo "✨ Benefits:"
echo "  ✅ Audio crash     → only audio restarts"
echo "  ✅ Camera crash    → only camera restarts"
echo "  ✅ Sensor crash    → only sensors restart"
echo "  ✅ Dashboard crash → only hub restarts"
echo "  ✅ Better fault isolation"
echo "  ✅ Independent service logs"
echo "  ✅ Simple and clean architecture"
echo ""
echo "🌐 Dashboard: http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "════════════════════════════════════════════════════════════════"
