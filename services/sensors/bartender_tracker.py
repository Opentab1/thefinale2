"""
Pulse 1.0 - AI Bartender Drink Counter
Tracks individual bartenders and drinks made using computer vision

This is a NEW module - does not interfere with existing sensors
"""

import logging
import cv2
import numpy as np
from threading import Thread, Event, Lock
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import os
import time

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    logging.warning("face_recognition not available - bartender ID will use position-based tracking only")

logger = logging.getLogger(__name__)


class BartenderTracker:
    """
    Tracks bartenders and counts drinks made in real-time
    Uses face recognition + position tracking for bartender identification
    """
    
    def __init__(self, camera_index: int = 0):
        """Initialize bartender tracker"""
        self.camera_index = camera_index
        self.running = False
        self.stop_event = Event()
        
        # Bartender database
        self.bartenders = {}  # {id: {'name': str, 'face_encoding': array, 'drinks_today': int}}
        self.next_bartender_id = 1
        
        # Current detections
        self.current_bartenders = []  # List of detected bartenders in frame
        self.drinks_per_bartender = {}  # {bartender_id: drink_count}
        
        # Drink detection zones
        self.bar_zones = []  # List of (x, y, w, h) rectangles
        self.last_drink_time = {}  # {bartender_id: timestamp}
        self.min_time_between_drinks = 30  # seconds
        
        # Performance tracking
        self.total_drinks_today = 0
        self.start_time = datetime.now()
        
        # Face recognition setup
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Snapshot for dashboard
        self._snapshot_path = "/opt/pulse/data/bartender_camera.jpg"
        self._last_snapshot_ts = 0.0
        self._snapshot_interval = 1.0
        
        # Thread safety
        self.data_lock = Lock()
        
        # Ensure data directory exists
        try:
            os.makedirs(os.path.dirname(self._snapshot_path), exist_ok=True)
        except Exception:
            # Fallback to workspace
            self._snapshot_path = os.path.join(os.getcwd(), "data", "bartender_camera.jpg")
            try:
                os.makedirs(os.path.dirname(self._snapshot_path), exist_ok=True)
            except Exception:
                pass
        
        logger.info("Bartender tracker initialized")
    
    def add_bartender(self, name: str, face_image: Optional[np.ndarray] = None) -> int:
        """
        Register a new bartender
        
        Args:
            name: Bartender's name
            face_image: Optional face image for recognition (BGR format)
            
        Returns:
            bartender_id: Unique ID assigned to bartender
        """
        bartender_id = self.next_bartender_id
        self.next_bartender_id += 1
        
        face_encoding = None
        if face_image is not None and FACE_RECOGNITION_AVAILABLE:
            try:
                # Convert BGR to RGB for face_recognition
                rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
                encodings = face_recognition.face_encodings(rgb_image)
                if encodings:
                    face_encoding = encodings[0]
                    logger.info(f"Face encoding created for {name}")
            except Exception as e:
                logger.error(f"Error creating face encoding: {e}")
        
        with self.data_lock:
            self.bartenders[bartender_id] = {
                'name': name,
                'face_encoding': face_encoding,
                'drinks_today': 0,
                'shift_start': datetime.now(),
                'last_seen': None
            }
            self.drinks_per_bartender[bartender_id] = 0
        
        logger.info(f"Registered bartender: {name} (ID: {bartender_id})")
        return bartender_id
    
    def set_bar_zone(self, x: int, y: int, w: int, h: int):
        """
        Define the bar area where drinks are made
        
        Args:
            x, y: Top-left corner
            w, h: Width and height
        """
        with self.data_lock:
            self.bar_zones = [(x, y, w, h)]
        logger.info(f"Bar zone set: ({x}, {y}, {w}, {h})")
    
    def _detect_bartenders(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect bartenders in frame
        
        Returns:
            List of detected bartenders with bounding boxes and IDs
        """
        detections = []
        
        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
        )
        
        # Try to identify each face
        for (x, y, w, h) in faces:
            bartender_id = None
            confidence = 0.0
            name = "Unknown"
            
            # Try face recognition if available
            if FACE_RECOGNITION_AVAILABLE and self.bartenders:
                try:
                    face_crop = frame[y:y+h, x:x+w]
                    rgb_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
                    encodings = face_recognition.face_encodings(rgb_crop)
                    
                    if encodings:
                        face_encoding = encodings[0]
                        
                        # Compare with known bartenders
                        for bid, bartender in self.bartenders.items():
                            if bartender['face_encoding'] is not None:
                                matches = face_recognition.compare_faces(
                                    [bartender['face_encoding']], face_encoding, tolerance=0.6
                                )
                                if matches[0]:
                                    distance = face_recognition.face_distance(
                                        [bartender['face_encoding']], face_encoding
                                    )[0]
                                    conf = 1.0 - distance
                                    if conf > confidence:
                                        bartender_id = bid
                                        confidence = conf
                                        name = bartender['name']
                except Exception as e:
                    logger.debug(f"Face recognition error: {e}")
            
            # Check if person is in bar zone
            in_bar_zone = self._is_in_bar_zone(x, y, w, h)
            
            detections.append({
                'bartender_id': bartender_id,
                'name': name,
                'box': (x, y, w, h),
                'confidence': confidence,
                'in_bar_zone': in_bar_zone,
                'center': (x + w // 2, y + h // 2)
            })
        
        return detections
    
    def _is_in_bar_zone(self, x: int, y: int, w: int, h: int) -> bool:
        """Check if bounding box is in bar zone"""
        if not self.bar_zones:
            return True  # If no zones defined, assume all are in bar
        
        center_x = x + w // 2
        center_y = y + h // 2
        
        for (zx, zy, zw, zh) in self.bar_zones:
            if zx <= center_x <= zx + zw and zy <= center_y <= zy + zh:
                return True
        
        return False
    
    def _detect_drink_made(self, bartender_id: int, detection: Dict) -> bool:
        """
        Detect if bartender just made a drink
        Simple heuristic: person in bar zone + time since last drink
        
        In production, this would use hand tracking/action recognition
        """
        if not detection['in_bar_zone']:
            return False
        
        # Check time since last drink for this bartender
        now = time.time()
        if bartender_id in self.last_drink_time:
            time_since_last = now - self.last_drink_time[bartender_id]
            if time_since_last < self.min_time_between_drinks:
                return False
        
        # Simple placeholder: in this demo, we'll trigger on presence
        # Real implementation would use hand tracking (MediaPipe) or action recognition
        # For now, we manually trigger drinks via API
        
        return False
    
    def record_drink(self, bartender_id: int) -> bool:
        """
        Manually record a drink for a bartender
        
        Args:
            bartender_id: ID of bartender who made the drink
            
        Returns:
            bool: True if successful
        """
        with self.data_lock:
            if bartender_id not in self.bartenders:
                logger.warning(f"Unknown bartender ID: {bartender_id}")
                return False
            
            # Check rate limit
            now = time.time()
            if bartender_id in self.last_drink_time:
                time_since_last = now - self.last_drink_time[bartender_id]
                if time_since_last < 5:  # Min 5 seconds between drinks
                    logger.debug(f"Drink recording rate limited for bartender {bartender_id}")
                    return False
            
            # Record drink
            self.drinks_per_bartender[bartender_id] += 1
            self.bartenders[bartender_id]['drinks_today'] += 1
            self.last_drink_time[bartender_id] = now
            self.total_drinks_today += 1
            
            logger.info(f"Drink recorded: {self.bartenders[bartender_id]['name']} "
                       f"(Total: {self.drinks_per_bartender[bartender_id]})")
            
            return True
    
    def _annotate_frame(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Draw bounding boxes and labels on frame"""
        annotated = frame.copy()
        
        # Draw bar zones
        for (zx, zy, zw, zh) in self.bar_zones:
            cv2.rectangle(annotated, (zx, zy), (zx + zw, zy + zh), (100, 100, 255), 2)
            cv2.putText(annotated, "BAR ZONE", (zx + 5, zy + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)
        
        # Draw bartender detections
        for det in detections:
            x, y, w, h = det['box']
            bartender_id = det['bartender_id']
            name = det['name']
            confidence = det['confidence']
            in_zone = det['in_bar_zone']
            
            # Choose color based on status
            if bartender_id is not None:
                color = (0, 255, 0)  # Green - identified
                label = f"{name} (#{bartender_id})"
                if bartender_id in self.drinks_per_bartender:
                    label += f" - {self.drinks_per_bartender[bartender_id]} drinks"
            elif in_zone:
                color = (0, 255, 255)  # Yellow - in bar zone but unidentified
                label = "Bartender? (Unregistered)"
            else:
                color = (200, 200, 200)  # Gray - person detected
                label = "Person"
            
            # Draw box
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            
            # Draw label background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(annotated, (x, y - label_size[1] - 10), 
                         (x + label_size[0], y), color, -1)
            
            # Draw label text
            cv2.putText(annotated, label, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        # Draw stats overlay
        stats_text = [
            f"Total Drinks Today: {self.total_drinks_today}",
            f"Active Bartenders: {len([d for d in detections if d['bartender_id'] is not None])}"
        ]
        
        y_offset = 30
        for text in stats_text:
            cv2.putText(annotated, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(annotated, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            y_offset += 30
        
        return annotated
    
    def _save_snapshot(self, frame: np.ndarray):
        """Save annotated frame as JPEG snapshot"""
        try:
            now = time.time()
            if (now - self._last_snapshot_ts) < self._snapshot_interval:
                return
            
            ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ok:
                with open(self._snapshot_path, 'wb') as f:
                    f.write(buf.tobytes())
                self._last_snapshot_ts = now
        except Exception as e:
            logger.debug(f"Snapshot save error: {e}")
    
    def start_tracking(self):
        """Start bartender tracking loop"""
        if self.running:
            logger.warning("Bartender tracker already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        thread = Thread(target=self._tracking_loop)
        thread.daemon = True
        thread.start()
        
        logger.info("Bartender tracking started")
    
    def _tracking_loop(self):
        """Main tracking loop"""
        try:
            # Try Picamera2 first
            try:
                from picamera2 import Picamera2
                camera = Picamera2()
                config = camera.create_video_configuration(main={"size": (640, 480), "format": "RGB888"})
                camera.configure(config)
                camera.start()
                use_picamera = True
                logger.info("Using Picamera2 for bartender tracking")
            except Exception as e:
                logger.info(f"Picamera2 not available: {e}, using USB camera")
                camera = cv2.VideoCapture(self.camera_index)
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
                    
                    # Process every other frame to reduce CPU load
                    frame_count += 1
                    if frame_count % 2 != 0:
                        continue
                    
                    # Detect bartenders
                    detections = self._detect_bartenders(frame)
                    
                    with self.data_lock:
                        self.current_bartenders = detections
                        
                        # Update last seen times
                        for det in detections:
                            if det['bartender_id'] is not None:
                                self.bartenders[det['bartender_id']]['last_seen'] = datetime.now()
                    
                    # Annotate frame
                    annotated_frame = self._annotate_frame(frame, detections)
                    
                    # Save snapshot
                    self._save_snapshot(annotated_frame)
                    
                    # Small delay
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error in tracking loop: {e}")
            
            # Cleanup
            if use_picamera:
                camera.stop()
            else:
                camera.release()
            
            logger.info("Bartender tracking stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in tracking loop: {e}")
            self.running = False
    
    def stop_tracking(self):
        """Stop bartender tracking"""
        self.running = False
        self.stop_event.set()
    
    def get_stats(self) -> Dict:
        """Get current bartender statistics"""
        with self.data_lock:
            stats = {
                'total_drinks_today': self.total_drinks_today,
                'active_bartenders': len([d for d in self.current_bartenders if d['bartender_id'] is not None]),
                'registered_bartenders': len(self.bartenders),
                'bartenders': []
            }
            
            # Add per-bartender stats
            for bid, bartender in self.bartenders.items():
                drinks = self.drinks_per_bartender.get(bid, 0)
                
                # Calculate drinks per hour
                shift_duration = (datetime.now() - bartender['shift_start']).total_seconds() / 3600
                drinks_per_hour = drinks / shift_duration if shift_duration > 0 else 0
                
                stats['bartenders'].append({
                    'id': bid,
                    'name': bartender['name'],
                    'drinks_today': drinks,
                    'drinks_per_hour': round(drinks_per_hour, 1),
                    'shift_start': bartender['shift_start'].isoformat(),
                    'last_seen': bartender['last_seen'].isoformat() if bartender['last_seen'] else None,
                    'is_active': bartender['last_seen'] is not None and 
                                (datetime.now() - bartender['last_seen']).total_seconds() < 60
                })
            
            return stats
    
    def get_bartender_list(self) -> List[Dict]:
        """Get list of registered bartenders"""
        with self.data_lock:
            return [
                {
                    'id': bid,
                    'name': bartender['name'],
                    'drinks_today': self.drinks_per_bartender.get(bid, 0)
                }
                for bid, bartender in self.bartenders.items()
            ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo usage
    tracker = BartenderTracker()
    
    # Register some test bartenders
    tracker.add_bartender("Sarah")
    tracker.add_bartender("Mike")
    tracker.add_bartender("Alex")
    
    # Set bar zone (example coordinates)
    tracker.set_bar_zone(100, 100, 400, 300)
    
    # Start tracking
    tracker.start_tracking()
    
    try:
        while True:
            time.sleep(5)
            stats = tracker.get_stats()
            print(f"\n=== Bartender Stats ===")
            print(f"Total Drinks: {stats['total_drinks_today']}")
            print(f"Active: {stats['active_bartenders']}")
            for b in stats['bartenders']:
                print(f"  {b['name']}: {b['drinks_today']} drinks ({b['drinks_per_hour']}/hr)")
    except KeyboardInterrupt:
        print("\nStopping...")
        tracker.stop_tracking()
