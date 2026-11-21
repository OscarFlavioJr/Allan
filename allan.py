#!/usr/bin/env python3
import sys
import os

os.environ["GDK_BACKEND"] = "x11"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from core.brain import Brain
from core.config import Config
from core.ollama_manager import is_running, start_server
from ui.overlay import AllanOverlay


def main():
    if not is_running():
        print("Iniciando Ollama...")
        if not start_server():
            print("Aviso: Ollama não disponível.")

    config = Config()
    brain = Brain(config)

    if config.get("model"):
        brain.set_model(config.get("model"))

    overlay = AllanOverlay(brain, config)
    overlay.show_all()

    if overlay.expanded:
        overlay._collapse()

    Gtk.main()


if __name__ == "__main__":
    main()
