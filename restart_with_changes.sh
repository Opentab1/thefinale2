#!/bin/bash
# Quick restart script with latest changes

echo "=========================================="
echo "Restarting Pulse with Latest Changes"
echo "=========================================="

cd /opt/pulse

echo "[1/3] Pulling latest changes from GitHub..."
git pull origin main

echo ""
echo "[2/3] Restarting Pulse service..."
sudo systemctl restart pulse.service

echo ""
echo "[3/3] Checking status..."
sleep 2
sudo systemctl status pulse.service --no-pager -l | head -20

echo ""
echo "=========================================="
echo "✅ Restart Complete!"
echo "=========================================="
echo ""
echo "View logs: sudo journalctl -u pulse.service -f"
echo "Check dB/Song: python3 /opt/pulse/diagnose_db_song_detector.py"
echo ""
