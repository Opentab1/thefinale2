#!/bin/bash
#
# PULSE - Simple Installation Script for Raspberry Pi
# Run this once to install Pulse, then use 'pulse' command to start
#

set -e

echo "════════════════════════════════════════════════════════════"
echo "  PULSE INSTALLATION"
echo "════════════════════════════════════════════════════════════"
echo ""

# Detect where we are
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$SCRIPT_DIR/services/hub/main.py" ]; then
    echo "❌ Error: This doesn't appear to be a Pulse directory"
    echo "   Missing: services/hub/main.py"
    exit 1
fi

echo "Installing Pulse from: $SCRIPT_DIR"
echo ""

# Determine install location
INSTALL_DIR="/opt/pulse"

if [ "$EUID" -eq 0 ]; then
    # Running as root/sudo - install to /opt/pulse
    INSTALL_DIR="/opt/pulse"
    INSTALL_AS_ROOT=true
else
    # Running as regular user - install to home directory
    INSTALL_DIR="$HOME/pulse"
    INSTALL_AS_ROOT=false
fi

echo "Install location: $INSTALL_DIR"
echo ""

# Ask for confirmation
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 0
fi

# Create directory
if [ "$INSTALL_AS_ROOT" = true ]; then
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
    chown -R pi:pi "$INSTALL_DIR" 2>/dev/null || chown -R $USER:$USER "$INSTALL_DIR"
else
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
fi

echo "✓ Files copied to $INSTALL_DIR"

# Install system-wide command
if [ "$INSTALL_AS_ROOT" = true ]; then
    cp "$INSTALL_DIR/start-pulse-anywhere" /usr/local/bin/pulse
    chmod +x /usr/local/bin/pulse
    echo "✓ Installed 'pulse' command to /usr/local/bin/pulse"
else
    mkdir -p "$HOME/.local/bin"
    cp "$INSTALL_DIR/start-pulse-anywhere" "$HOME/.local/bin/pulse"
    chmod +x "$HOME/.local/bin/pulse"
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        echo "✓ Added $HOME/.local/bin to PATH (restart terminal or run: source ~/.bashrc)"
    fi
    echo "✓ Installed 'pulse' command to $HOME/.local/bin/pulse"
fi

# Create necessary directories
mkdir -p /var/log/pulse 2>/dev/null || mkdir -p "$HOME/.pulse/logs"
mkdir -p /opt/pulse/data 2>/dev/null || mkdir -p "$HOME/.pulse/data"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ INSTALLATION COMPLETE!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "To start Pulse, simply run:"
echo ""
echo "    pulse"
echo ""
if [ "$INSTALL_AS_ROOT" = false ]; then
    echo "Note: If 'pulse' command not found, run:"
    echo "    source ~/.bashrc"
    echo "Or restart your terminal, then run 'pulse'"
    echo ""
fi
echo "The command works from anywhere!"
echo "════════════════════════════════════════════════════════════"
