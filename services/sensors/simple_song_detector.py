#!/usr/bin/env python3
"""
simple_song_detector.py - Crash-proof song detection using RapidAPI Shazam Core

Based on proven Nov 5th architecture with critical fixes:
- Uses arecord instead of sounddevice (bypasses PortAudio SIGABRT bug)
- RapidAPI Shazam Core for unlimited detection
- No rate limits with paid tier
- Stable 24/7 operation without crashes

This approach provides unlimited, reliable, CRASH-FREE song detection.
"""

import time
import logging
import threading
import asyncio
import wave
import tempfile
import os
import subprocess

# Check if arecord is available (always should be on Linux)
ARECORD_AVAILABLE = True
try:
    subprocess.run(['which', 'arecord'], capture_output=True, check=True)
except (subprocess.CalledProcessError, FileNotFoundError):
    ARECORD_AVAILABLE = False
    logging.warning("arecord not available. Install alsa-utils package.")

# Try to import requests for RapidAPI
try:
    import requests
    RAPIDAPI_AVAILABLE = True
    RAPIDAPI_KEY = "de528fdc31mshb7f88b1b939f9b7p1db4cejsn1e64b438f142"
except ImportError:
    RAPIDAPI_AVAILABLE = False
    RAPIDAPI_KEY = None
    logging.warning("requests library not available. Install with 'pip install requests'")

logger = logging.getLogger(__name__)

class SongDetector:
    """Simple, reliable song detector using RapidAPI Shazam Core"""
    
    def __init__(self, enabled=True, detection_interval=60):
        """
        Initialize the song detector
        
        Args:
            enabled: Whether song detection is enabled
            detection_interval: Seconds between detection attempts (default: 60)
        """
        self.enabled = enabled and ARECORD_AVAILABLE and RAPIDAPI_AVAILABLE
        
        if self.enabled:
            logger.info("✅ Song detection enabled (detection interval: %ds)", detection_interval)
        else:
            if not RAPIDAPI_AVAILABLE:
                logger.warning("⚠️ RapidAPI not available. Song detection disabled.")
            if not ARECORD_AVAILABLE:
                logger.warning("⚠️ arecord not available. Song detection disabled.")
        
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
            
            # Record audio using arecord (bypasses PortAudio bug)
            logger.debug(f"Recording {self.duration}s audio clip for song detection...")
            
            try:
                # Use arecord to record directly to WAV file
                # plughw:2,0 = USB mic (card 2: SF-558)
                result = subprocess.run([
                    'arecord',
                    '-D', 'plughw:2,0',  # USB microphone
                    '-f', 'S16_LE',      # 16-bit signed little-endian
                    '-c', '1',            # Mono (1 channel)
                    '-r', '44100',        # 44.1kHz sample rate
                    '-d', str(self.duration),  # Duration in seconds
                    temp_filename         # Output file
                ], capture_output=True, timeout=self.duration + 2)
                
                if result.returncode != 0:
                    logger.error(f"arecord failed: {result.stderr.decode()}")
                    return
                
                logger.debug(f"Audio saved to {temp_filename}")
                
            except subprocess.TimeoutExpired:
                logger.error(f"arecord timed out after {self.duration + 2}s")
                return
            except Exception as e:
                logger.error(f"Error recording audio: {e}")
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
        Process audio file with RapidAPI Shazam Core
        
        KEY APPROACH:
        - Simple HTTP POST to RapidAPI
        - No async complexity
        - Official Shazam database
        - No rate limits (paid tier)
        """
        try:
            # Call RapidAPI (simple HTTP, no async/event loop needed)
            result = self._recognize_song(audio_file)
            
            # Log what we received for debugging
            if result:
                logger.debug(f"🔍 API response type: {type(result)}, has track: {'track' in result if isinstance(result, dict) else False}")
            
            # Process result - check track exists AND is not None
            if result and isinstance(result, dict) and 'track' in result and result['track']:
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
                # No song found - this is normal, not an error
                logger.debug("🎵 No song detected (no match in database)")
            
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
    
    def _recognize_song(self, audio_file):
        """
        Recognize song using RapidAPI Shazam Core
        
        API Documentation: https://rapidapi.com/tipsters/api/shazam-core
        File format: {'file': (filename, file_object, 'audio/wav')}
        Optimal: 2-4 seconds, 500-1500 KB, max 2 MB
        """
        try:
            url = "https://shazam-core.p.rapidapi.com/v1/tracks/recognize"
            
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "shazam-core.p.rapidapi.com"
            }
            
            # Open file and format exactly as API docs specify
            filename = os.path.basename(audio_file)
            with open(audio_file, 'rb') as f:
                # Format: {'file': (filename, file_object, mime_type)}
                files = {'file': (filename, f, 'audio/wav')}
                
                # POST request with 15 second timeout
                response = requests.post(url, files=files, headers=headers, timeout=15.0)
            
            # Check response status
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"✅ RapidAPI Success: {response.status_code}")
                return result
            else:
                logger.warning(f"⚠️ RapidAPI returned status {response.status_code}")
                logger.debug(f"Response: {response.text[:200]}")
                return None
            
        except requests.Timeout:
            logger.warning("⚠️ RapidAPI recognition timed out after 15s")
            return None
            
        except requests.RequestException as e:
            logger.error(f"RapidAPI request error: {e}")
            return None
            
        except Exception as e:
            logger.error(f"RapidAPI recognition error: {e}")
            logger.exception(e)
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
