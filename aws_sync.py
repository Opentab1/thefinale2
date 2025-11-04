#!/usr/bin/env python3
"""
Pulse AWS Sync Service
Reads data from Pulse SQLite database and sends to AWS IoT Core via MQTT
This file is OUTSIDE the git repo - safe to modify
"""

import os
import sys
import json
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import contextmanager

# MQTT client for AWS IoT
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip3 install paho-mqtt")
    sys.exit(1)

# SSL/TLS support
try:
    import ssl
except ImportError:
    print("ERROR: SSL support not available")
    sys.exit(1)

# Configure logging
LOG_DIR = Path("/opt/pulse/aws_sync")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PulseDBReader:
    """Read-only interface to Pulse SQLite database"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def get_latest_environment(self) -> Optional[Dict]:
        """Get most recent environmental data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM environment 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_current_occupancy(self, zone: str = None) -> Dict:
        """Get most recent occupancy data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if zone:
                cursor.execute('''
                    SELECT * FROM occupancy 
                    WHERE zone = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ''', (zone,))
            else:
                cursor.execute('''
                    SELECT * FROM occupancy 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ''')
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}
    
    def get_latest_music(self) -> Optional[Dict]:
        """Get most recent music log"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM music_log 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_recent_data(self, minutes: int = 5) -> Dict:
        """Get all recent data from last N minutes"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get latest environment
            env = self.get_latest_environment()
            
            # Get latest occupancy
            occupancy = self.get_current_occupancy()
            
            # Get latest music
            music = self.get_latest_music()
            
            return {
                'environment': env,
                'occupancy': occupancy,
                'music': music,
                'timestamp': datetime.now().isoformat()
            }


class AWSSyncService:
    """Service to sync Pulse data to AWS IoT Core via MQTT"""
    
    def __init__(self, config_path: str = "/opt/pulse/aws_sync/aws_config.env"):
        self.config = self._load_config(config_path)
        self.db_reader = PulseDBReader(self.config['PULSE_DB_PATH'])
        self.mqtt_client = None
        self.endpoint = self.config['AWS_IOT_ENDPOINT']
        self.thing_name = self.config['AWS_IOT_THING_NAME']
        self.last_sync_time = {}
        self.connected = False
        
        # Initialize MQTT client
        self._init_mqtt_client()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from environment file"""
        config = {}
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Please create it following AWS_SETUP_GUIDE.md"
            )
        
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        
        # Validate required config
        required = [
            'AWS_IOT_ENDPOINT',
            'AWS_IOT_THING_NAME',
            'AWS_IOT_CERT_PATH',
            'AWS_IOT_KEY_PATH',
            'AWS_IOT_ROOT_CA_PATH',
            'PULSE_DB_PATH'
        ]
        
        missing = [k for k in required if k not in config]
        if missing:
            raise ValueError(f"Missing required config: {missing}")
        
        # Set defaults
        config['AWS_SYNC_INTERVAL'] = int(config.get('AWS_SYNC_INTERVAL', '60'))
        
        return config
    
    def _init_mqtt_client(self):
        """Initialize MQTT client for AWS IoT Core"""
        try:
            # Verify certificates exist
            cert_path = self.config['AWS_IOT_CERT_PATH']
            key_path = self.config['AWS_IOT_KEY_PATH']
            root_ca = self.config['AWS_IOT_ROOT_CA_PATH']
            
            for path in [cert_path, key_path, root_ca]:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Certificate file not found: {path}")
            
            # Create MQTT client
            client_id = f"pulse-{self.thing_name}-{int(time.time())}"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Configure TLS
            self.mqtt_client.tls_set(
                ca_certs=root_ca,
                certfile=cert_path,
                keyfile=key_path,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_publish = self._on_publish
            
            logger.info("MQTT client initialized")
            logger.info(f"Endpoint: {self.endpoint}")
            logger.info(f"Thing: {self.thing_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.connected = True
            logger.info("✓ Connected to AWS IoT Core")
        else:
            self.connected = False
            logger.error(f"Failed to connect to AWS IoT: Return code {rc}")
            if rc == 1:
                logger.error("  → Incorrect protocol version")
            elif rc == 2:
                logger.error("  → Invalid client identifier")
            elif rc == 3:
                logger.error("  → Server unavailable")
            elif rc == 4:
                logger.error("  → Bad username or password")
            elif rc == 5:
                logger.error("  → Not authorized - check IoT policy")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from AWS IoT (rc={rc})")
        else:
            logger.info("Disconnected from AWS IoT")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published (mid={mid})")
    
    def _ensure_connected(self):
        """Ensure MQTT connection is active"""
        if not self.connected or not self.mqtt_client.is_connected():
            try:
                logger.info("Connecting to AWS IoT Core...")
                self.mqtt_client.connect(self.endpoint, port=8883, keepalive=60)
                self.mqtt_client.loop_start()
                # Wait for connection
                timeout = 10
                start = time.time()
                while not self.connected and (time.time() - start) < timeout:
                    time.sleep(0.1)
                if not self.connected:
                    raise Exception("Connection timeout")
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                return False
        return True
    
    def _publish_to_iot(self, topic: str, payload: Dict):
        """Publish message to AWS IoT Core via MQTT"""
        try:
            # Ensure connected
            if not self._ensure_connected():
                return False
            
            # Convert payload to JSON
            message = json.dumps(payload)
            
            # Publish with QoS 1 (at least once delivery)
            result = self.mqtt_client.publish(topic, message, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}")
                return True
            else:
                logger.error(f"Publish failed with return code: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to publish to AWS IoT: {e}")
            return False
    
    def sync_data(self):
        """Sync current sensor data to AWS"""
        try:
            # Collect data
            data = self.db_reader.get_recent_data(minutes=5)
            
            # Format payload
            payload = {
                'device_id': self.thing_name,
                'timestamp': datetime.now().isoformat(),
                'occupancy': None,
                'temperature_f': None,
                'humidity': None,
                'pressure': None,
                'light_level': None,
                'noise_level': None,
                'current_song': None
            }
            
            # Extract environment data
            env = data.get('environment')
            if env:
                payload['temperature_f'] = env.get('temperature')
                payload['humidity'] = env.get('humidity')
                payload['pressure'] = env.get('pressure')
                payload['light_level'] = env.get('light_level')
                payload['noise_level'] = env.get('noise_level')
            
            # Extract occupancy
            occ = data.get('occupancy')
            if occ:
                payload['occupancy'] = occ.get('count')
                payload['entry_count'] = occ.get('entry_count', 0)
                payload['exit_count'] = occ.get('exit_count', 0)
                payload['zone'] = occ.get('zone')
            
            # Extract music
            music = data.get('music')
            if music:
                payload['current_song'] = {
                    'title': music.get('track_name'),
                    'artist': music.get('artist'),
                    'volume': music.get('volume'),
                    'source': music.get('source')
                }
            
            # Publish to AWS IoT
            topic = f"pulse/sensor-data"
            success = self._publish_to_iot(topic, payload)
            
            if success:
                logger.info(f"✓ Synced data to AWS: {payload.get('occupancy')} people, {payload.get('temperature_f')}°F")
            else:
                logger.warning("Failed to sync data to AWS")
            
            return success
            
        except Exception as e:
            logger.error(f"Error syncing data: {e}", exc_info=True)
            return False
    
    def test_connection(self):
        """Test AWS IoT connection"""
        logger.info("Testing AWS IoT connection...")
        
        try:
            # Test database access
            env = self.db_reader.get_latest_environment()
            logger.info(f"✓ Database accessible: {env is not None}")
            if env:
                logger.info(f"  Latest temp: {env.get('temperature')}°F")
            
            # Test MQTT connection
            logger.info("Testing MQTT connection to AWS IoT...")
            if self._ensure_connected():
                logger.info("✓ AWS IoT connection successful!")
                
                # Test publish
                test_payload = {
                    'device_id': self.thing_name,
                    'timestamp': datetime.now().isoformat(),
                    'test': True,
                    'message': 'Connection test'
                }
                if self._publish_to_iot('pulse/test', test_payload):
                    logger.info("✓ Test message published successfully")
                    return True
                else:
                    logger.warning("Connection OK but publish failed")
                    return False
            else:
                logger.error("✗ Failed to connect to AWS IoT")
                return False
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def run(self):
        """Main sync loop"""
        logger.info("="*80)
        logger.info("PULSE AWS SYNC SERVICE STARTING")
        logger.info("="*80)
        logger.info(f"Device: {self.thing_name}")
        logger.info(f"Endpoint: {self.endpoint}")
        logger.info(f"Database: {self.config['PULSE_DB_PATH']}")
        logger.info(f"Sync Interval: {self.config['AWS_SYNC_INTERVAL']}s")
        logger.info("="*80)
        
        # Connect to AWS IoT
        if not self._ensure_connected():
            logger.error("Failed to connect to AWS IoT. Exiting.")
            return
        
        interval = self.config['AWS_SYNC_INTERVAL']
        
        try:
            sync_count = 0
            while True:
                sync_count += 1
                logger.info(f"\n--- Sync #{sync_count} ---")
                
                success = self.sync_data()
                
                if not success:
                    logger.warning("Sync failed, will retry on next interval")
                    # Try to reconnect
                    self.mqtt_client.loop_stop()
                    self.connected = False
                    time.sleep(5)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\nShutting down AWS sync service...")
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            if self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            raise


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pulse AWS Sync Service')
    parser.add_argument('--test', action='store_true', help='Test connection only')
    parser.add_argument('--config', default='/opt/pulse/aws_sync/aws_config.env',
                       help='Path to config file')
    
    args = parser.parse_args()
    
    try:
        service = AWSSyncService(config_path=args.config)
        
        if args.test:
            service.test_connection()
        else:
            service.run()
            
    except Exception as e:
        logger.error(f"Service failed to start: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
