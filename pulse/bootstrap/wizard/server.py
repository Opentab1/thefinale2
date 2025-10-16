from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
import yaml
import os

app = FastAPI(title='Pulse Wizard')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

ui_dir = Path(__file__).resolve().parent / 'ui'
ui_dir.mkdir(parents=True, exist_ok=True)
app.mount('/', StaticFiles(directory=str(ui_dir), html=True), name='ui')

CONFIG_FILE = Path('/opt/pulse/config/config.yaml')
SETUP_FLAG = Path('/opt/pulse/.setup_done')

@app.post('/save')
async def save(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Merge minimal fields if existing
        data = {}
        if CONFIG_FILE.exists():
            data = yaml.safe_load(CONFIG_FILE.read_text()) or {}
        data.update(body or {})
        CONFIG_FILE.write_text(yaml.safe_dump(data, sort_keys=False))
    except Exception:
        pass
    try:
        SETUP_FLAG.write_text('done')
        # Disable and stop the firstboot service immediately
        os.system('sudo systemctl disable pulse-firstboot.service >/dev/null 2>&1')
        os.system('sudo systemctl stop pulse-firstboot.service >/dev/null 2>&1')
        # Trigger reboot in background after short delay
        os.system('(sleep 2 && sudo reboot) &')
    except Exception:
        pass
    return JSONResponse({"ok": True, "message": "Setup complete! Rebooting..."})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9090)
