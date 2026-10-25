"""Helper umum: perintah sistem, format, jaringan dasar."""
from __future__ import annotations

import os
import platform
import re
import socket
import struct
import sys
from collections import Counter

import psutil

from .config import IS_WIN, run_cmd


# --------------------------------------------------------------------------- helpers
def is_loopback(name):
    n = name.lower()
    return n == "lo" or n.startswith("lo0") or "loopback" in n


def net_snapshot():
    io_ = psutil.net_io_counters(pernic=True)
    stats = psutil.net_if_stats()
    out = {}
    for name, c in io_.items():
        st = stats.get(name)
        if not st or not st.isup or is_loopback(name):
            continue
        out[name] = (c.bytes_sent, c.bytes_recv)
    return out


def iface_meta():
    meta = {}
    addrs, stats = psutil.net_if_addrs(), psutil.net_if_stats()
    for n, a in addrs.items():
        ip = next((x.address for x in a if x.family == socket.AF_INET), None)
        st = stats.get(n)
        meta[n] = {"ip": ip, "speed": st.speed if st else 0}
    return meta


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))  # tidak mengirim paket, hanya memilih rute
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def default_gateway():
    """IP router/gateway default (None kalau tidak ketemu)."""
    ipv4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    try:
        if IS_WIN:
            best = None
            for line in run_cmd(["route", "print", "-4", "0.0.0.0"], 4).splitlines():
                p = line.split()
                if len(p) >= 5 and p[0] == "0.0.0.0" and p[1] == "0.0.0.0" and ipv4.match(p[2]):
                    try:
                        metric = int(p[4])
                    except ValueError:
                        metric = 9999
                    if best is None or metric < best[0]:
                        best = (metric, p[2])
            return best[1] if best else None
        if os.path.exists("/proc/net/route"):
            with open("/proc/net/route") as f:
                for line in list(f)[1:]:
                    p = line.split()
                    if len(p) > 3 and p[1] == "00000000" and int(p[3], 16) & 2:
                        return socket.inet_ntoa(struct.pack("<L", int(p[2], 16)))
        m = re.search(r"gateway:\s*(\S+)", run_cmd(["route", "-n", "get", "default"], 3))
        return m.group(1) if m else None
    except Exception:
        return None


def cpu_name():
    if IS_WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except Exception:
            pass
    return platform.processor() or platform.machine()


def collect_disks():
    rows = []
    for p in psutil.disk_partitions(all=False):
        if IS_WIN and ("cdrom" in p.opts or p.fstype == ""):
            continue
        if p.mountpoint.startswith(("/snap", "/var/lib/docker", "/boot/efi")):
            continue
        if not IS_WIN and "ro" in p.opts.split(","):  # squashfs/read-only: selalu 100%, bukan masalah
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        if u.total == 0:
            continue
        rows.append({"mount": p.mountpoint, "fs": p.fstype, "total": u.total,
                     "used": u.used, "percent": u.percent})
    return rows


def collect_procs(n=10):
    cores = psutil.cpu_count() or 1
    rows = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        i = p.info
        if i["pid"] == 0:
            continue
        rows.append({"pid": i["pid"], "name": i["name"] or "?",
                     "cpu": (i["cpu_percent"] or 0) / cores, "mem": i["memory_percent"] or 0})
    count = len(rows)
    top_cpu = sorted(rows, key=lambda r: (r["cpu"], r["mem"]), reverse=True)[:n]
    top_mem = sorted(rows, key=lambda r: r["mem"], reverse=True)[:n]
    return top_cpu, top_mem, count


def collect_conns(pid_names):
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception:
        return {"counts": {}, "list": [], "error": True}
    counts = Counter(c.status for c in conns)
    est = [c for c in conns if c.status == "ESTABLISHED" and c.raddr
           and c.raddr.ip not in ("127.0.0.1", "::1")]
    out, lookups = [], 0
    for c in est:
        name = pid_names.get(c.pid)
        if name is None and c.pid and lookups < 40:
            lookups += 1
            try:
                name = psutil.Process(c.pid).name()
            except Exception:
                name = "?"
            pid_names[c.pid] = name
        out.append({"proc": name or "?", "lport": c.laddr.port if c.laddr else 0,
                    "remote": f"{c.raddr.ip}:{c.raddr.port}"})
    out.sort(key=lambda r: r["proc"].lower())
    return {"counts": dict(counts), "list": out[:14], "total_est": len(est), "error": False}


def icmp_ping(host, timeout=1.5):
    """Ping ICMP lewat perintah OS (untuk router). Parsing bebas bahasa: angka sebelum 'ms'."""
    if IS_WIN:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
    elif sys.platform == "darwin":
        cmd = ["ping", "-c", "1", "-W", str(int(timeout * 1000)), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host]
    out = run_cmd(cmd, timeout + 1.5)
    m = re.search(r"[=<]\s*([\d.]+)\s*ms", out, re.I)
    return float(m.group(1)) if m else None


# --------------------------------------------------------------------------- perangkat LAN (HP, laptop, TV)
MAC_RE = re.compile(r"(?:[0-9a-f]{1,2}[:-]){5}[0-9a-f]{1,2}", re.I)


def norm_mac(m):
    return ":".join(p.zfill(2) for p in re.split(r"[:-]", m.lower())).upper()


def _clamp_int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def _num(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def own_mac(lip):
    """MAC adapter milik PC ini (supaya PC sendiri tidak pernah dianggap asing)."""
    try:
        for addrs in psutil.net_if_addrs().values():
            if any(a.family == socket.AF_INET and a.address == lip for a in addrs):
                for a in addrs:
                    if a.family == psutil.AF_LINK and a.address and MAC_RE.fullmatch(a.address):
                        return norm_mac(a.address)
    except Exception:
        pass
    return None
