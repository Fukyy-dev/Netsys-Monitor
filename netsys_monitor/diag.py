"""Diagnosis: traceroute & benchmark DNS."""
from __future__ import annotations

import ipaddress
import os
import random
import re
import shutil
import socket
import statistics
import struct
import subprocess
import threading
import time

from .config import IS_WIN, NOWINDOW, run_cmd
from .util import default_gateway

# --------------------------------------------------------------------------- diagnosis: traceroute & benchmark DNS
TRACE = {"running": False, "target": None, "hops": [], "error": None, "done": False, "ts": None, "raw": []}
DNSB = {"running": False, "ts": None, "results": [], "error": None, "phase": "", "advice": ""}
_IP4 = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
_RTT = re.compile(r"(<?\d+(?:[.,]\d+)?)\s*ms", re.I)
_HOST_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*")


def valid_target(t):
    """IP atau nama domain saja (tanpa spasi/opsi), supaya tidak bisa menyisipkan argumen ke perintah."""
    if not t or len(t) > 253 or t.startswith("-"):
        return False
    try:
        ipaddress.ip_address(t)
        return True
    except ValueError:
        return bool(_HOST_RE.fullmatch(t))


def _hop_tag(ip, gw):
    if not ip:
        return ""
    if gw and ip == gw:
        return "Router"
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return ""
    if a.version == 4 and a in ipaddress.ip_network("100.64.0.0/10"):
        return "CGNAT ISP"
    return "Lokal" if a.is_private else ""


def parse_trace_line(line, gw=None):
    """Satu baris hop dari tracert/traceroute (bebas bahasa: hanya angka, 'ms', '*' dan IPv4 yang dibaca)."""
    m = re.match(r"^\s*(\d{1,2})\s+(.*)$", line)
    if not m:
        return None
    n, rest = int(m.group(1)), m.group(2)
    rtts = []
    for tok in _RTT.findall(rest):
        t = tok.replace(",", ".")
        rtts.append(0.5 if t.startswith("<") else float(t))
    stars = rest.count("*")
    ips = _IP4.findall(rest)
    ip = next((x for x in ips if all(int(o) < 256 for o in x.split("."))), None)
    sent = len(rtts) + stars
    if not sent and not ip:
        return None
    sent = sent or 3
    return {"n": n, "ip": ip, "tag": _hop_tag(ip, gw), "rtts": rtts, "sent": sent,
            "avg": sum(rtts) / len(rtts) if rtts else None, "min": min(rtts) if rtts else None,
            "max": max(rtts) if rtts else None, "loss": 100.0 * (sent - len(rtts)) / sent}


def trace_cmd(target):
    if IS_WIN:
        return ["tracert", "-d", "-h", "20", "-w", "800", target]
    if shutil.which("traceroute"):
        return ["traceroute", "-n", "-m", "20", "-w", "1", "-q", "3", target]
    return None


def run_trace(target):
    proc = killer = None
    try:
        cmd = trace_cmd(target)
        if not cmd:
            raise RuntimeError("Perintah traceroute tidak ditemukan di sistem ini.")
        gw = default_gateway()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                text=True, errors="replace", creationflags=NOWINDOW)
        killer = threading.Timer(90, proc.kill)
        killer.start()
        for line in proc.stdout:
            if line.strip():
                TRACE["raw"] = (TRACE["raw"] + [line.strip()])[-8:]
            hop = parse_trace_line(line, gw)
            if hop:
                hops = [h for h in TRACE["hops"] if h["n"] != hop["n"]] + [hop]
                TRACE["hops"] = sorted(hops, key=lambda h: h["n"])
        proc.wait(timeout=5)
        if not TRACE["hops"]:
            TRACE["error"] = "Tidak ada hasil. " + " ".join(TRACE["raw"][-2:])
    except Exception as e:
        TRACE["error"] = f"Traceroute gagal: {e}"
    finally:
        if killer:
            killer.cancel()
        if proc and proc.poll() is None:
            proc.kill()
        TRACE.update(running=False, done=True)


def diag_trace_start(b):
    target = str(b.get("target") or "").strip()
    if not valid_target(target):
        return 400, {"error": "Tujuan harus berupa alamat IP atau nama domain yang valid."}
    if TRACE["running"]:
        return 409, {"error": "Traceroute sedang berjalan."}
    TRACE.update(running=True, target=target, hops=[], error=None, done=False, ts=time.time(), raw=[])
    threading.Thread(target=run_trace, args=(target,), daemon=True).start()
    return 202, {"ok": True}


def trace_snapshot():
    return dict(TRACE, hops=list(TRACE["hops"]), raw=list(TRACE["raw"]))


PUBLIC_DNS = (("Cloudflare", "1.1.1.1"), ("Google", "8.8.8.8"), ("Quad9", "9.9.9.9"),
              ("OpenDNS", "208.67.222.222"), ("AdGuard", "94.140.14.14"))
DNS_COLD = ("google.com", "wikipedia.org", "detik.com", "tokopedia.com")  # + label acak = pasti belum di-cache
DNS_WARM = ("google.com", "youtube.com", "facebook.com", "wikipedia.org", "tokopedia.com", "detik.com")


def dns_query(server, name, timeout=1.5, port=53):
    """Kirim satu query A lewat UDP, kembalikan waktu respon (ms) atau None. NOERROR dan NXDOMAIN dianggap sukses."""
    qid = random.randrange(65536)
    q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    for label in name.rstrip(".").split("."):
        b = label.encode("idna")
        q += bytes([len(b)]) + b
    q += b"\x00" + struct.pack(">HH", 1, 1)
    s = socket.socket(socket.AF_INET6 if ":" in server else socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout)
        t0 = time.perf_counter()
        s.sendto(q, (server, port))
        end = t0 + timeout
        while time.perf_counter() < end:
            data, _ = s.recvfrom(1500)
            if len(data) >= 12 and struct.unpack(">H", data[:2])[0] == qid:
                return (time.perf_counter() - t0) * 1000 if (data[3] & 0x0F) in (0, 3) else None
    except OSError:
        pass
    finally:
        s.close()
    return None


def _rand_label():
    return "ns" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10))


def system_dns_servers():
    out = []
    try:
        if IS_WIN:
            txt = run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           "(Get-DnsClientServerAddress -AddressFamily IPv4).ServerAddresses"], 10)
            out = [x.strip() for x in txt.splitlines()]
        elif os.path.exists("/etc/resolv.conf"):
            with open("/etc/resolv.conf") as f:
                out = [l.split()[1] for l in f if l.startswith("nameserver") and len(l.split()) > 1]
    except Exception:
        pass
    res = []
    for x in out:
        try:
            ipaddress.ip_address(x)
        except ValueError:
            continue
        if x not in res:
            res.append(x)
    return res


def dns_bench_one(name, ip, kind):
    cold, warm, total = [], [], 0
    for dom in DNS_COLD:
        total += 1
        r = dns_query(ip, f"{_rand_label()}.{dom}", 2.0)
        if r is not None:
            cold.append(r)
    for dom in DNS_WARM:
        dns_query(ip, dom)  # pemanasan cache, tidak dihitung
        total += 1
        r = dns_query(ip, dom)
        if r is not None:
            warm.append(r)
    ok = 100.0 * (len(cold) + len(warm)) / total
    c = statistics.median(cold) if cold else None
    w = statistics.median(warm) if warm else None
    return {"name": name, "ip": ip, "kind": kind, "cold": c, "warm": w, "ok": ok,
            "score": (c if c is not None else 9999) + (w if w is not None else 9999)}


def run_dns_bench():
    try:
        DNSB["phase"] = "Mendeteksi server DNS sistem..."
        sysdns = system_dns_servers()[:3]
        targets = []
        for ip in sysdns:
            try:
                priv = ipaddress.ip_address(ip).is_private
            except ValueError:
                priv = False
            targets.append(("DNS sistem" + (" (router)" if priv else ""), ip, "system"))
        targets += [(n, ip, "public") for n, ip in PUBLIC_DNS if ip not in sysdns]
        DNSB["phase"] = f"Menguji {len(targets)} server DNS..."
        results = [None] * len(targets)

        def work(i, t):
            results[i] = dns_bench_one(*t)

        ths = [threading.Thread(target=work, args=(i, t), daemon=True) for i, t in enumerate(targets)]
        for t in ths:
            t.start()
        for t in ths:
            t.join(60)
        rows = sorted((r for r in results if r), key=lambda r: r["score"])
        DNSB["results"] = rows
        DNSB["advice"] = _dns_advice(rows)
        DNSB["ts"] = time.time()
        if not rows or all(r["ok"] == 0 for r in rows):
            DNSB["error"] = "Semua server DNS tidak merespon. Firewall atau jaringan mungkin memblokir UDP port 53."
    except Exception as e:
        DNSB["error"] = f"Benchmark DNS gagal: {e}"
    finally:
        DNSB.update(running=False, phase="")


def _dns_advice(rows):
    if not rows or rows[0]["score"] >= 9999:
        return ""
    best = rows[0]
    sysr = [r for r in rows if r["kind"] == "system" and r["score"] < 9999]
    if not sysr:
        return f"Tercepat: {best['name']} ({best['ip']})."
    cur = min(sysr, key=lambda r: r["score"])
    if best["kind"] == "system":
        return "DNS bawaan sudah yang tercepat di antara yang diuji. Tidak perlu diganti."
    gain = (cur["cold"] or 0) - (best["cold"] or 0)
    if cur["cold"] and gain >= 15 and gain / cur["cold"] >= 0.25:
        return (f"{best['name']} ({best['ip']}) sekitar {gain:.0f} ms lebih cepat untuk domain yang belum di-cache "
                f"dibanding DNS sistem. Pertimbangkan menggantinya di pengaturan adapter atau router.")
    return "DNS bawaan sudah cukup cepat; selisihnya dengan yang tercepat kecil, tidak perlu diganti."


def diag_dns_start(b):
    if DNSB["running"]:
        return 409, {"error": "Benchmark DNS sedang berjalan."}
    DNSB.update(running=True, error=None, results=[], advice="", phase="Menyiapkan...")
    threading.Thread(target=run_dns_bench, daemon=True).start()
    return 202, {"ok": True}
