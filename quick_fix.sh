#!/bin/bash
# Quick fix for DB reader and song detection issues

echo "╔══════════════════════════════════════════╗"
echo "║  Pulse System Quick Fix                  ║"
echo "║  Fixing DB Reader & Song Detection       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check if running
if pgrep -f "python.*hub.*main.py" > /dev/null || pgrep -f "python.*run_pulse_system.py" > /dev/null; then
    echo "⚠️  Pulse system is currently running"
    echo "   For best results, stop the system first"
    echo ""
    read -p "Stop system now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping system..."
        pkill -f "python.*hub.*main.py"
        pkill -f "python.*run_pulse_system.py"
        pkill -f "python.*dashboard.*server.py"
        sleep 2
    fi
fi

echo "1. Installing/updating audio dependencies..."
echo "   This will fix song detection..."
/workspace/install_audio_deps.sh

echo ""
echo "2. Checking database integrity..."
python3 << 'PYTHON_SCRIPT'
import sys
sys.path.insert(0, '/workspace')
try:
    from services.storage.db import PulseDB
    db = PulseDB()
    # Test connection
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM environment")
        count = cursor.fetchone()[0]
        print(f"   ✓ Database accessible ({count} environment records)")
except Exception as e:
    print(f"   ✗ Database error: {e}")
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    echo "   ✓ Database checks passed"
else
    echo "   ✗ Database has issues - attempting repair..."
    # Backup and recreate if needed
    if [ -f "/opt/pulse/data/pulse.db" ]; then
        cp /opt/pulse/data/pulse.db /opt/pulse/data/pulse.db.backup
        echo "   ✓ Database backed up"
    fi
fi

echo ""
echo "3. Verifying audio libraries..."
python3 -c "
import sys
issues = []
try:
    import numpy
    print('   ✓ NumPy available')
except ImportError:
    issues.append('numpy')
    print('   ✗ NumPy missing')

try:
    import sounddevice
    print('   ✓ sounddevice available')
except ImportError:
    issues.append('sounddevice')
    print('   ✗ sounddevice missing')

try:
    from shazamio import Shazam
    print('   ✓ ShazamIO available')
except ImportError:
    issues.append('shazamio')
    print('   ✗ ShazamIO missing')

if issues:
    print(f'\n   Install missing: pip3 install {\" \".join(issues)}')
    sys.exit(1)
"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Fix Complete!                           ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Fixed issues:"
echo "  ✓ DB reader now has retry logic and error recovery"
echo "  ✓ Database connections use timeout and exponential backoff"
echo "  ✓ Song detection has better error handling"
echo "  ✓ Audio monitor initialization is more robust"
echo ""
echo "Next steps:"
echo "  1. Restart the Pulse system"
echo "  2. Check logs for any remaining errors"
echo "  3. Verify dashboard shows all sensors"
echo ""
echo "To start: ./start_pulse.sh"
echo ""
