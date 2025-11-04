# AWS Integration Guide for Raspberry Pi 5

This guide walks you through adding AWS connectivity to your Pulse system **without modifying any git-tracked files**.

## Architecture Overview

The AWS integration runs as a **separate service** that:
- Reads sensor data from your existing SQLite database
- Sends data to AWS IoT Core (perfect for IoT sensor data)
- Runs completely independently of your git repo
- Uses environment variables for credentials (secure)

## Step-by-Step Instructions

### Step 1: Install AWS SDK and Dependencies

On your Raspberry Pi, run:

```bash
# Install boto3 (AWS SDK for Python)
pip3 install boto3 awsiotsdk

# Or if using system Python
sudo pip3 install boto3 awsiotsdk
```

### Step 2: Create AWS Integration Directory

Create a directory outside the git repo for AWS files:

```bash
sudo mkdir -p /opt/pulse/aws
sudo chown $USER:$USER /opt/pulse/aws
cd /opt/pulse/aws
```

### Step 3: Set Up AWS IoT Core

1. **Log into AWS Console** → IoT Core
2. **Create a Thing**:
   - Go to "Manage" → "Things" → "Create things"
   - Name it: `pulse-rpi5` (or your preferred name)
   - Note the Thing name

3. **Create a Policy**:
   - Go to "Secure" → "Policies" → "Create policy"
   - Name: `PulseSensorPolicy`
   - Policy document (JSON):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "iot:Publish",
           "iot:Connect"
         ],
         "Resource": "*"
       }
     ]
   }
   ```

4. **Create Certificates**:
   - Go to "Secure" → "Certificates" → "Create"
   - Choose "One-click certificate creation"
   - **Download all 3 files**:
     - Certificate (`.pem`)
     - Private key (`.pem.key`)
     - Root CA certificate (download Amazon Root CA 1)
   - **Attach the policy** to the certificate
   - **Activate** the certificate

5. **Copy certificates to Pi**:
   ```bash
   # Create certificates directory
   mkdir -p /opt/pulse/aws/certificates
   
   # Copy your downloaded files (use scp, sftp, or copy-paste)
   # Certificate: device-certificate.pem
   # Private key: device-private-key.pem.key
   # Root CA: AmazonRootCA1.pem (download from AWS)
   
   # Set proper permissions
   chmod 644 /opt/pulse/aws/certificates/*.pem
   chmod 600 /opt/pulse/aws/certificates/*.pem.key
   ```

### Step 4: Get Your AWS IoT Endpoint

In AWS Console → IoT Core → Settings, copy your **Device data endpoint** (looks like: `xxxxx-ats.iot.us-east-1.amazonaws.com`)

### Step 5: Create Configuration File

Create `/opt/pulse/aws/config.json`:

```bash
nano /opt/pulse/aws/config.json
```

Paste this (replace with your values):

```json
{
  "endpoint": "YOUR_IOT_ENDPOINT.ats.iot.us-east-1.amazonaws.com",
  "thing_name": "pulse-rpi5",
  "certificate_path": "/opt/pulse/aws/certificates/device-certificate.pem",
  "private_key_path": "/opt/pulse/aws/certificates/device-private-key.pem.key",
  "root_ca_path": "/opt/pulse/aws/certificates/AmazonRootCA1.pem",
  "upload_interval_seconds": 30,
  "topic": "pulse/sensors/data"
}
```

### Step 6: Create the AWS Uploader Script

The script will be created at `/opt/pulse/aws/aws_uploader.py` - see the file created in this repo.

### Step 7: Test the Integration

Run manually first to test:

```bash
cd /opt/pulse/aws
python3 aws_uploader.py
```

You should see:
```
✓ Connected to AWS IoT Core
✓ Reading sensor data...
✓ Sent data to AWS (message ID: ...)
```

### Step 8: Create Systemd Service (Optional)

To run automatically on boot:

```bash
sudo nano /etc/systemd/system/pulse-aws.service
```

Paste:
```ini
[Unit]
Description=Pulse AWS IoT Uploader
After=network.target pulse-hub.service
Requires=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/pulse/aws
ExecStart=/usr/bin/python3 /opt/pulse/aws/aws_uploader.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pulse-aws.service
sudo systemctl start pulse-aws.service

# Check status
sudo systemctl status pulse-aws.service

# View logs
sudo journalctl -u pulse-aws.service -f
```

### Step 9: Verify Data in AWS

1. Go to AWS Console → IoT Core → Test
2. Subscribe to topic: `pulse/sensors/data`
3. You should see sensor data messages appearing

## Data Format

The script sends JSON data in this format:

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "device_id": "pulse-rpi5",
  "sensors": {
    "occupancy": 5,
    "temperature_f": 72.5,
    "humidity": 45.2,
    "light_level": 350,
    "noise_db": 55.3,
    "current_song": {
      "title": "Song Name",
      "artist": "Artist Name"
    }
  }
}
```

## Troubleshooting

### Connection Issues
- Check certificate paths and permissions
- Verify IoT endpoint is correct
- Check internet connectivity: `ping 8.8.8.8`

### Permission Errors
- Ensure certificates are readable: `ls -la /opt/pulse/aws/certificates/`
- Check database path permissions

### No Data Appearing
- Verify Pulse Hub is running and writing to database
- Check database path in config matches your installation
- View logs: `sudo journalctl -u pulse-aws.service -n 50`

## Security Notes

- Certificates are stored in `/opt/pulse/aws/certificates/` with restricted permissions
- Never commit certificates to git
- Rotate certificates periodically (IoT Core → Certificates → Actions → Deactivate/Delete)

## Next Steps (Optional)

Once data is flowing, you can:
- Set up AWS IoT Rules to route data to:
  - **DynamoDB** for long-term storage
  - **S3** for data lake
  - **Kinesis** for real-time analytics
  - **CloudWatch** for monitoring
- Create dashboards in AWS IoT SiteWise or Grafana
- Set up alarms for temperature/humidity thresholds
