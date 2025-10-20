#!/bin/bash
# Deploy Pulse to Raspberry Pi
# Run this from the development environment

set -euo pipefail

echo "════════════════════════════════════════════════════════════"
echo "  PULSE DEPLOYMENT TO RASPBERRY PI"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check if we're in the right directory
if [ ! -d "services/hub" ]; then
    echo "❌ Error: Must run from Pulse root directory"
    echo "   Current directory: $(pwd)"
    exit 1
fi

echo "This script will help you deploy Pulse to your Raspberry Pi."
echo ""

# Option to create a tarball
echo "Creating deployment package..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="pulse_deployment_${TIMESTAMP}.tar.gz"

tar -czf "/tmp/${PACKAGE_NAME}" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='venv' \
    --exclude='node_modules' \
    services/ \
    dashboard/ \
    config/ \
    requirements.txt \
    START_HERE.sh \
    start_pulse.sh \
    start_pulse_dual.sh \
    run_pulse_system.py \
    diagnose_sensors.py \
    HOW_TO_START.md \
    FIXES_APPLIED.md \
    install.sh

echo "✓ Package created: /tmp/${PACKAGE_NAME}"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  DEPLOYMENT OPTIONS"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "OPTION 1: Copy via SCP"
echo "  On your computer, run:"
echo "  scp /tmp/${PACKAGE_NAME} pi@<pi-ip-address>:~/"
echo "  ssh pi@<pi-ip-address>"
echo "  tar -xzf ${PACKAGE_NAME}"
echo "  cd pulse"
echo "  ./START_HERE.sh"
echo ""
echo "OPTION 2: Copy via USB drive"
echo "  1. Copy /tmp/${PACKAGE_NAME} to a USB drive"
echo "  2. Insert USB drive into your Pi"
echo "  3. On Pi: cp /media/pi/USB/${PACKAGE_NAME} ~/"
echo "  4. On Pi: tar -xzf ${PACKAGE_NAME}"
echo "  5. On Pi: cd pulse && ./START_HERE.sh"
echo ""
echo "OPTION 3: Download link"
echo "  Upload /tmp/${PACKAGE_NAME} to a file sharing service"
echo "  Then download on your Pi with wget or curl"
echo ""
echo "════════════════════════════════════════════════════════════"
