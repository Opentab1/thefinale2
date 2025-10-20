from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import yaml
import json
import asyncio
from pathlib import Path

app = FastAPI(title="Pulse Hub")

# Allow local dashboard origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TogglePayload(BaseModel):
    system: str
    auto: bool

CONFIG_FILE = os.environ.get('CONFIG_FILE', '/opt/pulse/config/config.yaml')
DB_PATH = os.environ.get('DB_PATH', '/opt/pulse/data/pulse.db')

# Try to load config, use defaults if not available
try:
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f) or {}
except Exception:
    config = {}

auto_state = {
    'hvac': True,
    'lighting': True,
    'tv': True,
    'music': True,
}

# Live sensor data state
live_data = {
    'people_count': 0,
    'temperature': 72.0,
    'humidity': 45.0,
    'decibels': 0.0,
    'song': {
        'title': 'No song detected',
        'artist': '',
        'detected': False
    },
    'integrations': {
        'nest_connected': False,
        'hue_connected': False,
        'spotify_connected': False
    },
    'camera_active': False
}

subscribers = set()

async def broadcast(message: dict):
    living = set()
    for ws in list(subscribers):
        try:
            await ws.send_json(message)
            living.add(ws)
        except Exception:
            pass
    subscribers.clear()
    subscribers.update(living)

@app.get('/health')
async def health():
    return {'status': 'ok'}

@app.get('/config')
async def get_config():
    return JSONResponse(config)

@app.get('/live')
async def get_live_data():
    """Get current live sensor data"""
    # Try to read from database or sensor cache files
    try:
        # Check for sensor data files
        sensor_dir = Path('/opt/pulse/data/sensors')
        if sensor_dir.exists():
            # Read people count
            people_file = sensor_dir / 'people_count.txt'
            if people_file.exists():
                try:
                    live_data['people_count'] = int(people_file.read_text().strip())
                except Exception:
                    pass
            
            # Read temperature/humidity
            bme_file = sensor_dir / 'bme280.json'
            if bme_file.exists():
                try:
                    bme_data = json.loads(bme_file.read_text())
                    live_data['temperature'] = bme_data.get('temperature', 72.0)
                    live_data['humidity'] = bme_data.get('humidity', 45.0)
                except Exception:
                    pass
            
            # Read decibels
            audio_file = sensor_dir / 'audio_level.txt'
            if audio_file.exists():
                try:
                    live_data['decibels'] = float(audio_file.read_text().strip())
                except Exception:
                    pass
            
            # Read song detection
            song_file = sensor_dir / 'song.json'
            if song_file.exists():
                try:
                    song_data = json.loads(song_file.read_text())
                    live_data['song'] = song_data
                except Exception:
                    pass
            
            # Read light level if present (written by light service)
            light_file = sensor_dir / 'light_level.txt'
            if light_file.exists():
                try:
                    # Only add to live_data if numeric; front-end may not yet render
                    live_data['light_level'] = float(light_file.read_text().strip())
                except Exception:
                    pass
            
            # Check camera status
            camera_file = sensor_dir / 'camera_active.txt'
            if camera_file.exists():
                try:
                    live_data['camera_active'] = camera_file.read_text().strip().lower() == 'true'
                except Exception:
                    pass
        
        # Check integration connections
        try:
            from pathlib import Path
            env_file = Path('/opt/pulse/.env')
            if env_file.exists():
                env_content = env_file.read_text()
                live_data['integrations']['nest_connected'] = 'NEST_' in env_content
                live_data['integrations']['hue_connected'] = 'HUE_' in env_content
                live_data['integrations']['spotify_connected'] = 'SPOTIFY_' in env_content
        except Exception:
            pass
            
    except Exception as e:
        print(f"Error reading sensor data: {e}")
    
    return JSONResponse(live_data)

@app.get('/camera/stream')
async def camera_stream():
    """Serve latest camera frame as JPEG"""
    try:
        frame_path = Path('/opt/pulse/data/camera/latest_frame.jpg')
        if frame_path.exists():
            return StreamingResponse(
                open(frame_path, 'rb'),
                media_type='image/jpeg'
            )
    except Exception:
        pass
    # Return a placeholder 1x1 transparent pixel if no camera
    from io import BytesIO
    from base64 import b64decode
    pixel = b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
    return StreamingResponse(BytesIO(pixel), media_type='image/png')

@app.post('/toggle')
async def toggle(body: TogglePayload):
    auto_state[body.system] = body.auto
    await broadcast({'type': 'auto_state', 'data': auto_state})
    return {'ok': True}

@app.websocket('/ws')
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    subscribers.add(ws)
    try:
        # Send initial state
        await ws.send_json({'type': 'auto_state', 'data': auto_state})
        await ws.send_json({'type': 'live_data', 'data': live_data})
        
        # Background task to send live updates every 2 seconds
        async def send_updates():
            while True:
                try:
                    await asyncio.sleep(2)
                    # Re-fetch live data
                    await get_live_data()  # This updates live_data dict
                    await ws.send_json({'type': 'live_data', 'data': live_data})
                except Exception:
                    break
        
        # Start background updates
        update_task = asyncio.create_task(send_updates())
        
        # Keep connection alive
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if 'update_task' in locals():
            update_task.cancel()
        subscribers.discard(ws)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=7000)
