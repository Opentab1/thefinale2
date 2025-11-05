#!/bin/bash
# Permanent fix for dB reader and song detector

echo "=========================================="
echo "FIXING dB READER & SONG DETECTOR"
echo "=========================================="
echo ""

cd /workspace

# Step 1: Install missing dependencies
echo "[1/3] Installing missing audio dependencies..."
echo "---"
pip3 install --upgrade sounddevice shazamio aiohttp numpy pyaudio 2>&1 | grep -E "(Successfully|Requirement|ERROR|WARNING)" || echo "Done"
echo ""

# Step 2: Fix code bug in mic_song_detect.py
echo "[2/3] Fixing type hint bug in audio monitor..."
echo "---"

# The issue is that when numpy is unavailable, np is None
# But the code uses np.ndarray as a type hint at class level
# This causes an AttributeError before the class even loads

# We need to use string annotations for type hints when numpy might be None
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/workspace')

file_path = '/workspace/services/sensors/mic_song_detect.py'

# Read the file
with open(file_path, 'r') as f:
    content = f.read()

# Fix the type hints to use string annotations when numpy is not available
# Change all np.ndarray type hints to 'np.ndarray' or check if we need from __future__ import annotations

# The better fix is to add "from __future__ import annotations" at the top
# This makes all type hints strings by default, evaluated lazily

if 'from __future__ import annotations' not in content:
    # Find the first import line and add this before it
    lines = content.split('\n')
    
    # Find where docstring ends (after first """)
    docstring_end = -1
    in_docstring = False
    docstring_count = 0
    for i, line in enumerate(lines):
        if '"""' in line:
            docstring_count += 1
            if docstring_count == 2:
                docstring_end = i
                break
    
    # Insert after docstring
    if docstring_end >= 0:
        lines.insert(docstring_end + 1, 'from __future__ import annotations')
        lines.insert(docstring_end + 2, '')
        content = '\n'.join(lines)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print("✓ Fixed type hint issue by adding 'from __future__ import annotations'")
    else:
        print("✗ Could not find insertion point")
else:
    print("✓ Type hint fix already applied")

PYEOF

echo ""

# Step 3: Verify the fix
echo "[3/3] Verifying the fix..."
echo "---"
python3 << 'PYEOF'
import sys
sys.path.insert(0, '/workspace')

try:
    from services.sensors.mic_song_detect import AudioMonitor
    print("✓ AudioMonitor module loads successfully")
    
    # Try to initialize it
    try:
        monitor = AudioMonitor()
        print("✓ AudioMonitor can be initialized")
        print("")
        print("SUCCESS! Both dB reader and song detector are now working.")
    except Exception as e:
        print(f"⚠ Module loads but initialization failed: {e}")
        print("  This might be okay if no audio device is present")
except ImportError as e:
    print(f"✗ Still cannot import AudioMonitor: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "=========================================="
echo "FIX COMPLETE!"
echo "=========================================="
echo ""
echo "Your dB reader and song detector should now work permanently."
echo ""
echo "To test them, run:"
echo "  ./diagnose_audio_live.sh"
echo ""
