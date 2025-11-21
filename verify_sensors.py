#!/usr/bin/env python3
"""
Pulse Sensor Verification Script
Checks if your sensors are actively reading and displaying current data
"""

import os
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_status(label, value, status='info', unit=''):
    """Print a formatted status line"""
    color = Colors.GREEN if status == 'good' else Colors.YELLOW if status == 'warn' else Colors.RED if status == 'error' else Colors.BLUE
    print(f"  {Colors.BOLD}{label:.<40}{Colors.END} {color}{value}{unit}{Colors.END}")

def find_database():
    """Find the Pulse database"""
    possible_paths = [
        "/opt/pulse/data/pulse.db",
        os.path.join(os.getcwd(), "data", "pulse.db"),
        os.path.join(os.path.dirname(__file__), "data", "pulse.db"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    return cursor.fetchone() is not None

def get_latest_environment(cursor):
    """Get latest environmental sensor readings"""
    if not check_table_exists(cursor, 'environment'):
        return None
    
    cursor.execute('''
        SELECT timestamp, temperature, humidity, pressure, light_level, noise_level, zone
        FROM environment 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    row = cursor.fetchone()
    
    if row:
        return {
            'timestamp': row[0],
            'temperature': row[1],
            'humidity': row[2],
            'pressure': row[3],
            'light_level': row[4],
            'noise_level': row[5],
            'zone': row[6]
        }
    return None

def get_latest_occupancy(cursor):
    """Get latest occupancy data"""
    if not check_table_exists(cursor, 'occupancy'):
        return None
    
    cursor.execute('''
        SELECT timestamp, zone, count, entry_count, exit_count
        FROM occupancy 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''')
    row = cursor.fetchone()
    
    if row:
        return {
            'timestamp': row[0],
            'zone': row[1],
            'count': row[2],
            'entry_count': row[3],
            'exit_count': row[4]
        }
    return None

def get_sensor_reading_counts(cursor):
    """Get count of sensor readings in last hour"""
    if not check_table_exists(cursor, 'sensor_readings'):
        return {}
    
    cursor.execute('''
        SELECT sensor_type, COUNT(*) as count
        FROM sensor_readings
        WHERE timestamp >= datetime('now', '-1 hour')
        GROUP BY sensor_type
    ''')
    
    return {row[0]: row[1] for row in cursor.fetchall()}

def get_recent_activity(cursor, minutes=5):
    """Check if there's been any activity in the last N minutes"""
    tables = ['environment', 'occupancy', 'sensor_readings']
    activity = {}
    
    for table in tables:
        if not check_table_exists(cursor, table):
            continue
            
        cursor.execute(f'''
            SELECT COUNT(*) 
            FROM {table}
            WHERE timestamp >= datetime('now', '-{minutes} minutes')
        ''')
        count = cursor.fetchone()[0]
        activity[table] = count
    
    return activity

def format_timestamp(timestamp_str):
    """Format timestamp to show how long ago"""
    try:
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now()
        if ts.tzinfo:
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        delta = now - ts
        
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())} seconds ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)} minutes ago"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)} hours ago"
        else:
            return f"{int(delta.total_seconds() / 86400)} days ago"
    except:
        return timestamp_str

def main():
    print_header("🔍 PULSE SENSOR VERIFICATION")
    
    # Find database
    print(f"{Colors.BOLD}Looking for database...{Colors.END}")
    db_path = find_database()
    
    if not db_path:
        print_status("Database Status", "NOT FOUND", 'error')
        print(f"\n{Colors.RED}❌ Could not find pulse.db database!{Colors.END}")
        print(f"\n{Colors.YELLOW}Expected locations:{Colors.END}")
        print("  - /opt/pulse/data/pulse.db")
        print("  - ./data/pulse.db")
        print("\n💡 Make sure Pulse is running and has created the database.")
        return 1
    
    print_status("Database Location", db_path, 'good')
    print_status("Database Size", f"{os.path.getsize(db_path) / 1024:.1f} KB", 'info')
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check recent activity
        print_header("📊 RECENT ACTIVITY (Last 5 minutes)")
        activity = get_recent_activity(cursor, 5)
        
        total_activity = sum(activity.values())
        if total_activity == 0:
            print(f"{Colors.YELLOW}⚠️  No sensor activity detected in the last 5 minutes!{Colors.END}")
            print(f"{Colors.YELLOW}   This might mean sensors are not running or updating slowly.{Colors.END}\n")
        else:
            print(f"{Colors.GREEN}✓ Active sensor updates detected!{Colors.END}\n")
        
        for table, count in activity.items():
            status = 'good' if count > 0 else 'warn'
            print_status(f"{table.replace('_', ' ').title()} updates", str(count), status)
        
        # Environmental Sensors
        print_header("🌡️  ENVIRONMENTAL SENSORS")
        env_data = get_latest_environment(cursor)
        
        if env_data:
            age = format_timestamp(env_data['timestamp'])
            age_status = 'good' if 'seconds' in age or ('minute' in age and int(age.split()[0]) < 5) else 'warn'
            
            print_status("Last Update", age, age_status)
            print_status("Zone", env_data.get('zone') or 'N/A', 'info')
            
            if env_data.get('temperature'):
                print_status("Temperature", f"{env_data['temperature']:.1f}", 'good', "°F")
            else:
                print_status("Temperature", "No data", 'warn')
            
            if env_data.get('humidity'):
                print_status("Humidity", f"{env_data['humidity']:.1f}", 'good', "%")
            else:
                print_status("Humidity", "No data", 'warn')
            
            if env_data.get('pressure'):
                print_status("Pressure", f"{env_data['pressure']:.2f}", 'good', " hPa")
            else:
                print_status("Pressure", "No data", 'warn')
            
            if env_data.get('light_level') is not None:
                print_status("Light Level", f"{env_data['light_level']:.1f}", 'good', " lux")
            else:
                print_status("Light Level", "No data", 'warn')
            
            if env_data.get('noise_level'):
                print_status("Noise Level", f"{env_data['noise_level']:.1f}", 'good', " dB")
            else:
                print_status("Noise Level", "No data", 'info')
        else:
            print(f"{Colors.YELLOW}⚠️  No environmental data found in database{Colors.END}")
        
        # Occupancy / People Counter
        print_header("👥 PEOPLE COUNTER")
        occ_data = get_latest_occupancy(cursor)
        
        if occ_data:
            age = format_timestamp(occ_data['timestamp'])
            age_status = 'good' if 'seconds' in age or ('minute' in age and int(age.split()[0]) < 5) else 'warn'
            
            print_status("Last Update", age, age_status)
            print_status("Zone", occ_data.get('zone') or 'N/A', 'info')
            print_status("Current Count", str(occ_data['count']), 'good', " people")
            print_status("Total Entries", str(occ_data['entry_count']), 'info')
            print_status("Total Exits", str(occ_data['exit_count']), 'info')
        else:
            print(f"{Colors.YELLOW}⚠️  No occupancy data found in database{Colors.END}")
        
        # Sensor Reading History
        print_header("📈 SENSOR ACTIVITY (Last Hour)")
        readings = get_sensor_reading_counts(cursor)
        
        if readings:
            for sensor_type, count in sorted(readings.items()):
                status = 'good' if count > 10 else 'warn' if count > 0 else 'error'
                print_status(f"{sensor_type.replace('_', ' ').title()}", f"{count} readings", status)
        else:
            print(f"{Colors.YELLOW}⚠️  No sensor readings found in last hour{Colors.END}")
        
        # Summary
        print_header("✅ VERIFICATION SUMMARY")
        
        all_sensors_ok = True
        
        if not env_data:
            print(f"{Colors.YELLOW}⚠️  Environmental sensors: NO DATA{Colors.END}")
            all_sensors_ok = False
        elif env_data.get('temperature') and env_data.get('humidity'):
            print(f"{Colors.GREEN}✓ Environmental sensors: WORKING{Colors.END}")
        else:
            print(f"{Colors.YELLOW}⚠️  Environmental sensors: PARTIAL DATA{Colors.END}")
            all_sensors_ok = False
        
        if not occ_data:
            print(f"{Colors.YELLOW}⚠️  People counter: NO DATA{Colors.END}")
            all_sensors_ok = False
        else:
            print(f"{Colors.GREEN}✓ People counter: WORKING{Colors.END}")
        
        if total_activity == 0:
            print(f"{Colors.YELLOW}⚠️  Recent activity: NONE (sensors may be slow or stopped){Colors.END}")
            all_sensors_ok = False
        else:
            print(f"{Colors.GREEN}✓ Recent activity: DETECTED{Colors.END}")
        
        print()
        if all_sensors_ok:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 All sensors appear to be working correctly!{Colors.END}")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Some sensors may not be working or updating slowly.{Colors.END}")
            print(f"{Colors.YELLOW}   Check that Pulse services are running properly.{Colors.END}")
        
        print()
        
        conn.close()
        return 0
        
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error reading database: {e}{Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
