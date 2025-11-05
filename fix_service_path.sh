#!/bin/bash
# Fix the service Python path

echo "=== Finding correct Python path ==="

# Check common locations
if [ -f "/opt/pulse/.venv/bin/python3" ]; then
    PYTHON_PATH="/opt/pulse/.venv/bin/python3"
    echo "✅ Found: $PYTHON_PATH"
elif [ -f "/opt/pulse/venv/bin/python3" ]; then
    PYTHON_PATH="/opt/pulse/venv/bin/python3"
    echo "✅ Found: $PYTHON_PATH"
elif [ -f "/opt/pulse/.venv/bin/python" ]; then
    PYTHON_PATH="/opt/pulse/.venv/bin/python"
    echo "✅ Found: $PYTHON_PATH"
elif command -v python3 &> /dev/null; then
    PYTHON_PATH=$(which python3)
    echo "✅ Using system Python: $PYTHON_PATH"
else
    echo "❌ Python not found!"
    exit 1
fi

# Verify it works
if $PYTHON_PATH --version &> /dev/null; then
    echo "✅ Python works: $($PYTHON_PATH --version)"
else
    echo "❌ Python doesn't work!"
    exit 1
fi

echo ""
echo "=== Updating service file ==="

# Update service file
SERVICE_FILE="/etc/systemd/system/pulse-hub.service"

# Escape the path for sed
ESCAPED_PATH=$(echo "$PYTHON_PATH" | sed 's/[\/&]/\\&/g')

# Update ExecStart line
sed -i "s|ExecStart=.*python.*|ExecStart=$PYTHON_PATH -u /opt/pulse/services/hub/main.py|" "$SERVICE_FILE"

echo "✅ Service file updated"
echo ""
echo "=== New service file content ==="
grep -A 2 "ExecStart" "$SERVICE_FILE"

echo ""
echo "=== Reloading and restarting service ==="
systemctl daemon-reload
systemctl restart pulse-hub
sleep 5

echo ""
echo "=== Service Status ==="
systemctl status pulse-hub --no-pager | head -20

echo ""
echo "=== Recent Logs ==="
journalctl -u pulse-hub --since "5 seconds ago" --no-pager | tail -30 || echo "No logs yet"
