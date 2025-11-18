#!/usr/bin/env python3
"""
crash_proof_song_detector.py - Crash-proof song detection using subprocess isolation

Fixes the shazamio "double free or corruption" crash by running Shazam
in a completely separate subprocess. When Shazam crashes, only the
subprocess dies, not the main service.

Based on party_box approach with added crash protection.
"""

import time
import logging
import threading
import wave
import tempfile
import os
import subprocess
import json
from pathlib import Path

import shutil

# Check if arecord is available (bypass sounddevice/PortAudio)
ARECORD_AVAILABLE = shutil.which('arecord') is not None

logger = logging.getLogger(__name__)

class SongDetector:
    """Crash-proof song detector using subprocess isolation"""
    
    def __init__(self, enabled=True, detection_interval=60):
        """
        Initialize the song detector
        
        Args:
            enabled: Whether song detection is enabled
            detection_interval: Seconds between detection attempts (default: 60)
        """
        self.enabled = enabled and ARECORD_AVAILABLE
        
        if self.enabled:
            logger.info("✅ Song detection enabled (detection interval: %ds, arecord mode)", detection_interval)
        else:
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
                    logger.info("🎵 Starting song recognition (crash-proof subprocess)...")
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
            
            # Record audio using arecord (bypasses PortAudio completely)
            logger.debug(f"Recording {self.duration}s audio clip with arecord...")
            
            try:
                # Use arecord command to record audio directly
                cmd = [
                    'arecord',
                    '-D', 'default',  # Use default device
                    '-f', 'S16_LE',   # 16-bit signed little-endian
                    '-r', str(self.sample_rate),  # Sample rate
                    '-c', str(self.channels),     # Mono
                    '-d', str(self.duration),     # Duration in seconds
                    temp_filename
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.duration + 2
                )
                
                if result.returncode != 0:
                    logger.error(f"arecord failed: {result.stderr}")
                    return
                
                logger.debug(f"Audio recorded to {temp_filename}")
                
            except Exception as e:
                logger.error(f"Error recording audio with arecord: {e}")
                return
            
            # Process in subprocess (crash isolation!)
            self._process_audio_file_subprocess(temp_filename)
            
        except Exception as e:
            logger.error(f"Error in detect_song: {e}")
    
    def _process_audio_file_subprocess(self, audio_file):
        """
        Process audio file in isolated subprocess
        
        KEY APPROACH: Run Shazam in separate process so crashes don't kill main service
        """
        try:
            # Create a Python script to run in subprocess
            script = f"""
import asyncio
import json
import sys

try:
    from shazamio import Shazam
    
    async def recognize():
        shazam = Shazam()
        result = await asyncio.wait_for(shazam.recognize('{audio_file}'), timeout=15.0)
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(recognize())
    loop.close()
    
    if result and 'track' in result:
        track = result['track']
        output = {{
            'success': True,
            'title': track.get('title', 'Unknown'),
            'artist': track.get('subtitle', 'Unknown')
        }}
    else:
        output = {{'success': False}}
    
    print(json.dumps(output))
    
except Exception as e:
    output = {{'success': False, 'error': str(e)}}
    print(json.dumps(output))
"""
            
            # Run in subprocess with timeout
            logger.debug("Running Shazam in isolated subprocess...")
            result = subprocess.run(
                ['python3', '-c', script],
                capture_output=True,
                text=True,
                timeout=20,  # 20 second timeout
                cwd='/opt/pulse'
            )
            
            # Parse result
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout.strip())
                    if data.get('success'):
                        with self.lock:
                            self.latest_song = {
                                "title": data.get('title', 'Unknown'),
                                "artist": data.get('artist', 'Unknown'),
                                "timestamp": time.time()
                            }
                        logger.info(f"🎵 Song detected: {data['title']} by {data['artist']}")
                    else:
                        logger.debug("🎵 No song detected")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Shazam result: {e}")
            else:
                # Subprocess crashed or failed
                if result.returncode != 0:
                    logger.warning(f"⚠️ Shazam subprocess crashed (exit code: {result.returncode}) - service continues running")
                else:
                    logger.debug("🎵 No song detected")
            
            # Clean up temporary file
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except Exception as e:
                logger.warning(f"Error removing temporary file: {e}")
                
        except subprocess.TimeoutExpired:
            logger.warning("⚠️ Shazam subprocess timed out - skipping this detection")
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error in subprocess song detection: {e}")
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            except:
                pass
    
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
    
    logger.info("Starting crash-proof song detector test")
    
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
