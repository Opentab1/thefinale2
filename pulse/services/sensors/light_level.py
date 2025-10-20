#!/usr/bin/env python3
import asyncio
import os
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

DATA_DIR = Path('/opt/pulse/data/sensors')
CAMERA_DIR = Path('/opt/pulse/data/camera')
SNAPSHOT_FILE = CAMERA_DIR / 'latest_frame.jpg'
LIGHT_LEVEL_FILE = DATA_DIR / 'light_level.txt'

def _calc_lux_from_image(img: np.ndarray) -> float:
    try:
        if img is None or img.size == 0:
            return 0.0
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        mean_brightness = float(np.mean(gray))
        lux = (mean_brightness / 255.0) * 1000.0
        return round(lux, 1)
    except Exception:
        return 0.0

async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CAMERA_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            img = None
            if SNAPSHOT_FILE.exists():
                img = cv2.imread(str(SNAPSHOT_FILE))
            lux = _calc_lux_from_image(img)
            # If snapshot not available, synthesize daytime/nighttime approximate lux
            if lux == 0.0 and (not SNAPSHOT_FILE.exists()):
                hour = datetime.now().hour
                if 7 <= hour <= 19:
                    lux = 400.0
                else:
                    lux = 50.0
            LIGHT_LEVEL_FILE.write_text(f"{lux:.1f}")
            print(f"[Light] {lux:.1f} lux")
        except Exception as e:
            try:
                LIGHT_LEVEL_FILE.write_text("0.0")
            except Exception:
                pass
        await asyncio.sleep(int(os.getenv('LIGHT_UPDATE_INTERVAL_SEC', '10')))

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
