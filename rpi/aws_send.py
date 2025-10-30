#!/usr/bin/env python3
"""
AWS IoT Core Data Sender
Sends sensor data to AWS IoT Core every 30 seconds
NO Amplify, NO Cognito - Just IoT Core MQTT
"""

import json
import time
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    from awscrt import io, mqtt
    from awsiot import mqtt_connection_builder
except ImportError:
    print("⚠️  AWS IoT SDK not installed. Install with: pip3 install awsiotsdk")
    print("Falling back to mock mode...")
    MOCK_MODE = True
else:
    MOCK_MODE = False

# Configuration (EXACT VALUES PROVIDED)
IOT_ENDPOINT = "a1h5tm3jvbz8cg-ats.iot.us-east-2.amazonaws.com"
CLIENT_ID = "pulse-fergs-stpete-main-floor-rpi5"
TOPIC = "pulse/fergs-stpete/main-floor"

# Default database path for production on RPi
DB_PATH = "/opt/pulse/data/pulse.db"

# Location metadata (EXACT VALUES PROVIDED)
VENUE_ID = "fergs-stpete"
LOCATION_ID = "main-floor"

# Certificate paths
CERT_DIR = Path("/etc/pulse/certs")
ROOT_CA = CERT_DIR / "AmazonRootCA1.pem"
CERT = CERT_DIR / "device.pem.crt"
PRIVATE_KEY = CERT_DIR / "private.pem.key"

class AWSIoTSender:
    """Send sensor data to AWS IoT Core"""
    
    def __init__(self):
        self.connected = False
        self.mqtt_connection = None
        
        if not MOCK_MODE:
            self.setup_connection()
    
    def setup_connection(self):
        """Initialize MQTT connection to AWS IoT Core"""
        try:
            # Check if certificates exist
            if not all([ROOT_CA.exists(), CERT.exists(), PRIVATE_KEY.exists()]):
                print("⚠️  AWS IoT certificates not found at:")
                print(f"   {CERT_DIR}")
                print("   Run setup first: rpi/startup.sh")
                return
            
            # Create MQTT connection
            event_loop_group = io.EventLoopGroup(1)
            host_resolver = io.DefaultHostResolver(event_loop_group)
            client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
            
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=IOT_ENDPOINT,
                cert_filepath=str(CERT),
                pri_key_filepath=str(PRIVATE_KEY),
                client_bootstrap=client_bootstrap,
                ca_filepath=str(ROOT_CA),
                client_id=CLIENT_ID,
                clean_session=False,
                keep_alive_secs=30
            )
            
            # Connect
            print(f"🔌 Connecting to AWS IoT Core: {IOT_ENDPOINT}")
            connect_future = self.mqtt_connection.connect()
            connect_future.result()
            self.connected = True
            print("✅ Connected to AWS IoT Core")
            
        except Exception as e:
            print(f"❌ Failed to connect to AWS IoT: {e}")
            self.connected = False
    
    def get_sensor_data(self):
        """Fetch latest sensor data from local database (PulseDB schema) and normalize payload"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Occupancy (most recent)
            cursor.execute(
                """
                SELECT count, timestamp
                FROM occupancy
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            occ_row = cursor.fetchone()
            occupancy = int(occ_row[0]) if occ_row and occ_row[0] is not None else 0

            # Environment (most recent)
            cursor.execute(
                """
                SELECT temperature, humidity, light_level, noise_level, timestamp
                FROM environment
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            env_row = cursor.fetchone()
            temperature_f = env_row[0] if env_row else None
            humidity = env_row[1] if env_row else None
            light_level = env_row[2] if env_row else None
            noise_db = env_row[3] if env_row else None
            last_ts = env_row[4] if env_row else None

            # Music (most recent)
            cursor.execute(
                """
                SELECT track_name, artist
                FROM music_log
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            song_row = cursor.fetchone()
            current_song = None
            if song_row:
                title = song_row[0] or None
                artist = song_row[1] or None
                if title or artist:
                    current_song = {"title": title, "artist": artist}

            conn.close()

            # If we have at least occupancy or any environment metric, build payload
            if any(v is not None for v in (temperature_f, humidity, light_level, noise_db)) or occupancy is not None:
                payload = {
                    "venue_id": VENUE_ID,
                    "location_id": LOCATION_ID,
                    "device_id": CLIENT_ID,
                    "timestamp": datetime.now().isoformat(),
                    "occupancy": int(occupancy or 0),
                    "temperature_f": round(float(temperature_f), 1) if temperature_f is not None else None,
                    "humidity": round(float(humidity), 1) if humidity is not None else None,
                    "light_level": round(float(light_level), 0) if light_level is not None else None,
                    "noise_db": round(float(noise_db), 1) if noise_db is not None else None,
                    "current_song": current_song,
                    "camera_active": None,
                    "last_reading": last_ts,
                    "source": "rpi"
                }
                return payload
            else:
                return None

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        except Exception as e:
            print(f"Error fetching sensor data: {e}")
            return None
    
    def send_data(self, data):
        """Send data to AWS IoT Core on the exact topic"""
        if MOCK_MODE:
            print(f"📤 [MOCK] Would send to AWS IoT topic '{TOPIC}': {json.dumps(data, indent=2)}")
            return True
        
        if not self.connected:
            print("⚠️  Not connected to AWS IoT Core")
            return False
        
        try:
            payload = json.dumps(data)
            self.mqtt_connection.publish(
                topic=TOPIC,
                payload=payload,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            temp_display = data.get('temperature_f')
            occ_display = data.get('occupancy')
            print(f"📤 Sent to AWS IoT [{TOPIC}]: temp={temp_display}F, occupancy={occ_display}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to publish: {e}")
            return False
    
    def run(self, interval=30):
        """Main loop - send data every interval seconds"""
        print(f"🚀 Starting AWS IoT sender (interval: {interval}s)")
        
        while True:
            try:
                # Get data
                data = self.get_sensor_data()
                
                if data:
                    self.send_data(data)
                else:
                    print("⚠️  No sensor data available")
                
                # Wait for next interval
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n👋 Stopping AWS IoT sender...")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(interval)
        
        # Cleanup
        if self.mqtt_connection and self.connected:
            print("Disconnecting from AWS IoT Core...")
            disconnect_future = self.mqtt_connection.disconnect()
            disconnect_future.result()
    
    def disconnect(self):
        """Disconnect from AWS IoT Core"""
        if self.mqtt_connection and self.connected:
            disconnect_future = self.mqtt_connection.disconnect()
            disconnect_future.result()
            self.connected = False

def main():
    """Entry point"""
    sender = AWSIoTSender()
    
    try:
        sender.run(interval=30)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        sender.disconnect()

if __name__ == '__main__':
    main()
