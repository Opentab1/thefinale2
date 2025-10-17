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
import io
import time
import requests
import hmac
import hashlib
import base64

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
        self._last_song_detect_ts = 0.0
        self._song_detect_interval = float(os.getenv('SONG_DETECT_INTERVAL_SEC', '10'))
        self._song_detect_provider = os.getenv('SONG_DETECT_PROVIDER', 'shazam').strip().lower()
        self._audd_api_token = os.getenv('AUDD_API_TOKEN', '').strip()
        self._acr_host = os.getenv('ACR_HOST', '').strip()
        self._acr_key = os.getenv('ACR_ACCESS_KEY', '').strip()
        self._acr_secret = os.getenv('ACR_ACCESS_SECRET', '').strip()
        
        # Audio interface
        self.audio = pyaudio.PyAudio()
        self._validate_device()
    
    def _validate_device(self):
        """Validate and pick the best audio input device automatically.

        Preference order:
        1) ALSA default reported by sounddevice
        2) PyAudio device whose name contains any of: 'USB', 'Mic', 'PnP', 'Microphone'
        3) First PyAudio device with input channels > 0
        """
        try:
            # 1) ALSA default via sounddevice
            if self.device_index is None:
                try:
                    sd_default = sd.default.device
                    if isinstance(sd_default, (list, tuple)):
                        sd_in = sd_default[0]
                    else:
                        sd_in = sd_default
                    if sd_in is not None and int(sd_in) >= 0:
                        self.device_index = int(sd_in)
                        logger.info(f"Using sounddevice default input index: {self.device_index}")
                except Exception as e:
                    logger.debug(f"sounddevice default selection failed: {e}")

            # 2) PyAudio search by name
            preferred_substrings = ["USB", "Mic", "PnP", "Microphone"]
            chosen_by_name = None
            device_count = self.audio.get_device_count()
            for i in range(device_count):
                try:
                    di = self.audio.get_device_info_by_index(i)
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

            # 3) First available input device
            if self.device_index is None:
                for i in range(device_count):
                    try:
                        di = self.audio.get_device_info_by_index(i)
                    except Exception:
                        continue
                    if di.get('maxInputChannels', 0) > 0:
                        self.device_index = i
                        logger.info(f"Using first available input device: {di.get('name')} (index {i})")
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
        """Detect song from audio data via configured provider."""
        try:
            if self._song_detect_provider == 'shazam':
                return self._detect_song_shazam(audio_data)
            if self._song_detect_provider == 'audd' and self._audd_api_token:
                return self._detect_song_audd(audio_data)
            if self._song_detect_provider == 'acrcloud' and self._acr_host and self._acr_key and self._acr_secret:
                return self._detect_song_acrcloud(audio_data)
            # TODO: add 'acrcloud' support when credentials are provided
        except Exception as e:
            logger.error(f"Song detection failed: {e}")
        return {"detected": False, "title": None, "artist": None, "confidence": 0.0}

    def _detect_song_shazam(self, audio_data: np.ndarray) -> dict:
        """Detect song using ShazamIO (no key required)."""
        try:
            from shazamio import Shazam
            # Write WAV to temp file (ShazamIO expects a path)
            with io.BytesIO() as buf:
                with wave.open(buf, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(audio_data.tobytes())
                wav_bytes = buf.getvalue()

            import tempfile, os as _os
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
                tf.write(wav_bytes)
                tmp_path = tf.name

            try:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(Shazam().recognize(tmp_path))
                loop.close()
            finally:
                try:
                    _os.remove(tmp_path)
                except Exception:
                    pass

            if result and 'track' in result:
                track = result['track']
                title = track.get('title')
                artist = track.get('subtitle')
                if title or artist:
                    return { 'detected': True, 'title': title, 'artist': artist, 'confidence': 1.0 }
        except Exception as e:
            logger.error(f"Shazam detection failed: {e}")
        return { 'detected': False, 'title': None, 'artist': None, 'confidence': 0.0 }

    def _detect_song_acrcloud(self, audio_data: np.ndarray) -> dict:
        """Detect song using ACRCloud identify API."""
        endpoint = f"/v1/identify"
        url = f"http://{self._acr_host}{endpoint}"
        http_method = "POST"
        data_type = "audio"
        signature_version = "1"
        timestamp = str(int(time.time()))

        # Prepare sample bytes as WAV
        with io.BytesIO() as buf:
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            sample_bytes = buf.getvalue()

        string_to_sign = "\n".join([http_method, endpoint, self._acr_key, data_type, signature_version, timestamp])
        sign = base64.b64encode(hmac.new(self._acr_secret.encode('utf-8'), string_to_sign.encode('utf-8'), digestmod=hashlib.sha1).digest()).decode('utf-8')

        files = {
            'sample': ('sample.wav', sample_bytes, 'audio/wav')
        }
        data = {
            'access_key': self._acr_key,
            'data_type': data_type,
            'signature_version': signature_version,
            'signature': sign,
            'timestamp': timestamp,
        }
        resp = requests.post(url, data=data, files=files, timeout=15)
        js = resp.json()
        if js.get('status', {}).get('code') == 0 and js.get('metadata', {}).get('music'):
            m = js['metadata']['music'][0]
            title = m.get('title')
            artist = None
            if isinstance(m.get('artists'), list) and m['artists']:
                artist = m['artists'][0].get('name')
            return { 'detected': True, 'title': title, 'artist': artist, 'confidence': 1.0 }
        return { 'detected': False, 'title': None, 'artist': None, 'confidence': 0.0 }

    def _detect_song_audd(self, audio_data: np.ndarray) -> dict:
        """Detect song using AudD API by sending ~10 seconds of audio."""
        # Encode PCM int16 numpy array to WAV bytes in-memory
        with io.BytesIO() as buf:
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            wav_bytes = buf.getvalue()

        files = { 'file': ('audio.wav', wav_bytes, 'audio/wav') }
        data = { 'api_token': self._audd_api_token, 'return': 'timecode,deezer,apple_music,spotify' }
        resp = requests.post('https://api.audd.io/', data=data, files=files, timeout=15)
        js = resp.json()
        if js.get('status') == 'success' and js.get('result'):
            r = js['result']
            title = r.get('title')
            artist = r.get('artist')
            confidence = float(r.get('score') or 1.0)
            return { 'detected': True, 'title': title, 'artist': artist, 'confidence': confidence }
        return { 'detected': False, 'title': None, 'artist': None, 'confidence': 0.0 }
    
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
            
            # Buffer for song detection (collect ~10 seconds)
            song_buffer = []
            buffer_duration = max(10, int(self._song_detect_interval))
            buffer_chunks = int(buffer_duration * self.sample_rate / self.chunk_size)
            
            while self.running and not self.stop_event.is_set():
                try:
                    # Read audio data
                    audio_bytes = stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                    if audio_data.size == 0:
                        continue
                    
                    # Calculate dB level
                    db = self.calculate_db(audio_data)
                    self.current_db = db
                    self.peak_db = max(self.peak_db, db)
                    
                    # Add to song detection buffer
                    song_buffer.append(audio_data)
                    if len(song_buffer) > buffer_chunks:
                        song_buffer.pop(0)
                    
                    # Attempt song detection every configured interval
                    now = time.time()
                    if (now - self._last_song_detect_ts) >= self._song_detect_interval:
                        # Keep last N seconds of audio; concatenate and detect
                        if len(song_buffer) > buffer_chunks:
                            song_buffer = song_buffer[-buffer_chunks:]
                        combined_audio = np.concatenate(song_buffer) if song_buffer else np.zeros(self.chunk_size, dtype=np.int16)
                        if combined_audio.size >= self.sample_rate * 3:  # at least 3 seconds
                            song_info = self.detect_song(combined_audio)
                            if song_info.get("detected"):
                                self.current_song = {
                                    "title": song_info.get("title"),
                                    "artist": song_info.get("artist"),
                                    "confidence": song_info.get("confidence", 0.0),
                                    "timestamp": datetime.now().isoformat()
                                }
                                logger.info(f"Detected song: {self.current_song['title']} - {self.current_song['artist']}")
                            self._last_song_detect_ts = now
                        combined_audio = np.concatenate(song_buffer)
                        song_info = self.detect_song(combined_audio)
                        if song_info.get("detected"):
                            self.current_song = {
                                "title": song_info.get("title"),
                                "artist": song_info.get("artist"),
                                "confidence": song_info.get("confidence", 0.0),
                                "timestamp": datetime.now().isoformat()
                            }
                            logger.info(f"Detected song: {self.current_song['title']} - {self.current_song['artist']}")
                        self._last_song_detect_ts = now
                    
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
