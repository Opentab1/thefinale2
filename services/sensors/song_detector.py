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
                # CRITICAL: Even if ShazamIO is unavailable, we should still start watchdog
                # so it can restart when ShazamIO becomes available later
                if enabled:  # User wanted it enabled
                    logging.info("Watchdog will start in degraded mode (will monitor for ShazamIO availability)")
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
        
        # CRITICAL FIX: Watchdog for thread health monitoring
        self.watchdog_thread = None
        self.watchdog_active = False
        self.watchdog_interval = 3.0  # CRITICAL: Check every 3 seconds for immediate recovery
        self.last_heartbeat = time.time()
        self.thread_restart_count = 0
        self.max_restarts_per_hour = 100  # Allow many restarts - better than crashing
        self._last_restart_time = 0.0
        
        # CRITICAL FIX: Reusable event loop to prevent resource leaks
        self._event_loop = None
        self._event_loop_thread = None
        self._event_loop_lock = threading.Lock()
        self._shazam_instance = None
        self._shazam_created_at = 0.0
        self._shazam_refresh_interval = 3600.0  # Refresh every hour
        
        # Start detection thread if enabled OR if user wanted it enabled (degraded mode)
        # CRITICAL: Start watchdog even in degraded mode so it can restart when dependencies become available
        if self.enabled or enabled:
            try:
                # CRITICAL FIX: Create event loop proactively so it's ready when needed
                # This is especially important in buffer mode where detection happens on-demand
                if not self._ensure_event_loop():
                    logging.error("⚠️ Failed to create event loop during initialization")
                    # Don't disable entirely - will retry when detection is attempted
                
                # Only start detection thread if actually enabled (ShazamIO available)
                if self.enabled:
                    self.start_detection_thread()
                
                # ALWAYS start watchdog if user requested it (even in degraded mode)
                # This ensures recovery when dependencies become available
                self._start_watchdog()
                
                # CRITICAL FIX: Verify threads started successfully
                if self.enabled:
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
        """Watchdog loop to monitor thread health and restart if needed - CRITICAL: Must never fail"""
        consecutive_errors = 0
        # CRITICAL: Watchdog should ALWAYS run if watchdog_active is True
        # It monitors thread health and can restart when dependencies become available
        # CRITICAL FIX: Check if thread is None OR dead (not just None)
        while self.watchdog_active:
            try:
                time.sleep(self.watchdog_interval)
                consecutive_errors = 0  # Reset on successful check
                
                # CRITICAL: Check if detection thread is alive - IMMEDIATE RESTART if dead
                # Check if we should have a detection thread (enabled) and if it's dead or missing
                if self.enabled:
                    # We should have a detection thread - check if it's alive
                    if self.detection_thread is None or not self.detection_thread.is_alive():
                        logging.error("🚨 CRITICAL: Song detection thread died! Restarting IMMEDIATELY...")
                        self.thread_restart_count += 1
                        
                        # CRITICAL: Only rate limit if we're restarting too frequently (more than once per second)
                        now = time.time()
                        time_since_last_restart = now - self._last_restart_time if self._last_restart_time > 0 else float('inf')
                        if time_since_last_restart < 1.0:
                            # Restarting too fast - wait a bit
                            time.sleep(0.5)
                        
                        # Update restart time AFTER the check
                        self._last_restart_time = time.time()
                        
                        # ALWAYS restart - no matter what
                        try:
                            self.start_detection_thread()
                            logging.info("✅ Song detection thread restarted successfully")
                        except Exception as restart_error:
                            logging.error(f"❌ Failed to restart detection thread: {restart_error}")
                            # Try again next cycle
                            continue
                    else:
                        # Thread exists and is alive - check heartbeat
                        # CRITICAL: Check heartbeat - detect stuck threads IMMEDIATELY
                        heartbeat_age = time.time() - self.last_heartbeat
                        # In buffer mode, heartbeat should update every 5 seconds
                        # In auto-record mode, heartbeat should update every detection_interval
                        max_heartbeat_age = max(15.0, self.detection_interval * 2) if not self.use_buffer_mode else 15.0
                        
                        if heartbeat_age > max_heartbeat_age:
                            logging.warning(f"🚨 CRITICAL: Song detection thread heartbeat stale ({heartbeat_age:.1f}s > {max_heartbeat_age}s). Thread may be stuck. FORCING RESTART!")
                            # Force restart immediately
                            self.detection_active = False
                            if self.detection_thread and self.detection_thread.is_alive():
                                try:
                                    self.detection_thread.join(timeout=1.0)  # Shorter timeout
                                except Exception:
                                    pass
                            try:
                                self.start_detection_thread()
                                logging.info("✅ Song detection thread restarted after heartbeat timeout")
                            except Exception as restart_error:
                                logging.error(f"❌ Failed to restart after heartbeat timeout: {restart_error}")
                else:
                    # In degraded mode (ShazamIO unavailable), check if ShazamIO became available
                    # CRITICAL FIX: Also check if we have a dead thread that needs cleanup
                    if self.detection_thread is not None and not self.detection_thread.is_alive():
                        # Thread exists but is dead - clean it up
                        logging.debug("Cleaning up dead detection thread in degraded mode")
                        self.detection_thread = None
                    
                    # Check if ShazamIO became available
                    if SHAZAMIO_AVAILABLE:
                        logging.info("ShazamIO became available! Enabling detection...")
                        self.enabled = True
                        try:
                            self.start_detection_thread()
                            logging.info("✅ Detection thread started after ShazamIO became available")
                        except Exception as e:
                            logging.error(f"Failed to start detection thread after ShazamIO became available: {e}")
                            # Reset enabled flag if we can't start
                            self.enabled = False
                    
            except Exception as e:
                consecutive_errors += 1
                logging.error(f"🚨 CRITICAL ERROR in song detector watchdog (consecutive: {consecutive_errors}): {e}")
                import traceback
                logging.error(traceback.format_exc())
                # If watchdog itself is failing, try to restart everything
                if consecutive_errors >= 5:
                    logging.error("🚨 CRITICAL: Watchdog has failed 5 times. Attempting emergency restart...")
                    try:
                        # Try to restart watchdog
                        self.watchdog_active = False
                        time.sleep(1)
                        self._start_watchdog()
                        consecutive_errors = 0
                    except Exception:
                        logging.error("🚨 CRITICAL: Failed to restart watchdog. System may be unstable.")
                time.sleep(self.watchdog_interval)
    
    def _detection_loop(self):
        """Background thread for periodic song detection - CRITICAL: Must never crash"""
        logging.info("✅ Song detection loop started")
        consecutive_errors = 0
        
        # Initialize last detection time to now to prevent immediate first detection
        # This gives the AudioMonitor time to open its dB monitoring stream first
        self.last_detection_time = time.time()
        
        while self.detection_active:
            try:
                # CRITICAL: Update heartbeat FIRST - watchdog depends on this
                self.last_heartbeat = time.time()
                consecutive_errors = 0  # Reset error counter on successful iteration
                
                if self.use_buffer_mode:
                    # In buffer mode, we just maintain heartbeat for watchdog
                    # External code will call detect_song_from_buffer() when needed
                    time.sleep(5)
                else:
                    # Auto-record mode: Check if it's time for a new detection
                    current_time = time.time()
                    if current_time - self.last_detection_time >= self.detection_interval:
                        logging.info("Starting song recognition...")
                        try:
                            self.detect_song()
                            self.last_detection_time = current_time
                        except Exception as detect_error:
                            logging.error(f"Error during song detection: {detect_error}")
                            # Continue anyway - don't crash the loop
                            self.last_detection_time = current_time
                    
                    # Sleep to avoid consuming CPU
                    time.sleep(5)
            except KeyboardInterrupt:
                # Allow graceful shutdown
                logging.info("Song detection loop interrupted")
                break
            except Exception as e:
                consecutive_errors += 1
                logging.error(f"🚨 CRITICAL ERROR in detection loop (consecutive: {consecutive_errors}): {e}")
                import traceback
                logging.error(traceback.format_exc())
                
                # CRITICAL: Don't let errors crash the loop - always continue
                # If we have too many consecutive errors, log warning but keep going
                if consecutive_errors >= 10:
                    logging.error("🚨 CRITICAL: Detection loop has had 10 consecutive errors but continuing...")
                    consecutive_errors = 0  # Reset to prevent log spam
                
                time.sleep(5)  # Continue even after errors
        
        logging.warning("Song detection loop exited (should not happen unless stopped)")
    
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
        Detect song from pre-recorded audio buffer - CRITICAL: Must never crash
        
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
            
            # Ensure buffer is numpy array
            if not isinstance(audio_buffer, np.ndarray):
                audio_buffer = np.array(audio_buffer, dtype=np.int16)
            
            # CRITICAL FIX: Check if buffer has actual audio data (not all zeros)
            buffer_sum = np.sum(np.abs(audio_buffer))
            if buffer_sum == 0:
                logging.debug("Audio buffer is empty (all zeros) - skipping detection")
                return False
            
            # CRITICAL FIX: Ensure event loop exists before attempting detection
            # Retry up to 3 times if event loop creation fails
            for attempt in range(3):
                if self._ensure_event_loop():
                    break
                if attempt < 2:
                    logging.warning(f"⚠️ Event loop unavailable (attempt {attempt+1}/3), retrying...")
                    time.sleep(0.5)
                else:
                    logging.error("⚠️ Event loop unavailable after 3 attempts - cannot process audio")
                    return False
            
            # Create temporary file for the recording
            temp_filename = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name
                
                # Save to WAV file
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_buffer.tobytes())
                
                logging.debug(f"Audio buffer saved to {temp_filename} for song detection (buffer sum: {buffer_sum})")
                
                # Process in a separate thread
                processing_thread = threading.Thread(
                    target=self._process_audio_file,
                    args=(temp_filename,),
                    daemon=True,
                    name="SongDetectionProcessing"
                )
                processing_thread.start()
                
                return True
            except Exception as file_error:
                logging.error(f"Error creating temp file for song detection: {file_error}")
                # Clean up temp file if it was created
                if temp_filename and os.path.exists(temp_filename):
                    try:
                        os.remove(temp_filename)
                    except Exception:
                        pass
                return False
            
        except Exception as e:
            logging.error(f"🚨 CRITICAL: Error detecting song from buffer: {e}")
            import traceback
            logging.error(traceback.format_exc())
            # Don't crash - return False and let caller handle it
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
        if self.detection_thread:
            try:
                if hasattr(self.detection_thread, 'is_alive') and self.detection_thread.is_alive():
                    self.detection_thread.join(timeout=2.0)
                    logging.info("Song detection thread stopped")
            except Exception as e:
                logging.debug(f"Error stopping detection thread: {e}")
        
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