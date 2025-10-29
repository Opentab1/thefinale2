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

# Configuration
IOT_ENDPOINT = "iot.us-east-2.amazonaws.com"  # Replace with your endpoint
CLIENT_ID = "pulse-rpi-local"
TOPIC = "pulse/sensors/data"
DB_PATH = "/workspace/services/storage/pulse.db"

# Certificate paths (will be set up by startup.sh)
CERT_DIR = Path.home() / ".pulse" / "certs"
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
        """Fetch latest sensor data from local database"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get latest readings
            cursor.execute("""
                SELECT temperature, humidity, pressure, people_count, timestamp
                FROM sensor_data
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'device_id': CLIENT_ID,
                    'timestamp': datetime.now().isoformat(),
                    'temperature': round(row[0], 2) if row[0] else None,
                    'humidity': round(row[1], 2) if row[1] else None,
                    'pressure': round(row[2], 2) if row[2] else None,
                    'people_count': row[3] or 0,
                    'last_reading': row[4]
                }
            else:
                return None
                
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        except Exception as e:
            print(f"Error fetching sensor data: {e}")
            return None
    
    def send_data(self, data):
        """Send data to AWS IoT Core"""
        if MOCK_MODE:
            print(f"📤 [MOCK] Would send to AWS IoT: {json.dumps(data, indent=2)}")
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
            print(f"📤 Sent to AWS IoT: {data['temperature']}°C, {data['people_count']} people")
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
