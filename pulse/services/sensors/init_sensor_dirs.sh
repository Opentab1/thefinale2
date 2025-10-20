#!/usr/bin/env bash
# Initialize sensor data directories and placeholder files

set -euo pipefail

SENSOR_DIR="/opt/pulse/data/sensors"
CAMERA_DIR="/opt/pulse/data/camera"

# Create directories
mkdir -p "$SENSOR_DIR"
mkdir -p "$CAMERA_DIR"

# Initialize placeholder files with default values
echo "0" > "$SENSOR_DIR/people_count.txt"
echo "0.0" > "$SENSOR_DIR/audio_level.txt"
echo "false" > "$SENSOR_DIR/camera_active.txt"

# BME280 default data
cat > "$SENSOR_DIR/bme280.json" <<EOF
{
  "temperature": 72.0,
  "humidity": 45.0,
  "pressure": 1013.25,
  "timestamp": "$(date -Iseconds)"
}
EOF

# Song detection default
cat > "$SENSOR_DIR/song.json" <<EOF
{
  "title": "No song detected",
  "artist": "",
  "detected": false,
  "timestamp": "$(date -Iseconds)"
}
EOF

# Set proper permissions
chown -R pi:pi "/opt/pulse/data" 2>/dev/null || true
chmod -R 755 "/opt/pulse/data" 2>/dev/null || true

echo "✓ Sensor data directories initialized at $SENSOR_DIR"
