#!/bin/bash
# Install Simple Local Dashboard as System Service
# This replaces the complex dashboard with the simple sensor-reading dashboard

set -e

echo "🎵 Installing Simple Local Dashboard"
echo "====================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "⚠️  Please run as normal user (not root)"
   exit 1
fi

# Check if we're in the right location
if [ ! -f "/opt/pulse/rpi/simple_local_dashboard.py" ]; then
    echo "❌ Simple dashboard not found. Are you in /opt/pulse?"
    exit 1
fi

echo "📦 Step 1: Installing Python dependencies..."
pip3 install --user flask flask-cors 2>/dev/null || true

# Check if venv exists, if not create it
if [ ! -d "/opt/pulse/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv /opt/pulse/venv
    /opt/pulse/venv/bin/pip install flask flask-cors
fi

echo ""
echo "📦 Step 2: Stopping old services..."
sudo systemctl stop pulse.service 2>/dev/null || true
sudo systemctl stop pulse-hub.service 2>/dev/null || true
sudo systemctl stop pulse-dashboard.service 2>/dev/null || true

echo ""
echo "📝 Step 3: Installing new service file..."
sudo cp /opt/pulse/services/systemd/pulse.service /etc/systemd/system/
sudo systemctl daemon-reload

echo ""
echo "🚀 Step 4: Enabling and starting simple dashboard..."
sudo systemctl enable pulse.service
sudo systemctl start pulse.service

echo ""
echo "⏳ Waiting for dashboard to start (sensors need 30-40 seconds to warm up)..."
sleep 5

# Check status
if sudo systemctl is-active --quiet pulse.service; then
    echo "✅ Dashboard service is running!"
    echo ""
    echo "📊 Access your dashboard at:"
    echo "   http://localhost:8080"
    echo "   http://$(hostname -I | awk '{print $1}'):8080"
    echo ""
    echo "📝 View logs:"
    echo "   sudo journalctl -u pulse.service -f"
    echo ""
    echo "💡 Note: Light sensor takes 30-40 seconds to initialize"
    echo ""
else
    echo "❌ Dashboard failed to start. Check logs:"
    sudo journalctl -u pulse.service -n 50
    exit 1
fi

echo "✅ Installation complete!"
