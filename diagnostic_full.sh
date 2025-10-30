#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        PULSE SYSTEM COMPREHENSIVE DIAGNOSTIC                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_item() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. ENVIRONMENT CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -n "Working Directory: "
pwd

echo -n "User: "
whoami

echo -n "Python Version: "
python3 --version 2>&1 || echo "NOT FOUND"

echo -n "Node Version: "
node --version 2>&1 || echo "NOT FOUND"

echo -n "SQLite Version: "
sqlite3 --version 2>&1 || echo "NOT FOUND"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. PYTHON PACKAGES CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

packages=("flask" "flask-cors" "flask-socketio" "pyyaml" "sqlalchemy" "awsiotsdk")
for pkg in "${packages[@]}"; do
    if pip3 show "$pkg" &>/dev/null; then
        version=$(pip3 show "$pkg" | grep "Version:" | cut -d' ' -f2)
        check_item 0 "$pkg ($version)"
    else
        check_item 1 "$pkg - NOT INSTALLED"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. DIRECTORY STRUCTURE CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

dirs=(
    "/workspace/services/hub"
    "/workspace/services/sensors"
    "/workspace/services/storage"
    "/workspace/dashboard/api"
    "/workspace/config"
)

for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        check_item 0 "$dir exists"
    else
        check_item 1 "$dir NOT FOUND"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. CONFIGURATION FILES CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

configs=(
    "/workspace/config/config.yaml"
    "/workspace/pulse/config/config.yaml"
)

for config in "${configs[@]}"; do
    if [ -f "$config" ]; then
        check_item 0 "$config exists"
    else
        check_item 1 "$config NOT FOUND"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. AWS IOT CONFIGURATION CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -d "/etc/pulse/certs" ]; then
    check_item 0 "/etc/pulse/certs directory exists"
    
    certs=(
        "/etc/pulse/certs/AmazonRootCA1.pem"
        "/etc/pulse/certs/device.pem.crt"
        "/etc/pulse/certs/private.pem.key"
    )
    
    for cert in "${certs[@]}"; do
        if [ -f "$cert" ]; then
            check_item 0 "$(basename $cert) exists"
        else
            check_item 1 "$(basename $cert) NOT FOUND"
        fi
    done
else
    check_item 1 "/etc/pulse/certs directory NOT FOUND"
    echo -e "${YELLOW}   → AWS IoT certificates need to be set up${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. DATABASE CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

db_locations=(
    "/workspace/pulse.db"
    "/workspace/data/pulse.db"
    "/opt/pulse/data/pulse.db"
)

db_found=0
for db_path in "${db_locations[@]}"; do
    if [ -f "$db_path" ]; then
        check_item 0 "Database found at $db_path"
        db_found=1
        
        # Check tables
        echo "   Tables in database:"
        sqlite3 "$db_path" "SELECT name FROM sqlite_master WHERE type='table';" 2>/dev/null | sed 's/^/     - /'
        
        # Check record counts
        echo "   Record counts:"
        for table in occupancy environment music_log; do
            count=$(sqlite3 "$db_path" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
            echo "     - $table: $count records"
        done
        break
    fi
done

if [ $db_found -eq 0 ]; then
    check_item 1 "No database found in any standard location"
    echo -e "${YELLOW}   → Database needs to be created${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. RUNNING PROCESSES CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if pgrep -f "services/hub/main.py" > /dev/null; then
    check_item 0 "Hub service is running"
    pgrep -f "services/hub/main.py" | while read pid; do
        echo "     PID: $pid"
    done
else
    check_item 1 "Hub service is NOT running"
fi

if pgrep -f "dashboard/api/server.py" > /dev/null; then
    check_item 0 "Dashboard API is running"
    pgrep -f "dashboard/api/server.py" | while read pid; do
        echo "     PID: $pid"
    done
else
    check_item 1 "Dashboard API is NOT running"
fi

if pgrep -f "aws_send.py" > /dev/null; then
    check_item 0 "AWS IoT sender is running"
else
    check_item 1 "AWS IoT sender is NOT running"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8. NETWORK PORTS CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ports=("8080:Dashboard API" "3000:React Dev Server" "9090:Setup Wizard")
for port_info in "${ports[@]}"; do
    port="${port_info%%:*}"
    name="${port_info#*:}"
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        check_item 0 "Port $port ($name) is listening"
    else
        check_item 1 "Port $port ($name) is NOT listening"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "9. SUMMARY & RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo -e "${YELLOW}Based on this diagnostic, you need to:${NC}"
echo ""

# Check what's missing
if ! pip3 show flask &>/dev/null; then
    echo -e "${RED}[REQUIRED]${NC} Install Python dependencies"
    echo "   Command: pip3 install -r /workspace/requirements.txt"
    echo ""
fi

if [ ! -d "/etc/pulse/certs" ]; then
    echo -e "${YELLOW}[OPTIONAL]${NC} Set up AWS IoT certificates (for cloud sync)"
    echo "   See: /workspace/AWS_IOT_SETUP.md"
    echo ""
fi

if [ $db_found -eq 0 ]; then
    echo -e "${RED}[REQUIRED]${NC} Database needs to be created"
    echo "   This will happen automatically when hub starts"
    echo ""
fi

if ! pgrep -f "services/hub/main.py" > /dev/null; then
    echo -e "${RED}[REQUIRED]${NC} Start the hub service to collect sensor data"
    echo ""
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                  DIAGNOSTIC COMPLETE                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
