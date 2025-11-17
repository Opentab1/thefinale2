#!/usr/bin/env python3
"""
simple_song_detector.py - Simple, reliable song detection using ShazamIO

Based on proven party_box approach:
- Fresh event loop created for EACH Shazam API call
- Event loop closed immediately after use
- No long-lived event loops (prevents staleness)
- Simple daemon thread (no complex watchdogs)

This approach is proven to run indefinitely on Raspberry Pi without failures.
"""

import time
import logging
import threading
import asyncio
import wave
import tempfile
import os

# Try to import sound-related libraries
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice library not available. Install with 'pip install sounddevice'")

# Try to import ShazamIO
try:
    from shazamio import Shazam
    SHAZAMIO_AVAILABLE = True
except ImportError:
    SHAZAMIO_AVAILABLE = False
    logging.warning("ShazamIO library not available. Install with 'pip install shazamio'")

logger = logging.getLogger(__name__)

class SongDetector:
    """Simple, reliable song detector using ShazamIO with fresh event loops"""
    
    def __init__(self, enabled=True, detection_interval=60):
        """
        Initialize the song detector
        
        Args:
            enabled: Whether song detection is enabled
            detection_interval: Seconds between detection attempts (default: 60)
        """
        self.enabled = enabled and SOUNDDEVICE_AVAILABLE and SHAZAMIO_AVAILABLE
        
        if self.enabled:
            logger.info("✅ Song detection enabled (detection interval: %ds)", detection_interval)
        else:
            if not SHAZAMIO_AVAILABLE:
                logger.warning("⚠️ ShazamIO not available. Song detection disabled.")
            if not SOUNDDEVICE_AVAILABLE:
                logger.warning("⚠️ sounddevice not available. Song detection disabled.")
        
        # Audio parameters
        self.sample_rate = 44100
        self.channels = 1
        self.duration = 5  # 5 seconds of audio for Shazam
        
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
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                name="SongDetector",
                daemon=True
            )
            self.detection_thread.start()
            logger.info("✅ Song detection thread started")
    
    def _detection_loop(self):
        """Background thread for periodic song detection"""
        logger.info("🎵 Song detection loop started")
        
        while self.detection_active:
            try:
                # Check if it's time for a new detection
                current_time = time.time()
                if current_time - self.last_detection_time >= self.detection_interval:
                    logger.info("🎵 Starting song recognition...")
                    self.detect_song()
                    self.last_detection_time = current_time
                
                # Sleep to avoid consuming CPU
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in song detection loop: {e}")
                time.sleep(10)  # Wait longer on error
    
    def detect_song(self):
        """Record audio and detect song"""
        if not self.enabled:
            return
            
        try:
            # Create temporary file for the recording
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Record audio
            logger.debug(f"Recording {self.duration}s audio clip for song detection...")
            
            try:
                recording = sd.rec(
                    int(self.duration * self.sample_rate),
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='int16'
                )
                sd.wait()  # Wait for recording to complete
                
            except Exception as e:
                logger.error(f"Error recording audio: {e}")
                return
            
            # Save to WAV file
            try:
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(recording.tobytes())
                
                logger.debug(f"Audio saved to {temp_filename}")
                
            except Exception as e:
                logger.error(f"Error saving audio file: {e}")
                return
            
            # Process in a separate thread to avoid blocking
            processing_thread = threading.Thread(
                target=self._process_audio_file,
                args=(temp_filename,),
                daemon=True
            )
            processing_thread.start()
            
        except Exception as e:
            logger.error(f"Error in detect_song: {e}")
    
    def _process_audio_file(self, audio_file):
        """
        Process audio file with ShazamIO
        
        KEY APPROACH (from party_box):
        - Create FRESH event loop for this operation
        - Run recognition
        - Close loop immediately
        - No long-lived loops = no staleness
        """
        try:
            # ✅ CREATE FRESH EVENT LOOP (party_box proven approach)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run Shazam recognition
            result = loop.run_until_complete(self._recognize_song(audio_file))
            
            # ✅ CLOSE LOOP IMMEDIATELY (prevents staleness)
            loop.close()
            
            # Process result
            if result and 'track' in result:
                track = result['track']
                title = track.get('title', 'Unknown')
                artist = track.get('subtitle', 'Unknown')
                
                with self.lock:
                    self.latest_song = {
                        "title": title,
                        "artist": artist,
                        "timestamp": time.time()
                    }
                
                logger.info(f"🎵 Song detected: {title} by {artist}")
            else:
                logger.debug("🎵 No song detected")
            
            # Clean up temporary file
            try:
                os.remove(audio_file)
            except Exception as e:
                logger.warning(f"Error removing temporary file: {e}")
                
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            # Clean up on error
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
    
    async def _recognize_song(self, audio_file):
        """
        Recognize song using ShazamIO (async)
        
        Creates fresh Shazam instance for each call (no reuse)
        """
        try:
            # Fresh Shazam instance for this call
            shazam = Shazam()
            
            # Add timeout to prevent hanging
            result = await asyncio.wait_for(
                shazam.recognize(audio_file),
                timeout=15.0
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning("⚠️ Shazam recognition timed out after 15s")
            return None
            
        except Exception as e:
            logger.error(f"Shazam recognition error: {e}")
            return None
    
    def get_latest_song(self):
        """Get the latest detected song information"""
        with self.lock:
            return self.latest_song.copy()
    
    def get_current_song(self):
        """Get current song (for backward compatibility)"""
        return self.get_latest_song()
    
    def stop(self):
        """Stop song detection thread"""
        logger.info("Stopping song detector...")
        self.detection_active = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=3.0)
            if self.detection_thread.is_alive():
                logger.warning("Song detection thread did not stop gracefully")
            else:
                logger.info("✅ Song detection thread stopped")


# Module test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting song detector test")
    
    # Create detector
    detector = SongDetector(
        enabled=True,
        detection_interval=60
    )
    
    try:
        # Run for a few minutes and print detected songs
        logger.info("Running test for 3 minutes...")
        logger.info("Play some music to test detection...")
        
        for i in range(18):  # 3 minutes / 10 seconds
            time.sleep(10)
            song = detector.get_latest_song()
            if song['title'] != 'Unknown':
                logger.info(f"🎵 Latest song: {song['title']} by {song['artist']}")
            else:
                logger.info("🎵 No song detected yet")
    
    except KeyboardInterrupt:
        logger.info("Test interrupted")
    finally:
        detector.stop()
        logger.info("Test complete")
