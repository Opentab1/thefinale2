"""
Pulse 1.0 - Microphone Audio Analysis
Song detection and decibel level monitoring
Integrated with party_box song detection for production-ready music recognition
"""

import logging
from threading import Thread, Event
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

        self.current_db = 0.0
        self.peak_db = 0.0
        self.current_song = None

        # Song detection state tracking
        self.song_detector = None
        self._song_detection_enabled = False
        self._shazam_class = None
        self._last_song_detect_attempt_ts = None
        self._last_song_detect_success_ts = None
        self._last_song_detect_duration = None
        self._last_song_detect_error = None
        self._last_song_detect_status = "idle"
        self._last_song_disabled_log_ts = 0.0

        # Watchdog tracking
        self._monitoring_thread = None
        self._last_activity = 0.0

        # Song detection + dB cadence configuration
        try:
            song_interval_env = float(os.getenv('SONG_DETECT_INTERVAL_SEC', '10'))
        except (TypeError, ValueError):
            song_interval_env = 10.0
        self._song_detect_interval = max(5.0, min(song_interval_env, 120.0))

        try:
            db_interval_env = float(os.getenv('DB_UPDATE_INTERVAL_SEC', '2.0'))
        except (TypeError, ValueError):
            db_interval_env = 2.0
        self._db_interval = max(0.5, min(db_interval_env, 10.0))

        self._last_db_ts = 0.0
        self._last_song_detect_ts = 0.0

        # Rolling audio buffer for song detection (5 seconds at 44100 Hz)
        # This allows song detection without opening a separate audio stream
        self._audio_buffer_size = int(5 * self.sample_rate)  # 5 seconds
        self._audio_buffer = np.zeros(self._audio_buffer_size, dtype=np.int16)
        self._buffer_index = 0

        # Initialize song detection pipeline (Shazam + compatibility layer)
        self._initialize_song_detection()

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
    
    def _initialize_song_detection(self):
        """Set up song detection helpers and availability flags."""
        disable_env = os.getenv('PULSE_DISABLE_SONG_DETECTION', '').strip().lower()
        disabled_markers = {'1', 'true', 'yes', 'on', 'disable', 'disabled'}
        detection_allowed = disable_env not in disabled_markers

        # Initialize legacy SongDetector wrapper if available for compatibility/logging
        if SongDetector is not None:
            try:
                self.song_detector = SongDetector(
                    enabled=False,
                    detection_interval=int(self._song_detect_interval)
                )
                logger.info("✅ Song detector compatibility layer initialized (shared audio buffer)")
            except Exception as e:
                logger.warning(f"Failed to initialize SongDetector wrapper: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                self.song_detector = None
        else:
            self.song_detector = None
            logger.warning("⚠️ Song detector wrapper unavailable (song_detector.py import failed)")

        if not detection_allowed:
            logger.info("Song detection disabled via PULSE_DISABLE_SONG_DETECTION environment flag")
            self._song_detection_enabled = False
            self._last_song_detect_status = "disabled"
            return

        try:
            from shazamio import Shazam

            self._shazam_class = Shazam
            self._song_detection_enabled = True
            self._last_song_detect_status = "idle"
            logger.info(
                "✅ ShazamIO library available - song detection enabled (interval %.1fs)",
                self._song_detect_interval
            )
        except ImportError:
            self._song_detection_enabled = False
            self._last_song_detect_status = "dependency_missing"
            logger.warning("⚠️ ShazamIO not available - song detection disabled")
            logger.warning("   Install with: pip install shazamio aiohttp")
        except Exception as e:
            self._song_detection_enabled = False
            self._last_song_detect_status = "error"
            logger.warning(f"Failed to initialize ShazamIO for song detection: {e}")

        if not self._song_detection_enabled:
            logger.info("Song detection disabled; continuing with dB monitoring only")

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
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        self._last_activity = time.time()
    
    def _watchdog_loop(self):
        """Watchdog to restart monitoring if it crashes"""
        while self.running and not self.stop_event.is_set():
            try:
                # Check if monitoring thread is alive
                if not self._monitoring_thread.is_alive():
                    logger.error("Audio monitoring thread died! Restarting...")
                    self._start_monitoring_thread()
                
                # Check if monitoring is stuck (no activity for 60 seconds)
                if time.time() - self._last_activity > 60:
                    logger.warning("Audio monitoring appears stuck (no activity for 60s)")
                    logger.warning("This is normal if no audio is detected, continuing...")
                    self._last_activity = time.time()  # Reset to prevent spam
                
                self.stop_event.wait(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in watchdog: {e}")
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
                    if pa_stream is not None:
                        audio_bytes = pa_stream.read(self.chunk_size, exception_on_overflow=False)
                        audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    elif sd_stream is not None:
                        audio_data, _ = sd_stream.read(self.chunk_size)  # type: ignore[union-attr]
                        if isinstance(audio_data, np.ndarray) and audio_data.ndim > 1:
                            audio_data = audio_data[:, 0]
                        audio_data = audio_data.astype(np.int16, copy=False)
                    else:
                        # No stream available - just check song detection and wait
                        if self.song_detector is not None:
                            song_info = self.song_detector.get_latest_song()
                            if song_info and song_info.get("title") != "Unknown":
                                self.current_song = song_info
                                logger.info(f"🎵 Song: {song_info['title']} - {song_info['artist']}")
                        self.stop_event.wait(5.0)
                        continue

                    if audio_data.size == 0:
                        continue
                    
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
                    
                    # Calculate dB level at configured cadence
                    now_db = time.time()
                    if (now_db - self._last_db_ts) >= self._db_interval:
                        db = self.calculate_db(audio_data)
                        self.current_db = db
                        self.peak_db = max(self.peak_db, db)
                        self._last_db_ts = now_db
                        self._last_activity = now_db  # Update watchdog
                        logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB)")

                    # Trigger song detection at configured interval using buffered audio
                    # Run in non-blocking way to prevent hanging
                    now_song = time.time()
                    if self._song_detection_enabled and (now_song - self._last_song_detect_ts) >= self._song_detect_interval:
                        if self._buffer_index >= self._audio_buffer_size:  # Buffer is full (5 seconds)
                            logger.info("🎵 Running song detection from audio buffer...")
                            # Run in separate thread to prevent blocking even if it hangs
                            try:
                                self._last_song_detect_attempt_ts = now_song
                                self._last_song_detect_status = "running"
                                self._detect_song_from_buffer()
                            except Exception as e:
                                logger.error(f"Failed to start song detection thread: {e}")
                                self._last_song_detect_status = "error"
                                self._last_song_detect_error = str(e)
                        else:
                            logger.debug(
                                "Audio buffer not ready for song detection (index: %d/%d)",
                                self._buffer_index,
                                self._audio_buffer_size
                            )
                        self._last_song_detect_ts = now_song
                        self._last_activity = now_song  # Update watchdog
                    elif not self._song_detection_enabled:
                        # Log occasionally if song detection is disabled so operators know why
                        if now_song - self._last_song_disabled_log_ts >= 60:
                            logger.debug(
                                "Song detection disabled (status: %s)",
                                self._last_song_detect_status
                            )
                            self._last_song_disabled_log_ts = now_song
                    
                    # CRITICAL: Always update last_activity even if no song detection
                    # This prevents watchdog from thinking we're stuck
                    self._last_activity = time.time()
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info("Audio monitoring stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
            self.running = False
        finally:
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
    
    def _detect_song_from_buffer(self):
        """Detect song using buffered audio data (runs in background thread with hard timeout)"""

        if not self._song_detection_enabled or self._shazam_class is None:
            logger.debug(
                "Song detection skipped (enabled=%s, shazam=%s)",
                self._song_detection_enabled,
                bool(self._shazam_class)
            )
            if not self._song_detection_enabled:
                self._last_song_detect_status = "disabled"
            else:
                self._last_song_detect_status = "dependency_missing"
                self._last_song_detect_error = "ShazamIO class not available"
            return

        import tempfile
        import wave
        import threading
        import signal
        import asyncio
        import platform

        def timeout_handler(signum, frame):
            raise TimeoutError("Song detection exceeded hard timeout")

        def detect_async():
            temp_filename = None
            local_status = "running"
            local_error = None
            local_result = None
            start_ts = time.time()
            self._last_song_detect_attempt_ts = start_ts
            self._last_song_detect_error = None
            try:
                # Save buffer to temporary WAV file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name

                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(self._audio_buffer.tobytes())

                logger.debug(f"Saved audio buffer to {temp_filename}")

                use_signal_timeout = platform.system() != 'Windows'

                try:
                    if use_signal_timeout:
                        # Set alarm for 25 seconds (hard kill)
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(25)

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        local_result, local_status, local_error = loop.run_until_complete(
                            asyncio.wait_for(
                                self._recognize_song_async(temp_filename),
                                timeout=20.0
                            )
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Song detection timed out (20s) - skipping")
                        local_result = None
                        local_status = "timeout"
                        local_error = "Song detection exceeded 20 second timeout"
                    finally:
                        try:
                            pending = asyncio.all_tasks(loop)
                            for task in pending:
                                task.cancel()
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception:
                            pass
                        loop.close()
                finally:
                    if use_signal_timeout:
                        signal.alarm(0)

                if local_status == "success" and local_result and 'track' in local_result:
                    track = local_result['track']
                    title = track.get('title', 'Unknown')
                    artist = track.get('subtitle', 'Unknown')

                    detected_ts = time.time()
                    confidence = None
                    try:
                        matches = local_result.get('matches') or []
                        if matches:
                            confidence = matches[0].get('score')
                    except Exception:
                        confidence = None

                    new_song = {
                        "title": title,
                        "artist": artist,
                        "timestamp": detected_ts,
                        "detected_at": datetime.fromtimestamp(detected_ts).isoformat(),
                        "confidence": float(confidence) if confidence is not None else 1.0,
                        "source": "shazam"
                    }

                    if self.current_song and self.current_song.get("title") == title and self.current_song.get("artist") == artist:
                        logger.debug(f"✅ Song confirmed: {title} - {artist}")
                    else:
                        logger.info(f"✅ Song detected: {title} - {artist}")

                    self.current_song = new_song
                    local_status = "match"
                    local_error = None
                else:
                    if local_status == "success":
                        local_status = "no_match"
                        local_error = None

                    if local_status == "no_match":
                        logger.debug("No song detected from buffer (Shazam returned no match)")
                        if local_result:
                            logger.debug(f"Shazam result keys: {list(local_result.keys())}")
                        else:
                            logger.debug("Shazam returned None (may be network issue or timeout)")

            except TimeoutError as e:
                local_status = "timeout"
                local_error = str(e)
                logger.error(f"Song detection hard timeout exceeded: {e}")
            except Exception as e:
                local_status = "error"
                local_error = f"{type(e).__name__}: {e}"
                logger.error(f"Error detecting song from buffer: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            finally:
                if temp_filename:
                    try:
                        import os
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)
                    except Exception as cleanup_error:
                        logger.debug(f"Failed to remove temp file: {cleanup_error}")

                duration = time.time() - start_ts
                self._last_song_detect_duration = duration

                if local_status == "match":
                    self._last_song_detect_success_ts = time.time()
                    if self.current_song is not None:
                        self.current_song["latency_sec"] = duration
                    self._last_song_detect_error = None
                else:
                    self._last_song_detect_error = local_error

                self._last_song_detect_status = local_status

        thread = threading.Thread(target=detect_async, daemon=True)
        thread.start()

        # Don't wait for thread - it runs independently

    async def _recognize_song_async(self, audio_file):
        """Recognize song using ShazamIO (async with timeout)"""
        import asyncio

        if self._shazam_class is None:
            return None, "dependency_missing", "ShazamIO class not initialized"

        try:
            shazam = self._shazam_class()
            result = await asyncio.wait_for(
                shazam.recognize(audio_file),
                timeout=15.0
            )
            return result, "success", None
        except asyncio.TimeoutError:
            logger.warning("Song recognition timed out after 15 seconds")
            return None, "timeout", "Song recognition timed out after 15 seconds"
        except ImportError as e:
            logger.error(f"ShazamIO not available: {e}")
            logger.error("Install with: pip install shazamio aiohttp")
            return None, "dependency_missing", str(e)
        except Exception as e:
            logger.error(f"Shazam recognition error: {type(e).__name__}: {e}")
            return None, "error", f"{type(e).__name__}: {e}"
    
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
        """Get currently detected song from party_box detector"""
        if self.current_song:
            song = dict(self.current_song)
            if song.get("detected_at") is None and song.get("timestamp"):
                try:
                    song["detected_at"] = datetime.fromtimestamp(song["timestamp"]).isoformat()
                except Exception:
                    song["detected_at"] = None
            song.setdefault("latency_sec", self._last_song_detect_duration)
            song.setdefault("source", "shazam" if self._song_detection_enabled else None)
            return song
        return {
            "title": "Unknown",
            "artist": "Unknown",
            "confidence": 0.0,
            "timestamp": None,
            "detected_at": None,
            "latency_sec": None,
            "source": None
        }
    
    def get_stats(self) -> dict:
        """Get all audio statistics"""
        def _to_iso(ts):
            if not ts:
                return None
            try:
                return datetime.fromtimestamp(ts).isoformat()
            except Exception:
                return None

        song_detection = {
            "enabled": self._song_detection_enabled,
            "interval_sec": self._song_detect_interval,
            "last_attempt_ts": self._last_song_detect_attempt_ts,
            "last_attempt_iso": _to_iso(self._last_song_detect_attempt_ts),
            "last_success_ts": self._last_song_detect_success_ts,
            "last_success_iso": _to_iso(self._last_song_detect_success_ts),
            "last_duration_sec": self._last_song_detect_duration,
            "last_status": self._last_song_detect_status,
            "last_error": self._last_song_detect_error,
            "backend": "shazam" if self._shazam_class is not None else None
        }

        return {
            "current_db": self.current_db,
            "peak_db": self.peak_db,
            "current_song": self.get_current_song(),
            "song_detection": song_detection,
            "timestamp": datetime.now().isoformat()
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_monitoring()
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
