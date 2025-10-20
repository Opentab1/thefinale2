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

        # Song detection configuration from environment (default: 30s)
        self._song_detect_interval = float(os.getenv('SONG_DETECT_INTERVAL_SEC', '30'))
        self._db_interval = float(os.getenv('DB_UPDATE_INTERVAL_SEC', '2.0'))
        self._last_db_ts = 0.0

        # Initialize song detector if available
        if SongDetector is not None:
            try:
                self.song_detector = SongDetector(
                    enabled=True,
                    detection_interval=int(self._song_detect_interval)
                )
                logger.info("Initialized song detector from party_box")
            except Exception as e:
                logger.warning(f"Failed to initialize song detector: {e}")
                self.song_detector = None
        else:
            self.song_detector = None
            logger.info("Song detector disabled (dependencies missing)")

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
        """Start audio monitoring"""
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        thread = Thread(target=self._monitoring_loop)
        thread.daemon = True
        thread.start()
        
        logger.info("Started audio monitoring")
    
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
                    
                    # Calculate dB level more frequently for better responsiveness (every 2 seconds)
                    now_db = time.time()
                    if (now_db - self._last_db_ts) >= 2.0:  # Update every 2 seconds
                        db = self.calculate_db(audio_data)
                        self.current_db = db
                        self.peak_db = max(self.peak_db, db)
                        self._last_db_ts = now_db
                        logger.info(f"🔊 Audio: {db:.1f} dB (Peak: {self.peak_db:.1f} dB)")
                    
                    # Get song detection results from background detector
                    if self.song_detector is not None:
                        song_info = self.song_detector.get_latest_song()
                        if song_info and song_info.get("title") != "Unknown":
                            if not self.current_song or self.current_song.get("title") != song_info.get("title"):
                                # New song detected!
                                logger.info(f"🎵 Song detected: {song_info['title']} - {song_info['artist']}")
                            self.current_song = song_info
                    
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
    
    def stop_monitoring(self):
        """Stop audio monitoring"""
        self.running = False
        self.stop_event.set()
        
        # Stop song detector
        try:
            self.song_detector.stop()
        except Exception as e:
            logger.warning(f"Error stopping song detector: {e}")
    
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
            return self.current_song
        return {
            "title": "Unknown",
            "artist": "Unknown",
            "confidence": 0.0,
            "timestamp": None
        }
    
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
