"""Hosts file, pembuka jendela UI dan fokus jendela."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import webbrowser

from .config import APP_NAME, HOSTS_PATH, HOSTS_TAG, IS_WIN, run_cmd


# --------------------------------------------------------------------------- hosts file / launcher
def resolves_local(domain):
    try:
        return socket.gethostbyname(domain) == "127.0.0.1"
    except OSError:
        return False


def ensure_hosts(domain):
    """Daftarkan domain -> 127.0.0.1 di hosts file (butuh hak admin). True kalau sudah/berhasil."""
    if resolves_local(domain):
        return True
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="surrogateescape") as f:
            content = f.read()
        with open(HOSTS_PATH, "a", encoding="utf-8", errors="surrogateescape") as f:
            f.write(("" if content.endswith("\n") or not content else "\n")
                    + f"127.0.0.1\t{domain}\t{HOSTS_TAG}\n")
    except OSError:
        return False
    if IS_WIN:
        run_cmd(["ipconfig", "/flushdns"], 5)
    return resolves_local(domain)


def remove_hosts(domain):
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="surrogateescape") as f:
            lines = f.readlines()
        keep = [l for l in lines if not (HOSTS_TAG in l and domain in l)]
        if len(keep) == len(lines):
            return True
        with open(HOSTS_PATH, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.writelines(keep)
        if IS_WIN:
            run_cmd(["ipconfig", "/flushdns"], 5)
        return True
    except OSError:
        return False


def find_app_browser():
    if IS_WIN:
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        la = os.environ.get("LOCALAPPDATA", "")
        cands = [pf86 + r"\Microsoft\Edge\Application\msedge.exe",
                 pf + r"\Microsoft\Edge\Application\msedge.exe",
                 pf + r"\Google\Chrome\Application\chrome.exe",
                 pf86 + r"\Google\Chrome\Application\chrome.exe",
                 la + r"\Google\Chrome\Application\chrome.exe"]
    elif sys.platform == "darwin":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    else:
        cands = [shutil.which(x) for x in ("google-chrome", "google-chrome-stable", "chromium",
                                           "chromium-browser", "microsoft-edge")]
    return next((c for c in cands if c and os.path.exists(c)), None)


def open_ui(url, as_app):
    if as_app and focus_window():  # jendela dashboard sudah terbuka: cukup dimunculkan, bukan dibuka ulang
        return
    exe = find_app_browser() if as_app else None
    if exe:
        try:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1480,940"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    webbrowser.open(url)


def focus_window(title_part=APP_NAME):
    """Windows: cari jendela dashboard yang sudah terbuka (judul memuat 'Netsys Monitor'), pulihkan bila
    di-minimize lalu bawa ke depan. True bila ketemu, sehingga tidak perlu membuka jendela baru."""
    if not IS_WIN:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.IsIconic.argtypes = [wintypes.HWND]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.BringWindowToTop.argtypes = [wintypes.HWND]
        found = []
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _):
            if u.IsWindowVisible(hwnd):
                n = u.GetWindowTextLengthW(hwnd)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(hwnd, buf, n + 1)
                    if title_part in buf.value:
                        found.append(hwnd)
            return True

        u.EnumWindows(proc(cb), 0)
        if not found:
            return False
        hwnd = found[0]
        u.ShowWindow(hwnd, 9 if u.IsIconic(hwnd) else 5)  # SW_RESTORE / SW_SHOW
        u.keybd_event(0x12, 0, 0, 0)  # tekan Alt sebentar: izinkan SetForegroundWindow dari proses latar
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.keybd_event(0x12, 0, 2, 0)
        return True
    except Exception:
        return False
