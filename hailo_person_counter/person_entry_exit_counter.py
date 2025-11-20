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
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
# Inheritance from the app_callback_class
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.new_variable = 42  # New variable example
        # ADDED: Track previous positions of people and entry/exit counts
        self.previous_positions = {}  # Dictionary to store {track_id: x_position}
        self.entry_count = 0
        self.exit_count = 0

    def new_function(self):  # New function example
        return "The meaning of life is: "

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------

# This is the callback function that will be called when data is available from the pipeline
def app_callback(pad, info, user_data):
    # Get the GstBuffer from the probe info
    buffer = info.get_buffer()
    # Check if the buffer is valid
    if buffer is None:
        return Gst.PadProbeReturn.OK

    # Using the user_data to count the number of frames
    user_data.increment()
    string_to_print = f"Frame count: {user_data.get_count()}\n"

    # Get the caps from the pad
    format, width, height = get_caps_from_pad(pad)

    # If the user_data.use_frame is set to True, we can get the video frame from the buffer
    frame = None
    if user_data.use_frame and format is not None and width is not None and height is not None:
        # Get video frame
        frame = get_numpy_from_buffer(buffer, format, width, height)

    # Get the detections from the buffer
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # ADDED: Calculate center line position
    center_x = width // 2 if width is not None else 0

    # Parse the detections
    detection_count = 0
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        if label == "person":
            # Get track ID
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = track[0].get_id()
            string_to_print += (f"Detection: ID: {track_id} Label: {label} Confidence: {confidence:.2f}\n")
            detection_count += 1
            
            # ADDED: Track crossing detection
            if track_id > 0 and width is not None:
                # Calculate center of bounding box
                bbox_center_x = int((bbox.xmin() + bbox.xmax()) / 2 * width)
                
                # Check if this person was tracked before
                if track_id in user_data.previous_positions:
                    prev_x = user_data.previous_positions[track_id]
                    
                    # Check if crossed the center line
                    # Entry: crossing from left to right (prev_x < center_x and bbox_center_x >= center_x)
                    if prev_x < center_x and bbox_center_x >= center_x:
                        user_data.entry_count += 1
                        string_to_print += f">>> ENTRY detected! ID: {track_id}\n"
                    
                    # Exit: crossing from right to left (prev_x >= center_x and bbox_center_x < center_x)
                    elif prev_x >= center_x and bbox_center_x < center_x:
                        user_data.exit_count += 1
                        string_to_print += f"<<< EXIT detected! ID: {track_id}\n"
                
                # Update position for next frame
                user_data.previous_positions[track_id] = bbox_center_x
    
    if user_data.use_frame:
        # Note: using imshow will not work here, as the callback function is not running in the main thread
        # Let's print the detection count to the frame
        cv2.putText(frame, f"Detections: {detection_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        # Example of how to use the new_variable and new_function from the user_data
        # Let's print the new_variable and the result of the new_function to the frame
        cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # ADDED: Draw vertical center line
        if width is not None and height is not None:
            cv2.line(frame, (center_x, 0), (center_x, height), (0, 255, 0), 2)
        
        # ADDED: Draw entry/exit counters in bottom left corner
        if height is not None:
            cv2.putText(frame, f"Entries: {user_data.entry_count}", (10, height - 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, f"Exits: {user_data.exit_count}", (10, height - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Convert the frame to BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        user_data.set_frame(frame)

    print(string_to_print)
    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    env_file     = project_root / ".env"
    env_path_str = str(env_file)
    os.environ["HAILO_ENV_FILE"] = env_path_str
    # Create an instance of the user app callback class
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
