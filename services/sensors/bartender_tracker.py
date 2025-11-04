"""
Pulse 1.0 - AI Bartender Drink Counter (Anonymous Tracking)
Tracks individual bartenders and drinks made using computer vision

PRIVACY-FIRST: Uses anonymous person re-identification (ReID)
- NO face recognition or biometric data stored
- Tracks bartenders by appearance (clothing, position, body features)
- Each bartender gets a random anonymous ID for the shift
- Owner can manually map IDs to names externally

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
import hashlib

logger = logging.getLogger(__name__)


class BartenderTracker:
    """
    Tracks bartenders anonymously using person re-identification (ReID)
    NO face recognition - privacy-first approach
    
    Each bartender is assigned a random anonymous ID based on appearance
    """
    
    def __init__(self, camera_index: int = 0):
        """Initialize anonymous bartender tracker"""
        self.camera_index = camera_index
        self.running = False
        self.stop_event = Event()
        
        # Anonymous bartender tracking
        self.active_bartenders = {}  # {anon_id: {'appearance_features': array, 'drinks_today': int, 'last_seen': datetime}}
        self.next_anon_id = 1
        
        # Person detector (for body detection)
        self.person_detector = cv2.HOGDescriptor()
        self.person_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # ReID tracking parameters
        self.reid_threshold = 0.7  # Similarity threshold for matching
        self.reid_history = {}  # {anon_id: [feature_vectors]}
        self.max_history_length = 10  # Keep last N appearance samples
        
        # Current detections
        self.current_detections = []  # List of detected people in frame
        self.drinks_per_bartender = {}  # {anon_id: drink_count}
        
        # Drink detection zones
        self.bar_zones = []  # List of (x, y, w, h) rectangles
        self.last_drink_time = {}  # {anon_id: timestamp}
        self.min_time_between_drinks = 30  # seconds
        
        # Performance tracking
        self.total_drinks_today = 0
        self.start_time = datetime.now()
        
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
        
        logger.info("Anonymous bartender tracker initialized (NO face recognition)")
    
    def _extract_appearance_features(self, person_crop: np.ndarray) -> np.ndarray:
        """
        Extract appearance features for person re-identification
        Uses simple color histogram + spatial features (no biometrics)
        
        Args:
            person_crop: Cropped image of person
            
        Returns:
            Feature vector for ReID
        """
        try:
            # Resize to standard size
            person_crop = cv2.resize(person_crop, (64, 128))
            
            # Extract color histogram (HSV color space - better for clothing)
            hsv = cv2.cvtColor(person_crop, cv2.COLOR_BGR2HSV)
            
            # Split into upper body (clothing) and lower body
            height = person_crop.shape[0]
            upper = hsv[:height//2, :]
            lower = hsv[height//2:, :]
            
            # Calculate histograms for each region
            hist_upper = cv2.calcHist([upper], [0, 1], None, [8, 8], [0, 180, 0, 256])
            hist_lower = cv2.calcHist([lower], [0, 1], None, [8, 8], [0, 180, 0, 256])
            
            # Normalize
            hist_upper = cv2.normalize(hist_upper, hist_upper).flatten()
            hist_lower = cv2.normalize(hist_lower, hist_lower).flatten()
            
            # Combine features
            features = np.concatenate([hist_upper, hist_lower])
            
            return features
        except Exception as e:
            logger.error(f"Error extracting appearance features: {e}")
            return np.zeros(128)  # Return zero vector on error
    
    def _match_to_existing_bartender(self, features: np.ndarray) -> Optional[int]:
        """
        Match appearance features to existing bartender
        
        Args:
            features: Appearance feature vector
            
        Returns:
            anon_id if match found, None otherwise
        """
        best_match_id = None
        best_similarity = 0.0
        
        for anon_id, bartender in self.active_bartenders.items():
            # Compare with historical features
            if anon_id in self.reid_history:
                for hist_features in self.reid_history[anon_id]:
                    # Cosine similarity
                    similarity = np.dot(features, hist_features) / (
                        np.linalg.norm(features) * np.linalg.norm(hist_features) + 1e-6
                    )
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_id = anon_id
        
        # Return match if above threshold
        if best_similarity > self.reid_threshold:
            return best_match_id
        
        return None
    
    def _create_new_bartender(self, features: np.ndarray) -> int:
        """
        Create a new anonymous bartender ID
        
        Args:
            features: Initial appearance features
            
        Returns:
            New anonymous ID
        """
        anon_id = self.next_anon_id
        self.next_anon_id += 1
        
        with self.data_lock:
            self.active_bartenders[anon_id] = {
                'appearance_features': features,
                'drinks_today': 0,
                'shift_start': datetime.now(),
                'last_seen': datetime.now()
            }
            self.drinks_per_bartender[anon_id] = 0
            self.reid_history[anon_id] = [features]
        
        logger.info(f"New bartender detected: Anonymous ID #{anon_id}")
        return anon_id
    
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
    
    def _detect_people(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect people (potential bartenders) in frame using HOG detector
        
        Returns:
            List of detected people with bounding boxes
        """
        detections = []
        
        try:
            # Resize for faster detection
            scale = 0.5
            resized = cv2.resize(frame, None, fx=scale, fy=scale)
            
            # Detect people using HOG
            boxes, weights = self.person_detector.detectMultiScale(
                resized,
                winStride=(8, 8),
                padding=(4, 4),
                scale=1.05
            )
            
            # Process each detection
            for i, (x, y, w, h) in enumerate(boxes):
                # Scale back to original size
                x, y, w, h = int(x/scale), int(y/scale), int(w/scale), int(h/scale)
                
                # Ensure within frame bounds
                x = max(0, x)
                y = max(0, y)
                w = min(w, frame.shape[1] - x)
                h = min(h, frame.shape[0] - y)
                
                # Extract person crop for ReID
                person_crop = frame[y:y+h, x:x+w]
                
                # Extract appearance features
                features = self._extract_appearance_features(person_crop)
                
                # Try to match to existing bartender
                anon_id = self._match_to_existing_bartender(features)
                
                # If no match and in bar zone, create new bartender
                in_bar_zone = self._is_in_bar_zone(x, y, w, h)
                if anon_id is None and in_bar_zone:
                    anon_id = self._create_new_bartender(features)
                elif anon_id is not None:
                    # Update appearance history
                    if anon_id in self.reid_history:
                        self.reid_history[anon_id].append(features)
                        # Keep only recent history
                        if len(self.reid_history[anon_id]) > self.max_history_length:
                            self.reid_history[anon_id].pop(0)
                
                detections.append({
                    'anon_id': anon_id,
                    'box': (x, y, w, h),
                    'features': features,
                    'in_bar_zone': in_bar_zone,
                    'center': (x + w // 2, y + h // 2)
                })
        
        except Exception as e:
            logger.error(f"Error detecting people: {e}")
        
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
    
    def record_drink(self, anon_id: int) -> bool:
        """
        Manually record a drink for an anonymous bartender
        
        Args:
            anon_id: Anonymous ID of bartender who made the drink
            
        Returns:
            bool: True if successful
        """
        with self.data_lock:
            if anon_id not in self.active_bartenders:
                logger.warning(f"Unknown anonymous bartender ID: {anon_id}")
                return False
            
            # Check rate limit
            now = time.time()
            if anon_id in self.last_drink_time:
                time_since_last = now - self.last_drink_time[anon_id]
                if time_since_last < 5:  # Min 5 seconds between drinks
                    logger.debug(f"Drink recording rate limited for bartender #{anon_id}")
                    return False
            
            # Record drink
            self.drinks_per_bartender[anon_id] += 1
            self.active_bartenders[anon_id]['drinks_today'] += 1
            self.last_drink_time[anon_id] = now
            self.total_drinks_today += 1
            
            logger.info(f"Drink recorded: Anonymous Bartender #{anon_id} "
                       f"(Total: {self.drinks_per_bartender[anon_id]})")
            
            return True
    
    def _annotate_frame(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Draw bounding boxes and labels on frame (anonymous tracking)"""
        annotated = frame.copy()
        
        # Draw bar zones
        for (zx, zy, zw, zh) in self.bar_zones:
            cv2.rectangle(annotated, (zx, zy), (zx + zw, zy + zh), (100, 100, 255), 2)
            cv2.putText(annotated, "BAR ZONE", (zx + 5, zy + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)
        
        # Draw bartender detections with anonymous IDs
        for det in detections:
            x, y, w, h = det['box']
            anon_id = det['anon_id']
            in_zone = det['in_bar_zone']
            
            # Choose color based on status
            if anon_id is not None:
                color = (0, 255, 0)  # Green - tracked bartender
                label = f"Bartender #{anon_id}"
                if anon_id in self.drinks_per_bartender:
                    drinks = self.drinks_per_bartender[anon_id]
                    label += f" - {drinks} drinks"
            elif in_zone:
                color = (0, 255, 255)  # Yellow - in bar zone but not yet tracked
                label = "Person in Bar Zone"
            else:
                color = (200, 200, 200)  # Gray - person outside bar
                label = "Person"
            
            # Draw box
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
            
            # Draw label background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(annotated, (x, y - label_size[1] - 10), 
                         (x + label_size[0] + 10, y), color, -1)
            
            # Draw label text
            cv2.putText(annotated, label, (x + 5, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # Draw stats overlay
        active_count = len([d for d in detections if d['anon_id'] is not None])
        stats_text = [
            f"Total Drinks Today: {self.total_drinks_today}",
            f"Active Bartenders: {active_count}",
            "NO FACE DATA - Anonymous Tracking"
        ]
        
        y_offset = 30
        for text in stats_text:
            # White outline
            cv2.putText(annotated, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 3)
            # Black text
            cv2.putText(annotated, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
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
                    
                    # Detect people (potential bartenders)
                    detections = self._detect_people(frame)
                    
                    with self.data_lock:
                        self.current_detections = detections
                        
                        # Update last seen times for tracked bartenders
                        for det in detections:
                            if det['anon_id'] is not None:
                                self.active_bartenders[det['anon_id']]['last_seen'] = datetime.now()
                    
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
        """Get current anonymous bartender statistics"""
        with self.data_lock:
            stats = {
                'total_drinks_today': self.total_drinks_today,
                'active_bartenders': len([d for d in self.current_detections if d['anon_id'] is not None]),
                'tracked_bartenders': len(self.active_bartenders),
                'privacy_mode': 'ANONYMOUS - NO BIOMETRIC DATA',
                'bartenders': []
            }
            
            # Add per-bartender stats (anonymous)
            for anon_id, bartender in self.active_bartenders.items():
                drinks = self.drinks_per_bartender.get(anon_id, 0)
                
                # Calculate drinks per hour
                shift_duration = (datetime.now() - bartender['shift_start']).total_seconds() / 3600
                drinks_per_hour = drinks / shift_duration if shift_duration > 0 else 0
                
                # Check if currently active (seen in last 60 seconds)
                is_active = bartender['last_seen'] is not None and \
                           (datetime.now() - bartender['last_seen']).total_seconds() < 60
                
                stats['bartenders'].append({
                    'id': anon_id,
                    'anonymous_id': f"BARTENDER-{anon_id:03d}",  # e.g., BARTENDER-001
                    'drinks_today': drinks,
                    'drinks_per_hour': round(drinks_per_hour, 1),
                    'shift_start': bartender['shift_start'].isoformat(),
                    'last_seen': bartender['last_seen'].isoformat() if bartender['last_seen'] else None,
                    'is_active': is_active
                })
            
            # Sort by drinks (highest first)
            stats['bartenders'].sort(key=lambda x: x['drinks_today'], reverse=True)
            
            return stats
    
    def get_bartender_list(self) -> List[Dict]:
        """Get list of anonymous bartenders currently being tracked"""
        with self.data_lock:
            return [
                {
                    'id': anon_id,
                    'anonymous_id': f"BARTENDER-{anon_id:03d}",
                    'drinks_today': self.drinks_per_bartender.get(anon_id, 0),
                    'is_active': (datetime.now() - bartender['last_seen']).total_seconds() < 60 
                                if bartender['last_seen'] else False
                }
                for anon_id, bartender in self.active_bartenders.items()
            ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo usage - Anonymous tracking
    tracker = BartenderTracker()
    
    # Set bar zone (example coordinates - adjust for your camera view)
    tracker.set_bar_zone(100, 100, 400, 300)
    
    # Start tracking
    tracker.start_tracking()
    
    print("🔒 PRIVACY MODE: Anonymous bartender tracking active")
    print("   - NO face recognition")
    print("   - NO biometric data stored")
    print("   - Bartenders tracked by appearance only")
    print("   - Each person gets anonymous ID for the shift\n")
    
    try:
        while True:
            time.sleep(5)
            stats = tracker.get_stats()
            print(f"\n=== Anonymous Bartender Stats ===")
            print(f"Total Drinks: {stats['total_drinks_today']}")
            print(f"Active: {stats['active_bartenders']}")
            print(f"Mode: {stats['privacy_mode']}")
            for b in stats['bartenders']:
                status = "🟢 ACTIVE" if b['is_active'] else "⚪ INACTIVE"
                print(f"  {b['anonymous_id']}: {b['drinks_today']} drinks "
                      f"({b['drinks_per_hour']}/hr) {status}")
    except KeyboardInterrupt:
        print("\nStopping...")
        tracker.stop_tracking()
