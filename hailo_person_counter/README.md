# Hailo Person Entry/Exit Counter

Real-time person counting application using Hailo AI Hat for Raspberry Pi.

## Features

- **Live person detection** with tracking IDs
- **Entry/Exit counting** - counts people crossing a center line
- **Visual indicators**:
  - Green vertical line down the center of the screen
  - Live entry and exit counters displayed in bottom left
  - Detection count and tracking information

## How It Works

- Detects when a person crosses the center line of the camera view
- **Entry**: Person moves from left to right across the line
- **Exit**: Person moves from right to left across the line
- Uses Hailo's tracking system to maintain unique IDs for each person

## Requirements

- Raspberry Pi with Hailo AI Hat
- Hailo detection apps installed
- Python dependencies from the Hailo apps repository

## Usage

```bash
python3 person_entry_exit_counter.py
```

## Display Information

- **Top left**: Detection count and example text
- **Center**: Green vertical line (crossing detection zone)
- **Bottom left**: 
  - Entries: [count]
  - Exits: [count]

All overlays are displayed in green for visibility.
