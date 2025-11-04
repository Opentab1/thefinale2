#!/bin/bash
# Setup script for AWS integration on Raspberry Pi
# Run this on your Raspberry Pi 5 (NOT in the git repo)

set -e

echo "=========================================="
echo "Pulse AWS Integration Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please do NOT run this script as root/sudo"
   echo "It will use sudo when needed for specific operations"
   exit 1
fi

# Create AWS directory
echo "Step 1: Creating AWS integration directory..."
sudo mkdir -p /opt/pulse/aws/certificates
sudo chown $USER:$USER /opt/pulse/aws
sudo chown $USER:$USER /opt/pulse/aws/certificates
echo "✓ Created /opt/pulse/aws/"

# Install Python dependencies
echo ""
echo "Step 2: Installing AWS SDK..."
pip3 install --user boto3 awsiotsdk || sudo pip3 install boto3 awsiotsdk
echo "✓ AWS SDK installed"

# Create config template
echo ""
echo "Step 3: Creating config template..."
cat > /opt/pulse/aws/config.json << 'EOF'
{
  "endpoint": "YOUR_IOT_ENDPOINT.ats.iot.us-east-1.amazonaws.com",
  "thing_name": "pulse-rpi5",
  "certificate_path": "/opt/pulse/aws/certificates/device-certificate.pem",
  "private_key_path": "/opt/pulse/aws/certificates/device-private-key.pem.key",
  "root_ca_path": "/opt/pulse/aws/certificates/AmazonRootCA1.pem",
  "upload_interval_seconds": 30,
  "topic": "pulse/sensors/data"
}
EOF
echo "✓ Config template created at /opt/pulse/aws/config.json"
echo "  ⚠️  You MUST edit this file with your AWS IoT endpoint!"

# Copy the uploader script
echo ""
echo "Step 4: Copying AWS uploader script..."
# Note: This assumes you've copied aws_uploader.py to /opt/pulse/aws/
# If not, the user will need to copy it manually
if [ -f "./aws_uploader.py" ]; then
    cp ./aws_uploader.py /opt/pulse/aws/aws_uploader.py
    chmod +x /opt/pulse/aws/aws_uploader.py
    echo "✓ Uploader script copied"
else
    echo "⚠️  aws_uploader.py not found in current directory"
    echo "   Please copy aws_uploader.py to /opt/pulse/aws/ manually"
fi

# Create log directory
echo ""
echo "Step 5: Creating log directory..."
sudo mkdir -p /var/log/pulse
sudo chown $USER:$USER /var/log/pulse
echo "✓ Log directory created"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Set up AWS IoT Core (see AWS_INTEGRATION_GUIDE.md)"
echo "2. Download certificates to /opt/pulse/aws/certificates/"
echo "3. Edit /opt/pulse/aws/config.json with your endpoint"
echo "4. Test: python3 /opt/pulse/aws/aws_uploader.py"
echo ""
echo "For detailed instructions, see: AWS_INTEGRATION_GUIDE.md"
echo ""
