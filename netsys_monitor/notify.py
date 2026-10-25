"""Pengirim notifikasi: desktop (tray) dan webhook (Discord/Telegram/generic), jam tenang, serta pencatat riwayat."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request

from . import history, settings
from .config import ALERTS, APP_NAME, APP_VERSION, LAT, LOCK, STATE, wib_now

log = logging.getLogger("netsys")
TELEGRAM_API = os.environ.get("NETSYS_TELEGRAM_API", "https://api.telegram.org")
_T0 = time.time()
_desktop = [None]  # fungsi(title, msg) yang didaftarkan tray
WEBHOOK = {"ok": None, "ts": None, "error": None}
_sent = []  # cap pengiriman webhook: maksimal 6 per menit
EMOJI = {"crit": "🔴", "warn": "🟡", "ok": "🟢"}


def set_desktop_handler(fn):
    _desktop[0] = fn


def in_quiet_hours(now=None):
    q = settings.get("quiet", default={})
    if not q.get("enabled"):
        return False
    now = now or wib_now()
    cur = now.hour * 60 + now.minute
    a = int(q["start"][:2]) * 60 + int(q["start"][3:])
    b = int(q["end"][:2]) * 60 + int(q["end"][3:])
    if a == b:
        return False
    return a <= cur < b if a < b else (cur >= a or cur < b)  # lewat tengah malam


def _post(url, payload, timeout=6):
    req = urllib.request.Request(url, json.dumps(payload).encode("utf-8"),
                                 {"Content-Type": "application/json", "User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def build_webhook(cfg, a):
    """(url, payload) untuk satu alert. `a` = dict dengan id, level, title, value, detail."""
    text = f"{EMOJI.get(a['level'], '')} {a['title']}\n{a['value']} · {a['detail']}"[:1800]
    if cfg["kind"] == "telegram":
        return f"{TELEGRAM_API}/bot{cfg['token']}/sendMessage", {"chat_id": cfg["chat_id"], "text": f"{APP_NAME}\n{text}"}
    if cfg["kind"] == "discord":
        return cfg["url"], {"username": APP_NAME, "content": f"**{APP_NAME}**\n{text}"}
    return cfg["url"], {"app": APP_NAME, "version": APP_VERSION, "id": a["id"], "level": a["level"], "title": a["title"],
                        "value": a["value"], "detail": a["detail"], "ts": time.time()}


def webhook_ready(cfg):
    if cfg["kind"] == "telegram":
        return bool(cfg["token"] and cfg["chat_id"])
    return bool(cfg["url"])


def send_webhook(a, cfg=None):
    """Kirim sinkron. (ok, pesan)."""
    cfg = cfg or settings.snapshot(reveal=True)["webhook"]
    if not webhook_ready(cfg):
        return False, "Webhook belum lengkap (URL, atau token dan chat id untuk Telegram)."
    try:
        url, payload = build_webhook(cfg, a)
        _post(url, payload)
        WEBHOOK.update(ok=True, ts=time.time(), error=None)
        return True, "Terkirim"
    except Exception as e:
        msg = type(e).__name__ + (f" {e.code}" if hasattr(e, "code") else "")  # jangan bocorkan URL/token ke pesan
        WEBHOOK.update(ok=False, ts=time.time(), error=msg)
        log.warning("webhook gagal: %s", msg)
        return False, f"Gagal: {msg}"


def send_test():
    return send_webhook({"id": "test", "level": "warn", "title": "Tes notifikasi",
                         "value": "OK", "detail": "Jika Anda membaca ini, webhook Netsys Monitor berfungsi."})


def _webhook_allowed():
    now = time.time()
    _sent[:] = [t for t in _sent if now - t < 60]
    if len(_sent) >= 6:
        return False
    _sent.append(now)
    return True


def dispatch(a, now=None):
    """Putuskan & kirim notifikasi untuk satu alert baru. Mengembalikan daftar kanal yang dipakai (untuk tes)."""
    now = now or time.time()
    intruder = a["id"].startswith(("intruder_", "gwchg_"))
    if not (a["level"] == "crit" or intruder):
        return []
    if not intruder and now - _T0 < 45:  # lonjakan beban saat baru login/start
        return []
    if in_quiet_hours():
        return []
    used = []
    if settings.get("notify", default=True) and _desktop[0]:
        try:
            _desktop[0](a["title"], f"{a['value']} · {a['detail']}")
            used.append("desktop")
        except Exception:
            log.exception("notifikasi desktop gagal")
    cfg = settings.snapshot(reveal=True)["webhook"]
    if cfg["enabled"] and webhook_ready(cfg) and (a["level"] == "crit" or cfg["min_level"] == "warn" or intruder) and _webhook_allowed():
        threading.Thread(target=send_webhook, args=(a, cfg), daemon=True).start()
        used.append("webhook")
    return used


def _loop():
    seen, last_metric, last_prune = {}, 0.0, 0.0
    while True:
        time.sleep(2)
        try:
            with LOCK:
                active = {x["id"]: dict(id=x["id"], level=x["level"], title=x["title"], value=x["value"], detail=x["detail"])
                          for x in ALERTS.get("active", [])}
                latest, lat = STATE.get("latest"), dict(LAT)
            for aid, a in active.items():
                if aid not in seen:
                    history.log_event("start", aid, a["level"], a["title"], a["detail"])
                    dispatch(a)
            for aid, a in list(seen.items()):
                if aid not in active:
                    history.log_event("end", aid, "ok", a["title"], "")
            seen = active
            now = time.time()
            if latest and latest.get("cpu") and now - last_metric >= 60:
                from .wifi import wifi_snapshot
                history.log_metrics(latest, lat, wifi_snapshot())
                last_metric = now
            if now - last_prune > 3600:
                history.prune()
                last_prune = now
        except Exception:
            log.exception("dispatcher error")


def start():
    threading.Thread(target=_loop, daemon=True, name="notify").start()

