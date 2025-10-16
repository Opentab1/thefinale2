"""
Pulse 1.0 - TV Control via HDMI-CEC
"""

import logging
import subprocess
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CECTVController:
    def __init__(self):
        self.auto_mode = True
        self.devices = []
        self._scan_devices()
    
    def _scan_devices(self):
        """Scan for CEC devices"""
        try:
            # Use a shell pipeline to send the scan command to cec-client
            result = subprocess.run(
                "echo scan | cec-client -s -d 1",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Parse device list
            lines = result.stdout.split('\n')
            self.devices = []
            
            for line in lines:
                if 'device #' in line.lower():
                    # Extract device info
                    # Example: "device #1: TV"
                    parts = line.split(':')
                    if len(parts) >= 2:
                        device_num = parts[0].split('#')[1].strip()
                        device_name = parts[1].strip()
                        self.devices.append({
                            "id": device_num,
                            "name": device_name
                        })
            
            logger.info(f"Found {len(self.devices)} CEC devices")
            
        except Exception as e:
            logger.error(f"Error scanning CEC devices: {e}")
    
    def _send_command(self, command: str) -> bool:
        """Send CEC command"""
        try:
            result = subprocess.run(
                f"echo '{command}' | cec-client -s -d 1",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            success = result.returncode == 0
            
            if success:
                logger.debug(f"CEC command sent: {command}")
            else:
                logger.error(f"CEC command failed: {command}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending CEC command: {e}")
            return False
    
    def power_on(self, device_id: str = "0") -> bool:
        """Power on device"""
        command = f"on {device_id}"
        success = self._send_command(command)
        
        if success:
            logger.info(f"Powered on device {device_id}")
        
        return success
    
    def power_off(self, device_id: str = "0") -> bool:
        """Power off device"""
        command = f"standby {device_id}"
        success = self._send_command(command)
        
        if success:
            logger.info(f"Powered off device {device_id}")
        
        return success
    
    def set_active_source(self) -> bool:
        """Set Raspberry Pi as active source"""
        command = "as"
        return self._send_command(command)
    
    def volume_up(self, device_id: str = "0") -> bool:
        """Increase volume"""
        command = f"volup"
        return self._send_command(command)
    
    def volume_down(self, device_id: str = "0") -> bool:
        """Decrease volume"""
        command = f"voldown"
        return self._send_command(command)
    
    def mute(self) -> bool:
        """Mute audio"""
        command = "mute"
        return self._send_command(command)
    
    def get_devices(self) -> List[Dict]:
        """Get list of CEC devices"""
        return self.devices
    
    def get_power_status(self, device_id: str = "0") -> Optional[str]:
        """Get power status of device"""
        try:
            result = subprocess.run(
                f"echo 'pow {device_id}' | cec-client -s -d 1",
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            output = result.stdout.lower()
            
            if 'power status: on' in output:
                return "on"
            elif 'power status: standby' in output or 'standby' in output:
                return "off"
            else:
                return "unknown"
                
        except Exception as e:
            logger.error(f"Error getting power status: {e}")
            return None
    
    def set_auto_mode(self, enabled: bool):
        """Enable/disable auto mode"""
        self.auto_mode = enabled
        logger.info(f"Auto mode {'enabled' if enabled else 'disabled'}")
    
    def is_auto_mode(self) -> bool:
        """Check if auto mode is enabled"""
        return self.auto_mode


class IPTVController:
    """Control TVs via network/IP (alternative to CEC)"""
    
    def __init__(self, tv_ips: List[str] = None):
        self.tv_ips = tv_ips or []
        self.auto_mode = True
    
    def add_tv(self, ip: str, name: str = None):
        """Add TV to control list"""
        self.tv_ips.append({"ip": ip, "name": name or ip})
    
    def send_wake_on_lan(self, mac_address: str) -> bool:
        """Send Wake-on-LAN packet"""
        try:
            # Create magic packet
            mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
            magic_packet = b'\xff' * 6 + mac_bytes * 16
            
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, ('<broadcast>', 9))
            sock.close()
            
            logger.info(f"Sent WoL packet to {mac_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending WoL: {e}")
            return False
    
    def power_on_samsung(self, tv_ip: str) -> bool:
        """Power on Samsung TV (network control)"""
        try:
            import requests
            
            url = f"http://{tv_ip}:8001/api/v2/applications/samsung.remote.control"
            requests.post(url, timeout=3)
            
            logger.info(f"Powered on Samsung TV at {tv_ip}")
            return True
            
        except Exception as e:
            logger.error(f"Error powering on Samsung TV: {e}")
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
    
    print("Testing CEC TV Controller...")
    
    try:
        controller = CECTVController()
        
        print(f"\nFound {len(controller.devices)} devices:")
        for device in controller.devices:
            print(f"  {device['id']}: {device['name']}")
        
        # Test power status
        if controller.devices:
            device_id = controller.devices[0]['id']
            status = controller.get_power_status(device_id)
            print(f"\nDevice {device_id} power status: {status}")
        
    except Exception as e:
        print(f"Error: {e}")
