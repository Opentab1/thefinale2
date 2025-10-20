"""
Hailo AI accelerator detector placeholder
This module will be used when Hailo hardware is available
"""

import logging

logger = logging.getLogger(__name__)

# Hailo hardware is optional
HAILO_AVAILABLE = False

class HailoPersonDetector:
    """Placeholder for Hailo AI accelerator detector"""
    def __init__(self, confidence_threshold=0.5):
        logger.warning("Hailo detector not implemented. Please install hailo-rpi5-examples for acceleration.")
        self.device = None
        self.confidence_threshold = confidence_threshold
    
    def detect_people(self, frame):
        """Placeholder detection method"""
        return []
    
    def cleanup(self):
        """Cleanup resources"""
        pass
