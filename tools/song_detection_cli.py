#!/usr/bin/env python3
"""
Command-line helper to run a single (or repeated) song-detection attempt
using the same configuration the audio service uses. Helpful for verifying
RapidAPI keys + microphone input on the Pi without starting the daemon.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "services"))

from services.sensors.simple_song_detector import SongDetector, load_song_config  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Pulse song detection CLI tester")
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Number of detection attempts to run (default: 1)",
    )
    parser.add_argument(
        "--sleep",
        type=int,
        default=60,
        help="Seconds to sleep between attempts when --loops > 1 (default: 60)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING...)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON payload (song + health) instead of friendly text",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    config, cfg_path = load_song_config()
    logging.info("Loaded song config from %s", cfg_path or "defaults")

    detector = SongDetector(enabled=True, detection_interval=args.sleep, auto_start=False)
    try:
        for attempt in range(1, args.loops + 1):
            logging.info("🎵 Attempt %d/%d", attempt, args.loops)
            result = detector.detect_song_blocking()
            health = detector.get_health_status()

            if args.json:
                print(json.dumps({"song": result, "health": health}, indent=2))
            else:
                title = result.get("title")
                artist = result.get("artist")
                ts = result.get("timestamp")
                print(
                    f"Result → title={title} artist={artist} ts={ts} provider={result.get('provider')}"
                )
                print(
                    "Health → status={status} failures={failure_streak} last_error={last_error}".format(
                        **health
                    )
                )

            if attempt < args.loops:
                time.sleep(max(1, args.sleep))
    finally:
        detector.stop()


if __name__ == "__main__":
    main()
