from typing import Dict

class MusicSpotify:
    def __init__(self):
        self.available = False
        self.playing = False
        self.volume = 50
        self.track = ''
        self.playlist = ''

    def connect(self) -> bool:
        self.available = False
        return self.available

    def get_status(self) -> Dict:
        return {
            'available': self.available,
            'playing': self.playing,
            'volume': self.volume,
            'track': self.track,
            'playlist': self.playlist,
        }

    def set_volume(self, pct: int) -> bool:
        self.volume = max(0, min(100, int(pct)))
        return self.available

    def play(self) -> bool:
        self.playing = True
        return self.available

    def pause(self) -> bool:
        self.playing = False
        return self.available

    def skip(self) -> bool:
        return self.available
