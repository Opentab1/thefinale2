#!/usr/bin/env python3
import asyncio
import json
import time
from pathlib import Path

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'


async def read_status():
    if not STATUS_FILE.exists():
        return {"last_check": None, "modules": {}}
    try:
        data = json.loads(STATUS_FILE.read_text())
        if not isinstance(data, dict):
            return {"last_check": None, "modules": {}}
        # Migrate legacy flat schema into modules map on-the-fly
        if "modules" not in data or not isinstance(data.get("modules"), dict):
            return {
                "last_check": data.get("last_check") or data.get("last_checked"),
                "modules": {}
            }
        return data
    except Exception:
        return {"last_check": None, "modules": {}}


async def run_detection():
    from . import hardware_detect  # type: ignore
    try:
        hardware_detect.main()
    except Exception:
        pass


async def main_loop():
    retry_interval = 60
    while True:
        await run_detection()
        await asyncio.sleep(retry_interval)


if __name__ == '__main__':
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
