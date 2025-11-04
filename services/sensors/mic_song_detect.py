"""
Pulse 1.0 - Microphone Audio Analysis
Song detection and decibel level monitoring
Integrated with party_box song detection for production-ready music recognition
"""

import logging
from threading import Thread, Event, Lock
from datetime import datetime
import os
import time
from typing import Optional, Tuple

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
        self._last_successful_read = 0.0
        self._restart_requested = False

        try:
            stall_timeout = float(os.getenv('AUDIO_STREAM_STALL_TIMEOUT_SEC', '90'))
        except (TypeError, ValueError):
            stall_timeout = 90.0
        self._stream_stall_timeout = max(30.0, stall_timeout)

        try:
            reconnect_delay = float(os.getenv('AUDIO_STREAM_RECONNECT_DELAY_SEC', '5'))
        except (TypeError, ValueError):
            reconnect_delay = 5.0
        self._stream_reconnect_delay = max(1.0, reconnect_delay)

        self._consecutive_stream_failures = 0
        self._active_backend: Optional[str] = None

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
        
        # Rolling audio buffer for song detection (5 seconds at 44100 Hz)
        # This allows song detection without opening a separate audio stream
        self._audio_buffer_size = int(5 * self.sample_rate)  # 5 seconds
        self._audio_buffer = np.zeros(self._audio_buffer_size, dtype=np.int16)
        self._buffer_index = 0

        # Initialize song detector if available
        if SongDetector is not None:
            try:
                # Pass enabled=False so it doesn't start its own recording thread
                # We'll call detect_song_from_buffer() manually with our buffered audio
                self.song_detector = SongDetector(
                    enabled=False,  # Don't start background recording
                    detection_interval=int(self._song_detect_interval)
                )
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
        self._ensure_pyaudio_instance(initial=True)

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
        
        # Start monitoring thread
        self._start_monitoring_thread()
        
        # Start watchdog thread to restart if monitoring crashes
        watchdog_thread = Thread(target=self._watchdog_loop, daemon=True)
        watchdog_thread.start()
        
        logger.info("Started audio monitoring with watchdog")
    
    def _start_monitoring_thread(self):
        """Start the monitoring thread"""
        self._restart_requested = False
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        self._last_activity = time.time()
        self._last_successful_read = time.time()

    def _ensure_pyaudio_instance(self, initial: bool = False):
        """Ensure a PyAudio instance is available."""
        if not PYAUDIO_AVAILABLE:
            return

        if self.pyaudio_instance is None:
            try:
                self.pyaudio_instance = pyaudio.PyAudio()  # type: ignore[arg-type]
                if initial:
                    logger.info("PyAudio initialized successfully")
                else:
                    logger.info("PyAudio instance reinitialized")
            except Exception as e:
                logger.warning(f"PyAudio initialization failed: {e}")
                self.pyaudio_instance = None

    def _reset_pyaudio_instance(self):
        """Terminate and clear the PyAudio instance."""
        if not PYAUDIO_AVAILABLE:
            return

        if self.pyaudio_instance is not None:
            try:
                self.pyaudio_instance.terminate()
            except Exception:
                pass
        self.pyaudio_instance = None

    def _close_audio_streams(self, pa_stream: Optional[object], sd_stream: Optional[object]):
        """Safely close audio input streams."""
        if pa_stream is not None:
            try:
                pa_stream.stop_stream()
            except Exception:
                pass
            try:
                pa_stream.close()
            except Exception:
                pass

        if sd_stream is not None:
            try:
                sd_stream.stop()
            except Exception:
                pass
            try:
                sd_stream.close()
            except Exception:
                pass

    def _open_audio_streams(self) -> Tuple[Optional[object], Optional[object], Optional[str]]:
        """Attempt to open an audio input stream using available backends."""
        # Revalidate device index in case hardware changed
        if self.device_index is None:
            self._validate_device()

        pa_stream = None
        sd_stream = None
        backend: Optional[str] = None

        if PYAUDIO_AVAILABLE:
            self._ensure_pyaudio_instance()

        if PYAUDIO_AVAILABLE and self.pyaudio_instance is not None and self.device_index is not None:
            try:
                pa_stream = self.pyaudio_instance.open(
                    format=pyaudio.paInt16,  # type: ignore[attr-defined]
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=self.device_index,
                    frames_per_buffer=self.chunk_size
                )
                backend = "pyaudio"
                self._consecutive_stream_failures = 0
                self._active_backend = backend
                logger.info(f"✓ Audio stream opened successfully (PyAudio, device {self.device_index})")
                return pa_stream, None, backend
            except Exception as e:
                logger.error(f"Failed to open PyAudio stream: {e}")
                logger.error(f"  Error details: {type(e).__name__}: {str(e)}")
                self._consecutive_stream_failures += 1
                self._reset_pyaudio_instance()
                self._ensure_pyaudio_instance()

        if SOUNDDEVICE_AVAILABLE:
            try:
                sd_stream = sd.InputStream(  # type: ignore[call-arg]
                    samplerate=self.sample_rate,
                    dtype='int16',
                    channels=1,
                    blocksize=self.chunk_size,
                    device=self.device_index if self.device_index is not None else None,
                )
                sd_stream.start()
                backend = "sounddevice"
                self._consecutive_stream_failures = 0
                self._active_backend = backend
                device_msg = f", device {self.device_index}" if self.device_index is not None else ""
                logger.info(f"✓ Audio stream opened successfully (sounddevice{device_msg})")
                return None, sd_stream, backend
            except Exception as e:
                logger.error(f"Failed to open sounddevice stream: {e}")
                logger.error(f"  Error details: {type(e).__name__}: {str(e)}")
                self._consecutive_stream_failures += 1

        self._active_backend = None
        return None, None, None
    
    def _watchdog_loop(self):
        """Watchdog to restart monitoring if it crashes or stalls."""
        check_interval = max(3.0, min(self._stream_stall_timeout / 3.0, 10.0))

        while self.running and not self.stop_event.is_set():
            try:
                thread_alive = (
                    self._monitoring_thread is not None and self._monitoring_thread.is_alive()
                )

                if not thread_alive:
                    if self.running and not self._restart_requested:
                        logger.error("Audio monitoring thread not running; restarting...")
                        self._start_monitoring_thread()
                else:
                    now = time.time()
                    inactive_for = now - self._last_activity
                    since_last_read = now - self._last_successful_read

                    if (
                        self._stream_stall_timeout
                        and (inactive_for > self._stream_stall_timeout
                             or since_last_read > self._stream_stall_timeout)
                        and not self._restart_requested
                    ):
                        logger.warning(
                            "Audio monitoring appears stalled (inactive %.1fs, last read %.1fs ago); requesting restart",
                            inactive_for,
                            since_last_read,
                        )
                        self._restart_requested = True

                    if self._restart_requested:
                        # Allow the worker thread to exit on its own
                        if self._monitoring_thread is not None:
                            self._monitoring_thread.join(timeout=self._stream_reconnect_delay)
                        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
                            logger.info("Audio monitoring restart confirmed; launching new thread")
                            self._start_monitoring_thread()

                self.stop_event.wait(check_interval)
            except Exception as e:
                logger.error(f"Error in watchdog: {e}")
                self.stop_event.wait(check_interval)
    
    def _monitoring_loop(self):
        """Main monitoring loop with integrated song detection and auto-recovery."""
        pa_stream: Optional[object] = None
        sd_stream: Optional[object] = None

        try:
            while self.running and not self.stop_event.is_set():
                if self._restart_requested:
                    logger.info("Audio monitoring loop exiting due to watchdog restart request")
                    break

                now = time.time()
                if (
                    self._stream_stall_timeout
                    and self._last_successful_read
                    and (now - self._last_successful_read) > self._stream_stall_timeout
                ):
                    logger.warning(
                        "Audio stream stalled for %.1fs; reopening stream",
                        now - self._last_successful_read,
                    )
                    self._close_audio_streams(pa_stream, sd_stream)
                    if self._active_backend == "pyaudio":
                        self._reset_pyaudio_instance()
                    pa_stream = None
                    sd_stream = None
                    self._last_successful_read = now
                    self._last_activity = now
                    self.stop_event.wait(self._stream_reconnect_delay)
                    continue

                if pa_stream is None and sd_stream is None:
                    pa_stream, sd_stream, _backend = self._open_audio_streams()
                    if pa_stream is None and sd_stream is None:
                        backoff = min(
                            self._stream_reconnect_delay * (1 + min(self._consecutive_stream_failures, 5)),
                            30.0,
                        )
                        logger.error(
                            "CRITICAL: Unable to open audio stream (attempt %d). Retrying in %.1fs",
                            self._consecutive_stream_failures,
                            backoff,
                        )
                        retry_time = time.time()
                        self._last_activity = retry_time
                        self._last_successful_read = retry_time
                        self.stop_event.wait(backoff)
                        continue
                    else:
                        self._last_activity = time.time()
                        self._last_successful_read = self._last_activity
                        logger.info("🔊 Audio monitoring active - dB readings will appear shortly")

                try:
                    if pa_stream is not None:
                        audio_bytes = pa_stream.read(self.chunk_size, exception_on_overflow=False)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    elif sd_stream is not None:
                        audio_data_np, _overflow = sd_stream.read(self.chunk_size)  # type: ignore[union-attr]
                        if isinstance(audio_data_np, np.ndarray) and audio_data_np.ndim > 1:
                            audio_data_np = audio_data_np[:, 0]
                        audio_data = np.array(audio_data_np, dtype=np.int16, copy=False)
                    else:
                        # No stream available - wait before retrying
                        self._last_activity = time.time()
                        self.stop_event.wait(self._stream_reconnect_delay)
                        continue
                except Exception as read_error:
                    logger.error(
                        f"Error reading from {self._active_backend or 'audio'} stream: {read_error}"
                    )
                    import traceback
                    logger.debug(traceback.format_exc())
                    self._close_audio_streams(pa_stream, sd_stream)
                    if self._active_backend == "pyaudio":
                        self._reset_pyaudio_instance()
                    pa_stream = None
                    sd_stream = None
                    error_time = time.time()
                    self._last_activity = error_time
                    self._last_successful_read = error_time
                    self.stop_event.wait(self._stream_reconnect_delay)
                    continue

                if audio_data.size == 0:
                    idle_time = time.time()
                    self._last_activity = idle_time
                    self._last_successful_read = idle_time
                    self.stop_event.wait(0.05)
                    continue

                self._last_successful_read = time.time()
                self._last_activity = self._last_successful_read

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

                # Calculate dB level at configured cadence
                now_db = self._last_successful_read
                if (now_db - self._last_db_ts) >= self._db_interval:
                    db = self.calculate_db(audio_data)
                    self.current_db = db
                    self.peak_db = max(self.peak_db, db)
                    self._last_db_ts = now_db
                    logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB)")

                # Trigger song detection on the configured cadence using buffered audio
                now_song = self._last_successful_read
                if self.song_detector is not None and (now_song - self._last_song_detect_ts) >= self._song_detect_interval:
                    if self._buffer_index >= self._audio_buffer_size:
                        try:
                            if self._detect_song_from_buffer():
                                logger.info("🎵 Running song detection from audio buffer...")
                        except Exception as detection_error:
                            logger.error(f"Failed to start song detection thread: {detection_error}")
                    else:
                        logger.debug(
                            "Audio buffer not ready for song detection (index: %s/%s)",
                            self._buffer_index,
                            self._audio_buffer_size,
                        )
                    self._last_song_detect_ts = now_song
                elif self.song_detector is None:
                    if int(now_song) % 60 == 0:
                        logger.debug("Song detector not available - song detection disabled")

            logger.info("Audio monitoring loop stopped")

        except Exception as fatal_error:
            logger.error(f"Fatal error in monitoring loop: {fatal_error}")
            import traceback
            logger.debug(traceback.format_exc())
        finally:
            self._close_audio_streams(pa_stream, sd_stream)
            self._active_backend = None
    
    def _detect_song_from_buffer(self):
        """Detect song using buffered audio data (runs in background thread)."""
        import tempfile
        import wave
        import threading
        import asyncio

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
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name

                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(self._audio_buffer.tobytes())

                logger.debug(f"Saved audio buffer to {temp_filename}")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = None
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            self._recognize_song_async(temp_filename),
                            timeout=20.0
                        )
                    )
                except asyncio.TimeoutError:
                    logger.warning("Song detection timed out (20s) - skipping")
                    self._song_detection_stats["last_error"] = "timeout"
                except Exception as detect_error:
                    logger.error(f"Song detection error: {detect_error}")
                    self._song_detection_stats["last_error"] = f"{type(detect_error).__name__}: {detect_error}"
                finally:
                    try:
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                    loop.close()

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
                logger.error(f"Error detecting song from buffer: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                self._song_detection_stats["last_error"] = f"{type(e).__name__}: {e}"
            finally:
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
            import asyncio
            from shazamio import Shazam
            
            shazam = Shazam()
            
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
        except Exception as e:
            logger.error(f"Shazam recognition error: {type(e).__name__}: {e}")
            return None
    
    def stop_monitoring(self):
        """Stop audio monitoring"""
        self.running = False
        self.stop_event.set()
    
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
        self._close_audio_streams(None, None)
        self._reset_pyaudio_instance()


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
