#!/usr/bin/env python3
"""
BME280 Diagnostic Tool - Find out why your sensor isn't working
Run on Raspberry Pi: python3 diagnose_bme280_now.py
"""

import sys
import subprocess
import os

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)

def print_result(check_name, status, details=""):
    symbols = {"pass": "✓", "fail": "✗", "warn": "⚠"}
    colors = {"pass": "\033[92m", "fail": "\033[91m", "warn": "\033[93m"}
    reset = "\033[0m"
    
    symbol = symbols.get(status, "?")
    color = colors.get(status, "")
    
    print(f"{color}{symbol}{reset} {check_name}")
    if details:
        print(f"  → {details}")

def run_command(cmd, shell=False):
    """Run a command and return output"""
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        else:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=5)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def check_i2c_enabled():
    """Check if I2C interface is enabled"""
    print_header("1. CHECK I2C INTERFACE")
    
    # Check if /dev/i2c-1 exists
    if os.path.exists("/dev/i2c-1"):
        print_result("I2C device exists", "pass", "/dev/i2c-1 found")
        return True
    else:
        print_result("I2C device missing", "fail", "/dev/i2c-1 not found")
        print("\n💡 FIX: Enable I2C interface")
        print("   sudo raspi-config")
        print("   → Interface Options → I2C → Enable")
        print("   → Reboot after enabling")
        return False

def check_i2c_tools():
    """Check if i2c-tools is installed"""
    print_header("2. CHECK I2C TOOLS")
    
    code, out, err = run_command("which i2cdetect")
    if code == 0:
        print_result("i2c-tools installed", "pass", out.strip())
        return True
    else:
        print_result("i2c-tools missing", "fail", "Not installed")
        print("\n💡 FIX: Install i2c-tools")
        print("   sudo apt-get update")
        print("   sudo apt-get install -y i2c-tools")
        return False

def check_i2c_sensor():
    """Check if BME280 sensor is detected on I2C bus"""
    print_header("3. CHECK BME280 ON I2C BUS")
    
    code, out, err = run_command("i2cdetect -y 1")
    
    if code != 0:
        print_result("I2C scan failed", "fail", err)
        return None
    
    print("\nI2C Bus Scan Results:")
    print(out)
    
    # Check for BME280 addresses (0x76 or 0x77)
    found_76 = "76" in out
    found_77 = "77" in out
    
    if found_76:
        print_result("BME280 found at 0x76", "pass", "Sensor detected")
        return 0x76
    elif found_77:
        print_result("BME280 found at 0x77", "pass", "Sensor detected")
        return 0x77
    else:
        print_result("BME280 NOT FOUND", "fail", "No sensor at 0x76 or 0x77")
        print("\n💡 CHECK:")
        print("   1. Sensor is connected to Raspberry Pi")
        print("   2. Wiring is correct:")
        print("      VCC → Pin 1 (3.3V)")
        print("      GND → Pin 6 (Ground)")
        print("      SDA → Pin 3 (GPIO2)")
        print("      SCL → Pin 5 (GPIO3)")
        print("   3. Sensor has power (LED on if present)")
        return None

def check_python_libs():
    """Check if required Python libraries are installed"""
    print_header("4. CHECK PYTHON LIBRARIES")
    
    libs = {
        "adafruit_bme280": "Adafruit BME280 driver",
        "busio": "I2C communication",
        "board": "Pin definitions",
        "smbus2": "SMBus support"
    }
    
    all_ok = True
    missing = []
    
    for lib, desc in libs.items():
        try:
            __import__(lib)
            print_result(f"{lib}", "pass", desc)
        except ImportError:
            print_result(f"{lib}", "fail", f"{desc} - NOT INSTALLED")
            missing.append(lib)
            all_ok = False
    
    if not all_ok:
        print("\n💡 FIX: Install missing Python libraries")
        print("   pip3 install adafruit-blinka adafruit-circuitpython-bme280 smbus2")
    
    return all_ok

def test_sensor_reading(address=0x76):
    """Try to read from the BME280 sensor"""
    print_header("5. TEST SENSOR READING")
    
    try:
        import busio
        import board
        import adafruit_bme280.advanced as adafruit_bme280
        
        print("Initializing BME280 sensor...")
        
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            print_result("I2C bus created", "pass", "Using busio.I2C()")
        except Exception as e:
            print_result("busio.I2C() failed", "warn", f"{e}")
            print("  Trying board.I2C()...")
            i2c = board.I2C()
            print_result("I2C bus created", "pass", "Using board.I2C()")
        
        # Try to create sensor object
        try:
            sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=address)
            print_result("Sensor initialized", "pass", f"At address {hex(address)}")
        except Exception as e:
            # Try alternate address
            alt_addr = 0x77 if address == 0x76 else 0x76
            print_result(f"Sensor at {hex(address)} failed", "warn", f"{e}")
            print(f"  Trying alternate address {hex(alt_addr)}...")
            sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=alt_addr)
            print_result("Sensor initialized", "pass", f"At address {hex(alt_addr)}")
            address = alt_addr
        
        # Try to read values
        print("\nReading sensor values...")
        temp = sensor.temperature
        humidity = sensor.humidity
        pressure = sensor.pressure
        
        temp_f = (temp * 9/5) + 32
        
        print_result("Temperature", "pass", f"{temp_f:.1f}°F ({temp:.1f}°C)")
        print_result("Humidity", "pass", f"{humidity:.1f}%")
        print_result("Pressure", "pass", f"{pressure:.2f} hPa")
        
        print("\n" + "🎉"*25)
        print("  BME280 SENSOR IS WORKING! ✓")
        print("🎉"*25)
        
        return True
        
    except ImportError as e:
        print_result("Import failed", "fail", f"Missing library: {e}")
        return False
    except Exception as e:
        print_result("Sensor test failed", "fail", str(e))
        print(f"\nError details: {type(e).__name__}: {e}")
        return False

def check_config():
    """Check if BME280 is enabled in config"""
    print_header("6. CHECK PULSE CONFIG")
    
    config_paths = [
        "/opt/pulse/config/config.yaml",
        "/workspace/config/config.yaml"
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                if 'bme280: true' in content:
                    print_result("BME280 enabled in config", "pass", config_path)
                    return True
                elif 'bme280: false' in content:
                    print_result("BME280 disabled in config", "fail", config_path)
                    print("\n💡 FIX: Enable BME280 in config")
                    print(f"   nano {config_path}")
                    print("   Change 'bme280: false' to 'bme280: true'")
                    return False
    
    print_result("Config file not found", "warn", "Checked: " + ", ".join(config_paths))
    return None

def check_logs():
    """Check recent logs for BME280 errors"""
    print_header("7. CHECK RECENT LOGS")
    
    log_paths = [
        "/var/log/pulse/hub.log",
        "/var/log/pulse/pulse.log"
    ]
    
    for log_path in log_paths:
        if os.path.exists(log_path):
            print(f"\nChecking {log_path}...")
            code, out, err = run_command(f"tail -50 {log_path} | grep -i bme280", shell=True)
            if out:
                print("Recent BME280 log entries:")
                print(out[:500])  # Show last 500 chars
            else:
                print("No BME280 entries in recent logs")
            break

def main():
    print("\n" + "🔍"*35)
    print("  BME280 SENSOR DIAGNOSTIC TOOL")
    print("🔍"*35)
    print("\nThis will check why your BME280 temperature sensor isn't working.\n")
    
    # Run all checks
    i2c_ok = check_i2c_enabled()
    tools_ok = check_i2c_tools()
    
    sensor_addr = None
    if i2c_ok and tools_ok:
        sensor_addr = check_i2c_sensor()
    
    libs_ok = check_python_libs()
    
    if sensor_addr and libs_ok:
        sensor_works = test_sensor_reading(sensor_addr)
    else:
        sensor_works = False
    
    config_ok = check_config()
    check_logs()
    
    # Final summary
    print_header("DIAGNOSTIC SUMMARY")
    
    if sensor_works:
        print("\n✅ BME280 SENSOR IS WORKING!")
        print("\nIf the dashboard still doesn't show temperature:")
        print("1. Restart Pulse services:")
        print("   sudo systemctl restart pulse-hub-main.service")
        print("\n2. Check dashboard logs:")
        print("   sudo journalctl -u pulse-hub-main.service -f")
    else:
        print("\n❌ BME280 SENSOR HAS ISSUES")
        print("\nFix the issues above, then run this diagnostic again.")
        print("\nCommon fixes:")
        print("1. Enable I2C: sudo raspi-config")
        print("2. Install tools: sudo apt-get install i2c-tools")
        print("3. Install Python libs: pip3 install adafruit-blinka adafruit-circuitpython-bme280")
        print("4. Check wiring (see above)")
        print("5. Reboot: sudo reboot")
    
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()
