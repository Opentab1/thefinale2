#!/usr/bin/env python3
"""
simple_song_detector.py - Simple, reliable song detection using ShazamIO

Based on proven party_box approach:
- Fresh event loop created for EACH Shazam API call
- Event loop closed immediately after use
- No long-lived event loops (prevents staleness)
- Simple daemon thread (no complex watchdogs)

This approach is proven to run indefinitely on Raspberry Pi without failures.
"""

import time
import logging
import threading
import asyncio
import wave
import tempfile
import os
import json
import base64
import copy
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import requests

# Try to import sound-related libraries
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice library not available. Install with 'pip install sounddevice'")

# Try to import ShazamIO
try:
    from shazamio import Shazam
    SHAZAMIO_AVAILABLE = True
except ImportError:
    SHAZAMIO_AVAILABLE = False
    logging.warning("ShazamIO library not available. Install with 'pip install shazamio'")

logger = logging.getLogger(__name__)

CONFIG_SEARCH_PATHS = [
    Path(os.environ.get("PULSE_SONG_CONFIG", "/opt/pulse/config/song_detection.json")),
    Path(__file__).resolve().parents[3] / "config" / "song_detection.json",
]

DEFAULT_SONG_CONFIG: Dict[str, Any] = {
    "provider": "shazamio",
    "detection_interval_seconds": 60,
    "recording": {
        "duration_seconds": 5,
        "sample_rate": 44100,
        "channels": 1,
    },
    "rapidapi": {
        "enabled": True,
        "api_key": "",
        "api_key_env": "PULSE_RAPIDAPI_KEY",
        "scheme": "https",
        "host": "shazam-core.p.rapidapi.com",
        "endpoint": "/v1/tracks/identify",
        "method": "POST",
        "send_as": "base64_json",  # or multipart_form
        "audio_field": "audio",
        "payload_template": {},
        "form_fields": {},
        "query": {},
        "headers": {},
        "title_path": ["track", "title"],
        "artist_path": ["track", "subtitle"],
        "timeout_seconds": 25,
    },
    "backoff": {
        "max_failure_streak": 5,
        "cooldown_seconds": 180,
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
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


def load_song_config() -> (Dict[str, Any], Optional[Path]):
    """Load song detection configuration from known locations."""
    config = copy.deepcopy(DEFAULT_SONG_CONFIG)
    selected_path: Optional[Path] = None
    for path in CONFIG_SEARCH_PATHS:
        if path and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as cfg_file:
                    data = json.load(cfg_file)
                    config = _deep_merge(config, data)
                    selected_path = path
                    break
            except Exception as exc:
                logger.warning(f"Unable to read song detection config at {path}: {exc}")
    return config, selected_path


class SongRecognitionError(Exception):
    """Raised when a recognition backend fails."""


class SongRecognizer:
    """Base interface for recognition providers."""

    name = "base"

    def recognize(self, audio_file: str) -> Optional[Dict[str, Any]]:
        raise SongRecognitionError("No song recognizer configured")


class ShazamIORecognizer(SongRecognizer):
    name = "shazamio"

    def __init__(self, timeout: float = 15.0):
        if not SHAZAMIO_AVAILABLE:
            raise SongRecognitionError("ShazamIO library not available")
        self.timeout = timeout

    def recognize(self, audio_file: str) -> Optional[Dict[str, Any]]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            shazam = Shazam()
            coro = shazam.recognize(audio_file)
            result = loop.run_until_complete(asyncio.wait_for(coro, timeout=self.timeout))
            if not result or "track" not in result:
                return None
            track = result.get("track") or {}
            return {
                "title": track.get("title"),
                "artist": track.get("subtitle"),
                "raw": track,
            }
        except asyncio.TimeoutError as exc:
            raise SongRecognitionError("ShazamIO recognition timed out") from exc
        except Exception as exc:
            raise SongRecognitionError(f"ShazamIO error: {exc}") from exc
        finally:
            try:
                loop.close()
            except Exception:
                pass


class RapidAPIRecognizer(SongRecognizer):
    name = "rapidapi"

    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", True)
        if not self.enabled:
            raise SongRecognitionError("RapidAPI recognizer disabled by config")

        api_key = config.get("api_key")
        env_key = config.get("api_key_env")
        if not api_key and env_key:
            api_key = os.environ.get(env_key, "").strip()
        if not api_key:
            raise SongRecognitionError("RapidAPI key missing. Set in config or env variable.")

        self.api_key = api_key
        self.scheme = config.get("scheme", "https")
        self.host = config.get("host") or "shazam-core.p.rapidapi.com"
        self.endpoint = config.get("endpoint", "/v1/tracks/identify")
        self.method = (config.get("method") or "POST").upper()
        self.send_mode = config.get("send_as", "base64_json")
        self.audio_field = config.get("audio_field", "audio")
        self.payload_template = copy.deepcopy(config.get("payload_template") or {})
        self.form_fields = copy.deepcopy(config.get("form_fields") or {})
        self.query_params = copy.deepcopy(config.get("query") or {})
        self.extra_headers = copy.deepcopy(config.get("headers") or {})
        self.title_path = config.get("title_path") or ["track", "title"]
        self.artist_path = config.get("artist_path") or ["track", "subtitle"]
        self.timeout = float(config.get("timeout_seconds", 25))

    def recognize(self, audio_file: str) -> Optional[Dict[str, Any]]:
        with open(audio_file, "rb") as audio:
            audio_bytes = audio.read()
        if not audio_bytes:
            raise SongRecognitionError("Recorded audio file is empty")

        url = f"{self.scheme}://{self.host}{self.endpoint}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.host,
        }
        headers.update(self.extra_headers or {})

        response = self._send_request(url, headers, audio_bytes)

        if response.status_code >= 400:
            snippet = response.text[:200]
            raise SongRecognitionError(f"RapidAPI error {response.status_code}: {snippet}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise SongRecognitionError("RapidAPI response was not valid JSON") from exc

        title = self._extract_field(payload, self.title_path)
        artist = self._extract_field(payload, self.artist_path)
        if not title and not artist:
            return None

        return {
            "title": title or "Unknown",
            "artist": artist or "Unknown",
            "raw": payload,
        }

    def _send_request(self, url: str, headers: Dict[str, str], audio_bytes: bytes):
        if self.send_mode == "base64_json":
            body = copy.deepcopy(self.payload_template) or {}
            body[self.audio_field] = base64.b64encode(audio_bytes).decode("ascii")
            headers.setdefault("Content-Type", "application/json")
            return requests.request(
                self.method,
                url,
                headers=headers,
                json=body,
                params=self.query_params,
                timeout=self.timeout,
            )
        if self.send_mode == "multipart_form":
            files = {
                self.audio_field: ("clip.wav", audio_bytes, "audio/wav"),
            }
            data = copy.deepcopy(self.form_fields) or {}
            return requests.request(
                self.method,
                url,
                headers=headers,
                data=data,
                files=files,
                params=self.query_params,
                timeout=self.timeout,
            )
        raise SongRecognitionError(f"Unsupported RapidAPI send mode: {self.send_mode}")

    @staticmethod
    def _extract_field(payload: Any, path: Sequence[Any]) -> Optional[Any]:
        current = payload
        for key in path or []:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    index = int(key)
                except (ValueError, TypeError):
                    return None
                if index < 0 or index >= len(current):
                    return None
                current = current[index]
            else:
                return None
            if current is None:
                return None
        return current


class SongDetector:
    """Song detector that can use ShazamIO or RapidAPI."""

    def __init__(
        self,
        enabled: bool = True,
        detection_interval: Optional[int] = 60,
        auto_start: bool = True,
    ):
        self.lock = threading.Lock()
        self.config, self.config_path = load_song_config()

        recording_cfg = self.config.get("recording", {})
        self.sample_rate = int(recording_cfg.get("sample_rate", 44100))
        self.channels = int(recording_cfg.get("channels", 1))
        self.duration = int(recording_cfg.get("duration_seconds", 5))

        if detection_interval is None:
            detection_interval = int(self.config.get("detection_interval_seconds", 60))
        self.detection_interval = detection_interval

        backoff_cfg = self.config.get("backoff", {})
        self.max_failure_streak = int(backoff_cfg.get("max_failure_streak", 5))
        self.cooldown_seconds = int(backoff_cfg.get("cooldown_seconds", 180))
        self.cooldown_until = 0.0
        self._cooldown_notified = False

        self.failure_streak = 0
        self.last_error: Optional[str] = None

        provider = (self.config.get("provider") or "shazamio").lower()
        self.recognizer = self._build_recognizer(provider)
        self.provider = self.recognizer.name if self.recognizer else provider

        self.enabled = enabled and SOUNDDEVICE_AVAILABLE and self.recognizer is not None
        if not SOUNDDEVICE_AVAILABLE:
            logger.warning("⚠️ sounddevice not available. Song detection disabled.")
        if not self.recognizer:
            logger.warning("⚠️ Song recognizer unavailable (provider=%s).", provider)

        self.latest_song = {
            "title": "Unknown",
            "artist": "Unknown",
            "timestamp": None,
            "last_attempt_time": None,
            "provider": self.provider,
        }
        self.last_raw_result: Optional[Dict[str, Any]] = None

        self.health_state = {
            "status": "initializing" if self.enabled else "disabled",
            "provider": self.provider,
            "failure_streak": 0,
            "cooldown_until": None,
            "last_error": None,
            "last_success": None,
            "last_attempt": None,
            "config_path": str(self.config_path) if self.config_path else None,
        }

        self.auto_start = auto_start
        self.detection_thread: Optional[threading.Thread] = None
        self.detection_active = False
        self.last_detection_time = 0.0

        if self.enabled and self.auto_start:
            logger.info(
                "✅ Song detection enabled via %s (interval=%ss, sample_rate=%s)",
                self.provider,
                self.detection_interval,
                self.sample_rate,
            )
            self.start_detection_thread()
        elif not self.enabled:
            logger.warning("Song detection disabled (provider=%s)", self.provider)

    def _build_recognizer(self, provider: str) -> Optional[SongRecognizer]:
        try:
            if provider == "rapidapi":
                return RapidAPIRecognizer(self.config.get("rapidapi", {}))
            return ShazamIORecognizer()
        except SongRecognitionError as exc:
            logger.error("Recognizer '%s' unavailable: %s", provider, exc)
            # Attempt fallback
            if provider != "rapidapi":
                rapid_cfg = self.config.get("rapidapi", {})
                try:
                    return RapidAPIRecognizer(rapid_cfg)
                except SongRecognitionError as rapid_exc:
                    logger.error("RapidAPI fallback unavailable: %s", rapid_exc)
            return None

    def start_detection_thread(self):
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_active = True
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                name="SongDetector",
                daemon=True,
            )
            self.detection_thread.start()
            logger.info("✅ Song detection thread started")

    def _update_last_attempt(self, attempt_time: float):
        with self.lock:
            self.latest_song["last_attempt_time"] = attempt_time
            self.health_state["last_attempt"] = attempt_time

    def _safe_remove_file(self, path: Optional[str]):
        if not path:
            return
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as exc:
            logger.debug(f"Unable to remove temp file {path}: {exc}")

    def _record_audio_clip(self) -> Optional[str]:
        temp_filename: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name

            logger.debug("Recording %ds audio clip for song detection...", self.duration)
            recording = sd.rec(
                int(self.duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
            )
            sd.wait()

            with wave.open(temp_filename, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(recording.tobytes())

            return temp_filename

        except Exception as exc:
            logger.error(f"Error recording audio: {exc}")
            self._safe_remove_file(temp_filename)
            return None

    def _in_cooldown(self) -> bool:
        if not self.cooldown_until:
            return False
        now = time.time()
        if now >= self.cooldown_until:
            self.cooldown_until = 0.0
            self.health_state["cooldown_until"] = None
            self.health_state["status"] = "recovering"
            self._cooldown_notified = False
            return False
        if not self._cooldown_notified:
            remaining = int(self.cooldown_until - now)
            logger.warning("Song detector cooling down for %ss", remaining)
            self._cooldown_notified = True
        return True

    def _detection_loop(self):
        logger.info("🎵 Song detection loop started")

        while self.detection_active:
            try:
                if self._in_cooldown():
                    time.sleep(2)
                    continue

                current_time = time.time()
                if current_time - self.last_detection_time >= self.detection_interval:
                    logger.debug("🎵 Starting song recognition...")
                    self.detect_song()
                    self.last_detection_time = current_time

                time.sleep(5)

            except Exception as exc:
                logger.error(f"Error in song detection loop: {exc}")
                time.sleep(10)

    def detect_song(self):
        if not self.enabled or not self.recognizer:
            return

        attempt_time = time.time()
        self._update_last_attempt(attempt_time)
        temp_filename = self._record_audio_clip()
        if not temp_filename:
            self._record_failure("Recording failed")
            return

        processing_thread = threading.Thread(
            target=self._process_audio_file,
            args=(temp_filename, attempt_time),
            daemon=True,
        )
        processing_thread.start()

    def detect_song_blocking(self) -> Dict[str, Any]:
        """Record and detect synchronously (for CLI/testing)."""
        if not self.recognizer:
            raise SongRecognitionError("Song recognizer not configured")
        attempt_time = time.time()
        self._update_last_attempt(attempt_time)
        temp_filename = self._record_audio_clip()
        if not temp_filename:
            self._record_failure("Recording failed")
            return self.get_latest_song()
        self._process_audio_file(temp_filename, attempt_time)
        return self.get_latest_song()

    def _process_audio_file(self, audio_file: str, attempt_time: float):
        try:
            if not self.recognizer:
                raise SongRecognitionError("Song recognizer not configured")

            match = self.recognizer.recognize(audio_file)
            if match:
                self._record_success(match, attempt_time)
                logger.info("🎵 Song detected: %s by %s", match.get("title"), match.get("artist"))
            else:
                self._record_no_match(attempt_time)
                logger.debug("🎵 No song detected in this sample")

        except SongRecognitionError as exc:
            logger.warning(f"Song recognition error: {exc}")
            self._record_failure(str(exc))
        except Exception as exc:
            logger.error(f"Unexpected error processing audio: {exc}", exc_info=True)
            self._record_failure(str(exc))
        finally:
            self._safe_remove_file(audio_file)

    def _record_success(self, match: Dict[str, Any], attempt_time: float):
        with self.lock:
            ts = time.time()
            self.latest_song.update(
                {
                    "title": match.get("title") or "Unknown",
                    "artist": match.get("artist") or "Unknown",
                    "timestamp": ts,
                    "last_attempt_time": attempt_time,
                    "provider": self.provider,
                }
            )
            self.last_raw_result = match.get("raw")
            self.failure_streak = 0
            self.last_error = None
            self.cooldown_until = 0.0
            self.health_state.update(
                {
                    "status": "ok",
                    "failure_streak": 0,
                    "last_error": None,
                    "last_success": ts,
                    "last_attempt": attempt_time,
                    "cooldown_until": None,
                }
            )
            self._cooldown_notified = False

    def _record_no_match(self, attempt_time: float):
        with self.lock:
            self.latest_song["last_attempt_time"] = attempt_time
            self.failure_streak = 0
            self.cooldown_until = 0.0
            self.health_state.update(
                {
                    "status": "listening",
                    "failure_streak": 0,
                    "last_attempt": attempt_time,
                    "cooldown_until": None,
                }
            )
            self._cooldown_notified = False

    def _record_failure(self, message: str):
        self.failure_streak += 1
        self.last_error = message
        cooldown_hit = False
        if self.failure_streak >= self.max_failure_streak:
            self.cooldown_until = time.time() + self.cooldown_seconds
            cooldown_hit = True
            self._cooldown_notified = False
        with self.lock:
            self.health_state.update(
                {
                    "status": "cooldown" if cooldown_hit else "error",
                    "failure_streak": self.failure_streak,
                    "last_error": message,
                    "cooldown_until": self.cooldown_until if cooldown_hit else self.health_state.get("cooldown_until"),
                }
            )

    def get_latest_song(self) -> Dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self.latest_song)

    def get_health_status(self) -> Dict[str, Any]:
        with self.lock:
            status = copy.deepcopy(self.health_state)
            status["provider"] = self.provider
            status["last_error"] = self.last_error
            return status

    def get_current_song(self) -> Dict[str, Any]:
        return self.get_latest_song()

    def stop(self):
        logger.info("Stopping song detector...")
        self.detection_active = False

        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=3.0)
            if self.detection_thread.is_alive():
                logger.warning("Song detection thread did not stop gracefully")
            else:
                logger.info("✅ Song detection thread stopped")


# Module test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting song detector test")
    
    # Create detector
    detector = SongDetector(
        enabled=True,
        detection_interval=60
    )
    
    try:
        # Run for a few minutes and print detected songs
        logger.info("Running test for 3 minutes...")
        logger.info("Play some music to test detection...")
        
        for i in range(18):  # 3 minutes / 10 seconds
            time.sleep(10)
            song = detector.get_latest_song()
            if song['title'] != 'Unknown':
                logger.info(f"🎵 Latest song: {song['title']} by {song['artist']}")
            else:
                logger.info("🎵 No song detected yet")
    
    except KeyboardInterrupt:
        logger.info("Test interrupted")
    finally:
        detector.stop()
        logger.info("Test complete")
