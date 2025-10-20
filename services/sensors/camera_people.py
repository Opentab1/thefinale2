"""
Pulse 1.0 - Camera-based People Counting
Uses computer vision to detect and count people in venue
Integrated with party_box-inspired implementations for production-ready AI counting
"""

import logging
import cv2
import numpy as np
from threading import Thread, Event
from datetime import datetime
from typing import Optional, Tuple
import os
from .person_tracker_adapter import PersonTracker
try:
    from .person_detector import PersonDetector
except Exception:
    PersonDetector = None

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

        # Determine model type hint
        self.model_type = model_type or "hog"
        self.use_ai_hat = use_ai_hat

        # Initialize detector (party_box-inspired)
        self.detector = None
        self._init_detector()

        # Initialize tracker (party_box-inspired)
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
    
    def _init_detector(self):
        """Initialize person detection model (prefers AI hat > SSD > HOG)."""
        try:
            if self.use_ai_hat and (os.path.exists('/dev/hailo0') or os.path.exists('/dev/apex_0')):
                logger.info("AI HAT present; detector will use accelerator when available")
            # Prefer lightweight PersonDetector wrapper; falls back internally
            if PersonDetector is not None:
                self.detector = PersonDetector(
                    confidence_threshold=self.confidence_threshold,
                    model_type=self.model_type,
                )
                logger.info(f"Initialized detector with model: {self.model_type}")
                return
        except Exception as e:
            logger.warning(f"Preferred detector unavailable: {e}")
        # As last resort fallback to simple motion subtractor to prevent crashes
        try:
            self.detector = cv2.HOGDescriptor()
            self.detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            logger.info("Initialized HOG detector as fallback")
        except Exception as e:
            logger.error(f"Failed to initialize HOG; falling back to motion: {e}")
            self.detector = cv2.createBackgroundSubtractorMOG2()
    
    def _init_ai_hat_detector(self):
        """Initialize AI HAT accelerated detector if hardware present.

        Falls back by raising if no supported accelerator is found.
        """
        try:
            if not (os.path.exists('/dev/hailo0') or os.path.exists('/dev/apex_0')):
                raise RuntimeError("AI HAT device not found")
            # Placeholder for actual AI HAT integration
            logger.info("AI HAT detector initialized")
            # No-op; acceleration handled within specific backends
            self.detector = self.detector or None
        except Exception as e:
            # Propagate to allow CPU fallback in _init_detector
            raise e
    
    def _init_cpu_detector(self):
        """Initialize CPU-based detector; prefer PersonDetector when available."""
        if PersonDetector is not None:
            try:
                self.detector = PersonDetector(confidence_threshold=self.confidence_threshold, model_type="ssd")
                logger.info("CPU detector initialized (PersonDetector)")
                return
            except Exception as e:
                logger.warning(f"PersonDetector unavailable: {e}")
        try:
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
            self.detector = cv2.createBackgroundSubtractorMOG2()
    
    def detect_people(self, frame: np.ndarray) -> Tuple[int, list, list]:
        """Detect people in frame and return (count, boxes, detections)."""
        try:
            # party_box-inspired detector path
            if PersonDetector is not None and isinstance(self.detector, PersonDetector):
                count, boxes, detections = self._detect_party(self.detector, frame)
                return count, boxes, detections
            elif isinstance(self.detector, cv2.HOGDescriptor):
                count, boxes = self._detect_hog(frame)
                detections = [{'box': tuple(b), 'confidence': 0.6} for b in boxes]
                return count, boxes, detections
            elif isinstance(self.detector, cv2.dnn_Net):
                count, boxes = self._detect_dnn(frame)
                detections = [{'box': tuple(b), 'confidence': 0.6} for b in boxes]
                return count, boxes, detections
            elif self.detector == "ai_hat":
                count, boxes = self._detect_ai_hat(frame)
                detections = [{'box': tuple(b), 'confidence': 0.8} for b in boxes]
                return count, boxes, detections
            else:
                count, boxes = self._detect_motion(frame)
                detections = [{'box': tuple(b), 'confidence': 0.5} for b in boxes]
                return count, boxes, detections
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return 0, [], []
    
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

    def _detect_party(self, detector: "PersonDetector", frame: np.ndarray) -> Tuple[int, list, list]:
        """Detect via party_box PersonDetector."""
        try:
            results = detector.detect_people(frame) or []
            boxes = [list(map(int, d.get('box', (0, 0, 0, 0)))) for d in results]
            detections = [
                {
                    'box': tuple(list(map(int, d.get('box', (0, 0, 0, 0))))),
                    'confidence': float(d.get('confidence', self.confidence_threshold)),
                }
                for d in results
            ]
            return len(boxes), boxes, detections
        except Exception as e:
            logger.error(f"Party detector error: {e}")
            return 0, [], []
    
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
        """Main counting loop with party_box-inspired integration"""
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
                    
                    # Detect people
                    raw_count, boxes, detections = self.detect_people(frame)

                    # Update tracker for stable counts and entry/exit tracking
                    annotated_frame, stats = self.tracker.process_detections(detections, frame)
                    self.current_count = int(stats.get('current', raw_count))
                    self.entry_count = int(stats.get('entries', self.entry_count))
                    self.exit_count = int(stats.get('exits', self.exit_count))
                    logger.debug(
                        f"Count: {self.current_count}, Entry: {self.entry_count}, Exit: {self.exit_count}"
                    )

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
