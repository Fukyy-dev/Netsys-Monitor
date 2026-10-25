"""Mesin peringatan & skor kesehatan."""
from __future__ import annotations

import re
import time
from collections import deque

from .config import ALERTS, DEV_ICON, LOCK, fmt_bytes, fmt_dur, wib_time

# --------------------------------------------------------------------------- alert engine
TH = {"cpu": (85, 95), "ram": (85, 93), "gpu_temp": (80, 88), "cpu_temp": (85, 95),
      "disk": (90, 95), "loss": (5, 15), "latency": (150, 300), "battery": (20, 10),
      "wifi": (50, 30)}  # sinyal WiFi: makin kecil makin buruk (persen)
ALERT_ON = 3    # detik berturut-turut di atas ambang sebelum peringatan muncul
ALERT_OFF = 6   # detik berturut-turut normal sebelum dianggap pulih
_act, _pend, _clr = {}, {}, {}
_events = deque(maxlen=40)


def _lv(v, warn, crit):
    return "crit" if v >= crit else "warn" if v >= warn else "ok"


def _rule(key, unit):
    w, c = TH[key]
    return f"Peringatan ≥ {w}{unit} · kritis ≥ {c}{unit}"


def _sid(s):
    return re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_") or "x"


def _alert(aid, level, icon, title, value, rule, detail, actions, metric, unit, context=None, top=None):
    return {"id": aid, "level": level, "icon": icon, "title": title, "value": value, "rule": rule,
            "detail": detail, "actions": actions, "metric": metric, "unit": unit,
            "context": context or [], "top": top or []}


def evaluate(L, S, lat, devs=None, guard=None, wifi=None):
    """Kembalikan (kandidat peringatan, daftar pemeriksaan) dari snapshot saat ini."""
    out, checks = [], []
    cpu_i, mem, net = L["cpu"], L["mem"], L["net"]
    procs, procs_mem = S.get("procs", []), S.get("procs_mem", [])

    # ---- CPU
    cpu = cpu_i["total"]
    lv = _lv(cpu, *TH["cpu"])
    checks.append({"id": "cpu", "label": "Beban CPU", "icon": "cpu", "value": f"{cpu:.0f}%",
                   "state": lv, "rule": _rule("cpu", "%")})
    if lv != "ok":
        freq = f" Frekuensi saat ini {cpu_i['freq'] / 1000:.2f} GHz." if cpu_i.get("freq") else ""
        out.append(_alert(
            "cpu", lv, "cpu", "CPU hampir penuh" if lv == "crit" else "Beban CPU tinggi",
            f"{cpu:.0f}%", _rule("cpu", "%"),
            f"Prosesor terpakai {cpu:.0f}% dari {len(cpu_i['cores'])} thread.{freq} "
            "Aplikasi bisa terasa lambat atau tersendat.",
            ["Akhiri atau tutup proses dengan beban terbesar pada daftar penyebab",
             "Periksa apakah ada scan antivirus, update sistem, atau indexing yang sedang berjalan",
             "Pastikan power plan tidak di mode hemat dan pendinginan (fan/heatsink) berfungsi baik"],
            cpu, "%",
            top=[{"name": p["name"], "val": round(p["cpu"], 1), "unit": "%"}
                 for p in procs[:3] if p["cpu"] >= 0.5]))

    # ---- RAM
    ram = mem["percent"]
    lv = _lv(ram, *TH["ram"])
    checks.append({"id": "ram", "label": "Pemakaian RAM", "icon": "mem", "value": f"{ram:.0f}%",
                   "state": lv, "rule": _rule("ram", "%")})
    if lv != "ok":
        out.append(_alert(
            "ram", lv, "mem", "Memori hampir habis" if lv == "crit" else "Pemakaian memori tinggi",
            f"{ram:.0f}%", _rule("ram", "%"),
            f"RAM terpakai {fmt_bytes(mem['used'])} dari {fmt_bytes(mem['total'])}. Swap terpakai "
            f"{mem['swap_percent']:.0f}%; saat RAM habis sistem memakai disk sehingga jauh lebih lambat.",
            ["Tutup tab browser dan aplikasi yang tidak dipakai",
             "Restart aplikasi dengan memori terbesar bila terus membengkak (indikasi memory leak)",
             "Pertimbangkan menambah RAM bila kondisi ini sering terjadi"],
            ram, "%",
            top=[{"name": p["name"], "val": round(p["mem"] / 100 * mem["total"] / 1e9, 2), "unit": "GB"}
                 for p in procs_mem[:3]]))

    # ---- suhu CPU
    if cpu_i.get("temp") is not None:
        t = cpu_i["temp"]
        lv = _lv(t, *TH["cpu_temp"])
        checks.append({"id": "cpu_temp", "label": "Suhu CPU", "icon": "thermo", "value": f"{t:.0f}°C",
                       "state": lv, "rule": _rule("cpu_temp", "°C")})
        if lv != "ok":
            out.append(_alert(
                "cpu_temp", lv, "thermo", "Suhu CPU tinggi", f"{t:.0f}°C", _rule("cpu_temp", "°C"),
                f"Suhu prosesor {t:.0f}°C. Suhu berlebih membuat CPU menurunkan kecepatan (thermal throttling).",
                ["Bersihkan debu pada fan dan heatsink, pastikan ventilasi tidak tertutup",
                 "Periksa pasta termal bila suhu tetap tinggi saat beban ringan",
                 "Kurangi beban kerja sementara sampai suhu turun"],
                t, "°C", top=[{"name": p["name"], "val": round(p["cpu"], 1), "unit": "%"}
                              for p in procs[:3] if p["cpu"] >= 0.5]))

    # ---- GPU
    gpus = L.get("gpu") or []
    for g in gpus:
        if g.get("temp") is None:
            continue
        gid = f"gpu_temp_{g['id']}"
        lv = _lv(g["temp"], *TH["gpu_temp"])
        label = "Suhu GPU" + (f" {g['id'] + 1}" if len(gpus) > 1 else "")
        checks.append({"id": gid, "label": label, "icon": "thermo", "value": f"{g['temp']:.0f}°C",
                       "state": lv, "rule": _rule("gpu_temp", "°C")})
        if lv != "ok":
            parts = []
            if g.get("util") is not None:
                parts.append(f"beban {g['util']:.0f}%")
            if g.get("power") is not None:
                parts.append(f"daya {g['power']:.0f} W")
            if g.get("fan") is not None:
                parts.append(f"fan {g['fan']:.0f}%")
            extra = " (" + ", ".join(parts) + ")" if parts else ""
            out.append(_alert(
                gid, lv, "thermo", f"{label} tinggi", f"{g['temp']:.0f}°C", _rule("gpu_temp", "°C"),
                f"{g['name']} berada di {g['temp']:.0f}°C{extra}. Suhu tinggi menurunkan performa dan umur komponen.",
                ["Periksa aliran udara casing dan bersihkan debu pada heatsink serta fan",
                 "Pastikan fan GPU berputar dan kurva fan tidak terlalu rendah",
                 "Turunkan beban: batasi FPS, kurangi power limit, atau turunkan kualitas grafis"],
                g["temp"], "°C"))

    # ---- disk
    for d in S.get("disks", [])[:6]:
        did = "disk_" + _sid(d["mount"])
        lv = _lv(d["percent"], *TH["disk"])
        checks.append({"id": did, "label": f"Drive {d['mount']}", "icon": "disk",
                       "value": f"{d['percent']:.0f}% terpakai", "state": lv, "rule": _rule("disk", "%")})
        if lv != "ok":
            out.append(_alert(
                did, lv, "disk", f"Drive {d['mount']} hampir penuh", f"{d['percent']:.0f}%", _rule("disk", "%"),
                f"Sisa ruang {fmt_bytes(d['total'] - d['used'])} dari {fmt_bytes(d['total'])}. "
                "Disk yang terlalu penuh memperlambat sistem dan bisa membuat update atau aplikasi gagal.",
                ["Jalankan Disk Cleanup / Storage Sense dan kosongkan Recycle Bin",
                 "Pindahkan file besar (video, backup, installer) ke drive lain atau cloud",
                 "Hapus aplikasi yang sudah tidak dipakai"],
                d["percent"], "%"))

    # ---- jaringan
    router = lat.get("Router")
    inet = [lat[k] for k in ("Cloudflare", "Google") if k in lat]
    r_ok = bool(router and router.get("ever_ok") and router.get("fails", 0) < 5)
    r_down = bool(router and router.get("ever_ok") and router.get("fails", 0) >= 5)
    inet_down = bool(inet) and all(v.get("fails", 0) >= 5 for v in inet)
    avgs = [v["avg"] for v in inet if v.get("avg") is not None]

    if inet:
        checks.append({"id": "internet", "label": "Koneksi internet", "icon": "wifi",
                       "value": "Terputus" if inet_down else (f"{sum(avgs) / len(avgs):.0f} ms" if avgs else "mengukur"),
                       "state": "crit" if inet_down else ("ok" if avgs else "na"),
                       "rule": "Kritis bila semua target gagal ≥ 5 detik berturut-turut"})
    if router:
        if router.get("avg") is not None:
            r_val, r_state = f"{router['avg']:.0f} ms", "ok"
        else:
            r_val, r_state = "tidak merespon", "crit" if r_down else "na"
        checks.append({"id": "router", "label": f"Router {router['host']}", "icon": "server", "value": r_val,
                       "state": r_state, "rule": "Ping ICMP ke gateway (bisa diblokir oleh router)"})

    if inet_down:
        gw = router["host"] if router else ""
        if r_down:
            title, detail = "Jaringan lokal terputus", (
                f"Router ({gw}) dan internet sama-sama tidak merespon. Perangkat ini kehilangan koneksi ke jaringan lokal.")
            actions = ["Periksa kabel LAN atau pastikan WiFi masih tersambung",
                       "Pastikan router menyala dan lampunya normal",
                       "Matikan lalu aktifkan kembali adapter jaringan, atau restart router"]
        elif r_ok:
            title, detail = "Internet terputus", (
                f"Router ({gw}) merespon normal tetapi internet tidak terjangkau. "
                "Gangguan kemungkinan ada di modem atau penyedia layanan (ISP).")
            actions = ["Restart modem/ONT dan tunggu sekitar 30 detik",
                       "Periksa lampu WAN/Internet pada modem",
                       "Hubungi ISP bila gangguan berlangsung lebih dari beberapa menit"]
        else:
            title, detail = "Internet terputus", "Cloudflare (1.1.1.1) dan Google (8.8.8.8) tidak dapat dijangkau."
            actions = ["Pastikan perangkat tersambung ke WiFi atau LAN",
                       "Restart router/modem",
                       "Periksa apakah VPN atau firewall memblokir koneksi"]
        out.append(_alert(
            "internet_down", "crit", "wifi", title, "Offline", "Semua target gagal ≥ 5 detik", detail, actions,
            100, "", context=[f"Gagal berturut-turut selama {min(v['fails'] for v in inet)} detik"]))

    for name in ("Cloudflare", "Google"):
        v = lat.get(name)
        if not v or v.get("samples", 0) < 10:
            continue
        loss = v["loss"]
        lv = _lv(loss, *TH["loss"])
        checks.append({"id": f"loss_{name}", "label": f"Packet loss {name}", "icon": "wifi",
                       "value": f"{loss:.0f}%", "state": lv, "rule": _rule("loss", "%")})
        if lv == "ok" or inet_down:
            continue
        lost = round(loss * v["samples"] / 100)
        if r_ok and router.get("samples", 0) >= 10:
            rl = router["loss"]
            if rl >= TH["loss"][0]:
                ctx = [f"Router ikut mengalami loss ({rl:.0f}%) → masalah ada di jaringan lokal: sinyal WiFi lemah, kabel longgar, atau interferensi."]
                actions = ["Dekatkan perangkat ke router atau pakai kabel LAN",
                           "Ganti channel WiFi atau pindah ke band 5 GHz",
                           "Restart router dan periksa kabel"]
            else:
                ctx = [f"Router stabil (loss {rl:.0f}%) → masalah ada setelah router, kemungkinan di ISP atau rute internet."]
                actions = ["Pantau beberapa menit; gangguan rute sering pulih sendiri",
                           "Restart modem bila loss menetap",
                           "Laporkan ke ISP disertai waktu kejadian dari Riwayat"]
        else:
            ctx = ["Router tidak bisa dijadikan pembanding (ICMP diblokir atau gateway tidak terdeteksi)."]
            actions = ["Periksa kekuatan sinyal WiFi atau kabel jaringan",
                       "Restart router/modem",
                       "Matikan sementara VPN atau unduhan besar lalu amati lagi"]
        out.append(_alert(
            f"loss_{name}", lv, "wifi", f"Packet loss ke {name}", f"{loss:.0f}%", _rule("loss", "%"),
            f"{lost} dari {v['samples']} uji koneksi terakhir ke {name} ({v['host']}) tidak terjawab. "
            "Loss membuat video call putus-putus, game lag, dan halaman web lambat dimuat.",
            actions, loss, "%", context=ctx))

    if avgs:
        la = sum(avgs) / len(avgs)
        lv = _lv(la, *TH["latency"])
        checks.append({"id": "latency", "label": "Latency internet", "icon": "pulse", "value": f"{la:.0f} ms",
                       "state": lv, "rule": _rule("latency", " ms")})
        if lv != "ok" and not inet_down:
            ctx = [f"Jitter hingga {max(v.get('jitter', 0) for v in inet):.0f} ms"]
            tp = (net["down"] + net["up"]) * 8 / 1e6
            if tp >= 20:
                ctx.append(f"Traffic jaringan sedang tinggi ({tp:.0f} Mbps) dan bisa menambah latency (bufferbloat).")
            if r_ok and router.get("avg") is not None:
                ra = router["avg"]
                ctx.append(f"Latency ke router {ra:.0f} ms → " + (
                    "jaringan lokal sehat, kelambatan ada di sisi ISP atau rute internet." if ra < 30
                    else "jaringan lokal ikut lambat (cek WiFi atau kabel)."))
            out.append(_alert(
                "latency", lv, "pulse", "Latency internet tinggi", f"{la:.0f} ms", _rule("latency", " ms"),
                f"Waktu respon rata-rata ke Cloudflare dan Google {la:.0f} ms. Latency tinggi terasa pada "
                "game online, video call, dan akses web.",
                ["Hentikan unduhan, unggahan, atau streaming besar yang sedang berjalan",
                 "Dekatkan perangkat ke router atau gunakan kabel LAN",
                 "Restart router; bila tetap tinggi hubungi ISP"],
                la, " ms", context=ctx))

    # ---- perangkat yang dipantau (HP, laptop, TV di Wi-Fi/LAN yang sama)
    for dv in devs or []:
        if dv["online"] is None:
            continue
        did = "dev_" + dv["id"]
        icon = DEV_ICON.get(dv["type"], "server")
        if dv["online"]:
            val = "Online" + (f" · {dv['last']:.0f} ms" if dv.get("last") is not None else "")
            checks.append({"id": did, "label": f"Perangkat {dv['name']}", "icon": icon, "value": val,
                           "state": "ok", "rule": f"{dv['ip']} · ping/probe LAN"})
            continue
        checks.append({"id": did, "label": f"Perangkat {dv['name']}", "icon": icon, "value": "Offline",
                       "state": "warn" if dv["watch"] else "na",
                       "rule": f"{dv['ip']} · peringatan " + ("aktif" if dv["watch"] else "dimatikan")})
        if not dv["watch"]:
            continue
        seen = f"Terakhir terlihat pukul {wib_time(dv['last_seen'])} WIB." if dv.get("last_seen") else "Belum pernah merespon sejak dipantau."
        if r_ok:
            ctx = ["Router merespon normal → Wi-Fi/LAN aktif; perangkat ini kemungkinan mati, keluar jangkauan, atau mode hemat daya.",
                   "HP sering menahan balasan ping saat layar mati — bisa jadi false alarm."]
        elif r_down:
            ctx = ["Router juga tidak merespon → masalah ada di jaringan lokal, bukan hanya di perangkat ini."]
        else:
            ctx = ["HP sering menahan balasan ping saat layar mati atau hemat daya — bisa jadi false alarm."]
        out.append(_alert(
            did, "warn", icon, f"{dv['name']} tidak terjangkau", "Offline", "Tidak membalas probe ≥ 10 detik",
            f"{dv['name']} ({dv['ip']}) tidak membalas ping maupun probe TCP. {seen}",
            ["Pastikan perangkat menyala dan tersambung ke Wi-Fi yang sama",
             "Nyalakan layar HP lalu cek lagi, atau nonaktifkan mode hemat daya Wi-Fi",
             "Matikan peringatan perangkat ini (ikon lonceng) bila memang sering offline"],
            100, "", context=ctx))

    # ---- sinyal WiFi PC ini
    if wifi and wifi.get("connected") and wifi.get("signal") is not None:
        sg = wifi["signal"]
        wl, cl = TH["wifi"]
        lv = "crit" if sg <= cl else "warn" if sg <= wl else "ok"
        wrule = f"Peringatan ≤ {wl}% · kritis ≤ {cl}%"
        checks.append({"id": "wifi_signal", "label": "Sinyal WiFi", "icon": "wifi", "value": f"{sg:.0f}%",
                       "state": lv, "rule": wrule})
        if lv != "ok":
            ctx = []
            if wifi.get("band"):
                ctx.append(f"Terhubung di band {wifi['band']}" + (f", channel {wifi['channel']}" if wifi.get("channel") else "") + ".")
            if wifi.get("band") == "2.4 GHz":
                ctx.append("Band 2.4 GHz jangkauannya jauh tetapi padat dan rawan interferensi; band 5 GHz lebih cepat namun jangkauannya lebih pendek.")
            if wifi.get("rx") is not None and wifi.get("tx") is not None:
                ctx.append(f"Kecepatan link saat ini {wifi['rx']:.0f} / {wifi['tx']:.0f} Mbps (terima / kirim).")
            dbm = f" (sekitar {wifi['dbm']} dBm)" if wifi.get("dbm") is not None else ""
            out.append(_alert(
                "wifi_signal", lv, "wifi", "Sinyal WiFi sangat lemah" if lv == "crit" else "Sinyal WiFi lemah",
                f"{sg:.0f}%", wrule,
                f"Sinyal ke {wifi.get('ssid') or 'access point'} hanya {sg:.0f}%{dbm}. Sinyal lemah membuat kecepatan "
                "turun, ping naik-turun, dan koneksi mudah putus.",
                ["Dekatkan PC ke router atau kurangi penghalang (dinding, lemari, logam)",
                 "Pindah ke band 5 GHz bila router dual-band, atau ganti channel yang lebih sepi",
                 "Gunakan kabel LAN atau tambahkan access point/repeater bila ruangan jauh dari router"],
                100 - sg, "", context=ctx))

    # ---- penjaga WiFi: perangkat asing
    if guard and guard.get("enabled"):
        unk, iv = guard["unknown"], guard["interval"]
        every = f"{iv // 60} menit" if iv >= 60 else f"{iv} detik"
        if guard["scanned"]:
            gl = "crit" if any(not u["random"] for u in unk) else "warn" if unk else "ok"
            checks.append({"id": "guard", "label": "Perangkat asing", "icon": "shield",
                           "value": f"{len(unk)} baru" if unk else "Aman", "state": gl,
                           "rule": f"Pindai tiap {every} · {guard['known']} perangkat dikenal"})
        else:
            checks.append({"id": "guard", "label": "Perangkat asing", "icon": "shield", "value": "menunggu pindai",
                           "state": "na", "rule": f"Pindai tiap {every}"})
        for u in unk:
            nm = u.get("name")
            now_txt = "saat ini sedang online" if u["online"] else "saat ini tidak terlihat (mungkin tidur atau keluar jangkauan)"
            ctx = [("MAC acak (fitur privasi HP): kemungkinan HP milik tamu atau HP sendiri yang alamatnya berganti."
                    if u["random"] else
                    "MAC asli (bukan acak): bisa dicocokkan dengan stiker label atau info perangkat."),
                   f"Pertama terlihat pukul {wib_time(u['first_seen'])} WIB, terlihat terakhir pukul {wib_time(u['last_seen'])} WIB."]
            out.append(_alert(
                "intruder_" + _sid(u["mac"]), "warn" if u["random"] else "crit", "radar",
                f"Perangkat asing: {nm}" if nm else "Perangkat asing terdeteksi", "Baru",
                "MAC belum pernah terlihat di jaringan ini",
                f"Perangkat {u['ip']} (MAC {u['mac']}) belum ada di daftar perangkat dikenal untuk jaringan {u['label']} "
                f"dan {now_txt}. Bisa jadi tamu atau perangkat baru milik sendiri, tetapi bisa juga ada yang menumpang WiFi.",
                ["Jika perangkat ini milik Anda: buka tab Perangkat, lalu klik Percayai",
                 "Cocokkan MAC dengan daftar client di halaman admin router; blokir lewat MAC filter bila bukan milik Anda",
                 "Ganti password WiFi (WPA2/WPA3) dan matikan WPS bila perangkat asing terus muncul"],
                100, "", context=ctx))

    # ---- MAC gateway berubah (router diganti, atau ARP spoofing / man-in-the-middle)
    for an in (guard or {}).get("anomalies", []):
        old = ", ".join(an["old"]) or "-"
        out.append(_alert(
            an["id"], "crit", "alert", "MAC gateway berubah", "Periksa",
            "MAC router berbeda dari yang pernah terlihat pada WiFi dan subnet yang sama",
            f"Pada WiFi '{an['ssid']}' ({an['subnet']}) gateway kini memakai MAC {an['new']}, sebelumnya {old}. Ini normal bila router "
            "diganti atau di-reset, tetapi juga pola khas ARP spoofing (ada perangkat yang menyamar sebagai router untuk menyadap lalu lintas).",
            ["Jika Anda memang mengganti/mereset router: buka tab Perangkat, klik Percayai pada peringatan ini",
             "Jika tidak: putuskan dari WiFi ini, jangan login ke akun penting, dan periksa daftar client di halaman admin router",
             "Gunakan HTTPS/VPN saat memakai jaringan yang diragukan"],
            100, "", context=[f"Pertama terlihat pukul {wib_time(an['ts'])} WIB."]))

    # ---- baterai
    b = L.get("battery")
    if b:
        pct, plugged = b["percent"], b["plugged"]
        lv = "ok" if plugged or pct > TH["battery"][0] else ("crit" if pct <= TH["battery"][1] else "warn")
        checks.append({"id": "battery", "label": "Baterai", "icon": "battery",
                       "value": f"{pct:.0f}%" + (" (mengisi)" if plugged else ""), "state": lv,
                       "rule": f"Peringatan ≤ {TH['battery'][0]}%, kritis ≤ {TH['battery'][1]}% saat tidak diisi"})
        if lv != "ok":
            out.append(_alert(
                "battery", lv, "battery", "Baterai hampir habis", f"{pct:.0f}%",
                f"Peringatan ≤ {TH['battery'][0]}% · kritis ≤ {TH['battery'][1]}%",
                f"Baterai tersisa {pct:.0f}% dan tidak sedang diisi. Laptop bisa mati sewaktu-waktu.",
                ["Colokkan charger sekarang", "Aktifkan mode hemat daya dan kurangi kecerahan layar",
                 "Simpan pekerjaan yang belum tersimpan"], 100 - pct, "%"))
    return out, checks


def health_score(L, active):
    score = 100.0
    for a in active:
        if a["id"].startswith(("dev_", "intruder_")):  # HP offline / tamu asing tidak menurunkan kesehatan PC
            continue
        score -= 30 if a["level"] == "crit" else 12
    score -= max(0, L["cpu"]["total"] - 60) * 0.15 + max(0, L["mem"]["percent"] - 70) * 0.15
    score = max(0, min(100, score))
    label = "Prima" if score >= 90 else "Baik" if score >= 75 else "Perlu perhatian" if score >= 50 else "Kritis"
    return {"score": round(score), "label": label}


def _peak_text(a):
    return "-" if not a["unit"] else f"{a['peak']:.0f}{a['unit']}"


def update_alerts(L, S, lat, devs=None, guard=None, wifi=None):
    cands, checks = evaluate(L, S, lat, devs, guard, wifi)
    now = time.time()
    cmap = {a["id"]: a for a in cands}
    for aid, a in cmap.items():
        _clr.pop(aid, None)
        cur = _act.get(aid)
        if cur:
            if a["level"] == "crit" and cur["level"] != "crit":
                _events.appendleft({"ts": now, "level": "crit", "kind": "escalate", "title": a["title"],
                                    "text": f"Naik ke kritis ({a['value']})"})
            since, peak = cur["since"], max(cur["peak"], a["metric"])
            cur.clear()
            cur.update(a, since=since, peak=peak)
        else:
            n = _pend.get(aid, 0) + 1
            _pend[aid] = n
            if n >= ALERT_ON:
                _act[aid] = dict(a, since=now, peak=a["metric"])
                _pend.pop(aid, None)
                _events.appendleft({"ts": now, "level": a["level"], "kind": "start", "title": a["title"],
                                    "text": f"Nilai {a['value']} · {a['rule']}"})
    for aid in list(_pend):
        if aid not in cmap:
            _pend.pop(aid)
    for aid in list(_act):
        if aid not in cmap:
            n = _clr.get(aid, 0) + 1
            _clr[aid] = n
            if n >= ALERT_OFF:
                a = _act.pop(aid)
                _clr.pop(aid, None)
                _events.appendleft({"ts": now, "level": "ok", "kind": "end", "title": a["title"],
                                    "text": f"Pulih setelah {fmt_dur(now - a['since'])} · puncak {_peak_text(a)}"})
    active = []
    for a in _act.values():
        d = dict(a)
        d["peak_text"] = _peak_text(a)
        active.append(d)
    active.sort(key=lambda a: (a["level"] != "crit", a["since"]))
    with LOCK:
        ALERTS.update(active=active, events=list(_events)[:30], checks=checks,
                      health=health_score(L, active), now=now)
