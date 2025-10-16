#!/bin/bash
# Pulse Dashboard Kiosk Mode Startup Script

# Disable screen blanking
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after inactivity
unclutter -idle 0.1 &

# Detect which service should be running and set the correct URL
WIZARD_COMPLETE="/opt/pulse/config/.wizard_complete"
PULSE_URL="http://localhost:8080"

if [ ! -f "$WIZARD_COMPLETE" ]; then
  # First boot - wizard is running
  PULSE_URL="http://localhost:9090"
  echo "First boot detected. Opening setup wizard at $PULSE_URL"
else
  # Wizard complete - dashboard is running
  echo "Setup complete. Opening dashboard at $PULSE_URL"
fi

# Wait for the service to be ready (max 60 seconds)
echo "Waiting for service to be ready..."
MAX_WAIT=60
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  if curl -s -o /dev/null -w "%{http_code}" "$PULSE_URL" | grep -q "200\|301\|302"; then
    echo "Service is ready!"
    break
  fi
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  echo "Waiting... ($ELAPSED/$MAX_WAIT seconds)"
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo "Warning: Service did not respond after $MAX_WAIT seconds. Attempting to open anyway..."
fi

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
  --app="$PULSE_URL"
