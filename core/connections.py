import subprocess
import shutil
import os
import configparser


NATIVE_APPS = {
    "discord": {
        "label": "Discord",
        "process": "discord",
        "launch": "discord",
        "icon": "🎮",
    },
    "spotify": {
        "label": "Spotify",
        "process": "spotify",
        "launch": "spotify",
        "icon": "🎵",
    },
    "steam": {
        "label": "Steam",
        "process": "steam",
        "launch": "steam",
        "icon": "🎮",
    },
}

_DESKTOP_DIRS = [
    os.path.expanduser("~/.local/share/applications"),
    "/usr/share/applications",
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
]

_pwa_cache = {}


def _scan_pwas():
    pwas = []
    for d in _DESKTOP_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".desktop"):
                continue
            path = os.path.join(d, f)
            try:
                cp = configparser.ConfigParser(interpolation=None)
                cp.read(path)
                entry = cp["Desktop Entry"] if "Desktop Entry" in cp else None
                if not entry:
                    continue
                exec_line = entry.get("Exec", "")
                if "--app-id=" not in exec_line:
                    continue
                name = entry.get("Name", "").strip()
                if not name:
                    continue
                wmclass = entry.get("StartupWMClass", "").strip()
                icon_path = entry.get("Icon", "").strip()
                app_id = f"pwa-{f.replace('.desktop', '')}"
                pwas.append({
                    "id": app_id,
                    "label": name,
                    "exec": exec_line.strip(),
                    "wmclass": wmclass,
                    "icon_path": icon_path,
                    "file": path,
                })
            except Exception:
                continue
    return pwas


def _find_pwa_desktop(patterns):
    for pwa in _scan_pwas():
        label = pwa["label"].lower()
        for pat in patterns:
            if pat.lower() in label:
                _pwa_cache[pwa["id"]] = pwa
                return {
                    "exec": pwa["exec"],
                    "wmclass": pwa["wmclass"],
                    "file": pwa["file"],
                }
    return None


def _is_process_running(name):
    if not name:
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-f", name],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_installed(name):
    if not name:
        return False
    return shutil.which(name) is not None or _has_desktop_file(name)


def _has_desktop_file(name):
    for d in _DESKTOP_DIRS:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if name.lower() in f.lower():
                return True
    return False


def get_all_apps(config=None):
    connected = {}
    if config:
        connected = config.get("connections") or {}

    result = []

    for app_id, info in NATIVE_APPS.items():
        installed = _is_installed(info["process"]) or _is_installed(info.get("launch"))
        if not installed:
            continue
        running = _is_process_running(info["process"])
        is_connected = app_id in connected
        result.append({
            "id": app_id,
            "label": info["label"],
            "icon": info["icon"],
            "installed": True,
            "running": running,
            "connected": is_connected,
            "type": "native",
        })

    for pwa in _scan_pwas():
        _pwa_cache[pwa["id"]] = pwa
        running = _is_process_running(pwa["wmclass"]) if pwa.get("wmclass") else False
        is_connected = pwa["id"] in connected
        result.append({
            "id": pwa["id"],
            "label": pwa["label"],
            "icon": "🌐",
            "installed": True,
            "running": running,
            "connected": is_connected,
            "type": "pwa",
        })

    return result


def connect_app(app_id, config):
    connections = config.get("connections") or {}
    connections[app_id] = True
    config.set("connections", connections)


def disconnect_app(app_id, config):
    connections = config.get("connections") or {}
    connections.pop(app_id, None)
    config.set("connections", connections)


def launch_app(app_id):
    pwa = _pwa_cache.get(app_id)
    if pwa and pwa.get("exec"):
        cmd = pwa["exec"].replace("%u", "").replace("%U", "").replace("%f", "").replace("%F", "").strip()
        try:
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    info = NATIVE_APPS.get(app_id)
    if not info or not info.get("launch"):
        return False
    try:
        subprocess.Popen([info["launch"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def stop_app(app_id):
    pwa = _pwa_cache.get(app_id)
    if pwa and pwa.get("wmclass"):
        try:
            subprocess.run(["pkill", "-f", pwa["wmclass"]], timeout=5)
            return True
        except Exception:
            return False

    info = NATIVE_APPS.get(app_id)
    if not info or not info.get("process"):
        return False
    try:
        subprocess.run(["pkill", "-f", info["process"]], timeout=5)
        return True
    except Exception:
        return False
