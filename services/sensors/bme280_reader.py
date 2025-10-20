"""
Pulse 1.0 - BME280 Temperature/Humidity/Pressure Sensor
"""

import logging
import time
import numpy as np
from threading import Thread, Event
from datetime import datetime
from typing import Optional, Dict

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
        
        self._init_sensor()
    
    def _init_sensor(self):
        """Initialize BME280 sensor"""
        try:
            import board
            import adafruit_bme280.advanced as adafruit_bme280
            
            i2c = board.I2C()
            
            try:
                self.sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=self.address)
            except ValueError:
                # Try alternate address
                logger.info(f"Sensor not found at {hex(self.address)}, trying 0x77")
                self.sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
            
            # Configure sensor for indoor monitoring
            self.sensor.sea_level_pressure = 1013.25
            self.sensor.mode = adafruit_bme280.MODE_NORMAL
            self.sensor.standby_period = adafruit_bme280.STANDBY_TC_500
            self.sensor.iir_filter = adafruit_bme280.IIR_FILTER_X16
            self.sensor.overscan_pressure = adafruit_bme280.OVERSCAN_X16
            self.sensor.overscan_humidity = adafruit_bme280.OVERSCAN_X1
            self.sensor.overscan_temperature = adafruit_bme280.OVERSCAN_X2
            
            logger.info(f"BME280 sensor initialized at address {hex(self.address)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize BME280 sensor: {e}")
            raise
    
    def read_sensor(self) -> Dict[str, float]:
        """Read current sensor values"""
        try:
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
                "altitude": round(self.sensor.altitude, 1),
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
        
        self.running = True
        self.stop_event.clear()
        
        thread = Thread(target=self._reading_loop, args=(interval,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started BME280 reading (interval: {interval}s)")
    
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
        return {
            "temperature_f": self.temperature,
            "temperature_c": (self.temperature - 32) * 5/9 if self.temperature else None,
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
