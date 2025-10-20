#!/bin/bash
# PULSE - Simple Startup
# Just run this script from the Pulse directory

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec bash "$SCRIPT_DIR/START_HERE.sh"
