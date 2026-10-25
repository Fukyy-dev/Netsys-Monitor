"""Loop latar belakang: sampler, latency, speedtest."""
from __future__ import annotations

import logging
import socket
import threading
import time
import urllib.request
from collections import deque

import psutil

from . import settings
from .alerts import update_alerts
from .config import ACTIVITY, HIST, LAT, LOCK, ST, STATE, wib_now
from .devices import device_snapshot
from .guard import guard_alert_state
from .hwmon import cpu_temp_info, hwmon_fresh
from .usage import USAGE
from .util import collect_conns, collect_disks, collect_procs, default_gateway, icmp_ping, iface_meta, local_ip, net_snapshot
from .wifi import wifi_snapshot

log = logging.getLogger("netsys")


# --------------------------------------------------------------------------- background loops
def sampler(gpu):
    psutil.cpu_percent(percpu=True)  # prime
    prev = None
    peak_d = peak_u = 0.0
    while True:
        t0 = time.time()
        try:
            cores = psutil.cpu_percent(percpu=True)
            cpu = sum(cores) / max(1, len(cores))
            freq = psutil.cpu_freq()
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            nets = net_snapshot()
            dio = psutil.disk_io_counters()
            tot_s = sum(v[0] for v in nets.values())
            tot_r = sum(v[1] for v in nets.values())
            USAGE.update(tot_s, tot_r)
            meta = STATE["slow"].get("ifaces_meta", {})
            gpus = gpu.read()

            down = up = dr = dw = 0.0
            ifaces = []
            if prev:
                dt = max(0.001, t0 - prev["t"])
                for name, (s, r) in nets.items():
                    ps, pr = prev["nets"].get(name, (s, r))
                    u_, d_ = max(0, s - ps) / dt, max(0, r - pr) / dt
                    up += u_
                    down += d_
                    m = meta.get(name, {})
                    ifaces.append({"name": name, "ip": m.get("ip"), "link": m.get("speed", 0),
                                   "down": d_, "up": u_, "sent": s, "recv": r})
                if dio and prev["dio"]:
                    dr = max(0, dio.read_bytes - prev["dio"].read_bytes) / dt
                    dw = max(0, dio.write_bytes - prev["dio"].write_bytes) / dt
            ifaces.sort(key=lambda i: i["down"] + i["up"], reverse=True)
            peak_d, peak_u = max(peak_d, down), max(peak_u, up)

            batt = None
            try:
                b = psutil.sensors_battery()
                if b:
                    batt = {"percent": b.percent, "plugged": b.power_plugged}
            except Exception:
                pass

            ct, csrc = cpu_temp_info()
            hw = hwmon_fresh()
            ping_main = (LAT.get("Cloudflare") or {}).get("last")
            latest = {
                "ts": t0,
                "cpu": {"total": cpu, "cores": cores, "freq": freq.current if freq else None,
                        "freq_max": freq.max if freq else None, "temp": ct,
                        "temp_src": csrc, "fans": hw.get("fans", []), "power": hw.get("cpu_power")},
                "mem": {"percent": vm.percent, "used": vm.used, "total": vm.total,
                        "swap_percent": sw.percent, "swap_used": sw.used, "swap_total": sw.total},
                "gpu": gpus,
                "net": {"down": down, "up": up, "peak_down": peak_d, "peak_up": peak_u,
                        "ifaces": ifaces},
                "disk_io": {"read": dr, "write": dw},
                "battery": batt,
            }
            with LOCK:
                STATE["latest"] = latest
                H = HIST
                H["t"].append(t0)
                H["cpu"].append(round(cpu, 1))
                H["ram"].append(vm.percent)
                H["gpu"].append(gpus[0]["util"] if gpus and gpus[0]["util"] is not None else None)
                H["down"].append(round(down * 8 / 1e6, 3))
                H["up"].append(round(up * 8 / 1e6, 3))
                H["dr"].append(round(dr / 1e6, 3))
                H["dw"].append(round(dw / 1e6, 3))
                H["ping"].append(ping_main)
            prev = {"t": t0, "nets": nets, "dio": dio}
        except Exception as e:  # jangan sampai thread mati
            log.exception("sampler error: %s", e)
        else:
            try:
                update_alerts(latest, STATE["slow"], dict(LAT), device_snapshot(), guard_alert_state(), wifi_snapshot())
            except Exception as e:
                log.exception("alert error: %s", e)
        time.sleep(max(0.05, 1.0 - (time.time() - t0)))


def slow_loop():
    pid_names = {}
    while True:
        try:
            procs, procs_mem, count = collect_procs()
            slow = dict(STATE["slow"])
            slow.update({
                "disks": collect_disks(), "procs": procs, "procs_mem": procs_mem,
                "proc_count": count, "conns": collect_conns(pid_names),
                "local_ip": local_ip(), "ifaces_meta": iface_meta(),
            })
            STATE["slow"] = slow
        except Exception as e:
            log.exception("slow error: %s", e)
        # mode hemat: tak ada UI yang membuka dashboard >30 dtk -> proses/disk/koneksi dibaca jauh lebih jarang
        idle = settings.get("idle_mode", default=True) and time.time() - ACTIVITY["last"] > 30
        time.sleep(12 if idle else 3)


def tcp_ping(host, port, timeout=1.5):
    t = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return (time.perf_counter() - t) * 1000
    except OSError:
        return None


def latency_worker(name, host, port, kind):
    win = deque(maxlen=30)
    fails, ever = 0, False
    while True:
        r = tcp_ping(host, port) if kind == "tcp" else icmp_ping(host)
        win.append(r)
        if r is None:
            fails += 1
        else:
            fails, ever = 0, True
        ok = [x for x in win if x is not None]
        jitter = (sum(abs(a - b) for a, b in zip(ok[1:], ok[:-1])) / (len(ok) - 1)) if len(ok) > 1 else 0
        LAT[name] = {
            "host": host, "kind": kind, "last": win[-1],
            "avg": sum(ok) / len(ok) if ok else None,
            "min": min(ok) if ok else None, "max": max(ok) if ok else None,
            "jitter": jitter,
            "loss": 100.0 * (len(win) - len(ok)) / len(win),
            "reachable": bool(ok) or len(win) < 5,
            "fails": fails, "ever_ok": ever, "samples": len(win),
        }
        time.sleep(1)


def start_latency_monitors():
    targets = []
    gw = default_gateway()
    if gw:
        targets.append(("Router", gw, 0, "icmp"))
    targets += [("Cloudflare", "1.1.1.1", 443, "tcp"), ("Google", "8.8.8.8", 443, "tcp")]
    for n, h, _p, k in targets:  # urutan tampil tetap
        LAT[n] = {"host": h, "kind": k, "last": None, "avg": None, "min": None, "max": None,
                  "jitter": 0, "loss": 0, "reachable": True, "fails": 0, "ever_ok": False, "samples": 0}
    for t in targets:
        threading.Thread(target=latency_worker, args=t, daemon=True).start()


def public_ip_loop():
    while True:
        wait = 600
        try:
            with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
                STATE["public_ip"] = r.read().decode().strip()
        except Exception:
            wait = 30
        time.sleep(wait)


def run_speedtest():
    if ST["running"]:
        return
    ST.update(running=True, error=None, phase="Mencari server terbaik...")
    try:
        import speedtest
        s = speedtest.Speedtest()
        s.get_best_server()
        ST["phase"] = "Mengukur download..."
        s.download()
        ST["phase"] = "Mengukur upload..."
        s.upload()
        r = s.results.dict()
        res = {"down": r["download"] / 1e6, "up": r["upload"] / 1e6, "ping": r["ping"],
               "server": f'{r["server"]["name"]}, {r["server"]["country"]}',
               "isp": r["client"].get("isp", ""), "time": wib_now().strftime("%H:%M:%S") + " WIB"}
        ST["result"] = res
        ST["history"] = ([res] + ST["history"])[:5]
    except ImportError:
        ST["error"] = "Modul speedtest belum ada. Jalankan: pip install speedtest-cli"
    except Exception as e:
        ST["error"] = f"Speedtest gagal: {e}"
    finally:
        ST["running"] = False
        ST["phase"] = ""
