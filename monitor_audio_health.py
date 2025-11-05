#!/usr/bin/env python3
"""
REAL-TIME AUDIO HEALTH MONITOR
Continuously monitors the song detector and decibel reader health
Displays live status and alerts on any issues

Run this in a separate terminal to monitor system health 24/7
"""

import sys
import os
import time
import logging
from datetime import datetime
from threading import Thread

# Add path
sys.path.insert(0, '/opt/pulse')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class AudioHealthMonitor:
    """Real-time health monitoring for audio services"""
    
    def __init__(self):
        self.monitor = None
        self.running = True
        self.check_interval = 5  # Check every 5 seconds
        
        # Health metrics
        self.last_db_reading = 0
        self.last_db_change_time = time.time()
        self.consecutive_zero_readings = 0
        self.total_checks = 0
        self.failed_checks = 0
        self.last_song = None
        self.song_detection_count = 0
        
        # Thread health tracking
        self.last_monitoring_thread_check = time.time()
        self.last_watchdog_thread_check = time.time()
        self.last_song_detector_thread_check = time.time()
        
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def print_header(self):
        """Print status header"""
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}🔊 AUDIO HEALTH MONITOR - LIVE STATUS{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.WHITE}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print()
    
    def check_status(self, status):
        """Return colored status indicator"""
        if status == "OK":
            return f"{Colors.GREEN}✅ OK{Colors.END}"
        elif status == "WARNING":
            return f"{Colors.YELLOW}⚠️  WARNING{Colors.END}"
        else:
            return f"{Colors.RED}❌ CRITICAL{Colors.END}"
    
    def initialize_monitor(self):
        """Initialize the audio monitor"""
        try:
            from services.sensors.mic_song_detect import AudioMonitor
            
            logger.info("Initializing AudioMonitor...")
            self.monitor = AudioMonitor()
            
            if not self.monitor.running:
                logger.info("Starting audio monitoring...")
                self.monitor.start_monitoring()
                time.sleep(2)
            
            if self.monitor.running:
                logger.info("✅ AudioMonitor initialized and running")
                return True
            else:
                logger.error("❌ AudioMonitor failed to start")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize AudioMonitor: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def check_db_reader_health(self):
        """Check decibel reader health"""
        if not self.monitor or not self.monitor.running:
            return "CRITICAL", "Monitor not running"
        
        try:
            current_db = self.monitor.get_current_db()
            self.total_checks += 1
            
            # Check if dB is stuck at 0
            if current_db == 0:
                self.consecutive_zero_readings += 1
            else:
                self.consecutive_zero_readings = 0
            
            # Check if dB reading changed
            if current_db != self.last_db_reading:
                self.last_db_change_time = time.time()
                self.last_db_reading = current_db
            
            # Determine health status
            time_since_change = time.time() - self.last_db_change_time
            
            if self.consecutive_zero_readings > 3:
                self.failed_checks += 1
                return "CRITICAL", f"Stuck at 0 dB ({self.consecutive_zero_readings} readings)"
            elif time_since_change > 30:
                self.failed_checks += 1
                return "WARNING", f"No change for {time_since_change:.1f}s"
            elif current_db > 0:
                return "OK", f"Active: {current_db:.1f} dB"
            else:
                return "WARNING", f"Reading: {current_db:.1f} dB"
                
        except Exception as e:
            self.failed_checks += 1
            return "CRITICAL", f"Error: {str(e)}"
    
    def check_song_detector_health(self):
        """Check song detector health"""
        if not self.monitor:
            return "CRITICAL", "Monitor not available"
        
        try:
            if not hasattr(self.monitor, 'song_detector') or not self.monitor.song_detector:
                return "WARNING", "Song detector not initialized"
            
            sd = self.monitor.song_detector
            
            if not sd.enabled:
                return "WARNING", "Song detector disabled"
            
            # Check threads
            issues = []
            
            # Check detection thread
            if sd.detection_thread is None or not sd.detection_thread.is_alive():
                issues.append("Detection thread dead")
            
            # Check watchdog thread
            if sd.watchdog_thread is None or not sd.watchdog_thread.is_alive():
                issues.append("Watchdog thread dead")
            
            # Check event loop
            if sd._event_loop is None or sd._event_loop.is_closed():
                issues.append("Event loop unavailable")
            
            # Check for circuit breaker
            if hasattr(sd, '_api_circuit_open') and sd._api_circuit_open:
                issues.append("API circuit breaker OPEN")
            
            # Get latest song
            song = sd.get_latest_song()
            if song and song.get('title') != 'Unknown':
                if self.last_song != song.get('title'):
                    self.song_detection_count += 1
                    self.last_song = song.get('title')
            
            if issues:
                return "CRITICAL", "; ".join(issues)
            else:
                return "OK", f"Running ({self.song_detection_count} songs detected)"
                
        except Exception as e:
            return "CRITICAL", f"Error: {str(e)}"
    
    def check_thread_health(self):
        """Check all threads are alive"""
        if not self.monitor or not self.monitor.running:
            return "CRITICAL", "Monitor not running"
        
        try:
            threads_ok = []
            threads_dead = []
            
            # Check monitoring thread
            if self.monitor._monitoring_thread and self.monitor._monitoring_thread.is_alive():
                threads_ok.append("Monitoring")
            else:
                threads_dead.append("Monitoring")
            
            # Check health thread
            if self.monitor._health_thread and self.monitor._health_thread.is_alive():
                threads_ok.append("Health")
            else:
                threads_dead.append("Health")
            
            # Check song detector threads
            if hasattr(self.monitor, 'song_detector') and self.monitor.song_detector:
                sd = self.monitor.song_detector
                if sd.detection_thread and sd.detection_thread.is_alive():
                    threads_ok.append("SongDetect")
                else:
                    threads_dead.append("SongDetect")
                
                if sd.watchdog_thread and sd.watchdog_thread.is_alive():
                    threads_ok.append("SDWatchdog")
                else:
                    threads_dead.append("SDWatchdog")
            
            if threads_dead:
                return "CRITICAL", f"Dead: {', '.join(threads_dead)}"
            else:
                return "OK", f"All threads running ({len(threads_ok)})"
                
        except Exception as e:
            return "CRITICAL", f"Error: {str(e)}"
    
    def get_current_song_info(self):
        """Get current song information"""
        if not self.monitor:
            return "N/A", "Monitor not available"
        
        try:
            song = self.monitor.get_current_song()
            if song and song.get('title') not in (None, 'Unknown'):
                title = song.get('title', 'Unknown')
                artist = song.get('artist', 'Unknown')
                return f"{title} - {artist}", None
            else:
                return "No song detected", None
        except Exception as e:
            return "Error", str(e)
    
    def display_status(self):
        """Display current status"""
        self.clear_screen()
        self.print_header()
        
        # Overall health
        db_status, db_msg = self.check_db_reader_health()
        song_status, song_msg = self.check_song_detector_health()
        thread_status, thread_msg = self.check_thread_health()
        
        # Determine overall status
        if "CRITICAL" in [db_status, song_status, thread_status]:
            overall = "CRITICAL"
        elif "WARNING" in [db_status, song_status, thread_status]:
            overall = "WARNING"
        else:
            overall = "OK"
        
        print(f"{Colors.BOLD}OVERALL STATUS: {self.check_status(overall)}{Colors.END}")
        print()
        
        # Component health
        print(f"{Colors.BOLD}{Colors.BLUE}COMPONENT HEALTH:{Colors.END}")
        print(f"  🔊 dB Reader:      {self.check_status(db_status):40s} - {db_msg}")
        print(f"  🎵 Song Detector:  {self.check_status(song_status):40s} - {song_msg}")
        print(f"  🧵 Thread Health:  {self.check_status(thread_status):40s} - {thread_msg}")
        print()
        
        # Current readings
        print(f"{Colors.BOLD}{Colors.BLUE}CURRENT READINGS:{Colors.END}")
        if self.monitor and self.monitor.running:
            current_db = self.monitor.get_current_db()
            peak_db = self.monitor.get_peak_db()
            print(f"  Current dB:  {Colors.GREEN if current_db > 0 else Colors.YELLOW}{current_db:.1f} dB{Colors.END}")
            print(f"  Peak dB:     {peak_db:.1f} dB")
        else:
            print(f"  {Colors.RED}Monitor not running{Colors.END}")
        print()
        
        # Current song
        print(f"{Colors.BOLD}{Colors.BLUE}CURRENT SONG:{Colors.END}")
        song_info, song_error = self.get_current_song_info()
        if song_error:
            print(f"  {Colors.RED}{song_error}{Colors.END}")
        else:
            if "No song" in song_info:
                print(f"  {Colors.YELLOW}{song_info}{Colors.END}")
            else:
                print(f"  {Colors.GREEN}{song_info}{Colors.END}")
        print()
        
        # Statistics
        print(f"{Colors.BOLD}{Colors.BLUE}STATISTICS:{Colors.END}")
        uptime = time.time() - self.last_db_change_time if hasattr(self, 'last_db_change_time') else 0
        success_rate = ((self.total_checks - self.failed_checks) / self.total_checks * 100) if self.total_checks > 0 else 0
        print(f"  Total Checks:       {self.total_checks}")
        print(f"  Failed Checks:      {self.failed_checks}")
        print(f"  Success Rate:       {success_rate:.1f}%")
        print(f"  Songs Detected:     {self.song_detection_count}")
        print(f"  Time Since Change:  {uptime:.1f}s")
        print()
        
        # Alerts
        if overall == "CRITICAL":
            print(f"{Colors.BOLD}{Colors.RED}🚨 ALERT: CRITICAL ISSUES DETECTED!{Colors.END}")
            print(f"{Colors.RED}System requires immediate attention!{Colors.END}")
            print()
        elif overall == "WARNING":
            print(f"{Colors.BOLD}{Colors.YELLOW}⚠️  WARNING: Issues detected{Colors.END}")
            print()
        
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.WHITE}Press Ctrl+C to exit | Updating every {self.check_interval}s{Colors.END}")
    
    def run(self):
        """Run the monitor"""
        logger.info("="*80)
        logger.info("🔊 AUDIO HEALTH MONITOR STARTING")
        logger.info("="*80)
        
        # Initialize
        if not self.initialize_monitor():
            logger.error("Failed to initialize monitor!")
            return False
        
        logger.info("✅ Monitor initialized - starting live display...")
        time.sleep(2)
        
        # Main monitoring loop
        try:
            while self.running:
                self.display_status()
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("\n\n👋 Monitor stopped by user")
            return True
        except Exception as e:
            logger.error(f"\n\n🚨 CRITICAL ERROR: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point"""
    monitor = AudioHealthMonitor()
    
    try:
        monitor.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
