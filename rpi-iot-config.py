#!/usr/bin/env python3
"""
Raspberry Pi 5 → AWS IoT Core Integration
Publishes sensor data from Pulse system to AWS IoT for dashboard consumption
"""

import json
import time
import sys
from pathlib import Path

# AWS IoT Configuration
IOT_CONFIG = {
    "endpoint": "a1h5tm3jvbz8cg-ats.iot.us-east-2.amazonaws.com",
    "region": "us-east-2",
    "client_id": "pulse-fergs-stpete-main-floor-rpi5",
    "cert_path": "/etc/pulse/certs/",  # Store certificates here
    "topics": {
        # EXACT TOPIC PROVIDED (no suffix!)
        "sensors": "pulse/fergs-stpete/main-floor",
        "controls": "pulse/fergs-stpete/main-floor/controls",
        "status": "pulse/fergs-stpete/main-floor/status"
    },
    "venue_id": "fergs-stpete",
    "location_id": "main-floor",
}

def setup_iot_client():
    """
    Initialize AWS IoT MQTT client
    Requires:
    - Device certificate
    - Private key
    - Amazon Root CA
    """
    try:
        from awscrt import io, mqtt
        from awsiot import mqtt_connection_builder
        
        # Event callbacks
        def on_connection_success(connection, callback_data):
            print(f"✓ Connected to AWS IoT Core")
        
        def on_connection_failure(connection, callback_data):
            print(f"✗ Connection failed: {callback_data}")
        
        def on_connection_closed(connection, callback_data):
            print("Connection closed")
        
        # Build MQTT connection
        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=IOT_CONFIG["endpoint"],
            cert_filepath=f"{IOT_CONFIG['cert_path']}/device.pem.crt",
            pri_key_filepath=f"{IOT_CONFIG['cert_path']}/private.pem.key",
            ca_filepath=f"{IOT_CONFIG['cert_path']}/AmazonRootCA1.pem",
            client_id=IOT_CONFIG["client_id"],
            clean_session=False,
            keep_alive_secs=30,
            on_connection_success=on_connection_success,
            on_connection_failure=on_connection_failure,
            on_connection_closed=on_connection_closed
        )
        
        # Connect
        connect_future = mqtt_connection.connect()
        connect_future.result()
        
        return mqtt_connection
        
    except ImportError:
        print("ERROR: AWS IoT SDK not installed")
        print("Install with: pip install awsiotsdk")
        return None
    except Exception as e:
        print(f"ERROR: Failed to setup IoT client: {e}")
        return None

def publish_sensor_data(mqtt_connection, sensor_data):
    """
    Publish sensor data to AWS IoT
    """
    if not mqtt_connection:
        return
    
    topic = IOT_CONFIG["topics"]["sensors"]
    message = json.dumps(sensor_data)
    
    try:
        mqtt_connection.publish(
            topic=topic,
            payload=message,
            qos=mqtt.QoS.AT_LEAST_ONCE
        )
        print(f"Published to {topic}: {message}")
    except Exception as e:
        print(f"ERROR: Failed to publish: {e}")

def main():
    """
    Main IoT publishing loop
    Reads from Pulse sensor systems and publishes to AWS IoT
    """
    print("=== Pulse RPi → AWS IoT Bridge ===")
    print(f"Region: {IOT_CONFIG['region']}")
    print(f"Endpoint: {IOT_CONFIG['endpoint']}")
    print(f"Topic: {IOT_CONFIG['topics']['sensors']}")
    print()
    
    # Setup connection
    mqtt_connection = setup_iot_client()
    
    if not mqtt_connection:
        print("Failed to establish IoT connection. Exiting.")
        sys.exit(1)
    
    # Main loop - publish sensor data every 2 seconds
    try:
        while True:
            # Simulated data in schema expected by dashboard
            sensor_data = {
                "venue_id": IOT_CONFIG["venue_id"],
                "location_id": IOT_CONFIG["location_id"],
                "device_id": IOT_CONFIG["client_id"],
                "timestamp": int(time.time() * 1000),
                "occupancy": 0,
                "temperature_f": 72.0,
                "humidity": 45.0,
                "light_level": 0,
                "noise_db": 0.0,
                "current_song": {
                    "title": "No song detected",
                    "artist": "",
                    "detected": False
                },
                "camera_active": False,
                "source": "rpi"
            }
            
            publish_sensor_data(mqtt_connection, sensor_data)
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        if mqtt_connection:
            disconnect_future = mqtt_connection.disconnect()
            disconnect_future.result()
        print("Disconnected from AWS IoT")

if __name__ == "__main__":
    main()
