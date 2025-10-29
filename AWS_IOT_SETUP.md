# AWS IoT Core Setup for Pulse Dashboard

## Overview
This guide configures Raspberry Pi 5 to stream sensor data to AWS IoT Core, which is then consumed by the Pulse Dashboard in real-time.

## Architecture
```
Raspberry Pi 5 → AWS IoT Core → Pulse Dashboard (Amplify)
                    (MQTT)        (WebSocket/MQTT)
```

## Setup Steps

### 1. Create IoT Thing in AWS Console

1. Go to AWS IoT Core console (us-east-2 region)
2. Navigate to **Manage → All devices → Things**
3. Click **Create things**
4. Select **Create single thing**
5. Name: `pulse-rpi-main` (or your location name)
6. Click **Next**

### 2. Generate Certificates

1. Choose **Auto-generate a new certificate**
2. Download all 4 files:
   - Device certificate (xxxxx-certificate.pem.crt)
   - Private key (xxxxx-private.pem.key)
   - Public key (xxxxx-public.pem.key)
   - Amazon Root CA 1
3. Click **Activate** certificate
4. Click **Attach a policy** (create one if needed)

### 3. Create IoT Policy

Create a policy named `PulseDevicePolicy` with this JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "iot:Connect",
        "iot:Publish",
        "iot:Subscribe",
        "iot:Receive"
      ],
      "Resource": [
        "arn:aws:iot:us-east-2:*:client/pulse-*",
        "arn:aws:iot:us-east-2:*:topic/pulse/*",
        "arn:aws:iot:us-east-2:*:topicfilter/pulse/*"
      ]
    }
  ]
}
```

### 4. Install Certificates on RPi

```bash
# On Raspberry Pi
sudo mkdir -p /etc/pulse/certs
sudo chmod 700 /etc/pulse/certs

# Copy certificates (use SCP or paste content)
sudo nano /etc/pulse/certs/device.pem.crt
sudo nano /etc/pulse/certs/private.pem.key
sudo nano /etc/pulse/certs/AmazonRootCA1.pem

# Set permissions
sudo chmod 600 /etc/pulse/certs/*
```

### 5. Install AWS IoT SDK on RPi

```bash
# Activate virtual environment
source /opt/pulse/.venv/bin/activate

# Install AWS IoT SDK
pip install awsiotsdk
```

### 6. Update IoT Configuration

Edit `rpi-iot-config.py` and update:

```python
IOT_CONFIG = {
    "endpoint": "xxxxx-ats.iot.us-east-2.amazonaws.com",  # From IoT Settings
    "region": "us-east-2",
    "client_id": "pulse-rpi-main",
    # ... rest stays same
}
```

To find your endpoint:
```bash
aws iot describe-endpoint --endpoint-type iot:Data-ATS --region us-east-2
```

### 7. Test Connection

```bash
# Run the IoT bridge
python3 rpi-iot-config.py
```

You should see:
```
=== Pulse RPi → AWS IoT Bridge ===
Region: us-east-2
Endpoint: xxxxx-ats.iot.us-east-2.amazonaws.com

✓ Connected to AWS IoT Core
Published to pulse/main-location/sensors: {...}
```

### 8. Create Systemd Service (Production)

Create `/etc/systemd/system/pulse-iot-bridge.service`:

```ini
[Unit]
Description=Pulse AWS IoT Bridge
After=network.target pulse-hub.service

[Service]
Type=simple
User=pulse
WorkingDirectory=/opt/pulse
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/pulse/.venv/bin/python3 /opt/pulse/rpi-iot-config.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pulse-iot-bridge
sudo systemctl start pulse-iot-bridge
sudo systemctl status pulse-iot-bridge
```

### 9. Configure Dashboard to Receive IoT Data

The dashboard is already configured to receive data from AWS IoT Core through the Cognito-authenticated connection.

**MQTT Topics:**
- `pulse/main-location/sensors` - Sensor readings
- `pulse/main-location/controls` - Control commands
- `pulse/main-location/status` - System status

### 10. Test End-to-End

1. Ensure RPi is publishing to IoT Core
2. Open Pulse Dashboard at https://dashboard.advizia.ai
3. Sign in with Cognito credentials
4. Navigate to Live Overview
5. You should see real-time data from your RPi

## MQTT Topic Structure

```
pulse/
  └── {location-name}/
      ├── sensors        # Sensor data (temperature, people count, etc.)
      ├── controls       # Control commands from dashboard
      └── status         # System health and status
```

## Data Format (Sensors Topic)

```json
{
  "timestamp": 1698765432000,
  "location": "Main Location",
  "people_count": 5,
  "temperature": 72,
  "humidity": 45,
  "decibels": 65,
  "light_level": 450,
  "song": {
    "title": "Example Song",
    "artist": "Example Artist",
    "detected": true
  },
  "integrations": {
    "nest_connected": true,
    "hue_connected": true,
    "spotify_connected": false
  },
  "camera_active": true
}
```

## Troubleshooting

**Cannot connect to IoT Core:**
- Verify certificates are in `/etc/pulse/certs/`
- Check certificate permissions (600)
- Verify IoT endpoint is correct
- Ensure IoT policy is attached to certificate

**No data in dashboard:**
- Check RPi is publishing (see logs)
- Verify topic names match
- Check Cognito authentication in dashboard
- Look at browser console for errors

**High latency:**
- Reduce publish frequency in `rpi-iot-config.py`
- Check network connection quality
- Consider using QoS 0 instead of 1

## Security Notes

- Certificates are device-specific and should never be shared
- Use certificate rotation (AWS recommends yearly)
- Monitor AWS IoT usage in CloudWatch
- Enable AWS IoT logging for security auditing

## Cost Optimization

AWS IoT Core pricing (as of 2024):
- Connectivity: $0.08 per million minutes
- Messaging: $1.00 per million messages

For 1 device publishing every 2 seconds:
- ~1.3M messages/month
- ~$1.30/month for messaging
- ~$0.08/month for connectivity
- **Total: ~$1.40/month**

## Next Steps

- [ ] Set up CloudWatch metrics for IoT messages
- [ ] Configure IoT Rules for data transformation
- [ ] Set up DynamoDB for historical data storage
- [ ] Create Lambda functions for data processing
- [ ] Add IoT Device Defender for security monitoring
