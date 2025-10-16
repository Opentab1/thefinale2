"""
Pulse 1.0 - Nest/Google Smart Device Management (SDM) Control
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

class NestHVACController:
    def __init__(self, project_id: str, device_id: str, 
                 client_id: str, client_secret: str, refresh_token: str):
        self.project_id = project_id
        self.device_id = device_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        
        self.base_url = "https://smartdevicemanagement.googleapis.com/v1"
        self.device_path = f"enterprises/{project_id}/devices/{device_id}"
        
        self.credentials = None
        self.auto_mode = True
        
        self._init_credentials()
    
    def _init_credentials(self):
        """Initialize Google OAuth credentials"""
        try:
            self.credentials = Credentials(
                None,
                refresh_token=self.refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_uri="https://oauth2.googleapis.com/token"
            )
            
            # Refresh if needed
            if not self.credentials.valid:
                self.credentials.refresh(Request())
            
            logger.info("Nest credentials initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize credentials: {e}")
            raise
    
    def _ensure_valid_token(self):
        """Ensure access token is valid"""
        if not self.credentials.valid:
            self.credentials.refresh(Request())
    
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make authenticated API request"""
        self._ensure_valid_token()
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.credentials.token}",
            "Content-Type": "application/json"
        }
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def get_status(self) -> Dict:
        """Get current thermostat status"""
        try:
            result = self._make_request("GET", self.device_path)
            
            traits = result.get("traits", {})
            
            # Extract relevant data
            temp_trait = traits.get("sdm.devices.traits.Temperature", {})
            humidity_trait = traits.get("sdm.devices.traits.Humidity", {})
            thermostat_trait = traits.get("sdm.devices.traits.ThermostatTemperatureSetpoint", {})
            mode_trait = traits.get("sdm.devices.traits.ThermostatMode", {})
            hvac_trait = traits.get("sdm.devices.traits.ThermostatHvac", {})
            
            # Convert Celsius to Fahrenheit
            current_temp_c = temp_trait.get("ambientTemperatureCelsius", 0)
            current_temp_f = (current_temp_c * 9/5) + 32
            
            heat_setpoint_c = thermostat_trait.get("heatCelsius", 0)
            cool_setpoint_c = thermostat_trait.get("coolCelsius", 0)
            
            status = {
                "current_temperature_f": round(current_temp_f, 1),
                "current_temperature_c": round(current_temp_c, 1),
                "humidity": humidity_trait.get("ambientHumidityPercent", 0),
                "mode": mode_trait.get("mode", "OFF"),
                "hvac_status": hvac_trait.get("status", "OFF"),
                "heat_setpoint_f": round((heat_setpoint_c * 9/5) + 32, 1),
                "cool_setpoint_f": round((cool_setpoint_c * 9/5) + 32, 1),
                "timestamp": datetime.now().isoformat()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return {}
    
    def set_mode(self, mode: str) -> bool:
        """
        Set thermostat mode
        Modes: HEAT, COOL, HEATCOOL, OFF
        """
        try:
            valid_modes = ["HEAT", "COOL", "HEATCOOL", "OFF"]
            mode = mode.upper()
            
            if mode not in valid_modes:
                raise ValueError(f"Invalid mode. Must be one of: {valid_modes}")
            
            data = {
                "command": "sdm.devices.commands.ThermostatMode.SetMode",
                "params": {"mode": mode}
            }
            
            endpoint = f"{self.device_path}:executeCommand"
            self._make_request("POST", endpoint, data)
            
            logger.info(f"Set mode to {mode}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            return False
    
    def set_temperature(self, heat_f: float = None, cool_f: float = None) -> bool:
        """Set temperature setpoints (Fahrenheit)"""
        try:
            # Convert to Celsius
            heat_c = (heat_f - 32) * 5/9 if heat_f else None
            cool_c = (cool_f - 32) * 5/9 if cool_f else None
            
            params = {}
            if heat_c is not None:
                params["heatCelsius"] = heat_c
            if cool_c is not None:
                params["coolCelsius"] = cool_c
            
            if not params:
                raise ValueError("Must provide at least one setpoint")
            
            data = {
                "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
                "params": params
            }
            
            endpoint = f"{self.device_path}:executeCommand"
            self._make_request("POST", endpoint, data)
            
            logger.info(f"Set temperature: heat={heat_f}°F, cool={cool_f}°F")
            return True
            
        except Exception as e:
            logger.error(f"Error setting temperature: {e}")
            return False
    
    def adjust_temperature(self, delta_f: float, mode: str = "auto") -> bool:
        """
        Adjust temperature by delta
        mode: 'heat', 'cool', or 'auto'
        """
        try:
            status = self.get_status()
            
            if not status:
                return False
            
            current_mode = status["mode"]
            
            if mode == "auto":
                # Determine based on current mode
                if current_mode == "HEAT":
                    new_heat = status["heat_setpoint_f"] + delta_f
                    return self.set_temperature(heat_f=new_heat)
                elif current_mode == "COOL":
                    new_cool = status["cool_setpoint_f"] + delta_f
                    return self.set_temperature(cool_f=new_cool)
                elif current_mode == "HEATCOOL":
                    new_heat = status["heat_setpoint_f"] + delta_f
                    new_cool = status["cool_setpoint_f"] + delta_f
                    return self.set_temperature(heat_f=new_heat, cool_f=new_cool)
            elif mode == "heat":
                new_heat = status["heat_setpoint_f"] + delta_f
                return self.set_temperature(heat_f=new_heat)
            elif mode == "cool":
                new_cool = status["cool_setpoint_f"] + delta_f
                return self.set_temperature(cool_f=new_cool)
            
            return False
            
        except Exception as e:
            logger.error(f"Error adjusting temperature: {e}")
            return False
    
    def turn_off(self) -> bool:
        """Turn HVAC off"""
        return self.set_mode("OFF")
    
    def set_auto_mode(self, enabled: bool):
        """Enable/disable auto mode"""
        self.auto_mode = enabled
        logger.info(f"Auto mode {'enabled' if enabled else 'disabled'}")
    
    def is_auto_mode(self) -> bool:
        """Check if auto mode is enabled"""
        return self.auto_mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example usage (requires environment variables)
    project_id = os.getenv("GOOGLE_PROJECT_ID")
    device_id = os.getenv("NEST_DEVICE_ID")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("NEST_REFRESH_TOKEN")
    
    if all([project_id, device_id, client_id, client_secret, refresh_token]):
        try:
            controller = NestHVACController(
                project_id, device_id,
                client_id, client_secret, refresh_token
            )
            
            # Get status
            status = controller.get_status()
            print("Current Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
            
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Missing required environment variables")
