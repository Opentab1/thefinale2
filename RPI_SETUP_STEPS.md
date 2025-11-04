# Raspberry Pi Setup - Run These Commands

## Step 1: Create the AWS Directory

```bash
sudo mkdir -p /opt/pulse/aws/certificates
sudo chown $USER:$USER /opt/pulse/aws
sudo chown $USER:$USER /opt/pulse/aws/certificates
```

Verify:
```bash
ls -la /opt/pulse/aws/
```

## Step 2: Install AWS SDK

```bash
pip3 install --user awsiotsdk boto3
```

If that doesn't work:
```bash
sudo pip3 install awsiotsdk boto3
```

## Step 3: Copy the Uploader Script

First, find where your workspace is:
```bash
pwd
```

Then copy the uploader script. If you're in the workspace directory:
```bash
cp aws_uploader.py /opt/pulse/aws/aws_uploader.py
chmod +x /opt/pulse/aws/aws_uploader.py
```

Verify:
```bash
ls -la /opt/pulse/aws/aws_uploader.py
```

## Step 4: Create Config File

```bash
nano /opt/pulse/aws/config.json
```

Paste this (we'll fill in the endpoint later):
```json
{
  "endpoint": "YOUR_ENDPOINT_HERE.ats.iot.us-east-1.amazonaws.com",
  "thing_name": "pulse-rpi5",
  "certificate_path": "/opt/pulse/aws/certificates/device-certificate.pem",
  "private_key_path": "/opt/pulse/aws/certificates/device-private-key.pem.key",
  "root_ca_path": "/opt/pulse/aws/certificates/AmazonRootCA1.pem",
  "upload_interval_seconds": 30,
  "topic": "pulse/sensors/data"
}
```

Save: Ctrl+X, then Y, then Enter

## Step 5: Set Up AWS IoT Core (Do This in AWS Console)

1. Go to https://console.aws.amazon.com/iot/
2. Click "Manage" → "Things" → "Create things"
3. Click "Create single thing"
4. Name: `pulse-rpi5`
5. Click "Next" then "Create thing"

## Step 6: Create Policy

1. In AWS Console: "Secure" → "Policies" → "Create policy"
2. Name: `PulseSensorPolicy`
3. Policy document:
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

## Step 7: Create Certificates

1. "Secure" → "Certificates" → "Create"
2. Click "One-click certificate creation"
3. Download all 3 files:
   - Certificate (save as `device-certificate.pem`)
   - Private key (save as `device-private-key.pem.key`)
   - Root CA (click "Download Amazon Root CA 1" - save as `AmazonRootCA1.pem`)
4. Click "Activate" on the certificate
5. Click "Attach policy" → Select `PulseSensorPolicy` → "Attach"
6. Click "Attach thing" → Select `pulse-rpi5` → "Attach"

## Step 8: Get Your IoT Endpoint

1. In AWS Console: "Settings" (bottom left)
2. Copy the "Device data endpoint" (looks like: `xxxxx-ats.iot.us-east-1.amazonaws.com`)

## Step 9: Upload Certificates to Pi

Use `scp` from your computer, or copy-paste the certificate contents:

```bash
# Create the files
nano /opt/pulse/aws/certificates/device-certificate.pem
# Paste certificate content, save (Ctrl+X, Y, Enter)

nano /opt/pulse/aws/certificates/device-private-key.pem.key
# Paste private key content, save

nano /opt/pulse/aws/certificates/AmazonRootCA1.pem
# Paste root CA content, save
```

Or download directly:
```bash
# Download Amazon Root CA (if you don't have it)
cd /opt/pulse/aws/certificates
wget https://www.amazontrust.com/repository/AmazonRootCA1.pem
```

Set permissions:
```bash
chmod 644 /opt/pulse/aws/certificates/*.pem
chmod 600 /opt/pulse/aws/certificates/*.pem.key
```

## Step 10: Update Config with Endpoint

```bash
nano /opt/pulse/aws/config.json
```

Replace `YOUR_ENDPOINT_HERE` with your actual endpoint from Step 8.

## Step 11: Test It!

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

## Step 12: Set Up as Service (Optional but Recommended)

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

Save and enable:
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
