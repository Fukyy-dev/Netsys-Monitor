"""Konstanta, path data, waktu WIB dan state bersama."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

try:
    import psutil  # noqa: F401
except ImportError:
    sys.exit('psutil belum terpasang. Jalankan:  pip install psutil')


APP_NAME = "Netsys Monitor"
DEFAULT_DOMAIN = "netsys-monitor.test"
FALLBACK_DOMAIN = "127.0.0.1"
DEFAULT_PORT = 8765
IS_WIN = os.name == "nt"
NOWINDOW = 0x08000000 if IS_WIN else 0  # sembunyikan jendela console subprocess
HISTORY_LEN = 120
APP_VERSION = "2.3"
FROZEN = bool(getattr(sys, "frozen", False))  # True saat dibungkus PyInstaller (.exe)


def _data_dir():
    """Folder data (usage_log, devices, perangkat dikenal, pengaturan, log), selalu folder milik pengguna:
    Windows %LOCALAPPDATA%/NetsysMonitor, macOS ~/Library/Application Support/NetsysMonitor,
    Linux $XDG_DATA_HOME/netsys-monitor. Bisa diganti dengan variabel lingkungan NETSYS_DATA."""
    env = os.environ.get("NETSYS_DATA")
    home = os.path.expanduser("~")
    if env:
        path = env
    elif IS_WIN:
        path = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local"), "NetsysMonitor")
    elif sys.platform == "darwin":
        path = os.path.join(home, "Library", "Application Support", "NetsysMonitor")
    else:
        path = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share"), "netsys-monitor")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "NetsysMonitor")
        os.makedirs(path, exist_ok=True)
    return path


def _migrate_legacy(dest):
    """Versi lama (skrip tunggal) menyimpan data di samping skrip. Salin sekali ke folder data baru."""
    if os.environ.get("NETSYS_DATA"):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    for src in (os.getcwd(), os.path.dirname(here)):
        for name in ("usage_log.json", "devices.json", "known_devices.json"):
            f, t = os.path.join(src, name), os.path.join(dest, name)
            try:
                if os.path.isfile(f) and not os.path.exists(t):
                    import shutil
                    shutil.copy2(f, t)
            except OSError:
                pass


ACTIVITY = {"last": time.time()}  # terakhir kali UI meminta data (untuk mode hemat saat jendela tidak dibuka)
DATA_DIR = _data_dir()
_migrate_legacy(DATA_DIR)
USAGE_FILE = os.path.join(DATA_DIR, "usage_log.json")
KNOWN_FILE = os.path.join(DATA_DIR, "known_devices.json")
LOG_FILE = os.path.join(DATA_DIR, "netsys.log")
INSTANCE_FILE = os.path.join(DATA_DIR, "instance.json")
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts" if IS_WIN else "/etc/hosts"
HOSTS_TAG = "# Netsys Monitor"

WIB = timezone(timedelta(hours=7))  # Waktu Indonesia Barat


def wib_now():
    return datetime.now(WIB)


def wib_time(ts):
    return datetime.fromtimestamp(ts, WIB).strftime("%H:%M:%S")


STATE = {"latest": {}, "slow": {}, "public_ip": None}
LAT = {}
HIST = {k: deque(maxlen=HISTORY_LEN) for k in
        ("t", "cpu", "ram", "gpu", "down", "up", "dr", "dw", "ping")}
LOCK = threading.Lock()
ST = {"running": False, "phase": "", "error": None, "result": None, "history": []}
ALERTS = {"active": [], "events": [], "checks": [], "health": {"score": 100, "label": "Prima"}}

DEV_TYPES = ("phone", "laptop", "tablet", "tv", "console", "iot", "router", "other")
DEV_ICON = {"phone": "phone", "laptop": "laptop", "tablet": "tablet", "tv": "tv",
            "console": "gamepad", "iot": "cpu", "router": "router", "other": "server"}
DEV_FILE = os.path.join(DATA_DIR, "devices.json")
DEV_LOCK = threading.Lock()
DEVICES = {}
MAX_DEVICES = 24
SCAN = {"running": False, "phase": "", "error": None, "found": [], "ts": None, "subnet": None}


def run_cmd(args, timeout=3):
    try:
        # stdin=DEVNULL: build --noconsole tidak punya stdin valid (WinError 6) ; errors=replace: output netsh/ping non-ASCII
        r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL, creationflags=NOWINDOW)
        return r.stdout.strip()
    except Exception:
        return ""


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fmt_bytes(b):
    b = float(b)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or u == "TB":
            return f"{b:.0f} {u}" if u == "B" else f"{b:.1f} {u}"
        b /= 1024


def fmt_dur(sec):
    sec = int(sec)
    if sec < 60:
        return f"{sec} d"
    if sec < 3600:
        return f"{sec // 60} m {sec % 60:02d} d"
    return f"{sec // 3600} j {(sec % 3600) // 60:02d} m"
