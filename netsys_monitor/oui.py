"""Vendor dari MAC (database OUI IEEE). Tidak disertakan di paket: diunduh sekali atas permintaan pengguna."""
from __future__ import annotations

import csv
import io
import logging
import os
import threading
import time
import urllib.request

from .config import DATA_DIR

log = logging.getLogger("netsys")
OUI_FILE = os.path.join(DATA_DIR, "oui.csv")
OUI_URL = os.environ.get("NETSYS_OUI_URL", "https://standards-oui.ieee.org/oui/oui.csv")
_DB = {"map": None, "mtime": 0.0}
_LOCK = threading.Lock()


def parse_csv(text):
    """Format IEEE: Registry,Assignment,Organization Name,Organization Address."""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        a, n = (row.get("Assignment") or "").strip().upper(), (row.get("Organization Name") or "").strip()
        if len(a) == 6 and n:
            out[a] = n
    return out


def _load():
    try:
        mt = os.path.getmtime(OUI_FILE)
    except OSError:
        _DB["map"] = None
        return None
    if _DB["map"] is None or mt != _DB["mtime"]:
        try:
            with open(OUI_FILE, "r", encoding="utf-8", errors="replace", newline="") as f:
                _DB["map"], _DB["mtime"] = parse_csv(f.read()), mt
        except OSError:
            _DB["map"] = None
    return _DB["map"]


def vendor_of(mac):
    """Nama vendor atau None (MAC acak, tidak dikenal, atau database belum diunduh)."""
    try:
        first = int(mac[:2], 16)
    except (ValueError, TypeError):
        return None
    if first & 2:  # locally administered = MAC acak/virtual: tidak ada vendor
        return None
    with _LOCK:
        m = _load()
    if not m:
        return None
    name = m.get("".join(ch for ch in mac.upper() if ch in "0123456789ABCDEF")[:6])
    if not name:
        return None
    for suf in (", Inc.", " Inc.", ", Ltd.", " Co., Ltd.", " Co.,Ltd.", " Corporation", " Technologies", " Limited"):
        if name.endswith(suf):
            name = name[: -len(suf)]
    return name[:30]


def status():
    with _LOCK:
        m = _load()
    return {"loaded": len(m) if m else 0, "updated": os.path.getmtime(OUI_FILE) if m else None}


def download():
    """Unduh database dari IEEE. Mengembalikan (ok, pesan)."""
    try:
        req = urllib.request.Request(OUI_URL, headers={"User-Agent": "NetsysMonitor (+local)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read(30 * 1024 * 1024)
        text = raw.decode("utf-8", "replace")
        m = parse_csv(text)
        if len(m) < 1000:
            return False, "Berkas yang diunduh tidak terlihat seperti database OUI IEEE."
        tmp = OUI_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, OUI_FILE)
        with _LOCK:
            _DB["map"] = None
        return True, f"{len(m)} vendor tersimpan"
    except Exception as e:
        log.warning("unduh OUI gagal: %s", e)
        return False, f"Gagal mengunduh: {e}"


def download_async():
    threading.Thread(target=download, daemon=True).start()


def age_days():
    try:
        return (time.time() - os.path.getmtime(OUI_FILE)) / 86400
    except OSError:
        return None
