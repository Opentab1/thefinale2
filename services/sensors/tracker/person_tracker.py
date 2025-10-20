#!/usr/bin/env python3
"""
person_tracker.py - Advanced person tracking system for accurate counting of people
entering and exiting the camera view.

This module provides a robust tracking system that:
1. Tracks people between frames using improved matching algorithms
2. Distinguishes between whole people and body parts
3. Counts people entering (appearing in) and exiting (disappearing from) the frame
4. Provides visualization of tracking information
"""

import time
import logging
import numpy as np
import cv2

class PersonTracker:
    def __init__(self, confidence_threshold=0.5, min_detection_frames=5):
        """
        Initialize the person tracker
        
        Args:
            confidence_threshold: Minimum confidence for a detection to be considered
            min_detection_frames: Minimum number of consecutive frames to track before counting
        """
        # Configuration
        self.confidence_threshold = confidence_threshold
        self.min_detection_frames = min_detection_frames
        
        # Tracking state
        self.tracked_people = {}      # Dictionary of all tracked people
        self.next_id = 0              # ID counter for new detections
        
        # Counting state
        self.entry_count = 0          # People who entered the frame
        self.exit_count = 0           # People who exited the frame
        self.current_count = 0        # People currently in frame
        
        # Debug flags
        self.debug_mode = False
        
        # Filter settings
        self.min_person_height = 80   # Minimum height in pixels to be considered a person
        self.min_person_width = 30    # Minimum width in pixels
        self.min_aspect_ratio = 1.2   # Height should be at least this times width for a person
        
        # For frame dimensions
        self.frame_height = None
        self.frame_width = None
        
    def update_frame_dimensions(self, frame):
        """Update frame dimensions if they changed"""
        height, width = frame.shape[:2]
        if self.frame_height != height or self.frame_width != width:
            self.frame_height = height
            self.frame_width = width
            
    def _is_valid_person(self, detection):
        """
        Check if a detection is likely to be a valid person and not just a body part
        
        Args:
            detection: Dictionary with detection information including 'box'
            
        Returns:
            bool: True if the detection meets the criteria for a person
        """
        x, y, w, h = detection['box']
        
        # Size check
        if h < self.min_person_height or w < self.min_person_width:
            return False
            
        # Aspect ratio check (people are typically taller than wide)
        aspect_ratio = h / w if w > 0 else 0
        if aspect_ratio < self.min_aspect_ratio:
            return False
            
        # Position check (reject detections that are mostly outside the frame)
        if y + h < 0 or y > self.frame_height or x + w < 0 or x > self.frame_width:
            return False
            
        # Confidence check
        if detection.get('confidence', 0) < self.confidence_threshold:
            return False
            
        return True
        
    def _calculate_detection_features(self, detection):
        """
        Calculate additional features from a detection to help with tracking
        
        Args:
            detection: Dictionary with detection information
            
        Returns:
            tuple: Center point, area, aspect ratio
        """
        x, y, w, h = detection['box']
        center = (x + w // 2, y + h // 2)
        area = w * h
        aspect_ratio = h / w if w > 0 else 0
        
        return center, area, aspect_ratio
        
    def _match_detection_to_tracked(self, detection):
        """
        Match a detection to existing tracked people using improved matching algorithm
        
        Args:
            detection: Dictionary with detection information
            
        Returns:
            int or None: ID of the matched person, or None if no match
        """
        if not self._is_valid_person(detection):
            return None
            
        x, y, w, h = detection['box']
        new_center, new_area, new_aspect = self._calculate_detection_features(detection)
        
        best_id = None
        best_score = float('inf')
        
        # Box representation as (x1, y1, x2, y2)
        new_box = [x, y, x + w, y + h]
        
        for person_id, data in self.tracked_people.items():
            # Skip people who have exited
            if data['status'] in ('exited', 'invalid'):
                continue
                
            px, py, pw, ph = data['box']
            old_center = data['center']
            old_area = pw * ph
            old_aspect = ph / pw if pw > 0 else 0
            
            # Time since last seen (for predicting movement)
            time_gap = time.time() - data['last_seen']
            if time_gap > 1.0:  # Skip if not seen for more than 1 second
                continue
                
            # Calculate predicted position based on velocity
            velocity = data['velocity']
            predicted_x = old_center[0] + velocity[0] * time_gap
            predicted_y = old_center[1] + velocity[1] * time_gap
            
            # Distance between centers (using prediction)
            distance = np.sqrt((new_center[0] - predicted_x)**2 + (new_center[1] - predicted_y)**2)
            
            # Area difference ratio (1 = same area)
            area_ratio = new_area / old_area if old_area > 0 else float('inf')
            if area_ratio < 1:
                area_ratio = 1 / area_ratio
                
            # Aspect ratio difference
            aspect_diff = abs(new_aspect - old_aspect)
            
            # Calculate IoU (Intersection over Union)
            old_box = [px, py, px + pw, py + ph]
            iou = self._calculate_iou(new_box, old_box)
            
            # Calculate overall matching score (lower is better)
            # We prioritize IoU and distance for matching
            position_score = distance * 0.5
            shape_score = (area_ratio - 1) * 20 + aspect_diff * 10
            iou_score = (1 - iou) * 50  # Higher weight for IoU
            time_score = time_gap * 10
            
            score = position_score + shape_score + iou_score + time_score
            
            # Use a threshold for matching
            if score < 100 and score < best_score:
                best_score = score
                best_id = person_id
                
        return best_id
        
    def _calculate_iou(self, box1, box2):
        """
        Calculate Intersection over Union between two bounding boxes
        
        Args:
            box1, box2: Bounding boxes in format [x1, y1, x2, y2]
            
        Returns:
            float: IoU value between 0 and 1
        """
        # Calculate intersection
        x_left = max(box1[0], box2[0])
        y_top = max(box1[1], box2[1])
        x_right = min(box1[2], box2[2])
        y_bottom = min(box1[3], box2[3])
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
            
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
        box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = box1_area + box2_area - intersection
        
        # Calculate IoU
        iou = intersection / union if union > 0 else 0.0
        
        return iou
        
    def process_detections(self, detections, frame):
        """
        Process new detections and update tracking information
        
        Args:
            detections: List of detections from the detector
            frame: Current frame for visualization
            
        Returns:
            frame: Updated frame with visualization
            dict: Counting information
        """
        self.update_frame_dimensions(frame)
        
        # ID set for current frame
        current_ids = set()
        
        # First pass: update existing tracks and create new ones
        for detection in detections:
            # Skip if not a valid person
            if not self._is_valid_person(detection):
                continue
                
            x, y, w, h = detection['box']
            confidence = detection.get('confidence', 0.5)
            detector_type = detection.get('detector', 'Unknown')
            
            # Match to existing track or create new one
            person_id = self._match_detection_to_tracked(detection)
            
            # New person
            if person_id is None:
                person_id = self.next_id
                self.next_id += 1
                
                # Calculate center and create new tracking entry
                center = (x + w // 2, y + h // 2)
                
                self.tracked_people[person_id] = {
                    'box': (x, y, w, h),
                    'center': center,
                    'first_seen': time.time(),
                    'last_seen': time.time(),
                    'frames_tracked': 1,
                    'confidence': confidence,
                    'detector': detector_type,
                    'status': 'tentative',  # New status: need more confirmations
                    'trajectory': [center],
                    'velocity': (0, 0)
                }
                
            # Update existing person
            else:
                # Get previous state
                old_center = self.tracked_people[person_id]['center']
                old_time = self.tracked_people[person_id]['last_seen']
                current_time = time.time()
                time_gap = current_time - old_time
                
                # Calculate new center and velocity
                new_center = (x + w // 2, y + h // 2)
                
                # Only update velocity with a reasonable time gap to avoid extreme values
                if time_gap > 0.01:
                    velocity = (
                        (new_center[0] - old_center[0]) / time_gap,
                        (new_center[1] - old_center[1]) / time_gap
                    )
                else:
                    velocity = self.tracked_people[person_id]['velocity']
                
                # Update tracking record
                self.tracked_people[person_id].update({
                    'box': (x, y, w, h),
                    'center': new_center,
                    'last_seen': current_time,
                    'frames_tracked': self.tracked_people[person_id]['frames_tracked'] + 1,
                    'confidence': max(self.tracked_people[person_id]['confidence'], confidence),
                    'velocity': velocity
                })
                
                # Keep trajectory history bounded
                self.tracked_people[person_id]['trajectory'].append(new_center)
                if len(self.tracked_people[person_id]['trajectory']) > 30:  # Increased history
                    self.tracked_people[person_id]['trajectory'] = self.tracked_people[person_id]['trajectory'][-30:]
                
                # Update status after tracking for several frames
                if self.tracked_people[person_id]['status'] == 'tentative':
                    if self.tracked_people[person_id]['frames_tracked'] >= self.min_detection_frames:
                        # Person is confirmed stable - count as an entry
                        self.tracked_people[person_id]['status'] = 'active'
                        self.entry_count += 1
                        logging.info(f"Person {person_id} ENTERED (confirmed). Count: {self.entry_count}")
            
            # Add to current IDs
            current_ids.add(person_id)
        
        # Second pass: handle missing people and cleanup
        self._handle_missing_people(current_ids, frame)
        
        # Update current count - active or counted people
        self.current_count = len([pid for pid, data in self.tracked_people.items() 
                                if data['status'] == 'active'])
        
        # Create counting info dictionary
        counting_info = {
            'entries': self.entry_count,
            'exits': self.exit_count,
            'current': self.current_count
        }
        
        # Draw visualizations
        return self._draw_visualizations(frame), counting_info
    
    def _handle_missing_people(self, current_ids, frame):
        """
        Handle people not detected in the current frame
        
        Args:
            current_ids: Set of IDs detected in the current frame
            frame: Current frame
        """
        current_time = time.time()
        
        # Predict locations for briefly missing people
        self._predict_missing_people(current_ids, frame)
        
        # Check for people who are gone
        for person_id, data in list(self.tracked_people.items()):
            # Skip already handled people
            if data['status'] in ('exited', 'invalid'):
                continue
                
            # Mark as exited if not seen for some time
            if person_id not in current_ids:
                time_missing = current_time - data['last_seen']
                
                # Short disappearance - might be occlusion or detection error
                if time_missing > 0.5 and time_missing <= 2.0:
                    # Keep as is, prediction will handle visualization
                    pass
                    
                # Longer disappearance - person likely left
                elif time_missing > 2.0:
                    if data['status'] == 'active':
                        # Count as an exit since they disappeared
                        self.exit_count += 1
                        logging.info(f"Person {person_id} EXITED. Count: {self.exit_count}")
                        
                        # Mark as exited
                        self.tracked_people[person_id]['status'] = 'exited'
                    elif data['status'] == 'tentative':
                        # Was never a confirmed person - invalid
                        self.tracked_people[person_id]['status'] = 'invalid'
        
        # Cleanup old records periodically
        if len(self.tracked_people) > 50:  # Only clean up when we have many records
            ids_to_remove = []
            for person_id, data in self.tracked_people.items():
                # Remove invalid tracks immediately
                if data['status'] == 'invalid' and (current_time - data['last_seen'] > 1.0):
                    ids_to_remove.append(person_id)
                # Remove exited tracks after some time
                elif data['status'] == 'exited' and (current_time - data['last_seen'] > 30.0):
                    ids_to_remove.append(person_id)
            
            for person_id in ids_to_remove:
                del self.tracked_people[person_id]
    
    def _predict_missing_people(self, current_ids, frame):
        """
        Predict positions for temporarily missing people
        
        Args:
            current_ids: Set of currently visible person IDs
            frame: Current frame for visualization
        """
        current_time = time.time()
        
        for person_id, data in self.tracked_people.items():
            # Skip people already detected in this frame or invalid/exited
            if person_id in current_ids or data['status'] in ('exited', 'invalid'):
                continue
            
            # Only predict for briefly missing people (< 2 seconds)
            time_missing = current_time - data['last_seen']
            if time_missing > 2.0:
                continue
            
            # Get last known position and velocity
            px, py, pw, ph = data['box']
            velocity = data['velocity']
            
            # Predict new position using velocity and time
            new_x = int(px + velocity[0] * time_missing)
            new_y = int(py + velocity[1] * time_missing)
            
            # Ensure predicted position is within frame bounds
            new_x = max(0, min(new_x, self.frame_width - pw))
            new_y = max(0, min(new_y, self.frame_height - ph))
            
            # Store predicted box
            data['predicted_box'] = (new_x, new_y, pw, ph)
    
    def _draw_visualizations(self, frame):
        """
        Draw tracking and counting visualization on the frame
        
        Args:
            frame: Current video frame
            
        Returns:
            frame: Frame with visualizations
        """
        # Draw people boxes and trajectories
        for person_id, data in self.tracked_people.items():
            # Skip invalid tracks
            if data['status'] == 'invalid':
                continue
                
            # Exited people are drawn differently if in debug mode
            if data['status'] == 'exited':
                if self.debug_mode:
                    # Show exited people with a different color when debugging
                    time_since_exit = time.time() - data['last_seen']
                    if time_since_exit < 5.0:  # Only show recently exited people
                        x, y, w, h = data['box']
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (100, 100, 100), 1)
                        cv2.putText(frame, f"X-{person_id}", (x, y - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
                continue
            
            # Choose color based on status
            if data['status'] == 'tentative':
                color = (0, 165, 255)  # Orange - not yet confirmed
            elif data['status'] == 'active':
                color = (0, 255, 0)    # Green - confirmed person
            
            # Draw actual box if seen in this frame
            if time.time() - data['last_seen'] < 0.1:  # Very recently seen
                x, y, w, h = data['box']
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                
                # Add label with ID and status
                label = f"ID:{person_id}"
                if data['status'] == 'tentative':
                    label += f" ({data['frames_tracked']}/{self.min_detection_frames})"
                
                cv2.putText(frame, label, (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            # Draw predicted box for missing people
            elif 'predicted_box' in data:
                x, y, w, h = data['predicted_box']
                # Draw with dashed line
                for i in range(0, w, 5):
                    cv2.line(frame, (x + i, y), (x + i + 3, y), color, 1)
                    cv2.line(frame, (x + i, y + h), (x + i + 3, y + h), color, 1)
                for i in range(0, h, 5):
                    cv2.line(frame, (x, y + i), (x, y + i + 3), color, 1)
                    cv2.line(frame, (x + w, y + i), (x + w, y + i + 3), color, 1)
                    
                cv2.putText(frame, f"P:{person_id}", (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Draw trajectory in debug mode
            if self.debug_mode and len(data['trajectory']) > 1:
                points = np.array(data['trajectory'], dtype=np.int32)
                cv2.polylines(frame, [points], False, color, 1)
        
        # Draw counting info
        cv2.putText(frame, f"Entries: {self.entry_count}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Exits: {self.exit_count}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Current: {self.current_count}", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Draw debug indicator
        if self.debug_mode:
            cv2.putText(frame, "DEBUG MODE", (frame.shape[1] - 150, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame
    
    def toggle_debug_mode(self):
        """Toggle debug visualization mode"""
        self.debug_mode = not self.debug_mode
        return self.debug_mode
    
    def reset_counts(self):
        """Reset all counts to zero"""
        self.entry_count = 0
        self.exit_count = 0
        # Current count is not reset as it depends on tracked people