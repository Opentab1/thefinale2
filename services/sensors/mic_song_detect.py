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
        self._restart_event = Event()

        self.current_db = 0.0
        self.peak_db = 0.0
        self.current_song = None
        
        # Watchdog tracking
        self._monitoring_thread = None
        self._last_activity = 0.0

        # Song detection configuration from environment (default: 30s)
        self._song_detect_interval = float(os.getenv('SONG_DETECT_INTERVAL_SEC', '30'))
        self._db_interval = float(os.getenv('DB_UPDATE_INTERVAL_SEC', '2.0'))
        self._last_db_ts = 0.0
        self._last_song_detect_ts = 0.0
        self._watchdog_timeout_sec = float(os.getenv('AUDIO_WATCHDOG_TIMEOUT_SEC', '90'))
        self._stale_song_timeout_sec = float(os.getenv('SONG_STALE_TIMEOUT_SEC', '300'))
        
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
        self._restart_event.clear()
        self._last_activity = time.time()
        
        # Start monitoring thread
        self._start_monitoring_thread()
        
        # Start watchdog thread to restart if monitoring crashes
        watchdog_thread = Thread(target=self._watchdog_loop, daemon=True)
        watchdog_thread.start()
        
        logger.info("Started audio monitoring with watchdog")
    
    def _start_monitoring_thread(self):
        """Start the monitoring thread"""
        self._restart_event.clear()
        self._monitoring_thread = Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        self._last_activity = time.time()

    def _request_restart(self):
        """Signal the monitoring thread to restart safely."""
        if not self.running or self.stop_event.is_set():
            return

        thread = self._monitoring_thread
        if thread is None:
            self._start_monitoring_thread()
            return

        if self._restart_event.is_set():
            logger.debug("Audio monitoring restart already in progress")
            return

        logger.info("Restarting audio monitoring thread")
        self._restart_event.set()

        thread.join(timeout=5.0)

        if thread.is_alive():
            logger.error("Audio monitoring thread did not stop cleanly; retrying later")
            self._restart_event.clear()
            return

        self._restart_event.clear()

        if self.running and not self.stop_event.is_set():
            self._start_monitoring_thread()
    
    def _watchdog_loop(self):
        """Watchdog to restart monitoring if it crashes"""
        while self.running and not self.stop_event.is_set():
            try:
                thread = self._monitoring_thread
                if thread is None or not thread.is_alive():
                    logger.error("Audio monitoring thread died! Restarting...")
                    self._start_monitoring_thread()
                    self.stop_event.wait(2)
                    continue

                inactive_for = time.time() - self._last_activity
                if inactive_for > self._watchdog_timeout_sec:
                    logger.warning(
                        "Audio monitoring inactive for %.1fs – restarting stream",
                        inactive_for
                    )
                    self._request_restart()
                    self._last_activity = time.time()
                
                self.stop_event.wait(10)
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
                if self._restart_event.is_set():
                    logger.debug("Audio monitoring restart requested; exiting loop")
                    break
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
                    
                    # Calculate dB level more frequently for better responsiveness (every 2 seconds)
                    now_db = time.time()
                    if (now_db - self._last_db_ts) >= 2.0:  # Update every 2 seconds
                        db = self.calculate_db(audio_data)
                        self.current_db = db
                        self.peak_db = max(self.peak_db, db)
                        self._last_db_ts = now_db
                        self._last_activity = now_db  # Update watchdog
                        logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB)")
                    
                    # Trigger song detection every 30 seconds using buffered audio
                    now_song = time.time()
                    if self.song_detector is not None and (now_song - self._last_song_detect_ts) >= self._song_detect_interval:
                        if self._buffer_index >= self._audio_buffer_size:  # Buffer is full (5 seconds)
                            logger.info("🎵 Running song detection from audio buffer...")
                            self._detect_song_from_buffer()
                        else:
                            logger.debug(f"Audio buffer not ready for song detection (index: {self._buffer_index}/{self._audio_buffer_size})")
                        self._last_song_detect_ts = now_song
                        self._last_activity = now_song  # Update watchdog
                    elif self.song_detector is None:
                        # Log occasionally if song detector is not available
                        if int(now_song) % 60 == 0:  # Log once per minute
                            logger.debug("Song detector not available - song detection disabled")

                    self._prune_stale_song(now_song)
                    
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

            # Mark thread as stopped so watchdog can spawn a new one
            self._monitoring_thread = None

    def _prune_stale_song(self, now_ts: float):
        """Clear current song if we haven't refreshed it recently."""
        if not self.current_song:
            return

        song_ts = self._to_epoch(self.current_song.get("timestamp"))
        if song_ts is None:
            return

        if now_ts - song_ts > self._stale_song_timeout_sec:
            elapsed = now_ts - song_ts
            logger.debug("Song detection stale for %.1fs – clearing current song", elapsed)
            self.current_song = None
    
    def _detect_song_from_buffer(self):
        """Detect song using buffered audio data (runs in background thread)"""
        import tempfile
        import wave
        import threading
        
        def detect_async():
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
                
                # Process the audio file with ShazamIO (with overall timeout)
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Add 20 second overall timeout for entire song detection
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            self._recognize_song_async(temp_filename),
                            timeout=20.0
                        )
                    )
                except asyncio.TimeoutError:
                    logger.warning("Song detection timed out (20s) - skipping")
                    result = None
                finally:
                    loop.close()
                
                # Process result
                if result and 'track' in result:
                    track = result['track']
                    title = track.get('title', 'Unknown')
                    artist = track.get('subtitle', 'Unknown')
                    
                    new_song = {
                        "title": title,
                        "artist": artist,
                        "timestamp": time.time(),
                        "confidence": 1.0
                    }
                    
                    # Only log if it's a new song
                    if not self.current_song or self.current_song.get("title") != title:
                        logger.info(f"✅ Song detected: {title} - {artist}")
                    
                    self.current_song = new_song
                else:
                    logger.debug("No song detected from buffer (Shazam returned no match)")
                    # Log reason if available
                    if result:
                        logger.debug(f"Shazam result: {list(result.keys())}")
                    else:
                        logger.debug("Shazam returned None (may be network issue or timeout)")
                
                # Clean up temp file
                try:
                    import os
                    os.remove(temp_filename)
                except Exception:
                    pass
                    
            except Exception as e:
                logger.error(f"Error detecting song from buffer: {e}")
        
        # Run in background thread to not block audio monitoring
        thread = threading.Thread(target=detect_async, daemon=True)
        thread.start()
    
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
        self._restart_event.set()

        thread = self._monitoring_thread
        if thread is not None and thread.is_alive():
            try:
                thread.join(timeout=5.0)
            except Exception:
                pass
    
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
        now = time.time()
        self._prune_stale_song(now)

        if self.current_song:
            return self.current_song
        return {
            "title": "Unknown",
            "artist": "Unknown",
            "confidence": 0.0,
            "timestamp": None
        }

    def _to_epoch(self, value):
        """Convert timestamps to epoch seconds for stale detection."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            try:
                return float(value)
            except Exception:
                return None

        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                try:
                    return datetime.fromisoformat(value).timestamp()
                except ValueError:
                    return None

        return None
    
    def get_stats(self) -> dict:
        """Get all audio statistics"""
        return {
            "current_db": self.current_db,
            "peak_db": self.peak_db,
            "current_song": self.get_current_song(),
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
