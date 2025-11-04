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
        self._last_audio_data_time = 0.0  # Track when we last received audio data
        self._stream_healthy = False  # Track if audio stream is actually working

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
        self._shazam_refresh_interval = 1800.0  # Refresh every 30 minutes to prevent stale sessions
        self._shazam_use_count = 0  # Track number of uses
        self._shazam_max_uses = 50  # Recreate after 50 uses to prevent resource accumulation

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
    
    def _is_detection_loop_healthy(self) -> bool:
        """Check if the detection event loop is still running and responsive."""
        if self._detection_loop is None or self._detection_loop_thread is None:
            return False
        
        # Check if thread is alive
        if not self._detection_loop_thread.is_alive():
            return False
        
        # Check if loop is running
        try:
            if self._detection_loop.is_closed():
                return False
            if not self._detection_loop.is_running():
                return False
        except Exception:
            return False
        
        return True
    
    def _ensure_detection_loop(self) -> bool:
        """Ensure the dedicated async loop for Shazam runs in a background thread."""
        if self._detection_loop is not None and self._is_detection_loop_healthy():
            return True

        with self._detection_loop_lock:
            # Double-check after acquiring lock
            if self._detection_loop is not None and self._is_detection_loop_healthy():
                return True
            
            # Clean up unhealthy loop if it exists
            if self._detection_loop is not None:
                logger.warning("Cleaning up unhealthy detection loop before recreating")
                self._shutdown_detection_loop()

            try:
                loop = asyncio.new_event_loop()
                ready_event = Event()

                def _loop_runner():
                    try:
                        asyncio.set_event_loop(loop)
                        ready_event.set()
                        logger.debug("Song detection event loop started")
                        loop.run_forever()
                    except Exception as e:
                        logger.error(f"Detection loop runner failed: {e}")
                    finally:
                        logger.debug("Detection loop runner exiting")

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
                logger.info("Detection event loop created successfully")
                return True
            except Exception as exc:
                logger.error(f"Failed to initialize song detection loop: {exc}")
                import traceback
                logger.error(traceback.format_exc())
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
        """Start the monitoring thread"""
        # Clean up old thread if it exists
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.warning("Old monitoring thread still alive, attempting to stop it first")
            self.stop_event.set()
            self._monitoring_thread.join(timeout=3.0)
            if self._monitoring_thread.is_alive():
                logger.error("Old monitoring thread did not stop, continuing anyway")
            self.stop_event.clear()
        
        logger.info("Starting new monitoring thread...")
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True, name="AudioMonitoringThread")
        self._monitoring_thread.start()
        self._last_activity = time.time()
        self._last_audio_data_time = time.time()  # Initialize to prevent immediate false alarm
        logger.info("Monitoring thread started successfully")
    
    def _watchdog_loop(self):
        """Watchdog to restart monitoring if it crashes or gets stuck"""
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while self.running and not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # Check if monitoring thread is alive
                if not self._monitoring_thread or not self._monitoring_thread.is_alive():
                    logger.error("Audio monitoring thread died! Restarting...")
                    consecutive_failures += 1
                    if consecutive_failures < max_consecutive_failures:
                        self._start_monitoring_thread()
                    else:
                        logger.error(f"Monitoring thread failed {consecutive_failures} times. Waiting before retry...")
                        self.stop_event.wait(30)  # Wait 30s before trying again
                        consecutive_failures = 0
                        self._start_monitoring_thread()
                    self.stop_event.wait(5)
                    continue
                
                # Check if we're actually receiving audio data (more reliable than activity)
                time_since_audio = current_time - self._last_audio_data_time
                if self._last_audio_data_time > 0 and time_since_audio > 45:  # No audio data for 45 seconds
                    logger.error(f"Audio stream appears dead (no data for {time_since_audio:.1f}s). Restarting monitoring...")
                    # Force restart the monitoring thread to reinitialize the audio stream
                    self.stop_event.set()  # Signal current thread to stop
                    time.sleep(2)  # Give it time to clean up
                    if self._monitoring_thread and self._monitoring_thread.is_alive():
                        self._monitoring_thread.join(timeout=5.0)
                    self.stop_event.clear()
                    self._start_monitoring_thread()
                    self.stop_event.wait(5)
                    continue
                
                # Check if detection loop is still running
                if self.song_detector and self._detection_loop and not self._is_detection_loop_healthy():
                    logger.error("Song detection event loop is unhealthy. Recreating...")
                    self._shutdown_detection_loop()
                    if self._ensure_detection_loop():
                        logger.info("Song detection event loop recreated successfully")
                    else:
                        logger.error("Failed to recreate detection loop")
                
                # Reset consecutive failures if we get here
                consecutive_failures = 0
                
                # Check general activity for logging
                if current_time - self._last_activity > 90:
                    logger.info("Watchdog: System quiet for 90s, but monitoring thread is alive and healthy")
                    self._last_activity = current_time
                
                self.stop_event.wait(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in watchdog: {e}")
                import traceback
                logger.error(traceback.format_exc())
                self.stop_event.wait(10)
    
    def _monitoring_loop(self):
        """Main monitoring loop with integrated song detection"""
        pa_stream = None
        sd_stream = None
        stream_opened = False

        try:
            # Try PyAudio first
            if PYAUDIO_AVAILABLE and self.pyaudio_instance is not None:
                if self.device_index is None:
                    logger.error("No audio input device found; cannot open audio stream")
                    logger.warning("Audio monitoring will be disabled")
                else:
                    try:
                        pa_stream = self.pyaudio_instance.open(
                            format=pyaudio.paInt16,  # type: ignore[attr-defined]
                            channels=1,
                            rate=self.sample_rate,
                            input=True,
                            input_device_index=self.device_index,
                            frames_per_buffer=self.chunk_size
                        )
                        stream_opened = True
                        logger.info(f"✓ Audio stream opened successfully (PyAudio, device {self.device_index})")
                    except Exception as e:
                        logger.error(f"Failed to open PyAudio stream: {e}")
                        logger.error(f"  Error details: {type(e).__name__}: {str(e)}")
                        # Try sounddevice as fallback if available
                        if SOUNDDEVICE_AVAILABLE:
                            logger.info("Attempting fallback to sounddevice...")
            
            # Try sounddevice if PyAudio didn't work or isn't available
            if not stream_opened and SOUNDDEVICE_AVAILABLE:
                if self.device_index is None:
                    logger.error("No audio input device found; cannot open audio stream")
                    logger.warning("Audio monitoring will be disabled")
                else:
                    try:
                        sd_stream = sd.InputStream(  # type: ignore[call-arg]
                            samplerate=self.sample_rate,
                            dtype='int16',
                            channels=1,
                            blocksize=self.chunk_size,
                            device=self.device_index,
                        )
                        sd_stream.start()
                        stream_opened = True
                        logger.info(f"✓ Audio stream opened successfully (sounddevice, device {self.device_index})")
                    except Exception as e:
                        logger.error(f"Failed to open sounddevice stream: {e}")
                        logger.error(f"  Error details: {type(e).__name__}: {str(e)}")
            
            if not stream_opened:
                logger.error("="*80)
                logger.error("CRITICAL: Could not open any audio stream!")
                logger.error("Audio monitoring (dB readings) will NOT work.")
                logger.error("Check:")
                logger.error("  1. Audio device is connected: arecord -l")
                logger.error("  2. Device permissions: arecord -d 1 test.wav")
                logger.error("  3. Dependencies installed: pip install pyaudio sounddevice")
                logger.error("="*80)
                # Still run the loop for song detection, but no dB readings
            else:
                logger.info("🔊 Audio monitoring active - dB readings will appear shortly")

            while self.running and not self.stop_event.is_set():
                try:
                    # Read audio data
                    audio_data = None
                    read_success = False
                    
                    if pa_stream is not None:
                        try:
                            audio_bytes = pa_stream.read(self.chunk_size, exception_on_overflow=False)
                            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                            read_success = True
                        except Exception as read_err:
                            logger.error(f"PyAudio read failed: {read_err}. Stream may be closed.")
                            # Stream is broken, exit loop to trigger restart
                            break
                    elif sd_stream is not None:
                        try:
                            audio_data, _ = sd_stream.read(self.chunk_size)  # type: ignore[union-attr]
                            if isinstance(audio_data, np.ndarray) and audio_data.ndim > 1:
                                audio_data = audio_data[:, 0]
                            audio_data = audio_data.astype(np.int16, copy=False)
                            read_success = True
                        except Exception as read_err:
                            logger.error(f"sounddevice read failed: {read_err}. Stream may be closed.")
                            # Stream is broken, exit loop to trigger restart
                            break
                    else:
                        # No stream available - just check song detection and wait
                        if self.song_detector is not None:
                            song_info = self.song_detector.get_latest_song()
                            if song_info and song_info.get("title") != "Unknown":
                                self.current_song = song_info
                                logger.info(f"🎵 Song: {song_info['title']} - {song_info['artist']}")
                        self.stop_event.wait(5.0)
                        continue

                    if audio_data is None or audio_data.size == 0:
                        logger.warning("Received empty audio data, skipping iteration")
                        continue
                    
                    # Mark that we successfully received audio data
                    if read_success:
                        self._last_audio_data_time = time.time()
                        self._stream_healthy = True
                    
                    # Store audio in rolling buffer for song detection
                    chunk_len = min(len(audio_data), self._audio_buffer_size)
                    if self._buffer_index + chunk_len <= self._audio_buffer_size:
                        # Fits in remaining buffer space
                        self._audio_buffer[self._buffer_index:self._buffer_index + chunk_len] = audio_data[:chunk_len]
                        self._buffer_index += chunk_len
                    else:
                        # Wrap around - shift old data and append new
                        shift_amount = chunk_len
                        self._audio_buffer = np.roll(self._audio_buffer, -shift_amount)
                        self._audio_buffer[-shift_amount:] = audio_data[:chunk_len]
                        self._buffer_index = self._audio_buffer_size  # Buffer is full
                    
                    # Calculate dB level more frequently for better responsiveness (every 2 seconds)
                    now_db = time.time()
                    if (now_db - self._last_db_ts) >= 2.0:  # Update every 2 seconds
                        db = self.calculate_db(audio_data)
                        self.current_db = db
                        self.peak_db = max(self.peak_db, db)
                        self._last_db_ts = now_db
                        self._last_activity = now_db  # Update watchdog
                        logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB)")
                    
                    # Trigger song detection on the configured cadence using buffered audio
                    # Run in non-blocking way to prevent hanging
                    now_song = time.time()
                    if self.song_detector is not None and (now_song - self._last_song_detect_ts) >= self._song_detect_interval:
                        if self._buffer_index >= self._audio_buffer_size:  # Buffer is full (5 seconds)
                            # Run in separate thread to prevent blocking even if it hangs
                            try:
                                if self._detect_song_from_buffer():
                                    logger.info("🎵 Running song detection from audio buffer...")
                            except Exception as e:
                                logger.error(f"Failed to start song detection thread: {e}")
                        else:
                            logger.debug(f"Audio buffer not ready for song detection (index: {self._buffer_index}/{self._audio_buffer_size})")
                        self._last_song_detect_ts = now_song
                        self._last_activity = now_song  # Update watchdog
                    elif self.song_detector is None:
                        # Log occasionally if song detector is not available
                        if int(now_song) % 60 == 0:  # Log once per minute
                            logger.debug("Song detector not available - song detection disabled")
                    
                    # Update last_activity for general liveness tracking
                    # Note: _last_audio_data_time is updated when we actually read audio data
                    self._last_activity = time.time()
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info("Audio monitoring stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't set running to False - let watchdog restart us
            logger.info("Monitoring loop exited due to error, watchdog will restart")
        finally:
            try:
                if pa_stream:
                    pa_stream.stop_stream()
                    pa_stream.close()
                    logger.debug("PyAudio stream closed")
            except Exception as e:
                logger.debug(f"Error closing PyAudio stream: {e}")
            try:
                if sd_stream:
                    sd_stream.stop()
                    sd_stream.close()
                    logger.debug("sounddevice stream closed")
            except Exception as e:
                logger.debug(f"Error closing sounddevice stream: {e}")
            
            # Mark stream as unhealthy so watchdog knows to restart
            self._stream_healthy = False
    
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
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name

                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(self._audio_buffer.tobytes())

                logger.debug(f"Saved audio buffer to {temp_filename}")

                result = None
                try:
                    # Verify detection loop is healthy before attempting
                    if not self._ensure_detection_loop():
                        logger.error("Detection loop unavailable; skipping detection")
                        self._song_detection_stats["last_error"] = "loop_unavailable"
                        return
                    
                    future = asyncio.run_coroutine_threadsafe(
                        self._recognize_song_async(temp_filename),
                        self._detection_loop
                    )
                    result = future.result(timeout=20.0)
                except concurrent.futures.TimeoutError:
                    if future:
                        future.cancel()
                    logger.warning("Song detection timed out (20s) - skipping")
                    self._song_detection_stats["last_error"] = "timeout"
                    # Check if loop is still healthy after timeout
                    if not self._is_detection_loop_healthy():
                        logger.error("Detection loop appears unhealthy after timeout")
                except Exception as detect_error:
                    logger.error(f"Song detection error: {detect_error}")
                    import traceback
                    logger.debug(traceback.format_exc())
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
            
            # Use a single reusable Shazam instance to prevent resource leaks
            # Creating new instances for each call causes unclosed ClientSession leaks
            # Refresh the instance periodically to prevent stale sessions
            with self._shazam_lock:
                current_time = time.time()
                needs_refresh = (
                    self._shazam_instance is None or
                    (current_time - self._shazam_created_at) > self._shazam_refresh_interval or
                    self._shazam_use_count >= self._shazam_max_uses
                )
                
                if needs_refresh:
                    # Close old instance if it exists
                    if self._shazam_instance is not None:
                        try:
                            if hasattr(self._shazam_instance, 'client') and hasattr(self._shazam_instance.client, 'close'):
                                await self._shazam_instance.client.close()
                            logger.debug(f"Closed old Shazam instance (age: {current_time - self._shazam_created_at:.1f}s, uses: {self._shazam_use_count})")
                        except Exception as e:
                            logger.debug(f"Error closing old Shazam instance: {e}")
                    
                    # Create new instance
                    self._shazam_instance = Shazam()
                    self._shazam_created_at = current_time
                    self._shazam_use_count = 0
                    logger.info("Created new Shazam instance for song detection")
                
                shazam = self._shazam_instance
                self._shazam_use_count += 1
            
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
        logger.info("Stopping audio monitoring...")
        self.running = False
        self.stop_event.set()
        
        # Wait for monitoring thread to finish
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            logger.debug("Waiting for monitoring thread to stop...")
            self._monitoring_thread.join(timeout=5.0)
            if self._monitoring_thread.is_alive():
                logger.warning("Monitoring thread did not stop cleanly")
        
        logger.info("Audio monitoring stopped")
    
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
    
    def get_health_status(self) -> dict:
        """Get detailed health status for monitoring and debugging"""
        current_time = time.time()
        
        return {
            "monitoring_active": self.running,
            "monitoring_thread_alive": self._monitoring_thread.is_alive() if self._monitoring_thread else False,
            "stream_healthy": self._stream_healthy,
            "last_activity_seconds_ago": round(current_time - self._last_activity, 1) if self._last_activity > 0 else None,
            "last_audio_data_seconds_ago": round(current_time - self._last_audio_data_time, 1) if self._last_audio_data_time > 0 else None,
            "detection_loop_healthy": self._is_detection_loop_healthy() if hasattr(self, '_is_detection_loop_healthy') else None,
            "detection_loop_exists": self._detection_loop is not None,
            "song_detector_enabled": self.song_detector is not None,
            "shazam_instance_age_seconds": round(current_time - self._shazam_created_at, 1) if self._shazam_created_at > 0 else None,
            "shazam_use_count": self._shazam_use_count,
            "current_db": self.current_db,
            "peak_db": self.peak_db,
            "song_detection_stats": self.get_song_detection_stats()
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
        self.stop_monitoring()
        
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
