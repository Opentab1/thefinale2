from typing import Dict

class TvCec:
    def __init__(self):
        self.available = False
        self.power = False
        self.input = 'HDMI1'

    def init(self) -> bool:
        self.available = False
        return self.available

    def get_status(self) -> Dict:
        return {
            'available': self.available,
            'power': self.power,
            'input': self.input,
        }

    def set_power(self, on: bool) -> bool:
        self.power = bool(on)
        return self.available

    def set_input(self, src: str) -> bool:
        self.input = src
        return self.available
