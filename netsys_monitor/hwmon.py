"""Suhu, fan & GPU lewat LibreHardwareMonitor."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request

import psutil

from .config import IS_WIN, run_cmd
from .util import _num


def cpu_temp_info():
    """(suhu, sumber). Windows: LibreHardwareMonitor; Linux/macOS: psutil."""
    t = hwmon_fresh().get("cpu_temp")
    if t is not None:
        return t, "LibreHardwareMonitor"
    try:
        if hasattr(psutil, "sensors_temperatures"):
            t = psutil.sensors_temperatures()
            for key in ("coretemp", "k10temp", "cpu_thermal", "zenpower"):
                if key in t and t[key]:
                    return t[key][0].current, "psutil"
            for v in t.values():
                if v:
                    return v[0].current, "psutil"
    except Exception:
        pass
    return None, None


def cpu_temp():
    return cpu_temp_info()[0]


# --------------------------------------------------------------------------- suhu, fan & GPU lewat LibreHardwareMonitor
# LibreHardwareMonitor (LHM) harus berjalan sebagai Administrator. Dibaca lewat Remote Web Server bawaannya
# (Options > Remote Web Server > Run, http://127.0.0.1:8085/data.json); cadangan: provider WMI milik LHM.
LHM_DEFAULT_URL = "http://127.0.0.1:8085/data.json"
HW_CFG = {"enabled": False, "url": LHM_DEFAULT_URL}
HW_LOCK = threading.Lock()
HWMON = {"ok": False, "source": None, "ts": 0.0, "error": None, "cpu_temp": None, "cpu_power": None,
         "gpus": [], "fans": [], "counts": {"temp": 0, "fan": 0, "gpu": 0}}
_LHM_TYPES = ("temperature", "fan", "power", "load", "clock", "control")


def _lhm_num(s):
    """Angka dari teks sensor ("58,5 °C", "1.250 RPM"). Pemisah ribuan hanya dianggap pada satuan bilangan bulat
    (RPM/MHz/MB/GB) dan bila bagian depannya bukan 0, supaya "0.004 V" tidak terbaca 4."""
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(s))
    if not m:
        return None
    tok = m.group(0)
    unit = str(s)[m.end():].strip().lower()
    if unit in ("rpm", "mhz", "mb", "gb", "kb") and re.fullmatch(r"[1-9]\d{0,2}([.,]\d{3})+", tok):
        return float(re.sub(r"[.,]", "", tok))
    return float(tok.replace(",", "."))


def _vendor(s):
    s = (s or "").lower()
    if any(k in s for k in ("nvidia", "geforce", "quadro", "rtx", "gtx")):
        return "nvidia"
    if any(k in s for k in ("amd", "radeon")):
        return "amd"
    if "intel" in s:
        return "intel"
    return ""


def _lhm_kind(path, sid):
    parts = (sid or "").lower().split("/")
    first = parts[1] if len(parts) > 1 else ""  # "/intelcpu/0/temperature/0" -> "intelcpu"
    if first:
        if "cpu" in first:
            return "cpu"
        if first.startswith("gpu"):
            return "gpu"
        if first in ("lpc", "motherboard", "embeddedcontroller", "superio"):
            return "board"
    for n in path:
        img = str(n.get("ImageURL") or "").lower()
        if "cpu" in img:
            return "cpu"
        if any(k in img for k in ("nvidia", "ati", "amd", "gpu")):
            return "gpu"
        if "mainboard" in img or "chip" in img:
            return "board"
    return "other"


def _lhm_hw(path, sid):
    """(kunci hardware, nama, vendor). Satu GPU = satu kunci, jadi iGPU + dGPU tidak tercampur."""
    node = next((n for n in path if any(k in str(n.get("ImageURL") or "").lower()
                                        for k in ("cpu", "nvidia", "ati", "amd", "gpu"))), None)
    name = str(node.get("Text") or "") if node else ""
    parts = (sid or "").lower().split("/")
    key = "/".join(parts[:3]) if len(parts) > 2 and parts[1] else name
    return key, name, _vendor(parts[1] if len(parts) > 1 else "") or _vendor(name)


def _lhm_type(unit, typ="", name=""):
    typ = (typ or "").lower()
    if typ in _LHM_TYPES:
        return typ
    if typ in ("smalldata", "data"):
        return "data"
    u = unit.strip().lower()
    if u in ("°c", "c"):
        return "temperature"
    if u == "rpm":
        return "fan"
    if u == "w":
        return "power"
    if u == "mhz":
        return "clock"
    if u in ("mb", "gb", "kb", "b"):
        return "data"
    if u == "%":
        return "control" if "fan" in name.lower() else "load"
    return typ or u


def _lhm_row(path, sid, name, typ, unit, num, raw_type=""):
    """Baris sensor ternormalisasi. Tipe 'data' (memori) selalu dalam byte."""
    kind = _lhm_kind(path, sid)
    if typ == "data":
        mult = {"gb": 2 ** 30, "mb": 2 ** 20, "kb": 1024, "b": 1}.get(unit.strip().lower())
        if mult is None:  # WMI tanpa satuan: SmallData = MB, Data = GB
            mult = 2 ** 30 if raw_type.lower() == "data" else 2 ** 20
        num *= mult
    key, hwname, vend = _lhm_hw(path, sid) if kind in ("gpu", "cpu") else ("", "", "")
    return {"kind": kind, "hw": key, "hwname": hwname, "vendor": vend, "name": name, "type": typ, "value": num}


def lhm_fetch_web(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "NetsysMonitor"})
    with urllib.request.urlopen(req, timeout=1.8) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    rows = []

    def walk(node, path):
        if not isinstance(node, dict):
            return
        path = path + [node]
        kids = node.get("Children") or []
        val = node.get("Value")
        if not kids and isinstance(val, str) and val.strip():
            num = _lhm_num(val)
            m = re.match(r"^\s*-?[\d.,]+\s*(.*)$", val)
            if num is not None and m:
                name = str(node.get("Text") or "")
                unit = m.group(1)
                rows.append(_lhm_row(path[:-1], node.get("SensorId"), name,
                                     _lhm_type(unit, node.get("Type"), name), unit, num, node.get("Type") or ""))
        for k in kids:
            walk(k, path)

    walk(data, [])
    return rows


def lhm_fetch_wmi():
    for ns in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
        cmd = ("Get-CimInstance -Namespace " + ns + " -ClassName Sensor -ErrorAction Stop | "
               "Where-Object { $_.SensorType -in 'Temperature','Fan','Power','Load','Clock','Control','SmallData','Data' } | "
               "Select-Object Name,SensorType,Value,Identifier | ConvertTo-Json -Compress")
        out = run_cmd(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], 10)
        if not out:
            continue
        data = json.loads(out)
        rows = []
        for it in data if isinstance(data, list) else [data]:
            v = _num(it.get("Value"), None)
            if v is None:
                continue
            raw = str(it.get("SensorType") or "")
            name = str(it.get("Name") or "")
            rows.append(_lhm_row([], it.get("Identifier"), name, _lhm_type("", raw, name), "", v, raw))
        if rows:
            return rows
    return None


def _pick_temp(rows, prefer):
    good = [r for r in rows if 0 < r["value"] < 130 and "distance" not in r["name"].lower()
            and "tjmax" not in r["name"].lower()]
    for key in prefer:
        for r in good:
            if key in r["name"].lower():
                return r["value"]
    return max((r["value"] for r in good), default=None)


def _pick(rows, typ, prefs):
    rs = [r for r in rows if r["type"] == typ]
    for key in prefs:
        for r in rs:
            if key in r["name"].lower():
                return r["value"]
    return None


def _gpu_summary(rows):
    temps = [r for r in rows if r["type"] == "temperature"]
    hot = [r for r in temps if any(k in r["name"].lower() for k in ("hot spot", "hotspot"))]
    main = [r for r in temps if r not in hot and "junction" not in r["name"].lower()]
    hotspot = _pick_temp(hot, ("hot",))
    used = total = None
    for u_k, t_k, f_k in (("gpu memory used", "gpu memory total", "gpu memory free"),
                          ("d3d dedicated memory used", "d3d dedicated memory total", None),
                          ("d3d shared memory used", "d3d shared memory total", None)):
        used = _pick(rows, "data", (u_k,))
        if used is not None:
            total = _pick(rows, "data", (t_k,))
            free = _pick(rows, "data", (f_k,)) if f_k else None
            if total is None and free is not None:
                total = used + free
            break
    ctl = [r for r in rows if r["type"] == "control" and "fan" in r["name"].lower()]
    return {"util": _pick(rows, "load", ("gpu core", "d3d 3d")),
            "temp": _pick_temp(main, ("gpu core", "core", "gpu")) or hotspot, "hotspot": hotspot,
            "vram_used": used, "vram_total": total,
            "power": _pick(rows, "power", ("gpu package", "gpu power", "total board power", "package", "gpu")),
            "clock": _pick(rows, "clock", ("gpu core", "core")), "clock_mem": _pick(rows, "clock", ("gpu memory", "memory")),
            "shared_used": _pick(rows, "data", ("d3d shared memory used",)),
            "shared_total": _pick(rows, "data", ("d3d shared memory total",)),
            "fan": ctl[0]["value"] if ctl else None,
            "fan_rpm": next((r["value"] for r in rows if r["type"] == "fan"), None)}


def hwmon_summarize(rows):
    temps = [r for r in rows if r["type"] == "temperature"]
    fans = [r for r in rows if r["type"] == "fan" and r["kind"] != "gpu"]
    pw = [r for r in rows if r["type"] == "power" and r["kind"] == "cpu"]
    cpu_temp_v = _pick_temp([r for r in temps if r["kind"] == "cpu"],
                            ("cpu package", "tctl", "tdie", "core max", "core average", "package"))
    cpu_vendor = next((r["vendor"] for r in rows if r["kind"] == "cpu" and r["vendor"]), "")
    groups = {}
    for r in rows:
        if r["kind"] == "gpu":
            g = groups.setdefault(r["hw"], {"name": "", "vendor": "", "rows": [], "key": r["hw"]})
            g["name"] = g["name"] or r["hwname"]
            g["vendor"] = g["vendor"] or r["vendor"]
            g["rows"].append(r)
    gpus = []
    for g in groups.values():
        s = _gpu_summary(g["rows"])
        if all(s[k] is None for k in ("util", "temp", "vram_used")):
            continue
        s.update(name=g["name"] or {"nvidia": "NVIDIA GPU", "amd": "AMD GPU", "intel": "Intel GPU"}.get(g["vendor"], "GPU"),
                 vendor=g["vendor"])
        # iGPU/APU satu die dengan CPU dan LHM sering tidak punya sensor suhu GPU: pakai suhu CPU, ditandai temp_shared
        nm_l = s["name"].lower()
        integrated = ("integrated" in g["key"].lower()
                      or (g["vendor"] == "amd" and cpu_vendor == "amd" and nm_l.endswith("graphics") and " rx " not in nm_l)
                      or (g["vendor"] == "intel" and cpu_vendor == "intel" and "arc" not in nm_l))
        if s["temp"] is None and integrated and cpu_temp_v is not None:
            s["temp"], s["temp_shared"] = cpu_temp_v, True
        gpus.append(s)
    return {"cpu_temp": _pick_temp([r for r in temps if r["kind"] == "cpu"],
                                   ("cpu package", "tctl", "tdie", "core max", "core average", "package")),
            "cpu_power": next((r["value"] for r in pw if "package" in r["name"].lower()), None),
            "gpus": gpus,
            "fans": [{"name": r["name"], "rpm": r["value"], "cpu": "cpu" in r["name"].lower()} for r in fans][:8],
            "counts": {"temp": len(temps), "fan": len(fans), "gpu": len(gpus)}}


def hwmon_loop():
    wmi_fail, wmi_next = 0, 0.0
    while True:
        rows, src, err = None, None, None
        try:
            rows, src = lhm_fetch_web(HW_CFG["url"]), "LibreHardwareMonitor"
        except Exception as e:
            err = type(e).__name__
        if not rows and IS_WIN and time.time() >= wmi_next:
            try:
                rows, src = lhm_fetch_wmi(), "LibreHardwareMonitor (WMI)"
            except Exception:
                rows = None
            wmi_fail = 0 if rows else wmi_fail + 1
            wmi_next = time.time() + (8 if wmi_fail < 3 else 45)
        with HW_LOCK:
            if rows:
                HWMON.update(hwmon_summarize(rows), ok=True, source=src, ts=time.time(), error=None)
            else:
                HWMON["error"] = err or "Sensor tidak ditemukan"
                if time.time() - HWMON["ts"] > 8:
                    HWMON.update(ok=False, cpu_temp=None, cpu_power=None, gpus=[], fans=[])
        time.sleep(2 if rows else 4)


def hwmon_fresh():
    with HW_LOCK:
        if HWMON["ok"] and time.time() - HWMON["ts"] < 8:
            return dict(HWMON)
    return {}


def hwmon_gpus():
    return hwmon_fresh().get("gpus") or []


def _gpu_tokens(name):
    return set(re.findall(r"[a-z]*\d{2,}[a-z]*", (name or "").lower()))


def merge_gpus(base, lhm):
    """Lengkapi data GPU dari pynvml/nvidia-smi/winperf dengan sensor LibreHardwareMonitor (VRAM, suhu, daya,
    fan, clock). GPU yang hanya dikenal LHM (mis. iGPU di laptop ber-NVIDIA) ditambahkan sebagai GPU baru."""
    if not lhm:
        return base
    out, used = [dict(g) for g in base], set()

    def same(g, l):
        va, vb = _vendor(g["name"]), l.get("vendor") or _vendor(l.get("name"))
        if va and vb and va != vb:
            return False
        x, y = g["name"].lower(), (l.get("name") or "").lower()
        if y and (x in y or y in x or _gpu_tokens(x) & _gpu_tokens(y)):
            return True
        return bool(va and va == vb)

    for l in lhm:
        tgt = next((g for g in out if id(g) not in used and same(g, l)), None)
        if tgt is None:
            tgt = {"id": len(out), "name": l.get("name") or "GPU", "util": None, "mem_util": None, "vram_used": None,
                   "vram_total": None, "temp": None, "power": None, "power_limit": None, "fan": None,
                   "clock": None, "clock_mem": None}
            out.append(tgt)
        used.add(id(tgt))
        for k in ("util", "temp", "power", "fan", "clock", "clock_mem", "vram_used", "vram_total"):
            if l.get(k) is not None and (tgt.get(k) is None or (k == "util" and tgt.get("src") == "winperf")):
                tgt[k] = l[k]
                if k == "temp" and l.get("temp_shared"):
                    tgt["temp_shared"] = True
        for k in ("hotspot", "fan_rpm", "shared_used", "shared_total"):
            if l.get(k) is not None:
                tgt[k] = l[k]
        tgt["src"] = "LibreHardwareMonitor" if tgt.get("src") != "winperf" else "winperf+LHM"
    return out


def hwmon_status():
    with HW_LOCK:
        d = dict(HWMON)
    fresh = d["ok"] and time.time() - d["ts"] < 8
    return {"enabled": HW_CFG["enabled"], "ok": bool(fresh), "source": d["source"] if fresh else None,
            "url": HW_CFG["url"], "error": None if fresh else d["error"], "counts": d["counts"],
            "has_cpu_temp": d["cpu_temp"] is not None and fresh}
