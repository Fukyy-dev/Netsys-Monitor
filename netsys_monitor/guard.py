"""Penjaga WiFi: deteksi perangkat asing."""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import threading
import time

from . import history
from .alerts import _sid
from .config import KNOWN_FILE, SCAN
from .devices import run_scan
from .oui import vendor_of
from .util import MAC_RE, _clamp_int, _num, norm_mac
from .wifi import wifi_snapshot
from .wol import send_wol

log = logging.getLogger("netsys")


# --------------------------------------------------------------------------- penjaga WiFi: deteksi perangkat asing
# Setiap pindai (otomatis berkala atau manual) hasil ARP dibandingkan dengan daftar MAC yang pernah dikenal.
# Pindai pertama di sebuah jaringan = "daftar awal" (baseline, otomatis dipercaya). Setelah itu MAC yang belum
# pernah terlihat ditandai "baru/asing" dan memicu peringatan sampai pengguna menekan "Percayai".
KNOWN_LOCK = threading.RLock()
KNOWN = {"config": {"enabled": True, "interval": 180}, "networks": {}, "gateways": {}, "anomalies": {}}
GUARD = {"net": None, "online": set(), "last_scan": None, "next_scan": None}
GUARD_WAKE = threading.Event()
GUARD_MIN, GUARD_MAX, GUARD_DEFAULT = 30, 3600, 180


def _clean_known(mac, d):
    now = time.time()
    return {"mac": mac, "ip": str(d.get("ip") or "")[:45],
            "name": str(d["name"])[:60] if d.get("name") else None,
            "first_seen": _num(d.get("first_seen"), now), "last_seen": _num(d.get("last_seen"), now),
            "status": "trusted" if d.get("status") == "trusted" else "new",
            "random": bool(d.get("random")), "router": bool(d.get("router")),
            "origin": d.get("origin") if d.get("origin") in ("baseline", "detected", "manual") else "detected",
            "seen": _clamp_int(d.get("seen"), 1, 10 ** 9, 1)}


def load_known():
    try:
        with open(KNOWN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = data.get("config") or {}
        nets = {}
        for nid, rec in (data.get("networks") or {}).items():
            devs = {}
            for mac, d in (rec.get("devices") or {}).items():
                if isinstance(d, dict) and MAC_RE.fullmatch(str(mac)):
                    m = norm_mac(str(mac))
                    devs[m] = _clean_known(m, d)
            nets[str(nid)[:80]] = {"label": str(rec.get("label") or nid)[:60],
                                   "created": _num(rec.get("created"), time.time()),
                                   "baseline_done": bool(rec.get("baseline_done")), "devices": devs}
    except Exception:
        return
    gws, anoms = {}, {}
    try:
        for k, g in (data.get("gateways") or {}).items():
            gws[str(k)[:120]] = {"ssid": str(g.get("ssid") or "")[:64], "subnet": str(g.get("subnet") or "")[:45],
                                 "macs": {m: _num(t, time.time()) for m, t in (g.get("macs") or {}).items() if MAC_RE.fullmatch(str(m))}}
        for k, a in (data.get("anomalies") or {}).items():
            anoms[str(k)[:160]] = {"id": str(k)[:160], "kind": "gateway_changed", "ssid": str(a.get("ssid") or "")[:64],
                                   "subnet": str(a.get("subnet") or "")[:45], "old": [m for m in (a.get("old") or []) if MAC_RE.fullmatch(str(m))],
                                   "new": str(a.get("new") or ""), "ts": _num(a.get("ts"), time.time())}
    except (AttributeError, TypeError):
        gws, anoms = {}, {}
    with KNOWN_LOCK:
        KNOWN["config"] = {"enabled": bool(cfg.get("enabled", True)),
                           "interval": _clamp_int(cfg.get("interval"), GUARD_MIN, GUARD_MAX, GUARD_DEFAULT)}
        KNOWN["networks"] = nets
        KNOWN["gateways"], KNOWN["anomalies"] = gws, anoms


def save_known():
    with KNOWN_LOCK:
        data = {"version": 2, "config": dict(KNOWN["config"]), "networks": KNOWN["networks"],
                "gateways": KNOWN["gateways"], "anomalies": KNOWN["anomalies"]}
        try:
            tmp = KNOWN_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, KNOWN_FILE)
        except Exception:
            pass


def _cur_net():
    nid = GUARD.get("net")
    return KNOWN["networks"].get(nid) if nid else None


def guard_ingest(found, net, gw_mac):
    """Dipanggil setiap pindai selesai. Identitas jaringan = MAC gateway (fallback: subnet), jadi pindah ke
    WiFi lain tidak membanjiri peringatan: tiap jaringan punya daftar dan baseline sendiri."""
    now = time.time()
    nid = gw_mac or f"subnet:{net}"
    online = set()
    try:
        w = wifi_snapshot()
        ssid = w.get("ssid") if w.get("connected") else None
    except Exception:
        ssid = None
    with KNOWN_LOCK:
        _check_gateway(ssid, net, gw_mac, now)
        rec = KNOWN["networks"].get(nid)
        if rec is None:
            rec = KNOWN["networks"][nid] = {"label": str(net), "created": now, "baseline_done": False, "devices": {}}
        learning = not rec["baseline_done"]
        for f in found:
            mac = f.get("mac")
            if f.get("self") or not mac:
                continue
            online.add(mac)
            d = rec["devices"].get(mac)
            if d is None:
                rec["devices"][mac] = {
                    "mac": mac, "ip": f["ip"], "name": (f.get("name") or None) and str(f["name"])[:60],
                    "first_seen": now, "last_seen": now, "status": "trusted" if learning else "new",
                    "random": bool(f.get("random")), "router": bool(f.get("router")),
                    "origin": "baseline" if learning else "detected", "seen": 1}
                if not learning:
                    history.log_dev(mac, f["ip"], f.get("name"), "perangkat baru")
            else:
                d["ip"], d["last_seen"], d["router"] = f["ip"], now, bool(f.get("router"))
                d["seen"] = d.get("seen", 0) + 1
                if f.get("name"):
                    d["name"] = str(f["name"])[:60]
        if learning and online:  # baseline hanya selesai kalau pindai benar-benar menemukan perangkat
            rec["baseline_done"] = True
        rec["label"] = str(net)
        GUARD.update(net=nid, online=online, last_scan=now)
    save_known()


def _check_gateway(ssid, net, gw_mac, now):
    """MAC gateway berubah pada SSID + subnet yang sama = router diganti/direset, atau ARP spoofing (MITM).
    Dipanggil dalam KNOWN_LOCK. Pertama kali melihat kombinasi itu = dipercaya (belajar)."""
    if not ssid or not gw_mac:
        return
    key = f"{ssid}|{net}"
    g = KNOWN["gateways"].setdefault(key, {"ssid": ssid, "subnet": str(net), "macs": {}})
    if not g["macs"]:
        g["macs"][gw_mac] = now
    elif gw_mac not in g["macs"]:
        aid = "gwchg_" + _sid(key) + "_" + _sid(gw_mac)
        if aid not in KNOWN["anomalies"]:
            KNOWN["anomalies"][aid] = {"id": aid, "kind": "gateway_changed", "ssid": ssid, "subnet": str(net),
                                       "old": list(g["macs"]), "new": gw_mac, "ts": now}
            history.log_event("anomaly", aid, "crit", "MAC gateway berubah", f"{ssid} {net}: {list(g['macs'])} -> {gw_mac}")


def guard_ack(b):
    """Percayai gateway baru (mis. router memang diganti): anomali ditutup dan MAC baru dipelajari."""
    with KNOWN_LOCK:
        a = KNOWN["anomalies"].pop(str(b.get("id") or ""), None)
        if not a:
            return 404, {"error": "Anomali tidak ditemukan"}
        g = KNOWN["gateways"].setdefault(f"{a['ssid']}|{a['subnet']}", {"ssid": a["ssid"], "subnet": a["subnet"], "macs": {}})
        g["macs"][a["new"]] = time.time()
    save_known()
    return 200, {"ok": True}


def guard_wake(b):
    mac = _guard_mac(b)
    if not mac:
        return 400, {"error": "MAC tidak valid"}
    from .config import SCAN
    ok, msg = send_wol(mac, SCAN.get("subnet"))
    history.log_dev(mac, "", "", "wake-on-lan")
    return (200 if ok else 500), ({"ok": True, "message": msg} if ok else {"error": msg})


def guard_alert_state():
    with KNOWN_LOCK:
        cfg = KNOWN["config"]
        rec = _cur_net()
        unknown = []
        if rec and cfg["enabled"]:
            for d in rec["devices"].values():
                if d["status"] == "new":
                    unknown.append(dict(d, online=d["mac"] in GUARD["online"], label=rec["label"]))
        return {"enabled": cfg["enabled"], "interval": cfg["interval"],
                "scanned": bool(rec and rec["baseline_done"]),
                "known": len(rec["devices"]) if rec else 0, "unknown": unknown,
                "anomalies": [dict(a) for a in KNOWN["anomalies"].values()] if cfg["enabled"] else []}


def guard_snapshot():
    with KNOWN_LOCK:
        cfg = dict(KNOWN["config"])
        rec = _cur_net()
        devs = [dict(d, online=d["mac"] in GUARD["online"], vendor=vendor_of(d["mac"])) for d in rec["devices"].values()] if rec else []

        def key(d):
            try:
                ipk = int(ipaddress.ip_address(d["ip"]))
            except ValueError:
                ipk = 0
            return (d["status"] != "new", not d["online"], ipk)

        devs.sort(key=key)
        return {"enabled": cfg["enabled"], "interval": cfg["interval"],
                "network": rec["label"] if rec else None,
                "last_scan": GUARD["last_scan"], "next_scan": GUARD["next_scan"] if cfg["enabled"] else None,
                "baseline_done": bool(rec and rec["baseline_done"]), "devices": devs,
                "anomalies": [dict(a) for a in KNOWN["anomalies"].values()],
                "new": sum(1 for d in devs if d["status"] == "new"),
                "trusted": sum(1 for d in devs if d["status"] == "trusted"),
                "online": sum(1 for d in devs if d["online"])}


def _guard_mac(b):
    m = str(b.get("mac") or "")
    return norm_mac(m) if MAC_RE.fullmatch(m) else None


def guard_trust(b):
    with KNOWN_LOCK:
        rec = _cur_net()
        if not rec:
            return 400, {"error": "Belum ada hasil pindai. Pindai jaringan dulu."}
        if b.get("all"):
            for d in rec["devices"].values():
                if d["status"] != "trusted":
                    d["status"] = "trusted"
                    d["origin"] = "manual" if d["origin"] == "detected" else d["origin"]
        else:
            d = rec["devices"].get(_guard_mac(b) or "")
            if not d:
                return 404, {"error": "Perangkat tidak ditemukan"}
            d["status"] = "trusted"
            d["origin"] = "manual" if d["origin"] == "detected" else d["origin"]
    save_known()
    history.log_dev("*" if b.get("all") else (_guard_mac(b) or ""), "", "", "percayai semua" if b.get("all") else "percayai")
    return 200, {"ok": True}


def guard_untrust(b):
    with KNOWN_LOCK:
        rec = _cur_net()
        d = rec["devices"].get(_guard_mac(b) or "") if rec else None
        if not d:
            return 404, {"error": "Perangkat tidak ditemukan"}
        d["status"], d["origin"] = "new", "detected"
    save_known()
    history.log_dev(d["mac"], d["ip"], d.get("name"), "tandai asing")
    return 200, {"ok": True}


def guard_forget(b):
    with KNOWN_LOCK:
        rec = _cur_net()
        if not rec or rec["devices"].pop(_guard_mac(b) or "", None) is None:
            return 404, {"error": "Perangkat tidak ditemukan"}
    save_known()
    return 200, {"ok": True}


def guard_reset(b):
    """Kosongkan daftar jaringan aktif lalu pindai ulang: hasil pindai berikutnya menjadi baseline baru."""
    with KNOWN_LOCK:
        rec = _cur_net()
        if not rec:
            return 400, {"error": "Belum ada hasil pindai. Pindai jaringan dulu."}
        rec["devices"].clear()
        rec["baseline_done"] = False
        rec["created"] = time.time()
    save_known()
    if not SCAN["running"]:
        threading.Thread(target=run_scan, daemon=True).start()
    return 200, {"ok": True}


def guard_config(b):
    with KNOWN_LOCK:
        if "enabled" in b:
            KNOWN["config"]["enabled"] = bool(b["enabled"])
        if "interval" in b:
            KNOWN["config"]["interval"] = _clamp_int(b["interval"], GUARD_MIN, GUARD_MAX, GUARD_DEFAULT)
    save_known()
    GUARD_WAKE.set()
    return 200, {"ok": True}


def guard_loop():
    time.sleep(6)  # beri waktu sampler & monitor latency siap dulu
    while True:
        with KNOWN_LOCK:
            enabled = KNOWN["config"]["enabled"]
        if enabled and not SCAN["running"]:
            GUARD["next_scan"] = None
            try:
                run_scan()
            except Exception as e:
                log.exception("guard scan error: %s", e)
        with KNOWN_LOCK:
            enabled, interval = KNOWN["config"]["enabled"], KNOWN["config"]["interval"]
        GUARD["next_scan"] = time.time() + interval if enabled else None
        GUARD_WAKE.wait(interval if enabled else 3600)
        GUARD_WAKE.clear()
