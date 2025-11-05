#!/usr/bin/env python3
"""
EMERGENCY AUDIO RECOVERY SYSTEM
This script provides emergency recovery for the song detector and decibel reader.
Run this if the main system fails or stops working.

This is your LAST LINE OF DEFENSE.
"""

import sys
import os
import time
import logging
import subprocess
import psutil

# Add path
sys.path.insert(0, '/opt/pulse')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EmergencyRecovery:
    """Emergency recovery system for audio services"""
    
    def __init__(self):
        self.recovery_attempts = 0
        self.max_recovery_attempts = 10
        
    def check_audio_processes(self):
        """Check if audio-related processes are running"""
        logger.info("🔍 Checking audio processes...")
        
        audio_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if any(keyword in cmdline.lower() for keyword in ['audio', 'mic_song_detect', 'song_detector', 'pulse']):
                    audio_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if audio_processes:
            logger.info(f"Found {len(audio_processes)} audio-related processes:")
            for proc in audio_processes:
                logger.info(f"  PID {proc['pid']}: {proc['name']}")
        else:
            logger.warning("⚠️ No audio processes found!")
        
        return audio_processes
    
    def check_audio_devices(self):
        """Check if audio devices are available"""
        logger.info("🔍 Checking audio devices...")
        
        try:
            result = subprocess.run(
                ['arecord', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("✅ Audio devices found:")
                for line in result.stdout.split('\n'):
                    if line.strip():
                        logger.info(f"  {line}")
                return True
            else:
                logger.error("❌ No audio devices found!")
                logger.error(result.stderr)
                return False
        except Exception as e:
            logger.error(f"❌ Error checking audio devices: {e}")
            return False
    
    def test_audio_capture(self):
        """Test if audio capture is working"""
        logger.info("🔍 Testing audio capture...")
        
        try:
            # Try to record 1 second of audio
            test_file = '/tmp/audio_test.wav'
            result = subprocess.run(
                ['arecord', '-d', '1', '-f', 'cd', test_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and os.path.exists(test_file):
                file_size = os.path.getsize(test_file)
                logger.info(f"✅ Audio capture working (recorded {file_size} bytes)")
                os.remove(test_file)
                return True
            else:
                logger.error("❌ Audio capture failed!")
                logger.error(result.stderr)
                return False
        except Exception as e:
            logger.error(f"❌ Error testing audio capture: {e}")
            return False
    
    def check_dependencies(self):
        """Check if required Python packages are installed"""
        logger.info("🔍 Checking Python dependencies...")
        
        dependencies = {
            'numpy': None,
            'sounddevice': None,
            'pyaudio': None,
            'shazamio': None
        }
        
        for package in dependencies:
            try:
                __import__(package)
                dependencies[package] = True
                logger.info(f"  ✅ {package}")
            except ImportError:
                dependencies[package] = False
                logger.error(f"  ❌ {package} NOT INSTALLED")
        
        return all(dependencies.values())
    
    def kill_zombie_processes(self):
        """Kill any zombie audio processes"""
        logger.info("🔪 Killing zombie audio processes...")
        
        killed = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if any(keyword in cmdline.lower() for keyword in ['audio', 'mic_song_detect', 'song_detector']):
                    logger.info(f"  Killing PID {proc.info['pid']}: {proc.info['name']}")
                    proc.kill()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if killed > 0:
            logger.info(f"✅ Killed {killed} processes")
            time.sleep(2)
        else:
            logger.info("  No processes to kill")
        
        return killed
    
    def restart_audio_services(self):
        """Restart the audio monitoring services"""
        logger.info("🔄 Restarting audio services...")
        
        try:
            # Try to import and restart AudioMonitor
            from services.sensors.mic_song_detect import AudioMonitor
            
            logger.info("  Creating new AudioMonitor instance...")
            monitor = AudioMonitor()
            
            logger.info("  Starting monitoring...")
            monitor.start_monitoring()
            
            # Wait and verify
            time.sleep(3)
            
            if monitor.running:
                db = monitor.get_current_db()
                logger.info(f"✅ Audio monitoring started! Current dB: {db:.1f}")
                
                # Check song detector
                if hasattr(monitor, 'song_detector') and monitor.song_detector:
                    if monitor.song_detector.enabled:
                        logger.info("✅ Song detector enabled and running")
                    else:
                        logger.warning("⚠️ Song detector disabled")
                
                return True, monitor
            else:
                logger.error("❌ Audio monitoring failed to start!")
                return False, None
                
        except Exception as e:
            logger.error(f"❌ Error restarting audio services: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    def run_recovery(self):
        """Run the full recovery process"""
        logger.info("="*80)
        logger.info("🚨 EMERGENCY AUDIO RECOVERY SYSTEM ACTIVATED")
        logger.info("="*80)
        
        self.recovery_attempts += 1
        logger.info(f"Recovery attempt {self.recovery_attempts}/{self.max_recovery_attempts}")
        
        # Step 1: Check dependencies
        logger.info("\n[STEP 1] Checking dependencies...")
        if not self.check_dependencies():
            logger.error("❌ CRITICAL: Missing dependencies. Install with:")
            logger.error("  pip install numpy sounddevice pyaudio shazamio")
            return False
        
        # Step 2: Check audio devices
        logger.info("\n[STEP 2] Checking audio devices...")
        if not self.check_audio_devices():
            logger.error("❌ CRITICAL: No audio devices found!")
            logger.error("  Check: sudo arecord -l")
            logger.error("  Check: sudo i2cdetect -y 1")
            return False
        
        # Step 3: Test audio capture
        logger.info("\n[STEP 3] Testing audio capture...")
        if not self.test_audio_capture():
            logger.error("❌ CRITICAL: Audio capture not working!")
            return False
        
        # Step 4: Kill zombie processes
        logger.info("\n[STEP 4] Killing zombie processes...")
        self.kill_zombie_processes()
        
        # Step 5: Restart services
        logger.info("\n[STEP 5] Restarting audio services...")
        success, monitor = self.restart_audio_services()
        
        if success:
            logger.info("\n" + "="*80)
            logger.info("✅ EMERGENCY RECOVERY SUCCESSFUL!")
            logger.info("="*80)
            
            # Monitor for 30 seconds to verify
            logger.info("\n🔍 Monitoring for 30 seconds to verify stability...")
            for i in range(6):
                time.sleep(5)
                if monitor and monitor.running:
                    db = monitor.get_current_db()
                    logger.info(f"  [{i+1}/6] dB: {db:.1f} - Status: {'✅ OK' if db > 0 else '⚠️ WARNING'}")
                else:
                    logger.error(f"  [{i+1}/6] ❌ Monitoring stopped!")
                    return False
            
            logger.info("\n✅ System stable - recovery complete!")
            return True
        else:
            logger.error("\n" + "="*80)
            logger.error("❌ EMERGENCY RECOVERY FAILED!")
            logger.error("="*80)
            return False


def main():
    """Main entry point"""
    recovery = EmergencyRecovery()
    
    try:
        success = recovery.run_recovery()
        
        if success:
            logger.info("\n💪 System recovered and running normally!")
            logger.info("You can now exit this script (Ctrl+C)")
            logger.info("The audio services will continue running in the background.")
            
            # Keep running to monitor
            while True:
                time.sleep(60)
                logger.info("🔍 Still monitoring... (press Ctrl+C to exit)")
        else:
            logger.error("\n🚨 RECOVERY FAILED!")
            logger.error("Manual intervention required.")
            logger.error("Contact support or check system logs.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n👋 Emergency recovery script stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n🚨 CRITICAL ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
