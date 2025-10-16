#!/bin/bash
# Pulse Dashboard Kiosk Mode Startup Script

# Disable screen blanking
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after inactivity
unclutter -idle 0.1 &

# Wait for either wizard or dashboard to be available
WIZARD_MARKER="/opt/pulse/config/.wizard_complete"
MAX_WAIT=60
WAITED=0

# Check if wizard setup is complete
if [ -f "$WIZARD_MARKER" ]; then
  # Wizard complete - wait for dashboard to be ready
  URL="http://localhost:8080"
  echo "Wizard complete, waiting for dashboard at $URL..."
else
  # First boot - wait for wizard to be ready
  URL="http://localhost:9090"
  echo "First boot detected, waiting for wizard at $URL..."
fi

# Wait for the service to be available
while ! curl -s "$URL" > /dev/null; do
  if [ $WAITED -ge $MAX_WAIT ]; then
    echo "Timeout waiting for service at $URL"
    break
  fi
  sleep 2
  WAITED=$((WAITED + 2))
done

echo "Starting Chromium in kiosk mode at $URL"

# Start Chromium in kiosk mode (try new command first, fallback to old)
if command -v chromium &> /dev/null; then
  chromium \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --app="$URL"
else
  chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --app="$URL"
fi
