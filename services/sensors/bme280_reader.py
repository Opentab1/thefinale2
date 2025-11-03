"""
Pulse 1.0 - BME280 Temperature/Humidity/Pressure Sensor
"""

import logging
import os
import random
import time
from pathlib import Path
from threading import Thread, Event
from datetime import datetime
from typing import Optional, Dict

import numpy as np

logger = logging.getLogger(__name__)

class BME280Reader:
    def __init__(self, address: int = 0x76):
        self.address = address
        self.sensor = None
        self.running = False
        self.stop_event = Event()
        
        self.temperature = None
        self.humidity = None
        self.pressure = None
        self.simulated = False
        self._sim_state: Dict[str, Optional[float]] = {
            "temperature_c": None,
            "humidity": None,
            "pressure": None,
            "altitude": 0.0
        }
        self._sim_last_update = 0.0
        
        self._init_sensor()
    
    def _init_sensor(self):
        """Initialize BME280 sensor with robust error handling"""
        force_sim = os.getenv('PULSE_ENABLE_BME280_SIM')
        if force_sim and force_sim.strip().lower() in {'1', 'true', 'yes', 'on'}:
            self._enable_simulation("forced via PULSE_ENABLE_BME280_SIM")
            return

        try:
            # Use busio directly to avoid board pin mapping issues
            import busio
            import board
            import adafruit_bme280.advanced as adafruit_bme280
            
            logger.debug(f"Attempting to initialize BME280 at address {hex(self.address)}")
            
            # Create I2C bus using busio (more reliable on Pi 5)
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                logger.debug("I2C bus created successfully using busio.I2C()")
            except Exception as e:
                logger.debug(f"busio.I2C() failed ({e}), falling back to board.I2C()")
                # Fallback to board.I2C() if busio fails
                i2c = board.I2C()
            
            # Try to initialize sensor at primary address
            try:
                logger.debug(f"Creating BME280 sensor object at {hex(self.address)}...")
                self.sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=self.address)
                logger.debug(f"BME280 sensor object created at {hex(self.address)}")
            except (ValueError, OSError) as e:
                # Try alternate address (BME280 can be at 0x76 or 0x77)
                alternate_addr = 0x77 if self.address == 0x76 else 0x76
                logger.info(f"Sensor not found at {hex(self.address)} ({e}), trying {hex(alternate_addr)}")
                try:
                    self.sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=alternate_addr)
                    self.address = alternate_addr  # Update stored address
                    logger.info(f"BME280 sensor initialized at alternate address {hex(alternate_addr)}")
                except (ValueError, OSError) as e2:
                    logger.error(f"I2C bus error - sensor not found at {hex(self.address)} or {hex(alternate_addr)}")
                    logger.error("Check sensor connection and run: sudo i2cdetect -y 1")
                    raise Exception(f"BME280 not found at either address") from e2
            
            # Configure sensor for indoor monitoring
            logger.debug("Configuring BME280 sensor...")
            self.sensor.sea_level_pressure = 1013.25
            self.sensor.mode = adafruit_bme280.MODE_NORMAL
            self.sensor.standby_period = adafruit_bme280.STANDBY_TC_500
            self.sensor.iir_filter = adafruit_bme280.IIR_FILTER_X16
            self.sensor.overscan_pressure = adafruit_bme280.OVERSCAN_X16
            self.sensor.overscan_humidity = adafruit_bme280.OVERSCAN_X1
            self.sensor.overscan_temperature = adafruit_bme280.OVERSCAN_X2
            logger.debug("BME280 sensor configured")
            
            logger.info(f"BME280 sensor initialized at address {hex(self.address)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BME280 sensor: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            if self._enable_simulation(str(e)):
                return
            raise
    
    def _enable_simulation(self, reason: str = "") -> bool:
        """Enable simulated readings when hardware is unavailable."""
        if not self._should_use_simulation():
            return False

        self.simulated = True

        base_temp_c = self._get_env_float('PULSE_SIM_TEMP_C', 22.0)
        base_humidity = self._get_env_float('PULSE_SIM_HUMIDITY', 45.0)
        base_pressure = self._get_env_float('PULSE_SIM_PRESSURE', 1013.25)
        base_altitude = self._get_env_float('PULSE_SIM_ALTITUDE', 0.0)

        self._sim_state.update({
            "temperature_c": base_temp_c,
            "humidity": base_humidity,
            "pressure": base_pressure,
            "altitude": base_altitude
        })

        self.temperature = (base_temp_c * 9/5) + 32
        self.humidity = base_humidity
        self.pressure = base_pressure
        self._sim_last_update = time.time()

        reason_text = f" ({reason})" if reason else ""
        logger.warning("BME280 hardware unavailable%s - using simulated readings for development.", reason_text)
        logger.warning("Set PULSE_ENABLE_BME280_SIM=0 to disable simulation and surface hardware errors.")
        return True

    def _should_use_simulation(self) -> bool:
        env = os.getenv('PULSE_ENABLE_BME280_SIM')
        if env is not None:
            env_val = env.strip().lower()
            if env_val in {'1', 'true', 'yes', 'on'}:
                return True
            if env_val in {'0', 'false', 'no', 'off'}:
                return False
        # Default: enable simulation automatically on non-Raspberry Pi systems (development machines)
        return not self._is_running_on_pi()

    @staticmethod
    def _is_running_on_pi() -> bool:
        try:
            model_path = Path('/sys/firmware/devicetree/base/model')
            if model_path.exists():
                model = model_path.read_text(errors='ignore').lower()
                if 'raspberry pi' in model:
                    return True
        except Exception:
            pass
        try:
            return os.uname().machine.startswith('arm')
        except AttributeError:
            return False

    @staticmethod
    def _get_env_float(var: str, default: float) -> float:
        try:
            value = os.getenv(var)
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    def _generate_simulated_readings(self) -> Dict[str, float]:
        now = time.time()
        if (now - self._sim_last_update) >= 1.0:
            temp_c = self._sim_state.get("temperature_c") or 22.0
            humidity = self._sim_state.get("humidity") or 45.0
            pressure = self._sim_state.get("pressure") or 1013.25
            altitude = self._sim_state.get("altitude") or 0.0

            temp_c = max(16.0, min(32.0, temp_c + random.uniform(-0.25, 0.25)))
            humidity = max(25.0, min(75.0, humidity + random.uniform(-0.8, 0.8)))
            pressure = max(1008.0, min(1018.0, pressure + random.uniform(-0.6, 0.6)))

            self._sim_state.update({
                "temperature_c": temp_c,
                "humidity": humidity,
                "pressure": pressure,
                "altitude": altitude
            })
            self.temperature = (temp_c * 9/5) + 32
            self.humidity = humidity
            self.pressure = pressure
            self._sim_last_update = now

        temp_c = self._sim_state.get("temperature_c") or 22.0
        humidity = self._sim_state.get("humidity") or 45.0
        pressure = self._sim_state.get("pressure") or 1013.25
        altitude = self._sim_state.get("altitude") or 0.0
        temp_f = (temp_c * 9/5) + 32

        return {
            "temperature_f": round(temp_f, 1),
            "temperature_c": round(temp_c, 1),
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 2),
            "altitude": round(altitude, 1)
        }
    
    def read_sensor(self) -> Dict[str, float]:
        """Read current sensor values"""
        try:
            if self.simulated:
                data = self._generate_simulated_readings()
                self.temperature = data.get("temperature_f")
                self.humidity = data.get("humidity")
                self.pressure = data.get("pressure")
                data["timestamp"] = datetime.now().isoformat()
                return data

            if self.sensor is None:
                raise Exception("Sensor not initialized")
            
            # Read values
            temp_c = self.sensor.temperature
            humidity = self.sensor.humidity
            pressure = self.sensor.pressure
            
            # Convert temperature to Fahrenheit
            temp_f = (temp_c * 9/5) + 32
            
            # Update stored values
            self.temperature = temp_f
            self.humidity = humidity
            self.pressure = pressure
            
            return {
                "temperature_f": round(temp_f, 1),
                "temperature_c": round(temp_c, 1),
                "humidity": round(humidity, 1),
                "pressure": round(pressure, 2),
                "altitude": round(self.sensor.altitude, 1) if hasattr(self.sensor, 'altitude') else None,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error reading sensor: {e}")
            return {}
    
    def start_reading(self, interval: int = 30):
        """Start continuous sensor reading"""
        if self.running:
            logger.warning("Reader already running")
            return
        
        # CRITICAL: Do an initial synchronous read to populate the cache
        # This ensures cached values are never None when hub queries them
        logger.info("Performing initial BME280 reading...")
        try:
            initial_data = self.read_sensor()
            if initial_data and initial_data.get("temperature_f") is not None:
                logger.info(f"Initial reading: {initial_data['temperature_f']:.1f}°F, {initial_data['humidity']:.1f}%")
            else:
                logger.warning("Initial reading returned no data - sensor may not be working")
        except Exception as e:
            logger.error(f"Initial sensor read failed: {e}")
            raise  # Re-raise to prevent starting with bad sensor
        
        self.running = True
        self.stop_event.clear()
        
        thread = Thread(target=self._reading_loop, args=(interval,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started BME280 background reading (interval: {interval}s)")
    
    def _reading_loop(self, interval: int):
        """Main reading loop"""
        try:
            while self.running and not self.stop_event.is_set():
                try:
                    data = self.read_sensor()
                    
                    if data:
                        logger.debug(
                            f"Temp: {data['temperature_f']:.1f}°F, "
                            f"Humidity: {data['humidity']:.1f}%, "
                            f"Pressure: {data['pressure']:.2f} hPa"
                        )
                    
                    # Wait for next reading
                    self.stop_event.wait(interval)
                    
                except Exception as e:
                    logger.error(f"Error in reading loop: {e}")
                    self.stop_event.wait(interval)
            
            logger.info("BME280 reading stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in reading loop: {e}")
            self.running = False
    
    def stop_reading(self):
        """Stop sensor reading"""
        self.running = False
        self.stop_event.set()
    
    def get_temperature(self, unit: str = "f") -> Optional[float]:
        """Get current temperature"""
        if self.temperature is None:
            return None
        
        if unit.lower() == "c":
            return (self.temperature - 32) * 5/9
        return self.temperature
    
    def get_humidity(self) -> Optional[float]:
        """Get current humidity"""
        return self.humidity
    
    def get_pressure(self) -> Optional[float]:
        """Get current pressure"""
        return self.pressure
    
    def get_all_readings(self) -> Dict:
        """Get all current readings"""
        if self.simulated:
            data = self._generate_simulated_readings()
            data["timestamp"] = datetime.now().isoformat()
            return data

        temp_f = self.temperature
        temp_c = ((temp_f - 32) * 5/9) if isinstance(temp_f, (int, float)) else None
        return {
            "temperature_f": temp_f,
            "temperature_c": temp_c,
            "humidity": self.humidity,
            "pressure": self.pressure,
            "timestamp": datetime.now().isoformat()
        }
    
    def calculate_heat_index(self) -> Optional[float]:
        """Calculate heat index (feels like temperature)"""
        if self.temperature is None or self.humidity is None:
            return None
        
        T = self.temperature
        RH = self.humidity
        
        # Rothfusz regression (NWS formula)
        if T >= 80:
            HI = -42.379 + 2.04901523*T + 10.14333127*RH - 0.22475541*T*RH
            HI += -0.00683783*T*T - 0.05481717*RH*RH + 0.00122874*T*T*RH
            HI += 0.00085282*T*RH*RH - 0.00000199*T*T*RH*RH
            
            return round(HI, 1)
        else:
            # Simple formula for lower temperatures
            return T
    
    def calculate_dew_point(self) -> Optional[float]:
        """Calculate dew point temperature"""
        if self.temperature is None or self.humidity is None:
            return None
        
        # Convert to Celsius
        T = (self.temperature - 32) * 5/9
        RH = self.humidity
        
        # Magnus formula
        a = 17.27
        b = 237.7
        
        alpha = ((a * T) / (b + T)) + np.log(RH / 100.0)
        dew_c = (b * alpha) / (a - alpha)
        dew_f = (dew_c * 9/5) + 32
        
        return round(dew_f, 1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        reader = BME280Reader()
        
        # Single reading
        data = reader.read_sensor()
        print("Single reading:")
        for key, value in data.items():
            print(f"  {key}: {value}")
        
        # Continuous reading
        print("\nStarting continuous reading (Ctrl+C to stop)...")
        reader.start_reading(interval=5)
        
        import time
        while True:
            time.sleep(10)
            readings = reader.get_all_readings()
            print(f"\nTemp: {readings['temperature_f']:.1f}°F, "
                  f"Humidity: {readings['humidity']:.1f}%, "
                  f"Pressure: {readings['pressure']:.2f} hPa")
            
            heat_index = reader.calculate_heat_index()
            if heat_index:
                print(f"Heat Index: {heat_index:.1f}°F")
        
    except KeyboardInterrupt:
        print("\nStopping...")
        reader.stop_reading()
    except Exception as e:
        print(f"Error: {e}")
