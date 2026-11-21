import subprocess
import shutil


def _run(cmd, timeout=5):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip(), result.returncode == 0
    except Exception:
        return "", False


def _has_playerctl():
    return shutil.which("playerctl") is not None


def _has_xdotool():
    return shutil.which("xdotool") is not None


def get_active_player():
    if not _has_playerctl():
        return None
    out, ok = _run(["playerctl", "-l"])
    if not ok or not out:
        return None
    players = out.strip().split("\n")
    for p in players:
        if "chrom" in p.lower() or "brave" in p.lower() or "firefox" in p.lower():
            return p
    return players[0]


def get_status():
    if not _has_playerctl():
        return None
    player = get_active_player()
    if not player:
        return None
    status, _ = _run(["playerctl", "-p", player, "status"])
    title, _ = _run(["playerctl", "-p", player, "metadata", "title"])
    artist, _ = _run(["playerctl", "-p", player, "metadata", "artist"])
    return {
        "player": player,
        "status": status,
        "title": title,
        "artist": artist,
    }


def play():
    player = get_active_player()
    if player:
        _, ok = _run(["playerctl", "-p", player, "play"])
        return ok
    return False


def pause():
    player = get_active_player()
    if player:
        _, ok = _run(["playerctl", "-p", player, "pause"])
        return ok
    return False


def play_pause():
    player = get_active_player()
    if player:
        _, ok = _run(["playerctl", "-p", player, "play-pause"])
        return ok
    return False


def next_track():
    player = get_active_player()
    if player:
        _, ok = _run(["playerctl", "-p", player, "next"])
        return ok
    return False


def prev_track():
    player = get_active_player()
    if player:
        _, ok = _run(["playerctl", "-p", player, "previous"])
        return ok
    return False


def open_uri(uri):
    player = get_active_player()
    if player:
        _, ok = _run(["playerctl", "-p", player, "open", uri])
        if ok:
            return True
    return False


def navigate_existing_window(url, wmclass=None):
    if not _has_xdotool():
        return False
    if wmclass:
        wid, ok = _run(["xdotool", "search", "--class", wmclass])
        if ok and wid:
            window_id = wid.split("\n")[0]
            _run(["xdotool", "windowactivate", window_id])
            _run(["xdotool", "key", "--window", window_id, "ctrl+l"])
            _run(["xdotool", "type", "--window", window_id, "--clearmodifiers", url])
            _run(["xdotool", "key", "--window", window_id, "Return"])
            return True
    return False


def _kill_pwa_by_appid(exec_line):
    if not exec_line or "--app-id=" not in exec_line:
        return False
    import re
    m = re.search(r"--app-id=(\S+)", exec_line)
    if not m:
        return False
    app_id = m.group(1)
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"app-id={app_id}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            subprocess.run(["pkill", "-f", f"app-id={app_id}"], timeout=5)
            import time
            time.sleep(0.8)
            return True
    except Exception:
        pass
    return False


def play_song_in_existing(url, wmclass=None, pwa_exec=None):
    pause()

    if pwa_exec:
        _kill_pwa_by_appid(pwa_exec)
        cmd = pwa_exec.replace("%u", "").replace("%U", "").replace("%f", "").replace("%F", "").strip()
        cmd = f"{cmd} --app={url}"
        try:
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    subprocess.Popen(
        ["xdg-open", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return True


def get_player_volume():
    player = get_active_player()
    if player:
        out, ok = _run(["playerctl", "-p", player, "volume"])
        if ok:
            try:
                return int(float(out) * 100)
            except (ValueError, TypeError):
                pass
    return None


def set_player_volume(percent):
    player = get_active_player()
    if player:
        vol = max(0.0, min(1.0, percent / 100.0))
        _, ok = _run(["playerctl", "-p", player, "volume", f"{vol:.2f}"])
        return ok
    return False


# ── Volume ──

def _get_volume_cmd():
    if shutil.which("wpctl"):
        return "wpctl"
    if shutil.which("amixer"):
        return "amixer"
    return None


def get_volume():
    tool = _get_volume_cmd()
    if tool == "wpctl":
        out, ok = _run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if ok and out:
            try:
                vol = float(out.split()[-1])
                return int(vol * 100)
            except (ValueError, IndexError):
                pass
    elif tool == "amixer":
        out, ok = _run(["amixer", "get", "Master"])
        if ok:
            import re
            m = re.search(r"(\d+)%", out)
            if m:
                return int(m.group(1))
    return None


def set_volume(percent):
    percent = max(0, min(100, percent))
    tool = _get_volume_cmd()
    if tool == "wpctl":
        _, ok = _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent / 100:.2f}"])
        return ok
    elif tool == "amixer":
        _, ok = _run(["amixer", "set", "Master", f"{percent}%"])
        return ok
    return False


def change_volume(delta):
    current = get_volume()
    if current is None:
        return False, None
    new_vol = max(0, min(100, current + delta))
    ok = set_volume(new_vol)
    return ok, new_vol


def mute():
    tool = _get_volume_cmd()
    if tool == "wpctl":
        _, ok = _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
        return ok
    elif tool == "amixer":
        _, ok = _run(["amixer", "set", "Master", "toggle"])
        return ok
    return False
