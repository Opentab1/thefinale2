from typing import Dict

class LightingHue:
    def __init__(self):
        self.available = False
        self.brightness = 50
        self.color = '#ffffff'
        self.scene = 'default'

    def connect(self, bridge_ip: str | None = None) -> bool:
        self.available = False
        return self.available

    def get_status(self) -> Dict:
        return {
            'available': self.available,
            'brightness': self.brightness,
            'color': self.color,
            'scene': self.scene,
        }

    def set_brightness(self, pct: int) -> bool:
        self.brightness = max(0, min(100, int(pct)))
        return self.available

    def set_color(self, hex_color: str) -> bool:
        self.color = hex_color
        return self.available

    def set_scene(self, scene: str) -> bool:
        self.scene = scene
        return self.available
