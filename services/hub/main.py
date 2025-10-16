"""
Pulse 1.0 - Hub Orchestration Engine
Main coordinator for all sensors, controls, and automation
"""

import logging
import os
import sys
import time
import yaml
from datetime import datetime, timedelta
from threading import Thread, Event
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.db import PulseDB
from sensors.health_monitor import HealthMonitor
from sensors.camera_people import PeopleCounter
from sensors.mic_song_detect import AudioMonitor
from sensors.bme280_reader import BME280Reader
from sensors.light_level import LightSensor
from sensors.pan_tilt import PanTiltController

logger = logging.getLogger(__name__)

class PulseHub:
    def __init__(self, config_path: str = "/opt/pulse/config/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.db = PulseDB()
        self.health_monitor = HealthMonitor()
        
        # Sensors
        self.people_counter = None
        self.audio_monitor = None
        self.bme280 = None
        self.light_sensor = None
        self.pan_tilt = None
        
        # Controllers
        self.hvac_controller = None
        self.lighting_controller = None
        self.tv_controller = None
        self.music_controller = None
        
        # State
        self.running = False
        self.stop_event = Event()
        
        # Rate limiting for automation
        self.last_hvac_change = datetime.now() - timedelta(minutes=10)
        self.last_lighting_change = datetime.now() - timedelta(minutes=10)
        self.last_music_change = datetime.now() - timedelta(minutes=3)
        
        self._init_components()
    
    def _load_config(self) -> dict:
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def _init_components(self):
        """Initialize sensors and controllers based on config"""
        modules = self.config.get('modules', {})
        integrations = self.config.get('smart_integrations', {})
        
        # Initialize sensors
        if modules.get('camera'):
            try:
                use_ai_hat = modules.get('ai_hat', False)
                self.people_counter = PeopleCounter(use_ai_hat=use_ai_hat)
                self.health_monitor.register_test("camera", lambda: True)
                logger.info("People counter initialized")
            except Exception as e:
                logger.warning(f"Could not initialize people counter: {e}")
        
        if modules.get('mic'):
            try:
                self.audio_monitor = AudioMonitor()
                self.health_monitor.register_test("mic", lambda: True)
                logger.info("Audio monitor initialized")
            except Exception as e:
                logger.warning(f"Could not initialize audio monitor: {e}")
        
        if modules.get('bme280'):
            try:
                self.bme280 = BME280Reader()
                self.health_monitor.register_test("bme280", lambda: True)
                logger.info("BME280 sensor initialized")
            except Exception as e:
                logger.warning(f"Could not initialize BME280: {e}")
        
        if modules.get('light_sensor'):
            try:
                self.light_sensor = LightSensor()
                self.health_monitor.register_test("light_sensor", lambda: True)
                logger.info("Light sensor initialized")
            except Exception as e:
                logger.warning(f"Could not initialize light sensor: {e}")
        
        if modules.get('pan_tilt'):
            try:
                self.pan_tilt = PanTiltController()
                self.health_monitor.register_test("pan_tilt", lambda: True)
                logger.info("Pan-tilt controller initialized")
            except Exception as e:
                logger.warning(f"Could not initialize pan-tilt: {e}")
        
        # Initialize controllers
        self._init_hvac(integrations.get('hvac', {}))
        self._init_lighting(integrations.get('lighting', {}))
        self._init_tv(integrations.get('tv', {}))
        self._init_music(integrations.get('music', {}))
    
    def _init_hvac(self, config: dict):
        """Initialize HVAC controller"""
        if not config.get('enabled'):
            return
        
        try:
            from controls.hvac_nest import NestHVACController
            
            self.hvac_controller = NestHVACController(
                project_id=os.getenv('GOOGLE_PROJECT_ID'),
                device_id=config.get('device_id') or os.getenv('NEST_DEVICE_ID'),
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                refresh_token=os.getenv('NEST_REFRESH_TOKEN')
            )
            
            logger.info("HVAC controller initialized")
        except Exception as e:
            logger.warning(f"Could not initialize HVAC: {e}")
    
    def _init_lighting(self, config: dict):
        """Initialize lighting controller"""
        if not config.get('enabled'):
            return
        
        try:
            from controls.lighting_hue import HueLightingController
            
            self.lighting_controller = HueLightingController(
                bridge_ip=config.get('bridge_ip') or os.getenv('HUE_BRIDGE_IP'),
                username=os.getenv('HUE_USERNAME')
            )
            
            logger.info("Lighting controller initialized")
        except Exception as e:
            logger.warning(f"Could not initialize lighting: {e}")
    
    def _init_tv(self, config: dict):
        """Initialize TV controller"""
        if not config.get('enabled'):
            return
        
        try:
            if config.get('provider') == 'cec':
                from controls.tv_cec import CECTVController
                self.tv_controller = CECTVController()
            else:
                from controls.tv_cec import IPTVController
                self.tv_controller = IPTVController(config.get('devices', []))
            
            logger.info("TV controller initialized")
        except Exception as e:
            logger.warning(f"Could not initialize TV: {e}")
    
    def _init_music(self, config: dict):
        """Initialize music controller"""
        if not config.get('enabled'):
            return
        
        try:
            if config.get('provider') == 'spotify':
                from controls.music_spotify import SpotifyController
                
                self.music_controller = SpotifyController(
                    client_id=os.getenv('SPOTIFY_CLIENT_ID'),
                    client_secret=os.getenv('SPOTIFY_CLIENT_SECRET'),
                    redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:9090/callback/spotify')
                )
            else:
                from controls.music_local import LocalMusicController
                self.music_controller = LocalMusicController()
            
            logger.info("Music controller initialized")
        except Exception as e:
            logger.warning(f"Could not initialize music: {e}")
    
    def start(self):
        """Start the hub"""
        if self.running:
            logger.warning("Hub already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        # Start sensors
        if self.people_counter:
            self.people_counter.start_counting()
        
        if self.audio_monitor:
            self.audio_monitor.start_monitoring()
        
        if self.bme280:
            self.bme280.start_reading(interval=30)
        
        if self.light_sensor:
            self.light_sensor.start_monitoring(interval=30)
        
        # Start main loop
        thread = Thread(target=self._main_loop)
        thread.daemon = True
        thread.start()
        
        logger.info("Pulse Hub started")
    
    def _main_loop(self):
        """Main hub loop"""
        loop_interval = 30  # seconds
        
        while self.running and not self.stop_event.is_set():
            try:
                # Collect sensor data
                sensor_data = self._collect_sensor_data()
                
                # Store in database
                self._store_sensor_data(sensor_data)
                
                # Run automation rules
                self._run_automation_rules(sensor_data)
                
                # Update learning data
                self._update_learning_data(sensor_data)
                
                # Wait for next iteration
                self.stop_event.wait(loop_interval)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.stop_event.wait(loop_interval)
    
    def _collect_sensor_data(self) -> dict:
        """Collect data from all sensors"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "occupancy": 0,
            "temperature_f": None,
            "humidity": None,
            "light_level": None,
            "noise_db": None,
            "current_song": None
        }
        
        if self.people_counter:
            data["occupancy"] = self.people_counter.get_current_count()
        
        if self.bme280:
            readings = self.bme280.get_all_readings()
            data["temperature_f"] = readings.get("temperature_f")
            data["humidity"] = readings.get("humidity")
        
        if self.light_sensor:
            data["light_level"] = self.light_sensor.get_light_level()
        
        if self.audio_monitor:
            data["noise_db"] = self.audio_monitor.get_current_db()
            data["current_song"] = self.audio_monitor.get_current_song()
        
        return data
    
    def _store_sensor_data(self, data: dict):
        """Store sensor data in database"""
        try:
            # Occupancy
            if data.get("occupancy") is not None:
                self.db.log_occupancy("Main Floor", data["occupancy"])
            
            # Environment
            self.db.log_environment(
                temperature=data.get("temperature_f"),
                humidity=data.get("humidity"),
                light_level=data.get("light_level"),
                noise_level=data.get("noise_db")
            )
            
            # Music
            song = data.get("current_song")
            if song and song.get("title") != "Unknown":
                volume = 0
                if self.music_controller:
                    try:
                        current = self.music_controller.get_current_track()
                        volume = current.get("volume_percent", 0)
                    except:
                        pass
                
                self.db.log_music(
                    song["title"],
                    song.get("artist", "Unknown"),
                    volume
                )
            
        except Exception as e:
            logger.error(f"Error storing sensor data: {e}")
    
    def _run_automation_rules(self, data: dict):
        """Run automation rules based on sensor data"""
        policies = self.config.get('policies', {})
        
        # HVAC automation
        if self.hvac_controller and policies.get('hvac', {}).get('auto_mode'):
            self._automate_hvac(data, policies['hvac'])
        
        # Lighting automation
        if self.lighting_controller and policies.get('lighting', {}).get('auto_mode'):
            self._automate_lighting(data, policies['lighting'])
        
        # Music automation
        if self.music_controller and policies.get('music', {}).get('auto_mode'):
            self._automate_music(data, policies['music'])
    
    def _automate_hvac(self, data: dict, policy: dict):
        """Automated HVAC control"""
        try:
            # Rate limit
            if (datetime.now() - self.last_hvac_change).seconds < 600:
                return
            
            temp = data.get("temperature_f")
            occupancy = data.get("occupancy", 0)
            
            if temp is None:
                return
            
            # Get current HVAC status
            status = self.hvac_controller.get_status()
            current_mode = status.get("mode", "OFF")
            
            # Simple comfort-based logic
            target_temp = 70  # Default
            
            # Adjust based on occupancy
            if occupancy > 10:
                target_temp = 68  # Cooler when crowded
            elif occupancy < 3:
                target_temp = 72  # Warmer when empty
            
            # Clamp to policy limits
            min_temp = policy.get('min_f', 67)
            max_temp = policy.get('max_f', 75)
            target_temp = max(min_temp, min(max_temp, target_temp))
            
            # Make adjustment if needed
            delta = temp - target_temp
            
            if abs(delta) > 2:  # Only adjust if >2°F off
                if delta > 0:  # Too hot
                    if current_mode != "COOL":
                        self.hvac_controller.set_mode("COOL")
                        self.db.log_automation("hvac", f"Set to COOL", 
                                             f"Temp {temp}°F > target {target_temp}°F")
                    self.hvac_controller.set_temperature(cool_f=target_temp)
                else:  # Too cold
                    if current_mode != "HEAT":
                        self.hvac_controller.set_mode("HEAT")
                        self.db.log_automation("hvac", f"Set to HEAT",
                                             f"Temp {temp}°F < target {target_temp}°F")
                    self.hvac_controller.set_temperature(heat_f=target_temp)
                
                self.last_hvac_change = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in HVAC automation: {e}")
            self.db.log_automation("hvac", "Error", str(e), success=False)
    
    def _automate_lighting(self, data: dict, policy: dict):
        """Automated lighting control"""
        try:
            # Rate limit
            if (datetime.now() - self.last_lighting_change).seconds < 600:
                return
            
            light_level = data.get("light_level", 0)
            occupancy = data.get("occupancy", 0)
            hour = datetime.now().hour
            
            # No one here - dim lights
            if occupancy == 0:
                self.lighting_controller.set_brightness_pct(1, 10)
                self.db.log_automation("lighting", "Dimmed to 10%", "No occupancy")
                self.last_lighting_change = datetime.now()
                return
            
            # Use circadian rhythm
            self.lighting_controller.set_circadian(hour)
            self.db.log_automation("lighting", f"Set circadian for hour {hour}", 
                                 f"Occupancy: {occupancy}")
            
            self.last_lighting_change = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in lighting automation: {e}")
            self.db.log_automation("lighting", "Error", str(e), success=False)
    
    def _automate_music(self, data: dict, policy: dict):
        """Automated music control"""
        try:
            # Rate limit
            if (datetime.now() - self.last_music_change).seconds < 180:
                return
            
            occupancy = data.get("occupancy", 0)
            noise_db = data.get("noise_db", 0)
            
            # Adjust volume based on noise level
            if noise_db > 70:  # Noisy
                target_volume = 65
            elif noise_db < 50:  # Quiet
                target_volume = 40
            else:
                target_volume = 50
            
            # Clamp to policy
            min_vol = policy.get('volume_min', 25)
            max_vol = policy.get('volume_max', 70)
            target_volume = max(min_vol, min(max_vol, target_volume))
            
            self.music_controller.set_volume(target_volume)
            self.db.log_automation("music", f"Set volume to {target_volume}%",
                                 f"Noise: {noise_db:.1f}dB, Occupancy: {occupancy}")
            
            self.last_music_change = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in music automation: {e}")
            self.db.log_automation("music", "Error", str(e), success=False)
    
    def _update_learning_data(self, data: dict):
        """Update learning data for ML optimization"""
        try:
            # Calculate dwell time (placeholder - would track individuals)
            avg_dwell = 30.0  # minutes
            
            now = datetime.now()
            
            self.db.log_learning_data(
                avg_dwell_minutes=avg_dwell,
                occupancy=data.get("occupancy", 0),
                temperature=data.get("temperature_f", 0),
                humidity=data.get("humidity", 0),
                light_level=data.get("light_level", 0),
                noise_level=data.get("noise_db", 0),
                music_volume=0,  # Would get from controller
                day_of_week=now.weekday(),
                hour_of_day=now.hour
            )
        
        except Exception as e:
            logger.error(f"Error updating learning data: {e}")
    
    def stop(self):
        """Stop the hub"""
        self.running = False
        self.stop_event.set()
        
        # Stop sensors
        if self.people_counter:
            self.people_counter.stop_counting()
        
        if self.audio_monitor:
            self.audio_monitor.stop_monitoring()
        
        if self.bme280:
            self.bme280.stop_reading()
        
        if self.light_sensor:
            self.light_sensor.stop_monitoring()
        
        logger.info("Pulse Hub stopped")
    
    def get_status(self) -> dict:
        """Get current hub status"""
        sensor_data = self._collect_sensor_data()
        
        return {
            "running": self.running,
            "sensors": sensor_data,
            "modules": {
                "camera": self.people_counter is not None,
                "mic": self.audio_monitor is not None,
                "bme280": self.bme280 is not None,
                "light_sensor": self.light_sensor is not None,
                "pan_tilt": self.pan_tilt is not None
            },
            "controllers": {
                "hvac": self.hvac_controller is not None,
                "lighting": self.lighting_controller is not None,
                "tv": self.tv_controller is not None,
                "music": self.music_controller is not None
            }
        }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    hub = PulseHub()
    
    try:
        hub.start()
        
        # Keep running
        while True:
            time.sleep(60)
            status = hub.get_status()
            logger.info(f"Status: {status['running']}, "
                       f"Occupancy: {status['sensors'].get('occupancy', 0)}")
    
    except KeyboardInterrupt:
        logger.info("\nStopping hub...")
        hub.stop()
