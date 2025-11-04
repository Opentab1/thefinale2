#!/bin/bash
# Quick setup script for AWS sync on Raspberry Pi
# Run this script to set up AWS sync service

set -e

echo "=========================================="
echo "Pulse AWS Sync Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please run as regular user (not root)"
   exit 1
fi

# Create directories
echo "Creating directories..."
sudo mkdir -p /opt/pulse/aws_sync/certs
sudo chown -R $USER:$USER /opt/pulse/aws_sync

# Copy sync script
echo "Copying sync script..."
if [ -f "/workspace/aws_sync.py" ]; then
    cp /workspace/aws_sync.py /opt/pulse/aws_sync/
    chmod +x /opt/pulse/aws_sync/aws_sync.py
    echo "✓ Sync script copied"
else
    echo "✗ aws_sync.py not found in /workspace"
    echo "  Please ensure you're running from the workspace directory"
    exit 1
fi

# Check for paho-mqtt
echo ""
echo "Checking dependencies..."
if python3 -c "import paho.mqtt.client" 2>/dev/null; then
    echo "✓ paho-mqtt installed"
else
    echo "✗ paho-mqtt not installed"
    echo "  Installing..."
    pip3 install paho-mqtt
    echo "✓ paho-mqtt installed"
fi

# Create config template if it doesn't exist
if [ ! -f "/opt/pulse/aws_sync/aws_config.env" ]; then
    echo ""
    echo "Creating config template..."
    cat > /opt/pulse/aws_sync/aws_config.env << 'EOF'
# AWS IoT Endpoint (from AWS Console → IoT Core → Settings)
AWS_IOT_ENDPOINT=xxxxx-ats.iot.us-east-1.amazonaws.com

# Thing Name (from AWS Console → IoT Core → Things)
AWS_IOT_THING_NAME=pulse-rpi5

# Certificate paths
AWS_IOT_CERT_PATH=/opt/pulse/aws_sync/certs/certificate.pem
AWS_IOT_KEY_PATH=/opt/pulse/aws_sync/certs/private-key.pem
AWS_IOT_ROOT_CA_PATH=/opt/pulse/aws_sync/certs/root-ca.pem

# Sync interval (seconds) - how often to send data
AWS_SYNC_INTERVAL=60

# Database path (your existing Pulse database)
PULSE_DB_PATH=/opt/pulse/data/pulse.db
EOF
    chmod 600 /opt/pulse/aws_sync/aws_config.env
    echo "✓ Config template created at /opt/pulse/aws_sync/aws_config.env"
    echo ""
    echo "⚠️  IMPORTANT: Edit /opt/pulse/aws_sync/aws_config.env with your AWS details"
fi

# Find database
echo ""
echo "Looking for Pulse database..."
if [ -f "/opt/pulse/data/pulse.db" ]; then
    echo "✓ Found database at /opt/pulse/data/pulse.db"
elif [ -f "/workspace/data/pulse.db" ]; then
    echo "✓ Found database at /workspace/data/pulse.db"
    echo "  Update PULSE_DB_PATH in aws_config.env to: /workspace/data/pulse.db"
else
    echo "✗ Database not found"
    echo "  Update PULSE_DB_PATH in aws_config.env with the correct path"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Set up AWS IoT Core (see AWS_SETUP_GUIDE.md)"
echo "2. Copy certificates to /opt/pulse/aws_sync/certs/"
echo "3. Edit /opt/pulse/aws_sync/aws_config.env with your AWS details"
echo "4. Test connection: python3 /opt/pulse/aws_sync/aws_sync.py --test"
echo "5. Start sync: python3 /opt/pulse/aws_sync/aws_sync.py"
echo ""
echo "For detailed instructions, see: AWS_SETUP_GUIDE.md"
