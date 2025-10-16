"""
Pulse 1.0 - Local Music Playback
Fallback for when Spotify is not available
"""

import logging
import os
import subprocess
from typing import List, Dict, Optional
from pathlib import Path
import random

logger = logging.getLogger(__name__)

class LocalMusicController:
    def __init__(self, music_directory: str = "/opt/pulse/music"):
        self.music_directory = music_directory
        self.playlist = []
        self.current_index = 0
        self.is_playing = False
        self.volume = 50
        self.auto_mode = True
        
        # Ensure directory exists
        os.makedirs(self.music_directory, exist_ok=True)
        
        self._scan_music_directory()
    
    def _scan_music_directory(self):
        """Scan music directory for audio files"""
        try:
            audio_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.m4a']
            
            self.playlist = []
            music_path = Path(self.music_directory)
            
            for ext in audio_extensions:
                self.playlist.extend(list(music_path.rglob(f'*{ext}')))
            
            logger.info(f"Found {len(self.playlist)} audio files")
            
        except Exception as e:
            logger.error(f"Error scanning music directory: {e}")
    
    def get_playlist(self) -> List[Dict]:
        """Get current playlist"""
        return [{
            "index": i,
            "path": str(track),
            "filename": track.name
        } for i, track in enumerate(self.playlist)]
    
    def play_file(self, file_path: str) -> bool:
        """Play specific audio file"""
        try:
            # Kill any existing player
            self.stop()
            
            # Play using aplay/mpg123/ffplay
            if file_path.endswith('.wav'):
                cmd = ['aplay', file_path]
            elif file_path.endswith('.mp3'):
                cmd = ['mpg123', '-q', file_path]
            else:
                cmd = ['ffplay', '-nodisp', '-autoexit', file_path]
            
            # Start playback in background
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.is_playing = True
            logger.info(f"Playing: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error playing file: {e}")
            return False
    
    def play(self, index: int = None) -> bool:
        """Start playback at specific index or current"""
        if not self.playlist:
            logger.warning("Playlist is empty")
            return False
        
        if index is not None:
            self.current_index = max(0, min(len(self.playlist) - 1, index))
        
        track = self.playlist[self.current_index]
        return self.play_file(str(track))
    
    def stop(self) -> bool:
        """Stop playback"""
        try:
            # Kill audio players
            subprocess.run(['killall', 'aplay'], stderr=subprocess.DEVNULL)
            subprocess.run(['killall', 'mpg123'], stderr=subprocess.DEVNULL)
            subprocess.run(['killall', 'ffplay'], stderr=subprocess.DEVNULL)
            
            self.is_playing = False
            logger.info("Stopped playback")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            return False
    
    def next_track(self) -> bool:
        """Skip to next track"""
        if not self.playlist:
            return False
        
        self.current_index = (self.current_index + 1) % len(self.playlist)
        return self.play()
    
    def previous_track(self) -> bool:
        """Go to previous track"""
        if not self.playlist:
            return False
        
        self.current_index = (self.current_index - 1) % len(self.playlist)
        return self.play()
    
    def shuffle(self):
        """Shuffle playlist"""
        random.shuffle(self.playlist)
        self.current_index = 0
        logger.info("Playlist shuffled")
    
    def set_volume(self, volume_percent: int) -> bool:
        """Set system volume"""
        try:
            volume_percent = max(0, min(100, volume_percent))
            self.volume = volume_percent
            
            # Use amixer to set volume
            subprocess.run(
                ['amixer', 'sset', 'Master', f'{volume_percent}%'],
                capture_output=True
            )
            
            logger.info(f"Set volume to {volume_percent}%")
            return True
            
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return False
    
    def adjust_volume(self, delta: int) -> bool:
        """Adjust volume by delta"""
        new_volume = max(0, min(100, self.volume + delta))
        return self.set_volume(new_volume)
    
    def get_current_track(self) -> Dict:
        """Get currently playing track info"""
        if not self.playlist or self.current_index >= len(self.playlist):
            return {
                "is_playing": False,
                "track": None,
                "index": 0,
                "total": len(self.playlist)
            }
        
        track = self.playlist[self.current_index]
        
        return {
            "is_playing": self.is_playing,
            "track": track.name,
            "path": str(track),
            "index": self.current_index,
            "total": len(self.playlist),
            "volume": self.volume
        }
    
    def set_auto_mode(self, enabled: bool):
        """Enable/disable auto mode"""
        self.auto_mode = enabled
        logger.info(f"Auto mode {'enabled' if enabled else 'disabled'}")
    
    def is_auto_mode(self) -> bool:
        """Check if auto mode is enabled"""
        return self.auto_mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    controller = LocalMusicController()
    
    playlist = controller.get_playlist()
    print(f"Found {len(playlist)} tracks")
    
    if playlist:
        print("\nPlaylist:")
        for track in playlist[:5]:  # Show first 5
            print(f"  {track['index']}: {track['filename']}")
        
        if len(playlist) > 5:
            print(f"  ... and {len(playlist) - 5} more")
    else:
        print("No audio files found in music directory")
