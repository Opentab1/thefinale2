import time
from typing import Dict, List, Tuple
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

    def _center(self, box: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x, y, w, h = box
        return (x + w // 2, y + h // 2)

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

    def process_detections(self, detections: List[Dict], frame) -> Tuple[object, Dict]:
        self.height, self.width = frame.shape[:2]
        now = time.time()
        current_ids = set()

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
                    self.entries += 1
                current_ids.add(match_id)

        # Handle missing (exits or invalid)
        for tid, data in list(self.tracked.items()):
            if tid not in current_ids:
                dt = now - data['last_seen']
                if dt > 2.0:
                    if data['status'] == 'active':
                        self.exits += 1
                        data['status'] = 'exited'
                    elif data['status'] == 'tentative':
                        data['status'] = 'invalid'

        self.current = sum(1 for _, d in self.tracked.items() if d['status'] == 'active')
        return frame, {
            'entries': self.entries,
            'exits': self.exits,
            'current': self.current,
        }
