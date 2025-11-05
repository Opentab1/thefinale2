#!/usr/bin/env python3
"""
simple_decibel_detector.py - Simple, reliable decibel level detection

Based on proven party_box approach - runs independently with no complex watchdogs.
Records short audio samples and calculates dB levels.

Key principles:
- Simple daemon thread (no watchdogs needed)
- Short recordings (0.2s) to avoid conflicts
- Direct calculation (no event loops)
- Clean, proven approach
"""

import time
import logging
import threading
import numpy as np
import math
from datetime import datetime

# Try to import sound-related libraries
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice library not available. Install with 'pip install sounddevice'")

logger = logging.getLogger(__name__)

class DecibelDetector:
    """Simple, reliable decibel level detector"""
    
    def __init__(self, enabled=True, update_interval=10, reference_pressure=0.00002):
        """
        Initialize the decibel detector
        
        Args:
            enabled: Whether decibel detection is enabled
            update_interval: Seconds between measurements (default: 10)
            reference_pressure: Reference pressure for dB calculation (default: 0.00002 Pa or 20µPa)
        """
        self.enabled = enabled and SOUNDDEVICE_AVAILABLE
        
        if self.enabled:
            logger.info("✅ Decibel detection enabled (update interval: %ds)", update_interval)
        else:
            if not SOUNDDEVICE_AVAILABLE:
                logger.warning("⚠️ sounddevice not available. Decibel detection disabled.")
        
        # Audio parameters
        self.sample_rate = 44100
        self.channels = 1
        self.duration = 0.2  # Short recording (0.2s) to avoid conflicts
        self.reference_pressure = reference_pressure
        
        # Detection state
        self.latest_reading = {"db_value": 0, "timestamp": None}
        self.detection_thread = None
        self.detection_active = False
        self.last_detection_time = 0
        self.update_interval = update_interval
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Start detection thread if enabled
        if self.enabled:
            self.start_detection_thread()

    def start_detection_thread(self):
        """Start background thread for decibel detection"""
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_active = True
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                name="DecibelDetector",
                daemon=True
            )
            self.detection_thread.start()
            logger.info("✅ Decibel detection thread started")
    
    def _detection_loop(self):
        """Background thread for periodic decibel detection"""
        logger.info("🔊 Decibel detection loop started")
        
        while self.detection_active:
            try:
                # Check if it's time for a new detection
                current_time = time.time()
                if current_time - self.last_detection_time >= self.update_interval:
                    self.measure_decibel()
                    self.last_detection_time = current_time
                
                # Sleep to avoid consuming CPU
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in decibel detection loop: {e}")
                time.sleep(5)  # Wait longer on error
    
    def measure_decibel(self):
        """Record audio and calculate decibel level"""
        if not self.enabled:
            return
            
        try:
            # Record audio sample
            logger.debug(f"Recording {self.duration}s audio clip for decibel calculation...")
            
            try:
                recording = sd.rec(
                    int(self.duration * self.sample_rate),
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32'
                )
                sd.wait()  # Wait for recording to complete
                
            except Exception as e:
                logger.error(f"Error during audio recording: {e}")
                return
            
            # Calculate RMS value with protection against NaN and Inf
            try:
                # Clip any extreme values
                recording = np.clip(recording, -1.0, 1.0)
                
                # Calculate RMS with protection
                squared = np.square(recording)
                mean_squared = np.mean(squared) if squared.size > 0 else 0.0
                rms = np.sqrt(mean_squared) if mean_squared > 0 else 0.0
                
                # Safety check for NaN or Inf
                if not np.isfinite(rms):
                    rms = 0.0
                    
            except Exception as e:
                logger.error(f"Error calculating RMS: {e}")
                rms = 0.0
            
            # Convert to decibels
            if rms > 0:  # Avoid log of zero
                db_value = 20 * math.log10(rms / self.reference_pressure)
            else:
                db_value = 0
            
            # Apply adjustment for rough calibration (calibrated for typical USB microphones)
            # Offset reduced from +40 to -10 based on real-world testing
            # Max raised from 100 to 150 to accommodate full dB range
            adjusted_db = max(0, min(150, db_value - 10))  # Adjusted offset and cap at 150dB
            
            # Update latest reading
            with self.lock:
                self.latest_reading = {
                    "db_value": round(adjusted_db, 1),
                    "timestamp": time.time(),
                    "datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
            logger.info(f"🔊 Measured decibel level: {adjusted_db:.1f} dB")
            
        except Exception as e:
            logger.error(f"Error measuring decibel level: {e}")
    
    def get_latest_reading(self):
        """Get the latest decibel reading"""
        with self.lock:
            return self.latest_reading.copy()
    
    def get_current_db(self):
        """Get current dB value (for backward compatibility)"""
        return self.get_latest_reading().get("db_value", 0.0)
    
    def stop(self):
        """Stop decibel detection thread"""
        logger.info("Stopping decibel detector...")
        self.detection_active = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=3.0)
            if self.detection_thread.is_alive():
                logger.warning("Decibel detection thread did not stop gracefully")
            else:
                logger.info("✅ Decibel detection thread stopped")


# Module test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting decibel detector test")
    
    # Create detector
    detector = DecibelDetector(
        enabled=True,
        update_interval=10
    )
    
    try:
        # Run for 60 seconds and print readings
        logger.info("Running test for 60 seconds...")
        for i in range(6):
            time.sleep(10)
            reading = detector.get_latest_reading()
            logger.info(f"Decibel reading: {reading['db_value']:.1f} dB at {reading.get('datetime', 'N/A')}")
    
    except KeyboardInterrupt:
        logger.info("Test interrupted")
    finally:
        detector.stop()
        logger.info("Test complete")
