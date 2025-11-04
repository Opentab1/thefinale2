# AWS Integration Setup Guide for Raspberry Pi 5

This guide will help you connect your Pulse system to AWS **without modifying any files in your git repository**. All AWS-related files will be stored separately.

## Overview

The AWS sync service will:
- Read data from your existing SQLite database
- Send sensor data to AWS IoT Core
- Run independently without interfering with your current system
- Store AWS credentials securely (not in git)

## Step 1: Install AWS Dependencies

```bash
# Install paho-mqtt (MQTT client for AWS IoT)
pip3 install paho-mqtt

# Verify installation
python3 -c "import paho.mqtt.client as mqtt; print('MQTT client installed successfully')"
```

**Note:** We use MQTT instead of boto3 because AWS IoT Core uses certificate-based authentication for IoT devices, which works best with MQTT clients.

## Step 2: Create AWS Account & Set Up IoT Core

1. **Create AWS Account** (if you don't have one)
   - Go to https://aws.amazon.com/
   - Create a free tier account

2. **Create IoT Thing**
   - Go to AWS Console → IoT Core
   - Click "Manage" → "Things" → "Create things"
   - Choose "Create single thing"
   - Name it: `pulse-rpi5` (or your preferred name)
   - Save the Thing name

3. **Create IoT Policy**
   - Go to "Secure" → "Policies" → "Create policy"
   - Name: `PulseRPi5Policy`
   - Add these permissions:
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
           "Resource": "*"
         }
       ]
     }
     ```
   - Click "Create"

4. **Create Certificates**
   - Go to "Secure" → "Certificates" → "Create"
   - Choose "One-click certificate creation"
   - Download:
     - Certificate (pem)
     - Private key (pem)
     - Root CA certificate (Amazon Root CA 1)
   - **IMPORTANT**: Save these files securely - you'll need them!
   - Attach the policy you created to the certificate
   - Activate the certificate

5. **Get Your Endpoint**
   - Go to "Settings" → Note your "Device data endpoint"
   - Format: `xxxxx-ats.iot.us-east-1.amazonaws.com` (yours will be different)
   - Save this endpoint URL

## Step 3: Set Up Credentials on Your Raspberry Pi

```bash
# Create directory for AWS sync (outside git repo)
sudo mkdir -p /opt/pulse/aws_sync
sudo mkdir -p /opt/pulse/aws_sync/certs
sudo chown -R $USER:$USER /opt/pulse/aws_sync

# Copy certificate files to your Pi
# Use scp from your computer or copy-paste the contents:
# - certificate.pem
# - private-key.pem  
# - root-ca.pem (Amazon Root CA 1)

# Example: Using scp from your computer
# scp certificate.pem private-key.pem root-ca.pem pi@your-pi-ip:/opt/pulse/aws_sync/certs/

# Set secure permissions
chmod 600 /opt/pulse/aws_sync/certs/*.pem
chmod 644 /opt/pulse/aws_sync/certs/root-ca.pem
```

## Step 4: Create Environment Configuration File

```bash
# Create config file (NOT in git repo)
nano /opt/pulse/aws_sync/aws_config.env
```

Add this content (replace with YOUR values):

```bash
# AWS IoT Endpoint (from Step 2.5)
AWS_IOT_ENDPOINT=xxxxx-ats.iot.us-east-1.amazonaws.com

# Thing Name (from Step 2.2)
AWS_IOT_THING_NAME=pulse-rpi5

# Certificate paths
AWS_IOT_CERT_PATH=/opt/pulse/aws_sync/certs/certificate.pem
AWS_IOT_KEY_PATH=/opt/pulse/aws_sync/certs/private-key.pem
AWS_IOT_ROOT_CA_PATH=/opt/pulse/aws_sync/certs/root-ca.pem

# Sync interval (seconds) - how often to send data
AWS_SYNC_INTERVAL=60

# Database path (your existing Pulse database)
PULSE_DB_PATH=/opt/pulse/data/pulse.db
```

Save and exit (Ctrl+X, Y, Enter)

## Step 5: Verify Your Database Path

```bash
# Check where your Pulse database is located
ls -la /opt/pulse/data/pulse.db

# If it doesn't exist there, check alternative locations
find /workspace -name "pulse.db" 2>/dev/null
find ~ -name "pulse.db" 2>/dev/null
```

Update `PULSE_DB_PATH` in `aws_config.env` with the correct path.

## Step 6: Copy Sync Script to Working Directory

```bash
# Copy the sync script to /opt/pulse/aws_sync (outside git repo)
sudo mkdir -p /opt/pulse/aws_sync
sudo cp /workspace/aws_sync.py /opt/pulse/aws_sync/
sudo chmod +x /opt/pulse/aws_sync/aws_sync.py
sudo chown $USER:$USER /opt/pulse/aws_sync/aws_sync.py
```

## Step 7: Test the AWS Connection

```bash
# Test connection
cd /opt/pulse/aws_sync
python3 aws_sync.py --test
```

If successful, you should see:
- "✓ Database accessible"
- "✓ AWS IoT connection successful!"
- "✓ Test message published successfully"

## Step 8: Run the Sync Service

### Option A: Manual Start (for testing)

```bash
cd /opt/pulse/aws_sync
python3 aws_sync.py
```

### Option B: Run as Background Service

```bash
# Create systemd service
sudo nano /etc/systemd/system/pulse-aws-sync.service
```

Add this content:

```ini
[Unit]
Description=Pulse AWS Data Sync Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/pulse/aws_sync
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /opt/pulse/aws_sync/aws_sync.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pulse-aws-sync.service
sudo systemctl start pulse-aws-sync.service
sudo systemctl status pulse-aws-sync.service
```

## Step 9: Verify Data is Flowing

1. **Check logs**:
   ```bash
   tail -f /opt/pulse/aws_sync/sync.log
   ```

2. **Check AWS IoT Console**:
   - Go to AWS Console → IoT Core → Test
   - Subscribe to topic: `pulse/sensor-data`
   - You should see messages appearing every 60 seconds (or your configured interval)

3. **Verify in IoT Core**:
   - Go to "Monitor" → "MQTT test client"
   - Subscribe to: `pulse/sensor-data`
   - You should see JSON messages with sensor data

## Step 10: Monitor in AWS CloudWatch (Optional)

1. Go to AWS Console → CloudWatch
2. Create custom dashboard to visualize:
   - Temperature trends
   - Occupancy patterns
   - Environmental data

## Troubleshooting

### Connection Issues
```bash
# Check certificates are correct
ls -la /opt/pulse/aws_sync/certs/

# Test connectivity
ping $(grep AWS_IOT_ENDPOINT /opt/pulse/aws_sync/aws_config.env | cut -d'=' -f2)
```

### Database Access Issues
```bash
# Check database permissions
ls -la /opt/pulse/data/pulse.db

# If needed, fix permissions
sudo chmod 644 /opt/pulse/data/pulse.db
```

### View Logs
```bash
# Service logs
sudo journalctl -u pulse-aws-sync.service -f

# Sync script logs
tail -f /opt/pulse/aws_sync/sync.log
```

## Security Notes

✅ **DO NOT** commit these files to git:
- `/opt/pulse/aws_sync/certs/*.pem` (certificate files)
- `/opt/pulse/aws_sync/aws_config.env` (configuration file)
- `/opt/pulse/aws_sync/sync.log` (log file)

✅ The sync script (`aws_sync.py`) is in your workspace but it's safe - it reads credentials from external files

✅ Certificates are stored with restrictive permissions (600)

✅ All AWS-related files are stored in `/opt/pulse/aws_sync/` which is **outside** your git repository

## Data Format Sent to AWS

The sync service sends JSON messages like:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "device_id": "pulse-rpi5",
  "occupancy": 5,
  "temperature_f": 72.5,
  "humidity": 45.2,
  "light_level": 350,
  "noise_db": 65.3,
  "current_song": {
    "title": "Song Name",
    "artist": "Artist Name"
  }
}
```

## Next Steps (Optional)

- Set up AWS Timestream for long-term time-series storage
- Create Lambda functions to process data
- Set up CloudWatch alarms for thresholds
- Create DynamoDB tables for structured queries

---

**All done!** Your Pulse system is now sending data to AWS without modifying any git repository files.
