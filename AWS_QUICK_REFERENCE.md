# AWS Integration Quick Reference

## What Was Created

1. **`aws_sync.py`** - Main sync service script (reads from your database, sends to AWS)
2. **`AWS_SETUP_GUIDE.md`** - Complete step-by-step setup instructions
3. **`setup_aws_sync.sh`** - Quick setup script to prepare directories

## Key Points

✅ **No git repository files are modified** - all AWS files are stored separately
✅ **Uses MQTT with certificate authentication** - proper IoT device security
✅ **Reads from existing database** - no changes to your Pulse system
✅ **Runs independently** - can start/stop without affecting main system

## Quick Start

```bash
# 1. Run setup script
./setup_aws_sync.sh

# 2. Follow AWS_SETUP_GUIDE.md to:
#    - Set up AWS IoT Core
#    - Download certificates
#    - Configure aws_config.env

# 3. Test connection
python3 /opt/pulse/aws_sync/aws_sync.py --test

# 4. Start syncing
python3 /opt/pulse/aws_sync/aws_sync.py
```

## File Locations

- **Sync script**: `/opt/pulse/aws_sync/aws_sync.py`
- **Config file**: `/opt/pulse/aws_sync/aws_config.env` (create this)
- **Certificates**: `/opt/pulse/aws_sync/certs/` (put your .pem files here)
- **Logs**: `/opt/pulse/aws_sync/sync.log`

## What Gets Sent to AWS

The service sends sensor data every 60 seconds (configurable) to AWS IoT Core topic: `pulse/sensor-data`

Data includes:
- Occupancy (people count, entries/exits)
- Temperature, humidity, pressure
- Light level
- Noise level
- Current song playing

## Troubleshooting

- **Connection issues**: Check certificates are in `/opt/pulse/aws_sync/certs/` with correct permissions (600)
- **Database not found**: Update `PULSE_DB_PATH` in `aws_config.env`
- **MQTT errors**: Verify IoT policy allows Connect/Publish, check endpoint URL

See `AWS_SETUP_GUIDE.md` for detailed troubleshooting.
