# Quick Fix for Missing Temperature Readings

If you installed Pulse but temperature readings show `null`:

## The Problem

I2C interface needs to be enabled for the BME280 temperature sensor.

## The Fix

### Option 1: Enable I2C Manually (Fastest)

```bash
sudo raspi-config
```
- Navigate to: **Interface Options** → **I2C** → **Yes**
- Exit and reboot

```bash
sudo reboot
```

### Option 2: Command Line

```bash
# Add I2C to boot config
echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt

# Add user to i2c group
sudo usermod -a -G i2c pi

# Reboot
sudo reboot
```

## After Reboot - Verify

```bash
# Check I2C device exists
ls /dev/i2c-1
# Should show: /dev/i2c-1

# Check BME280 sensor is detected
sudo i2cdetect -y 1
# Should show "76" or "77" in the grid
```

## Ensure Dependencies Are Installed

```bash
cd /opt/pulse
source venv/bin/activate
pip install adafruit-blinka adafruit-circuitpython-bme280
```

## Test It Works

```bash
cd /opt/pulse
python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/pulse/services')
from sensors.bme280_reader import BME280Reader
sensor = BME280Reader(address=0x76)
data = sensor.read_sensor()
print(f"Temperature: {data['temperature_f']:.1f}°F")
print(f"Humidity: {data['humidity']:.1f}%")
EOF
```

## Restart Pulse

```bash
sudo systemctl restart pulse-hub.service
```

## Check Dashboard

Wait 30 seconds, then:
```bash
curl http://localhost:8080/api/sensors/current | python3 -m json.tool | grep temperature
```

Should now show actual temperature value!

---

**Note:** The `install.sh` script already enables I2C, but you MUST reboot for it to take effect. If you didn't reboot after installation, that's why temperature doesn't work.
