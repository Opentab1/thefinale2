#!/bin/bash
# Apply DB Reader and Song Detection fixes after fresh install
# Run this after installing Pulse on a fresh SD card

cd /opt/pulse

echo "Applying latest fixes from GitHub..."
git fetch origin
git checkout cursor/diagnose-and-fix-system-failures-3377
git pull origin cursor/diagnose-and-fix-system-failures-3377

echo "✓ Fixes applied! Restarting services..."
sudo systemctl restart pulse-hub.service pulse-dashboard.service 2>/dev/null || echo "Services not running as systemd (OK if running manually)"

echo ""
echo "✓ Done! Your fixes are now active."
echo "Run: ./START_HERE.sh or restart your services"
