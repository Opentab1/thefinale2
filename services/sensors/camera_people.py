"""
Pulse 1.0 - Camera-based People Counting
Uses computer vision to detect and count people in venue
"""

import logging
import cv2
import numpy as np
from threading import Thread, Event
from datetime import datetime
from typing import Optional, Tuple
import os

logger = logging.getLogger(__name__)

class PeopleCounter:
    def __init__(self, use_ai_hat: bool = True, confidence_threshold: float = 0.5):
        self.use_ai_hat = use_ai_hat
        self.confidence_threshold = confidence_threshold
        self.running = False
        self.stop_event = Event()
        self.current_count = 0
        self.entry_count = 0
        self.exit_count = 0
        self._last_snapshot_ts = 0.0
        self._snapshot_interval_seconds = 1.0
        self._snapshot_path = "/opt/pulse/data/latest_camera.jpg"

        # Initialize detector
        self.detector = None
        self._init_detector()

        # Ensure snapshot directory exists
        try:
            os.makedirs(os.path.dirname(self._snapshot_path), exist_ok=True)
        except Exception:
            pass
    
    def _init_detector(self):
        """Initialize person detection model"""
        try:
            if self.use_ai_hat:
                # Try to use AI HAT acceleration
                try:
                    # Placeholder for Hailo or other AI accelerator
                    logger.info("Attempting to use AI HAT for acceleration")
                    self._init_ai_hat_detector()
                except Exception as e:
                    logger.warning(f"AI HAT not available, falling back to CPU: {e}")
                    self._init_cpu_detector()
            else:
                self._init_cpu_detector()
        except Exception as e:
            logger.error(f"Failed to initialize detector: {e}")
            raise
    
    def _init_ai_hat_detector(self):
        """Initialize AI HAT accelerated detector if hardware present.

        Falls back by raising if no supported accelerator is found.
        """
        try:
            if not (os.path.exists('/dev/hailo0') or os.path.exists('/dev/apex_0')):
                raise RuntimeError("AI HAT device not found")
            # Placeholder for actual AI HAT integration
            logger.info("AI HAT detector initialized")
            self.detector = "ai_hat"
        except Exception as e:
            # Propagate to allow CPU fallback in _init_detector
            raise e
    
    def _init_cpu_detector(self):
        """Initialize CPU-based detector using OpenCV DNN"""
        try:
            # Use MobileNet SSD for person detection
            model_path = "/opt/pulse/models"
            os.makedirs(model_path, exist_ok=True)
            
            prototxt = os.path.join(model_path, "MobileNetSSD_deploy.prototxt")
            model = os.path.join(model_path, "MobileNetSSD_deploy.caffemodel")
            
            if os.path.exists(prototxt) and os.path.exists(model):
                self.detector = cv2.dnn.readNetFromCaffe(prototxt, model)
                logger.info("CPU detector initialized with MobileNet SSD")
            else:
                logger.warning("Model files not found, using HOG detector")
                self.detector = cv2.HOGDescriptor()
                self.detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        except Exception as e:
            logger.error(f"Failed to initialize CPU detector: {e}")
            # Fallback to simple background subtraction
            self.detector = cv2.createBackgroundSubtractorMOG2()
    
    def detect_people(self, frame: np.ndarray) -> Tuple[int, list]:
        """Detect people in frame and return count with bounding boxes"""
        try:
            if isinstance(self.detector, cv2.HOGDescriptor):
                return self._detect_hog(frame)
            elif isinstance(self.detector, cv2.dnn_Net):
                return self._detect_dnn(frame)
            elif self.detector == "ai_hat":
                return self._detect_ai_hat(frame)
            else:
                # Background subtraction fallback
                return self._detect_motion(frame)
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return 0, []
    
    def _detect_hog(self, frame: np.ndarray) -> Tuple[int, list]:
        """Detect using HOG descriptor"""
        try:
            # Resize for faster processing
            scale = 0.5
            resized = cv2.resize(frame, None, fx=scale, fy=scale)
            
            boxes, weights = self.detector.detectMultiScale(
                resized,
                winStride=(4, 4),
                padding=(8, 8),
                scale=1.05
            )
            
            # Scale boxes back to original size
            boxes = [[int(x/scale), int(y/scale), int(w/scale), int(h/scale)] 
                    for x, y, w, h in boxes]
            
            return len(boxes), boxes
        except Exception as e:
            logger.error(f"HOG detection error: {e}")
            return 0, []
    
    def _detect_dnn(self, frame: np.ndarray) -> Tuple[int, list]:
        """Detect using DNN model"""
        try:
            h, w = frame.shape[:2]
            blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
            
            self.detector.setInput(blob)
            detections = self.detector.forward()
            
            boxes = []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                
                if confidence > self.confidence_threshold:
                    # Class 15 is person in MobileNet SSD
                    class_id = int(detections[0, 0, i, 1])
                    if class_id == 15:
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        boxes.append(box.astype(int).tolist())
            
            return len(boxes), boxes
        except Exception as e:
            logger.error(f"DNN detection error: {e}")
            return 0, []
    
    def _detect_ai_hat(self, frame: np.ndarray) -> Tuple[int, list]:
        """Detect using AI HAT"""
        # Placeholder for actual AI HAT implementation
        # Would use hailo-tappas or similar framework
        logger.debug("AI HAT detection placeholder")
        return 0, []
    
    def _detect_motion(self, frame: np.ndarray) -> Tuple[int, list]:
        """Simple motion-based detection (fallback)"""
        try:
            fg_mask = self.detector.apply(frame)
            
            # Find contours
            contours, _ = cv2.findContours(
                fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            
            # Filter by size
            min_area = 2000
            valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
            
            boxes = [cv2.boundingRect(c) for c in valid_contours]
            
            return len(boxes), boxes
        except Exception as e:
            logger.error(f"Motion detection error: {e}")
            return 0, []
    
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
        """Main counting loop"""
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
                    if frame_count % 3 != 0:
                        continue
                    
                    # Detect people
                    count, boxes = self.detect_people(frame)
                    
                    # Update count (simple approach - actual implementation would track individuals)
                    prev_count = self.current_count
                    self.current_count = count
                    
                    # Estimate entry/exit (simplified)
                    if count > prev_count:
                        self.entry_count += (count - prev_count)
                    elif count < prev_count:
                        self.exit_count += (prev_count - count)
                    
                    logger.debug(f"Count: {count}, Entry: {self.entry_count}, Exit: {self.exit_count}")

                    # Opportunistically save a recent snapshot for the dashboard
                    self._maybe_save_snapshot(frame)
                    
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
        self.entry_count = 0
        self.exit_count = 0

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    counter = PeopleCounter(use_ai_hat=False)
    
    try:
        counter.start_counting()
        
        import time
        while True:
            time.sleep(5)
            stats = counter.get_traffic_stats()
            print(f"Current: {stats['current_count']}, "
                  f"Entry: {stats['entry_count']}, "
                  f"Exit: {stats['exit_count']}")
    except KeyboardInterrupt:
        print("\nStopping...")
        counter.stop_counting()
