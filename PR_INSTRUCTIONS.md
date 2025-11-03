# Pull Request Instructions

## Branch Information
- **Branch**: `cursor/debug-song-and-temp-readings-38c0`
- **Base**: `main`
- **Commit**: `f93f416` - "Fix BME280 temperature fallback and improve song detection logging"

## PR Title
```
Fix temperature display and song detection issues
```

## PR Description

```markdown
## Issues Fixed

### 1. Temperature Not Displaying on Dashboard
- **Problem**: Temperature readings were showing as "-" or None on the dashboard
- **Root Cause**: BME280 sensor was using cached values, but if cache wasn't populated or thread failed, values would be None
- **Fix**: Added fallback logic to perform direct sensor read if cached values are None
- **Location**: `services/hub/main.py` - `_collect_sensor_data()` method

### 2. Song Detection Not Working
- **Problem**: Song detection was not identifying songs playing
- **Root Cause**: Silent failures, no clear logging to diagnose issues, ShazamIO initialization not verified
- **Fix**: 
  - Added explicit ShazamIO availability check during initialization
  - Added better error handling for ImportError when ShazamIO is missing
  - Added debug logging to show detection attempts, buffer status, and API responses
- **Locations**: 
  - `services/hub/main.py` - Added logging for song detection status
  - `services/sensors/mic_song_detect.py` - Improved initialization and error handling

## Changes Made
- Added fallback temperature reading when cache is None
- Improved error handling and logging for BME280 sensor
- Added ShazamIO availability checks and better initialization logging
- Enhanced song detection error messages and debugging information
- Added diagnostic documentation in TEMP_AND_SONG_FIX.md

## Files Changed
- `services/hub/main.py` - Temperature fallback logic
- `services/sensors/mic_song_detect.py` - Song detection improvements
- `TEMP_AND_SONG_FIX.md` - Diagnostic documentation

## Testing
After restarting the Pulse Hub service, users should see:
- Temperature readings appearing on the dashboard (with fallback if cache fails)
- Song detection attempting every 30 seconds with clear logging
- Better diagnostic information in logs to troubleshoot any remaining issues

## Related Issues
Fixes temperature display and song detection issues reported by users.
```

## How to Create the PR

### Option 1: Via GitHub Web Interface
1. Go to: https://github.com/Opentab1/thefinale2/compare/main...cursor/debug-song-and-temp-readings-38c0
2. Click "Create pull request"
3. Use the title and description above
4. Submit the PR

### Option 2: Via GitHub CLI (if authenticated)
```bash
gh pr create \
  --title "Fix temperature display and song detection issues" \
  --body "$(cat PR_INSTRUCTIONS.md | sed -n '/## PR Description/,/^##/p' | sed '1d;$d')" \
  --base main \
  --head cursor/debug-song-and-temp-readings-38c0
```

### Option 3: Direct URL
Visit this URL to create the PR:
https://github.com/Opentab1/thefinale2/compare/main...cursor/debug-song-and-temp-readings-38c0?expand=1&title=Fix%20temperature%20display%20and%20song%20detection%20issues

## Branch Status
✅ All changes committed
✅ Branch pushed to origin
✅ Ready for PR creation
