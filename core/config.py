import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/allan")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "name": "Allan",
    "mic_enabled": False,
    "color": "#00ff88",
    "color_bg": "#1a1a2e",
    "instructions": "Você é um assistente pessoal e local. Seja direto e útil. Fale em português brasileiro.",
    "model": None,
    "connections": {},
    "hover_enabled": True,
    "position": "top",
    "open_style": "slide",
    "bar_size": "normal",
}


class Config:
    def __init__(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    saved = json.load(f)
                self.data.update(saved)
            except Exception:
                pass

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
