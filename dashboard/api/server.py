"""
Pulse 1.0 - Dashboard API Server
Flask + SocketIO backend for real-time dashboard
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask import send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from threading import Thread
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.storage.db import PulseDB
from services.sensors.health_monitor import HealthMonitor

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../ui/build', static_url_path='')
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'pulse-development-key')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Initialize database and health monitor
db = PulseDB()
health_monitor = HealthMonitor()

# Global hub instance (will be set by main)
hub_instance = None

def set_hub_instance(hub):
    """Set the hub instance for API access"""
    global hub_instance
    hub_instance = hub


# ===== REST API Routes =====

@app.route('/')
def index():
    """Serve React app"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/status')
def get_status():
    """Get current system status"""
    try:
        if hub_instance:
            status = hub_instance.get_status()
        else:
            status = {
                "running": False,
                "sensors": {},
                "modules": {},
                "controllers": {}
            }
        
        # Add system stats
        stats = health_monitor.get_system_stats()
        status["system"] = stats
        
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/sensors/current')
def get_current_sensors():
    """Get current sensor readings"""
    try:
        if hub_instance:
            data = hub_instance._collect_sensor_data()
        else:
            # Fallback: derive current snapshot from database
            data = {
                "occupancy": db.get_current_occupancy(),
                "temperature_f": None,
                "humidity": None,
                "light_level": None,
                "noise_db": None,
                "current_song": None,
            }

            env = db.get_latest_environment()
            if env:
                data.update({
                    "temperature_f": env.get("temperature"),
                    "humidity": env.get("humidity"),
                    "light_level": env.get("light_level"),
                    "noise_db": env.get("noise_level"),
                })

            # Last played song from music_log (if any)
            try:
                with db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT track_name, artist FROM music_log ORDER BY timestamp DESC LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        data["current_song"] = {"title": row[0], "artist": row[1]}
                    else:
                        data["current_song"] = {"title": None, "artist": None}
            except Exception:
                data["current_song"] = {"title": None, "artist": None}
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting sensors: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/occupancy/current')
def get_current_occupancy():
    """Get current occupancy"""
    try:
        count = db.get_current_occupancy()
        return jsonify({"count": count, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"Error getting occupancy: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/occupancy/history')
def get_occupancy_history():
    """Get occupancy history"""
    try:
        hours = request.args.get('hours', default=24, type=int)
        data = db.get_hourly_occupancy(hours)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting occupancy history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/environment/current')
def get_current_environment():
    """Get current environmental data"""
    try:
        data = db.get_latest_environment()
        return jsonify(data or {})
    except Exception as e:
        logger.error(f"Error getting environment: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/environment/trends')
def get_environment_trends():
    """Get environmental trends"""
    try:
        hours = request.args.get('hours', default=24, type=int)
        data = db.get_environment_trends(hours)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/automation/recent')
def get_recent_automations():
    """Get recent automation actions"""
    try:
        limit = request.args.get('limit', default=50, type=int)
        data = db.get_recent_automations(limit)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting automations: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/health')
def get_health():
    """Get system health status"""
    try:
        status = health_monitor.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/camera/snapshot')
def camera_snapshot():
    """Serve the latest camera snapshot if available"""
    try:
        snapshot_path = Path('/opt/pulse/data/latest_camera.jpg')
        if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
            # Set cache control headers to avoid stale images
            return send_file(str(snapshot_path), mimetype='image/jpeg', max_age=0)
        return ("No snapshot", 404)
    except Exception as e:
        logger.error(f"Error serving snapshot: {e}")
        return ("Error", 500)


# ===== Control API Routes =====

@app.route('/api/hvac/status', methods=['GET'])
def get_hvac_status():
    """Get HVAC status"""
    try:
        if hub_instance and hub_instance.hvac_controller:
            status = hub_instance.hvac_controller.get_status()
            status["auto_mode"] = hub_instance.hvac_controller.is_auto_mode()
            return jsonify(status)
        return jsonify({"error": "HVAC not available"}), 404
    except Exception as e:
        logger.error(f"Error getting HVAC status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/hvac/mode', methods=['POST'])
def set_hvac_mode():
    """Set HVAC mode"""
    try:
        if not hub_instance or not hub_instance.hvac_controller:
            return jsonify({"error": "HVAC not available"}), 404
        
        mode = request.json.get('mode')
        success = hub_instance.hvac_controller.set_mode(mode)
        
        if success:
            db.log_automation("hvac", f"Set mode to {mode}", "Manual control")
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error setting HVAC mode: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/hvac/temperature', methods=['POST'])
def set_hvac_temperature():
    """Set HVAC temperature"""
    try:
        if not hub_instance or not hub_instance.hvac_controller:
            return jsonify({"error": "HVAC not available"}), 404
        
        heat_f = request.json.get('heat_f')
        cool_f = request.json.get('cool_f')
        
        success = hub_instance.hvac_controller.set_temperature(heat_f, cool_f)
        
        if success:
            db.log_automation("hvac", f"Set temp: heat={heat_f}, cool={cool_f}", "Manual control")
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error setting HVAC temperature: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/hvac/auto', methods=['POST'])
def set_hvac_auto():
    """Enable/disable HVAC auto mode"""
    try:
        if not hub_instance or not hub_instance.hvac_controller:
            return jsonify({"error": "HVAC not available"}), 404
        
        enabled = request.json.get('enabled', True)
        hub_instance.hvac_controller.set_auto_mode(enabled)
        
        return jsonify({"success": True, "auto_mode": enabled})
    except Exception as e:
        logger.error(f"Error setting HVAC auto mode: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/lighting/status', methods=['GET'])
def get_lighting_status():
    """Get lighting status"""
    try:
        if hub_instance and hub_instance.lighting_controller:
            lights = hub_instance.lighting_controller.get_lights()
            return jsonify({
                "lights": lights,
                "auto_mode": hub_instance.lighting_controller.is_auto_mode()
            })
        return jsonify({"error": "Lighting not available"}), 404
    except Exception as e:
        logger.error(f"Error getting lighting status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/lighting/brightness', methods=['POST'])
def set_lighting_brightness():
    """Set lighting brightness"""
    try:
        if not hub_instance or not hub_instance.lighting_controller:
            return jsonify({"error": "Lighting not available"}), 404
        
        light_id = request.json.get('light_id', 1)
        brightness_pct = request.json.get('brightness_pct')
        
        success = hub_instance.lighting_controller.set_brightness_pct(light_id, brightness_pct)
        
        if success:
            db.log_automation("lighting", f"Set brightness to {brightness_pct}%", "Manual control")
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error setting lighting brightness: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/lighting/scene', methods=['POST'])
def set_lighting_scene():
    """Set lighting scene"""
    try:
        if not hub_instance or not hub_instance.lighting_controller:
            return jsonify({"error": "Lighting not available"}), 404
        
        scene = request.json.get('scene')
        success = hub_instance.lighting_controller.set_scene(scene)
        
        if success:
            db.log_automation("lighting", f"Set scene to {scene}", "Manual control")
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error setting lighting scene: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/lighting/auto', methods=['POST'])
def set_lighting_auto():
    """Enable/disable lighting auto mode"""
    try:
        if not hub_instance or not hub_instance.lighting_controller:
            return jsonify({"error": "Lighting not available"}), 404
        
        enabled = request.json.get('enabled', True)
        hub_instance.lighting_controller.set_auto_mode(enabled)
        
        return jsonify({"success": True, "auto_mode": enabled})
    except Exception as e:
        logger.error(f"Error setting lighting auto mode: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/music/status', methods=['GET'])
def get_music_status():
    """Get music status"""
    try:
        if hub_instance and hub_instance.music_controller:
            track = hub_instance.music_controller.get_current_track()
            track["auto_mode"] = hub_instance.music_controller.is_auto_mode()
            return jsonify(track)
        return jsonify({"error": "Music not available"}), 404
    except Exception as e:
        logger.error(f"Error getting music status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/music/play', methods=['POST'])
def music_play():
    """Play music"""
    try:
        if not hub_instance or not hub_instance.music_controller:
            return jsonify({"error": "Music not available"}), 404
        
        uri = request.json.get('uri')
        success = hub_instance.music_controller.play(uri)
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error playing music: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/music/pause', methods=['POST'])
def music_pause():
    """Pause music"""
    try:
        if not hub_instance or not hub_instance.music_controller:
            return jsonify({"error": "Music not available"}), 404
        
        success = hub_instance.music_controller.pause()
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error pausing music: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/music/next', methods=['POST'])
def music_next():
    """Next track"""
    try:
        if not hub_instance or not hub_instance.music_controller:
            return jsonify({"error": "Music not available"}), 404
        
        success = hub_instance.music_controller.next_track()
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error skipping track: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/music/volume', methods=['POST'])
def set_music_volume():
    """Set music volume"""
    try:
        if not hub_instance or not hub_instance.music_controller:
            return jsonify({"error": "Music not available"}), 404
        
        volume = request.json.get('volume')
        success = hub_instance.music_controller.set_volume(volume)
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error setting volume: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/music/auto', methods=['POST'])
def set_music_auto():
    """Enable/disable music auto mode"""
    try:
        if not hub_instance or not hub_instance.music_controller:
            return jsonify({"error": "Music not available"}), 404
        
        enabled = request.json.get('enabled', True)
        hub_instance.music_controller.set_auto_mode(enabled)
        
        return jsonify({"success": True, "auto_mode": enabled})
    except Exception as e:
        logger.error(f"Error setting music auto mode: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/tv/power', methods=['POST'])
def tv_power():
    """Control TV power"""
    try:
        if not hub_instance or not hub_instance.tv_controller:
            return jsonify({"error": "TV not available"}), 404
        
        action = request.json.get('action')  # 'on' or 'off'
        
        if action == 'on':
            success = hub_instance.tv_controller.power_on()
        else:
            success = hub_instance.tv_controller.power_off()
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error controlling TV power: {e}")
        return jsonify({"error": str(e)}), 500


# ===== WebSocket Events =====

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit('connection_response', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


@socketio.on('request_update')
def handle_update_request():
    """Handle update request from client"""
    try:
        if hub_instance:
            data = hub_instance._collect_sensor_data()
            emit('sensor_update', data)
    except Exception as e:
        logger.error(f"Error handling update request: {e}")


def broadcast_sensor_data():
    """Broadcast sensor data to all connected clients"""
    while True:
        try:
            if hub_instance:
                data = hub_instance._collect_sensor_data()
                socketio.emit('sensor_update', data)
            
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            logger.error(f"Error broadcasting sensor data: {e}")
            time.sleep(5)


def start_broadcast_thread():
    """Start background thread for broadcasting data"""
    thread = Thread(target=broadcast_sensor_data)
    thread.daemon = True
    thread.start()


def run_server(host='0.0.0.0', port=8080, debug=False):
    """Run the dashboard server"""
    start_broadcast_thread()
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server(debug=True)
