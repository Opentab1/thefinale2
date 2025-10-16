"""
Pulse 1.0 - Hardware Health Monitor
Continuously checks hardware modules and attempts recovery
"""

import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, Callable
import psutil

logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self, config_path: str = "/opt/pulse/config/hardware_status.json"):
        self.config_path = config_path
        self.status = self._load_status()
        # Ensure status has the expected schema, migrate legacy flat files if needed
        if not isinstance(self.status, dict):
            self.status = {"last_check": None, "modules": {}}
        if "modules" not in self.status or not isinstance(self.status.get("modules"), dict):
            legacy = self.status if isinstance(self.status, dict) else {}
            self.status = {
                "last_check": legacy.get("last_check") or legacy.get("last_checked"),
                "modules": {}
            }
        self.test_functions: Dict[str, Callable] = {}
        
    def _load_status(self) -> Dict:
        """Load hardware status from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    # If legacy format (flat keys like 'camera', 'mic', etc.), migrate lazily
                    if not isinstance(data, dict):
                        return {"last_check": None, "modules": {}}
                    if "modules" not in data or not isinstance(data.get("modules"), dict):
                        return {
                            "last_check": data.get("last_check") or data.get("last_checked"),
                            "modules": {}
                        }
                    return data
        except Exception as e:
            logger.error(f"Error loading hardware status: {e}")
        
        return {
            "last_check": None,
            "modules": {}
        }
    
    def _save_status(self):
        """Save hardware status to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.status, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving hardware status: {e}")
    
    def register_test(self, module_name: str, test_func: Callable):
        """Register a hardware test function"""
        self.test_functions[module_name] = test_func
        # Defensive: ensure the 'modules' container exists even if status file was legacy
        if "modules" not in self.status or not isinstance(self.status.get("modules"), dict):
            self.status["modules"] = {}
        if module_name not in self.status["modules"]:
            self.status["modules"][module_name] = {
                "status": "unknown",
                "last_success": None,
                "failure_count": 0,
                "error": None
            }
    
    def test_module(self, module_name: str) -> bool:
        """Test a specific module"""
        if module_name not in self.test_functions:
            logger.warning(f"No test function registered for {module_name}")
            return False
        
        try:
            result = self.test_functions[module_name]()
            if result:
                self.status["modules"][module_name].update({
                    "status": "ok",
                    "last_success": datetime.now().isoformat(),
                    "failure_count": 0,
                    "error": None
                })
                logger.info(f"Module {module_name} is healthy")
                return True
            else:
                self._mark_failure(module_name, "Test returned False")
                return False
        except Exception as e:
            self._mark_failure(module_name, str(e))
            return False
    
    def _mark_failure(self, module_name: str, error: str):
        """Mark a module as failed"""
        module = self.status["modules"].get(module_name, {})
        module["status"] = "failed"
        module["failure_count"] = module.get("failure_count", 0) + 1
        module["error"] = error
        self.status["modules"][module_name] = module
        logger.error(f"Module {module_name} failed: {error}")
    
    def test_all_modules(self) -> Dict[str, bool]:
        """Test all registered modules"""
        results = {}
        for module_name in self.test_functions:
            results[module_name] = self.test_module(module_name)
        
        self.status["last_check"] = datetime.now().isoformat()
        self._save_status()
        return results
    
    def get_status(self, module_name: str = None) -> Dict:
        """Get status of a module or all modules"""
        if module_name:
            return self.status["modules"].get(module_name, {})
        return self.status
    
    def is_module_healthy(self, module_name: str) -> bool:
        """Check if a module is healthy"""
        module = self.status["modules"].get(module_name, {})
        return module.get("status") == "ok"
    
    def get_system_stats(self) -> Dict:
        """Get system resource usage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Try to get CPU temperature (Raspberry Pi specific)
            cpu_temp = None
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    cpu_temp = float(f.read()) / 1000.0
            except:
                pass
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "memory_available_mb": memory.available / 1024 / 1024,
                "disk_usage": disk.percent,
                "disk_free_gb": disk.free / 1024 / 1024 / 1024,
                "cpu_temperature": cpu_temp
            }
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def run_continuous_monitoring(self, interval_seconds: int = 60):
        """Run continuous health monitoring"""
        logger.info(f"Starting continuous health monitoring (interval: {interval_seconds}s)")
        
        while True:
            try:
                results = self.test_all_modules()
                failed = [name for name, status in results.items() if not status]
                
                if failed:
                    logger.warning(f"Failed modules: {', '.join(failed)}")
                
                stats = self.get_system_stats()
                logger.info(f"System stats: CPU {stats.get('cpu_usage', 0):.1f}%, "
                          f"Memory {stats.get('memory_usage', 0):.1f}%, "
                          f"Temp {stats.get('cpu_temperature', 0):.1f}°C")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            time.sleep(interval_seconds)


# Hardware test functions
def test_camera() -> bool:
    """Test if camera is available"""
    try:
        from picamera2 import Picamera2
        camera = Picamera2()
        camera.close()
        return True
    except Exception as e:
        logger.debug(f"Camera test failed: {e}")
        return False


def test_microphone() -> bool:
    """Test if microphone is available"""
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        p.terminate()
        return device_count > 0
    except Exception as e:
        logger.debug(f"Microphone test failed: {e}")
        return False


def test_bme280() -> bool:
    """Test if BME280 sensor is available"""
    try:
        import board
        import adafruit_bme280.advanced as adafruit_bme280
        i2c = board.I2C()
        sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
        # Try alternate address
        if not sensor:
            sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
        _ = sensor.temperature
        return True
    except Exception as e:
        logger.debug(f"BME280 test failed: {e}")
        return False


def test_pan_tilt() -> bool:
    """Test if pan-tilt HAT is available"""
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        # Test GPIO pins used by pan-tilt HAT (usually GPIO pins for servos)
        # This is a basic test - actual implementation would verify servo control
        return True
    except Exception as e:
        logger.debug(f"Pan-tilt test failed: {e}")
        return False


def test_ai_hat() -> bool:
    """Test if AI HAT is available"""
    try:
        # Check for Hailo AI kit or similar
        # This is a placeholder - actual test would verify the specific AI accelerator
        import os
        return os.path.exists('/dev/hailo0') or os.path.exists('/dev/apex_0')
    except Exception as e:
        logger.debug(f"AI HAT test failed: {e}")
        return False


def test_light_sensor() -> bool:
    """Test if light sensor is available"""
    try:
        # Placeholder - would test actual light sensor hardware
        # Could use camera as proxy for light detection
        return test_camera()
    except Exception as e:
        logger.debug(f"Light sensor test failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    monitor = HealthMonitor()
    
    # Register all tests
    monitor.register_test("camera", test_camera)
    monitor.register_test("mic", test_microphone)
    monitor.register_test("bme280", test_bme280)
    monitor.register_test("pan_tilt", test_pan_tilt)
    monitor.register_test("ai_hat", test_ai_hat)
    monitor.register_test("light_sensor", test_light_sensor)
    
    # Run initial test
    print("Running hardware tests...")
    results = monitor.test_all_modules()
    
    for module, status in results.items():
        print(f"  {module}: {'✓ OK' if status else '✗ FAILED'}")
    
    print("\nSystem stats:")
    stats = monitor.get_system_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
