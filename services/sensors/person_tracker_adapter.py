import time
from typing import Dict, List, Tuple, Optional
import numpy as np


class PersonTracker:
    """Simple, robust tracker adapted from party_box for stable people counts.

    - Matches detections between frames by nearest-center within a distance/time window
    - Promotes tracks from 'tentative' to 'active' after N frames (min_detection_frames)
    - Increments entry/exit counters when tracks appear/disappear
    """

    def __init__(self, confidence_threshold: float = 0.5, min_detection_frames: int = 5):
        self.confidence_threshold = confidence_threshold
        self.min_detection_frames = min_detection_frames

        self.tracked: Dict[int, Dict] = {}
        self.next_id: int = 0

        self.entries: int = 0
        self.exits: int = 0
        self.current: int = 0

        self.width: int = 0
        self.height: int = 0

        self.zone_line_enabled: bool = False
        self.zone_line_config: Optional[Dict] = None
        self.zone_labels = {"A": "A", "B": "B"}

    def _center(self, box: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x, y, w, h = box
        return (x + w // 2, y + h // 2)

    def configure_crossover_line(self, config: Dict) -> None:
        if not config:
            return
        orientation = (config.get("orientation") or "horizontal").lower()
        if orientation not in ("horizontal", "vertical"):
            orientation = "horizontal"
        position = float(config.get("position", 0.5))
        position = max(0.0, min(1.0, position))
        entry_zone = (config.get("entry_zone") or "A").upper()
        if entry_zone not in ("A", "B"):
            entry_zone = "A"
        label_a = config.get("label_a") or "A"
        label_b = config.get("label_b") or "B"
        hysteresis = float(config.get("hysteresis_px", 12.0))
        self.zone_line_config = {
            "orientation": orientation,
            "position": position,
            "entry_zone": entry_zone,
            "hysteresis_px": abs(hysteresis),
        }
        self.zone_labels = {"A": label_a, "B": label_b}
        self.zone_line_enabled = True
        self.entries = 0
        self.exits = 0
        for track in self.tracked.values():
            track["zone"] = None

    def _valid(self, det: Dict) -> bool:
        x, y, w, h = det['box']
        if det.get('confidence', 0.0) < self.confidence_threshold:
            return False
        if h < 80 or w < 30:
            return False
        # people are typically taller than wide
        if w > 0 and (h / w) < 1.2:
            return False
        # must be at least partially in-frame
        if (x + w) < 0 or x > self.width or (y + h) < 0 or y > self.height:
            return False
        return True

    def _zone_for_center(self, center: Tuple[int, int], previous_zone: Optional[str]) -> Optional[str]:
        if not self.zone_line_enabled or not self.zone_line_config:
            return None
        if self.width <= 0 or self.height <= 0:
            return previous_zone
        orientation = self.zone_line_config["orientation"]
        pos = self.zone_line_config["position"]
        hysteresis = float(self.zone_line_config.get("hysteresis_px", 0.0))
        x, y = center
        if orientation == "vertical":
            line = self.width * pos
            if x <= line - hysteresis:
                return "A"
            if x >= line + hysteresis:
                return "B"
            return previous_zone or ("A" if x < line else "B")
        else:
            line = self.height * pos
            if y <= line - hysteresis:
                return "A"
            if y >= line + hysteresis:
                return "B"
            return previous_zone or ("A" if y < line else "B")

    def _zone_label(self, zone_code: Optional[str]) -> str:
        if not zone_code:
            return ""
        return self.zone_labels.get(zone_code, zone_code)

    def _handle_zone_transition(
        self,
        track_id: int,
        previous_zone: Optional[str],
        new_zone: Optional[str],
        timestamp: float,
        frame_events: List[Dict],
    ) -> None:
        if not new_zone or not previous_zone or new_zone == previous_zone:
            return
        entry_zone = self.zone_line_config["entry_zone"]
        if previous_zone == entry_zone and new_zone != entry_zone:
            self.entries += 1
            event_type = "entry"
        elif new_zone == entry_zone and previous_zone != entry_zone:
            self.exits += 1
            event_type = "exit"
        else:
            return
        frame_events.append(
            {
                "type": event_type,
                "track_id": track_id,
                "timestamp": timestamp,
                "from_zone": previous_zone,
                "to_zone": new_zone,
                "from_label": self._zone_label(previous_zone),
                "to_label": self._zone_label(new_zone),
            }
        )

    def process_detections(self, detections: List[Dict], frame) -> Tuple[object, Dict]:
        self.height, self.width = frame.shape[:2]
        now = time.time()
        current_ids = set()
        frame_events: List[Dict] = []

        # Assign each detection to an existing track if close enough; otherwise create new
        for d in detections:
            if not self._valid(d):
                continue
            c = self._center(d['box'])
            match_id = None
            best_dist = 1e12
            for tid, data in self.tracked.items():
                if data['status'] in ('exited', 'invalid'):
                    continue
                px, py = data['center']
                dt = now - data['last_seen']
                if dt > 1.0:
                    continue
                dist = (c[0] - px) ** 2 + (c[1] - py) ** 2
                if dist < best_dist and dist < (100 ** 2):
                    best_dist = dist
                    match_id = tid

            if match_id is None:
                self.tracked[self.next_id] = {
                    'box': d['box'],
                    'center': c,
                    'last_seen': now,
                    'frames': 1,
                    'status': 'tentative',
                    'zone': self._zone_for_center(c, None) if self.zone_line_enabled else None,
                }
                current_ids.add(self.next_id)
                self.next_id += 1
            else:
                t = self.tracked[match_id]
                t['box'] = d['box']
                t['center'] = c
                t['last_seen'] = now
                t['frames'] = t.get('frames', 0) + 1
                if t['status'] == 'tentative' and t['frames'] >= self.min_detection_frames:
                    t['status'] = 'active'
                    if not self.zone_line_enabled:
                        self.entries += 1
                current_ids.add(match_id)
                if self.zone_line_enabled:
                    previous_zone = t.get('zone')
                    new_zone = self._zone_for_center(c, previous_zone)
                    if new_zone:
                        self._handle_zone_transition(match_id, previous_zone, new_zone, now, frame_events)
                        t['zone'] = new_zone

        # Handle missing (exits or invalid)
        for tid, data in list(self.tracked.items()):
            if tid not in current_ids:
                dt = now - data['last_seen']
                if dt > 2.0:
                    if data['status'] == 'active':
                        if not self.zone_line_enabled:
                            self.exits += 1
                        data['status'] = 'exited'
                    elif data['status'] == 'tentative':
                        data['status'] = 'invalid'

        if self.zone_line_enabled:
            self.current = max(0, self.entries - self.exits)
        else:
            self.current = sum(1 for _, d in self.tracked.items() if d['status'] == 'active')
        return frame, {
            'entries': self.entries,
            'exits': self.exits,
            'current': self.current,
            'events': frame_events,
        }
