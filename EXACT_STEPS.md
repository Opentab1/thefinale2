# EXACT STEPS - Copy and Paste Each Command

## STEP 1: Find where you are
```bash
pwd
```
Note the path - you'll need it.

## STEP 2: Create AWS directory
```bash
sudo mkdir -p /opt/pulse/aws/certificates
sudo chown $USER:$USER /opt/pulse/aws
sudo chown $USER:$USER /opt/pulse/aws/certificates
ls -la /opt/pulse/aws/
```

## STEP 3: Install AWS SDK
```bash
pip3 install --user awsiotsdk boto3
```
If that fails, try:
```bash
sudo pip3 install awsiotsdk boto3
```

## STEP 4: Find and copy the uploader script
If you're in the workspace directory, run:
```bash
ls -la aws_uploader.py
```
If you see it, copy it:
```bash
cp aws_uploader.py /opt/pulse/aws/aws_uploader.py
chmod +x /opt/pulse/aws/aws_uploader.py
ls -la /opt/pulse/aws/aws_uploader.py
```

If you're NOT in the workspace, find it first:
```bash
find ~ -name "aws_uploader.py" 2>/dev/null
```
Then copy it from wherever it is:
```bash
cp /path/to/aws_uploader.py /opt/pulse/aws/aws_uploader.py
chmod +x /opt/pulse/aws/aws_uploader.py
```

## STEP 5: Create config file
```bash
cat > /opt/pulse/aws/config.json << 'EOF'
{
  "endpoint": "REPLACE_WITH_YOUR_ENDPOINT",
  "thing_name": "pulse-rpi5",
  "certificate_path": "/opt/pulse/aws/certificates/device-certificate.pem",
  "private_key_path": "/opt/pulse/aws/certificates/device-private-key.pem.key",
  "root_ca_path": "/opt/pulse/aws/certificates/AmazonRootCA1.pem",
  "upload_interval_seconds": 30,
  "topic": "pulse/sensors/data"
}
EOF
cat /opt/pulse/aws/config.json
```

## STEP 6: Download Amazon Root CA (easier than copy-paste)
```bash
cd /opt/pulse/aws/certificates
wget https://www.amazontrust.com/repository/AmazonRootCA1.pem
ls -la AmazonRootCA1.pem
```

## STEP 7: Set up AWS IoT Core (in browser)
Go to: https://console.aws.amazon.com/iot/

1. Click "Manage" → "Things" → "Create things"
2. Click "Create single thing"
3. Name it: `pulse-rpi5`
4. Click "Next" → "Create thing"

## STEP 8: Create Policy
1. Click "Secure" → "Policies" → "Create policy"
2. Name: `PulseSensorPolicy`
3. Click "JSON" tab, paste this:
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
4. Click "Create"

## STEP 9: Create Certificates
1. Click "Secure" → "Certificates" → "Create"
2. Click "One-click certificate creation"
3. Download the 3 files:
   - Certificate (click download) → save to Pi as `device-certificate.pem`
   - Private key (click download) → save to Pi as `device-private-key.pem.key`
4. Click "Activate"
5. Click "Attach policy" → select `PulseSensorPolicy` → "Attach"
6. Click "Attach thing" → select `pulse-rpi5` → "Attach"

## STEP 10: Upload certificates to Pi
Use one of these methods:

**Method A: Use scp from your computer**
```bash
# On your COMPUTER (not Pi), run:
scp device-certificate.pem pi@YOUR_PI_IP:/opt/pulse/aws/certificates/
scp device-private-key.pem.key pi@YOUR_PI_IP:/opt/pulse/aws/certificates/
```

**Method B: Copy-paste on Pi**
```bash
# On your PI, create the certificate file:
nano /opt/pulse/aws/certificates/device-certificate.pem
# Paste the certificate content (starts with -----BEGIN CERTIFICATE-----)
# Ctrl+X, Y, Enter to save

# Create the private key file:
nano /opt/pulse/aws/certificates/device-private-key.pem.key
# Paste the private key content (starts with -----BEGIN RSA PRIVATE KEY-----)
# Ctrl+X, Y, Enter to save
```

## STEP 11: Set permissions
```bash
chmod 644 /opt/pulse/aws/certificates/*.pem
chmod 600 /opt/pulse/aws/certificates/*.pem.key
ls -la /opt/pulse/aws/certificates/
```

## STEP 12: Get your IoT endpoint
In AWS Console:
1. Click "Settings" (bottom left)
2. Copy the "Device data endpoint" (looks like: `a1b2c3d4e5f6g7-ats.iot.us-east-1.amazonaws.com`)

## STEP 13: Update config with endpoint
```bash
nano /opt/pulse/aws/config.json
```
Replace `REPLACE_WITH_YOUR_ENDPOINT` with your actual endpoint (keep the `.ats.iot.us-east-1.amazonaws.com` part)
Save: Ctrl+X, Y, Enter

## STEP 14: Test it!
```bash
cd /opt/pulse/aws
python3 aws_uploader.py
```

You should see:
```
✓ Connected to AWS IoT Core
✓ Reading sensor data...
✓ Uploaded sensor data...
```

Press Ctrl+C to stop.

## STEP 15: Verify data in AWS
1. AWS Console → IoT Core → "Test" (left menu)
2. Subscribe to topic: `pulse/sensors/data`
3. You should see messages appearing!

## STEP 16: Set up as service (runs automatically)
```bash
sudo nano /etc/systemd/system/pulse-aws.service
```

Paste this:
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

Save: Ctrl+X, Y, Enter

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pulse-aws.service
sudo systemctl start pulse-aws.service
sudo systemctl status pulse-aws.service
```

View logs:
```bash
sudo journalctl -u pulse-aws.service -f
```
