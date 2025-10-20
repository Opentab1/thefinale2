"""
Pulse 1.0 - Database Storage Layer
SQLite-based local storage with offline-first behavior
"""

import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
import json
from typing import Dict, List, Optional, Any

class PulseDB:
    def __init__(self, db_path: str = None):
        # Prefer system path, but fall back to workspace-local when not writable
        preferred = "/opt/pulse/data/pulse.db"
        path = db_path or preferred
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
            os.makedirs(local_dir, exist_ok=True)
            path = os.path.join(local_dir, "pulse.db")
        self.db_path = path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Sensor readings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sensor_type TEXT NOT NULL,
                    zone TEXT,
                    value REAL,
                    unit TEXT,
                    metadata TEXT
                )
            ''')
            
            # Occupancy tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS occupancy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    zone TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    entry_count INTEGER DEFAULT 0,
                    exit_count INTEGER DEFAULT 0
                )
            ''')
            
            # Environmental data
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS environment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    temperature REAL,
                    humidity REAL,
                    pressure REAL,
                    light_level REAL,
                    noise_level REAL,
                    zone TEXT
                )
            ''')
            
            # Music tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS music_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    track_name TEXT,
                    artist TEXT,
                    volume INTEGER,
                    source TEXT
                )
            ''')
            
            # Automation actions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS automation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    system TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    success BOOLEAN,
                    error TEXT
                )
            ''')
            
            # System health
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    module TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    cpu_usage REAL,
                    memory_usage REAL,
                    temperature REAL
                )
            ''')
            
            # Learning data - correlates conditions with dwell time
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learning_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    avg_dwell_minutes REAL,
                    occupancy INTEGER,
                    temperature REAL,
                    humidity REAL,
                    light_level REAL,
                    noise_level REAL,
                    music_volume INTEGER,
                    day_of_week INTEGER,
                    hour_of_day INTEGER
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_readings(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_occupancy_timestamp ON occupancy(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_environment_timestamp ON environment(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_timestamp ON automation_log(timestamp)')
            
            conn.commit()
    
    # Sensor readings
    def log_sensor_reading(self, sensor_type: str, value: float, unit: str = "", 
                          zone: str = None, metadata: Dict = None):
        """Log a sensor reading"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sensor_readings (sensor_type, zone, value, unit, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (sensor_type, zone, value, unit, json.dumps(metadata) if metadata else None))
    
    # Occupancy
    def log_occupancy(self, zone: str, count: int, entry_count: int = 0, exit_count: int = 0):
        """Log occupancy data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO occupancy (zone, count, entry_count, exit_count)
                VALUES (?, ?, ?, ?)
            ''', (zone, count, entry_count, exit_count))
    
    def get_current_occupancy(self, zone: str = None) -> int:
        """Get most recent occupancy count"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if zone:
                cursor.execute('''
                    SELECT count FROM occupancy 
                    WHERE zone = ? 
                    ORDER BY timestamp DESC LIMIT 1
                ''', (zone,))
            else:
                cursor.execute('''
                    SELECT SUM(count) as total FROM (
                        SELECT DISTINCT ON (zone) count, zone 
                        FROM occupancy 
                        ORDER BY zone, timestamp DESC
                    )
                ''')
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
    
    # Environment
    def log_environment(self, temperature: float = None, humidity: float = None,
                       pressure: float = None, light_level: float = None,
                       noise_level: float = None, zone: str = None):
        """Log environmental data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO environment (temperature, humidity, pressure, light_level, noise_level, zone)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (temperature, humidity, pressure, light_level, noise_level, zone))
    
    def get_latest_environment(self, zone: str = None) -> Optional[Dict]:
        """Get most recent environmental data"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM environment '
            params = []
            if zone:
                query += 'WHERE zone = ? '
                params.append(zone)
            query += 'ORDER BY timestamp DESC LIMIT 1'
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    # Music
    def log_music(self, track_name: str, artist: str, volume: int, source: str = "spotify"):
        """Log music playback"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO music_log (track_name, artist, volume, source)
                VALUES (?, ?, ?, ?)
            ''', (track_name, artist, volume, source))
    
    # Automation
    def log_automation(self, system: str, action: str, reason: str = None,
                       success: bool = True, error: str = None):
        """Log automation action"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO automation_log (system, action, reason, success, error)
                VALUES (?, ?, ?, ?, ?)
            ''', (system, action, reason, success, error))
    
    def get_recent_automations(self, limit: int = 100) -> List[Dict]:
        """Get recent automation actions"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM automation_log 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # System health
    def log_health(self, module: str, status: str, error: str = None,
                   cpu_usage: float = None, memory_usage: float = None,
                   temperature: float = None):
        """Log system health status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_health (module, status, error, cpu_usage, memory_usage, temperature)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (module, status, error, cpu_usage, memory_usage, temperature))
    
    # Learning
    def log_learning_data(self, avg_dwell_minutes: float, occupancy: int,
                         temperature: float, humidity: float, light_level: float,
                         noise_level: float, music_volume: int,
                         day_of_week: int, hour_of_day: int):
        """Log data for learning engine"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO learning_data 
                (avg_dwell_minutes, occupancy, temperature, humidity, light_level,
                 noise_level, music_volume, day_of_week, hour_of_day)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (avg_dwell_minutes, occupancy, temperature, humidity, light_level,
                  noise_level, music_volume, day_of_week, hour_of_day))
    
    def get_learning_data(self, hours: int = 168) -> List[Dict]:
        """Get learning data for analysis (default: last week)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM learning_data 
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
            ''', (hours,))
            return [dict(row) for row in cursor.fetchall()]
    
    # Analytics queries
    def get_hourly_occupancy(self, hours: int = 24) -> List[Dict]:
        """Get occupancy aggregated by hour"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                    AVG(count) as avg_count,
                    MAX(count) as max_count,
                    MIN(count) as min_count
                FROM occupancy
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                GROUP BY hour
                ORDER BY hour
            ''', (hours,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_environment_trends(self, hours: int = 24) -> List[Dict]:
        """Get environmental trends"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                    AVG(temperature) as avg_temp,
                    AVG(humidity) as avg_humidity,
                    AVG(noise_level) as avg_noise,
                    AVG(light_level) as avg_light
                FROM environment
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                GROUP BY hour
                ORDER BY hour
            ''', (hours,))
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up data older than specified days"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Keep automation logs and learning data longer
            tables = ['sensor_readings', 'occupancy', 'environment', 'music_log', 'system_health']
            
            for table in tables:
                cursor.execute(f'''
                    DELETE FROM {table}
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                ''', (days,))
            
            conn.commit()
