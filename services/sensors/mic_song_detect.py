"""
Pulse 1.0 - Microphone Audio Analysis
Song detection and decibel level monitoring
Integrated with party_box song detection for production-ready music recognition
"""

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
        self._last_db_update = 0.0  # Track when dB was last updated
        self._db_update_timeout = 30.0  # If no dB update for 30s, restart stream
        self._monitoring_thread_crash_count = 0
        self._max_thread_crashes = 10  # Prevent infinite restart loops

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

        # Dedicated async event loop for song recognition to keep Shazam stable
        self._detection_loop = None
        self._detection_loop_thread = None
        self._detection_loop_ready_event = None
        self._detection_loop_lock = Lock()

        # Stream state tracking for watchdog-based recovery
        self._monitoring_backend = None
        self._stream_restart_count = 0
        self._max_consecutive_read_errors = 3
        self._watchdog_restart_threshold = max(60.0, self._song_detect_interval * 4)
        self._stream_restart_request = Event()
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5  # After 5 consecutive failures, wait longer
        self._circuit_breaker_cooldown = 60.0  # Wait 60s before retrying after circuit breaker trips
        self._last_circuit_breaker_reset = 0.0
        
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
        self._shazam_refresh_interval = 3600.0  # Refresh every hour to prevent stale sessions

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
        """Ensure the dedicated async loop for Shazam runs in a background thread - with auto-restart."""
        # Check if loop exists and thread is alive
        if self._detection_loop is not None:
            if self._detection_loop_thread is not None and self._detection_loop_thread.is_alive():
                # Verify loop is still running by checking if it's closed
                try:
                    if not self._detection_loop.is_closed():
                        return True
                    else:
                        logger.warning("Detection loop is closed - will restart")
                except Exception:
                    logger.warning("Could not check detection loop status - will restart")
            else:
                logger.warning("Detection loop thread is not alive - will restart")

        with self._detection_loop_lock:
            # Double-check after acquiring lock
            if self._detection_loop is not None:
                if self._detection_loop_thread is not None and self._detection_loop_thread.is_alive():
                    try:
                        if not self._detection_loop.is_closed():
                            return True
                    except Exception:
                        pass
            
            # Clean up old loop if it exists
            try:
                self._shutdown_detection_loop()
            except Exception:
                pass

            try:
                loop = asyncio.new_event_loop()
                ready_event = Event()
                loop_ready = [False]  # Use list for mutable reference

                def _loop_runner():
                    try:
                        asyncio.set_event_loop(loop)
                        ready_event.set()
                        loop_ready[0] = True
                        logger.info("✅ Song detection event loop started")
                        loop.run_forever()
                    except Exception as loop_error:
                        logger.error(f"❌ Song detection loop crashed: {loop_error}", exc_info=True)
                        loop_ready[0] = False
                        # Attempt to restart after a delay
                        if self.running and not self.stop_event.is_set():
                            logger.warning("Will attempt to restart detection loop...")
                    finally:
                        logger.debug("Song detection loop thread exiting")

                thread = Thread(target=_loop_runner, name="AudioMonitorSongLoop", daemon=True)
                thread.start()

                if not ready_event.wait(timeout=5.0):
                    logger.error("❌ Song detection loop failed to start within 5 seconds")
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

                if not loop_ready[0]:
                    logger.error("Song detection loop thread started but reported not ready")
                    return False

                self._detection_loop = loop
                self._detection_loop_thread = thread
                self._detection_loop_ready_event = ready_event
                logger.info("✅ Song detection loop initialized and ready")
                return True
            except Exception as exc:
                logger.error(f"❌ Failed to initialize song detection loop: {exc}", exc_info=True)
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
        
        # Start monitoring thread
        self._start_monitoring_thread()
        
        # Start watchdog thread to restart if monitoring crashes
        watchdog_thread = Thread(target=self._watchdog_loop, daemon=True)
        watchdog_thread.start()
        
        logger.info("Started audio monitoring with watchdog")
    
    def _start_monitoring_thread(self):
        """Start the monitoring thread with enhanced error handling"""
        # Ensure old thread is cleaned up
        if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
            logger.warning("Old monitoring thread still alive - waiting for cleanup")
            # Don't wait indefinitely, just log and continue
            try:
                # Give it a moment, but don't block
                pass
            except Exception:
                pass
        
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True, name="AudioMonitorThread")
        self._monitoring_thread.start()
        self._last_activity = time.time()
        self._last_db_update = time.time()  # Initialize dB update timestamp
        self._stream_restart_count = 0
        self._stream_restart_request.clear()
        logger.info("✅ Monitoring thread started (PID-aware watchdog will monitor)")
    
    def _watchdog_loop(self):
        """Watchdog to restart monitoring if it crashes - ENHANCED for reliability"""
        watchdog_check_interval = 5.0  # Check every 5 seconds (more aggressive)
        
        while self.running and not self.stop_event.is_set():
            try:
                now = time.time()
                
                # Check if monitoring thread is alive
                if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
                    self._monitoring_thread_crash_count += 1
                    logger.error(
                        "⚠️ Audio monitoring thread died! Restarting... (crash count: %d/%d)",
                        self._monitoring_thread_crash_count,
                        self._max_thread_crashes
                    )
                    
                    if self._monitoring_thread_crash_count >= self._max_thread_crashes:
                        logger.error(
                            "🚨 CRITICAL: Monitoring thread has crashed %d times. "
                            "Entering circuit breaker cooldown for %.1fs",
                            self._monitoring_thread_crash_count,
                            self._circuit_breaker_cooldown
                        )
                        self._circuit_breaker_failures = self._circuit_breaker_threshold
                        self._last_circuit_breaker_reset = now
                        self.stop_event.wait(self._circuit_breaker_cooldown)
                        self._monitoring_thread_crash_count = 0  # Reset after cooldown
                        continue
                    
                    # Close any stale streams before restarting
                    try:
                        if self._monitoring_backend == "pyaudio" and self.pyaudio_instance:
                            # Try to close any existing streams
                            pass  # PyAudio handles cleanup automatically
                    except Exception:
                        pass
                    
                    self._start_monitoring_thread()
                    logger.info("✅ Monitoring thread restarted successfully")
                
                # Check circuit breaker status
                if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                    time_since_reset = now - self._last_circuit_breaker_reset
                    if time_since_reset < self._circuit_breaker_cooldown:
                        logger.debug(
                            "Circuit breaker active - waiting %.1fs before retry",
                            self._circuit_breaker_cooldown - time_since_reset
                        )
                        self.stop_event.wait(min(watchdog_check_interval, self._circuit_breaker_cooldown - time_since_reset))
                        continue
                    else:
                        logger.info("Circuit breaker cooldown complete - resetting")
                        self._circuit_breaker_failures = 0
                        self._last_circuit_breaker_reset = 0.0
                
                # Check for dB reading timeout (more aggressive check)
                if self._last_db_update > 0:
                    time_since_db_update = now - self._last_db_update
                    if time_since_db_update > self._db_update_timeout:
                        logger.warning(
                            "⚠️ dB readings have stopped updating for %.1fs (threshold: %.1fs) - forcing stream restart",
                            time_since_db_update,
                            self._db_update_timeout
                        )
                        self._stream_restart_request.set()
                        self._circuit_breaker_failures += 1
                        self._last_db_update = now  # Reset to prevent immediate retrigger
                
                # Check for general inactivity
                inactivity = now - self._last_activity
                if inactivity > self._watchdog_restart_threshold and self._monitoring_backend is not None:
                    logger.warning(
                        "⚠️ Audio monitoring stalled (no activity for %.1fs, backend=%s) - restarting stream",
                        inactivity,
                        self._monitoring_backend
                    )
                    self._stream_restart_request.set()
                    self._circuit_breaker_failures += 1
                    self._last_activity = now
                elif inactivity > self._watchdog_restart_threshold:
                    self._last_activity = now  # Prevent repeated warnings when backend is inactive
                
                # Check if detection loop is still running
                if self.song_detector is not None:
                    if not self._ensure_detection_loop():
                        logger.warning("⚠️ Song detection loop crashed - attempting restart")
                        self._shutdown_detection_loop()
                        if not self._ensure_detection_loop():
                            logger.error("❌ Failed to restart song detection loop")
                
                # Reset circuit breaker on successful checks
                if inactivity < self._watchdog_restart_threshold and (self._last_db_update == 0 or (now - self._last_db_update) < self._db_update_timeout):
                    if self._circuit_breaker_failures > 0:
                        self._circuit_breaker_failures = max(0, self._circuit_breaker_failures - 1)  # Gradual recovery
                
                self.stop_event.wait(watchdog_check_interval)
            except Exception as e:
                logger.error(f"❌ Error in watchdog: {e}", exc_info=True)
                self.stop_event.wait(watchdog_check_interval)
    
    def _monitoring_loop(self):
        """Main monitoring loop with automatic recovery for stream failures - NEVER GIVES UP."""
        logger.info("🔊 Audio monitoring loop thread started - will run indefinitely")
        consecutive_failures = 0
        max_consecutive_failures = 10
        
        # CRITICAL: This loop should NEVER exit unless explicitly stopped
        while self.running and not self.stop_event.is_set():
            backend = None
            pa_stream = None
            sd_stream = None

            try:
                # Check circuit breaker before attempting stream open
                if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                    wait_time = self._circuit_breaker_cooldown
                    logger.warning("Circuit breaker active - waiting %.1fs before retry", wait_time)
                    if self.stop_event.wait(wait_time):
                        break
                    continue

                backend, pa_stream, sd_stream = self._open_audio_stream(self._stream_restart_count)
                self._monitoring_backend = backend
                self._stream_restart_count = 0
                consecutive_failures = 0  # Reset on successful stream open
                logger.info("🔊 Audio monitoring active - dB readings will appear shortly")
                self._stream_restart_request.clear()
                
                # Run the audio loop - this should run indefinitely
                self._run_audio_loop(backend, pa_stream, sd_stream)

                # If run_audio_loop returns normally, it means stream needs restart
                logger.info("Audio loop returned - will restart stream")
                continue

            except self.StreamInitError as init_error:
                consecutive_failures += 1
                self._stream_restart_count += 1
                wait_time = min(10.0, 1.0 + self._stream_restart_count * 0.5)
                logger.error(
                    "❌ Audio stream initialization failed (attempt %d, consecutive failures: %d): %s",
                    self._stream_restart_count,
                    consecutive_failures,
                    init_error,
                )
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        "🚨 Too many consecutive failures (%d) - entering extended cooldown",
                        consecutive_failures
                    )
                    wait_time = self._circuit_breaker_cooldown
                    consecutive_failures = 0  # Reset after cooldown
                
                if self.stop_event.wait(wait_time):
                    break
                continue  # Always continue, never break

            except self.StreamRuntimeError as runtime_error:
                consecutive_failures += 1
                self._stream_restart_count += 1
                wait_time = min(10.0, 1.5 * self._stream_restart_count * 0.5)
                logger.warning(
                    "⚠️ Audio stream runtime failure detected: %s -- restarting stream (attempt %d, consecutive: %d)",
                    runtime_error,
                    self._stream_restart_count,
                    consecutive_failures,
                )
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        "🚨 Too many consecutive runtime failures (%d) - entering extended cooldown",
                        consecutive_failures
                    )
                    wait_time = self._circuit_breaker_cooldown
                    consecutive_failures = 0
                
                if self.stop_event.wait(wait_time):
                    break
                continue  # Always continue, never break

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received in monitoring loop")
                break

            except Exception as unexpected:
                consecutive_failures += 1
                self._stream_restart_count += 1
                wait_time = min(10.0, 1.5 * self._stream_restart_count * 0.5)
                logger.error(
                    "❌ Unexpected audio monitoring error (attempt %d, consecutive: %d): %s",
                    self._stream_restart_count,
                    consecutive_failures,
                    unexpected,
                    exc_info=True
                )
                
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        "🚨 Too many unexpected failures (%d) - entering extended cooldown",
                        consecutive_failures
                    )
                    wait_time = self._circuit_breaker_cooldown
                    consecutive_failures = 0
                
                if self.stop_event.wait(wait_time):
                    break
                continue  # Always continue, never break

            finally:
                # Always clean up streams
                self._monitoring_backend = None
                self._close_audio_stream(pa_stream, sd_stream)

        logger.info("Audio monitoring loop exited (running=%s, stop_event=%s)", self.running, self.stop_event.is_set())

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

        while self.running and not self.stop_event.is_set():
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
                self._last_db_update = now_db  # CRITICAL: Update timestamp for watchdog
                logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB)")

            # Trigger song detection on cadence using buffered audio
            now_song = time.time()
            if self.song_detector is not None and (now_song - self._last_song_detect_ts) >= self._song_detect_interval:
                if self._buffer_index >= self._audio_buffer_size:
                    try:
                        # Ensure detection loop is still running before attempting detection
                        if not self._ensure_detection_loop():
                            logger.error("❌ Song detection loop unavailable - cannot detect songs")
                            # Don't update timestamp, will retry next interval
                        elif self._detect_song_from_buffer():
                            logger.debug("🎵 Song detection triggered from audio buffer...")
                    except Exception as e:
                        logger.error(f"❌ Failed to start song detection: {e}", exc_info=True)
                        # Update timestamp to prevent rapid retries
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

            if self._stream_restart_request.is_set():
                logger.info("Audio stream restart requested by watchdog")
                self._stream_restart_request.clear()
                raise self.StreamRuntimeError("Watchdog requested audio stream restart")

            # If dB readings have stopped updating, trigger a restart
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
        """Detect song using buffered audio data (runs in background thread) - ENHANCED with better error handling."""
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
            """Background thread for song detection with comprehensive error handling."""
            temp_filename = None
            duration_sec = None
            future = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name

                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(self._audio_buffer.tobytes())

                logger.debug(f"Saved audio buffer to {temp_filename}")

                # Ensure detection loop is available
                if not self._ensure_detection_loop():
                    logger.error("❌ Song detection loop unavailable; cannot detect songs")
                    self._song_detection_stats["last_error"] = "loop_unavailable"
                    return

                result = None
                future = None
                try:
                    # Verify loop is still valid before submitting
                    if self._detection_loop is None or self._detection_loop.is_closed():
                        logger.error("❌ Detection loop is closed - cannot detect songs")
                        self._song_detection_stats["last_error"] = "loop_closed"
                        return
                    
                    future = asyncio.run_coroutine_threadsafe(
                        self._recognize_song_async(temp_filename),
                        self._detection_loop
                    )
                    result = future.result(timeout=20.0)
                except concurrent.futures.TimeoutError:
                    if future:
                        try:
                            future.cancel()
                        except Exception:
                            pass
                    logger.warning("⚠️ Song detection timed out (20s) - skipping")
                    self._song_detection_stats["last_error"] = "timeout"
                except RuntimeError as runtime_err:
                    # Loop might have been closed
                    if "loop is closed" in str(runtime_err).lower() or "event loop is closed" in str(runtime_err).lower():
                        logger.error("❌ Detection loop was closed during recognition - will restart on next attempt")
                        self._song_detection_stats["last_error"] = "loop_closed_during_operation"
                        # Force loop restart on next detection
                        try:
                            self._shutdown_detection_loop()
                        except Exception:
                            pass
                    else:
                        logger.error(f"❌ Runtime error during song detection: {runtime_err}")
                        self._song_detection_stats["last_error"] = f"RuntimeError: {runtime_err}"
                except Exception as detect_error:
                    logger.error(f"❌ Song detection error: {detect_error}", exc_info=True)
                    self._song_detection_stats["last_error"] = f"{type(detect_error).__name__}: {detect_error}"

                duration_sec = round(time.time() - start_monotonic, 2)

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
                else:
                    if result:
                        logger.debug(f"No song detected from buffer (keys: {list(result.keys())})")
                        self._song_detection_stats["last_error"] = "no_match"
                    else:
                        logger.debug("No song detected from buffer (no result returned)")
                        self._song_detection_stats["last_error"] = "no_result"

            except Exception as e:
                duration_sec = round(time.time() - start_monotonic, 2)
                logger.error(f"❌ Error detecting song from buffer: {e}", exc_info=True)
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
                self._song_detection_lock.release()

            # End detect_async

        try:
            thread = threading.Thread(target=detect_async, daemon=True, name="SongDetectionThread")
            thread.start()
            logger.debug("Song detection thread started")
        except Exception as start_error:
            self._song_detection_stats["active"] = False
            self._song_detection_stats["last_error"] = f"thread_start_error:{start_error}"
            self._song_detection_lock.release()
            logger.error(f"❌ Failed to start song detection thread: {start_error}", exc_info=True)
            return False

        return True
    
    async def _recognize_song_async(self, audio_file):
        """Recognize song using ShazamIO (async with timeout)"""
        try:
            from shazamio import Shazam
            
            # Use a single reusable Shazam instance to prevent resource leaks
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
                                await self._shazam_instance.client.close()
                        except Exception as e:
                            logger.debug(f"Error closing old Shazam instance: {e}")
                    
                    # Create new instance
                    self._shazam_instance = Shazam()
                    self._shazam_created_at = current_time
                    logger.info("Created new Shazam instance for song detection")
                
                shazam = self._shazam_instance
            
            # Add 15 second timeout to prevent hanging
            result = await asyncio.wait_for(
                shazam.recognize(audio_file),
                timeout=15.0
            )
            return result
        except ImportError as e:
            logger.error(f"ShazamIO not available: {e}")
            logger.error("Install with: pip install shazamio aiohttp")
            return None
        except asyncio.TimeoutError:
            logger.warning("Song recognition timed out after 15 seconds")
            return None
        except asyncio.CancelledError:
            logger.debug("Song recognition coroutine cancelled")
            raise
        except Exception as e:
            logger.error(f"Shazam recognition error: {type(e).__name__}: {e}")
            return None
    
    def stop_monitoring(self):
        """Stop audio monitoring"""
        self.running = False
        self.stop_event.set()
        self._stream_restart_request.clear()
    
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
            with self._shazam_lock:
                if self._shazam_instance is not None:
                    # ShazamIO's Shazam class uses aiohttp ClientSession internally
                    # We need to properly close it to prevent resource leaks
                    client = getattr(self._shazam_instance, 'client', None)
                    close_callable = getattr(client, 'close', None) if client else None

                    if close_callable is not None:
                        try:
                            close_coro = close_callable()
                            if asyncio.iscoroutine(close_coro):
                                future = None
                                try:
                                    if self._detection_loop is not None:
                                        future = asyncio.run_coroutine_threadsafe(close_coro, self._detection_loop)
                                        future.result(timeout=5.0)
                                    else:
                                        asyncio.run(close_coro)
                                except concurrent.futures.TimeoutError:
                                    if future:
                                        future.cancel()
                                    logger.debug("Timeout while closing Shazam client session")
                                except Exception as close_error:
                                    logger.debug(f"Error closing Shazam client: {close_error}", exc_info=True)
                                finally:
                                    if future and not future.done():
                                        future.cancel()
                                        try:
                                            future.result()
                                        except Exception:
                                            pass
                            else:
                                # If close() returned None, it likely handled closing synchronously
                                pass
                        except Exception as close_exc:
                            logger.debug(f"Exception while invoking Shazam client close(): {close_exc}", exc_info=True)
                    self._shazam_instance = None
                    logger.info("Shazam instance cleaned up")
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
