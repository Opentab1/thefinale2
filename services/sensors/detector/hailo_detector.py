"""
Production-ready Hailo AI accelerator detector.

This detector wraps Hailo's Python runtime (hailo_platform) to run YOLO models that
have been compiled to HEF files. It letterboxes OpenCV frames, feeds them to the
accelerator, and returns Pulse-friendly detection dictionaries.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_HAILO_IMPORT_ERROR: Optional[str] = None
try:
    from hailo_platform import (  # type: ignore
        HEF,
        VDevice,
        HailoStreamInterface,
        InferVStreams,
        ConfigureParams,
        InputVStreamParams,
        OutputVStreamParams,
        FormatType,
    )
except Exception as exc:  # pragma: no cover - executes only when Hailo SDK missing
    # Keep module importable even without the SDK so CPU fallback still works.
    HEF = VDevice = HailoStreamInterface = InferVStreams = ConfigureParams = None  # type: ignore
    InputVStreamParams = OutputVStreamParams = FormatType = None  # type: ignore
    _HAILO_IMPORT_ERROR = str(exc)

_HAILO_DEVICE_PATHS: Tuple[str, ...] = ("/dev/hailo0", "/dev/apex_0")


def _hardware_present() -> bool:
    return any(os.path.exists(path) for path in _HAILO_DEVICE_PATHS)


HAILO_AVAILABLE: bool = _HAILO_IMPORT_ERROR is None and _hardware_present()

# Default YOLO anchors/strides (YOLOv5 compatible). Users can override via constructor.
DEFAULT_ANCHORS = np.array(
    [
        10, 13, 16, 30, 33, 23,
        30, 61, 62, 45, 59, 119,
        116, 90, 156, 198, 373, 326,
    ],
    dtype=np.float32,
).reshape(3, 3, 2)
DEFAULT_STRIDES = (8, 16, 32)


class HailoPersonDetector:
    """High-performance person detector powered by the Hailo AI hat."""

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.45,
        hef_path: Optional[str] = None,
        input_size: Optional[Tuple[int, int]] = None,
        anchors: Optional[Sequence[Sequence[Sequence[float]]]] = None,
        strides: Optional[Sequence[int]] = None,
        num_classes: int = 80,
        person_class_ids: Optional[Sequence[int]] = None,
        max_detections: int = 50,
    ) -> None:
        if not HAILO_AVAILABLE:
            reason = _HAILO_IMPORT_ERROR or "Hailo hardware not detected"
            raise RuntimeError(
                "Hailo AI hat not available. "
                f"{reason}. Ensure hailo-platform is installed and /dev/hailo0 exists."
            )

        self.confidence_threshold = float(max(0.05, min(0.99, confidence_threshold)))
        self.nms_threshold = float(max(0.05, min(0.9, nms_threshold)))
        self.num_classes = int(max(1, num_classes))
        self.person_class_ids = tuple(person_class_ids or (0,))
        self.max_detections = int(max(1, max_detections))
        self.anchor_sets = np.array(anchors if anchors is not None else DEFAULT_ANCHORS, dtype=np.float32)
        self.strides = tuple(int(s) for s in (strides if strides is not None else DEFAULT_STRIDES))
        if self.anchor_sets.shape[0] != len(self.strides):
            raise ValueError("Anchors/strides mismatch: provide the same number of scales for each.")

        self.hef_path = self._resolve_hef_path(hef_path)
        self.device: Optional[VDevice] = None  # type: ignore[assignment]
        self.network_group = None
        self.network_group_params = None
        self.input_format = getattr(FormatType, "UINT8", None) if FormatType else None
        self.output_format = getattr(FormatType, "FLOAT32", None) if FormatType else None
        self.input_height = 640
        self.input_width = 640

        if input_size and len(input_size) == 2:
            self.input_width, self.input_height = (int(input_size[0]), int(input_size[1]))

        self._infer_gen = None
        self.loaded = False

        self._init_pipeline()
        self.loaded = True
        logger.info(
            "✅ Hailo detector ready (model=%s, input=%dx%d, anchors=%s)",
            os.path.basename(self.hef_path),
            self.input_width,
            self.input_height,
            self.anchor_sets.shape,
        )

    # --------------------------------------------------------------------- #
    # Public API                                                            #
    # --------------------------------------------------------------------- #
    def detect_people(self, frame) -> List[Dict]:
        if not self.loaded or frame is None or frame.size == 0:
            return []

        try:
            tensor, ratio, pad = self._preprocess_frame(frame)
            outputs = self._run_inference(tensor)
            detections = self._postprocess(outputs, ratio, pad, frame.shape[:2])
            if len(detections) > self.max_detections:
                detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)[: self.max_detections]
            return detections
        except Exception as exc:
            logger.error(f"Hailo detection failed: {exc}", exc_info=True)
            return []

    def cleanup(self):
        """Release accelerator resources."""
        if self._infer_gen:
            try:
                self._infer_gen.close()
            except Exception:
                pass
            self._infer_gen = None

        if self.network_group is not None:
            try:
                self.network_group = None
            except Exception:
                pass

        if self.device is not None:
            try:
                self.device.release()  # type: ignore[attr-defined]
            except AttributeError:
                try:
                    self.device.close()  # type: ignore[attr-defined]
                except Exception:
                    pass
            self.device = None

        self.loaded = False

    # --------------------------------------------------------------------- #
    # Initialization helpers                                                #
    # --------------------------------------------------------------------- #
    def _resolve_hef_path(self, explicit_path: Optional[str]) -> str:
        candidates: List[str] = []
        if explicit_path:
            candidates.append(explicit_path)
        env_path = os.getenv("PULSE_HAILO_HEF")
        if env_path:
            candidates.append(env_path)

        repo_models = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "hailo")
        )
        candidates.extend(
            [
                os.path.join("/opt/pulse/models/hailo", "yolov5m_wo_spp.hef"),
                os.path.join("/opt/pulse/models/hailo", "yolov8s.hef"),
                os.path.join(repo_models, "yolov5m_wo_spp.hef"),
                os.path.join(repo_models, "yolov8s.hef"),
            ]
        )

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)

        raise FileNotFoundError(
            "No HEF model file found for Hailo detector. "
            "Set PULSE_HAILO_HEF or place a YOLO HEF in /opt/pulse/models/hailo/."
        )

    def _init_pipeline(self):
        hef = HEF(self.hef_path)  # type: ignore[operator]
        configure_params = ConfigureParams.create_from_hef(  # type: ignore[operator]
            hef, interface=HailoStreamInterface.PCIe  # type: ignore[operator]
        )
        self.device = VDevice()  # type: ignore[operator]
        self.network_group = self.device.configure(hef, configure_params)[0]  # type: ignore[index]
        self.network_group_params = self.network_group.create_params()

        self.input_vstreams_params = InputVStreamParams.make_from_network_group(  # type: ignore[operator]
            self.network_group,
            quantized=False,
            format_type=self.input_format,
        )
        self.output_vstreams_params = OutputVStreamParams.make_from_network_group(  # type: ignore[operator]
            self.network_group,
            quantized=False,
            format_type=self.output_format,
        )

        self._infer_gen = self._build_infer_generator()
        self._extract_input_shape(hef)

    def _extract_input_shape(self, hef):
        try:
            infos = hef.get_input_vstream_infos()
            if infos:
                dims = self._shape_tuple(infos[0])
                if dims:
                    if len(dims) == 4:
                        _, h, w, _ = dims
                    elif len(dims) == 3:
                        h, w, _ = dims
                    else:
                        h = w = None
                    if h and w:
                        self.input_height = int(h)
                        self.input_width = int(w)
        except Exception as exc:
            logger.debug(f"Unable to read HEF input shape, defaulting to {self.input_width}x{self.input_height}: {exc}")

    def _build_infer_generator(self):
        if self.network_group is None:
            raise RuntimeError("Hailo network group not initialized")

        input_params = self.input_vstreams_params
        output_params = self.output_vstreams_params
        net_group = self.network_group
        params = self.network_group_params

        def _generator():
            with InferVStreams(net_group, input_params, output_params) as infer_pipeline:  # type: ignore[operator]
                with net_group.activate(params):  # type: ignore[call-arg]
                    while True:
                        frame = (yield)
                        if frame is None:
                            break
                        yield infer_pipeline.infer(frame)

        return _generator()

    # --------------------------------------------------------------------- #
    # Inference + preprocessing                                             #
    # --------------------------------------------------------------------- #
    def _run_inference(self, tensor: np.ndarray) -> Dict[str, np.ndarray]:
        if self._infer_gen is None:
            raise RuntimeError("Hailo inference pipeline not ready")
        try:
            next(self._infer_gen)
        except StopIteration:
            self._infer_gen = self._build_infer_generator()
            next(self._infer_gen)
        return self._infer_gen.send(tensor)

    def _preprocess_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        letterboxed, ratio, pad = self._letterbox(rgb, (self.input_width, self.input_height))

        if self.input_format == getattr(FormatType, "FLOAT32", None):
            tensor = letterboxed.astype(np.float32) / 255.0
        else:
            tensor = letterboxed.astype(np.uint8)

        tensor = np.expand_dims(tensor, axis=0)
        return tensor, ratio, pad

    def _letterbox(
        self,
        img: np.ndarray,
        new_shape: Tuple[int, int],
        color: Tuple[int, int, int] = (114, 114, 114),
    ) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        shape = img.shape[:2]  # (h, w)
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        r = min(new_shape[0] / shape[1], new_shape[1] / shape[0])
        new_unpad = (int(round(shape[1] * r)), int(round(shape[0] * r)))
        dw = new_shape[0] - new_unpad[0]
        dh = new_shape[1] - new_unpad[1]

        dw /= 2
        dh /= 2

        resized = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        bordered = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)

        return bordered, r, (left, top)

    # --------------------------------------------------------------------- #
    # Post-processing                                                       #
    # --------------------------------------------------------------------- #
    def _postprocess(
        self,
        outputs: Dict[str, np.ndarray],
        ratio: float,
        pad: Tuple[int, int],
        frame_shape: Tuple[int, int],
    ) -> List[Dict]:
        if not outputs:
            return []

        layers = []
        for name, tensor in outputs.items():
            arr = np.array(tensor)
            if arr.ndim < 3:
                continue
            shape = arr.shape
            if arr.ndim == 4 and shape[0] == 1:
                shape = shape[1:]
            area = shape[0] * shape[1]
            layers.append((area, name, arr))

        if not layers:
            return []

        # Sort largest -> smallest spatial resolution to align with anchors/strides order
        layers.sort(key=lambda item: item[0], reverse=True)

        detections: List[Dict] = []
        for idx, (_, name, arr) in enumerate(layers[: len(self.anchor_sets)]):
            stride = self.strides[min(idx, len(self.strides) - 1)]
            anchors = self.anchor_sets[min(idx, len(self.anchor_sets) - 1)]
            detections.extend(self._decode_layer(arr, anchors, stride, ratio, pad, frame_shape))

        return self._apply_nms(detections)

    def _decode_layer(
        self,
        tensor: np.ndarray,
        anchors: np.ndarray,
        stride: int,
        ratio: float,
        pad: Tuple[int, int],
        frame_shape: Tuple[int, int],
    ) -> List[Dict]:
        arr = np.array(tensor, dtype=np.float32)
        if arr.ndim == 4 and arr.shape[0] == 1:
            arr = arr[0]
        gh, gw, depth = arr.shape
        num_anchors = anchors.shape[0]
        attr_per_anchor = self.num_classes + 5

        if depth != num_anchors * attr_per_anchor:
            logger.debug(
                "Unexpected tensor shape for Hailo output (gh=%d, gw=%d, depth=%d). "
                "Expected %d anchors × (%d classes + 5).",
                gh,
                gw,
                depth,
                num_anchors,
                self.num_classes,
            )
            return []

        arr = arr.reshape(gh, gw, num_anchors, attr_per_anchor).transpose(2, 0, 1, 3)

        grid_x = np.broadcast_to(np.arange(gw, dtype=np.float32), (num_anchors, gh, gw))
        grid_y = np.broadcast_to(np.arange(gh, dtype=np.float32).reshape(1, gh, 1), (num_anchors, gh, gw))
        anchor_w = anchors[:, 0].reshape(num_anchors, 1, 1)
        anchor_h = anchors[:, 1].reshape(num_anchors, 1, 1)

        dx = self._sigmoid(arr[..., 0])
        dy = self._sigmoid(arr[..., 1])
        dw = self._sigmoid(arr[..., 2])
        dh = self._sigmoid(arr[..., 3])
        obj = self._sigmoid(arr[..., 4])
        cls = self._sigmoid(arr[..., 5:])

        bx = (dx * 2.0 - 0.5 + grid_x) * stride
        by = (dy * 2.0 - 0.5 + grid_y) * stride
        bw = ((dw * 2.0) ** 2) * anchor_w
        bh = ((dh * 2.0) ** 2) * anchor_h

        target_probs = cls[..., list(self.person_class_ids)]
        if target_probs.ndim == 3:
            target_probs = target_probs[..., np.newaxis]
        combined = obj[..., None] * target_probs
        best_scores = combined.max(axis=-1)

        mask = best_scores >= self.confidence_threshold
        if not np.any(mask):
            return []

        bx = bx[mask]
        by = by[mask]
        bw = bw[mask]
        bh = bh[mask]
        scores = best_scores[mask]

        pad_x, pad_y = pad
        x1 = (bx - bw / 2 - pad_x) / ratio
        y1 = (by - bh / 2 - pad_y) / ratio
        w = bw / ratio
        h = bh / ratio

        frame_h, frame_w = frame_shape
        x1 = np.clip(x1, 0, frame_w - 1)
        y1 = np.clip(y1, 0, frame_h - 1)
        w = np.clip(w, 0, frame_w - x1)
        h = np.clip(h, 0, frame_h - y1)

        detections: List[Dict] = []
        for bx1, by1, bw_, bh_, sc in zip(x1, y1, w, h, scores):
            if bw_ <= 0 or bh_ <= 0:
                continue
            detections.append(
                {
                    "box": (int(bx1), int(by1), int(bw_), int(bh_)),
                    "confidence": float(sc),
                    "detector": "HAILO",
                }
            )

        return detections

    def _apply_nms(self, detections: List[Dict]) -> List[Dict]:
        if len(detections) <= 1:
            return detections

        boxes = [d["box"] for d in detections]
        scores = [float(d["confidence"]) for d in detections]
        boxes_xyxy = [[x, y, x + w, y + h] for x, y, w, h in boxes]

        idxs = cv2.dnn.NMSBoxes(boxes_xyxy, scores, self.confidence_threshold, self.nms_threshold)
        if len(idxs) == 0:
            return detections

        idxs = idxs.flatten()
        return [detections[i] for i in idxs]

    # --------------------------------------------------------------------- #
    # Utility helpers                                                       #
    # --------------------------------------------------------------------- #
    @staticmethod
    def _shape_tuple(info) -> Optional[Tuple[int, ...]]:
        for attr in ("shape", "dims"):
            dims = getattr(info, attr, None)
            if dims:
                try:
                    return tuple(int(d) for d in dims)
                except TypeError:
                    pass
        h = getattr(info, "height", None)
        w = getattr(info, "width", None)
        c = getattr(info, "features", getattr(info, "channels", None))
        if None not in (h, w, c):
            return int(h), int(w), int(c)
        return None

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))
