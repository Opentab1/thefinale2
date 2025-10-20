#!/usr/bin/env python3
"""
song_detector.py - Background song detection using ShazamIO

This module provides song detection functionality that:
1. Records audio in the background
2. Identifies songs playing using Shazam's API
3. Provides current song information to the main application
"""

import time
import logging
import threading
import asyncio
import wave
import tempfile
import os

"""Background song detection with graceful fallbacks.

On systems without PortAudio/sounddevice, we keep the class loadable and simply
disable detection while logging a concise reason. This prevents crashes during
startup and keeps the rest of the system functional.
"""

# Try to import sound-related libraries
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception as e:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning(f"sounddevice unavailable: {e}. Song detection disabled.")

# Try to import ShazamIO
try:
    from shazamio import Shazam
    SHAZAMIO_AVAILABLE = True
except Exception as e:
    SHAZAMIO_AVAILABLE = False
    logging.warning(f"ShazamIO unavailable: {e}. Song detection disabled.")

class SongDetector:
    """Class for handling background song detection using ShazamIO"""
    def __init__(self, enabled=True, detection_interval=60):
        """
        Initialize the song detector
        
        Args:
            enabled: Whether song detection is enabled
            detection_interval        self.enabled = bool(enabled) and SOUNDDEVICE_AVAILABLE and SHAZAMIO_AVAILABLE
        
        if self.enabled:
            logging.info("🎵 Song detection enabled")
            logging.info(f"  - Detection interval: {detection_interval} seconds")
            logging.info(f"  - Using ShazamIO for recognition")
        else:
            reasons = []
            if not SHAZAMIO_AVAILABLE:
                reasons.append("ShazamIO not installed (pip install shazamio)")
            if not SOUNDDEVICE_AVAILABLE:
                reasons.append("sounddevice not installed (pip install sounddevice)")
            if not enabled:
                reasons.append("disabled by config")
            logging.warning("🎵 Song detection disabled: " + ", ".join(reasons) if reasons else "unknown reason")
            logging.warning("Song detector will return 'Unknown' for all queries") " + ", ".join(reasons) if reasons else "disabled by config")
        
        # Audio parameters
        self.sample_rate = 44100
        self.channels = 1
        self.duration = 5  # seconds to record
        
        # Song detection state
        self.latest_song = {"title": "Unknown", "artist": "Unknown", "timestamp": None}
        self.detection_thread = None
        self.detection_active = False
        self.last_detection_time = 0
        self.detection_interval = detection_interval
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Start detection thread if enabled
        if self.enabled:
            self.start_detection_thread()

    def start_detection_thread(self):
        """Start background thread for song detection"""
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_active = True
            self.detection_thread = threading.Thread(target=self._detection_loop)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            logging.info("Song detection thread started")
    
    def _detection_loop(self):
        """Background thread for periodic song detection"""
        logging.info("Song detection loop started")
        
        while self.detection_active:
            # Check if it's time for a new detection
            current_time = time.time()
            if current_time - self.last_detection_time >= self.detection_interval:
                logging.info("Starting song recognition...")
                self.detect_song()
                self.last_detection_time =    def detect_song(self):
        """Record audio and detect song"""
        if not self.enabled:
            logging.debug("Song detection skipped (disabled)")
            return
            
        try:
            # Create temporary file for the recording
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Record audio
            logging.info(f"🎤 Recording {self.duration}s audio clip for song detection...")
            recording = sd.rec(
                int(self.duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16'
            )
            sd.wait()  # Wait for recording to complete
            
            # Check if we actually recorded something
            import numpy as np
            max_val = np.max(np.abs(recording))
            logging.info(f"  Recording complete (max amplitude: {max_val})")
            
            if max_val < 100:  # Very quiet
                logging.warning("  ⚠ Recording is very quiet - mic might not be working")
            
            # Save to WAV file
            with wave.open(temp_filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit audio
                wf.setframerate(self.sample_rate)
                wf.writeframes(recording.tobytes())
            
            logging.info(f"  Audio saved to {temp_filename}")
            
            # Process in a separate thread
            processing_thread = threading.Thread(
                target=self._process_audio_file,
                args=(temp_filename,),
                daemon=True
            )
            processing_thread.start()
            
        except Exception as e:
            logging.error(f"Error recording audio for song detection: {e}")
            import traceback
            logging.error(traceback.format_exc()) )
            processing_thread.start()
            
        except Exception as e:
            logging.error(f"Error recording audio: {e}")
    
    def _process_audio_file(self, audio_file):
        """Process audio file with ShazamIO"""
        try:
            # Create event loop for async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run Shazam recognition
              # Process result
            if result and 'track' in result:
                track = result['track']
                title = track.get('title', 'Unknown')
                artist = track.get('subtitle', 'Unknown')
                
                with self.lock:
                    self.latest_song = {
                        "title": title,
                        "artist": artist,
                        "timestamp": time.time(),
                        "confidence": 1.0  # Shazam doesn't provide confidence, assume high if matched
                    }
                
                logging.info(f"✅ Song detected: {title} by {artist}")
            else:
                logging.info("❌ No song detected (silence or unrecognized)")
                with self.lock:
                    self.latest_song = {
                        "title": "Unknown",
                        "artist": "Unknown", 
                        "timestamp": time.time(),
                        "confidence": 0.0
                    }             logging.info(f"Song detected: {title} by {artist}")
            else:
                logging.info("No song detected")
            
            # Clean up temporary file
            try:
                os.remove(audio_file)
            except Exception as e:
                logging.warning(f"Error removing temporary file: {e}")
                
        except Exception as e:
            logging.error(f"Error processing audio: {e}")
    
    async def _recognize_song(self, audio_file):
        """Recognize song using ShazamIO (async)"""
        try:
            shazam = Shazam()
            result = await shazam.recognize(audio_file)
            return result
        except Exception as e:
            logging.error(f"Shazam recognition error: {e}")
            return None
    
    def get_latest_song(self):
        """Get the latest detected song information"""
        with self.lock:
            return self.latest_song.copy()
    
    def stop(self):
        """Stop song detection thread"""
        self.detection_active = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
            logging.info("Song detection thread stopped")