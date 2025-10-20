"""
Lightweight person detector adapted from party_box.

Backends:
- HOG (always available)
- MobileNet SSD via OpenCV DNN when model files are present in /opt/pulse/models
"""

from __future__ import annotations

import os
import logging
from typing import List, Dict

import numpy as np
import cv2


logger = logging.getLogger(__name__)


class PersonDetector:
    def __init__(self, confidence_threshold: float = 0.45, model_type: str = "hog"):
        self.confidence_threshold = float(confidence_threshold)
        self.model_type = (model_type or "hog").lower()

        self.models: Dict[str, Dict] = {}
        self._init_models()

        if self.model_type not in self.models or not self.models[self.model_type].get("loaded"):
            logger.warning("Model %s unavailable; falling back to HOG", self.model_type)
            self.model_type = "hog"

        # Filtering thresholds (favor whole-person boxes)
        self.min_person_height = 80
        self.min_person_width = 30
        self.min_aspect_ratio = 1.2

        # Frame dims (used by filter)
        self.frame_width = None
        self.frame_height = None

    def _models_dir(self) -> str:
        return "/opt/pulse/models"

    def _init_models(self):
        models_dir = self._models_dir()
        os.makedirs(models_dir, exist_ok=True)

        # HOG fallback
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.models["hog"] = {"detector": hog, "loaded": True}

        # MobileNet SSD
        prototxt = os.path.join(models_dir, "MobileNetSSD_deploy.prototxt")
        model = os.path.join(models_dir, "MobileNetSSD_deploy.caffemodel")
        self.models["ssd"] = {"detector": None, "loaded": False}
        if os.path.exists(prototxt) and os.path.exists(model):
            try:
                net = cv2.dnn.readNetFromCaffe(prototxt, model)
                self.models["ssd"] = {"detector": net, "loaded": True}
                logger.info("Loaded MobileNet SSD model")
            except Exception as e:
                logger.warning(f"Failed to load MobileNet SSD: {e}")

    def detect_people(self, frame) -> List[Dict]:
        self.frame_height, self.frame_width = frame.shape[:2]
        if self.model_type == "ssd" and self.models["ssd"].get("loaded"):
            dets = self._detect_ssd(frame)
        else:
            dets = self._detect_hog(frame)
        return self._filter_detections(dets)

    def _detect_hog(self, frame) -> List[Dict]:
        scale = min(1.0, 400 / max(1, frame.shape[1]))
        resized = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        hog = self.models["hog"]["detector"]
        boxes, weights = hog.detectMultiScale(resized, winStride=(8, 8), padding=(8, 8), scale=1.05)
        out: List[Dict] = []
        for i, (x, y, w, h) in enumerate(boxes):
            conf = float(weights[i]) if i < len(weights) else 0.5
            if conf < self.confidence_threshold:
                continue
            out.append({
                "box": (int(x / scale), int(y / scale), int(w / scale), int(h / scale)),
                "confidence": conf,
                "detector": "HOG"
            })
        return out

    def _detect_ssd(self, frame) -> List[Dict]:
        net = self.models["ssd"]["detector"]
        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        detections = net.forward()
        out: List[Dict] = []
        for i in range(detections.shape[2]):
            conf = float(detections[0, 0, i, 2])
            if conf <= self.confidence_threshold:
                continue
            class_id = int(detections[0, 0, i, 1])
            if class_id != 15:  # person
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            out.append({
                "box": (x1, y1, int(x2 - x1), int(y2 - y1)),
                "confidence": conf,
                "detector": "SSD"
            })
        return out

    def _filter_detections(self, detections: List[Dict]) -> List[Dict]:
        filtered: List[Dict] = []
        for d in detections or []:
            x, y, w, h = d.get("box", (0, 0, 0, 0))
            if h < self.min_person_height or w < self.min_person_width:
                continue
            aspect = h / w if w > 0 else 0
            if aspect < self.min_aspect_ratio:
                continue
            if self.frame_height and self.frame_width:
                if (y + h) < 0 or y > self.frame_height or (x + w) < 0 or x > self.frame_width:
                    continue
            filtered.append(d)

        if len(filtered) > 1:
            boxes_xyxy = []
            confs = []
            for d in filtered:
                x, y, w, h = d["box"]
                boxes_xyxy.append([x, y, x + w, y + h])
                confs.append(float(d.get("confidence", 0.5)))
            idxs = cv2.dnn.NMSBoxes(boxes_xyxy, confs, self.confidence_threshold, 0.45)
            if len(idxs) > 0:
                return [filtered[i] for i in idxs.flatten()]
        return filtered

    def set_model(self, model_type: str) -> bool:
        model_type = (model_type or "hog").lower()
        if model_type in self.models and self.models[model_type].get("loaded"):
            self.model_type = model_type
            return True
        return False

    def cleanup(self):
        # No resources to release in this lightweight version
        pass
