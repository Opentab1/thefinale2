#!/bin/bash
# Rebuild Pulse Dashboard UI
# This script rebuilds the React dashboard after fixing configuration issues

set -e

DASHBOARD_DIR="/opt/pulse/dashboard/ui"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 Pulse Dashboard Rebuild Script"
echo "=================================="
echo ""

# Check if we're in the right location
if [ ! -d "$DASHBOARD_DIR" ]; then
    echo "❌ Dashboard directory not found at $DASHBOARD_DIR"
    echo "Are you running this on the Pi with Pulse installed?"
    exit 1
fi

cd "$DASHBOARD_DIR"

echo "📦 Installing dependencies..."
if command -v npm &> /dev/null; then
    npm install
elif command -v yarn &> /dev/null; then
    yarn install
else
    echo "❌ Neither npm nor yarn found. Please install Node.js."
    exit 1
fi

echo ""
echo "🏗️  Building dashboard..."
npm run build

echo ""
echo "✅ Dashboard rebuilt successfully!"
echo ""
echo "🔄 Restarting dashboard service..."
sudo systemctl restart pulse-hub 2>/dev/null || echo "⚠️  Could not restart service. You may need to restart manually."

echo ""
echo "✅ Done! Try accessing your dashboard at:"
echo "   http://$(hostname -I | awk '{print $1}'):8080"
echo ""
