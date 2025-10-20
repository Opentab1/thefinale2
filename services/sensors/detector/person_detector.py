#!/usr/bin/env python3
"""
person_detector.py - Base detector class with improved filtering for whole-person detection

This module provides the base detector class that:
1. Implements multiple detection methods
2. Filters out body parts and false positives
3. Provides a common interface for different detector types
"""

import os
import logging
import time
import threading
import numpy as np
import cv2
# Try to import Hailo detector
try:
    from .hailo_detector import HailoPersonDetector, HAILO_AVAILABLE
except ImportError:
    HAILO_AVAILABLE = False
    logging.warning("Hailo detector module not available")

class PersonDetector:
    def __init__(self, confidence_threshold=0.45, model_type="hog"):
        """
        Initialize the person detector
        
        Args:
            confidence_threshold: Minimum confidence for detection
            model_type: Detection model to use (hog, ssd, yolo, or hailo)
        """
        # Configuration
        self.confidence_threshold = confidence_threshold
        self.model_type = model_type
        
        # Initialize models
        self.models = {}
        self.initialize_models()
        
        # Initialize Hailo detector separately
        self.hailo_detector = None
        if model_type == "hailo" and HAILO_AVAILABLE:
            try:
                self.hailo_detector = HailoPersonDetector(confidence_threshold=confidence_threshold)
                self.models['hailo'] = {
                    'detector': 'HAILO_ACCEL',
                    'loaded': True if self.hailo_detector.device is not None else False
                }
            except Exception as e:
                logging.error(f"Error initializing Hailo detector: {e}")
                self.models['hailo'] = {
                    'detector': None,
                    'loaded': False
                }
        
        # Frame dimensions
        self.frame_width = None
        self.frame_height = None
        
        # FPS calculation
        self.frame_count = 0
        self.start_time = time.time()
        self.fps = 0
        
        # For multi-threaded detection
        self.detection_thread = None
        self.detection_thread_active = False
        self.frame_for_detection = None
        self.detections = []
        self.detection_lock = threading.Lock()
        
        # Filtering parameters
        self.min_person_height = 80
        self.min_person_width = 30
        self.min_aspect_ratio = 1.2  # Height should be at least this times width for a person
        
        # Start detection thread
        self.start_detection_thread()
    
    def initialize_models(self):
        """Initialize detection models"""
        logging.info("Initializing detection models...")
        # Use shared models directory when available, else fallback to local
        preferred_dir = "/opt/pulse/models"
        models_dir = preferred_dir
        try:
            os.makedirs(models_dir, exist_ok=True)
        except Exception:
            # Fallback to a writable local directory in repo
            models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")
            models_dir = os.path.abspath(models_dir)
            os.makedirs(models_dir, exist_ok=True)
        
        # Initialize HOG detector (always as fallback)
        self.models['hog'] = {
            'detector': cv2.HOGDescriptor(),
            'loaded': True
        }
        self.models['hog']['detector'].setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        logging.info("HOG detector initialized")
        
        # Initialize YOLOv3
        self._init_yolo_model(models_dir)
        
        # Initialize MobileNet SSD
        self._init_ssd_model(models_dir)
        
        # Check if preferred model is available
        if self.model_type not in self.models or not self.models[self.model_type]['loaded']:
            logging.warning(f"Selected model {self.model_type} is not available. Falling back to HOG.")
            self.model_type = 'hog'
            
        logging.info(f"Model initialization complete, using {self.model_type} as primary")
    
    def _init_yolo_model(self, models_dir):
        """Initialize YOLO model"""
        weights_path = os.path.join(models_dir, "yolov3.weights")
        config_path = os.path.join(models_dir, "yolov3.cfg")
        names_path = os.path.join(models_dir, "coco.names")
        
        # Initialize YOLO entry in models dict
        self.models['yolo'] = {
            'detector': None,
            'loaded': False,
            'class_names': [],
            'input_size': (416, 416)
        }
        
        # Download YOLO files if needed
        if not os.path.exists(config_path):
            logging.info("Downloading YOLOv3 config...")
            os.system(f"wget -O {config_path} https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3.cfg")
        
        if not os.path.exists(names_path):
            logging.info("Downloading COCO names...")
            os.system(f"wget -O {names_path} https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names")
        
        if not os.path.exists(weights_path):
            logging.info("YOLO weights file not found. Skipping YOLO initialization.")
            return
        
        # Load class names
        if os.path.exists(names_path):
            with open(names_path, 'r') as f:
                self.models['yolo']['class_names'] = [line.strip() for line in f.readlines()]
        
        # Initialize YOLO if files exist
        if os.path.exists(weights_path) and os.path.exists(config_path):
            try:
                self.models['yolo']['detector'] = cv2.dnn.readNetFromDarknet(config_path, weights_path)
                # Prefer CPU for compatibility, change to DNN_TARGET_OPENCL for GPU
                self.models['yolo']['detector'].setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.models['yolo']['detector'].setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self.models['yolo']['loaded'] = True
                logging.info("YOLO model loaded successfully")
            except Exception as e:
                logging.error(f"Error loading YOLO model: {e}")
    
    def _init_ssd_model(self, models_dir):
        """Initialize MobileNet SSD model"""
        prototxt_path = os.path.join(models_dir, "MobileNetSSD_deploy.prototxt")
        model_path = os.path.join(models_dir, "MobileNetSSD_deploy.caffemodel")
        
        # Initialize SSD entry in models dict
        self.models['ssd'] = {
            'detector': None,
            'loaded': False
        }
        
        # Download SSD files if needed
        if not os.path.exists(prototxt_path):
            logging.info("Downloading MobileNet SSD prototxt...")
            os.system(f"wget -O {prototxt_path} https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt")
        
        if not os.path.exists(model_path):
            logging.info("SSD model file not found. Skipping SSD initialization.")
            return
        
        # Initialize SSD if files exist
        if os.path.exists(prototxt_path) and os.path.exists(model_path):
            try:
                self.models['ssd']['detector'] = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
                self.models['ssd']['loaded'] = True
                logging.info("MobileNet SSD model loaded successfully")
            except Exception as e:
                logging.error(f"Error loading MobileNet SSD model: {e}")
    
    def start_detection_thread(self):
        """Start background detection thread for better performance"""
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_thread_active = True
            self.detection_thread = threading.Thread(target=self._detection_worker)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            logging.info("Detection thread started")
    
    def _detection_worker(self):
        """Worker thread for detection processing"""
        while self.detection_thread_active:
            if self.frame_for_detection is not None:
                with self.detection_lock:
                    frame = self.frame_for_detection.copy()
                    self.frame_for_detection = None
                
                # Run detection with selected model
                detections = self._detect_with_model(frame, self.model_type)
                
                # Apply improved filtering
                filtered_detections = self._filter_detections(detections)
                
                # Update detections
                with self.detection_lock:
                    self.detections = filtered_detections
            
            # Sleep to avoid consuming too much CPU
            time.sleep(0.01)
    
    def _detect_with_model(self, frame, model_type):
        """
        Detect people using specified model
        
        Args:
            frame: Input frame
            model_type: Model to use (hog, ssd, yolo, or hailo)
            
        Returns:
            list: List of detections
        """
        if model_type == 'hailo' and self.hailo_detector is not None and 'hailo' in self.models and self.models['hailo']['loaded']:
            return self.hailo_detector.detect_people(frame)
        elif model_type == 'yolo' and self.models['yolo']['loaded']:
            return self._detect_with_yolo(frame)
        elif model_type == 'ssd' and self.models['ssd']['loaded']:
            return self._detect_with_ssd(frame)
        else:
            return self._detect_with_hog(frame)
    
    def _detect_with_yolo(self, frame):
        """Detect people using YOLOv3"""
        # Get frame dimensions
        (h, w) = frame.shape[:2]
        
        # Create a blob from the frame
        blob = cv2.dnn.blobFromImage(
            frame, 
            1/255.0, 
            self.models['yolo']['input_size'], 
            swapRB=True, 
            crop=False
        )
        
        # Set input and get output layer names
        self.models['yolo']['detector'].setInput(blob)
        layer_names = self.models['yolo']['detector'].getLayerNames()
        output_layers = [layer_names[i-1] for i in self.models['yolo']['detector'].getUnconnectedOutLayers().flatten()]
        
        # Forward pass through the network
        outputs = self.models['yolo']['detector'].forward(output_layers)
        
        people = []
        boxes = []
        confidences = []
        class_ids = []
        
        # Process each output layer
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                
                # Filter for person class (ID 0 in COCO dataset)
                if class_id == 0 and confidence > self.confidence_threshold:
                    # Scale the bounding box coordinates back to the frame size
                    box = detection[0:4] * np.array([w, h, w, h])
                    (center_x, center_y, width, height) = box.astype("int")
                    
                    # Calculate top-left corner coordinates
                    x = int(center_x - (width / 2))
                    y = int(center_y - (height / 2))
                    
                    # Add to lists
                    boxes.append([x, y, int(width), int(height)])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)
        
        # Apply non-maximum suppression to remove overlapping boxes
        if boxes:
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, 0.4)
            
            # Process the final detections
            if len(indices) > 0:
                for i in indices.flatten():
                    x, y, w, h = boxes[i]
                    
                    # Ensure coordinates are within frame bounds
                    x = max(0, x)
                    y = max(0, y)
                    
                    people.append({
                        'box': (x, y, w, h),
                        'confidence': confidences[i],
                        'detector': 'YOLO'
                    })
        
        return people
    
    def _detect_with_ssd(self, frame):
        """Detect people using MobileNet SSD"""
        # Get frame dimensions
        (h, w) = frame.shape[:2]
        
        # Create a blob from the frame
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
        
        # Set the blob as input to the network
        self.models['ssd']['detector'].setInput(blob)
        
        # Forward pass to get detections
        detections = self.models['ssd']['detector'].forward()
        
        people = []
        
        # Process the detections
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > self.confidence_threshold:
                # Extract the class ID
                class_id = int(detections[0, 0, i, 1])
                
                # Person class is ID 15 in MobileNet SSD
                if class_id == 15:
                    # Get bounding box coordinates
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    # Calculate width and height
                    width = endX - startX
                    height = endY - startY
                    
                    # Ensure coordinates are within frame bounds
                    startX = max(0, startX)
                    startY = max(0, startY)
                    
                    # Add to people list
                    people.append({
                        'box': (startX, startY, width, height),
                        'confidence': float(confidence),
                        'detector': 'SSD'
                    })
        
        return people
    
    def _detect_with_hog(self, frame):
        """Detect people using HOG descriptor"""
        # Resize for faster detection
        scale_factor = min(1.0, 400 / frame.shape[1])
        frame_resized = cv2.resize(frame, (0, 0), fx=scale_factor, fy=scale_factor)
        
        # Detect people
        boxes, weights = self.models['hog']['detector'].detectMultiScale(
            frame_resized, 
            winStride=(8, 8),
            padding=(8, 8), 
            scale=1.05
        )
        
        people = []
        
        # Scale boxes back to original frame size
        if len(boxes) > 0:
            for i, (x, y, w, h) in enumerate(boxes):
                # Get confidence if available
                confidence = float(weights[i]) if i < len(weights) else 0.5
                
                # Skip detections with low confidence
                if confidence < self.confidence_threshold:
                    continue
                
                # Scale the box back to original size
                x = int(x / scale_factor)
                y = int(y / scale_factor)
                w = int(w / scale_factor)
                h = int(h / scale_factor)
                
                people.append({
                    'box': (x, y, w, h),
                    'confidence': confidence,
                    'detector': 'HOG'
                })
        
        return people
    
    def _filter_detections(self, detections):
        """
        Filter detections to remove body parts and false positives
        
        Args:
            detections: List of detection dictionaries
            
        Returns:
            list: Filtered detections
        """
        filtered = []
        
        for detection in detections:
            x, y, w, h = detection['box']
            
            # Size check - filter out small detections (usually body parts)
            if h < self.min_person_height or w < self.min_person_width:
                continue
            
            # Aspect ratio check - people are typically taller than wide
            aspect_ratio = h / w if w > 0 else 0
            if aspect_ratio < self.min_aspect_ratio:
                continue
            
            # Position check - reject detections that are mostly outside the frame
            if y + h < 0 or y > self.frame_height or x + w < 0 or x > self.frame_width:
                continue
            
            # Add to filtered detections
            filtered.append(detection)
        
        # Non-maximum suppression to remove overlapping detections
        if len(filtered) > 1:
            boxes = np.array([d['box'] for d in filtered])
            confidences = np.array([d['confidence'] for d in filtered])
            
            # Convert (x, y, w, h) to (x1, y1, x2, y2) for NMS
            boxes_xyxy = []
            for x, y, w, h in boxes:
                boxes_xyxy.append([x, y, x + w, y + h])
            
            # Apply NMS
            indices = cv2.dnn.NMSBoxes(
                boxes_xyxy, 
                confidences, 
                self.confidence_threshold, 
                0.45  # NMS threshold
            )
            
            # Create new filtered list using NMS results
            nms_filtered = []
            if len(indices) > 0:
                for i in indices.flatten():
                    nms_filtered.append(filtered[i])
                return nms_filtered
        
        return filtered
    
    def detect_people(self, frame):
        """
        Detect people in a frame
        
        Args:
            frame: Input frame
            
        Returns:
            list: List of detections after filtering
        """
        # Update frame dimensions
        self.frame_height, self.frame_width = frame.shape[:2]
        
        # Update FPS calculation
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= 1.0:
            self.fps = self.frame_count / elapsed_time
            self.frame_count = 0
            self.start_time = time.time()
        
        # Submit frame for background processing if thread is active
        if self.detection_thread_active:
            with self.detection_lock:
                # Only update if previous frame has been processed
                if self.frame_for_detection is None:
                    self.frame_for_detection = frame.copy()
        else:
            # Fallback to synchronous detection
            detections = self._detect_with_model(frame, self.model_type)
            filtered_detections = self._filter_detections(detections)
            with self.detection_lock:
                self.detections = filtered_detections
        
        # Return current detections
        with self.detection_lock:
            return self.detections.copy()
    
    def set_model(self, model_type):
        """
        Change the detection model
        
        Args:
            model_type: New model type (hog, ssd, yolo, or hailo)
        
        Returns:
            bool: True if successful, False otherwise
        """
        model_type = model_type.lower()
        
        # Handle Hailo specially
        if model_type == 'hailo':
            if not HAILO_AVAILABLE:
                logging.warning("Hailo support not available. Keeping current model.")
                return False
                
            # If the hailo detector is not initialized yet, initialize it now
            if self.hailo_detector is None:
                try:
                    self.hailo_detector = HailoPersonDetector(confidence_threshold=self.confidence_threshold)
                    self.models['hailo'] = {
                        'detector': 'HAILO_ACCEL',
                        'loaded': True if self.hailo_detector.device is not None else False
                    }
                except Exception as e:
                    logging.error(f"Error initializing Hailo detector: {e}")
                    self.models['hailo'] = {
                        'detector': None,
                        'loaded': False
                    }
                    return False
            
            # Only switch if the detector is properly initialized
            if 'hailo' in self.models and self.models['hailo']['loaded']:
                self.model_type = 'hailo'
                logging.info("Switched to Hailo AI accelerator model")
                return True
            return False
            
        # For other models
        if model_type in self.models and self.models[model_type]['loaded']:
            self.model_type = model_type
            return True
        return False
    
    def get_fps(self):
        """Get current detection FPS"""
        return self.fps
    
    def set_confidence_threshold(self, threshold):
        """
        Set new confidence threshold
        
        Args:
            threshold: New confidence threshold (0-1)
        """
        self.confidence_threshold = max(0.1, min(1.0, threshold))
    
    def cleanup(self):
        """Clean up resources"""
        # Stop detection thread
        self.detection_thread_active = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
            logging.info("Detection thread stopped")
            
        # Clean up Hailo resources if available
        if self.hailo_detector is not None:
            self.hailo_detector.cleanup()
            logging.info("Hailo detector resources released")