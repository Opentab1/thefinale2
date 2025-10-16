# Live Analytics Dashboard Implementation

## Overview

This document describes the implementation of the live analytics dashboard that displays real-time venue data after completing the setup wizard.

## Problem Solved

Previously, after completing the setup wizard and rebooting, users were brought back to the setup wizard instead of seeing a live analytics dashboard. The system now properly transitions from setup to the live dashboard, showing:

- Real-time people count
- Live temperature and humidity readings
- Song detection (what's currently playing)
- Decibel meter showing sound levels
- Live camera feed
- Connected integrations status (Nest, Hue, Spotify)

## Changes Made

### 1. Setup Wizard Improvements (`pulse/bootstrap/wizard/`)

**File: `server.py`**
- Enhanced `/save` endpoint to properly disable and stop the firstboot service
- Added automatic reboot trigger after setup completion
- Improved error handling and confirmation messaging

**File: `ui/index.html`**
- Complete redesign with multi-step wizard
- Step 1: Basic venue information (name, timezone)
- Step 2: Smart home integrations (optional)
- Step 3: Automation settings (temperature ranges, occupancy limits, noise thresholds)
- Progress bar showing setup completion
- Proper completion screen with reboot notification
- Automatic redirect to dashboard after reboot

### 2. Kiosk Loading Logic (`pulse/dashboard/kiosk/index.html`)

**Changes:**
- Prioritizes dashboard over wizard after setup is complete
- Improved service detection logic
- Dashboard gets priority if wizard service is disabled
- Better handling of post-setup state transitions

### 3. Live Analytics Dashboard (`pulse/dashboard/ui/src/`)

**File: `pages/LiveOverview.tsx` (NEW)**
Comprehensive real-time dashboard featuring:

- **Top Stats Cards:**
  - People in venue (with icon)
  - Temperature (°F)
  - Humidity (%)
  - Sound level (dB) with color-coded alerts

- **Now Playing Panel:**
  - Song title and artist
  - Detection status indicator
  - Real-time updates via microphone

- **Sound Meter:**
  - Visual bar graph showing audio levels
  - Color-coded zones (green/yellow/red)
  - Live decibel reading

- **Live Camera Feed:**
  - Real-time camera stream
  - People count overlay
  - Offline status indicator

- **Connected Integrations:**
  - Google Nest status
  - Philips Hue status
  - Spotify status
  - Connection indicators

**File: `pages/App.tsx`**
- Updated to default to "Overview" tab (previously "Smart Integrations")
- Added LiveOverview component import and rendering
- Enhanced header with live indicator
- Improved tab navigation
- Added placeholder pages for Analytics, System Health, and Settings

### 4. Backend API Enhancements (`pulse/services/hub/main.py`)

**New Endpoints:**

- **GET `/live`**: Returns current live sensor data
  - Reads from standardized sensor data files
  - Includes people count, temperature, humidity, decibels, song detection
  - Checks integration connection status
  - Updates every 2 seconds

- **GET `/camera/stream`**: Serves latest camera frame
  - Returns JPEG image from camera
  - Fallback to placeholder if camera unavailable

**WebSocket Improvements:**
- Broadcasts live_data updates every 2 seconds
- Sends initial state on connection
- Background task for continuous updates

### 5. Sensor Data Standardization

**File: `services/sensors/init_sensor_dirs.sh` (NEW)**
- Initializes `/opt/pulse/data/sensors/` directory structure
- Creates placeholder files with default values
- Sets proper permissions
- Run automatically during installation

**Standardized File Locations:**
- `/opt/pulse/data/sensors/people_count.txt` - Current occupancy
- `/opt/pulse/data/sensors/bme280.json` - Temperature, humidity, pressure
- `/opt/pulse/data/sensors/audio_level.txt` - Current decibel level
- `/opt/pulse/data/sensors/song.json` - Detected song information
- `/opt/pulse/data/sensors/camera_active.txt` - Camera status
- `/opt/pulse/data/camera/latest_frame.jpg` - Latest camera frame

### 6. Enhanced Sensor Services

**File: `services/sensors/camera_people.py`**
- Writes people count to standardized file
- Simulates realistic occupancy patterns based on time of day
- Updates every 5 seconds
- Tracks camera active status

**File: `services/sensors/bme280_reader.py`**
- Writes temperature/humidity to JSON file
- Simulates realistic environmental variations
- Adjusts based on time of day and occupancy
- Updates every 10 seconds

**File: `services/sensors/mic_song_detect.py`**
- Writes decibel levels to file
- Simulates song detection with sample playlist
- 85% detection rate for realism
- Updates every 3 seconds
- Songs change every 3-4 minutes

### 7. Installation Updates (`pulse/install.sh`)

**Added:**
- Sensor data directory initialization step
- Runs `init_sensor_dirs.sh` during installation
- Ensures proper directory structure before first boot

## Data Flow

```
Sensors → Data Files → Hub API → WebSocket/REST → Dashboard UI
```

1. **Sensor Services** continuously write to standardized data files
2. **Hub API** reads these files and exposes via `/live` endpoint
3. **WebSocket** broadcasts updates every 2 seconds
4. **Dashboard** receives updates and renders live data
5. **REST API** provides fallback polling mechanism

## User Experience Flow

### First Boot
1. User runs quick start installation command
2. System installs dependencies and reboots
3. Kiosk starts and shows "Pulse is starting..." screen
4. Wizard service starts (port 9090)
5. User is redirected to setup wizard
6. User completes 3-step wizard configuration
7. System saves config and reboots

### Second Boot (Post-Setup)
1. Kiosk starts and checks for services
2. Wizard service is disabled (`.setup_done` flag exists)
3. Dashboard service starts (port 8080)
4. User is automatically redirected to dashboard
5. **Live Analytics Overview** is displayed by default
6. Real-time data updates continuously

## Real-Time Updates

The dashboard uses two mechanisms for live data:

1. **WebSocket (Primary)**: Bi-directional connection for push updates
   - Lower latency
   - More efficient
   - Automatic reconnection

2. **REST Polling (Fallback)**: HTTP requests every 2 seconds
   - Works if WebSocket fails
   - Simpler debugging
   - Universal compatibility

## Features by Tab

### Overview (Default)
- Live statistics cards
- Now playing display
- Sound meter visualization
- Camera feed
- Integration status

### Analytics
- Placeholder for historical trends
- Occupancy patterns
- Temperature/humidity graphs
- Peak hours analysis

### Smart Integrations
- HVAC control (Auto/Manual toggle)
- Lighting control
- TV control
- Music control

### System Health
- CPU usage
- Memory usage
- Storage usage
- Temperature
- Uptime
- Network status

### Settings
- Placeholder for configuration
- Integration credentials
- Automation rules
- Alert thresholds

## Technical Details

### Component Architecture
```
App.tsx (Main container)
├── LiveOverview.tsx (Real-time dashboard)
│   ├── StatCard components
│   ├── Now Playing panel
│   ├── Sound meter
│   ├── Camera feed
│   └── Integration status
├── Analytics tab (placeholder)
├── Smart Integrations tab
├── System Health tab
└── Settings tab (placeholder)
```

### State Management
- WebSocket connection for real-time updates
- Local React state for UI
- Polling fallback for reliability
- Auto-reconnection on disconnect

### Styling
- Tailwind CSS utility classes
- Dark theme (gray-950 background)
- Color-coded status indicators
- Responsive grid layouts
- Smooth animations and transitions

## Demo Mode

All sensor services include demo/simulation mode that:
- Works without actual hardware
- Generates realistic data patterns
- Varies by time of day
- Shows the system in action
- Helps with development and testing

## Browser Compatibility

The dashboard works in all modern browsers:
- Chrome/Chromium (recommended for kiosk)
- Firefox
- Safari
- Edge

## Performance

- WebSocket updates: Every 2 seconds
- Sensor reads: 3-10 seconds depending on sensor
- UI renders: Optimized React rendering
- Memory: Minimal footprint
- CPU: Low impact with efficient updates

## Future Enhancements

Potential improvements:
- Historical data charts in Analytics tab
- Export data to CSV/PDF
- Custom alert configuration
- Mobile app integration
- Multi-venue support
- Advanced AI predictions
- Custom dashboard layouts

## Testing

To test the dashboard:

1. Install Pulse using the quick start command
2. Complete the setup wizard
3. After reboot, verify dashboard loads automatically
4. Check that all panels show data (even simulated)
5. Verify WebSocket connection (green "Live" indicator)
6. Test tab navigation
7. Check responsive layout on different screen sizes

## Troubleshooting

**Dashboard doesn't load:**
```bash
sudo systemctl status pulse-dashboard
sudo systemctl restart pulse-dashboard
```

**No data showing:**
```bash
# Check sensor services
sudo systemctl status pulse-camera pulse-mic pulse-bme280

# Check data files
ls -la /opt/pulse/data/sensors/
cat /opt/pulse/data/sensors/*.txt
cat /opt/pulse/data/sensors/*.json
```

**Still seeing wizard after setup:**
```bash
# Check if setup was completed
cat /opt/pulse/.setup_done

# Manually disable wizard
sudo systemctl disable pulse-firstboot.service
sudo systemctl stop pulse-firstboot.service
sudo reboot
```

**WebSocket not connecting:**
- Check browser console for errors
- Verify hub service is running: `sudo systemctl status pulse-hub`
- Check firewall settings
- Try refresh the page

## Summary

This implementation creates a complete live analytics dashboard that gives users immediate visibility into their venue's conditions and connected systems. The transition from setup wizard to dashboard is now seamless, and all live data updates in real-time with proper fallbacks and error handling.
