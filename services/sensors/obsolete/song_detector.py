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
        
        # CRITICAL FIX: Thread ID to prevent race conditions
        # Each thread instance gets a unique ID so old threads can identify themselves
        self._detection_thread_id = 0
        self._detection_thread_id_lock = threading.Lock()
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # CRITICAL FIX: Watchdog for thread health monitoring
        self.watchdog_thread = None
        self.watchdog_active = False
        self.watchdog_interval = 5.0  # Check every 5 seconds (ULTRA AGGRESSIVE)
        self.last_heartbeat = time.time()
        self.thread_restart_count = 0
        self.max_restarts_per_hour = 20  # Allow more restarts (was 10)
        self.restart_count_reset_time = time.time()  # CRITICAL FIX: Track when to reset counter
        
        # CRITICAL FIX: Watchdog thread ID to prevent race conditions
        self._watchdog_thread_id = 0
        self._watchdog_thread_id_lock = threading.Lock()
        
        # CRITICAL FIX: Reusable event loop to prevent resource leaks
        self._event_loop = None
        self._event_loop_thread = None
        self._event_loop_lock = threading.Lock()
        self._shazam_instance = None
        self._shazam_created_at = 0.0
        self._shazam_refresh_interval = 3600.0  # Refresh every hour
        
        # CRITICAL: Circuit breaker for external API failures
        self._api_failure_count = 0
        self._api_last_failure_time = 0
        self._api_circuit_open = False
        self._api_circuit_reset_time = 300  # Reset circuit after 5 minutes
        self._api_max_failures_before_open = 3  # Open circuit after 3 consecutive failures
        
        # Start detection thread if enabled
        if self.enabled:
            # CRITICAL FIX: Don't fail initialization if event loop creation fails
            # It will be created on-demand when needed
            try:
                logging.info("Creating event loop for song detection...")
                if not self._ensure_event_loop():
                    logging.warning("⚠️ Event loop creation failed during init - will retry on first detection")
                else:
                    logging.info("✓ Event loop created successfully")
            except Exception as e:
                logging.warning(f"Event loop creation error (will retry later): {e}")
            
            # Start threads - these should not fail initialization even if event loop fails
            try:
                self.start_detection_thread()
                self._start_watchdog()
                
                # Verify threads started (but don't fail init if they didn't)
                if self.detection_thread is None or not self.detection_thread.is_alive():
                    logging.error("⚠️ Detection thread failed to start - watchdog will retry")
                if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
                    logging.error("⚠️ Watchdog failed to start - attempting one more time")
                    try:
                        self._start_watchdog()
                    except Exception as retry_err:
                        logging.error(f"Watchdog restart failed: {retry_err}")
            except Exception as e:
                logging.error(f"⚠️ Error starting song detector threads: {e}")
                import traceback
                logging.debug(traceback.format_exc())
                # Try to at least start watchdog so it can recover
                try:
                    if self.watchdog_thread is None or not self.watchdog_thread.is_alive():
                        self._start_watchdog()
                except Exception as watchdog_err:
                    logging.error(f"CRITICAL: Could not start watchdog: {watchdog_err}")

    def start_detection_thread(self):
        """Start background thread for song detection"""
        # CRITICAL FIX: Stop old thread properly using thread ID
        if self.detection_thread is not None and self.detection_thread.is_alive():
            logging.warning("Detection thread still alive during restart - stopping it")
            self.detection_active = False
            
            # Wait for old thread to exit
            self.detection_thread.join(timeout=3.0)
            if self.detection_thread.is_alive():
                logging.error("Old detection thread won't stop within 3s - incrementing thread ID to abandon it")
                # Old thread will see it has wrong ID and exit
        
        # CRITICAL FIX: Increment thread ID so old thread knows to exit
        with self._detection_thread_id_lock:
            self._detection_thread_id += 1
            current_thread_id = self._detection_thread_id
        
        # Now start new thread with new ID
        self.detection_active = True
        self.last_heartbeat = time.time()  # Reset heartbeat
        self.detection_thread = threading.Thread(
            target=self._detection_loop,
            args=(current_thread_id,),
            name=f"SongDetectorLoop-{current_thread_id}"
        )
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        # CRITICAL FIX: Verify thread actually started
        time.sleep(0.1)
        if self.detection_thread.is_alive():
            logging.info(f"✓ Song detection thread started (ID: {current_thread_id})")
        else:
            logging.error(f"✗ Song detection thread failed to start (ID: {current_thread_id})")
    
    def _start_watchdog(self):
        """Start watchdog thread to monitor and restart detection thread if it dies"""
        # CRITICAL FIX: Stop old watchdog properly using thread ID
        if self.watchdog_thread is not None and self.watchdog_thread.is_alive():
            logging.warning("Watchdog thread still alive during restart - stopping it")
            self.watchdog_active = False
            
            # Wait for old watchdog to exit
            self.watchdog_thread.join(timeout=3.0)
            if self.watchdog_thread.is_alive():
                logging.error("Old watchdog thread won't stop within 3s - incrementing thread ID to abandon it")
        
        # CRITICAL FIX: Increment thread ID so old watchdog knows to exit
        with self._watchdog_thread_id_lock:
            self._watchdog_thread_id += 1
            current_watchdog_id = self._watchdog_thread_id
        
        # Now start new watchdog with new ID
        self.watchdog_active = True
        self.watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            args=(current_watchdog_id,),
            name=f"SongDetectorWatchdog-{current_watchdog_id}"
        )
        self.watchdog_thread.daemon = True
        self.watchdog_thread.start()
        
        # CRITICAL FIX: Verify thread started
        time.sleep(0.1)
        if self.watchdog_thread.is_alive():
            logging.info(f"✅ Song detector watchdog started (ID: {current_watchdog_id})")
        else:
            logging.error(f"⚠️ Watchdog thread failed to start (ID: {current_watchdog_id})")
            self.watchdog_thread = None
    
    def _watchdog_loop(self, watchdog_id):
        """Watchdog loop to monitor thread health and restart if needed
        
        Args:
            watchdog_id: Unique ID for this watchdog instance
        """
        logging.info(f"Watchdog loop started (ID: {watchdog_id})")
        
        while self.watchdog_active and self.enabled:
            # CRITICAL FIX: Check if we're still the current watchdog
            with self._watchdog_thread_id_lock:
                if watchdog_id != self._watchdog_thread_id:
                    logging.info(f"Watchdog {watchdog_id} detected newer watchdog {self._watchdog_thread_id}, exiting gracefully")
                    return  # Exit cleanly - we've been replaced
            
            try:
                time.sleep(self.watchdog_interval)
                
                # CRITICAL FIX: Reset restart counter every hour for long-running stability
                current_time = time.time()
                if (current_time - self.restart_count_reset_time) > 3600:
                    if self.thread_restart_count > 0:
                        logging.info(f"🔄 Resetting thread restart counter ({self.thread_restart_count} -> 0) after 1 hour")
                    self.thread_restart_count = 0
                    self.restart_count_reset_time = current_time
                
                # Check if detection thread is alive
                if self.detection_thread is None or not self.detection_thread.is_alive():
                    logging.error("⚠️ Song detection thread died! Restarting...")
                    self.thread_restart_count += 1
                    
                    # Rate limit restarts - but use a sliding window
                    if self.thread_restart_count > self.max_restarts_per_hour:
                        logging.error(f"⚠️ Too many thread restarts ({self.thread_restart_count}). Waiting 5 minutes before retry.")
                        time.sleep(300)  # Wait 5 minutes (was 1 hour) for more responsive recovery
                        self.thread_restart_count = max(0, self.thread_restart_count - 5)  # Decay counter
                        continue
                    
                    # Restart the thread
                    self.start_detection_thread()
                
                # CRITICAL FIX: Check event loop thread health
                with self._event_loop_lock:
                    if self._event_loop_thread is not None and not self._event_loop_thread.is_alive():
                        logging.error("⚠️ Event loop thread died! Recreating...")
                        self._event_loop = None
                        self._event_loop_thread = None
                        # Will be recreated on next detection attempt
                
                # Check heartbeat - thread should update this every loop iteration
                heartbeat_age = time.time() - self.last_heartbeat
                # CRITICAL FIX: Increased heartbeat timeout to 60s to reduce false positives
                # API calls can legitimately take 10-15s, plus processing time
                if heartbeat_age > 60:  # Thread must respond within 60s (was 30s)
                    logging.error(f"🚨 CRITICAL: Song detection thread heartbeat stale ({heartbeat_age:.1f}s). FORCING RESTART!")
                    # CRITICAL FIX: Use start_detection_thread which properly handles old thread
                    # Don't manually set detection_active or join here - let start_detection_thread do it
                    self.start_detection_thread()
                    self.thread_restart_count += 1
                    
            except Exception as e:
                logging.error(f"Error in song detector watchdog: {e}")
                time.sleep(self.watchdog_interval)
    
    def _detection_loop(self, thread_id):
        """Background thread for periodic song detection
        
        Args:
            thread_id: Unique ID for this thread instance
        """
        logging.info(f"Song detection loop started (ID: {thread_id})")
        
        # Initialize last detection time to now to prevent immediate first detection
        # This gives the AudioMonitor time to open its dB monitoring stream first
        self.last_detection_time = time.time()
        
        while self.detection_active:
            # CRITICAL FIX: Check if we're still the current thread
            with self._detection_thread_id_lock:
                if thread_id != self._detection_thread_id:
                    logging.info(f"Thread {thread_id} detected newer thread {self._detection_thread_id}, exiting gracefully")
                    return  # Exit cleanly - we've been replaced
            
            try:
                # Update heartbeat (required for watchdog)
                self.last_heartbeat = time.time()
                
                # CRITICAL FIX: Don't recreate event loop in the detection loop!
                # Event loop is created once during initialization and reused.
                # Watchdog will handle restart if the entire detector needs to be restarted.
                
                if self.use_buffer_mode:
                    # In buffer mode, we just maintain heartbeat for watchdog
                    # External code will call detect_song_from_buffer() when needed
                    time.sleep(5)
                else:
                    # Auto-record mode: Check if it's time for a new detection
                    current_time = time.time()
                    if current_time - self.last_detection_time >= self.detection_interval:
                        logging.info("Starting song recognition...")
                        self.detect_song()
                        self.last_detection_time = current_time
                    
                    # Sleep to avoid consuming CPU
                    time.sleep(5)
            except Exception as e:
                logging.error(f"🚨 CRITICAL ERROR in detection loop (thread {thread_id}): {e}")
                import traceback
                logging.error(traceback.format_exc())
                # Update heartbeat even on error so watchdog knows we're alive
                self.last_heartbeat = time.time()
                time.sleep(5)  # Continue even after errors
        
        logging.info(f"Detection loop exiting (ID: {thread_id})")
    
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
        Detect song from pre-recorded audio buffer
        
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
            if not self._ensure_event_loop():
                logging.error("⚠️ Event loop unavailable - cannot process audio")
                return False
            
            # Create temporary file for the recording
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
                daemon=True
            )
            processing_thread.start()
            
            return True
            
        except Exception as e:
            logging.error(f"Error detecting song from buffer: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            return False
    
    def _ensure_event_loop(self):
        """Ensure we have a working event loop for async operations"""
        # CRITICAL FIX: Minimize time holding lock to prevent blocking
        # First check without lock if we need to do anything
        needs_creation = False
        with self._event_loop_lock:
            if self._event_loop is None or self._event_loop.is_closed():
                needs_creation = True
            elif self._event_loop_thread and not self._event_loop_thread.is_alive():
                needs_creation = True
                self._event_loop = None
                self._event_loop_thread = None
        
        if not needs_creation:
            return True  # Already have working event loop
        
        # Need to create new loop - do cleanup and creation outside lock where possible
        old_thread = None
        with self._event_loop_lock:
            # Double-check after acquiring lock
            if self._event_loop and not self._event_loop.is_closed() and self._event_loop_thread and self._event_loop_thread.is_alive():
                return True  # Someone else created it
            
            # CRITICAL FIX: Cleanup old thread if exists
            if self._event_loop_thread and self._event_loop_thread.is_alive():
                logging.warning("Event loop closed but thread still alive - will cleanup")
                if self._event_loop and not self._event_loop.is_closed():
                    try:
                        self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                    except Exception:
                        pass
                old_thread = self._event_loop_thread
                self._event_loop = None
                self._event_loop_thread = None
        
        # CRITICAL FIX: Wait for old thread OUTSIDE lock to not block other operations
        if old_thread:
            old_thread.join(timeout=3.0)
            if old_thread.is_alive():
                logging.error("Old event loop thread won't die - abandoning it")
        
        # Create new event loop
        loop_ready = threading.Event()
        loop = None
        
        def _loop_runner():
            nonlocal loop
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop_ready.set()
                loop.run_forever()
            except Exception as e:
                logging.error(f"Event loop runner error: {e}")
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
        
        thread = threading.Thread(target=_loop_runner, name="SongDetectorEventLoop", daemon=True)
        thread.start()
        
        # CRITICAL FIX: Wait for loop creation OUTSIDE lock
        if not loop_ready.wait(timeout=5.0):
            logging.error("❌ Failed to create event loop within timeout")
            return False
        
        # Only hold lock briefly to store the new loop
        with self._event_loop_lock:
            self._event_loop = loop
            self._event_loop_thread = thread
        
        logging.info("✅ Song detector event loop created")
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
        # CRITICAL: Check circuit breaker before attempting API call
        if self._api_circuit_open:
            time_since_open = time.time() - self._api_last_failure_time
            if time_since_open < self._api_circuit_reset_time:
                logging.debug(f"⚠️ API circuit breaker OPEN - skipping call (resets in {self._api_circuit_reset_time - time_since_open:.1f}s)")
                return None
            else:
                # Reset circuit breaker
                logging.info("✅ API circuit breaker RESET - attempting API call")
                self._api_circuit_open = False
                self._api_failure_count = 0
        
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
            # Success - reset circuit breaker failure count
            self._api_failure_count = 0
            return result
        except asyncio.TimeoutError:
            logging.warning("⚠️ Shazam recognition timed out after 10s")
            self._handle_api_failure("timeout")
            # Reset instance on timeout
            self._shazam_instance = None
            self._shazam_created_at = 0.0
            return None
        except Exception as e:
            logging.error(f"Shazam recognition error: {e}")
            self._handle_api_failure(str(e))
            # Reset instance on error
            self._shazam_instance = None
            self._shazam_created_at = 0.0
            return None
    
    def _handle_api_failure(self, error_msg):
        """Handle API failures with circuit breaker pattern"""
        current_time = time.time()
        self._api_failure_count += 1
        self._api_last_failure_time = current_time
        
        if self._api_failure_count >= self._api_max_failures_before_open:
            self._api_circuit_open = True
            logging.error(
                f"🚨 API CIRCUIT BREAKER OPENED after {self._api_failure_count} failures. "
                f"Will retry in {self._api_circuit_reset_time}s"
            )
        else:
            logging.warning(
                f"⚠️ API failure {self._api_failure_count}/{self._api_max_failures_before_open}: {error_msg}"
            )
        
        # CRITICAL FIX: Auto-decay failure count over time to prevent permanent circuit open
        # If last failure was >1 hour ago, reduce failure count
        if self._api_failure_count > 0 and (current_time - self._api_last_failure_time) > 3600:
            old_count = self._api_failure_count
            self._api_failure_count = max(0, self._api_failure_count - 1)
            if old_count != self._api_failure_count:
                logging.info(f"✅ API failure count decayed: {old_count} -> {self._api_failure_count}")
    
    def get_latest_song(self):
        """Get the latest detected song information"""
        with self.lock:
            return self.latest_song.copy()
    
    def stop(self):
        """Stop song detection thread"""
        logging.info("Stopping song detector...")
        self.detection_active = False
        self.watchdog_active = False
        
        # Stop detection thread
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=3.0)
            if self.detection_thread.is_alive():
                logging.warning("Detection thread did not stop gracefully")
            else:
                logging.info("✓ Song detection thread stopped")
        
        # Stop watchdog
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=3.0)
            if self.watchdog_thread.is_alive():
                logging.warning("Watchdog thread did not stop gracefully")
            else:
                logging.info("✓ Song detector watchdog stopped")
        
        # CRITICAL FIX: Properly clean up event loop with better error handling
        with self._event_loop_lock:
            if self._event_loop and not self._event_loop.is_closed():
                try:
                    self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                    logging.debug("Event loop stop requested")
                except Exception as e:
                    logging.warning(f"Error stopping event loop: {e}")
                
                # CRITICAL FIX: Wait for event loop thread to finish
                if self._event_loop_thread and self._event_loop_thread.is_alive():
                    self._event_loop_thread.join(timeout=3.0)
                    if self._event_loop_thread.is_alive():
                        logging.error("Event loop thread did not stop - abandoning")
                    else:
                        logging.info("✓ Event loop thread stopped")
                
                # Close the loop
                try:
                    if not self._event_loop.is_closed():
                        self._event_loop.close()
                        logging.debug("Event loop closed")
                except Exception as e:
                    logging.warning(f"Error closing event loop: {e}")
                
                self._event_loop = None
                self._event_loop_thread = None
        
        # Clean up Shazam instance
        if self._shazam_instance:
            try:
                # Try to close client if possible
                client = getattr(self._shazam_instance, 'client', None)
                if client and hasattr(client, 'close'):
                    # CRITICAL FIX: Don't create new event loop during cleanup
                    # Just mark instance for cleanup and let it be garbage collected
                    logging.debug("Marking Shazam instance for cleanup")
            except Exception as e:
                logging.debug(f"Error during Shazam cleanup: {e}")
            self._shazam_instance = None
        
        logging.info("✅ Song detector stopped and cleaned up")