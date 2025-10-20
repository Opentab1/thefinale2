"""
Pulse 1.0 - Camera-based People Counting
Uses computer vision to detect and count people in venue
Integrated with party_box implementations for production-ready AI counting
"""

import logging
import cv2
import numpy as np
from threading import Thread, Event
from datetime import datetime
from typing import Optional, Tuple
import os
from .detector.person_detector import PersonDetector
from .tracker.person_tracker import PersonTracker

logger = logging.getLogger(__name__)

class PeopleCounter:
    def __init__(self, use_ai_hat: bool = True, confidence_threshold: float = 0.5, model_type: str = "hog"):
        """
        Initialize people counter with advanced detection and tracking
        
        Args:
            use_ai_hat: Try to use AI HAT acceleration if available
            confidence_threshold: Minimum confidence for detections
            model_type: Detection model to use (hog, ssd, yolo, hailo)
        """
        self.confidence_threshold = confidence_threshold
        self.running = False
        self.stop_event = Event()
        self.current_count = 0
        self.entry_count = 0
        self.exit_count = 0
        self._last_snapshot_ts = 0.0
        self._snapshot_interval_seconds = 1.0
        self._snapshot_path = "/opt/pulse/data/latest_camera.jpg"

        # Determine model type
        if use_ai_hat and os.path.exists('/dev/hailo0'):
            self.model_type = "hailo"
            logger.info("Using Hailo AI accelerator for people detection")
        elif model_type:
            self.model_type = model_type
        else:
            self.model_type = "hog"  # Default fallback

        # Initialize detector with party_box implementation
        self.detector = PersonDetector(
            confidence_threshold=self.confidence_threshold,
            model_type=self.model_type
        )
        logger.info(f"Initialized detector with model: {self.model_type}")

        # Initialize tracker with party_box implementation
        self.tracker = PersonTracker(
            confidence_threshold=self.confidence_threshold,
            min_detection_frames=5
        )
        logger.info("Initialized person tracker")

        # Ensure snapshot directory exists
        try:
            os.makedirs(os.path.dirname(self._snapshot_path), exist_ok=True)
        except Exception:
            pass
    
    def detect_people(self, frame: np.ndarray) -> Tuple[int, list, list]:
        """
        Detect people in frame using party_box detector
        
        Returns:
            Tuple of (count, boxes, detections)
        """
        try:
            # Use party_box detector
            detections = self.detector.detect_people(frame)
            
            # Extract boxes
            boxes = [d['box'] for d in detections]
            count = len(detections)
            
            return count, boxes, detections
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return 0, [], []
    
    def start_counting(self, camera_index: int = 0, zone: str = "Main Floor"):
        """Start continuous people counting"""
        if self.running:
            logger.warning("Counter already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        thread = Thread(target=self._counting_loop, args=(camera_index, zone))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started people counting for zone: {zone}")
    
    def _counting_loop(self, camera_index: int, zone: str):
        """Main counting loop with party_box integration"""
        try:
            # Try picamera2 first (Raspberry Pi camera)
            try:
                from picamera2 import Picamera2
                camera = Picamera2()
                # Use video configuration for continuous capture
                try:
                    config = camera.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
                except Exception:
                    config = camera.create_still_configuration()
                camera.configure(config)
                camera.start()
                use_picamera = True
                logger.info("Using Picamera2")
            except Exception as e:
                logger.info(f"Picamera2 not available: {e}, using USB camera")
                camera = cv2.VideoCapture(camera_index)
                use_picamera = False
            
            frame_count = 0
            
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
                    
                    # Process every Nth frame to reduce CPU load
                    frame_count += 1
                    if frame_count % 2 != 0:  # Process every other frame
                        continue
                    
                    # Detect people using party_box detector
                    raw_count, boxes, detections = self.detect_people(frame)

                    # Update tracker for stable counts and entry/exit tracking
                    annotated_frame, stats = self.tracker.process_detections(detections, frame)
                    
                    # Update counts from tracker
                    self.current_count = int(stats.get('current', 0))
                    self.entry_count = int(stats.get('entries', 0))
                    self.exit_count = int(stats.get('exits', 0))
                    
                    logger.debug(f"Current: {self.current_count}, Entries: {self.entry_count}, Exits: {self.exit_count}")

                    # Save snapshot for dashboard
                    self._maybe_save_snapshot(annotated_frame)
                    
                except Exception as e:
                    logger.error(f"Error in counting loop: {e}")
                
            # Cleanup
            if use_picamera:
                camera.stop()
            else:
                camera.release()
            
            logger.info("People counting stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in counting loop: {e}")
            self.running = False
    
    def stop_counting(self):
        """Stop people counting"""
        self.running = False
        self.stop_event.set()
        
        # Cleanup detector resources
        try:
            self.detector.cleanup()
        except Exception as e:
            logger.warning(f"Error cleaning up detector: {e}")
    
    def get_current_count(self) -> int:
        """Get current people count"""
        return self.current_count
    
    def get_traffic_stats(self) -> dict:
        """Get entry/exit statistics"""
        return {
            "current_count": self.current_count,
            "entry_count": self.entry_count,
            "exit_count": self.exit_count,
            "timestamp": datetime.now().isoformat()
        }
    
    def reset_stats(self):
        """Reset entry/exit counters"""
        self.tracker.reset_counts()
        self.entry_count = 0
        self.exit_count = 0
        self.current_count = 0

    def _maybe_save_snapshot(self, frame: np.ndarray):
        """Save a JPEG snapshot to disk at a throttled interval."""
        try:
            now = datetime.now().timestamp()
            if (now - self._last_snapshot_ts) < self._snapshot_interval_seconds:
                return
            # Encode JPEG
            ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                return
            with open(self._snapshot_path, 'wb') as f:
                f.write(buf.tobytes())
            self._last_snapshot_ts = now
        except Exception as e:
            logger.debug(f"Snapshot save failed: {e}")
    
    def get_fps(self) -> float:
        """Get current detection FPS"""
        try:
            return self.detector.get_fps()
        except:
            return 0.0
    
    def set_model(self, model_type: str) -> bool:
        """
        Change the detection model
        
        Args:
            model_type: New model type (hog, ssd, yolo, hailo)
            
        Returns:
            bool: True if successful
        """
        try:
            success = self.detector.set_model(model_type)
            if success:
                self.model_type = model_type
                logger.info(f"Switched to model: {model_type}")
            return success
        except Exception as e:
            logger.error(f"Error switching model: {e}")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    counter = PeopleCounter(use_ai_hat=False, model_type="hog")
    
    try:
        counter.start_counting()
        
        import time
        while True:
            time.sleep(5)
            stats = counter.get_traffic_stats()
            print(f"Current: {stats['current_count']}, "
                  f"Entry: {stats['entry_count']}, "
                  f"Exit: {stats['exit_count']}, "
                  f"FPS: {counter.get_fps():.1f}")
    except KeyboardInterrupt:
        print("\nStopping...")
        counter.stop_counting()
