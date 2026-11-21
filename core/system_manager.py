import os
import subprocess
import shutil
import platform


def get_system_info():
    uname = platform.uname()
    mem = _read_meminfo()
    disk = shutil.disk_usage("/")
    return {
        "os": f"{uname.system} {uname.release}",
        "hostname": uname.node,
        "cpu": uname.processor or uname.machine,
        "ram_total_gb": round(mem["total"] / (1024**3), 1),
        "ram_used_gb": round(mem["used"] / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
    }


def _read_meminfo():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts[0] == "MemTotal:":
                    info["total"] = int(parts[1]) * 1024
                elif parts[0] == "MemAvailable:":
                    info["available"] = int(parts[1]) * 1024
    except Exception:
        info = {"total": 0, "available": 0}
    info["used"] = info.get("total", 0) - info.get("available", 0)
    return info


def list_dir(path="~"):
    path = os.path.expanduser(path)
    try:
        entries = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            is_dir = os.path.isdir(full)
            size = os.path.getsize(full) if not is_dir else 0
            entries.append({"name": name, "is_dir": is_dir, "size": size})
        return entries
    except PermissionError:
        return []


def run_command(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Timeout", "code": -1}


def open_app(name):
    try:
        subprocess.Popen(
            ["xdg-open", name] if "." in name else [name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def list_processes(limit=20):
    result = run_command(f"ps aux --sort=-%mem | head -n {limit + 1}")
    lines = result["stdout"].strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split()
    procs = []
    for line in lines[1:]:
        parts = line.split(None, 10)
        if len(parts) >= 11:
            procs.append({
                "user": parts[0],
                "pid": parts[1],
                "cpu": parts[2],
                "mem": parts[3],
                "command": parts[10][:80],
            })
    return procs


def kill_process(pid):
    try:
        os.kill(int(pid), 15)
        return True
    except Exception:
        return False
