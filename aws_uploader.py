#!/usr/bin/env python3
"""
Pulse AWS IoT Uploader
Reads sensor data from local SQLite database and sends to AWS IoT Core.
This runs independently and does NOT modify any git-tracked files.
"""

import json
import os
import sys
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

try:
    from awscrt import io, mqtt, auth
    from awsiot import mqtt_connection_builder
    HAS_AWS_SDK = True
except ImportError:
    HAS_AWS_SDK = False
    print("ERROR: awsiotsdk not installed. Run: pip3 install awsiotsdk")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/pulse/aws_uploader.log')
    ]
)
logger = logging.getLogger(__name__)


class PulseAWSUploader:
    def __init__(self, config_path: str = "/opt/pulse/aws/config.json"):
        """Initialize AWS uploader with configuration"""
        self.config = self._load_config(config_path)
        self.db_path = self._find_database()
        self.mqtt_connection = None
        self.running = False
        self.last_upload_time = None
        
        # Ensure log directory exists
        os.makedirs('/var/log/pulse', exist_ok=True)
        
        logger.info("="*80)
        logger.info("PULSE AWS UPLOADER INITIALIZING")
        logger.info("="*80)
        logger.info(f"Database: {self.db_path}")
        logger.info(f"AWS Endpoint: {self.config['endpoint']}")
        logger.info(f"Topic: {self.config['topic']}")
        logger.info(f"Upload Interval: {self.config['upload_interval_seconds']}s")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            required = ['endpoint', 'thing_name', 'certificate_path', 
                       'private_key_path', 'root_ca_path', 'topic']
            for field in required:
                if field not in config:
                    raise ValueError(f"Missing required config field: {field}")
            
            # Set defaults
            config.setdefault('upload_interval_seconds', 30)
            
            return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            logger.error("Please create /opt/pulse/aws/config.json")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def _find_database(self) -> str:
        """Find the Pulse database location"""
        # Try common locations
        possible_paths = [
            "/opt/pulse/data/pulse.db",
            os.path.expanduser("~/pulse/data/pulse.db"),
            os.path.join(os.path.dirname(__file__), "..", "data", "pulse.db"),
            "/workspace/data/pulse.db",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found database at: {path}")
                return path
        
        # Try to find it by checking parent directories
        for base in ["/opt/pulse", "/workspace", os.path.expanduser("~")]:
            for root, dirs, files in os.walk(base):
                if 'pulse.db' in files:
                    found = os.path.join(root, 'pulse.db')
                    logger.info(f"Found database at: {found}")
                    return found
        
        logger.error("Could not find pulse.db database!")
        logger.error("Searched in:")
        for path in possible_paths:
            logger.error(f"  - {path}")
        sys.exit(1)
    
    def _connect_aws(self) -> bool:
        """Connect to AWS IoT Core using MQTT"""
        try:
            logger.info("Connecting to AWS IoT Core...")
            
            # Setup event loop group and host resolver
            event_loop_group = io.EventLoopGroup(1)
            host_resolver = io.DefaultHostResolver(event_loop_group)
            client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
            
            # Build MQTT connection
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.config['endpoint'],
                cert_filepath=self.config['certificate_path'],
                pri_key_filepath=self.config['private_key_path'],
                ca_filepath=self.config['root_ca_path'],
                client_bootstrap=client_bootstrap,
                client_id=self.config['thing_name'],
                clean_session=False,
                keep_alive_secs=30
            )
            
            # Connect
            connect_future = self.mqtt_connection.connect()
            connect_future.result(timeout=10)
            
            logger.info("✓ Connected to AWS IoT Core")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to connect to AWS IoT Core: {e}")
            logger.error("Check your certificates and endpoint configuration")
            return False
    
    def _disconnect_aws(self):
        """Disconnect from AWS IoT Core"""
        if self.mqtt_connection:
            try:
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result(timeout=5)
                logger.info("Disconnected from AWS IoT Core")
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")
    
    def _read_latest_sensor_data(self) -> Optional[Dict]:
        """Read the most recent sensor data from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            data = {
                "timestamp": datetime.now().isoformat(),
                "device_id": self.config['thing_name'],
                "sensors": {}
            }
            
            # Get latest occupancy
            cursor.execute('''
                SELECT count, entry_count, exit_count 
                FROM occupancy 
                ORDER BY timestamp DESC 
                LIMIT 1
            ''')
            occ_row = cursor.fetchone()
            if occ_row:
                data["sensors"]["occupancy"] = occ_row["count"]
                data["sensors"]["entry_count"] = occ_row["entry_count"]
                data["sensors"]["exit_count"] = occ_row["exit_count"]
            
            # Get latest environment data
            cursor.execute('''
                SELECT temperature, humidity, pressure, light_level, noise_level
                FROM environment
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            env_row = cursor.fetchone()
            if env_row:
                if env_row["temperature"] is not None:
                    data["sensors"]["temperature_f"] = env_row["temperature"]
                if env_row["humidity"] is not None:
                    data["sensors"]["humidity"] = env_row["humidity"]
                if env_row["pressure"] is not None:
                    data["sensors"]["pressure"] = env_row["pressure"]
                if env_row["light_level"] is not None:
                    data["sensors"]["light_level"] = env_row["light_level"]
                if env_row["noise_level"] is not None:
                    data["sensors"]["noise_db"] = env_row["noise_level"]
            
            # Get latest song
            cursor.execute('''
                SELECT track_name, artist
                FROM music_log
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            song_row = cursor.fetchone()
            if song_row and song_row["track_name"]:
                data["sensors"]["current_song"] = {
                    "title": song_row["track_name"],
                    "artist": song_row["artist"] or "Unknown"
                }
            
            conn.close()
            
            # Only return if we have at least some data
            if data["sensors"]:
                return data
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading sensor data: {e}")
            return None
    
    def _send_to_aws(self, data: Dict) -> bool:
        """Send data to AWS IoT Core"""
        try:
            message_json = json.dumps(data)
            message_bytes = message_json.encode('utf-8')
            
            publish_future, packet_id = self.mqtt_connection.publish(
                topic=self.config['topic'],
                payload=message_bytes,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            
            publish_future.result(timeout=5)
            logger.debug(f"✓ Sent data to AWS (message ID: {packet_id})")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to send data to AWS: {e}")
            return False
    
    def _upload_cycle(self):
        """Single upload cycle: read data and send to AWS"""
        try:
            # Read latest sensor data
            data = self._read_latest_sensor_data()
            
            if not data:
                logger.debug("No sensor data available yet")
                return
            
            # Send to AWS
            if self._send_to_aws(data):
                self.last_upload_time = datetime.now()
                logger.info(f"✓ Uploaded sensor data: "
                          f"temp={data['sensors'].get('temperature_f', 'N/A')}°F, "
                          f"occupancy={data['sensors'].get('occupancy', 0)}")
            else:
                logger.warning("Failed to upload data to AWS")
                
        except Exception as e:
            logger.error(f"Error in upload cycle: {e}")
    
    def start(self):
        """Start the uploader service"""
        logger.info("="*80)
        logger.info("STARTING AWS UPLOADER")
        logger.info("="*80)
        
        # Connect to AWS
        if not self._connect_aws():
            logger.error("Failed to connect to AWS. Exiting.")
            sys.exit(1)
        
        self.running = True
        upload_interval = self.config['upload_interval_seconds']
        
        logger.info(f"Uploader started. Uploading every {upload_interval} seconds.")
        logger.info("Press Ctrl+C to stop.")
        logger.info("="*80)
        
        try:
            while self.running:
                self._upload_cycle()
                time.sleep(upload_interval)
                
        except KeyboardInterrupt:
            logger.info("\n" + "="*80)
            logger.info("STOPPING AWS UPLOADER - User Interrupt")
            logger.info("="*80)
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop the uploader service"""
        self.running = False
        self._disconnect_aws()
        logger.info("AWS Uploader stopped")


def main():
    """Main entry point"""
    try:
        uploader = PulseAWSUploader()
        uploader.start()
    except Exception as e:
        logger.error(f"Failed to start uploader: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
