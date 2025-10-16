#!/bin/bash
# Pulse Dashboard Kiosk Mode Startup Script

# Disable screen blanking
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after inactivity
unclutter -idle 0.1 &

# Start Chromium in kiosk mode (detect binary name)
CHROMIUM_BIN="$(command -v chromium-browser || true)"
if [ -z "$CHROMIUM_BIN" ]; then
  CHROMIUM_BIN="$(command -v chromium || true)"
fi
if [ -z "$CHROMIUM_BIN" ]; then
  echo "Chromium is not installed. Please install 'chromium'." >&2
  exit 1
fi

"$CHROMIUM_BIN" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --app=http://localhost:8080
