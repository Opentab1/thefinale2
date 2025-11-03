#!/bin/bash
# Quick fix script to install/repair audio dependencies for song detection

echo "=================================="
echo "Installing Audio Dependencies"
echo "=================================="

# Install system-level audio dependencies
echo "Installing system audio libraries..."
sudo apt-get update -qq
sudo apt-get install -y portaudio19-dev python3-pyaudio libasound2-dev

# Install Python audio packages
echo "Installing Python audio packages..."
pip3 install --upgrade numpy
pip3 install --upgrade sounddevice
pip3 install --upgrade pyaudio
pip3 install --upgrade shazamio
pip3 install --upgrade aiohttp

echo ""
echo "=================================="
echo "Audio Dependencies Installed"
echo "=================================="
echo ""
echo "Testing audio device availability..."
python3 -c "
import sounddevice as sd
try:
    devices = sd.query_devices()
    print('Available audio devices:')
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            print(f'  [{i}] {dev[\"name\"]} (Input channels: {dev[\"max_input_channels\"]})')
    print('')
    print('✓ Audio devices detected')
except Exception as e:
    print(f'✗ Error detecting audio devices: {e}')
    print('  You may need to connect a microphone or check ALSA configuration')
"

echo ""
echo "Testing ShazamIO installation..."
python3 -c "
try:
    from shazamio import Shazam
    print('✓ ShazamIO installed and importable')
except ImportError as e:
    print(f'✗ ShazamIO import failed: {e}')
    print('  Try: pip3 install --force-reinstall shazamio')
"

echo ""
echo "=================================="
echo "Installation Complete"
echo "=================================="
echo "Restart the Pulse system for changes to take effect"
