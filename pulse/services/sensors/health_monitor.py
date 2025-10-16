#!/usr/bin/env python3
import asyncio
import json
import time
from pathlib import Path

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'


async def read_status():
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text())
    except Exception:
        return {}


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
