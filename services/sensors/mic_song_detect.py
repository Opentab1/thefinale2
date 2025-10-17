"""
Pulse 1.0 - Microphone Audio Analysis
Song detection and decibel level monitoring
"""

import logging
import pyaudio
import sounddevice as sd
import numpy as np
from threading import Thread, Event
from datetime import datetime
import wave
import os
import tempfile

logger = logging.getLogger(__name__)

class AudioMonitor:
    def __init__(self, device_index: int = None, sample_rate: int = 44100, chunk_size: int = 2048):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.running = False
        self.stop_event = Event()
        
        self.current_db = 0.0
        self.peak_db = 0.0
        self.current_song = None
        
        # Audio interface
        self.audio = pyaudio.PyAudio()
        self._validate_device()
    
    def _validate_device(self):
        """Validate audio device availability"""
        try:
            if self.device_index is None:
                # Prefer ALSA default first via sounddevice
                try:
                    sd_default = sd.default.device
                    if isinstance(sd_default, (list, tuple)) and sd_default[0] is not None:
                        self.device_index = int(sd_default[0])
                        logger.info(f"Using sounddevice default input index: {self.device_index}")
                except Exception:
                    pass

            if self.device_index is None:
                # Discover first PyAudio input device
                device_count = self.audio.get_device_count()
                for i in range(device_count):
                    device_info = self.audio.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        self.device_index = i
                        logger.info(f"Using audio device: {device_info.get('name')}")
                        break

            if self.device_index is None:
                raise Exception("No input audio device found")
            
        except Exception as e:
            logger.error(f"Audio device validation failed: {e}")
            raise
    
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
    
    def detect_song(self, audio_data: np.ndarray) -> dict:
        """
        Detect song from audio data
        In production, this would use ACRCloud, Shazam API, or similar
        """
        # Placeholder for song detection
        # Would integrate with:
        # - ACRCloud API
        # - Shazam API
        # - AudD API
        # - Local audio fingerprinting
        
        return {
            "detected": False,
            "title": None,
            "artist": None,
            "confidence": 0.0
        }
    
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
        """Main monitoring loop"""
        stream = None
        
        try:
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size
            )
            
            logger.info("Audio stream opened")
            
            # Buffer for song detection (collect ~5 seconds)
            song_buffer = []
            buffer_duration = 5  # seconds
            buffer_chunks = int(buffer_duration * self.sample_rate / self.chunk_size)
            
            while self.running and not self.stop_event.is_set():
                try:
                    # Read audio data
                    audio_bytes = stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    
                    # Calculate dB level
                    db = self.calculate_db(audio_data)
                    self.current_db = db
                    self.peak_db = max(self.peak_db, db)
                    
                    # Add to song detection buffer
                    song_buffer.append(audio_data)
                    if len(song_buffer) > buffer_chunks:
                        song_buffer.pop(0)
                    
                    # Attempt song detection every N chunks
                    if len(song_buffer) >= buffer_chunks:
                        combined_audio = np.concatenate(song_buffer)
                        song_info = self.detect_song(combined_audio)
                        
                        if song_info["detected"]:
                            self.current_song = {
                                "title": song_info["title"],
                                "artist": song_info["artist"],
                                "confidence": song_info["confidence"],
                                "timestamp": datetime.now().isoformat()
                            }
                            logger.info(f"Detected song: {song_info['title']} - {song_info['artist']}")
                        
                        # Clear buffer after detection attempt
                        song_buffer = []
                    
                    # Analyze spectrum
                    spectrum = self.analyze_audio_spectrum(audio_data)
                    
                    logger.debug(f"dB: {db:.1f}, Peak: {self.peak_db:.1f}")
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
            
            logger.info("Audio monitoring stopped")
            
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
            self.running = False
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
    
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
        """Get currently detected song"""
        return self.current_song if self.current_song else {
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
        if self.audio:
            self.audio.terminate()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    monitor = AudioMonitor()
    
    try:
        monitor.start_monitoring()
        
        import time
        while True:
            time.sleep(2)
            stats = monitor.get_stats()
            print(f"dB: {stats['current_db']:.1f} (peak: {stats['peak_db']:.1f})")
            if stats['current_song']['title'] != "Unknown":
                print(f"Song: {stats['current_song']['title']} - {stats['current_song']['artist']}")
    except KeyboardInterrupt:
        print("\nStopping...")
        monitor.cleanup()
