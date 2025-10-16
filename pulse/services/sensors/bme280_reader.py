#!/usr/bin/env python3
import asyncio
import time
from pathlib import Path
import json

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'

async def has_sensor() -> bool:
    try:
        status = json.loads(STATUS_FILE.read_text())
        return bool(status.get('bme280'))
    except Exception:
        return False

async def read_loop():
    while True:
        if not await has_sensor():
            await asyncio.sleep(10)
            continue
        # Placeholder: real implementation would read from I2C
        # Emit fake telemetry or skip if not available
        # Keep running to avoid crash
        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(read_loop())
    except KeyboardInterrupt:
        pass
