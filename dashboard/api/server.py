"""
Pulse 1.0 - Dashboard API Server
Flask + SocketIO backend for real-time dashboard
"""

import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory, send_file, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from threading import Thread
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.storage.db import PulseDB
from services.sensors.health_monitor import HealthMonitor
# Avoid importing heavy OpenCV-dependent modules at import time to keep API up even
# when camera dependencies are missing. Camera sensor runs in the Hub service.
try:
    from services.sensors.camera_people import PeopleCounter  # noqa: F401
except Exception:
    PeopleCounter = None  # type: ignore

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../ui/build', static_url_path='')
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'pulse-development-key')

# Initialize SocketIO with robust async fallback
def _choose_async_mode() -> str:
    preferred = os.getenv('PULSE_SIO_MODE', '').strip().lower()
    if preferred in {'eventlet', 'gevent', 'threading'}:
        return preferred
    # Default to threading for maximum compatibility on fresh images
    # (eventlet/gevent can be enabled later via PULSE_SIO_MODE)
    return 'threading'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_choose_async_mode())

# Initialize database and health monitor
db = PulseDB()
health_monitor = HealthMonitor()
camera_for_snapshot = None

# Global hub instance (will be set by main)
hub_instance = None

def set_hub_instance(hub):
    """Set the hub instance for API access"""
    global hub_instance
    hub_instance = hub


# ===== REST API Routes =====

@app.route('/')
def index():
    """Serve React app. If UI is not built yet, return a simple readiness page."""
    index_path = Path(app.static_folder) / 'index.html'
    if index_path.exists():
        return send_from_directory(app.static_folder, 'index.html')
    return jsonify({"status": "ok", "ui": "not-built"})

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
            logger.debug(f"Sensor data from hub: temp={data.get('temperature_f')}, humidity={data.get('humidity')}")
        else:
            # Fallback: derive current snapshot from database
            data = {
                "occupancy": db.get_current_occupancy(),
                "entries": 0,
                "exits": 0,
                "traffic": None,
                "temperature_f": None,
                "temperature_c": None,
                "humidity": None,
                "pressure": None,
                "temperature_age_seconds": None,
                "light_level": None,
                "noise_db": None,
                "current_song": None,
                "song_detection": None,
            }

            # Fallback to database if hub is not available
            try:
                env = db.get_latest_environment()
                if env:
                    # Only update if database has more recent data than None
                    if data.get("temperature_f") is None and env.get("temperature") is not None:
                        data["temperature_f"] = env.get("temperature")
                        data["temperature_c"] = round((env.get("temperature") - 32) * 5/9, 1)
                    if data.get("humidity") is None and env.get("humidity") is not None:
                        data["humidity"] = env.get("humidity")
                    if data.get("pressure") is None and env.get("pressure") is not None:
                        data["pressure"] = env.get("pressure")
                    if data.get("light_level") is None and env.get("light_level") is not None:
                        data["light_level"] = env.get("light_level")
                    if data.get("noise_db") is None and env.get("noise_level") is not None:
                        data["noise_db"] = env.get("noise_level")
                    logger.debug(f"Sensor data from DB: temp={data.get('temperature_f')}, humidity={data.get('humidity')}")
            except Exception as e:
                logger.error(f"Error reading environment from DB: {e}")

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
            except Exception as e:
                logger.debug(f"Error reading music log: {e}")
                data["current_song"] = {"title": None, "artist": None}
        
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error getting sensors: {e}")
        import traceback
        logger.error(traceback.format_exc())
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


@app.route('/api/audio/stream')
def audio_stream():
    """Stream live audio from microphone (simple monitoring)"""
    try:
        import sounddevice as sd
        import numpy as np
        
        def generate_audio():
            """Generator that yields audio chunks"""
            sample_rate = 16000  # 16kHz for web streaming
            block_size = 4096
            
            # WAV header for 16-bit PCM audio
            import struct
            
            def make_wav_header(sample_rate, channels=1, bits_per_sample=16):
                byte_rate = sample_rate * channels * bits_per_sample // 8
                block_align = channels * bits_per_sample // 8
                
                header = b'RIFF'
                header += struct.pack('<I', 0)  # Placeholder for file size
                header += b'WAVE'
                header += b'fmt '
                header += struct.pack('<I', 16)  # fmt chunk size
                header += struct.pack('<H', 1)  # PCM format
                header += struct.pack('<H', channels)
                header += struct.pack('<I', sample_rate)
                header += struct.pack('<I', byte_rate)
                header += struct.pack('<H', block_align)
                header += struct.pack('<H', bits_per_sample)
                header += b'data'
                header += struct.pack('<I', 0xFFFFFFFF)  # Placeholder for data size
                
                return header
            
            # Send WAV header first
            yield make_wav_header(sample_rate)
            
            # Stream audio chunks
            with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=block_size) as stream:
                while True:
                    data, _ = stream.read(block_size)
                    yield data.tobytes()
        
        return Response(generate_audio(), mimetype='audio/wav')
        
    except Exception as e:
        logger.error(f"Error streaming audio: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/camera/snapshot')
def camera_snapshot():
    """Return the latest snapshot saved by the people counter.
    
    IMPORTANT: This endpoint does NOT open the camera directly to avoid
    conflicts with the people counter which keeps the camera open continuously.
    The people counter saves snapshots every second to latest_camera.jpg.
    """
    try:
        # Read snapshot file created by people counter
        snapshot_path = Path('/opt/pulse/data/latest_camera.jpg')
        
        if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
            resp = send_file(str(snapshot_path), mimetype='image/jpeg', max_age=0)
            resp.headers['Cache-Control'] = 'no-store'
            return resp
        
        # If snapshot doesn't exist yet, return a placeholder
        # (People counter will create it within 1-2 seconds of starting)
        transparent_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\xda\x63\x60\x00\x00\x00\x02\x00\x01'
            b'\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return Response(transparent_png, mimetype='image/png', headers={'Cache-Control': 'no-store'})
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
    broadcast_count = 0
    while True:
        try:
            if hub_instance:
                data = hub_instance._collect_sensor_data()
                logger.debug(f"Broadcasting data from hub: temp={data.get('temperature_f')}, humidity={data.get('humidity')}")
            else:
                # Fallback to current snapshot from DB so UI still updates
                data = {
                    "occupancy": db.get_current_occupancy(),
                    "temperature_f": None,
                    "temperature_c": None,
                    "humidity": None,
                    "pressure": None,
                    "temperature_age_seconds": None,
                    "light_level": None,
                    "noise_db": None,
                    "current_song": None,
                    "song_detection": None,
                }
                # Fallback to database for environment data
                try:
                    env = db.get_latest_environment()
                    if env:
                        # Only update if we don't already have data
                        if data.get("temperature_f") is None and env.get("temperature") is not None:
                            data["temperature_f"] = env.get("temperature")
                            data["temperature_c"] = round((env.get("temperature") - 32) * 5/9, 1)
                        if data.get("humidity") is None and env.get("humidity") is not None:
                            data["humidity"] = env.get("humidity")
                        if data.get("pressure") is None and env.get("pressure") is not None:
                            data["pressure"] = env.get("pressure")
                        if data.get("light_level") is None and env.get("light_level") is not None:
                            data["light_level"] = env.get("light_level")
                        if data.get("noise_db") is None and env.get("noise_level") is not None:
                            data["noise_db"] = env.get("noise_level")
                        logger.debug(f"Broadcasting data from DB: temp={data.get('temperature_f')}, humidity={data.get('humidity')}")
                except Exception as e:
                    logger.error(f"Error reading environment from DB: {e}")
                
                # Last played song from music_log (with timeout protection)
                try:
                    with db.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT track_name, artist FROM music_log ORDER BY timestamp DESC LIMIT 1")
                        row = cur.fetchone()
                        if row:
                            data["current_song"] = {"title": row[0], "artist": row[1]}
                        else:
                            data["current_song"] = {"title": None, "artist": None}
                except Exception as e:
                    logger.debug(f"Error reading music log: {e}")
                    data["current_song"] = {"title": None, "artist": None}

            socketio.emit('sensor_update', data)
            
            # Log every 12 broadcasts (1 minute at 5 second intervals)
            broadcast_count += 1
            if broadcast_count % 12 == 0:
                logger.info(f"Dashboard broadcast #{broadcast_count}: temp={data.get('temperature_f')}, occupancy={data.get('occupancy')}")
            
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            logger.error(f"Error broadcasting sensor data: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(5)


def start_broadcast_thread():
    """Start background thread for broadcasting data"""
    thread = Thread(target=broadcast_sensor_data)
    thread.daemon = True
    thread.start()


def run_server(host='0.0.0.0', port=8080, debug=False):
    """Run the dashboard server with safe fallbacks."""
    start_broadcast_thread()
    try:
        socketio.run(app, host=host, port=port, debug=debug)
    except Exception as e:
        logger.error(f"SocketIO server failed ({e}); falling back to Flask built-in server")
        # Minimal fallback to keep HTTP API reachable
        app.run(host=host, port=port, debug=False)


# ===== Camera helper (optional init placeholder) =====
def _try_init_camera_once():
    """Placeholder for future camera warmup/init if needed."""
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_server(debug=True)
