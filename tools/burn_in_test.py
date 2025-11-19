#!/usr/bin/env python3
"""
Pulse burn-in orchestrator: runs audio and/or camera services for a fixed duration,
captures logs, and reports whether either service died early. Designed to run on
the Raspberry Pi after deployment to prove long-haul stability.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ServiceSpec:
    name: str
    command: List[str]
    log_path: Path
    process: Optional[subprocess.Popen] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    returncode: Optional[int] = None
    status: str = "pending"

    def start(self, env: Dict[str, str]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(self.log_path, "w", buffering=1)
        self.process = subprocess.Popen(
            self.command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=env,
        )
        self.started_at = time.time()
        self.status = "running"

    def poll(self) -> None:
        if not self.process:
            return
        ret = self.process.poll()
        if ret is not None and self.status == "running":
            self.returncode = ret
            self.ended_at = time.time()
            self.status = "ok" if ret == 0 else "failed"

    def stop(self, timeout: float = 5.0) -> None:
        if not self.process or self.process.poll() is not None:
            return
        try:
            self.process.send_signal(signal.SIGINT)
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.terminate()
        finally:
            self.poll()


def build_services(include_audio: bool, include_camera: bool) -> List[ServiceSpec]:
    services: List[ServiceSpec] = []
    if include_audio:
        services.append(
            ServiceSpec(
                name="audio",
                command=["python3", str(ROOT / "run_audio_service.py")],
                log_path=LOG_DIR / "burn_in_audio.log",
            )
        )
    if include_camera:
        services.append(
            ServiceSpec(
                name="camera",
                command=["python3", str(ROOT / "run_camera_service.py")],
                log_path=LOG_DIR / "burn_in_camera.log",
            )
        )
    return services


def main():
    parser = argparse.ArgumentParser(description="Pulse burn-in test runner")
    parser.add_argument(
        "--duration",
        type=int,
        default=900,
        help="Seconds to keep services running (default: 900 = 15 minutes)",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Include audio service in burn-in (default: enabled unless --camera-only)",
    )
    parser.add_argument(
        "--camera",
        action="store_true",
        help="Include camera service in burn-in (default: enabled unless --audio-only)",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Run only the audio service burn-in",
    )
    parser.add_argument(
        "--camera-only",
        action="store_true",
        help="Run only the camera service burn-in",
    )
    args = parser.parse_args()

    include_audio = True
    include_camera = True
    if args.audio_only:
        include_camera = False
    if args.camera_only:
        include_audio = False
    if args.audio or args.camera:
        # Explicit flags override defaults
        include_audio = args.audio or args.audio_only or not args.camera
        include_camera = args.camera or args.camera_only or not args.audio

    services = build_services(include_audio, include_camera)
    if not services:
        parser.error("No services selected. Use --audio, --camera, --audio-only or --camera-only.")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONPATH", str(ROOT))

    print("=" * 80)
    print("PULSE BURN-IN TEST")
    print("=" * 80)
    print(f"Workspace: {ROOT}")
    print(f"Log directory: {LOG_DIR}")
    print(f"Duration: {args.duration}s")
    print(f"Services: {', '.join(s.name for s in services)}")
    print("=" * 80)

    for svc in services:
        print(f"→ Starting {svc.name} service (log: {svc.log_path})")
        svc.start(env)

    deadline = time.monotonic() + max(1, args.duration)
    try:
        while time.monotonic() < deadline:
            all_done = True
            for svc in services:
                svc.poll()
                if svc.status == "running":
                    all_done = False
            if all_done:
                break
            time.sleep(1)
    finally:
        for svc in services:
            svc.stop()

    print("\nSUMMARY")
    print("-" * 80)
    exit_code = 0
    for svc in services:
        runtime = 0
        if svc.started_at:
            end = svc.ended_at or time.time()
            runtime = end - svc.started_at
        status = svc.status
        if status == "running":
            status = "stopped"
        if status not in ("ok", "stopped"):
            exit_code = 1
        print(
            f"{svc.name.upper():>6}: status={status:<7} runtime={runtime:6.1f}s "
            f"log={svc.log_path} "
            f"returncode={svc.returncode}"
        )
    print("-" * 80)
    if exit_code == 0:
        print("✅ Burn-in completed without early failures.")
    else:
        print("⚠️ Burn-in detected failures. Inspect logs for details.")
    sys.exit(exit_code)


if __name__ == "__main__":
    import sys

    main()
