#!/usr/bin/env python3
import json
import os
import subprocess
from pathlib import Path

STATUS_FILE = Path(__file__).resolve().parents[2] / 'config' / 'hardware_status.json'


def has_camera() -> bool:
    try:
        return Path('/dev/video0').exists()
    except Exception:
        return False


def has_mic() -> bool:
    try:
        out = subprocess.run(['arecord', '-l'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=3)
        return 'card' in out.stdout.lower()
    except Exception:
        return False


def has_bme280() -> bool:
    # Heuristic: i2cdetect presence at 0x76/0x77
    try:
        for bus in ('0', '1'):
            res = subprocess.run(['i2cdetect', '-y', bus], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3)
            if '76' in res.stdout or '77' in res.stdout:
                return True
    except Exception:
        pass
    return False


def has_ai_hat() -> bool:
    # Placeholder: detect Pi 5 AI Hat via lsmod or device tree markers
    try:
        dt = Path('/proc/device-tree/model').read_text(errors='ignore')
        if 'Raspberry Pi' in dt:
            # Assume absent unless specific accel is present
            mods = subprocess.run(['lsmod'], stdout=subprocess.PIPE, text=True, timeout=3).stdout.lower()
            return 'ipu6' in mods or 'v4l2' in mods  # loose heuristic
    except Exception:
        pass
    return False


def main():
    # Write new unified schema with modules map; keep last_checked for backward compat
    status = {
        'last_check': None,
        'last_checked': None,
        'modules': {
            'camera': {'present': has_camera()},
            'mic': {'present': has_mic()},
            'bme280': {'present': has_bme280()},
            'light_sensor': {'present': False},  # optional
            'ai_hat': {'present': has_ai_hat()},
        }
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)
    print(json.dumps(status))


if __name__ == '__main__':
    main()
