#!/bin/bash
set -euo pipefail

# Pulse Dashboard Kiosk Mode Startup Script (resilient)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Disable screen blanking if X11 is available
if [[ -n "${DISPLAY:-}" ]] && command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset s noblank || true
  xset -dpms || true
fi

# Hide mouse cursor after inactivity on X11
if command -v unclutter >/dev/null 2>&1 && [[ "${XDG_SESSION_TYPE:-x11}" != "wayland" ]]; then
  unclutter -idle 0.5 -root >/dev/null 2>&1 &
fi

# Start a lightweight local HTTP server to host the offline fallback page
FALLBACK_PORT=9977
PID_FILE="/tmp/pulse-kiosk-http.pid"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
    kill "$old_pid" >/dev/null 2>&1 || true
    sleep 0.2 || true
  fi
fi

python3 -m http.server "$FALLBACK_PORT" --directory "$SCRIPT_DIR" >/dev/null 2>&1 &
echo $! > "$PID_FILE"
trap 'kill "$(cat "$PID_FILE" 2>/dev/null)" >/dev/null 2>&1 || true' EXIT

# Detect Chromium binary
CHROMIUM_BIN="$(command -v chromium-browser || true)"
if [[ -z "$CHROMIUM_BIN" ]]; then
  CHROMIUM_BIN="$(command -v chromium || true)"
fi
if [[ -z "$CHROMIUM_BIN" ]]; then
  echo "Chromium is not installed. Please install the 'chromium' package." >&2
  exit 1
fi

# Wayland/X11 handling
OZONE_FLAG="--ozone-platform-hint=auto"
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
  OZONE_FLAG="--ozone-platform=wayland"
else
  OZONE_FLAG="--ozone-platform=x11"
fi

# Common Chromium flags for kiosk stability (no fullscreen kiosk to allow normal tabs)
COMMON_FLAGS=(
  --noerrdialogs
  --disable-infobars
  --no-first-run
  --disable-session-crashed-bubble
  --disable-features=TranslateUI
  --disable-pinch
  --overscroll-history-navigation=0
  --password-store=basic
  --use-mock-keychain
  --check-for-update-interval=31536000
  --simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT'
)

# Decide preferred target (wizard vs dashboard) based on setup marker
PREFERRED="wizard"
WIZARD_COMPLETE="/opt/pulse/config/.wizard_complete"
if [[ -f "$WIZARD_COMPLETE" ]]; then
  PREFERRED="dashboard"
fi

# Build target URL with preference hint for the fallback page script
TARGET_URL="http://localhost:${FALLBACK_PORT}/index.html?preferred=${PREFERRED}"

# Launch in app mode focused on our page, but still allows Alt+Tab to terminal
exec "$CHROMIUM_BIN" "${COMMON_FLAGS[@]}" "$OZONE_FLAG" \
  --app="$TARGET_URL" \
  --window-size=1280,800 \
  --force-device-scale-factor=1.0
