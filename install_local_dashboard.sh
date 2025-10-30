#!/bin/bash
set -e

echo "🚀 Installing Pulse Local Dashboard..."

# Install Flask if needed
pip3 install flask 2>/dev/null || sudo pip3 install flask

# Make script executable
chmod +x rpi/local_dashboard.py

# Install systemd service
sudo cp rpi/pulse-local-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pulse-local-dashboard.service
sudo systemctl restart pulse-local-dashboard.service

echo ""
echo "✅ Local Dashboard installed!"
echo ""
echo "📍 Access at: http://localhost:8080"
echo "🔄 Auto-starts on boot"
echo "📊 Status: sudo systemctl status pulse-local-dashboard"
echo ""
echo "Opening browser in 3 seconds..."
sleep 3

# Try to open browser (works on RPi with desktop)
if command -v chromium-browser &> /dev/null; then
    chromium-browser --kiosk http://localhost:8080 &
elif command -v firefox &> /dev/null; then
    firefox http://localhost:8080 &
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8080 &
else
    echo "⚠️  No browser found. Open http://localhost:8080 manually."
fi

echo "Done! 🎉"
