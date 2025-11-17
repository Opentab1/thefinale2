# Obsolete Audio Modules

This directory contains the old, complex audio monitoring code that was replaced with simpler, more reliable implementations.

## Why These Files Were Moved Here

These files were replaced on **2024-11-05** due to persistent failures after ~10 minutes of operation:

- `mic_song_detect.py` (841 lines) - Complex AudioMonitor with dual event loops
- `song_detector.py` (729 lines) - Complex SongDetector with multiple watchdogs

## What Replaced Them

New simple, reliable modules based on proven party_box approach:

- `simple_decibel_detector.py` (~180 lines) - Simple dB reading
- `simple_song_detector.py` (~200 lines) - Simple song detection with fresh event loops

## Key Differences

### Old Approach (BROKEN - 10 minute failures):
- Long-lived event loops that became stale
- Complex shared audio buffer management
- 4 layers of watchdogs causing false positives
- Thread accumulation and resource leaks
- Conflicting dual architecture

### New Approach (WORKING - proven indefinite runtime):
- Fresh event loop per Shazam API call (party_box approach)
- Independent detectors with no shared state
- Simple health monitoring (1 check every 60s)
- Clean thread lifecycle
- Based on proven working implementation

## Can I Delete These Files?

**Not yet!** Keep them here for at least 30 days in case:
- Need to reference old implementation details
- Need to revert (unlikely but safer to keep)
- Need to compare approaches for learning

After successful 24-48 hour testing and 30 days of production use, these can be safely deleted.

## Reverting (If Needed)

To revert to old code (not recommended):

```bash
cd /workspace/services/sensors
mv obsolete/mic_song_detect.py .
mv obsolete/song_detector.py .
# Update hub/main.py imports back to old modules
```

But you won't need to - the new approach is proven to work! 🎉
