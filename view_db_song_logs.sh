#!/bin/bash
# Single command to view all db_reader and song detection logs (historical + current)

echo "=== Systemd Journal Logs (pulse-hub) ==="
sudo journalctl -u pulse-hub --no-pager | grep -E "(Audio:|dB|Song|song|noise_db|mic_song|AudioMonitor|Shazam|🔊|🎵)" || echo "No matching logs found in journal"

echo ""
echo "=== File Log: /var/log/pulse/hub.log ==="
if [ -f /var/log/pulse/hub.log ]; then
    sudo grep -E "(Audio:|dB|Song|song|noise_db|mic_song|AudioMonitor|Shazam|🔊|🎵)" /var/log/pulse/hub.log || echo "No matching logs in hub.log"
else
    echo "hub.log not found"
fi

echo ""
echo "=== Error Log: /var/log/pulse/hub-error.log ==="
if [ -f /var/log/pulse/hub-error.log ]; then
    sudo grep -E "(Audio:|dB|Song|song|noise_db|mic_song|AudioMonitor|Shazam|🔊|🎵)" /var/log/pulse/hub-error.log || echo "No matching logs in hub-error.log"
else
    echo "hub-error.log not found"
fi
