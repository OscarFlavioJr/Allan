import json
import subprocess
import urllib.request
import urllib.error

OLLAMA_BASE = "http://localhost:11434"


def _api(method, path, data=None, timeout=30):
    url = f"{OLLAMA_BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError:
        return None


def is_running():
    try:
        urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def start_server():
    if is_running():
        return True
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time
        for _ in range(10):
            time.sleep(1)
            if is_running():
                return True
        return False
    except FileNotFoundError:
        return False


def list_models():
    resp = _api("GET", "/api/tags")
    if not resp:
        return []
    return [m["name"] for m in resp.get("models", [])]


def pull_model(name, progress_cb=None):
    url = f"{OLLAMA_BASE}/api/pull"
    data = json.dumps({"name": name}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            for line in resp:
                info = json.loads(line.decode())
                if progress_cb:
                    progress_cb(info)
                if info.get("status") == "success":
                    return True
        return True
    except Exception as e:
        return str(e)


def delete_model(name):
    return _api("DELETE", "/api/delete", {"name": name}) is not None


def chat(model, messages, stream=False):
    if stream:
        return _chat_stream(model, messages)
    resp = _api("POST", "/api/chat", {
        "model": model,
        "messages": messages,
        "stream": False,
    }, timeout=120)
    if not resp:
        return None
    return resp.get("message", {}).get("content", "")


def _chat_stream(model, messages):
    url = f"{OLLAMA_BASE}/api/chat"
    data = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    }).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        for line in resp:
            chunk = json.loads(line.decode())
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
            if chunk.get("done"):
                break
        resp.close()
    except Exception:
        return
