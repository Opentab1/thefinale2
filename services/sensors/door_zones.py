"""Doorway zone configuration loader."""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, object] = {
    "defaults": {
        "orientation": "horizontal",
        "position": 0.5,
        "entry_zone": "A",
        "label_a": "A",
        "label_b": "B",
        "hysteresis_px": 12.0,
    },
    "doorways": [],
}

CONFIG_SEARCH_PATHS = [
    Path(os.environ.get("PULSE_DOOR_CONFIG", "/opt/pulse/config/door_zones.json")),
    Path(__file__).resolve().parents[3] / "config" / "door_zones.json",
]

_CACHE: Optional[Dict[str, object]] = None
_CACHE_PATH: Optional[Path] = None


def _deep_merge(base: Dict, override: Dict) -> Dict:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_door_config() -> Tuple[Dict[str, object], Optional[Path]]:
    global _CACHE, _CACHE_PATH
    if _CACHE is not None:
        return _CACHE, _CACHE_PATH

    config = copy.deepcopy(DEFAULT_CONFIG)
    selected_path = None

    for path in CONFIG_SEARCH_PATHS:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as cfg_file:
                    data = json.load(cfg_file)
                    config = _deep_merge(config, data)
                    selected_path = path
                    break
            except Exception as exc:
                logger.warning("Unable to parse door config at %s: %s", path, exc)

    _CACHE = config
    _CACHE_PATH = selected_path
    return config, selected_path


def get_zone_config(zone_name: str) -> Optional[Dict[str, object]]:
    if not zone_name:
        return None
    config, _ = load_door_config()
    defaults = config.get("defaults") or {}
    for doorway in config.get("doorways", []):
        if doorway.get("zone", "").lower() == zone_name.lower():
            merged = _deep_merge(defaults, doorway)
            merged["zone"] = doorway.get("zone", zone_name)
            return merged
    return None
