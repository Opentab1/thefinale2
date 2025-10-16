"""
Pulse 1.0 - Pan-Tilt HAT Controller
Controls camera motion for better people counting coverage
"""

import logging
import time
from typing import Tuple
import math

logger = logging.getLogger(__name__)

class PanTiltController:
    def __init__(self, pan_pin: int = 12, tilt_pin: int = 13):
        self.pan_pin = pan_pin
        self.tilt_pin = tilt_pin
        
        self.pan_angle = 90  # Center position
        self.tilt_angle = 90  # Center position
        
        self.pan_min = 0
        self.pan_max = 180
        self.tilt_min = 45  # Prevent looking too far down
        self.tilt_max = 135  # Prevent looking too far up
        
        self.pwm_pan = None
        self.pwm_tilt = None
        
        self._init_servos()
    
    def _init_servos(self):
        """Initialize servo motors"""
        try:
            import RPi.GPIO as GPIO
            
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Setup PWM pins
            GPIO.setup(self.pan_pin, GPIO.OUT)
            GPIO.setup(self.tilt_pin, GPIO.OUT)
            
            # 50Hz PWM frequency for servos
            self.pwm_pan = GPIO.PWM(self.pan_pin, 50)
            self.pwm_tilt = GPIO.PWM(self.tilt_pin, 50)
            
            # Start PWM
            self.pwm_pan.start(0)
            self.pwm_tilt.start(0)
            
            # Move to center position
            self.center()
            
            logger.info("Pan-Tilt servos initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize servos: {e}")
            raise
    
    def _angle_to_duty_cycle(self, angle: float) -> float:
        """Convert angle to PWM duty cycle"""
        # Standard servo: 0° = 2.5% duty, 180° = 12.5% duty
        duty = 2.5 + (angle / 180.0) * 10.0
        return duty
    
    def set_pan(self, angle: float, smooth: bool = False):
        """Set pan angle"""
        try:
            # Clamp angle
            angle = max(self.pan_min, min(self.pan_max, angle))
            
            if smooth and abs(angle - self.pan_angle) > 5:
                # Smooth movement
                self._smooth_move_pan(angle)
            else:
                # Direct movement
                duty = self._angle_to_duty_cycle(angle)
                self.pwm_pan.ChangeDutyCycle(duty)
                time.sleep(0.3)
                self.pwm_pan.ChangeDutyCycle(0)  # Stop sending signal
                self.pan_angle = angle
            
            logger.debug(f"Pan set to {angle}°")
            
        except Exception as e:
            logger.error(f"Error setting pan: {e}")
    
    def set_tilt(self, angle: float, smooth: bool = False):
        """Set tilt angle"""
        try:
            # Clamp angle
            angle = max(self.tilt_min, min(self.tilt_max, angle))
            
            if smooth and abs(angle - self.tilt_angle) > 5:
                # Smooth movement
                self._smooth_move_tilt(angle)
            else:
                # Direct movement
                duty = self._angle_to_duty_cycle(angle)
                self.pwm_tilt.ChangeDutyCycle(duty)
                time.sleep(0.3)
                self.pwm_tilt.ChangeDutyCycle(0)  # Stop sending signal
                self.tilt_angle = angle
            
            logger.debug(f"Tilt set to {angle}°")
            
        except Exception as e:
            logger.error(f"Error setting tilt: {e}")
    
    def _smooth_move_pan(self, target_angle: float):
        """Smoothly move pan to target angle"""
        steps = 10
        current = self.pan_angle
        step_size = (target_angle - current) / steps
        
        for i in range(steps):
            intermediate = current + (step_size * (i + 1))
            duty = self._angle_to_duty_cycle(intermediate)
            self.pwm_pan.ChangeDutyCycle(duty)
            time.sleep(0.05)
        
        self.pwm_pan.ChangeDutyCycle(0)
        self.pan_angle = target_angle
    
    def _smooth_move_tilt(self, target_angle: float):
        """Smoothly move tilt to target angle"""
        steps = 10
        current = self.tilt_angle
        step_size = (target_angle - current) / steps
        
        for i in range(steps):
            intermediate = current + (step_size * (i + 1))
            duty = self._angle_to_duty_cycle(intermediate)
            self.pwm_tilt.ChangeDutyCycle(duty)
            time.sleep(0.05)
        
        self.pwm_tilt.ChangeDutyCycle(0)
        self.tilt_angle = target_angle
    
    def set_position(self, pan: float, tilt: float, smooth: bool = False):
        """Set both pan and tilt"""
        self.set_pan(pan, smooth)
        self.set_tilt(tilt, smooth)
    
    def center(self):
        """Move to center position"""
        self.set_position(90, 90, smooth=False)
        logger.info("Moved to center position")
    
    def get_position(self) -> Tuple[float, float]:
        """Get current position"""
        return (self.pan_angle, self.tilt_angle)
    
    def scan_horizontal(self, steps: int = 5, delay: float = 2.0):
        """Perform horizontal scan"""
        logger.info("Starting horizontal scan")
        
        # Calculate step size
        range_size = self.pan_max - self.pan_min
        step_size = range_size / (steps - 1)
        
        positions = []
        for i in range(steps):
            angle = self.pan_min + (i * step_size)
            positions.append(angle)
        
        # Scan
        for angle in positions:
            self.set_pan(angle, smooth=True)
            time.sleep(delay)
        
        # Return to center
        self.center()
        
        logger.info("Horizontal scan complete")
    
    def scan_grid(self, pan_steps: int = 3, tilt_steps: int = 3, delay: float = 1.5):
        """Perform grid scan pattern"""
        logger.info("Starting grid scan")
        
        # Calculate positions
        pan_range = self.pan_max - self.pan_min
        tilt_range = self.tilt_max - self.tilt_min
        
        pan_step_size = pan_range / (pan_steps - 1) if pan_steps > 1 else 0
        tilt_step_size = tilt_range / (tilt_steps - 1) if tilt_steps > 1 else 0
        
        # Scan pattern
        for t in range(tilt_steps):
            tilt_angle = self.tilt_min + (t * tilt_step_size)
            
            # Alternate scan direction for efficiency
            pan_positions = range(pan_steps) if t % 2 == 0 else range(pan_steps - 1, -1, -1)
            
            for p in pan_positions:
                pan_angle = self.pan_min + (p * pan_step_size)
                self.set_position(pan_angle, tilt_angle, smooth=True)
                time.sleep(delay)
        
        # Return to center
        self.center()
        
        logger.info("Grid scan complete")
    
    def track_target(self, x: float, y: float, frame_width: int, frame_height: int):
        """
        Track a target in the frame
        x, y: target coordinates in frame
        frame_width, frame_height: frame dimensions
        """
        # Calculate offset from center
        center_x = frame_width / 2
        center_y = frame_height / 2
        
        offset_x = x - center_x
        offset_y = y - center_y
        
        # Convert to angle adjustments (simple proportional control)
        # Adjust these gains based on actual camera FOV
        pan_gain = 0.05
        tilt_gain = 0.05
        
        pan_adjust = offset_x * pan_gain
        tilt_adjust = -offset_y * tilt_gain  # Negative because image y is inverted
        
        # Apply adjustments
        new_pan = self.pan_angle + pan_adjust
        new_tilt = self.tilt_angle + tilt_adjust
        
        self.set_position(new_pan, new_tilt, smooth=True)
    
    def cleanup(self):
        """Cleanup GPIO resources"""
        try:
            if self.pwm_pan:
                self.pwm_pan.stop()
            if self.pwm_tilt:
                self.pwm_tilt.stop()
            
            import RPi.GPIO as GPIO
            GPIO.cleanup([self.pan_pin, self.tilt_pin])
            
            logger.info("Pan-Tilt cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        controller = PanTiltController()
        
        print("Testing pan-tilt controller...")
        
        # Center
        print("Moving to center...")
        controller.center()
        time.sleep(2)
        
        # Test pan
        print("Testing pan...")
        controller.set_pan(0)
        time.sleep(1)
        controller.set_pan(180)
        time.sleep(1)
        controller.center()
        time.sleep(1)
        
        # Test tilt
        print("Testing tilt...")
        controller.set_tilt(45)
        time.sleep(1)
        controller.set_tilt(135)
        time.sleep(1)
        controller.center()
        time.sleep(1)
        
        # Scan
        print("Performing horizontal scan...")
        controller.scan_horizontal(steps=5, delay=1.5)
        
        print("Test complete!")
        
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        controller.cleanup()
