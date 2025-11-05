"""
Pulse 1.0 - Microphone Audio Analysis
Song detection and decibel level monitoring
Integrated with party_box song detection for production-ready music recognition
"""
from __future__ import annotations


import asyncio
import concurrent.futures
import logging
from threading import Thread, Event, Lock
from datetime import datetime
import os
import time

# NumPy is required
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

# Optional backends
try:  # PyAudio is preferred for broad device support
    import pyaudio  # type: ignore
    PYAUDIO_AVAILABLE = True
except Exception:  # noqa: BLE001 - we want to catch any import failure
    pyaudio = None  # type: ignore
    PYAUDIO_AVAILABLE = False

try:  # sounddevice is a portable fallback
    import sounddevice as sd  # type: ignore
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    sd = None  # type: ignore
    SOUNDDEVICE_AVAILABLE = False

try:
    # Prefer local party_box-style song detector if available in our workspace
    from .song_detector import SongDetector  # type: ignore  # re-exported/compatible API
except Exception:
    # Fallback: use internal Shazam-based detection baked in this module
    SongDetector = None  # type: ignore

logger = logging.getLogger(__name__)

class AudioMonitor:
    class StreamInitError(Exception):
        """Raised when the audio input stream cannot be opened."""

    class StreamRuntimeError(Exception):
        """Raised when an already opened audio stream stops producing data."""

    def __init__(self, device_index: int = None, sample_rate: int = 44100, chunk_size: int = 2048):
        # Check for NumPy first
        if not NUMPY_AVAILABLE:
            logger.error("NumPy is not installed - audio monitor cannot function")
            logger.error("Install with: pip install numpy")
            raise ImportError("NumPy is required for AudioMonitor")
        
        # Check for at least one audio backend
        if not PYAUDIO_AVAILABLE and not SOUNDDEVICE_AVAILABLE:
            logger.error("No audio backend available (pyaudio or sounddevice)")
            logger.error("Install with: pip install pyaudio sounddevice")
            raise ImportError("PyAudio or sounddevice is required for AudioMonitor")
        
        # Allow overriding device/backend from environment for quick field fixes
        env_dev = os.getenv('PULSE_MIC_DEVICE_INDEX')
        try:
            device_index = int(env_dev) if env_dev is not None else device_index
        except Exception:
            pass
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.running = False
        self.stop_event = Event()
        self._song_detection_lock = Lock()

        self.current_db = 0.0
        self.peak_db = 0.0
        self.current_song = self._default_song_payload()
        
        # Watchdog tracking
        self._monitoring_thread = None
        self._last_activity = 0.0
        
        # CRITICAL FIX: Track complete system stalls (25min issue)
        self._system_completely_stalled_at = 0.0

        # Song detection configuration from environment (default: 10s)
        try:
            configured_interval = float(os.getenv('SONG_DETECT_INTERVAL_SEC', '10'))
        except (TypeError, ValueError):
            configured_interval = 10.0
        self._song_detect_interval = max(5.0, configured_interval)
        logger.info(f"Song detection interval set to {self._song_detect_interval:.1f}s")
        self._db_interval = float(os.getenv('DB_UPDATE_INTERVAL_SEC', '2.0'))
        self._last_db_ts = 0.0
        self._last_song_detect_ts = 0.0
        self._song_detection_stats = {
            "interval_sec": self._song_detect_interval,
            "last_attempt_started_at": None,
            "last_attempt_duration_sec": None,
            "last_success_at": None,
            "last_error": None,
            "active": False,
        }

        self._health_thread = None
        # CRITICAL FIX: Check health more frequently (every 3 seconds for faster failure detection)
        self._health_check_interval = 3.0  # Fixed: Always 3 seconds for rapid detection
        self._last_db_restart_ts = 0.0

        # Dedicated async event loop for song recognition to keep Shazam stable
        self._detection_loop = None
        self._detection_loop_thread = None
        self._detection_loop_ready_event = None
        self._detection_loop_lock = Lock()
        
        # CRITICAL FIX: Event loop health tracking to detect stuck loops FAST
        self._loop_last_heartbeat = 0.0
        self._loop_heartbeat_interval = 30.0  # Heartbeat every 30s (faster detection)
        self._loop_heartbeat_timeout = 90.0  # Restart loop if no heartbeat for 90s (faster recovery)

        # Stream state tracking for watchdog-based recovery
        self._monitoring_backend = None
        self._stream_restart_count = 0
        self._max_consecutive_read_errors = 3
        # CRITICAL FIX: Reduce watchdog threshold to catch failures VERY fast
        self._watchdog_restart_threshold = 15.0  # Fixed: Always 15 seconds for faster detection
        self._stream_restart_request = Event()
        
        # CRITICAL FIX: Track song detection thread to force-kill if stuck (reduced timeout)
        self._song_detection_thread = None
        self._song_detection_started_at = 0.0
        self._song_detection_max_duration = 20.0  # Kill if running longer than 20s (was 30s)
        
        # Rolling audio buffer for song detection (5 seconds at 44100 Hz)
        # This allows song detection without opening a separate audio stream
        self._audio_buffer_size = int(5 * self.sample_rate)  # 5 seconds
        self._audio_buffer = np.zeros(self._audio_buffer_size, dtype=np.int16)
        self._buffer_index = 0
        
        # Reusable Shazam instance to prevent resource leaks
        # Creating a new Shazam() for each detection causes unclosed ClientSession leaks
        self._shazam_instance = None
        self._shazam_lock = Lock()
        self._shazam_created_at = 0.0  # Track when instance was created
        self._shazam_refresh_interval = 600.0  # Refresh every 10 minutes to prevent stale sessions (was 1hr)
        self._shazam_consecutive_failures = 0  # Track failures for circuit breaker
        self._shazam_max_failures = 3  # Circuit breaker threshold

        # Initialize song detector if available
        if SongDetector is not None:
            try:
                # Pass enabled=False so it doesn't start its own recording thread
                # We'll call detect_song_from_buffer() manually with our buffered audio
                self.song_detector = SongDetector(
                    enabled=False,  # Don't start background recording
                    detection_interval=int(self._song_detect_interval)
                )

                if not self._ensure_detection_loop():
                    logger.warning("Song detection event loop failed to initialize; disabling detection")
                    self.song_detector = None
                else:
                    logger.info("✅ Song detector initialized (using shared audio buffer)")
                    # Check if ShazamIO is actually available
                    try:
                        from shazamio import Shazam
                        logger.info("✅ ShazamIO library available - song detection will work")
                    except ImportError:
                        logger.warning("⚠️ ShazamIO not available - song detection will not work")
                        logger.warning("   Install with: pip install shazamio aiohttp")
            except Exception as e:
                logger.warning(f"Failed to initialize song detector: {e}")
                logger.warning(f"   Error details: {type(e).__name__}: {str(e)}")
                import traceback
                logger.debug(traceback.format_exc())
                self.song_detector = None
        else:
            self.song_detector = None
            logger.warning("⚠️ Song detector disabled (SongDetector class not available)")
            logger.warning("   Check if song_detector.py is properly imported")

        # Audio interfaces (optional)
        self.pyaudio_instance = None
        if PYAUDIO_AVAILABLE:
            try:
                self.pyaudio_instance = pyaudio.PyAudio()  # type: ignore[arg-type]
                logger.info("PyAudio initialized successfully")
            except Exception as e:
                logger.warning(f"PyAudio initialization failed: {e}")
                self.pyaudio_instance = None

        # Validate and pick an input device
        self._validate_device()
        logger.info(f"Audio monitor initialized (device: {self.device_index}, backend: {'PyAudio' if PYAUDIO_AVAILABLE and self.pyaudio_instance else 'sounddevice'})")
    
    def _default_song_payload(self, title: str = "Unknown", artist: str = "Unknown",
                              confidence: float = 0.0, detected_at=None) -> dict:
        """Return a canonical song payload with consistent metadata fields."""
        return {
            "title": title,
            "artist": artist,
            "confidence": confidence,
            "timestamp": detected_at,
            "source": "mic_shazam"
        }

    def _validate_device(self):
        """Validate and pick the best audio input device automatically.

        Preference order:
        1) ALSA default reported by sounddevice (if available)
        2) PyAudio device whose name contains any of: 'USB', 'Mic', 'PnP', 'Microphone'
        3) First available input-capable device from either backend
        """
        try:
            # 1) ALSA default via sounddevice
            if SOUNDDEVICE_AVAILABLE and self.device_index is None:
                try:
                    sd_default = sd.default.device  # type: ignore[attr-defined]
                    if isinstance(sd_default, (list, tuple)):
                        sd_in = sd_default[0]
                    else:
                        sd_in = sd_default
                    
                    # Handle _InputOutputPair objects (has input/output attributes)
                    if hasattr(sd_in, 'input'):
                        sd_in = sd_in.input
                    
                    # Convert to int safely
                    if sd_in is not None:
                        try:
                            device_idx = int(sd_in)
                            if device_idx >= 0:
                                self.device_index = device_idx
                                logger.info(f"Using sounddevice default input index: {self.device_index}")
                        except (TypeError, ValueError):
                            logger.debug(f"Could not convert sounddevice default to int: {sd_in}")
                except Exception as e:
                    logger.debug(f"sounddevice default selection failed: {e}")

            # 2) PyAudio search by name
            if PYAUDIO_AVAILABLE and self.pyaudio_instance is not None:
                preferred_substrings = ["USB", "Mic", "PnP", "Microphone"]
                chosen_by_name = None
                try:
                    device_count = self.pyaudio_instance.get_device_count()
                except Exception:
                    device_count = 0
                for i in range(device_count):
                    try:
                        di = self.pyaudio_instance.get_device_info_by_index(i)
                    except Exception:
                        continue
                    if di.get('maxInputChannels', 0) > 0:
                        name = str(di.get('name', ''))
                        if any(s.lower() in name.lower() for s in preferred_substrings):
                            chosen_by_name = i
                            logger.info(f"Preferring input device by name: {name} (index {i})")
                            break
                if self.device_index is None and chosen_by_name is not None:
                    self.device_index = chosen_by_name

                # 3) First available PyAudio input device
                if self.device_index is None:
                    for i in range(device_count):
                        try:
                            di = self.pyaudio_instance.get_device_info_by_index(i)
                        except Exception:
                            continue
                        if di.get('maxInputChannels', 0) > 0:
                            self.device_index = i
                            logger.info(f"Using first available input device: {di.get('name')} (index {i})")
                            break

            # As last resort, accept sounddevice index 0 if present
            if self.device_index is None and SOUNDDEVICE_AVAILABLE:
                try:
                    devs = sd.query_devices()  # type: ignore[attr-defined]
                    for idx, di in enumerate(devs):
                        if int(di.get('max_input_channels', 0)) > 0:
                            self.device_index = idx
                            logger.info(f"Using sounddevice input device: {di.get('name')} (index {idx})")
                            break
                except Exception as e:
                    logger.debug(f"sounddevice device scan failed: {e}")

            if self.device_index is None:
                logger.warning("No input audio device found; audio monitoring will be disabled")
        except Exception as e:
            logger.error(f"Audio device validation failed: {e}")
    
    def _ensure_detection_loop(self) -> bool:
        """Ensure the dedicated async loop for Shazam runs in a background thread."""
        if self._detection_loop is not None:
            thread = self._detection_loop_thread
            loop = self._detection_loop
            if thread is None or not thread.is_alive() or (loop is not None and loop.is_closed()):
                logger.warning("Song detection loop thread unhealthy - restarting")
                self._shutdown_detection_loop()
            else:
                return True

        with self._detection_loop_lock:
            if self._detection_loop is not None:
                return True

            try:
                loop = asyncio.new_event_loop()
                ready_event = Event()

                def _loop_runner():
                    asyncio.set_event_loop(loop)
                    ready_event.set()
                    logger.debug("Song detection event loop started")
                    
                    # CRITICAL FIX: Schedule periodic heartbeat to detect stuck loops
                    async def _heartbeat():
                        while True:
                            self._loop_last_heartbeat = time.time()
                            await asyncio.sleep(self._loop_heartbeat_interval)
                    
                    loop.create_task(_heartbeat())
                    loop.run_forever()

                thread = Thread(target=_loop_runner, name="AudioMonitorSongLoop", daemon=True)
                thread.start()

                if not ready_event.wait(timeout=5.0):
                    logger.error("Song detection loop failed to start within 5 seconds")
                    # Attempt graceful shutdown of the loop/thread if possible
                    try:
                        loop.call_soon_threadsafe(loop.stop)
                    except RuntimeError:
                        pass
                    thread.join(timeout=1.0)
                    try:
                        loop.close()
                    except Exception:
                        pass
                    return False

                self._detection_loop = loop
                self._detection_loop_thread = thread
                self._detection_loop_ready_event = ready_event
                return True
            except Exception as exc:
                logger.error(f"Failed to initialize song detection loop: {exc}")
                return False

    def _shutdown_detection_loop(self):
        """Stop and clean up the dedicated song detection loop."""
        with self._detection_loop_lock:
            loop = self._detection_loop
            thread = self._detection_loop_thread
            self._detection_loop = None
            self._detection_loop_thread = None
            self._detection_loop_ready_event = None

            if loop is None:
                return

            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass

            if thread:
                thread.join(timeout=2.0)

            try:
                loop.close()
            except Exception:
                logger.debug("Song detection loop close raised", exc_info=True)

    def _reset_shazam_instance(self, reason: str = "reset"):
        """Dispose of the cached Shazam instance so a fresh one can be created."""
        old_instance = None
        with self._shazam_lock:
            if self._shazam_instance is None:
                return
            old_instance = self._shazam_instance
            self._shazam_instance = None
            self._shazam_created_at = 0.0

        client = getattr(old_instance, "client", None)
        close_callable = getattr(client, "close", None) if client else None

        if close_callable is None:
            logger.debug("Shazam reset (%s): no client close() available", reason)
            logger.info("Shazam instance reset (%s)", reason)
            return

        def _run_close(coro):
            if asyncio.iscoroutine(coro):
                loop = self._detection_loop
                if loop is not None and not loop.is_closed():
                    future = None
                    try:
                        future = asyncio.run_coroutine_threadsafe(coro, loop)
                        future.result(timeout=5.0)
                    except concurrent.futures.TimeoutError:
                        if future:
                            future.cancel()
                        logger.debug("Timeout closing Shazam client during %s", reason)
                    except Exception as exc:
                        logger.debug(
                            "Error closing Shazam client during %s: %s",
                            reason,
                            exc,
                            exc_info=True,
                        )
                    finally:
                        if future and not future.done():
                            future.cancel()
                            try:
                                future.result()
                            except Exception:
                                pass
                else:
                    new_loop = asyncio.new_event_loop()
                    try:
                        new_loop.run_until_complete(coro)
                    except Exception as exc:
                        logger.debug(
                            "Error closing Shazam client on new loop during %s: %s",
                            reason,
                            exc,
                            exc_info=True,
                        )
                    finally:
                        new_loop.close()

        try:
            close_result = close_callable()
        except Exception as exc:
            logger.debug(
                "Error invoking Shazam client close() during %s: %s",
                reason,
                exc,
                exc_info=True,
            )
        else:
            _run_close(close_result)

        logger.info("Shazam instance reset (%s)", reason)

    def _restart_detection_loop(self) -> bool:
        """Restart the song detection event loop."""
        self._reset_shazam_instance(reason="loop_restart")
        self._shutdown_detection_loop()
        if self._ensure_detection_loop():
            logger.info("Song detection event loop restarted")
            return True
        return False

    def _is_detection_loop_healthy(self, probe_timeout: float = 2.0) -> bool:
        """Determine if the detection loop thread is alive and responsive."""
        loop = self._detection_loop
        thread = self._detection_loop_thread

        if loop is None or thread is None:
            return False

        if loop.is_closed():
            return False

        if not thread.is_alive():
            return False

        future = None
        try:
            future = asyncio.run_coroutine_threadsafe(self._loop_ping(), loop)
            future.result(timeout=probe_timeout)
            return True
        except concurrent.futures.TimeoutError:
            if future is not None:
                future.cancel()
            logger.warning("Song detection event loop health probe timed out")
            return False
        except Exception as exc:
            logger.debug("Song detection event loop health probe failed: %s", exc, exc_info=True)
            return False

    async def _loop_ping(self):
        """Tiny coroutine used to ensure the detection loop is processing tasks."""
        return True

    def calculate_db(self, audio_data: np.ndarray) -> float:
        """Calculate decibel level from audio data"""
        try:
            # Convert to float and normalize
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # Calculate RMS
            rms = np.sqrt(np.mean(audio_float ** 2))
            
            # Convert to dB (with reference and floor)
            if rms > 0:
                db = 20 * np.log10(rms) + 94  # Calibrated to typical SPL
                db = max(0, min(120, db))  # Clamp between 0 and 120 dB
            else:
                db = 0
            
            return db
        except Exception as e:
            logger.error(f"Error calculating dB: {e}")
            return 0.0
    
    def analyze_audio_spectrum(self, audio_data: np.ndarray) -> dict:
        """Analyze audio frequency spectrum"""
        try:
            # Perform FFT
            fft = np.fft.rfft(audio_data)
            freqs = np.fft.rfftfreq(len(audio_data), 1.0 / self.sample_rate)
            magnitudes = np.abs(fft)
            
            # Calculate energy in different frequency bands
            bass = np.sum(magnitudes[(freqs >= 20) & (freqs < 250)])
            mid = np.sum(magnitudes[(freqs >= 250) & (freqs < 4000)])
            treble = np.sum(magnitudes[(freqs >= 4000) & (freqs < 20000)])
            
            total_energy = bass + mid + treble
            
            if total_energy > 0:
                return {
                    "bass_ratio": float(bass / total_energy),
                    "mid_ratio": float(mid / total_energy),
                    "treble_ratio": float(treble / total_energy),
                    "dominant_freq": float(freqs[np.argmax(magnitudes)])
                }
            else:
                return {
                    "bass_ratio": 0.0,
                    "mid_ratio": 0.0,
                    "treble_ratio": 0.0,
                    "dominant_freq": 0.0
                }
        except Exception as e:
            logger.error(f"Error analyzing spectrum: {e}")
            return {}
    
    def start_monitoring(self):
        """Start audio monitoring with automatic restart on crash"""
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self._last_db_restart_ts = 0.0
        
        # Start monitoring thread
        self._start_monitoring_thread()
        
        # Start watchdog thread to restart if monitoring crashes
        watchdog_thread = Thread(target=self._watchdog_loop, daemon=True)
        watchdog_thread.start()

        if self._health_thread is None or not self._health_thread.is_alive():
            self._health_thread = Thread(
                target=self._healthcheck_loop,
                name="AudioMonitorHealth",
                daemon=True,
            )
            self._health_thread.start()
            logger.debug("Audio monitor healthcheck thread launched")
        
        logger.info("Started audio monitoring with watchdog")
    
    def _start_monitoring_thread(self):
        """Start the monitoring thread"""
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        self._last_activity = time.time()
        self._stream_restart_count = 0
        self._stream_restart_request.clear()
    
    def _watchdog_loop(self):
        """Watchdog to restart monitoring if it crashes"""
        while self.running and not self.stop_event.is_set():
            try:
                # Check if monitoring thread is alive
                if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
                    logger.error("Audio monitoring thread died! Restarting...")
                    self._start_monitoring_thread()
                else:
                    now = time.time()
                    inactivity = now - self._last_activity
                    if inactivity > self._watchdog_restart_threshold and self._monitoring_backend is not None:
                        logger.warning(
                            "Audio monitoring stalled (no activity for %.1fs, backend=%s) - restarting stream",
                            inactivity,
                            self._monitoring_backend
                        )
                        self._stream_restart_request.set()
                        self._last_activity = now
                    elif inactivity > self._watchdog_restart_threshold:
                        self._last_activity = now  # Prevent repeated warnings when backend is inactive
                
                # CRITICAL FIX: Force-kill stuck song detection threads (NOW WITH CIRCUIT BREAKER)
                if self._song_detection_thread is not None and self._song_detection_thread.is_alive():
                    detection_duration = now - self._song_detection_started_at
                    if detection_duration > self._song_detection_max_duration:
                        logger.error(
                            "⚠️ CRITICAL: Song detection thread stuck for %.1fs - forcing restart!",
                            detection_duration
                        )
                        # Release the lock if held (this is safe because we're killing the thread)
                        if self._song_detection_lock.locked():
                            try:
                                self._song_detection_lock.release()
                            except RuntimeError:
                                pass  # Already unlocked
                        
                        # Increment failure counter for circuit breaker
                        self._shazam_consecutive_failures += 1
                        
                        # Reset Shazam instance to clear any stuck connections
                        self._reset_shazam_instance(reason="stuck_detection")
                        
                        # Restart the detection loop
                        if not self._restart_detection_loop():
                            logger.error("Failed to restart detection loop after stuck thread")
                        
                        self._song_detection_thread = None
                        self._song_detection_started_at = 0.0
                        self._song_detection_stats["active"] = False
                        self._song_detection_stats["last_error"] = f"force_killed_stuck_thread_failures_{self._shazam_consecutive_failures}"
                
                self.stop_event.wait(5)  # CRITICAL FIX: Check every 5 seconds (was 10)
            except Exception as e:
                logger.error(f"Error in watchdog: {e}")
                self.stop_event.wait(5)
    
    def _healthcheck_loop(self):
        """Periodic health checks for the audio monitor and song detection."""
        logger.debug("Audio monitor healthcheck thread started")
        while self.running and not self.stop_event.is_set():
            try:
                now = time.time()

                # CRITICAL FIX: Guard against stale dB readings with shorter threshold
                if self._last_db_ts and (now - self._last_db_ts) > self._watchdog_restart_threshold:
                    if self._monitoring_thread and self._monitoring_thread.is_alive():
                        if not self._stream_restart_request.is_set() and (now - self._last_db_restart_ts) > self._db_interval:
                            logger.warning(
                                "⚠️ dB readings stale for %.1fs - requesting audio stream restart",
                                now - self._last_db_ts,
                            )
                            self._stream_restart_request.set()
                            self._last_db_restart_ts = now
                            
                            # CRITICAL FIX: Track complete system stall (25min issue)
                            if self._system_completely_stalled_at == 0.0:
                                self._system_completely_stalled_at = now
                            elif (now - self._system_completely_stalled_at) > 60.0:
                                # System has been stalled for >60s despite restart attempts
                                logger.error(
                                    "🚨 CRITICAL: Audio system completely stalled for %.1fs - FORCING COMPLETE RESTART!",
                                    now - self._system_completely_stalled_at
                                )
                                # Stop and restart the entire monitoring system
                                try:
                                    self.stop_monitoring()
                                    time.sleep(2)
                                    self.start_monitoring()
                                    logger.info("✅ Complete audio system restart successful")
                                    self._system_completely_stalled_at = 0.0
                                except Exception as e:
                                    logger.error(f"❌ Failed to restart audio system: {e}")
                else:
                    # dB readings are fresh - reset stall tracker
                    self._system_completely_stalled_at = 0.0

                # CRITICAL FIX: Check event loop heartbeat to detect stuck loops (25min issue)
                if self._loop_last_heartbeat > 0:
                    heartbeat_age = now - self._loop_last_heartbeat
                    if heartbeat_age > self._loop_heartbeat_timeout:
                        logger.error(
                            "⚠️ CRITICAL: Event loop heartbeat stale (%.1fs) - loop is STUCK! Force restarting...",
                            heartbeat_age
                        )
                        # Force restart the entire detection loop
                        if not self._restart_detection_loop():
                            logger.error("Failed to restart stuck event loop - audio detection will fail")
                            self._song_detection_stats["last_error"] = "event_loop_stuck_restart_failed"
                        else:
                            logger.info("✅ Event loop restarted successfully after being stuck")
                            self._song_detection_stats["last_error"] = "recovered_from_stuck_loop"
                
                # Validate the async song detection loop when detection not already running
                if self.song_detector is not None and not self._song_detection_stats.get("active", False):
                    if not self._is_detection_loop_healthy():
                        logger.warning("Song detection loop unresponsive - attempting restart")
                        if not self._restart_detection_loop():
                            logger.error("Failed to restart song detection loop - disabling detection")
                            self._song_detection_stats["last_error"] = "loop_restart_failed"
                            self._song_detection_stats["active"] = False
                            self.song_detector = None

                self.stop_event.wait(self._health_check_interval)
            except Exception as exc:
                logger.error(f"Error in audio monitor healthcheck: {exc}", exc_info=True)
                self.stop_event.wait(self._health_check_interval)

        logger.debug("Audio monitor healthcheck thread stopped")
        self._health_thread = None

    def _monitoring_loop(self):
        """Main monitoring loop with automatic recovery for stream failures."""
        logger.debug("Audio monitoring loop thread started")
        while self.running and not self.stop_event.is_set():
            backend = None
            pa_stream = None
            sd_stream = None

            try:
                backend, pa_stream, sd_stream = self._open_audio_stream(self._stream_restart_count)
                self._monitoring_backend = backend
                self._stream_restart_count = 0
                logger.info("🔊 Audio monitoring active - dB readings will appear shortly")
                self._stream_restart_request.clear()
                self._run_audio_loop(backend, pa_stream, sd_stream)

                # If run_audio_loop returns normally, monitoring was stopped intentionally
                break

            except self.StreamInitError as init_error:
                self._stream_restart_count += 1
                wait_time = min(5.0, 1.0 + self._stream_restart_count)
                logger.error(
                    "Audio stream initialization failed (attempt %d): %s",
                    self._stream_restart_count,
                    init_error,
                )
                if self.stop_event.wait(wait_time):
                    break

            except self.StreamRuntimeError as runtime_error:
                self._stream_restart_count += 1
                wait_time = min(5.0, 1.5 * self._stream_restart_count)
                logger.warning(
                    "Audio stream runtime failure detected: %s -- restarting stream (attempt %d)",
                    runtime_error,
                    self._stream_restart_count,
                )
                if self.stop_event.wait(wait_time):
                    break
                continue

            except Exception as unexpected:
                self._stream_restart_count += 1
                wait_time = min(5.0, 1.5 * self._stream_restart_count)
                logger.error("Unexpected audio monitoring error: %s", unexpected, exc_info=True)
                if self.stop_event.wait(wait_time):
                    break

            finally:
                self._monitoring_backend = None
                self._close_audio_stream(pa_stream, sd_stream)

        logger.info("Audio monitoring stopped")

    def _open_audio_stream(self, restart_attempt: int):
        """Open the best available audio input stream."""
        errors = []

        if self.device_index is None:
            # Re-validate devices in case hardware becomes available later
            self._validate_device()

        if PYAUDIO_AVAILABLE and self.pyaudio_instance is not None:
            if self.device_index is not None:
                try:
                    pa_stream = self.pyaudio_instance.open(
                        format=pyaudio.paInt16,  # type: ignore[attr-defined]
                        channels=1,
                        rate=self.sample_rate,
                        input=True,
                        input_device_index=self.device_index,
                        frames_per_buffer=self.chunk_size
                    )
                    logger.info(f"✓ Audio stream opened successfully (PyAudio, device {self.device_index})")
                    return "pyaudio", pa_stream, None
                except Exception as e:
                    log_fn = logger.error if restart_attempt == 0 else logger.warning
                    log_fn(f"Failed to open PyAudio stream: {e}")
                    log_fn(f"  Error details: {type(e).__name__}: {str(e)}")
                    errors.append(f"PyAudio: {type(e).__name__}: {e}")
            else:
                message = "No audio input device found; cannot open PyAudio stream"
                logger.warning(message)
                errors.append(message)

        if SOUNDDEVICE_AVAILABLE:
            if self.device_index is not None:
                try:
                    sd_stream = sd.InputStream(  # type: ignore[call-arg]
                        samplerate=self.sample_rate,
                        dtype='int16',
                        channels=1,
                        blocksize=self.chunk_size,
                        device=self.device_index,
                    )
                    sd_stream.start()
                    logger.info(f"✓ Audio stream opened successfully (sounddevice, device {self.device_index})")
                    return "sounddevice", None, sd_stream
                except Exception as e:
                    log_fn = logger.error if restart_attempt == 0 else logger.warning
                    log_fn(f"Failed to open sounddevice stream: {e}")
                    log_fn(f"  Error details: {type(e).__name__}: {str(e)}")
                    errors.append(f"sounddevice: {type(e).__name__}: {e}")
            else:
                message = "No audio input device found; cannot open sounddevice stream"
                logger.warning(message)
                errors.append(message)

        if restart_attempt == 0:
            logger.error("=" * 80)
            logger.error("CRITICAL: Could not open any audio stream!")
            logger.error("Audio monitoring (dB readings) will NOT work.")
            logger.error("Check:")
            logger.error("  1. Audio device is connected: arecord -l")
            logger.error("  2. Device permissions: arecord -d 1 test.wav")
            logger.error("  3. Dependencies installed: pip install pyaudio sounddevice")
            logger.error("=" * 80)

        raise self.StreamInitError(" | ".join(errors) if errors else "No audio backend available")

    def _close_audio_stream(self, pa_stream, sd_stream):
        """Close any active audio streams."""
        try:
            if pa_stream:
                pa_stream.stop_stream()
                pa_stream.close()
        except Exception:
            pass

        try:
            if sd_stream:
                sd_stream.stop()
                sd_stream.close()
        except Exception:
            pass

    def _run_audio_loop(self, backend: str, pa_stream, sd_stream):
        """Consume audio data, compute dB, and trigger song detection."""
        consecutive_errors = 0
        # CRITICAL FIX: Track loop iterations to detect slow/hung reads
        loop_iteration_count = 0
        last_health_check = time.time()
        health_check_interval = 5.0  # Check stream health every 5 seconds

        while self.running and not self.stop_event.is_set():
            loop_iteration_count += 1
            try:
                audio_data = self._read_audio_chunk(backend, pa_stream, sd_stream)

                if audio_data is None or audio_data.size == 0:
                    consecutive_errors += 1
                    if consecutive_errors >= self._max_consecutive_read_errors:
                        raise self.StreamRuntimeError("Audio stream returned empty buffers repeatedly")
                    self.stop_event.wait(0.05)
                    continue

            except self.StreamRuntimeError as stream_error:
                consecutive_errors += 1
                logger.warning(
                    "Audio stream read failure (%d/%d): %s",
                    consecutive_errors,
                    self._max_consecutive_read_errors,
                    stream_error,
                )
                if consecutive_errors >= self._max_consecutive_read_errors:
                    raise
                if self.stop_event.wait(0.2):
                    break
                continue

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error in monitoring loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                if consecutive_errors >= self._max_consecutive_read_errors:
                    raise self.StreamRuntimeError(str(e)) from e
                if self.stop_event.wait(0.2):
                    break
                continue

            # Successful read resets error counter
            consecutive_errors = 0

            # Store audio in rolling buffer for song detection
            chunk_len = min(len(audio_data), self._audio_buffer_size)
            if self._buffer_index + chunk_len <= self._audio_buffer_size:
                self._audio_buffer[self._buffer_index:self._buffer_index + chunk_len] = audio_data[:chunk_len]
                self._buffer_index += chunk_len
            else:
                shift_amount = chunk_len
                self._audio_buffer = np.roll(self._audio_buffer, -shift_amount)
                self._audio_buffer[-shift_amount:] = audio_data[:chunk_len]
                self._buffer_index = self._audio_buffer_size

            # Calculate dB level (every 2 seconds)
            now_db = time.time()
            if (now_db - self._last_db_ts) >= self._db_interval:
                db = self.calculate_db(audio_data)
                self.current_db = db
                self.peak_db = max(self.peak_db, db)
                self._last_db_ts = now_db
                # CRITICAL FIX: Add loop count to help diagnose hangs
                logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB) [loop:{loop_iteration_count}]")

            # Trigger song detection on cadence using buffered audio
            now_song = time.time()
            if self.song_detector is not None and (now_song - self._last_song_detect_ts) >= self._song_detect_interval:
                if self._buffer_index >= self._audio_buffer_size:
                    try:
                        # CRITICAL FIX: Check if previous detection is stuck before starting new one
                        if self._song_detection_thread is not None and self._song_detection_thread.is_alive():
                            detection_age = now_song - self._song_detection_started_at
                            if detection_age > 25.0:  # Give it 25s before warning
                                logger.warning(
                                    f"⚠️ Previous song detection still running ({detection_age:.1f}s) - skipping"
                                )
                                self._last_song_detect_ts = now_song
                            else:
                                logger.debug(f"Song detection in progress ({detection_age:.1f}s) - skipping")
                        else:
                            if self._detect_song_from_buffer():
                                logger.info("🎵 Running song detection from audio buffer...")
                            self._last_song_detect_ts = now_song
                    except Exception as e:
                        logger.error(f"Failed to start song detection thread: {e}")
                        self._last_song_detect_ts = now_song
                else:
                    logger.debug(
                        "Audio buffer not ready for song detection (index: %s/%s)",
                        self._buffer_index,
                        self._audio_buffer_size,
                    )
                    self._last_song_detect_ts = now_song
            elif self.song_detector is None and int(now_song) % 60 == 0:
                logger.debug("Song detector not available - song detection disabled")

            # Update activity timestamp for watchdog
            self._last_activity = time.time()
            
            # CRITICAL FIX: Periodic stream health check to detect issues early
            if (self._last_activity - last_health_check) >= health_check_interval:
                last_health_check = self._last_activity
                # Log health metrics every 5 seconds
                if loop_iteration_count % 50 == 0:  # Don't spam logs
                    logger.debug(
                        f"Audio loop health: {loop_iteration_count} iterations, "
                        f"last_db={time.time() - self._last_db_ts:.1f}s ago, "
                        f"backend={backend}"
                    )

            # CRITICAL FIX: Check for restart request more frequently
            if self._stream_restart_request.is_set():
                logger.info("Audio stream restart requested by watchdog")
                self._stream_restart_request.clear()
                raise self.StreamRuntimeError("Watchdog requested audio stream restart")

            # CRITICAL FIX: Shorter threshold for detecting stalled dB readings
            if self._last_db_ts and (self._last_activity - self._last_db_ts) > self._watchdog_restart_threshold:
                raise self.StreamRuntimeError(
                    f"No decibel readings emitted for {(self._last_activity - self._last_db_ts):.1f}s"
                )

    def _read_audio_chunk(self, backend: str, pa_stream, sd_stream):
        """Read a chunk of audio data from the active backend."""
        try:
            if backend == "pyaudio" and pa_stream is not None:
                audio_bytes = pa_stream.read(self.chunk_size, exception_on_overflow=False)
                return np.frombuffer(audio_bytes, dtype=np.int16)

            if backend == "sounddevice" and sd_stream is not None:
                audio_data, _ = sd_stream.read(self.chunk_size)  # type: ignore[union-attr]
                if isinstance(audio_data, np.ndarray) and audio_data.ndim > 1:
                    audio_data = audio_data[:, 0]
                return audio_data.astype(np.int16, copy=False)

            raise self.StreamRuntimeError(f"No valid audio backend active (backend={backend})")

        except Exception as exc:  # noqa: BLE001 - we convert to StreamRuntimeError for handling upstream
            raise self.StreamRuntimeError(str(exc)) from exc
    
    def _detect_song_from_buffer(self):
        """Detect song using buffered audio data (runs in background thread)."""
        import tempfile
        import wave
        import threading

        if not self._song_detection_lock.acquire(blocking=False):
            logger.debug("Song detection skipped (previous attempt still running)")
            return False

        start_monotonic = time.time()
        started_at_iso = datetime.now().isoformat()
        self._song_detection_stats.update({
            "interval_sec": self._song_detect_interval,
            "last_attempt_started_at": started_at_iso,
            "active": True,
            "last_error": None,
        })

        def detect_async():
            temp_filename = None
            duration_sec = None
            future = None
            
            # CRITICAL FIX: Mark this thread as active for watchdog monitoring
            self._song_detection_thread = threading.current_thread()
            self._song_detection_started_at = time.time()
            
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name

                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(self._audio_buffer.tobytes())

                logger.debug(f"Saved audio buffer to {temp_filename}")

                if not self._ensure_detection_loop():
                    logger.error("Song detection loop unavailable; skipping detection")
                    self._song_detection_stats["last_error"] = "loop_unavailable"
                    return

                result = None
                # CRITICAL FIX: Reduce timeout from 20s to 12s and add circuit breaker
                try:
                    # Check circuit breaker before attempting detection
                    if self._shazam_consecutive_failures >= self._shazam_max_failures:
                        logger.warning(
                            f"⚠️ Circuit breaker OPEN: {self._shazam_consecutive_failures} consecutive failures - "
                            f"resetting Shazam and clearing failures"
                        )
                        self._reset_shazam_instance(reason="circuit_breaker")
                        self._shazam_consecutive_failures = 0
                        # Wait a bit before next attempt
                        time.sleep(5)
                    
                    future = asyncio.run_coroutine_threadsafe(
                        self._recognize_song_async(temp_filename),
                        self._detection_loop
                    )
                    result = future.result(timeout=12.0)  # Reduced from 15s to 12s
                    # Success - reset failure counter
                    self._shazam_consecutive_failures = 0
                except concurrent.futures.TimeoutError:
                    self._shazam_consecutive_failures += 1
                    if future:
                        future.cancel()
                    logger.warning(
                        f"⚠️ Song detection timed out (12s) - forcing Shazam reset "
                        f"(failure {self._shazam_consecutive_failures}/{self._shazam_max_failures})"
                    )
                    self._song_detection_stats["last_error"] = f"timeout_failure_{self._shazam_consecutive_failures}"
                    # CRITICAL FIX: Force reset of detection loop on timeout
                    try:
                        self._reset_shazam_instance(reason="detection_timeout")
                    except Exception as reset_error:
                        logger.error(f"Error resetting Shazam after timeout: {reset_error}")
                except Exception as detect_error:
                    self._shazam_consecutive_failures += 1
                    logger.error(
                        f"Song detection error: {detect_error} "
                        f"(failure {self._shazam_consecutive_failures}/{self._shazam_max_failures})"
                    )
                    self._song_detection_stats["last_error"] = f"{type(detect_error).__name__}: {detect_error}"
                    # CRITICAL FIX: Reset on any detection error to prevent cascading failures
                    try:
                        self._reset_shazam_instance(reason="detection_error")
                    except Exception:
                        pass

                duration_sec = round(time.time() - start_monotonic, 2)

                # CRITICAL FIX: Check if we were killed by watchdog
                if duration_sec > self._song_detection_max_duration:
                    logger.warning(f"Song detection took too long ({duration_sec:.1f}s) - result may be stale")
                    self._song_detection_stats["last_error"] = "detection_timeout"
                    return  # Don't process stale results

                if result and 'track' in result:
                    track = result['track']
                    title = track.get('title', 'Unknown')
                    artist = track.get('subtitle', 'Unknown')

                    payload = self._default_song_payload(
                        title=title,
                        artist=artist,
                        confidence=1.0,
                        detected_at=datetime.now().isoformat()
                    )
                    payload["detection_duration_sec"] = duration_sec

                    if not self.current_song or self.current_song.get("title") != title:
                        logger.info(f"✅ Song detected in {duration_sec:.2f}s: {title} - {artist}")
                    else:
                        logger.debug(f"Song re-confirmed in {duration_sec:.2f}s: {title} - {artist}")

                    self.current_song = payload
                    self._song_detection_stats["last_success_at"] = payload["timestamp"]
                    self._song_detection_stats["last_error"] = None
                    # Success - reset failure counter
                    self._shazam_consecutive_failures = 0
                else:
                    if result:
                        logger.debug(f"No song detected from buffer (keys: {list(result.keys())})")
                        self._song_detection_stats["last_error"] = "no_match"
                    else:
                        logger.debug("No song detected from buffer (no result returned)")
                        self._song_detection_stats["last_error"] = "no_result"

            except Exception as e:
                duration_sec = round(time.time() - start_monotonic, 2)
                logger.error(f"Error detecting song from buffer: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                self._song_detection_stats["last_error"] = f"{type(e).__name__}: {e}"
            finally:
                if future and not future.done():
                    future.cancel()
                    try:
                        future.result()
                    except Exception:
                        pass

                if temp_filename:
                    try:
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)
                    except Exception as cleanup_error:
                        logger.debug(f"Failed to remove temp file: {cleanup_error}")

                if duration_sec is None:
                    duration_sec = round(time.time() - start_monotonic, 2)

                self._song_detection_stats["last_attempt_duration_sec"] = duration_sec
                self._song_detection_stats["active"] = False
                
                # CRITICAL FIX: Clear thread tracking before releasing lock
                self._song_detection_thread = None
                self._song_detection_started_at = 0.0
                
                self._song_detection_lock.release()

            # End detect_async

        try:
            thread = threading.Thread(target=detect_async, daemon=True)
            thread.start()
        except Exception as start_error:
            self._song_detection_stats["active"] = False
            self._song_detection_stats["last_error"] = f"thread_start_error:{start_error}"
            self._song_detection_lock.release()
            logger.error(f"Failed to start song detection thread: {start_error}")
            return False

        return True
    
    async def _recognize_song_async(self, audio_file):
        """Recognize song using ShazamIO (async with timeout)"""
        try:
            from shazamio import Shazam
            
            # CRITICAL FIX: Use a single reusable Shazam instance to prevent resource leaks
            # Creating new instances for each call causes unclosed ClientSession leaks
            # Refresh the instance periodically to prevent stale sessions
            with self._shazam_lock:
                current_time = time.time()
                needs_refresh = (
                    self._shazam_instance is None or
                    (current_time - self._shazam_created_at) > self._shazam_refresh_interval
                )
                
                if needs_refresh:
                    # Close old instance if it exists
                    if self._shazam_instance is not None:
                        try:
                            if hasattr(self._shazam_instance, 'client') and hasattr(self._shazam_instance.client, 'close'):
                                # CRITICAL FIX: Timeout the close operation to prevent hangs
                                await asyncio.wait_for(
                                    self._shazam_instance.client.close(),
                                    timeout=2.0
                                )
                        except asyncio.TimeoutError:
                            logger.warning("Timeout closing old Shazam client - forcing new instance")
                        except Exception as e:
                            logger.debug(f"Error closing old Shazam instance: {e}")
                    
                    # Create new instance
                    self._shazam_instance = Shazam()
                    self._shazam_created_at = current_time
                    logger.info("Created new Shazam instance for song detection")
                
                shazam = self._shazam_instance
            
            # CRITICAL FIX: Wrap in shield() to prevent cancellation from hanging the loop
            # Also add multiple timeout layers for defense in depth (reduced from 10s to 8s)
            try:
                recognition_task = asyncio.create_task(shazam.recognize(audio_file))
                result = await asyncio.wait_for(
                    asyncio.shield(recognition_task),
                    timeout=8.0  # Reduced from 10s to 8s for faster failure detection
                )
            except asyncio.TimeoutError:
                # Force-cancel the task if it times out
                recognition_task.cancel()
                try:
                    await asyncio.wait_for(recognition_task, timeout=1.0)  # Reduced from 2s to 1s
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                logger.warning("⚠️ Shazam recognition task timed out after 8s - task cancelled")
                raise
            return result
        except ImportError as e:
            logger.error(f"ShazamIO not available: {e}")
            logger.error("Install with: pip install shazamio aiohttp")
            return None
        except asyncio.TimeoutError:
            logger.warning("⚠️ Song recognition timed out after 10 seconds - Shazam API may be slow")
            # CRITICAL FIX: Reset Shazam instance on timeout to clear stuck connections
            with self._shazam_lock:
                self._shazam_instance = None
                self._shazam_created_at = 0.0
            return None
        except asyncio.CancelledError:
            logger.debug("Song recognition coroutine cancelled")
            raise
        except Exception as e:
            logger.error(f"Shazam recognition error: {type(e).__name__}: {e}")
            # CRITICAL FIX: Reset Shazam instance on error to prevent cascading failures
            with self._shazam_lock:
                self._shazam_instance = None
                self._shazam_created_at = 0.0
            return None
    
    def stop_monitoring(self):
        """Stop audio monitoring"""
        self.running = False
        self.stop_event.set()
        self._stream_restart_request.clear()

        if self._health_thread and self._health_thread.is_alive():
            try:
                self._health_thread.join(timeout=2.0)
            except Exception:
                pass
        self._health_thread = None
    
    def get_current_db(self) -> float:
        """Get current decibel level"""
        return self.current_db
    
    def get_peak_db(self) -> float:
        """Get peak decibel level"""
        return self.peak_db
    
    def reset_peak(self):
        """Reset peak dB"""
        self.peak_db = 0.0
    
    def get_current_song(self) -> dict:
        """Get currently detected song augmented with detection metadata."""
        song_payload = dict(self.current_song) if self.current_song else self._default_song_payload()
        song_payload.update({
            "detection_interval_sec": self._song_detection_stats.get("interval_sec"),
            "last_detection_started_at": self._song_detection_stats.get("last_attempt_started_at"),
            "last_detection_duration_sec": self._song_detection_stats.get("last_attempt_duration_sec"),
            "last_detection_success_at": self._song_detection_stats.get("last_success_at"),
            "last_detection_error": self._song_detection_stats.get("last_error"),
            "detection_active": self._song_detection_stats.get("active", False)
        })
        return song_payload

    def get_song_detection_stats(self) -> dict:
        """Return a shallow copy of the song detection telemetry."""
        return dict(self._song_detection_stats)
    
    def get_stats(self) -> dict:
        """Get all audio statistics"""
        return {
            "current_db": self.current_db,
            "peak_db": self.peak_db,
            "current_song": self.get_current_song(),
            "song_detection": self.get_song_detection_stats(),
            "timestamp": datetime.now().isoformat()
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_monitoring()
        self._stream_restart_request.clear()
        
        # Cleanup Shazam instance and its ClientSession
        try:
            self._reset_shazam_instance(reason="cleanup")
        except Exception as e:
            logger.warning(f"Error cleaning up Shazam instance: {e}")
        finally:
            self._shutdown_detection_loop()
        
        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    monitor = AudioMonitor()
    
    try:
        monitor.start_monitoring()
        
        import time
        while True:
            time.sleep(5)
            stats = monitor.get_stats()
            print(f"dB: {stats['current_db']:.1f} (peak: {stats['peak_db']:.1f})")
            if stats['current_song']['title'] != "Unknown":
                print(f"Song: {stats['current_song']['title']} - {stats['current_song']['artist']}")
    except KeyboardInterrupt:
        print("\nStopping...")
        monitor.cleanup()
