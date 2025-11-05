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

# Try to import sound-related libraries
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice library not available. Install with 'pip install sounddevice'")

# Try to import ShazamIO with detailed error handling
try:
    from shazamio import Shazam
    SHAZAMIO_AVAILABLE = True
except ImportError as e:
    SHAZAMIO_AVAILABLE = False
    error_msg = str(e)
    
    # Python 3.13+ specific error: audioop removed from stdlib
    if "audioop" in error_msg or "pyaudioop" in error_msg:
        logging.warning("ShazamIO requires audioop (removed in Python 3.13+)")
        logging.warning("Install with: pip3 install --break-system-packages audioop-lts shazamio")
    else:
        logging.warning(f"ShazamIO library not available: {error_msg}")
        logging.warning("Install with: pip3 install --break-system-packages shazamio aiohttp")

class SongDetector:
    """Class for handling background song detection using ShazamIO"""
    def __init__(self, enabled=True, detection_interval=60, use_buffer_mode=False):
        """
        Initialize the song detector
        
        Args:
            enabled: Whether song detection is enabled
            detection_interval: Seconds between detection attempts (only used in auto-record mode)
            use_buffer_mode: If True, detection loop won't auto-record but will wait for external buffer calls
        """
        self.enabled = enabled and SHAZAMIO_AVAILABLE
        self.use_buffer_mode = use_buffer_mode
        
        if self.enabled:
            if self.use_buffer_mode:
                logging.info("Song detection enabled (buffer mode - external buffer calls)")
            else:
                logging.info("Song detection enabled (auto-record mode)")
        else:
            if not SHAZAMIO_AVAILABLE:
                logging.warning("ShazamIO not available. Song detection disabled.")
            if not self.use_buffer_mode and not SOUNDDEVICE_AVAILABLE:
                logging.warning("sounddevice not available. Song detection disabled.")
        
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
        
        # CRITICAL FIX: Watchdog for thread health monitoring - IMMEDIATE RECOVERY
        self.watchdog_thread = None
        self.watchdog_active = False
        self.watchdog_interval = 2.0  # CRITICAL: Check every 2 seconds for immediate failure detection
        self.last_heartbeat = time.time()
        self.thread_restart_count = 0
        self.max_restarts_per_hour = 1000  # CRITICAL: Allow unlimited restarts - we MUST recover
        
        # CRITICAL FIX: Reusable event loop to prevent resource leaks
        self._event_loop = None
        self._event_loop_thread = None
        self._event_loop_lock = threading.Lock()
        self._shazam_instance = None
        self._shazam_created_at = 0.0
        self._shazam_refresh_interval = 3600.0  # Refresh every hour
        
        # Start detection thread if enabled
        if self.enabled:
            try:
                # CRITICAL FIX: Create event loop proactively so it's ready when needed
                # This is especially important in buffer mode where detection happens on-demand
                if not self._ensure_event_loop():
                    logging.error("⚠️ Failed to create event loop during initialization")
                    # Don't disable entirely - will retry when detection is attempted
                
                self.start_detection_thread()
                self._start_watchdog()
                # CRITICAL FIX: Verify threads started successfully
                if self.detection_thread is None or not self.detection_thread.is_alive():
                    logging.error("⚠️ Failed to start detection thread - will retry via watchdog")
                if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
                    logging.error("⚠️ Failed to start watchdog thread - attempting restart")
                    self._start_watchdog()
            except Exception as e:
                logging.error(f"⚠️ Error starting song detector threads: {e}")
                import traceback
                logging.debug(traceback.format_exc())
                # Will be retried by watchdog if it starts
                try:
                    self._start_watchdog()
                except Exception:
                    logging.error("⚠️ CRITICAL: Failed to start watchdog thread")

    def start_detection_thread(self):
        """Start background thread for song detection"""
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_active = True
            self.last_heartbeat = time.time()  # Reset heartbeat
            self.detection_thread = threading.Thread(target=self._detection_loop, name="SongDetectorLoop")
            self.detection_thread.daemon = True
            self.detection_thread.start()
            logging.info("Song detection thread started")
    
    def _start_watchdog(self):
        """Start watchdog thread to monitor and restart detection thread if it dies"""
        if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
            self.watchdog_active = True
            self.watchdog_thread = threading.Thread(target=self._watchdog_loop, name="SongDetectorWatchdog")
            self.watchdog_thread.daemon = True
            self.watchdog_thread.start()
            # CRITICAL FIX: Wait a moment and verify thread started
            time.sleep(0.1)
            if self.watchdog_thread.is_alive():
                logging.info("✅ Song detector watchdog started")
            else:
                logging.error("⚠️ Watchdog thread failed to start")
                self.watchdog_thread = None
    
    def _watchdog_loop(self):
        """Watchdog loop to monitor thread health and restart IMMEDIATELY if needed"""
        while self.watchdog_active and self.enabled:
            try:
                time.sleep(self.watchdog_interval)  # Check every 2 seconds
                
                # CRITICAL: Check if detection thread is alive - IMMEDIATE RESTART
                if self.detection_thread is None or not self.detection_thread.is_alive():
                    logging.error("🚨 CRITICAL: Song detection thread died! Restarting IMMEDIATELY...")
                    self.thread_restart_count += 1
                    
                    # CRITICAL: NO RATE LIMITING - We MUST recover immediately
                    # Restart the thread immediately
                    try:
                        self.start_detection_thread()
                        logging.info("✅ Song detection thread restarted successfully")
                    except Exception as restart_error:
                        logging.error(f"❌ Failed to restart detection thread: {restart_error}")
                        # Try again on next watchdog cycle
                
                # CRITICAL: Check heartbeat - detect stalls IMMEDIATELY (reduced threshold)
                heartbeat_age = time.time() - self.last_heartbeat
                # CRITICAL: Reduced from 2x interval + 30s to just 10s for immediate detection
                if heartbeat_age > 10.0:  # Thread stuck if no heartbeat for 10 seconds
                    logging.warning(f"🚨 CRITICAL: Song detection thread heartbeat stale ({heartbeat_age:.1f}s). Thread stuck - FORCING IMMEDIATE RESTART!")
                    # Force restart immediately
                    self.detection_active = False
                    if self.detection_thread and self.detection_thread.is_alive():
                        try:
                            self.detection_thread.join(timeout=1.0)  # Shorter timeout
                        except Exception:
                            pass
                    try:
                        self.start_detection_thread()
                        logging.info("✅ Song detection thread restarted after stall")
                    except Exception as restart_error:
                        logging.error(f"❌ Failed to restart detection thread after stall: {restart_error}")
                    
            except Exception as e:
                logging.error(f"❌ CRITICAL ERROR in song detector watchdog: {e}")
                import traceback
                logging.error(traceback.format_exc())
                # Don't wait full interval on error - check again quickly
                time.sleep(1.0)
    
    def _detection_loop(self):
        """Background thread for periodic song detection - BULLETPROOF ERROR HANDLING"""
        logging.info("Song detection loop started")
        
        # Initialize last detection time to now to prevent immediate first detection
        # This gives the AudioMonitor time to open its dB monitoring stream first
        self.last_detection_time = time.time()
        
        consecutive_errors = 0
        max_consecutive_errors = 10  # After 10 errors, force restart
        
        while self.detection_active:
            try:
                # CRITICAL: Update heartbeat (required for watchdog) - MUST happen every iteration
                try:
                    self.last_heartbeat = time.time()
                except Exception as heartbeat_error:
                    logging.error(f"CRITICAL: Failed to update heartbeat: {heartbeat_error}")
                    # Continue anyway - watchdog will catch it
                
                if self.use_buffer_mode:
                    # In buffer mode, we just maintain heartbeat for watchdog
                    # External code will call detect_song_from_buffer() when needed
                    time.sleep(2)  # Reduced from 5s to 2s for faster heartbeat
                else:
                    # Auto-record mode: Check if it's time for a new detection
                    try:
                        current_time = time.time()
                        if current_time - self.last_detection_time >= self.detection_interval:
                            logging.info("Starting song recognition...")
                            try:
                                self.detect_song()
                            except Exception as detect_error:
                                logging.error(f"Error in detect_song(): {detect_error}")
                                # Continue - don't crash the loop
                            self.last_detection_time = current_time
                    except Exception as time_error:
                        logging.error(f"Error checking detection time: {time_error}")
                    
                    # Sleep to avoid consuming CPU
                    time.sleep(2)  # Reduced from 5s to 2s
                
                # Reset error counter on successful iteration
                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                logging.error(f"❌ CRITICAL ERROR in detection loop (error #{consecutive_errors}): {e}")
                import traceback
                logging.error(traceback.format_exc())
                
                # If too many consecutive errors, force restart by breaking loop
                # (watchdog will restart the thread)
                if consecutive_errors >= max_consecutive_errors:
                    logging.error(f"🚨 CRITICAL: Too many consecutive errors ({consecutive_errors}). Exiting loop for watchdog restart.")
                    break
                
                time.sleep(1)  # Brief pause before retry
    
    def detect_song(self):
        """Record audio and detect song (only works in auto-record mode)"""
        if not self.enabled:
            return
        if self.use_buffer_mode:
            logging.warning("detect_song() called but detector is in buffer mode. Use detect_song_from_buffer() instead.")
            return
            
        try:
            # Create temporary file for the recording
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Record audio
            logging.info(f"Recording {self.duration}s audio clip for song detection...")
            recording = sd.rec(
                int(self.duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16'
            )
            sd.wait()  # Wait for recording to complete
            
            # Save to WAV file
            with wave.open(temp_filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)  # 16-bit audio
                wf.setframerate(self.sample_rate)
                wf.writeframes(recording.tobytes())
            
            logging.info(f"Audio saved to {temp_filename}")
            
            # Process in a separate thread
            processing_thread = threading.Thread(
                target=self._process_audio_file,
                args=(temp_filename,),
                daemon=True
            )
            processing_thread.start()
            
        except Exception as e:
            logging.error(f"Error recording audio: {e}")
    
    def detect_song_from_buffer(self, audio_buffer, sample_rate=44100):
        """
        Detect song from pre-recorded audio buffer - BULLETPROOF ERROR HANDLING
        
        Args:
            audio_buffer: numpy array of audio data (int16)
            sample_rate: Sample rate of the audio (default: 44100)
        
        Returns:
            bool: True if detection was started successfully
        """
        if not self.enabled:
            logging.debug("Song detection disabled - skipping")
            return False
        
        try:
            import numpy as np
            
            # CRITICAL: Validate inputs
            if audio_buffer is None:
                logging.debug("Audio buffer is None - skipping detection")
                return False
            
            # Ensure buffer is numpy array
            try:
                if not isinstance(audio_buffer, np.ndarray):
                    audio_buffer = np.array(audio_buffer, dtype=np.int16)
            except Exception as array_error:
                logging.error(f"Failed to convert buffer to numpy array: {array_error}")
                return False
            
            # CRITICAL FIX: Check if buffer has actual audio data (not all zeros)
            try:
                buffer_sum = np.sum(np.abs(audio_buffer))
                if buffer_sum == 0:
                    logging.debug("Audio buffer is empty (all zeros) - skipping detection")
                    return False
            except Exception as sum_error:
                logging.error(f"Error checking buffer sum: {sum_error}")
                return False
            
            # CRITICAL FIX: Ensure event loop exists before attempting detection
            try:
                if not self._ensure_event_loop():
                    logging.error("⚠️ Event loop unavailable - cannot process audio")
                    return False
            except Exception as loop_error:
                logging.error(f"Error ensuring event loop: {loop_error}")
                return False
            
            # Create temporary file for the recording
            temp_filename = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name
            except Exception as temp_error:
                logging.error(f"Failed to create temp file: {temp_error}")
                return False
            
            # Save to WAV file
            try:
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_buffer.tobytes())
            except Exception as wave_error:
                logging.error(f"Failed to write WAV file: {wave_error}")
                # Clean up temp file
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
                return False
            
            logging.debug(f"Audio buffer saved to {temp_filename} for song detection (buffer sum: {buffer_sum})")
            
            # Process in a separate thread
            try:
                processing_thread = threading.Thread(
                    target=self._process_audio_file,
                    args=(temp_filename,),
                    daemon=True
                )
                processing_thread.start()
                return True
            except Exception as thread_error:
                logging.error(f"Failed to start processing thread: {thread_error}")
                # Clean up temp file
                try:
                    os.remove(temp_filename)
                except Exception:
                    pass
                return False
            
        except Exception as e:
            logging.error(f"❌ CRITICAL ERROR detecting song from buffer: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def _ensure_event_loop(self):
        """Ensure we have a working event loop for async operations"""
        with self._event_loop_lock:
            if self._event_loop is None or self._event_loop.is_closed():
                if self._event_loop_thread and self._event_loop_thread.is_alive():
                    # Loop closed but thread still alive - wait for it to finish
                    self._event_loop_thread.join(timeout=2.0)
                
                # Create new event loop in dedicated thread
                loop_ready = threading.Event()
                loop = None
                
                def _loop_runner():
                    nonlocal loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop_ready.set()
                    loop.run_forever()
                
                thread = threading.Thread(target=_loop_runner, name="SongDetectorEventLoop", daemon=True)
                thread.start()
                
                if loop_ready.wait(timeout=5.0):
                    self._event_loop = loop
                    self._event_loop_thread = thread
                    logging.info("Song detector event loop created")
                else:
                    logging.error("Failed to create event loop within timeout")
                    return False
            
            return True
    
    def _process_audio_file(self, audio_file):
        """Process audio file with ShazamIO"""
        try:
            # CRITICAL FIX: Use reusable event loop instead of creating new one each time
            if not self._ensure_event_loop():
                logging.error("Cannot process audio - event loop unavailable")
                return
            
            # Schedule recognition on the event loop
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self._recognize_song(audio_file),
                self._event_loop
            )
            
            # Wait for result with timeout
            try:
                result = future.result(timeout=15.0)
            except concurrent.futures.TimeoutError:
                logging.warning("⚠️ Song recognition timed out after 15s")
                future.cancel()
                result = None
            except Exception as e:
                logging.error(f"Error waiting for recognition result: {e}")
                result = None
            
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
                
                logging.info(f"Song detected: {title} by {artist}")
            else:
                logging.debug("No song detected")
            
            # Clean up temporary file
            try:
                os.remove(audio_file)
            except Exception as e:
                logging.warning(f"Error removing temporary file: {e}")
                
        except Exception as e:
            logging.error(f"Error processing audio: {e}")
            import traceback
            logging.debug(traceback.format_exc())
    
    async def _recognize_song(self, audio_file):
        """Recognize song using ShazamIO (async)"""
        try:
            # CRITICAL FIX: Use reusable Shazam instance to prevent resource leaks
            current_time = time.time()
            needs_refresh = (
                self._shazam_instance is None or
                (current_time - self._shazam_created_at) > self._shazam_refresh_interval
            )
            
            if needs_refresh:
                # Close old instance if it exists
                if self._shazam_instance is not None:
                    try:
                        client = getattr(self._shazam_instance, 'client', None)
                        if client and hasattr(client, 'close'):
                            await asyncio.wait_for(client.close(), timeout=2.0)
                    except Exception as e:
                        logging.debug(f"Error closing old Shazam instance: {e}")
                
                # Create new instance
                self._shazam_instance = Shazam()
                self._shazam_created_at = current_time
            
            shazam = self._shazam_instance
            
            # CRITICAL FIX: Add timeout to prevent hanging
            result = await asyncio.wait_for(
                shazam.recognize(audio_file),
                timeout=10.0
            )
            return result
        except asyncio.TimeoutError:
            logging.warning("⚠️ Shazam recognition timed out after 10s")
            # Reset instance on timeout
            self._shazam_instance = None
            self._shazam_created_at = 0.0
            return None
        except Exception as e:
            logging.error(f"Shazam recognition error: {e}")
            # Reset instance on error
            self._shazam_instance = None
            self._shazam_created_at = 0.0
            return None
    
    def get_latest_song(self):
        """Get the latest detected song information"""
        with self.lock:
            return self.latest_song.copy()
    
    def stop(self):
        """Stop song detection thread"""
        self.detection_active = False
        self.watchdog_active = False
        
        # Stop detection thread
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
            logging.info("Song detection thread stopped")
        
        # Stop watchdog
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=2.0)
            logging.info("Song detector watchdog stopped")
        
        # Clean up event loop
        with self._event_loop_lock:
            if self._event_loop and not self._event_loop.is_closed():
                try:
                    self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                except Exception:
                    pass
                if self._event_loop_thread:
                    self._event_loop_thread.join(timeout=2.0)
                try:
                    self._event_loop.close()
                except Exception:
                    pass
                self._event_loop = None
                self._event_loop_thread = None
        
        # Clean up Shazam instance
        if self._shazam_instance:
            try:
                # Try to close client if possible
                client = getattr(self._shazam_instance, 'client', None)
                if client and hasattr(client, 'close'):
                    # Create temporary loop for cleanup
                    cleanup_loop = asyncio.new_event_loop()
                    try:
                        cleanup_loop.run_until_complete(
                            asyncio.wait_for(client.close(), timeout=2.0)
                        )
                    except Exception:
                        pass
                    finally:
                        cleanup_loop.close()
            except Exception:
                pass
            self._shazam_instance = None
        
        logging.info("Song detector stopped and cleaned up")