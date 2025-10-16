"""
Pulse 1.0 - Philips Hue Lighting Control
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import math

logger = logging.getLogger(__name__)

class HueLightingController:
    def __init__(self, bridge_ip: str, username: str = None):
        self.bridge_ip = bridge_ip
        self.username = username
        self.bridge = None
        self.auto_mode = True
        
        self._init_bridge()
    
    def _init_bridge(self):
        """Initialize Hue Bridge connection"""
        try:
            from phue import Bridge
            
            self.bridge = Bridge(self.bridge_ip, username=self.username)
            
            # If no username, this will prompt for button press
            if not self.username:
                self.bridge.connect()
                self.username = self.bridge.username
                logger.info(f"Connected to Hue Bridge, username: {self.username}")
            
            logger.info(f"Hue Bridge initialized at {self.bridge_ip}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Hue Bridge: {e}")
            raise
    
    def get_lights(self) -> Dict:
        """Get all lights"""
        try:
            lights = {}
            for light_id in self.bridge.lights:
                light = self.bridge.get_light(light_id)
                lights[light_id] = {
                    "name": light.get("name"),
                    "on": light.get("state", {}).get("on", False),
                    "brightness": light.get("state", {}).get("bri", 0),
                    "hue": light.get("state", {}).get("hue"),
                    "saturation": light.get("state", {}).get("sat"),
                    "reachable": light.get("state", {}).get("reachable", False)
                }
            
            return lights
            
        except Exception as e:
            logger.error(f"Error getting lights: {e}")
            return {}
    
    def get_light_status(self, light_id: int) -> Dict:
        """Get status of a specific light"""
        try:
            light = self.bridge.get_light(light_id)
            state = light.get("state", {})
            
            return {
                "id": light_id,
                "name": light.get("name"),
                "on": state.get("on", False),
                "brightness": state.get("bri", 0),
                "brightness_pct": round((state.get("bri", 0) / 254) * 100),
                "hue": state.get("hue"),
                "saturation": state.get("sat"),
                "color_temp": state.get("ct"),
                "reachable": state.get("reachable", False),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting light status: {e}")
            return {}
    
    def set_light(self, light_id: int, on: bool = None, brightness: int = None,
                  hue: int = None, saturation: int = None, color_temp: int = None) -> bool:
        """
        Control a specific light
        brightness: 0-254
        hue: 0-65535
        saturation: 0-254
        color_temp: 153-500 (mireds)
        """
        try:
            command = {}
            
            if on is not None:
                command["on"] = on
            
            if brightness is not None:
                command["bri"] = max(0, min(254, brightness))
            
            if hue is not None:
                command["hue"] = max(0, min(65535, hue))
            
            if saturation is not None:
                command["sat"] = max(0, min(254, saturation))
            
            if color_temp is not None:
                command["ct"] = max(153, min(500, color_temp))
            
            if command:
                self.bridge.set_light(light_id, command)
                logger.info(f"Light {light_id} updated: {command}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error setting light: {e}")
            return False
    
    def set_brightness_pct(self, light_id: int, brightness_pct: int) -> bool:
        """Set brightness as percentage (0-100)"""
        brightness = int((brightness_pct / 100) * 254)
        return self.set_light(light_id, brightness=brightness)
    
    def set_all_lights(self, on: bool = None, brightness: int = None) -> bool:
        """Control all lights"""
        try:
            success = True
            for light_id in self.bridge.lights:
                if not self.set_light(light_id, on=on, brightness=brightness):
                    success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error setting all lights: {e}")
            return False
    
    def set_rgb_color(self, light_id: int, r: int, g: int, b: int) -> bool:
        """Set color using RGB values (0-255)"""
        try:
            # Convert RGB to HSV
            r_norm = r / 255.0
            g_norm = g / 255.0
            b_norm = b / 255.0
            
            max_val = max(r_norm, g_norm, b_norm)
            min_val = min(r_norm, g_norm, b_norm)
            diff = max_val - min_val
            
            # Calculate hue
            if diff == 0:
                hue_norm = 0
            elif max_val == r_norm:
                hue_norm = ((g_norm - b_norm) / diff) % 6
            elif max_val == g_norm:
                hue_norm = ((b_norm - r_norm) / diff) + 2
            else:
                hue_norm = ((r_norm - g_norm) / diff) + 4
            
            hue_norm = hue_norm / 6.0
            
            # Calculate saturation
            if max_val == 0:
                sat_norm = 0
            else:
                sat_norm = diff / max_val
            
            # Convert to Hue ranges
            hue_hue = int(hue_norm * 65535)
            sat_hue = int(sat_norm * 254)
            
            return self.set_light(light_id, hue=hue_hue, saturation=sat_hue)
            
        except Exception as e:
            logger.error(f"Error setting RGB color: {e}")
            return False
    
    def set_scene(self, scene_name: str) -> bool:
        """
        Set a predefined scene
        Scenes: 'energize', 'concentrate', 'relax', 'reading', 'bright', 'dim'
        """
        try:
            scenes = {
                "energize": {"bri": 254, "ct": 156},  # Cool, bright
                "concentrate": {"bri": 219, "ct": 233},  # Cool, moderate
                "relax": {"bri": 144, "ct": 467},  # Warm, dim
                "reading": {"bri": 240, "ct": 346},  # Warm, bright
                "bright": {"bri": 254, "ct": 300},  # Neutral, bright
                "dim": {"bri": 77, "ct": 400},  # Warm, very dim
                "evening": {"bri": 150, "ct": 450},  # Warm, moderate
                "night": {"bri": 30, "ct": 500}  # Very warm, very dim
            }
            
            scene = scenes.get(scene_name.lower())
            if not scene:
                logger.warning(f"Unknown scene: {scene_name}")
                return False
            
            for light_id in self.bridge.lights:
                self.set_light(light_id, on=True, brightness=scene["bri"], 
                             color_temp=scene["ct"])
            
            logger.info(f"Set scene: {scene_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting scene: {e}")
            return False
    
    def set_circadian(self, hour_24: int) -> bool:
        """
        Set lighting based on circadian rhythm
        Adjusts color temperature and brightness based on time of day
        """
        try:
            # Morning (6-12): Gradually increase brightness and cool temp
            # Afternoon (12-18): Bright and cool
            # Evening (18-22): Gradually decrease and warm up
            # Night (22-6): Dim and very warm
            
            if 6 <= hour_24 < 12:
                # Morning
                progress = (hour_24 - 6) / 6
                brightness = int(77 + (177 * progress))  # 77 to 254
                color_temp = int(500 - (250 * progress))  # 500 to 250
            elif 12 <= hour_24 < 18:
                # Afternoon
                brightness = 254
                color_temp = 250
            elif 18 <= hour_24 < 22:
                # Evening
                progress = (hour_24 - 18) / 4
                brightness = int(254 - (177 * progress))  # 254 to 77
                color_temp = int(250 + (250 * progress))  # 250 to 500
            else:
                # Night
                brightness = 30
                color_temp = 500
            
            for light_id in self.bridge.lights:
                self.set_light(light_id, on=True, brightness=brightness, 
                             color_temp=color_temp)
            
            logger.info(f"Set circadian lighting for hour {hour_24}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting circadian: {e}")
            return False
    
    def adjust_brightness(self, light_id: int, delta_pct: int) -> bool:
        """Adjust brightness by percentage"""
        try:
            status = self.get_light_status(light_id)
            current_pct = status.get("brightness_pct", 50)
            new_pct = max(0, min(100, current_pct + delta_pct))
            
            return self.set_brightness_pct(light_id, new_pct)
            
        except Exception as e:
            logger.error(f"Error adjusting brightness: {e}")
            return False
    
    def set_auto_mode(self, enabled: bool):
        """Enable/disable auto mode"""
        self.auto_mode = enabled
        logger.info(f"Auto mode {'enabled' if enabled else 'disabled'}")
    
    def is_auto_mode(self) -> bool:
        """Check if auto mode is enabled"""
        return self.auto_mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    import os
    bridge_ip = os.getenv("HUE_BRIDGE_IP")
    username = os.getenv("HUE_USERNAME")
    
    if bridge_ip:
        try:
            controller = HueLightingController(bridge_ip, username)
            
            # Get all lights
            lights = controller.get_lights()
            print("Available lights:")
            for light_id, info in lights.items():
                print(f"  {light_id}: {info['name']} - {'ON' if info['on'] else 'OFF'}")
            
            # Test scene
            print("\nSetting 'relax' scene...")
            controller.set_scene("relax")
            
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("HUE_BRIDGE_IP environment variable not set")
