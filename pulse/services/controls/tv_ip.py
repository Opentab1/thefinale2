from typing import Dict

class TvIp:
    def __init__(self):
        self.available = False
        self.power = False
        self.input = 'HDMI1'
        self.channel = '1'

    def discover(self) -> None:
        self.available = False

    def get_status(self) -> Dict:
        return {
            'available': self.available,
            'power': self.power,
            'input': self.input,
            'channel': self.channel,
        }

    def set_power(self, on: bool) -> bool:
        self.power = bool(on)
        return self.available

    def set_input(self, src: str) -> bool:
        self.input = src
        return self.available

    def set_channel(self, ch: str) -> bool:
        self.channel = ch
        return self.available
