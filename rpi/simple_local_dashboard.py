#!/usr/bin/env python3
"""
Simple Local Dashboard - NO AWS, NO Auth
Just reads sensor data from the Pi and displays it
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Try to import sensors - gracefully fail if not available
try:
    from services.sensors.bme280_reader import BME280Reader
    bme280 = BME280Reader()
    logger.info("✓ BME280 sensor loaded")
except Exception as e:
    logger.warning(f"BME280 not available: {e}")
    bme280 = None

try:
    from services.sensors.light_level import LightSensor
    light_sensor = LightSensor()
    logger.info("✓ Light sensor loaded")
except Exception as e:
    logger.warning(f"Light sensor not available: {e}")
    light_sensor = None

try:
    from services.sensors.mic_song_detect import AudioMonitor
    audio_monitor = AudioMonitor()
    logger.info("✓ Audio monitor loaded")
except Exception as e:
    logger.warning(f"Audio monitor not available: {e}")
    audio_monitor = None

try:
    from services.storage.db import PulseDB
    db = PulseDB()
    logger.info("✓ Database loaded")
except Exception as e:
    logger.warning(f"Database not available: {e}")
    db = None


def get_real_sensor_data():
    """Get actual sensor readings from the Pi"""
    data = {
        "decibels": 0,
        "light": 0,
        "indoorTemp": 0,
        "humidity": 0,
        "song": "—",
        "comfort": 95,
        "timestamp": int(time.time())
    }
    
    # Get BME280 data (temperature & humidity)
    if bme280:
        try:
            reading = bme280.read()
            if reading:
                data["indoorTemp"] = round(reading.get("temperature_f", 0), 1)
                data["humidity"] = int(reading.get("humidity", 0))
        except Exception as e:
            logger.debug(f"BME280 read error: {e}")
    
    # Get light level
    if light_sensor:
        try:
            reading = light_sensor.read()
            if reading:
                data["light"] = int(reading.get("light_level", 0))
        except Exception as e:
            logger.debug(f"Light sensor read error: {e}")
    
    # Get audio/noise level
    if audio_monitor:
        try:
            reading = audio_monitor.get_current_level()
            if reading:
                data["decibels"] = round(reading.get("noise_db", 0), 1)
        except Exception as e:
            logger.debug(f"Audio monitor error: {e}")
    
    # Get current song from database
    if db:
        try:
            with db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT track_name, artist FROM music_log ORDER BY timestamp DESC LIMIT 1")
                row = cur.fetchone()
                if row and row[0]:
                    data["song"] = f"{row[0]}" + (f" — {row[1]}" if row[1] else "")
        except Exception as e:
            logger.debug(f"Database query error: {e}")
    
    # Calculate comfort score
    try:
        comfort = 100
        if data["indoorTemp"] > 0:
            comfort -= abs(data["indoorTemp"] - 72) * 2
        if data["humidity"] > 0:
            comfort -= abs(data["humidity"] - 50) * 0.5
        if data["decibels"] > 70:
            comfort -= (data["decibels"] - 70) * 0.8
        data["comfort"] = max(0, min(100, int(comfort)))
    except:
        data["comfort"] = 95
    
    return data


# Simple HTML template (inline, no AWS references)
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Pulse Dashboard - Local Pi Sensors</title>
    <style>
      :root {
        --bg: #0f172a;
        --panel: #1e293b;
        --border: #334155;
        --text: #e2e8f0;
        --muted: #94a3b8;
        --accent: #3b82f6;
        --accent-bright: #60a5fa;
        --success: #10b981;
        --warning: #f59e0b;
      }
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background: var(--bg);
        color: var(--text);
        min-height: 100vh;
        padding: 20px;
      }
      .container { max-width: 1200px; margin: 0 auto; }
      
      header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 30px;
        padding-bottom: 20px;
        border-bottom: 2px solid var(--border);
      }
      h1 {
        font-size: 32px;
        font-weight: 700;
        color: var(--accent-bright);
      }
      .status-badge {
        padding: 8px 16px;
        background: var(--success);
        color: white;
        border-radius: 20px;
        font-size: 14px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .status-dot {
        width: 8px;
        height: 8px;
        background: white;
        border-radius: 50%;
        animation: pulse 2s infinite;
      }
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }
      
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        margin-bottom: 20px;
      }
      
      .card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        transition: transform 0.2s, box-shadow 0.2s;
      }
      .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
      }
      
      .card-label {
        font-size: 13px;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 12px;
      }
      
      .card-value {
        font-size: 48px;
        font-weight: 700;
        color: var(--accent-bright);
        line-height: 1;
        margin-bottom: 8px;
      }
      
      .card-unit {
        font-size: 18px;
        color: var(--muted);
        font-weight: 500;
      }
      
      .song-card {
        grid-column: 1 / -1;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
      }
      .song-card .card-label { color: rgba(255,255,255,0.8); }
      .song-card .card-value {
        color: white;
        font-size: 32px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      
      .comfort-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border: none;
      }
      .comfort-card .card-label { color: rgba(255,255,255,0.9); }
      .comfort-card .card-value { color: white; }
      
      .progress-bar {
        width: 100%;
        height: 8px;
        background: rgba(255,255,255,0.2);
        border-radius: 4px;
        overflow: hidden;
        margin-top: 12px;
      }
      .progress-fill {
        height: 100%;
        background: white;
        transition: width 0.5s ease;
        border-radius: 4px;
      }
      
      footer {
        text-align: center;
        padding: 20px;
        color: var(--muted);
        font-size: 14px;
      }
      
      .error-banner {
        background: var(--warning);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
        display: none;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <header>
        <h1>🎵 Pulse Dashboard</h1>
        <div class="status-badge" id="statusBadge">
          <div class="status-dot"></div>
          <span>LIVE</span>
        </div>
      </header>
      
      <div class="error-banner" id="errorBanner">
        Connection lost. Retrying...
      </div>
      
      <div class="grid">
        <div class="card song-card">
          <div class="card-label">Now Playing</div>
          <div class="card-value" id="song">—</div>
        </div>
        
        <div class="card">
          <div class="card-label">Sound Level</div>
          <div class="card-value">
            <span id="decibels">0</span>
            <span class="card-unit">dB</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="decibelsBar" style="width: 0%"></div>
          </div>
        </div>
        
        <div class="card">
          <div class="card-label">Light Level</div>
          <div class="card-value">
            <span id="light">0</span>
            <span class="card-unit">lux</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="lightBar" style="width: 0%"></div>
          </div>
        </div>
        
        <div class="card">
          <div class="card-label">Temperature</div>
          <div class="card-value">
            <span id="indoorTemp">0</span>
            <span class="card-unit">°F</span>
          </div>
        </div>
        
        <div class="card">
          <div class="card-label">Humidity</div>
          <div class="card-value">
            <span id="humidity">0</span>
            <span class="card-unit">%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="humidityBar" style="width: 0%"></div>
          </div>
        </div>
        
        <div class="card comfort-card">
          <div class="card-label">Comfort Score</div>
          <div class="card-value">
            <span id="comfort">0</span>
            <span class="card-unit">/ 100</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" id="comfortBar" style="width: 0%"></div>
          </div>
        </div>
      </div>
      
      <footer>
        Local Pi Dashboard • Updated every 2 seconds • No cloud connection required
      </footer>
    </div>
    
    <script>
      const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
      const el = id => document.getElementById(id);
      
      let failCount = 0;
      
      async function fetchData() {
        try {
          const res = await fetch('/data', { cache: 'no-store' });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          
          const d = await res.json();
          updateUI(d);
          
          // Reset error state
          failCount = 0;
          el('errorBanner').style.display = 'none';
          el('statusBadge').style.background = '#10b981';
          el('statusBadge').querySelector('span').textContent = 'LIVE';
          
        } catch (e) {
          console.error('Fetch error:', e);
          failCount++;
          
          if (failCount > 2) {
            el('errorBanner').style.display = 'block';
            el('statusBadge').style.background = '#ef4444';
            el('statusBadge').querySelector('span').textContent = 'OFFLINE';
          }
        }
      }
      
      function updateUI(d) {
        el('song').textContent = d.song || '—';
        
        el('decibels').textContent = d.decibels ?? 0;
        el('decibelsBar').style.width = clamp(((d.decibels ?? 0) - 40) * 1.5, 0, 100) + '%';
        
        el('light').textContent = d.light ?? 0;
        el('lightBar').style.width = clamp((d.light ?? 0) / 10, 0, 100) + '%';
        
        el('indoorTemp').textContent = d.indoorTemp ?? 0;
        
        el('humidity').textContent = d.humidity ?? 0;
        el('humidityBar').style.width = clamp(d.humidity ?? 0, 0, 100) + '%';
        
        el('comfort').textContent = d.comfort ?? 0;
        el('comfortBar').style.width = clamp(d.comfort ?? 0, 0, 100) + '%';
      }
      
      // Initial fetch
      fetchData();
      
      // Update every 2 seconds
      setInterval(fetchData, 2000);
    </script>
  </body>
</html>
"""

@app.route('/')
def index():
    """Serve the simple dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def get_data():
    """Return real sensor data as JSON"""
    data = get_real_sensor_data()
    logger.info(f"Sensor data: {data}")
    return jsonify(data)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "simple-local-dashboard"})


if __name__ == '__main__':
    logger.info("="*60)
    logger.info("🎵 Pulse Simple Local Dashboard")
    logger.info("="*60)
    logger.info("Dashboard URL: http://localhost:8080")
    logger.info("Data endpoint: http://localhost:8080/data")
    logger.info("No AWS • No Auth • Just Sensor Data")
    logger.info("="*60)
    
    app.run(host='0.0.0.0', port=8080, debug=False)
