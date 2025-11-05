#!/bin/bash
# Deploy 25-Minute Audio Failure Fix to Raspberry Pi

set -e

PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-partypi.local}"
WORKSPACE="/workspace"

echo "=================================="
echo "🚨 DEPLOYING 25-MIN AUDIO FIX"
echo "=================================="
echo ""
echo "Target: $PI_USER@$PI_HOST"
echo ""

# Check if we're on the Pi already
if [ -f /etc/rpi-issue ]; then
    echo "✅ Running on Raspberry Pi - installing locally"
    
    # Stop the service
    echo "Stopping pulse-hub service..."
    sudo systemctl stop pulse-hub || true
    
    # Backup the old file
    echo "Backing up old mic_song_detect.py..."
    sudo cp /opt/pulse/services/sensors/mic_song_detect.py \
            /opt/pulse/services/sensors/mic_song_detect.py.backup-$(date +%Y%m%d-%H%M%S) || true
    
    # Copy the new file
    echo "Installing fixed mic_song_detect.py..."
    sudo cp $WORKSPACE/services/sensors/mic_song_detect.py \
            /opt/pulse/services/sensors/mic_song_detect.py
    
    # Set correct permissions
    sudo chown pulse:pulse /opt/pulse/services/sensors/mic_song_detect.py
    sudo chmod 644 /opt/pulse/services/sensors/mic_song_detect.py
    
    # Restart the service
    echo "Starting pulse-hub service..."
    sudo systemctl start pulse-hub
    
    echo ""
    echo "=================================="
    echo "✅ FIX DEPLOYED SUCCESSFULLY"
    echo "=================================="
    echo ""
    echo "Monitor with:"
    echo "  sudo journalctl -u pulse-hub -f | grep -E '(Audio:|Song|heartbeat|stalled)'"
    
else
    echo "❌ Not on Raspberry Pi - use this script ON the Pi"
    echo ""
    echo "To deploy from your dev machine:"
    echo "  1. Push to git: git push origin $(git branch --show-current)"
    echo "  2. SSH to Pi: ssh $PI_USER@$PI_HOST"
    echo "  3. Pull changes: cd /opt/pulse && git pull"
    echo "  4. Restart service: sudo systemctl restart pulse-hub"
    echo ""
    echo "Or copy files directly:"
    echo "  scp services/sensors/mic_song_detect.py $PI_USER@$PI_HOST:/tmp/"
    echo "  ssh $PI_USER@$PI_HOST 'sudo cp /tmp/mic_song_detect.py /opt/pulse/services/sensors/ && sudo systemctl restart pulse-hub'"
fi
