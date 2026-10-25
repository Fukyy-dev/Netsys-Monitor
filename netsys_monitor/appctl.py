"""Aplikasi: auto-start, pengaturan, instance tunggal."""
from __future__ import annotations

import json
import logging
import os
import socket
import sys
import time
from logging.handlers import RotatingFileHandler

from .config import APP_NAME, APP_VERSION, DATA_DIR, FROZEN, INSTANCE_FILE, IS_WIN, LOG_FILE, wib_now

# --------------------------------------------------------------------------- aplikasi: auto-start, tray, instance tunggal
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "NetsysMonitor"
INSTANCE_PORT = 47653
TRAY = {"active": False}
_LOCK_SOCK = None
_AUTO_CACHE = {"t": 0.0, "v": (False, False)}


def msgbox(title, text):
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(text), str(title), 0x10)
        except Exception:
            pass


def fatal(msg):
    log.critical(msg)
    print(msg, file=sys.stderr)
    if FROZEN:  # .exe tanpa console: pesan harus muncul di jendela
        msgbox(APP_NAME, msg)
    sys.exit(1)


from . import settings
from .notify import WEBHOOK
from .oui import status as oui_status
from .updater import UPDATE

log = logging.getLogger("netsys")


def say(msg):
    """Pesan untuk pengguna: ke console (bila ada) dan ke file log."""
    try:
        print(msg)
    except Exception:
        pass
    log.info(msg)


def setup_logging(level="INFO"):
    """Log berputar (1 MB x 3) di folder data. Build --noconsole tidak punya stdout/stderr -> diganti devnull."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    root = logging.getLogger("netsys")
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    root.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass
    if not FROZEN and sys.stderr is not sys.__stderr__ or (not FROZEN and sys.stderr and sys.stderr.isatty()):
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.WARNING)
        sh.setFormatter(fmt)
        root.addHandler(sh)
    root.propagate = False
    log.info("--- %s %s start (%s WIB) ---", APP_NAME, APP_VERSION, wib_now().strftime("%Y-%m-%d %H:%M:%S"))


def autostart_command():
    if FROZEN:
        return f'"{sys.executable}" --background'
    exe = sys.executable
    if IS_WIN:  # pythonw.exe: tanpa jendela console saat login
        pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pyw):
            exe = pyw
    return f'"{exe}" "{os.path.abspath(__file__)}" --background'


def autostart_state():
    """(aktif, path usang). Di-cache 5 detik karena dipanggil tiap /api/stats."""
    if not IS_WIN:
        return False, False
    if time.time() - _AUTO_CACHE["t"] < 5:
        return _AUTO_CACHE["v"]
    v = (False, False)
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            val = winreg.QueryValueEx(k, RUN_NAME)[0]
        v = (bool(val), bool(val) and val != autostart_command())
    except OSError:
        pass
    _AUTO_CACHE.update(t=time.time(), v=v)
    return v


def set_autostart(on):
    if not IS_WIN:
        return False, "Auto-start hanya didukung di Windows."
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
        _AUTO_CACHE["t"] = 0.0
        return True, ""
    except OSError as e:
        return False, str(e)


def app_status():
    en, stale = autostart_state()
    return {"frozen": FROZEN, "version": APP_VERSION, "autostart": en, "autostart_stale": stale,
            "autostart_supported": IS_WIN, "tray": TRAY["active"], "data_dir": DATA_DIR,
            "notify": bool(get_setting("notify", True)), "theme": get_setting("theme", "auto"),
            "update": dict(UPDATE), "oui": oui_status(), "webhook": dict(WEBHOOK)}


def app_autostart(b):
    ok, err = set_autostart(bool(b.get("on")))
    return (200, {"ok": True}) if ok else (500, {"error": err or "Gagal mengubah auto-start"})


def acquire_single_instance():
    """True bila ini satu-satunya instance (kunci: port loopback 47653)."""
    global _LOCK_SOCK
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind(("127.0.0.1", INSTANCE_PORT))
        s.listen(1)
    except OSError:
        s.close()
        return False
    _LOCK_SOCK = s
    return True


def read_instance_url():
    try:
        with open(INSTANCE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("url")
    except Exception:
        return None


def write_instance_url(url):
    try:
        with open(INSTANCE_FILE, "w", encoding="utf-8") as f:
            json.dump({"url": url, "pid": os.getpid()}, f)
    except OSError:
        pass


def get_setting(key, default=None):
    return settings.get(key, default=default)


def set_setting(key, value):
    settings.set_value(key, value)


def app_setting(b):
    if "notify" in b:
        set_setting("notify", bool(b["notify"]))
    return 200, {"ok": True}
