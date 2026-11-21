import subprocess
import threading
import json
import os
import queue


MODELS_DIR = os.path.expanduser("~/.local/share/allan/vosk-models")
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
MODEL_NAME = "vosk-model-small-pt-0.3"


def is_available():
    try:
        import vosk
        return True
    except ImportError:
        return False


def model_path():
    return os.path.join(MODELS_DIR, MODEL_NAME)


def is_model_downloaded():
    return os.path.isdir(model_path())


def download_model(on_progress=None):
    os.makedirs(MODELS_DIR, exist_ok=True)
    zip_path = os.path.join(MODELS_DIR, f"{MODEL_NAME}.zip")
    try:
        import urllib.request
        def _report(block, block_size, total):
            if on_progress and total > 0:
                pct = int(block * block_size * 100 / total)
                on_progress(min(pct, 100))
        urllib.request.urlretrieve(MODEL_URL, zip_path, _report)
        import zipfile
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(MODELS_DIR)
        os.remove(zip_path)
        return True
    except Exception as e:
        if on_progress:
            on_progress(-1)
        return False


class VoiceListener:
    def __init__(self, on_text, on_partial=None):
        self.on_text = on_text
        self.on_partial = on_partial
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        if not is_available():
            return
        if not is_model_downloaded():
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def is_running(self):
        return self._running

    def _listen_loop(self):
        try:
            import vosk
            vosk.SetLogLevel(-1)

            model = vosk.Model(model_path())
            rec = vosk.KaldiRecognizer(model, 16000)

            process = subprocess.Popen(
                ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw", "-q"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            while self._running:
                data = process.stdout.read(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        self.on_text(text)
                else:
                    partial = json.loads(rec.PartialResult())
                    text = partial.get("partial", "").strip()
                    if text and self.on_partial:
                        self.on_partial(text)

            process.terminate()
        except Exception:
            pass
        finally:
            self._running = False
