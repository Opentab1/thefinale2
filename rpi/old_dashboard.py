#!/usr/bin/env python3
"""
Original RPi Local Dashboard
Runs on RPi 5, no cloud dependencies
"""

import json
import sqlite3
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading

# Configuration
PORT = 8080
DB_PATH = "/workspace/services/storage/pulse.db"

class DashboardHandler(BaseHTTPRequestHandler):
    """Simple HTTP server for local dashboard"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/api/status':
            self.serve_status()
        elif self.path == '/api/sensors':
            self.serve_sensors()
        else:
            self.send_error(404)
    
    def serve_dashboard(self):
        """Serve the main dashboard HTML"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pulse - Local Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .subtitle {
            text-align: center;
            opacity: 0.9;
            margin-bottom: 40px;
            font-size: 1.2em;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .card h2 {
            margin-bottom: 20px;
            font-size: 1.5em;
            border-bottom: 2px solid rgba(255,255,255,0.3);
            padding-bottom: 10px;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            margin: 15px 0;
            font-size: 1.1em;
        }
        .stat-label { opacity: 0.8; }
        .stat-value {
            font-weight: bold;
            font-size: 1.3em;
        }
        .status-ok { color: #4ade80; }
        .status-warn { color: #fbbf24; }
        .status-error { color: #ef4444; }
        .footer {
            text-align: center;
            margin-top: 40px;
            opacity: 0.7;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            background: #4ade80;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Pulse 1.0</h1>
        <p class="subtitle"><span class="live-indicator"></span>Local RPi Dashboard</p>
        
        <div class="grid">
            <div class="card">
                <h2>🌡️ Environment</h2>
                <div class="stat">
                    <span class="stat-label">Temperature:</span>
                    <span class="stat-value" id="temp">--°C</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Humidity:</span>
                    <span class="stat-value" id="humidity">--%</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Pressure:</span>
                    <span class="stat-value" id="pressure">-- hPa</span>
                </div>
            </div>
            
            <div class="card">
                <h2>👥 People</h2>
                <div class="stat">
                    <span class="stat-label">Count:</span>
                    <span class="stat-value status-ok" id="people">0</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Last Detected:</span>
                    <span class="stat-value" id="last-seen">Never</span>
                </div>
            </div>
            
            <div class="card">
                <h2>💡 Sensors</h2>
                <div class="stat">
                    <span class="stat-label">Camera:</span>
                    <span class="stat-value status-ok" id="camera">●</span>
                </div>
                <div class="stat">
                    <span class="stat-label">BME280:</span>
                    <span class="stat-value status-ok" id="bme280">●</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Audio:</span>
                    <span class="stat-value status-ok" id="audio">●</span>
                </div>
            </div>
            
            <div class="card">
                <h2>☁️ Cloud Sync</h2>
                <div class="stat">
                    <span class="stat-label">AWS IoT:</span>
                    <span class="stat-value status-ok" id="aws-status">Connected</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Last Sync:</span>
                    <span class="stat-value" id="last-sync">--</span>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Running on Raspberry Pi 5 | No Authentication Required</p>
            <p style="margin-top: 10px;">Access: http://localhost:8080</p>
        </div>
    </div>
    
    <script>
        // Auto-refresh data every 5 seconds
        async function updateData() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update UI
                document.getElementById('temp').textContent = data.temperature + '°C';
                document.getElementById('humidity').textContent = data.humidity + '%';
                document.getElementById('pressure').textContent = data.pressure + ' hPa';
                document.getElementById('people').textContent = data.people_count;
                document.getElementById('last-seen').textContent = data.last_detection || 'Never';
                document.getElementById('last-sync').textContent = data.last_sync || 'Never';
                
            } catch (error) {
                console.error('Failed to fetch data:', error);
            }
        }
        
        // Update every 5 seconds
        updateData();
        setInterval(updateData, 5000);
    </script>
</body>
</html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def serve_status(self):
        """Serve current system status as JSON"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Get latest sensor data
            cursor.execute("""
                SELECT temperature, humidity, pressure, people_count, timestamp
                FROM sensor_data
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row:
                data = {
                    'temperature': round(row[0], 1) if row[0] else 0,
                    'humidity': round(row[1], 1) if row[1] else 0,
                    'pressure': round(row[2], 1) if row[2] else 0,
                    'people_count': row[3] or 0,
                    'last_detection': row[4] or 'Never',
                    'last_sync': datetime.now().strftime('%H:%M:%S'),
                    'system': 'online'
                }
            else:
                data = {
                    'temperature': 0,
                    'humidity': 0,
                    'pressure': 0,
                    'people_count': 0,
                    'last_detection': 'Never',
                    'last_sync': 'Never',
                    'system': 'offline'
                }
            
            conn.close()
            
        except Exception as e:
            print(f"Database error: {e}")
            data = {
                'temperature': 0,
                'humidity': 0,
                'pressure': 0,
                'people_count': 0,
                'last_detection': 'Error',
                'last_sync': 'Error',
                'system': 'error'
            }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def serve_sensors(self):
        """Serve detailed sensor data"""
        data = {
            'sensors': [
                {'name': 'Camera', 'status': 'active'},
                {'name': 'BME280', 'status': 'active'},
                {'name': 'Audio', 'status': 'active'}
            ]
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

def run_server():
    """Start the dashboard server"""
    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"🎵 Pulse Dashboard running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        server.shutdown()

if __name__ == '__main__':
    run_server()
