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

        self.current_db = 0.0
        self.peak_db = 0.0
        
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

        self._health_thread = None
        # CRITICAL FIX: Check health MORE frequently (every 3 seconds for faster detection)
        self._health_check_interval = 3.0  # Fixed: Always 3 seconds (ULTRA AGGRESSIVE)
        self._last_db_restart_ts = 0.0

        # Event loop and Shazam instance management now handled by SongDetector

        # Stream state tracking for watchdog-based recovery
        self._monitoring_backend = None
        self._stream_restart_count = 0
        self._max_consecutive_read_errors = 3
        # CRITICAL FIX: Reduce watchdog threshold to catch failures IMMEDIATELY (was 60s, then 20s, now 15s)
        self._watchdog_restart_threshold = 15.0  # Fixed: Always 15 seconds (ULTRA AGGRESSIVE)
        self._stream_restart_request = Event()
        
        # Rolling audio buffer for song detection (5 seconds at 44100 Hz)
        # This allows song detection without opening a separate audio stream
        self._audio_buffer_size = int(5 * self.sample_rate)  # 5 seconds
        self._audio_buffer = np.zeros(self._audio_buffer_size, dtype=np.int16)
        self._buffer_index = 0
        
        # Shazam instance management now handled by SongDetector

        # Initialize song detector if available
        if SongDetector is not None:
            try:
                # Use buffer mode: SongDetector will use our shared audio buffer
                # enabled=True ensures watchdog and threads start properly
                self.song_detector = SongDetector(
                    enabled=True,  # Enable watchdog and recovery mechanisms
                    detection_interval=int(self._song_detect_interval),
                    use_buffer_mode=True  # Use buffer-based detection instead of auto-recording
                )
                logger.info("✅ Song detector initialized (using shared audio buffer, watchdog enabled)")
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
        
        # CRITICAL FIX: Verify monitoring thread started
        time.sleep(0.2)
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            logger.error("⚠️ Monitoring thread failed to start - will retry via watchdog")
            # Don't fail completely - watchdog will restart it
        
        # Start watchdog thread to restart if monitoring crashes
        watchdog_thread = Thread(target=self._watchdog_loop, daemon=True, name="AudioMonitorWatchdog")
        watchdog_thread.start()
        time.sleep(0.1)
        if not watchdog_thread.is_alive():
            logger.error("⚠️ Watchdog thread failed to start")

        if self._health_thread is None or not self._health_thread.is_alive():
            self._health_thread = Thread(
                target=self._healthcheck_loop,
                name="AudioMonitorHealth",
                daemon=True,
            )
            self._health_thread.start()
            time.sleep(0.1)
            if self._health_thread.is_alive():
                logger.debug("Audio monitor healthcheck thread launched")
            else:
                logger.error("⚠️ Health check thread failed to start")
        
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
                
                # SongDetector now handles its own thread monitoring via its watchdog
                
                self.stop_event.wait(3)  # CRITICAL FIX: Check every 3 seconds (ULTRA AGGRESSIVE, was 5)
            except Exception as e:
                logger.error(f"🚨 CRITICAL ERROR in watchdog: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.stop_event.wait(3)
    
    def _healthcheck_loop(self):
        """Periodic health checks for the audio monitor and song detection."""
        logger.debug("Audio monitor healthcheck thread started")
        while self.running and not self.stop_event.is_set():
            try:
                now = time.time()

                # CRITICAL FIX: Guard against stale dB readings with balanced threshold
                # Only trigger if monitoring thread is alive (otherwise watchdog will handle it)
                if self._monitoring_thread and self._monitoring_thread.is_alive():
                    if self._last_db_ts and (now - self._last_db_ts) > self._watchdog_restart_threshold:
                        if not self._stream_restart_request.is_set() and (now - self._last_db_restart_ts) > self._db_interval:
                            logger.warning(
                                "⚠️ dB readings stale for %.1fs - requesting audio stream restart",
                                now - self._last_db_ts,
                            )
                            self._stream_restart_request.set()
                            self._last_db_restart_ts = now
                            
                            # CRITICAL FIX: Track complete system stall
                            if self._system_completely_stalled_at == 0.0:
                                self._system_completely_stalled_at = now
                            elif (now - self._system_completely_stalled_at) > 45.0:  # Give it 45s
                                # System has been stalled for >45s despite restart attempts
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
                else:
                    # Monitoring thread not alive - watchdog will handle restart
                    # Reset stall tracker
                    self._system_completely_stalled_at = 0.0

                # SongDetector handles its own health monitoring via its watchdog thread
                # We don't need to check it here to avoid redundant monitoring

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
                    # CRITICAL FIX: Validate buffer has actual audio data before detection
                    buffer_sum = np.sum(np.abs(self._audio_buffer))
                    if buffer_sum == 0:
                        logger.debug("Skipping song detection - audio buffer is empty (all zeros)")
                        self._last_song_detect_ts = now_song
                    else:
                        try:
                            # Use SongDetector's buffer-based detection method
                            if self.song_detector.detect_song_from_buffer(self._audio_buffer, self.sample_rate):
                                logger.debug(f"🎵 Song detection started from audio buffer (buffer sum: {buffer_sum})")
                            else:
                                logger.debug("Song detection returned False - check logs for errors")
                            self._last_song_detect_ts = now_song
                        except Exception as e:
                            logger.error(f"Failed to start song detection: {e}")
                            import traceback
                            logger.debug(traceback.format_exc())
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

            # CRITICAL FIX: AGGRESSIVE threshold for detecting stalled dB readings (use half the watchdog threshold)
            if self._last_db_ts and (self._last_activity - self._last_db_ts) > (self._watchdog_restart_threshold * 0.75):
                logger.error(
                    f"🚨 CRITICAL: No dB readings for {(self._last_activity - self._last_db_ts):.1f}s - FORCING RESTART!"
                )
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
        # Use SongDetector's song data if available
        if self.song_detector is not None:
            song_data = self.song_detector.get_latest_song()
            if song_data and song_data.get("title") != "Unknown":
                return self._default_song_payload(
                    title=song_data.get("title", "Unknown"),
                    artist=song_data.get("artist", "Unknown"),
                    confidence=1.0,
                    detected_at=datetime.fromtimestamp(song_data.get("timestamp", time.time())).isoformat() if song_data.get("timestamp") else None
                )
        
        # Fallback to default
        return self._default_song_payload()

    def get_song_detection_stats(self) -> dict:
        """Return song detection telemetry."""
        # Return basic stats - SongDetector handles its own detailed stats
        return {
            "interval_sec": self._song_detect_interval,
            "detector_enabled": self.song_detector is not None and self.song_detector.enabled
        }
    
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
        logger.info("AudioMonitor cleanup started")
        
        # Stop monitoring first
        self.stop_monitoring()
        self._stream_restart_request.clear()
        
        # CRITICAL FIX: Stop song detector with proper error handling
        if hasattr(self, 'song_detector') and self.song_detector is not None:
            try:
                logger.debug("Stopping song detector...")
                self.song_detector.stop()
                # Give it a moment to cleanup
                time.sleep(0.5)
                logger.info("✓ Song detector stopped during cleanup")
            except Exception as e:
                logger.warning(f"Error stopping song detector during cleanup: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # Cleanup PyAudio instance
        try:
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                logger.debug("PyAudio instance terminated")
        except Exception as e:
            logger.debug(f"Error terminating PyAudio: {e}")
        
        logger.info("✓ AudioMonitor cleanup completed")


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
