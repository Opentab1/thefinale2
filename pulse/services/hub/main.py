from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import yaml

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

CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config/config.yaml')

with open(CONFIG_FILE, 'r') as f:
    config = yaml.safe_load(f)

auto_state = {
    'hvac': True,
    'lighting': True,
    'tv': True,
    'music': True,
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
        await ws.send_json({'type': 'auto_state', 'data': auto_state})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        subscribers.discard(ws)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=7000)
