"""
Pulse 1.0 - Spotify Music Control
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

class SpotifyController:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        
        self.sp = None
        self.auto_mode = True
        self.current_device_id = None
        
        self._init_spotify()
    
    def _init_spotify(self):
        """Initialize Spotify client"""
        try:
            scope = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing"
            
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=scope,
                cache_path="/opt/pulse/data/.spotify_cache"
            )
            
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            
            logger.info("Spotify client initialized")
            
            # Get available devices
            devices = self.get_devices()
            if devices:
                # Use first active device or just first device
                active = next((d for d in devices if d['is_active']), devices[0])
                self.current_device_id = active['id']
                logger.info(f"Using device: {active['name']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Spotify: {e}")
            raise
    
    def get_devices(self) -> List[Dict]:
        """Get available playback devices"""
        try:
            result = self.sp.devices()
            devices = result.get('devices', [])
            
            return [{
                "id": d['id'],
                "name": d['name'],
                "type": d['type'],
                "is_active": d['is_active'],
                "volume_percent": d['volume_percent']
            } for d in devices]
            
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []
    
    def set_device(self, device_id: str) -> bool:
        """Set active playback device"""
        try:
            self.sp.transfer_playback(device_id, force_play=False)
            self.current_device_id = device_id
            logger.info(f"Set device to {device_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting device: {e}")
            return False
    
    def get_current_track(self) -> Dict:
        """Get currently playing track"""
        try:
            result = self.sp.current_playback()
            
            if not result or not result.get('item'):
                return {
                    "is_playing": False,
                    "track": None,
                    "artist": None,
                    "album": None,
                    "progress_ms": 0,
                    "duration_ms": 0,
                    "volume_percent": 0
                }
            
            track = result['item']
            
            return {
                "is_playing": result['is_playing'],
                "track": track['name'],
                "artist": ', '.join([artist['name'] for artist in track['artists']]),
                "album": track['album']['name'],
                "progress_ms": result.get('progress_ms', 0),
                "duration_ms": track['duration_ms'],
                "volume_percent": result['device'].get('volume_percent', 0),
                "device": result['device']['name'],
                "shuffle": result.get('shuffle_state', False),
                "repeat": result.get('repeat_state', 'off'),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting current track: {e}")
            return {}
    
    def play(self, uri: str = None) -> bool:
        """
        Start playback
        uri: Spotify URI (track, album, playlist, etc.)
        """
        try:
            kwargs = {"device_id": self.current_device_id} if self.current_device_id else {}
            
            if uri:
                if uri.startswith('spotify:track:'):
                    kwargs['uris'] = [uri]
                else:
                    kwargs['context_uri'] = uri
            
            self.sp.start_playback(**kwargs)
            logger.info(f"Started playback{': ' + uri if uri else ''}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting playback: {e}")
            return False
    
    def pause(self) -> bool:
        """Pause playback"""
        try:
            self.sp.pause_playback(device_id=self.current_device_id)
            logger.info("Paused playback")
            return True
        except Exception as e:
            logger.error(f"Error pausing playback: {e}")
            return False
    
    def next_track(self) -> bool:
        """Skip to next track"""
        try:
            self.sp.next_track(device_id=self.current_device_id)
            logger.info("Skipped to next track")
            return True
        except Exception as e:
            logger.error(f"Error skipping track: {e}")
            return False
    
    def previous_track(self) -> bool:
        """Go to previous track"""
        try:
            self.sp.previous_track(device_id=self.current_device_id)
            logger.info("Went to previous track")
            return True
        except Exception as e:
            logger.error(f"Error going to previous track: {e}")
            return False
    
    def set_volume(self, volume_percent: int) -> bool:
        """Set volume (0-100)"""
        try:
            volume_percent = max(0, min(100, volume_percent))
            self.sp.volume(volume_percent, device_id=self.current_device_id)
            logger.info(f"Set volume to {volume_percent}%")
            return True
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return False
    
    def adjust_volume(self, delta: int) -> bool:
        """Adjust volume by delta"""
        try:
            current = self.get_current_track()
            current_volume = current.get('volume_percent', 50)
            new_volume = max(0, min(100, current_volume + delta))
            return self.set_volume(new_volume)
        except Exception as e:
            logger.error(f"Error adjusting volume: {e}")
            return False
    
    def set_shuffle(self, state: bool) -> bool:
        """Set shuffle mode"""
        try:
            self.sp.shuffle(state, device_id=self.current_device_id)
            logger.info(f"Set shuffle to {state}")
            return True
        except Exception as e:
            logger.error(f"Error setting shuffle: {e}")
            return False
    
    def set_repeat(self, state: str) -> bool:
        """
        Set repeat mode
        state: 'track', 'context', or 'off'
        """
        try:
            self.sp.repeat(state, device_id=self.current_device_id)
            logger.info(f"Set repeat to {state}")
            return True
        except Exception as e:
            logger.error(f"Error setting repeat: {e}")
            return False
    
    def search(self, query: str, search_type: str = "track", limit: int = 10) -> List[Dict]:
        """
        Search Spotify
        search_type: 'track', 'artist', 'album', 'playlist'
        """
        try:
            result = self.sp.search(q=query, type=search_type, limit=limit)
            
            items = result.get(f'{search_type}s', {}).get('items', [])
            
            results = []
            for item in items:
                if search_type == 'track':
                    results.append({
                        "uri": item['uri'],
                        "name": item['name'],
                        "artist": ', '.join([a['name'] for a in item['artists']]),
                        "album": item['album']['name']
                    })
                elif search_type == 'playlist':
                    results.append({
                        "uri": item['uri'],
                        "name": item['name'],
                        "owner": item['owner']['display_name'],
                        "tracks": item['tracks']['total']
                    })
                else:
                    results.append({
                        "uri": item['uri'],
                        "name": item['name']
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return []
    
    def get_user_playlists(self) -> List[Dict]:
        """Get user's playlists"""
        try:
            result = self.sp.current_user_playlists()
            playlists = result.get('items', [])
            
            return [{
                "uri": p['uri'],
                "id": p['id'],
                "name": p['name'],
                "tracks": p['tracks']['total'],
                "owner": p['owner']['display_name']
            } for p in playlists]
            
        except Exception as e:
            logger.error(f"Error getting playlists: {e}")
            return []
    
    def set_auto_mode(self, enabled: bool):
        """Enable/disable auto mode"""
        self.auto_mode = enabled
        logger.info(f"Auto mode {'enabled' if enabled else 'disabled'}")
    
    def is_auto_mode(self) -> bool:
        """Check if auto mode is enabled"""
        return self.auto_mode


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    import os
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:9090/callback/spotify")
    
    if all([client_id, client_secret]):
        try:
            controller = SpotifyController(client_id, client_secret, redirect_uri)
            
            # Get devices
            devices = controller.get_devices()
            print("Available devices:")
            for device in devices:
                print(f"  {device['name']} ({device['type']}) - "
                      f"{'Active' if device['is_active'] else 'Inactive'}")
            
            # Get current track
            track = controller.get_current_track()
            if track.get('is_playing'):
                print(f"\nNow playing:")
                print(f"  {track['track']} - {track['artist']}")
                print(f"  Album: {track['album']}")
                print(f"  Volume: {track['volume_percent']}%")
            
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Missing Spotify credentials")
