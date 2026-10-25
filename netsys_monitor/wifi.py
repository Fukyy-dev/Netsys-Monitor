"""Info WiFi PC ini (netsh wlan / nmcli)."""
from __future__ import annotations

import logging
import re
import shutil
import threading
import time
from collections import deque

from .config import HISTORY_LEN, IS_WIN, run_cmd
from .util import MAC_RE, norm_mac

log = logging.getLogger("netsys")


# --------------------------------------------------------------------------- info WiFi PC ini (netsh wlan / nmcli)
WIFI = {"supported": None, "connected": False}
WIFI_HIST = deque(maxlen=HISTORY_LEN)
WIFI_LOCK = threading.Lock()
_KV_RE = re.compile(r"^\s*([^:]+?)\s*:\s*(.*?)\s*$")
_CH_KEYS = ("channel", "saluran", "kanal", "canal")
_RX_KEYS = ("receive", "terima", "rx", "empf", "réception", "reception", "recib", "ricez")
_TX_KEYS = ("transmit", "kirim", "transmis", "tx", "sende", "émission", "emission", "transm", "trasm")


def _wlan_block(lines):
    """Satu blok interface dari `netsh wlan show interfaces`. Label netsh ikut bahasa Windows, jadi nilai
    dikenali dari bentuknya (persen = sinyal, '5 GHz' = band, MAC di baris BSSID, 802.11xx = standar radio)."""
    pairs = []
    for ln in lines:
        m = _KV_RE.match(ln)
        if m:
            pairs.append((m.group(1).strip().lower(), m.group(2).strip()))
    if not pairs:
        return None
    w, nums, seen_bssid = {}, [], False
    for k, v in pairs:
        if not v:
            continue
        if k == "ssid":
            w["ssid"] = v
        elif "bssid" in k:  # "BSSID" dan "AP BSSID" (Windows 11 terbaru)
            if MAC_RE.fullmatch(v):
                w["bssid"], seen_bssid = norm_mac(v), True
        elif re.fullmatch(r"\d{1,3}\s*%", v):
            w["signal"] = float(v.replace("%", "").strip())
        elif re.fullmatch(r"\d(?:[.,]\d)?\s*GHz", v, re.I):
            w["band"] = re.sub(r"\s+", " ", v.replace(",", ".")).upper().replace("GHZ", "GHz")
        elif v.startswith("802.11"):
            w["radio"] = v
        elif "auth" in k or "autent" in k:
            w["auth"] = v
        elif "cipher" in k:
            w["cipher"] = v
        elif re.fullmatch(r"\d+(?:[.,]\d+)?", v):
            val = float(v.replace(",", "."))
            if any(s in k for s in _CH_KEYS):
                w["channel"] = int(val)
            elif any(s in k for s in _RX_KEYS):
                w["rx"] = val
            elif any(s in k for s in _TX_KEYS):
                w["tx"] = val
            elif seen_bssid:
                nums.append(val)
    # cadangan posisi: urutan netsh selalu Channel, Receive rate, Transmit rate (setelah BSSID)
    for field, val in zip([f for f in ("channel", "rx", "tx") if f not in w], nums):
        w[field] = int(val) if field == "channel" else val
    w["connected"] = bool(w.get("signal") is not None or w.get("bssid") or w.get("ssid"))
    return _wifi_finish(w)


def _wifi_finish(w):
    sig = w.get("signal")
    if sig is not None:
        w["dbm"] = round(sig / 2 - 100)  # pemetaan kualitas->dBm Windows: 100% = -50 dBm, 0% = -100 dBm
        w["quality"] = ("Sangat kuat" if sig >= 80 else "Kuat" if sig >= 65 else "Cukup" if sig >= 50
                        else "Lemah" if sig >= 30 else "Sangat lemah")
    ch = w.get("channel")
    if ch and not w.get("band"):
        w["band"] = "2.4 GHz" if ch <= 14 else "5 GHz"
    return w


def parse_netsh_wlan(txt):
    blocks, cur = [], []
    for line in txt.splitlines():
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    best = None
    for blk in blocks:
        w = _wlan_block(blk)
        if not w:
            continue
        if w["connected"]:
            return w
        best = best or w
    return best


def parse_nmcli_wifi(txt):
    for line in txt.splitlines():
        p = [x.replace("\\:", ":") for x in re.split(r"(?<!\\):", line)]
        if len(p) < 7 or p[0] != "yes":
            continue
        w = {"connected": True, "ssid": p[1] or None}
        if MAC_RE.fullmatch(p[2]):
            w["bssid"] = norm_mac(p[2])
        if p[3].isdigit():
            w["channel"] = int(p[3])
        m = re.match(r"(\d+)", p[4])
        if m:
            mhz = int(m.group(1))
            w["band"] = "2.4 GHz" if mhz < 3000 else "5 GHz" if mhz < 5925 else "6 GHz"
        m = re.match(r"([\d.]+)", p[5])
        if m:
            w["rx"] = w["tx"] = float(m.group(1))
        if p[6].isdigit():
            w["signal"] = float(p[6])
        if len(p) > 7 and p[7]:
            w["auth"] = p[7]
        return _wifi_finish(w)
    return None


def wifi_read():
    if IS_WIN:
        txt = run_cmd(["netsh", "wlan", "show", "interfaces"], 6)
        w = parse_netsh_wlan(txt) if txt else None
        if w:
            w["supported"] = True
            if not w["connected"]:
                w["hint"] = "WiFi PC ini tidak tersambung ke jaringan mana pun."
            return w
        low = txt.lower()
        if "wlansvc" in low or "not running" in low:
            hint = "Layanan WLAN AutoConfig tidak berjalan (PC ini kemungkinan tidak punya adapter WiFi)."
        elif "location" in low or "lokasi" in low:
            hint = "Windows meminta izin Lokasi untuk membaca info WiFi: aktifkan Layanan Lokasi di Pengaturan > Privasi."
        else:
            hint = "Tidak ada adapter WiFi aktif (PC mungkin memakai kabel LAN)."
        return {"supported": True, "connected": False, "hint": hint}
    if shutil.which("nmcli"):
        txt = run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,CHAN,FREQ,RATE,SIGNAL,SECURITY", "dev", "wifi"], 6)
        w = parse_nmcli_wifi(txt)
        if w:
            w["supported"] = True
            return w
        return {"supported": True, "connected": False, "hint": "WiFi tidak tersambung."}
    return {"supported": False, "connected": False,
            "hint": "Info WiFi tersedia di Windows (netsh) dan Linux (nmcli)."}


def wifi_loop():
    if not IS_WIN and not shutil.which("nmcli"):
        with WIFI_LOCK:
            WIFI.update(wifi_read())
        return
    idle = 0
    while True:
        try:
            w = wifi_read()
            with WIFI_LOCK:
                WIFI_HIST.append(w.get("signal") if w.get("connected") else None)
                WIFI.clear()
                WIFI.update(w, ts=time.time())
            idle = 0 if w.get("connected") else idle + 1
        except Exception as e:
            log.exception("wifi error: %s", e)
        time.sleep(3 if idle < 3 else 12)


def wifi_snapshot():
    with WIFI_LOCK:
        return dict(WIFI, hist=list(WIFI_HIST))
