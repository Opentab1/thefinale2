"""
PartyBox-derived PersonDetector adapted for Pulse.

Provides multiple CPU-friendly person detection backends (HOG, MobileNet-SSD,
optional YOLO if weights present) with robust filtering and a simple API.

Differences vs. original:
- Defaults models directory to /opt/pulse/models (created by installer)
- Gracefully handles missing models and falls back to HOG
"""

from __future__ import annotations

import os
import logging
import time
from typing import Dict, List

import numpy as np
import cv2
import threading

logger = logging.getLogger(__name__)

# Optional Hailo accelerator support (if available in environment)
try:
    from detector.hailo_detector import HailoPersonDetector  # type: ignore
    HAILO_AVAILABLE = True
except Exception:
    HAILO_AVAILABLE = False


class PersonDetector:
    def __init__(
        self,
        confidence_threshold: float = 0.45,
        model_type: str = "hog",
        models_dir: str = "/opt/pulse/models",
    ) -> None:
        self.confidence_threshold = float(max(0.1, min(1.0, confidence_threshold)))
        self.model_type = (model_type or "hog").lower()
        self.models_dir = models_dir

        # Internal model registry
        self.models: Dict[str, Dict] = {}
        self._initialize_models()

        # Optional Hailo
        self.hailo_detector = None
        if self.model_type == "hailo" and HAILO_AVAILABLE:
            try:
                self.hailo_detector = HailoPersonDetector(confidence_threshold=self.confidence_threshold)
                self.models["hailo"] = {
                    "detector": "HAILO_ACCEL",
                    "loaded": getattr(self.hailo_detector, "device", None) is not None,
                }
            except Exception as e:
                logger.warning(f"Hailo initialization failed: {e}")
                self.models["hailo"] = {"detector": None, "loaded": False}

        # Frame stats
        self.frame_width = 0
        self.frame_height = 0
        self.frame_count = 0
        self._fps_start = time.time()
        self._fps = 0.0

        # Background detection thread support
        self._det_thread: threading.Thread | None = None
        self._det_thread_active = False
        self._frame_for_detection: np.ndarray | None = None
        self._detections: List[Dict] = []
        self._lock = threading.Lock()

        self._start_detection_thread()

    # --------------------------- Initialization --------------------------- #
    def _initialize_models(self) -> None:
        os.makedirs(self.models_dir, exist_ok=True)

        # HOG fallback (always available)
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.models["hog"] = {"detector": hog, "loaded": True}

        # MobileNet SSD (if files exist or can be downloaded by installer)
        self._init_ssd_model()

        # YOLOv3 (optional: only if weights present; we do not auto-download here)
        self._init_yolo_model()

        # Validate primary
        if self.model_type not in self.models or not self.models[self.model_type].get("loaded"):
            logger.warning(f"Selected model '{self.model_type}' not available. Falling back to HOG.")
            self.model_type = "hog"

    def _init_ssd_model(self) -> None:
        prototxt = os.path.join(self.models_dir, "MobileNetSSD_deploy.prototxt")
        caffemodel = os.path.join(self.models_dir, "MobileNetSSD_deploy.caffemodel")
        self.models["ssd"] = {"detector": None, "loaded": False}

        if not (os.path.exists(prototxt) and os.path.exists(caffemodel)):
            # Installer will attempt to fetch these; skip if missing
            return
        try:
            net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
            self.models["ssd"]["detector"] = net
            self.models["ssd"]["loaded"] = True
            logger.info("MobileNet-SSD model loaded")
        except Exception as e:
            logger.warning(f"Failed to load MobileNet-SSD: {e}")

    def _init_yolo_model(self) -> None:
        weights = os.path.join(self.models_dir, "yolov3.weights")
        cfg = os.path.join(self.models_dir, "yolov3.cfg")
        names = os.path.join(self.models_dir, "coco.names")
        self.models["yolo"] = {
            "detector": None,
            "loaded": False,
            "class_names": [],
            "input_size": (416, 416),
        }
        if not (os.path.exists(weights) and os.path.exists(cfg)):
            return
        try:
            if os.path.exists(names):
                with open(names, "r") as f:
                    self.models["yolo"]["class_names"] = [line.strip() for line in f]
            net = cv2.dnn.readNetFromDarknet(cfg, weights)
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.models["yolo"]["detector"] = net
            self.models["yolo"]["loaded"] = True
            logger.info("YOLOv3 model loaded")
        except Exception as e:
            logger.warning(f"Failed to load YOLOv3: {e}")

    # -------------------------- Detection thread -------------------------- #
    def _start_detection_thread(self) -> None:
        if self._det_thread is None or not self._det_thread.is_alive():
            self._det_thread_active = True
            self._det_thread = threading.Thread(target=self._detection_worker, daemon=True)
            self._det_thread.start()

    def _detection_worker(self) -> None:
        while self._det_thread_active:
            frame = None
            with self._lock:
                if self._frame_for_detection is not None:
                    frame = self._frame_for_detection.copy()
                    self._frame_for_detection = None
            if frame is not None:
                detections = self._detect_with_model(frame, self.model_type)
                filtered = self._filter_detections(detections, frame)
                with self._lock:
                    self._detections = filtered
            time.sleep(0.005)

    # ---------------------------- Model helpers --------------------------- #
    def _detect_with_model(self, frame: np.ndarray, model_type: str) -> List[Dict]:
        if model_type == "hailo" and HAILO_AVAILABLE and self.hailo_detector is not None:
            try:
                return self.hailo_detector.detect_people(frame)
            except Exception as e:
                logger.debug(f"Hailo detection failed: {e}")
        if model_type == "yolo" and self.models["yolo"].get("loaded"):
            return self._detect_with_yolo(frame)
        if model_type == "ssd" and self.models["ssd"].get("loaded"):
            return self._detect_with_ssd(frame)
        return self._detect_with_hog(frame)

    def _detect_with_yolo(self, frame: np.ndarray) -> List[Dict]:
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, self.models["yolo"]["input_size"], swapRB=True, crop=False)
        net = self.models["yolo"]["detector"]
        net.setInput(blob)
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]
        outputs = net.forward(output_layers)

        boxes: List[List[int]] = []
        confidences: List[float] = []
        people: List[Dict] = []
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = int(np.argmax(scores))
                confidence = float(scores[class_id])
                if class_id == 0 and confidence > self.confidence_threshold:
                    bx = detection[0:4] * np.array([w, h, w, h])
                    cx, cy, bw, bh = bx.astype(int)
                    x = int(cx - bw / 2)
                    y = int(cy - bh / 2)
                    boxes.append([x, y, int(bw), int(bh)])
                    confidences.append(confidence)
        if boxes:
            indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, 0.4)
            for i in (indices.flatten() if len(indices) > 0 else []):
                x, y, bw, bh = boxes[i]
                people.append({"box": (x, y, bw, bh), "confidence": confidences[i], "detector": "YOLO"})
        return people

    def _detect_with_ssd(self, frame: np.ndarray) -> List[Dict]:
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 0.007843, (300, 300), 127.5)
        net = self.models["ssd"]["detector"]
        net.setInput(blob)
        detections = net.forward()
        people: List[Dict] = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence <= self.confidence_threshold:
                continue
            class_id = int(detections[0, 0, i, 1])
            if class_id != 15:  # person class in SSD
                continue
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            bw = x2 - x1
            bh = y2 - y1
            people.append({"box": (max(0, x1), max(0, y1), bw, bh), "confidence": confidence, "detector": "SSD"})
        return people

    def _detect_with_hog(self, frame: np.ndarray) -> List[Dict]:
        scale = min(1.0, 400 / max(1, frame.shape[1]))
        resized = frame if scale == 1.0 else cv2.resize(frame, None, fx=scale, fy=scale)
        hog: cv2.HOGDescriptor = self.models["hog"]["detector"]
        boxes, weights = hog.detectMultiScale(resized, winStride=(8, 8), padding=(8, 8), scale=1.05)
        people: List[Dict] = []
        for i, (x, y, w, h) in enumerate(boxes):
            conf = float(weights[i]) if i < len(weights) else 0.5
            if conf < self.confidence_threshold:
                continue
            if scale != 1.0:
                x = int(x / scale)
                y = int(y / scale)
                w = int(w / scale)
                h = int(h / scale)
            people.append({"box": (x, y, w, h), "confidence": conf, "detector": "HOG"})
        return people

    # ----------------------------- Post-filter ---------------------------- #
    def _filter_detections(self, detections: List[Dict], frame: np.ndarray) -> List[Dict]:
        h, w = frame.shape[:2]
        filtered: List[Dict] = []
        for det in detections:
            x, y, bw, bh = det["box"]
            if bh < 80 or bw < 30:
                continue
            if bw > 0 and (bh / bw) < 1.2:
                continue
            if (x + bw) < 0 or x > w or (y + bh) < 0 or y > h:
                continue
            filtered.append(det)
        if len(filtered) <= 1:
            return filtered
        boxes = np.array([d["box"] for d in filtered])
        confidences = np.array([float(d.get("confidence", 0.5)) for d in filtered])
        boxes_xyxy = [[x, y, x + bw, y + bh] for x, y, bw, bh in boxes]
        indices = cv2.dnn.NMSBoxes(boxes_xyxy, confidences, self.confidence_threshold, 0.45)
        if len(indices) == 0:
            return filtered
        return [filtered[i] for i in indices.flatten()]

    # ------------------------------- Public ------------------------------- #
    def detect_people(self, frame: np.ndarray) -> List[Dict]:
        try:
            self.frame_height, self.frame_width = frame.shape[:2]
            self.frame_count += 1
            elapsed = time.time() - self._fps_start
            if elapsed >= 1.0:
                self._fps = self.frame_count / max(1e-6, elapsed)
                self.frame_count = 0
                self._fps_start = time.time()

            if self._det_thread_active:
                with self._lock:
                    if self._frame_for_detection is None:
                        self._frame_for_detection = frame.copy()
                with self._lock:
                    return list(self._detections)

            # Synchronous path
            dets = self._detect_with_model(frame, self.model_type)
            return self._filter_detections(dets, frame)
        except Exception as e:
            logger.error(f"PersonDetector error: {e}")
            return []

    def set_model(self, model_type: str) -> bool:
        model_type = (model_type or "hog").lower()
        if model_type == "hailo":
            if not HAILO_AVAILABLE:
                logger.warning("Hailo not available")
                return False
            if self.hailo_detector is None:
                try:
                    self.hailo_detector = HailoPersonDetector(confidence_threshold=self.confidence_threshold)  # type: ignore
                    self.models["hailo"] = {
                        "detector": "HAILO_ACCEL",
                        "loaded": getattr(self.hailo_detector, "device", None) is not None,
                    }
                except Exception as e:
                    logger.warning(f"Failed to init Hailo: {e}")
                    self.models["hailo"] = {"detector": None, "loaded": False}
                    return False
            if not self.models.get("hailo", {}).get("loaded"):
                return False
            self.model_type = "hailo"
            return True

        if self.models.get(model_type, {}).get("loaded"):
            self.model_type = model_type
            return True
        return False

    def get_fps(self) -> float:
        return float(self._fps)

    def cleanup(self) -> None:
        self._det_thread_active = False
        if self._det_thread and self._det_thread.is_alive():
            try:
                self._det_thread.join(timeout=1.0)
            except Exception:
                pass
