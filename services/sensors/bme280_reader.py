"""
Pulse 1.0 - BME280 Temperature/Humidity/Pressure Sensor
"""

import logging
import math
import time
import numpy as np
from threading import Thread, Event, Lock
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class BME280Reader:
    def __init__(self, address: int = 0x76):
        self.address = address
        self.sensor = None
        self.running = False
        self.stop_event = Event()
        self._sensor_lock = Lock()
        self._thread = None
        self._read_interval = None
        
        self.temperature = None
        self.humidity = None
        self.pressure = None
        self.altitude = None
        self.last_update = None
        
        self._init_sensor()

    @staticmethod
    def _sanitize_value(value: Optional[float]) -> Optional[float]:
        """Return a finite float value or None when reading is invalid."""
        if value is None:
            return None
        try:
            value_float = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(value_float) or math.isinf(value_float):
            return None
        return value_float
    
    def _init_sensor(self):
        """Initialize BME280 sensor with robust error handling"""
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
            raise
    
    def read_sensor(self) -> Dict[str, float]:
        """Read current sensor values"""
        try:
            if self.sensor is None:
                raise Exception("Sensor not initialized")
            
            with self._sensor_lock:
                # Read values
                temp_c_raw = getattr(self.sensor, "temperature", None)
                temp_c = self._sanitize_value(temp_c_raw)
                if temp_c is None:
                    raise ValueError("BME280 returned invalid temperature reading")

                humidity_raw = getattr(self.sensor, "humidity", None)
                humidity = self._sanitize_value(humidity_raw)

                pressure_raw = getattr(self.sensor, "pressure", None)
                pressure = self._sanitize_value(pressure_raw)

                altitude_raw = getattr(self.sensor, "altitude", None)
                altitude = self._sanitize_value(altitude_raw)
            
            # Convert temperature to Fahrenheit
            temp_f = (temp_c * 9/5) + 32

            # Prepare rounded outputs (keep internal state unrounded for calculations)
            temp_f_rounded = round(temp_f, 1)
            temp_c_rounded = round(temp_c, 1)
            humidity_rounded = round(humidity, 1) if humidity is not None else None
            pressure_rounded = round(pressure, 2) if pressure is not None else None
            altitude_rounded = round(altitude, 1) if altitude is not None else None

            # Update stored values
            self.temperature = temp_f
            self.humidity = humidity
            self.pressure = pressure
            self.altitude = altitude
            self.last_update = time.time()

            return {
                "temperature_f": temp_f_rounded,
                "temperature_c": temp_c_rounded,
                "humidity": humidity_rounded,
                "pressure": pressure_rounded,
                "altitude": altitude_rounded,
                "age_seconds": 0.0,
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
        
        self._read_interval = interval
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
        self._thread = thread
        
        logger.info(f"Started BME280 background reading (interval: {interval}s)")
    
    def _reading_loop(self, interval: int):
        """Main reading loop with error recovery"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while self.running and not self.stop_event.is_set():
                try:
                    data = self.read_sensor()
                    
                    if data and data.get("temperature_f") is not None:
                        logger.debug(
                            f"Temp: {data['temperature_f']:.1f}°F, "
                            f"Humidity: {data['humidity']:.1f}%, "
                            f"Pressure: {data['pressure']:.2f} hPa"
                        )
                        # Reset error counter on successful read
                        consecutive_errors = 0
                    else:
                        logger.warning("BME280 read returned no data")
                        consecutive_errors += 1
                    
                    # If too many consecutive errors, try to reinitialize sensor
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"BME280 has failed {consecutive_errors} times, attempting to reinitialize...")
                        try:
                            self._init_sensor()
                            consecutive_errors = 0
                            logger.info("BME280 reinitialized successfully")
                        except Exception as reinit_error:
                            logger.error(f"Failed to reinitialize BME280: {reinit_error}")
                            # Continue anyway, maybe it will recover
                    
                    # Wait for next reading
                    self.stop_event.wait(interval)
                    
                except Exception as e:
                    logger.error(f"Error in reading loop: {e}")
                    consecutive_errors += 1
                    self.stop_event.wait(interval)
            
            logger.info("BME280 reading stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in reading loop: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.running = False
        finally:
            self._thread = None
    
    def stop_reading(self):
        """Stop sensor reading"""
        self.running = False
        self.stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            try:
                thread.join(timeout=1.0)
            except Exception:
                pass
        self._thread = None
    
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
        temp_f = self._sanitize_value(self.temperature)
        humidity = self._sanitize_value(self.humidity)
        pressure = self._sanitize_value(self.pressure)
        altitude = self._sanitize_value(self.altitude)
        cache_age = self.get_cache_age()

        temp_c = (temp_f - 32) * 5/9 if temp_f is not None else None

        return {
            "temperature_f": round(temp_f, 1) if temp_f is not None else None,
            "temperature_c": round(temp_c, 1) if temp_c is not None else None,
            "humidity": round(humidity, 1) if humidity is not None else None,
            "pressure": round(pressure, 2) if pressure is not None else None,
            "altitude": round(altitude, 1) if altitude is not None else None,
            "age_seconds": round(cache_age, 1) if cache_age is not None else None,
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

    def get_cache_age(self) -> Optional[float]:
        if self.last_update is None:
            return None
        return max(0.0, time.time() - self.last_update)

    def is_cache_stale(self, max_age: float = 120.0) -> bool:
        age = self.get_cache_age()
        return age is None or age > max_age

    def restart_reading(self, interval: Optional[int] = None):
        """Restart the background reading thread."""
        requested_interval = interval or self._read_interval or 30
        logger.warning("Restarting BME280 background reader (interval: %ss)", requested_interval)
        self.stop_reading()
        time.sleep(0.1)
        try:
            self.start_reading(requested_interval)
        except Exception as exc:
            logger.error(f"Failed to restart BME280 reader: {exc}")
            raise

    def get_read_interval(self) -> int:
        return self._read_interval or 30


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
