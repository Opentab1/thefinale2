#!/usr/bin/env bash
set -euo pipefail

URL="http://localhost:8080"

# Wait for X to start
sleep 2

# Allow ESC to exit kiosk: use openbox and chromium flags
/usr/bin/chromium-browser   --noerrdialogs   --disable-infobars   --kiosk ""   --check-for-update-interval=31536000   --simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT'   --autoplay-policy=no-user-gesture-required   --overscroll-history-navigation=0   --test-type || true
