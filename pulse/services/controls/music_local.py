from typing import Dict

class MusicLocal:
    def __init__(self):
        self.available = True
        self.playing = False
        self.volume = 50

    def get_status(self) -> Dict:
        return {
            'available': self.available,
            'playing': self.playing,
            'volume': self.volume,
        }

    def set_volume(self, pct: int) -> bool:
        self.volume = max(0, min(100, int(pct)))
        return True

    def play(self) -> bool:
        self.playing = True
        return True

    def pause(self) -> bool:
        self.playing = False
        return True
