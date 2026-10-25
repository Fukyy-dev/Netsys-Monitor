"""Perangkat LAN: pindai ARP, pemantauan HP/laptop/TV."""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
from collections import deque

import psutil

from .config import DEV_FILE, DEV_LOCK, DEV_TYPES, DEVICES, MAX_DEVICES, SCAN, run_cmd
from .util import MAC_RE, default_gateway, icmp_ping, local_ip, norm_mac, own_mac

log = logging.getLogger("netsys")


def valid_lan_ip(ip):
    """Hanya alamat jaringan lokal (privat / link-local). Mencegah dashboard dipakai memindai internet."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and (a.is_private or a.is_link_local) and not (a.is_loopback or a.is_multicast or a.is_unspecified)


def parse_arp_text(txt):
    out = {}
    for line in txt.splitlines():
        m_ip = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", line)
        m_mac = MAC_RE.search(line)
        if not (m_ip and m_mac):
            continue
        mac = norm_mac(m_mac.group(0))
        if mac == "FF:FF:FF:FF:FF:FF" or mac.startswith("01:00:5E") or mac == "00:00:00:00:00:00":
            continue
        out[m_ip.group(1)] = mac
    return out


def read_arp():
    """Tabel ARP: {ip: mac} untuk perangkat yang baru saja berkomunikasi di LAN."""
    try:
        if os.path.exists("/proc/net/arp"):
            out = {}
            with open("/proc/net/arp") as f:
                for line in list(f)[1:]:
                    p = line.split()
                    if len(p) >= 4 and p[3] != "00:00:00:00:00:00" and int(p[2], 16) & 2:
                        out[p[0]] = norm_mac(p[3])
            return out
        return parse_arp_text(run_cmd(["arp", "-a"], 6))
    except Exception:
        return {}


def local_network(lip):
    try:
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == socket.AF_INET and a.address == lip and a.netmask:
                    net = ipaddress.ip_network(f"{lip}/{a.netmask}", strict=False)
                    if net.prefixlen < 22 or net.prefixlen > 30:
                        net = ipaddress.ip_network(f"{lip}/24", strict=False)
                    return net
    except Exception:
        pass
    return ipaddress.ip_network(f"{lip}/24", strict=False) if lip else None


def resolve_names(ips, deadline=5.0):
    res = {}

    def work(ip):
        try:
            n = socket.gethostbyaddr(ip)[0]
            if n and not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", n):
                res[ip] = n.split(".")[0] if re.search(r"[A-Za-z]", n) else n
        except Exception:
            pass

    ths = [threading.Thread(target=work, args=(ip,), daemon=True) for ip in ips[:80]]
    for t in ths:
        t.start()
    end = time.time() + deadline
    for t in ths:
        t.join(max(0, end - time.time()))
    return res


def run_scan():
    """Pindai subnet: kirim paket UDP kecil ke tiap alamat supaya OS mengisi tabel ARP, lalu baca tabelnya."""
    from .guard import guard_ingest
    if SCAN["running"]:
        return
    SCAN.update(running=True, error=None, phase="Menyiapkan pemindaian...")
    try:
        lip = local_ip()
        net = local_network(lip) if lip else None
        if not net:
            raise RuntimeError("IP lokal tidak terdeteksi - pastikan PC tersambung ke Wi-Fi/LAN.")
        hosts = [str(h) for h in net.hosts() if str(h) != lip]
        SCAN["phase"] = f"Mengirim probe ke {len(hosts)} alamat di {net}..."
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((lip, 0))
        except OSError:
            pass
        for _ in range(2):
            for h in hosts:
                try:
                    sock.sendto(b"\x00", (h, 9))
                except OSError:
                    pass
            time.sleep(1.3)
        sock.close()
        SCAN["phase"] = "Membaca tabel ARP..."
        arp, gw, found = read_arp(), default_gateway(), []
        for ip, mac in arp.items():
            try:
                a = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if a not in net or a in (net.network_address, net.broadcast_address) or ip == lip:
                continue
            found.append({"ip": ip, "mac": mac, "name": None, "random": bool(int(mac[:2], 16) & 2),
                          "router": ip == gw, "self": False})
        found.append({"ip": lip, "mac": own_mac(lip), "name": socket.gethostname(), "random": False,
                      "router": False, "self": True})
        SCAN["phase"] = "Mencari nama perangkat..."
        names = resolve_names([f["ip"] for f in found if not f["self"]])
        for f in found:
            f["name"] = f["name"] or names.get(f["ip"])
        found.sort(key=lambda f: ipaddress.ip_address(f["ip"]))
        SCAN.update(found=found, ts=time.time(), subnet=str(net))
        try:
            guard_ingest(found, net, arp.get(gw) if gw else None)
        except Exception as e:
            log.exception("guard error: %s", e)
    except Exception as e:
        SCAN["error"] = str(e)
    finally:
        SCAN.update(running=False, phase="")


def tcp_alive(ip, ports=(443, 80, 62078, 8080, 5555), timeout=0.35):
    """Perangkat dianggap hidup bila ada port yang menjawab atau menolak (RST). Untuk HP yang memblokir ping."""
    for p in ports:
        t = time.perf_counter()
        try:
            with socket.create_connection((ip, p), timeout=timeout):
                pass
            return True, (time.perf_counter() - t) * 1000
        except ConnectionRefusedError:
            return True, (time.perf_counter() - t) * 1000
        except OSError:
            continue
    return False, None


def _empty_rt():
    return {"online": None, "last": None, "avg": None, "min": None, "max": None, "jitter": 0,
            "loss": 0, "uptime": None, "last_seen": None, "since": time.time(), "hist": [],
            "method": None, "probes": 0}


def save_devices():
    with DEV_LOCK:
        data = [{k: d.get(k) for k in ("id", "name", "ip", "type", "watch", "mac", "added")}
                for d in DEVICES.values()]
    try:
        tmp = DEV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DEV_FILE)
    except Exception:
        pass


def device_worker(dev_id):
    win, hist = deque(maxlen=30), deque(maxlen=60)
    fails = sent = ok_n = 0
    online, since, last_seen = None, time.time(), None
    while True:
        with DEV_LOCK:
            dev = DEVICES.get(dev_id)
            ip = dev["ip"] if dev else None
            need_mac = bool(dev) and not dev.get("mac")
        if not dev:
            return  # perangkat sudah dihapus
        t0 = time.time()
        rtt, method = icmp_ping(ip, 1.2), "icmp"
        alive = rtt is not None
        if not alive:
            alive, r2 = tcp_alive(ip)
            method = "tcp" if alive else None
            rtt = r2 if (alive and r2 is not None and r2 < 300) else None
        sent += 1
        if alive:
            ok_n += 1
            fails, last_seen = 0, t0
        else:
            fails += 1
        win.append((alive, rtt))
        hist.append(rtt if alive else None)
        new_online = True if alive else (False if fails >= 3 else online)
        if new_online != online:
            online, since = new_online, t0
        rtts = [r for a, r in win if a and r is not None]
        jitter = (sum(abs(a - b) for a, b in zip(rtts[1:], rtts[:-1])) / (len(rtts) - 1)) if len(rtts) > 1 else 0
        rt = {"online": online, "last": rtt if alive else None,
              "avg": sum(rtts) / len(rtts) if rtts else None,
              "min": min(rtts) if rtts else None, "max": max(rtts) if rtts else None,
              "jitter": jitter, "loss": 100.0 * sum(1 for a, _ in win if not a) / len(win),
              "uptime": 100.0 * ok_n / sent, "last_seen": last_seen, "since": since,
              "hist": list(hist), "method": method, "probes": sent}
        mac = read_arp().get(ip) if (need_mac and alive) else None
        with DEV_LOCK:
            d = DEVICES.get(dev_id)
            if not d:
                return
            d["rt"] = rt
            if mac:
                d["mac"] = mac
        if mac:
            save_devices()
        time.sleep(max(0.5, 3.0 - (time.time() - t0)))


def device_snapshot():
    with DEV_LOCK:
        rows = [dict({"id": d["id"], "name": d["name"], "ip": d["ip"], "mac": d.get("mac"),
                      "type": d["type"], "watch": d["watch"], "added": d["added"]}, **d["rt"])
                for d in DEVICES.values()]
    rows.sort(key=lambda r: r["added"])
    return rows


def _start_device(dev_id):
    threading.Thread(target=device_worker, args=(dev_id,), daemon=True).start()


def load_devices():
    try:
        with open(DEV_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    for c in data[:MAX_DEVICES]:
        ip = str(c.get("ip", ""))
        if not valid_lan_ip(ip):
            continue
        did = re.sub(r"[^0-9a-f]", "", str(c.get("id") or "")) or secrets.token_hex(4)
        typ = c.get("type") if c.get("type") in DEV_TYPES else "other"
        DEVICES[did] = {"id": did, "name": str(c.get("name") or ip)[:40], "ip": ip, "type": typ,
                        "watch": bool(c.get("watch", True)), "mac": c.get("mac"),
                        "added": c.get("added") or time.time(), "rt": _empty_rt()}
    for did in list(DEVICES):
        _start_device(did)


def dev_add(b):
    name = str(b.get("name") or "").strip()[:40]
    ip = str(b.get("ip") or "").strip()
    typ = b.get("type") if b.get("type") in DEV_TYPES else "other"
    mac = str(b.get("mac") or "")
    mac = norm_mac(mac) if MAC_RE.fullmatch(mac) else None
    if not valid_lan_ip(ip):
        return 400, {"error": "IP harus alamat jaringan lokal yang valid, contoh 192.168.1.23"}
    with DEV_LOCK:
        if len(DEVICES) >= MAX_DEVICES:
            return 400, {"error": f"Maksimal {MAX_DEVICES} perangkat"}
        if any(d["ip"] == ip for d in DEVICES.values()):
            return 400, {"error": "IP tersebut sudah dipantau"}
        did = secrets.token_hex(4)
        DEVICES[did] = {"id": did, "name": name or ip, "ip": ip, "type": typ, "watch": True,
                        "mac": mac, "added": time.time(), "rt": _empty_rt()}
    save_devices()
    _start_device(did)
    return 200, {"ok": True, "id": did}


def dev_update(b):
    did = str(b.get("id") or "")
    with DEV_LOCK:
        d = DEVICES.get(did)
        if not d:
            return 404, {"error": "Perangkat tidak ditemukan"}
        if "name" in b:
            d["name"] = str(b["name"]).strip()[:40] or d["ip"]
        if b.get("type") in DEV_TYPES:
            d["type"] = b["type"]
        if "watch" in b:
            d["watch"] = bool(b["watch"])
    save_devices()
    return 200, {"ok": True}


def dev_remove(b):
    did = str(b.get("id") or "")
    with DEV_LOCK:
        if DEVICES.pop(did, None) is None:
            return 404, {"error": "Perangkat tidak ditemukan"}
    save_devices()
    return 200, {"ok": True}
