#!/bin/bash
################################################################################
# Pulse 1.0 - ONE-LINE STARTUP
# No AWS Amplify, Just Local Dashboard + AWS IoT Core Sync
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎵  PULSE 1.0 - LOCAL DASHBOARD STARTUP              ║
║                                                           ║
║     ✅ NO AWS Amplify                                     ║
║     ✅ NO Authentication                                  ║
║     ✅ Local Dashboard on :8080                           ║
║     ✅ AWS IoT Core Sync (Optional)                       ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}📍 Root directory: $ROOT_DIR${NC}"

################################################################################
# 1. Install System Dependencies
################################################################################
echo -e "\n${GREEN}[1/5] Installing system dependencies...${NC}"

if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv sqlite3 > /dev/null 2>&1
    echo "✅ System packages installed"
else
    echo "⚠️  Not on Debian/Ubuntu - skipping apt-get"
fi

################################################################################
# 2. Create Python Virtual Environment
################################################################################
echo -e "\n${GREEN}[2/5] Setting up Python environment...${NC}"

if [ ! -d "$ROOT_DIR/venv" ]; then
    python3 -m venv "$ROOT_DIR/venv"
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment exists"
fi

# Activate venv
source "$ROOT_DIR/venv/bin/activate"

# Install Python dependencies
pip install --quiet --upgrade pip
pip install --quiet -r "$ROOT_DIR/requirements.txt"

# Install AWS IoT SDK (optional)
if ! pip show awsiotsdk &> /dev/null; then
    echo "📦 Installing AWS IoT SDK..."
    pip install --quiet awsiotsdk || echo "⚠️  AWS IoT SDK install failed - will run in mock mode"
fi

echo "✅ Python dependencies installed"

################################################################################
# 3. Initialize Database
################################################################################
echo -e "\n${GREEN}[3/5] Initializing database...${NC}"

DB_DIR="$ROOT_DIR/services/storage"
DB_FILE="$DB_DIR/pulse.db"

mkdir -p "$DB_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "Creating database schema..."
    sqlite3 "$DB_FILE" << 'EOF'
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temperature REAL,
    humidity REAL,
    pressure REAL,
    people_count INTEGER DEFAULT 0,
    light_level REAL,
    song_detected TEXT
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_data(timestamp DESC);

-- Insert sample data
INSERT INTO sensor_data (timestamp, temperature, humidity, pressure, people_count)
VALUES 
    (datetime('now'), 22.5, 45.2, 1013.2, 0),
    (datetime('now', '-5 minutes'), 22.3, 45.5, 1013.1, 2),
    (datetime('now', '-10 minutes'), 22.1, 46.0, 1013.0, 1);
EOF
    echo "✅ Database initialized with sample data"
else
    echo "✅ Database exists"
fi

################################################################################
# 4. Configure AWS IoT Core (Optional)
################################################################################
echo -e "\n${GREEN}[4/5] AWS IoT Core setup...${NC}"

CERT_DIR="$HOME/.pulse/certs"

if [ ! -d "$CERT_DIR" ]; then
    echo "⚠️  AWS IoT certificates not found"
    echo ""
    echo "To enable AWS IoT Core sync:"
    echo "  1. Create Thing in AWS IoT Core"
    echo "  2. Download certificates to: $CERT_DIR"
    echo "     - AmazonRootCA1.pem"
    echo "     - device.pem.crt"
    echo "     - private.pem.key"
    echo "  3. Update IOT_ENDPOINT in rpi/aws_send.py"
    echo ""
    echo "Continuing without AWS sync..."
else
    echo "✅ AWS IoT certificates found"
fi

################################################################################
# 5. Start Services
################################################################################
echo -e "\n${GREEN}[5/5] Starting services...${NC}"

# Kill any existing processes
pkill -f "old_dashboard.py" 2>/dev/null || true
pkill -f "aws_send.py" 2>/dev/null || true

# Make scripts executable
chmod +x "$SCRIPT_DIR/old_dashboard.py"
chmod +x "$SCRIPT_DIR/aws_send.py"

# Start dashboard in background
echo "🚀 Starting local dashboard on port 8080..."
nohup python3 "$SCRIPT_DIR/old_dashboard.py" > /tmp/pulse_dashboard.log 2>&1 &
DASHBOARD_PID=$!

sleep 2

# Check if dashboard started
if ps -p $DASHBOARD_PID > /dev/null; then
    echo "✅ Dashboard running (PID: $DASHBOARD_PID)"
else
    echo "❌ Dashboard failed to start. Check /tmp/pulse_dashboard.log"
    exit 1
fi

# Start AWS IoT sender in background (if certificates exist)
if [ -d "$CERT_DIR" ]; then
    echo "🚀 Starting AWS IoT sender..."
    nohup python3 "$SCRIPT_DIR/aws_send.py" > /tmp/pulse_aws.log 2>&1 &
    AWS_PID=$!
    echo "✅ AWS sender running (PID: $AWS_PID)"
else
    echo "⏭️  Skipping AWS IoT sender (no certificates)"
fi

################################################################################
# Done!
################################################################################
echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}║     ✅  PULSE 1.0 IS RUNNING!                             ║${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}║     🌐 Dashboard: http://localhost:8080                   ║${NC}"
echo -e "${GREEN}║     📊 Status:    http://localhost:8080/api/status        ║${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}║     📝 Logs:                                              ║${NC}"
echo -e "${GREEN}║        Dashboard: /tmp/pulse_dashboard.log                ║${NC}"
echo -e "${GREEN}║        AWS IoT:   /tmp/pulse_aws.log                      ║${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}║     🛑 To stop:   pkill -f \"old_dashboard.py\"            ║${NC}"
echo -e "${GREEN}║                                                           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${YELLOW}💡 ONE-LINE COMMAND:${NC}"
echo -e "${BLUE}   bash rpi/startup.sh${NC}\n"
