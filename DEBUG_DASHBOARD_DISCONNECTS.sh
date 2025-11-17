#!/bin/bash
# DEBUG_DASHBOARD_DISCONNECTS.sh
# Comprehensive debugging script for dashboard connection issues

echo "🔍 PULSE DASHBOARD DISCONNECT DEBUGGER"
echo "========================================"
echo ""

echo "1️⃣ CHECKING SERVICE STATUS"
echo "----------------------------"
sudo systemctl status pulse-hub-main --no-pager | grep -E "Active|Main PID"
echo ""

echo "2️⃣ CHECKING RECENT HUB LOGS (Last 50 lines)"
echo "----------------------------------------------"
tail -50 /var/log/pulse/pulse-hub.log
echo ""

echo "3️⃣ CHECKING FOR SOCKETIO ERRORS"
echo "----------------------------------"
tail -100 /var/log/pulse/pulse-hub.log | grep -i "socket\|werkzeug\|error\|exception\|traceback"
echo ""

echo "4️⃣ CHECKING FOR DISCONNECT PATTERNS"
echo "--------------------------------------"
tail -200 /var/log/pulse/pulse-hub.log | grep -i "disconnect\|reconnect\|connection\|client"
echo ""

echo "5️⃣ CHECKING BROADCAST THREAD"
echo "------------------------------"
tail -100 /var/log/pulse/pulse-hub.log | grep -i "broadcast"
echo ""

echo "6️⃣ CHECKING HUB PROCESS INFO"
echo "------------------------------"
ps aux | grep "run_hub_service" | grep -v grep
echo ""

echo "7️⃣ CHECKING NETWORK CONNECTIONS (port 8080)"
echo "---------------------------------------------"
sudo netstat -tulpn | grep 8080 || sudo ss -tulpn | grep 8080
echo ""

echo "8️⃣ CHECKING FOR MEMORY ISSUES"
echo "-------------------------------"
free -h
echo ""

echo "9️⃣ CHECKING HUB ERROR LOG"
echo "---------------------------"
tail -50 /var/log/pulse/pulse-hub-error.log
echo ""

echo "🔟 TESTING SOCKETIO ENDPOINT"
echo "-----------------------------"
curl -s "http://localhost:8080/socket.io/?EIO=4&transport=polling" | head -20
echo ""

echo "1️⃣1️⃣ CHECKING PYTHON SOCKETIO VERSION"
echo "---------------------------------------"
/opt/pulse/venv/bin/pip show python-socketio flask-socketio | grep -E "Name|Version"
echo ""

echo "1️⃣2️⃣ REAL-TIME MONITORING (Press Ctrl+C to stop)"
echo "---------------------------------------------------"
echo "Watching for disconnects in real-time..."
tail -f /var/log/pulse/pulse-hub.log | grep --line-buffered -i "disconnect\|reconnect\|socket\|werkzeug error"
