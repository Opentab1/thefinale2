"""
Pulse 1.0 - First Boot Setup Wizard
Interactive configuration wizard that runs on first boot
"""

import logging
import os
import sys
import yaml
import subprocess
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

app = Flask(__name__)
# Allow kiosk (served from localhost:9977) to query status without CORS issues
CORS(app, resources={r"/*": {"origins": "*"}})

CONFIG_PATH = "/opt/pulse/config/config.yaml"
ENV_PATH = "/opt/pulse/.env"
WIZARD_FLAG_PATH = "/opt/pulse/config/.wizard_complete"

WIZARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Pulse 1.0 Setup Wizard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 800px;
            width: 100%;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
        .content { padding: 40px; }
        .step { display: none; }
        .step.active { display: block; }
        .form-group { margin-bottom: 25px; }
        .form-group label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        .hardware-status {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .hardware-item {
            padding: 15px;
            border-radius: 8px;
            background: #f5f5f5;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .hardware-item.ok { background: #e8f5e9; }
        .hardware-item.missing { background: #ffebee; }
        .status-icon {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: 700;
            font-size: 16px;
            line-height: 1;
        }
        .status-ok { background: #4caf50; }
        .status-missing { background: #f44336; }
        .buttons {
            display: flex;
            justify-content: space-between;
            margin-top: 30px;
        }
        button {
            padding: 14px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102,126,234,0.4); }
        .btn-secondary {
            background: #e0e0e0;
            color: #333;
        }
        .btn-secondary:hover { background: #d0d0d0; }
        .progress-bar {
            height: 4px;
            background: #e0e0e0;
            margin-bottom: 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }
        .success-message {
            text-align: center;
            padding: 40px;
        }
        .success-icon {
            width: 80px;
            height: 80px;
            background: #4caf50;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 40px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="progress-bar">
            <div class="progress-fill" id="progress"></div>
        </div>
        
        <div class="header">
            <h1>🎵 Pulse 1.0</h1>
            <p>Welcome! Let's set up your venue automation system.</p>
        </div>
        
        <div class="content">
            <!-- Step 1: Venue Setup -->
            <div class="step active" data-step="1">
                <h2>Venue Setup</h2>
                <div class="form-group">
                    <label>Venue Name</label>
                    <input type="text" id="venueName" placeholder="My Awesome Venue" value="Pulse Venue">
                </div>
                <div class="form-group">
                    <label>Timezone</label>
                    <select id="timezone">
                        <option value="America/Chicago">Central Time (Chicago)</option>
                        <option value="America/New_York">Eastern Time (New York)</option>
                        <option value="America/Los_Angeles">Pacific Time (Los Angeles)</option>
                        <option value="America/Denver">Mountain Time (Denver)</option>
                    </select>
                </div>
            </div>
            
            <!-- Step 2: Hardware Check -->
            <div class="step" data-step="2">
                <h2>Hardware Detection</h2>
                <p id="hardwareCheckMessage">Checking connected hardware modules...</p>
                <div class="hardware-status" id="hardwareStatus">
                    <div class="hardware-item" id="hw-camera"><span>Camera</span><div class="status-icon" id="icon-camera"></div></div>
                    <div class="hardware-item" id="hw-mic"><span>Microphone</span><div class="status-icon" id="icon-mic"></div></div>
                    <div class="hardware-item" id="hw-bme280"><span>BME280 Sensor</span><div class="status-icon" id="icon-bme280"></div></div>
                    <div class="hardware-item" id="hw-light_sensor"><span>Light Sensor</span><div class="status-icon" id="icon-light_sensor"></div></div>
                    <div class="hardware-item" id="hw-pan_tilt"><span>Pan-Tilt HAT</span><div class="status-icon" id="icon-pan_tilt"></div></div>
                    <div class="hardware-item" id="hw-ai_hat"><span>AI HAT</span><div class="status-icon" id="icon-ai_hat"></div></div>
                </div>
                <p style="margin-top: 20px; color: #666;">
                    ℹ️ Missing modules will be automatically disabled. The system will work with available hardware.
                </p>
            </div>
            
            <!-- Step 3: Smart Integrations -->
            <div class="step" data-step="3">
                <h2>Smart Integrations</h2>
                <p style="margin-bottom: 20px;">Configure your smart home integrations (optional - can be done later)</p>
                
                <div class="form-group">
                    <label>Enable Nest/Google HVAC</label>
                    <select id="hvacEnabled">
                        <option value="false">Skip for now</option>
                        <option value="true">Enable</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Enable Philips Hue Lighting</label>
                    <select id="lightingEnabled">
                        <option value="false">Skip for now</option>
                        <option value="true">Enable</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Enable Spotify Music</label>
                    <select id="musicEnabled">
                        <option value="false">Skip for now</option>
                        <option value="true">Enable</option>
                    </select>
                </div>
            </div>
            
            <!-- Step 4: Automation Limits -->
            <div class="step" data-step="4">
                <h2>Automation Limits</h2>
                <p style="margin-bottom: 20px;">Set safe limits for automated adjustments</p>
                
                <div class="form-group">
                    <label>HVAC Temperature Range (°F)</label>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <input type="number" id="hvacMin" placeholder="Min" value="67">
                        <input type="number" id="hvacMax" placeholder="Max" value="75">
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Lighting Brightness Range (%)</label>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <input type="number" id="lightMin" placeholder="Min" value="20">
                        <input type="number" id="lightMax" placeholder="Max" value="85">
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Music Volume Range (%)</label>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <input type="number" id="volumeMin" placeholder="Min" value="25">
                        <input type="number" id="volumeMax" placeholder="Max" value="70">
                    </div>
                </div>
            </div>
            
            <!-- Step 5: Complete -->
            <div class="step" data-step="5">
                <div class="success-message">
                    <div class="success-icon">✓</div>
                    <h2>Setup Complete!</h2>
                    <p style="margin: 20px 0;">Pulse is now configured and ready to run your venue.</p>
                    <p style="color: #666;">The system will reboot in a few seconds...</p>
                </div>
            </div>
            
            <div class="buttons">
                <button class="btn-secondary" id="prevBtn" onclick="prevStep()" style="display: none;">Previous</button>
                <button class="btn-primary" id="nextBtn" onclick="nextStep()">Next</button>
            </div>
        </div>
    </div>
    
    <script>
        let currentStep = 1;
        const totalSteps = 5;
        let hardwareChecked = false;
        
        function updateProgress() {
            const progress = (currentStep / totalSteps) * 100;
            document.getElementById('progress').style.width = progress + '%';
        }
        
        function showStep(step) {
            document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
            document.querySelector(`[data-step="${step}"]`).classList.add('active');
            
            document.getElementById('prevBtn').style.display = step > 1 ? 'block' : 'none';
            document.getElementById('nextBtn').textContent = step === totalSteps - 1 ? 'Complete Setup' : 'Next';
            
            if (step === totalSteps) {
                document.querySelector('.buttons').style.display = 'none';
            }

            // Trigger hardware check when entering step 2 so user can see results
            if (step === 2) {
                checkHardware();
            }
            
            updateProgress();

            // Automatically run hardware check when entering step 2
            if (step === 2 && !hardwareChecked) {
                checkHardware();
            }
        }
        
        function nextStep() {
            if (currentStep === 2 && !hardwareChecked) {
                // Wait for hardware check to complete before proceeding
                return;
            } else if (currentStep === totalSteps - 1) {
                completeSetup();
            } else {
                currentStep++;
                showStep(currentStep);
            }
        }
        
        function prevStep() {
            if (currentStep > 1) {
                currentStep--;
                showStep(currentStep);
            }
        }
        
        function setHardwareRow(key, ok) {
            const row = document.getElementById(`hw-${key}`);
            const icon = document.getElementById(`icon-${key}`);
            if (!row || !icon) return;
            row.classList.remove('ok', 'missing');
            icon.classList.remove('status-ok', 'status-missing');
            if (ok) {
                row.classList.add('ok');
                icon.classList.add('status-ok');
                icon.textContent = '✓';
            } else {
                row.classList.add('missing');
                icon.classList.add('status-missing');
                icon.textContent = '✗';
            }
        }

        function normalizeHardwareData(data) {
            if (data && typeof data === 'object' && data.modules && typeof data.modules === 'object') {
                const m = data.modules;
                return {
                    camera: !!(m.camera && m.camera.present),
                    mic: !!(m.mic && m.mic.present),
                    bme280: !!(m.bme280 && m.bme280.present),
                    light_sensor: !!(m.light_sensor && m.light_sensor.present),
                    pan_tilt: !!(m.pan_tilt && m.pan_tilt.present),
                    ai_hat: !!(m.ai_hat && m.ai_hat.present),
                };
            }
            return {
                camera: !!(data && data.camera),
                mic: !!(data && data.mic),
                bme280: !!(data && data.bme280),
                light_sensor: !!(data && data.light_sensor),
                pan_tilt: !!(data && data.pan_tilt),
                ai_hat: !!(data && data.ai_hat),
            };
        }


        function checkHardware() {
            // Indicate in-Progress
            const msg = document.getElementById('hardwareCheckMessage');
            if (msg) msg.textContent = 'Checking connected hardware modules...';

            fetch('/api/wizard/hardware-check')
                .then(r => r.json())
                .then(data => {
                    const results = normalizeHardwareData(data);
                    // Update hardware status display with green check / red X
                    setHardwareRow('camera', !!results.camera);
                    setHardwareRow('mic', !!results.mic);
                    setHardwareRow('bme280', !!results.bme280);
                    setHardwareRow('light_sensor', !!results.light_sensor);
                    setHardwareRow('pan_tilt', !!results.pan_tilt);
                    setHardwareRow('ai_hat', !!results.ai_hat);
                    hardwareChecked = true;
                    if (msg) msg.textContent = 'Hardware check complete. Review statuses below.';
                })
                .catch(() => {
                    // On error, mark all as missing
                    ['camera','mic','bme280','light_sensor','pan_tilt','ai_hat'].forEach(k => setHardwareRow(k, false));
                    hardwareChecked = true;
                    if (msg) msg.textContent = 'Could not check hardware automatically. Review defaults below.';
                });
        }
        
        function completeSetup() {
            const config = {
                venue: {
                    name: document.getElementById('venueName').value,
                    timezone: document.getElementById('timezone').value
                },
                integrations: {
                    hvac_enabled: document.getElementById('hvacEnabled').value === 'true',
                    lighting_enabled: document.getElementById('lightingEnabled').value === 'true',
                    music_enabled: document.getElementById('musicEnabled').value === 'true'
                },
                policies: {
                    hvac: {
                        min_f: parseInt(document.getElementById('hvacMin').value),
                        max_f: parseInt(document.getElementById('hvacMax').value)
                    },
                    lighting: {
                        min_pct: parseInt(document.getElementById('lightMin').value),
                        max_pct: parseInt(document.getElementById('lightMax').value)
                    },
                    music: {
                        volume_min: parseInt(document.getElementById('volumeMin').value),
                        volume_max: parseInt(document.getElementById('volumeMax').value)
                    }
                }
            };
            
            fetch('/api/wizard/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            })
            .then(r => r.json())
            .then(data => {
                currentStep++;
                showStep(currentStep);
                setTimeout(() => {
                    window.location.href = '/reboot';
                }, 3000);
            });
        }
        
        updateProgress();
    </script>
</body>
</html>
"""

@app.route('/api/wizard/status')
def wizard_status():
    """Report wizard completion status and marker presence"""
    try:
        cfg = load_config()
    except Exception:
        cfg = { 'wizard': { 'completed': False } }

    try:
        flag_exists = Path(WIZARD_FLAG_PATH).exists()
    except Exception:
        flag_exists = False

    return jsonify({
        "completed": bool(cfg.get('wizard', {}).get('completed', False)),
        "flag_exists": flag_exists,
        "config_path": CONFIG_PATH
    })

@app.route('/')
def index():
    """Serve wizard interface"""
    return render_template_string(WIZARD_HTML)


@app.route('/api/wizard/hardware-check')
def hardware_check():
    """Check hardware availability"""
    try:
        # Try to load hardware detection results
        hardware_report_path = Path("/var/log/pulse/hardware_report.txt")
        if hardware_report_path.exists():
            import json
            with open(hardware_report_path, 'r') as f:
                results = json.load(f)
                logger.info(f"Loaded hardware detection results: {results}")
                return jsonify(results)
    except Exception as e:
        logger.warning(f"Could not load hardware detection results: {e}")
    
    # Default to basic hardware available
    return jsonify({
        "camera": True,
        "mic": True,
        "bme280": False,
        "light_sensor": False,
        "pan_tilt": False,
        "ai_hat": False
    })


@app.route('/api/wizard/complete', methods=['POST'])
def complete_setup():
    """Complete setup and save configuration"""
    try:
        data = request.json
        
        # Ensure config directory exists
        config_dir = Path(CONFIG_PATH).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Update config.yaml
        config = load_config()
        config['venue']['name'] = data['venue']['name']
        config['venue']['timezone'] = data['venue']['timezone']
        
        config['smart_integrations']['hvac']['enabled'] = data['integrations']['hvac_enabled']
        config['smart_integrations']['lighting']['enabled'] = data['integrations']['lighting_enabled']
        config['smart_integrations']['music']['enabled'] = data['integrations']['music_enabled']
        
        config['policies']['hvac']['min_f'] = data['policies']['hvac']['min_f']
        config['policies']['hvac']['max_f'] = data['policies']['hvac']['max_f']
        config['policies']['lighting']['min_pct'] = data['policies']['lighting']['min_pct']
        config['policies']['lighting']['max_pct'] = data['policies']['lighting']['max_pct']
        config['policies']['music']['volume_min'] = data['policies']['music']['volume_min']
        config['policies']['music']['volume_max'] = data['policies']['music']['volume_max']
        
        config['wizard']['completed'] = True

        # Derive module enables based on detected hardware if report exists
        try:
            report_path = Path("/var/log/pulse/hardware_report.txt")
            if report_path.exists():
                import json as _json
                with open(report_path, 'r') as rf:
                    hw = _json.load(rf)
                # Normalize booleans
                modules_cfg = config.get('modules', {})
                for k in ['camera', 'mic', 'bme280', 'light_sensor', 'pan_tilt', 'ai_hat']:
                    if k in modules_cfg and k in hw:
                        try:
                            modules_cfg[k] = bool(hw[k]) if isinstance(hw[k], bool) else bool(hw.get(k, {}).get('present', False))
                        except Exception:
                            pass
                config['modules'] = modules_cfg
        except Exception:
            pass
        
        save_config(config)

        # Mark wizard as completed so first-boot service will not run again
        try:
            Path(WIZARD_FLAG_PATH).parent.mkdir(parents=True, exist_ok=True)
            Path(WIZARD_FLAG_PATH).touch(exist_ok=True)
        except Exception:
            pass

        # Try to disable the first-boot wizard and enable core services
        # These commands may require elevated privileges; ignore failures gracefully
        try:
            os.system('systemctl disable --now pulse-firstboot.service >/dev/null 2>&1')
        except Exception:
            pass
        try:
            os.system('systemctl enable --now pulse-hub.service pulse-dashboard.service pulse-health.service >/dev/null 2>&1')
        except Exception:
            pass
        
        # Generate encryption key if not exists
        if not os.path.exists(ENV_PATH):
            key = Fernet.generate_key()
            with open(ENV_PATH, 'w') as f:
                f.write(f"SECRET_KEY={key.decode()}\n")
                f.write(f"ENCRYPTION_KEY={key.decode()}\n")
        
        # Create wizard completion marker file (canonical location)
        marker_file = Path(WIZARD_FLAG_PATH)
        marker_file.touch()
        logger.info(f"Created wizard completion marker at {marker_file}")
        
        return jsonify({"success": True})
    
    except Exception as e:
        logger.error(f"Error completing setup: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/reboot')
def reboot():
    """Reboot the system"""
    subprocess.Popen(['sudo', 'reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "Rebooting..."


def load_config():
    """Load configuration"""
    config_path = Path(CONFIG_PATH)
    
    # If config doesn't exist, create default config
    if not config_path.exists():
        default_config = {
            'venue': {
                'name': 'Pulse Venue',
                'timezone': 'America/Chicago'
            },
            'modules': {
                'camera': True,
                'mic': True,
                'bme280': True,
                'light_sensor': True,
                'ai_hat': True,
                'pan_tilt': True
            },
            'smart_integrations': {
                'hvac': {
                    'enabled': False,
                    'provider': 'nest'
                },
                'lighting': {
                    'enabled': False,
                    'provider': 'hue'
                },
                'music': {
                    'enabled': False,
                    'provider': 'spotify'
                }
            },
            'policies': {
                'hvac': {
                    'min_f': 67,
                    'max_f': 75,
                    'auto_mode': True
                },
                'lighting': {
                    'min_pct': 20,
                    'max_pct': 85,
                    'auto_mode': True
                },
                'music': {
                    'volume_min': 25,
                    'volume_max': 70,
                    'auto_mode': True
                }
            },
            'wizard': {
                'completed': False
            }
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        save_config(default_config)
        return default_config
    
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


def save_config(config):
    """Save configuration"""
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Robust startup: retry bind if port is not immediately free
    import time as _t
    for _i in range(5):
        try:
            app.run(host='0.0.0.0', port=9090, debug=False)
            break
        except OSError as _e:
            logging.warning(f"Wizard server bind failed (attempt {_i+1}/5): {_e}")
            _t.sleep(2)
