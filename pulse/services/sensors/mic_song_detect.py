#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'

async def has_mic() -> bool:
    try:
        status = json.loads(STATUS_FILE.read_text())
        return bool(status.get('mic'))
    except Exception:
        return False

async def main():
    while True:
        if not await has_mic():
            await asyncio.sleep(10)
            continue
        # Placeholder: listen audio for dB and song detection
        await asyncio.sleep(2)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
