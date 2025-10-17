"""
Pulse 1.0 - Light Level Sensor
Uses camera-derived brightness as a lux proxy.

To avoid camera device conflicts with the people counter, this sensor reads
the latest snapshot written by the people counter by default. Set the
environment variable PULSE_LIGHT_SOURCE=camera to have it open the camera
directly instead (not recommended if people counter is running).
"""

import logging
import os
import cv2
import numpy as np
from threading import Thread, Event
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class LightSensor:
    def __init__(self, snapshot_path: str = "/opt/pulse/data/latest_camera.jpg"):
        self.running = False
        self.stop_event = Event()
        self.light_level = 0.0
        self.brightness_history = []
        self.max_history = 100
        self.snapshot_path = snapshot_path
    
    def calculate_brightness(self, frame: np.ndarray) -> float:
        """
        Calculate brightness from image frame
        Returns a value roughly corresponding to lux levels
        """
        try:
            # Convert to grayscale if color
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Calculate mean brightness
            mean_brightness = np.mean(gray)
            
            # Convert to approximate lux (rough calibration)
            # 0-255 brightness -> 0-1000 lux approximation
            lux_estimate = (mean_brightness / 255.0) * 1000.0
            
            return round(lux_estimate, 1)
            
        except Exception as e:
            logger.error(f"Error calculating brightness: {e}")
            return 0.0
    
    def analyze_lighting_conditions(self, lux: float) -> dict:
        """Analyze lighting conditions and provide classification"""
        if lux < 50:
            condition = "very_dark"
            description = "Very Dark"
        elif lux < 150:
            condition = "dark"
            description = "Dark"
        elif lux < 300:
            condition = "dim"
            description = "Dim"
        elif lux < 500:
            condition = "moderate"
            description = "Moderate"
        elif lux < 750:
            condition = "bright"
            description = "Bright"
        else:
            condition = "very_bright"
            description = "Very Bright"
        
        return {
            "condition": condition,
            "description": description,
            "lux": lux,
            "recommendation": self._get_lighting_recommendation(condition)
        }
    
    def _get_lighting_recommendation(self, condition: str) -> str:
        """Get lighting recommendation based on condition"""
        recommendations = {
            "very_dark": "Consider increasing ambient lighting",
            "dark": "Low light - good for evening ambiance",
            "dim": "Comfortable dim lighting",
            "moderate": "Optimal lighting level",
            "bright": "Bright and energetic",
            "very_bright": "Very bright - may be too intense"
        }
        return recommendations.get(condition, "")
    
    def start_monitoring(self, camera_index: int = 0, interval: int = 30):
        """Start continuous light monitoring.

        When PULSE_LIGHT_SOURCE != 'camera', reads brightness from
        the latest snapshot file to avoid camera contention.
        """
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        thread = Thread(target=self._monitoring_loop, args=(camera_index, interval))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started light monitoring (interval: {interval}s)")
    
    def _monitoring_loop(self, camera_index: int, interval: int):
        """Main monitoring loop"""
        camera = None
        use_picamera = False
        source = os.getenv('PULSE_LIGHT_SOURCE', 'snapshot').strip().lower()
        
        try:
            if source != 'camera':
                # Snapshot mode: read brightness from saved JPEGs
                while self.running and not self.stop_event.is_set():
                    try:
                        if os.path.exists(self.snapshot_path):
                            frame = cv2.imread(self.snapshot_path)
                            if frame is not None:
                                lux = self.calculate_brightness(frame)
                                self.light_level = lux
                                self.brightness_history.append(lux)
                                if len(self.brightness_history) > self.max_history:
                                    self.brightness_history.pop(0)
                                analysis = self.analyze_lighting_conditions(lux)
                                logger.debug(f"Light level: {lux:.1f} lux ({analysis['description']}) [snapshot]")
                        else:
                            logger.debug("Snapshot not found yet; waiting for people counter to write one")

                        self.stop_event.wait(interval)
                    except Exception as e:
                        logger.error(f"Error in snapshot monitoring loop: {e}")
                        self.stop_event.wait(interval)
                logger.info("Light monitoring stopped (snapshot mode)")
                return

            # Try picamera2 first (camera mode)
            try:
                from picamera2 import Picamera2
                camera = Picamera2()
                config = camera.create_still_configuration()
                camera.configure(config)
                camera.start()
                use_picamera = True
                logger.info("Using Picamera2 for light sensing")
            except Exception as e:
                logger.info(f"Picamera2 not available: {e}, using USB camera")
                camera = cv2.VideoCapture(camera_index)
                use_picamera = False
            
            while self.running and not self.stop_event.is_set():
                try:
                    # Capture frame
                    if use_picamera:
                        frame = camera.capture_array()
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    else:
                        ret, frame = camera.read()
                        if not ret:
                            logger.error("Failed to read frame")
                            break
                    
                    # Calculate brightness
                    lux = self.calculate_brightness(frame)
                    self.light_level = lux
                    
                    # Update history
                    self.brightness_history.append(lux)
                    if len(self.brightness_history) > self.max_history:
                        self.brightness_history.pop(0)
                    
                    # Analyze conditions
                    analysis = self.analyze_lighting_conditions(lux)
                    
                    logger.debug(f"Light level: {lux:.1f} lux ({analysis['description']})")
                    
                    # Wait for next reading
                    self.stop_event.wait(interval)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    self.stop_event.wait(interval)
            
            logger.info("Light monitoring stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
            self.running = False
        finally:
            if camera:
                if use_picamera:
                    camera.stop()
                else:
                    camera.release()
    
    def stop_monitoring(self):
        """Stop light monitoring"""
        self.running = False
        self.stop_event.set()
    
    def get_light_level(self) -> float:
        """Get current light level"""
        return self.light_level
    
    def get_average_light_level(self, samples: int = 10) -> float:
        """Get average light level from recent history"""
        if not self.brightness_history:
            return 0.0
        
        recent = self.brightness_history[-samples:]
        return round(np.mean(recent), 1)
    
    def get_stats(self) -> dict:
        """Get light statistics"""
        analysis = self.analyze_lighting_conditions(self.light_level)
        
        return {
            "current_lux": self.light_level,
            "average_lux": self.get_average_light_level(),
            "condition": analysis["condition"],
            "description": analysis["description"],
            "recommendation": analysis["recommendation"],
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    sensor = LightSensor()
    
    try:
        sensor.start_monitoring(interval=5)
        
        import time
        while True:
            time.sleep(10)
            stats = sensor.get_stats()
            print(f"\nLight Level: {stats['current_lux']:.1f} lux "
                  f"(Avg: {stats['average_lux']:.1f})")
            print(f"Condition: {stats['description']}")
            print(f"Recommendation: {stats['recommendation']}")
    except KeyboardInterrupt:
        print("\nStopping...")
        sensor.stop_monitoring()
