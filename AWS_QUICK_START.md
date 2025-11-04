# AWS Integration - Quick Start

## On Your Raspberry Pi 5

### 1. Copy Files to Pi (Outside Git Repo)

```bash
# Create AWS directory
sudo mkdir -p /opt/pulse/aws/certificates
sudo chown $USER:$USER /opt/pulse/aws /opt/pulse/aws/certificates

# Copy the uploader script (from your git repo workspace)
cp /path/to/workspace/aws_uploader.py /opt/pulse/aws/
chmod +x /opt/pulse/aws/aws_uploader.py

# Copy config template
cp /path/to/workspace/aws_config_template.json /opt/pulse/aws/config.json
```

### 2. Install Dependencies

```bash
pip3 install --user awsiotsdk boto3
# OR
sudo pip3 install awsiotsdk boto3
```

### 3. Set Up AWS IoT Core

1. Go to AWS Console → IoT Core
2. Create a Thing: `pulse-rpi5`
3. Create a Policy with publish/connect permissions
4. Create and download certificates (3 files)
5. Copy certificates to `/opt/pulse/aws/certificates/`
6. Get your IoT endpoint from Settings

### 4. Configure

Edit `/opt/pulse/aws/config.json`:
- Replace `YOUR_IOT_ENDPOINT` with your actual endpoint
- Update certificate filenames if different
- Adjust `upload_interval_seconds` if needed

### 5. Test

```bash
cd /opt/pulse/aws
python3 aws_uploader.py
```

You should see connection messages and data uploads.

### 6. Run as Service (Optional)

```bash
sudo nano /etc/systemd/system/pulse-aws.service
```

Paste:
```ini
[Unit]
Description=Pulse AWS IoT Uploader
After=network.target pulse-hub.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/pulse/aws
ExecStart=/usr/bin/python3 /opt/pulse/aws/aws_uploader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pulse-aws.service
sudo systemctl start pulse-aws.service
sudo journalctl -u pulse-aws.service -f
```

## Verify Data in AWS

AWS Console → IoT Core → Test → Subscribe to `pulse/sensors/data`

## Files Created (NOT in Git Repo)

- `/opt/pulse/aws/aws_uploader.py` - Main uploader script
- `/opt/pulse/aws/config.json` - Configuration
- `/opt/pulse/aws/certificates/*.pem` - AWS certificates
- `/var/log/pulse/aws_uploader.log` - Logs

## Important Notes

✅ **Nothing touches your git repo** - all files are in `/opt/pulse/aws/`  
✅ **Reads from existing database** - no changes to your Pulse code  
✅ **Runs independently** - can start/stop without affecting Pulse Hub  
✅ **Secure** - uses AWS IoT certificates, not git-committed credentials

For detailed instructions, see `AWS_INTEGRATION_GUIDE.md`
