"""
Pulse 1.0 - Database Storage Layer
SQLite-based local storage with offline-first behavior
WITH CONNECTION POOLING AND AUTO-RECOVERY
"""

import os
import sqlite3
import time
import threading
from datetime import datetime
from contextlib import contextmanager
from queue import Queue, Empty
import json
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)

class PulseDB:
    def __init__(self, db_path: str = None, pool_size: int = 5):
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
        
        # CRITICAL FIX: Implement connection pooling to prevent exhaustion
        self.pool_size = pool_size
        self._connection_pool = Queue(maxsize=pool_size)
        self._pool_lock = threading.Lock()
        self._connections_created = 0
        self._last_health_check = 0.0
        self._health_check_interval = 30.0  # Check health every 30 seconds
        
        # Initialize database schema
        self._init_database()
        
        # Pre-populate connection pool
        self._populate_pool()
        
        logger.info(f"✅ Database initialized with connection pool (size={pool_size}, path={self.db_path})")
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimal settings"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            conn.execute('PRAGMA journal_mode=WAL')
            # Set busy timeout to handle lock contention
            conn.execute('PRAGMA busy_timeout=5000')
            # CRITICAL FIX: Set synchronous mode for better performance
            conn.execute('PRAGMA synchronous=NORMAL')
            # CRITICAL FIX: Enable automatic checkpoint management
            conn.execute('PRAGMA wal_autocheckpoint=1000')
            # Cache size for better performance
            conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
            self._connections_created += 1
            logger.debug(f"Created new database connection (total: {self._connections_created})")
            return conn
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise
    
    def _populate_pool(self):
        """Pre-populate the connection pool"""
        for _ in range(self.pool_size):
            try:
                conn = self._create_connection()
                self._connection_pool.put(conn, block=False)
            except Exception as e:
                logger.error(f"Failed to populate connection pool: {e}")
                break
    
    def _validate_connection(self, conn: sqlite3.Connection) -> bool:
        """Validate a connection is still healthy"""
        try:
            conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False
    
    def _get_pooled_connection(self, timeout: float = 5.0) -> sqlite3.Connection:
        """Get a connection from the pool with health check"""
        try:
            # Try to get from pool
            conn = self._connection_pool.get(timeout=timeout)
            
            # Validate connection
            if self._validate_connection(conn):
                return conn
            else:
                # Connection is dead, create new one
                logger.warning("Pooled connection failed validation, creating new one")
                try:
                    conn.close()
                except Exception:
                    pass
                return self._create_connection()
        except Empty:
            # Pool is exhausted, create temporary connection
            logger.warning("Connection pool exhausted, creating temporary connection")
            return self._create_connection()
    
    def _return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool"""
        try:
            if self._validate_connection(conn):
                self._connection_pool.put(conn, block=False)
            else:
                # Connection is bad, close it and create new one for pool
                logger.warning("Returning invalid connection, creating replacement")
                try:
                    conn.close()
                except Exception:
                    pass
                # Create replacement
                new_conn = self._create_connection()
                self._connection_pool.put(new_conn, block=False)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            # Try to close the connection at least
            try:
                conn.close()
            except Exception:
                pass
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections WITH CONNECTION POOLING"""
        conn = None
        max_retries = 3
        retry_delay = 0.5
        
        # Periodic health check
        current_time = time.time()
        if current_time - self._last_health_check > self._health_check_interval:
            self._check_pool_health()
            self._last_health_check = current_time
        
        for attempt in range(max_retries):
            try:
                conn = self._get_pooled_connection()
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to get connection (attempt {attempt + 1}): {e}, retrying...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to get connection after {max_retries} attempts")
                    raise
        
        try:
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise e
        finally:
            if conn:
                self._return_connection(conn)
    
    def _check_pool_health(self):
        """Check and repair connection pool health"""
        try:
            # Count healthy connections
            healthy_count = 0
            temp_conns = []
            
            # Drain and check all connections
            while not self._connection_pool.empty():
                try:
                    conn = self._connection_pool.get(block=False)
                    if self._validate_connection(conn):
                        healthy_count += 1
                        temp_conns.append(conn)
                    else:
                        # Close bad connection
                        try:
                            conn.close()
                        except Exception:
                            pass
                except Empty:
                    break
            
            # Return healthy connections to pool
            for conn in temp_conns:
                try:
                    self._connection_pool.put(conn, block=False)
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
            
            # Create new connections if pool is under-populated
            needed = self.pool_size - healthy_count
            if needed > 0:
                logger.warning(f"Connection pool has {healthy_count}/{self.pool_size} healthy connections, creating {needed} new ones")
                for _ in range(needed):
                    try:
                        new_conn = self._create_connection()
                        self._connection_pool.put(new_conn, block=False)
                    except Exception as e:
                        logger.error(f"Failed to create replacement connection: {e}")
                        break
            
            logger.debug(f"Connection pool health check: {healthy_count + needed}/{self.pool_size} connections")
        except Exception as e:
            logger.error(f"Error during connection pool health check: {e}")
    
    def _init_database(self):
        """Initialize database schema"""
        # Use a temporary connection for initialization
        conn = None
        try:
            conn = self._create_connection()
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
            logger.info("✅ Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
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
    
    def close_all_connections(self):
        """Close all pooled connections (call on shutdown)"""
        logger.info("Closing all database connections...")
        closed_count = 0
        while not self._connection_pool.empty():
            try:
                conn = self._connection_pool.get(block=False)
                conn.close()
                closed_count += 1
            except Exception:
                pass
        logger.info(f"Closed {closed_count} database connections")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics for monitoring"""
        return {
            "pool_size": self.pool_size,
            "available_connections": self._connection_pool.qsize(),
            "connections_created": self._connections_created,
            "last_health_check": self._last_health_check,
            "db_path": self.db_path
        }
