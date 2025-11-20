#!/usr/bin/env python3
"""
Visitor Counter for Bar Entry/Exit Detection
=============================================
Ceiling-mounted camera facing down
Horizontal green line across middle of frame
Counts entries (top→bottom) and exits (bottom→top)

Requires: Raspberry Pi 5 with Hailo hat, supervision, hailo-rpi5-examples environment
"""

from pathlib import Path
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import numpy as np
import cv2
import hailo

from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer
from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.hailo_app_python.apps.detection.detection_pipeline import GStreamerDetectionApp


# -----------------------------------------------------------------------------------------------
# Visitor Counter Callback Class
# -----------------------------------------------------------------------------------------------
class VisitorCounterCallback(app_callback_class):
    def __init__(self):
        super().__init__()
        # Track people positions: {track_id: y_position}
        self.previous_positions = {}
        # Entry/Exit counters
        self.entry_count = 0
        self.exit_count = 0
        # Crossing hysteresis - prevent multiple counts for same crossing
        self.crossing_cooldown = {}  # {track_id: frames_since_crossing}
        self.cooldown_frames = 30  # Wait 30 frames before allowing another crossing count


# -----------------------------------------------------------------------------------------------
# Main Callback Function
# -----------------------------------------------------------------------------------------------
def app_callback(pad, info, user_data):
    """
    Callback function for processing video frames and detections.
    Tracks people crossing horizontal line to count entries/exits.
    """
    # Get the GstBuffer from the probe info
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    # Increment frame counter
    user_data.increment()
    
    # Get frame dimensions
    format, width, height = get_caps_from_pad(pad)
    
    # Get video frame for visualization
    frame = None
    if user_data.use_frame and format is not None and width is not None and height is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)

    # Get person detections from Hailo
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # Calculate horizontal line position (middle of frame)
    center_y = height // 2 if height is not None else 0
    
    # Update crossing cooldowns
    for track_id in list(user_data.crossing_cooldown.keys()):
        user_data.crossing_cooldown[track_id] += 1
        if user_data.crossing_cooldown[track_id] > user_data.cooldown_frames:
            del user_data.crossing_cooldown[track_id]
    
    # Process each person detection
    detection_count = 0
    output_text = f"Frame: {user_data.get_count()}\n"
    
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        
        # Only process person detections
        if label == "person":
            detection_count += 1
            
            # Get unique tracking ID
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = track[0].get_id()
            
            # Track crossing detection
            if track_id > 0 and height is not None:
                # Calculate center Y position of person's bounding box
                bbox_center_y = int((bbox.ymin() + bbox.ymax()) / 2 * height)
                
                # Check if this person was tracked in previous frame
                if track_id in user_data.previous_positions:
                    prev_y = user_data.previous_positions[track_id]
                    
                    # Only count if not in cooldown period
                    if track_id not in user_data.crossing_cooldown:
                        # ENTRY: crossing from top to bottom (prev_y < center_y and bbox_center_y >= center_y)
                        if prev_y < center_y and bbox_center_y >= center_y:
                            user_data.entry_count += 1
                            user_data.crossing_cooldown[track_id] = 0
                            output_text += f">>> ENTRY #{user_data.entry_count} - ID: {track_id} (conf: {confidence:.2f})\n"
                            print(f"🚶 ENTRY #{user_data.entry_count} - Person ID {track_id}")
                        
                        # EXIT: crossing from bottom to top (prev_y >= center_y and bbox_center_y < center_y)
                        elif prev_y >= center_y and bbox_center_y < center_y:
                            user_data.exit_count += 1
                            user_data.crossing_cooldown[track_id] = 0
                            output_text += f"<<< EXIT #{user_data.exit_count} - ID: {track_id} (conf: {confidence:.2f})\n"
                            print(f"🚶 EXIT #{user_data.exit_count} - Person ID {track_id}")
                
                # Update position for next frame
                user_data.previous_positions[track_id] = bbox_center_y
                
                # Draw bounding box on frame if available
                if frame is not None:
                    x1 = int(bbox.xmin() * width)
                    y1 = int(bbox.ymin() * height)
                    x2 = int(bbox.xmax() * width)
                    y2 = int(bbox.ymax() * height)
                    
                    # Draw box (cyan color)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                    
                    # Draw track ID above box
                    cv2.putText(frame, f"ID:{track_id}", (x1, y1 - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    
                    # Draw center point
                    cv2.circle(frame, (int((x1 + x2) / 2), bbox_center_y), 5, (0, 255, 255), -1)
    
    # Clean up old tracks (not seen for a while)
    active_track_ids = set()
    for detection in detections:
        if detection.get_label() == "person":
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                active_track_ids.add(track[0].get_id())
    
    # Remove tracks not seen in this frame
    for track_id in list(user_data.previous_positions.keys()):
        if track_id not in active_track_ids:
            del user_data.previous_positions[track_id]
    
    # Visualize on frame
    if user_data.use_frame and frame is not None:
        # Draw HORIZONTAL GREEN LINE across middle of frame
        cv2.line(frame, (0, center_y), (width, center_y), (0, 255, 0), 3)
        
        # Add "ENTRY" and "EXIT" zone labels
        cv2.putText(frame, "ENTRY ZONE", (10, center_y - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, "EXIT ZONE", (10, center_y + 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Display counts in BOTTOM RIGHT corner
        text_x = width - 250
        text_y_base = height - 80
        
        # Background rectangles for better visibility
        cv2.rectangle(frame, (text_x - 10, text_y_base - 35), 
                     (width - 10, height - 10), (0, 0, 0), -1)
        cv2.rectangle(frame, (text_x - 10, text_y_base - 35), 
                     (width - 10, height - 10), (0, 255, 0), 2)
        
        # Entry count (green)
        cv2.putText(frame, f"ENTRIES: {user_data.entry_count}", 
                   (text_x, text_y_base), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Exit count (green)
        cv2.putText(frame, f"EXITS:   {user_data.exit_count}", 
                   (text_x, text_y_base + 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Current detection count (top left)
        cv2.putText(frame, f"People Detected: {detection_count}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Frame counter (top left)
        cv2.putText(frame, f"Frame: {user_data.get_count()}", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Convert frame to BGR for display
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)
    
    # Print status (optional, can be removed for production)
    if detection_count > 0:
        print(output_text)
    
    return Gst.PadProbeReturn.OK


# -----------------------------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("VISITOR COUNTER - Bar Entry/Exit Detection")
    print("=" * 70)
    print("Camera: Ceiling-mounted, facing down")
    print("Line: Horizontal green line across middle")
    print("Logic: Top→Bottom = ENTRY, Bottom→Top = EXIT")
    print("Display: Bottom-right corner shows real-time counts")
    print("=" * 70)
    print("\nStarting detection... Press Ctrl+C to stop.\n")
    
    # Set up environment for Hailo
    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    if env_file.exists():
        os.environ["HAILO_ENV_FILE"] = str(env_file)
    
    # Create visitor counter callback instance
    user_data = VisitorCounterCallback()
    
    # Create and run GStreamer detection app
    app = GStreamerDetectionApp(app_callback, user_data)
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("VISITOR COUNTER - Session Summary")
        print("=" * 70)
        print(f"Total Entries: {user_data.entry_count}")
        print(f"Total Exits:   {user_data.exit_count}")
        print(f"Net Count:     {user_data.entry_count - user_data.exit_count}")
        print("=" * 70)
        print("\nShutting down gracefully...")
