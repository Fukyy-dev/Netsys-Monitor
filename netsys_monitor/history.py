"""Riwayat jangka panjang (SQLite): metrik per menit, kejadian peringatan, aksi pada perangkat. Ekspor CSV/JSON."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import sqlite3
import threading
import time

from .config import DATA_DIR

log = logging.getLogger("netsys")
DB_FILE = os.path.join(DATA_DIR, "history.db")
RETENTION_DAYS = 30
_LOCK = threading.Lock()
_conn = [None]
SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics(ts INTEGER PRIMARY KEY, cpu REAL, ram REAL, down REAL, up REAL, ping REAL, wifi REAL, cpu_temp REAL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, alert_id TEXT, level TEXT, title TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS devlog(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, mac TEXT, ip TEXT, name TEXT, action TEXT);
CREATE INDEX IF NOT EXISTS ev_ts ON events(ts);
"""


def _db():
    if _conn[0] is None:
        c = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=5)
        c.executescript(SCHEMA)
        _conn[0] = c
    return _conn[0]


def _exec(sql, args=(), many=False):
    try:
        with _LOCK:
            c = _db()
            cur = c.executemany(sql, args) if many else c.execute(sql, args)
            c.commit()
            return cur.fetchall()
    except sqlite3.Error as e:
        log.warning("history db: %s", e)
        return []


def log_metrics(latest, lat, wifi, ts=None):
    try:
        ts = int(ts or time.time())
        cpu, mem, net = latest["cpu"], latest["mem"], latest.get("net") or {}
        ping = (lat.get("Cloudflare") or {}).get("last")
        _exec("INSERT OR REPLACE INTO metrics VALUES(?,?,?,?,?,?,?,?)",
              (ts, cpu["total"], mem["percent"], net.get("down"), net.get("up"), ping,
               (wifi or {}).get("signal"), cpu.get("temp")))
    except (KeyError, TypeError):
        pass


def log_event(kind, alert_id, level, title, detail="", ts=None):
    _exec("INSERT INTO events(ts,kind,alert_id,level,title,detail) VALUES(?,?,?,?,?,?)",
          (ts or time.time(), kind, alert_id, level, title, (detail or "")[:500]))


def log_dev(mac, ip, name, action):
    _exec("INSERT INTO devlog(ts,mac,ip,name,action) VALUES(?,?,?,?,?)", (time.time(), mac, ip or "", name or "", action))


def prune(days=RETENTION_DAYS):
    cut = time.time() - days * 86400
    for t, col in (("metrics", "ts"), ("events", "ts"), ("devlog", "ts")):
        _exec(f"DELETE FROM {t} WHERE {col} < ?", (cut,))


def query_metrics(hours=24, points=240):
    """Rata-rata per bucket supaya grafik ringan: maksimal `points` titik."""
    hours = max(1, min(int(hours), RETENTION_DAYS * 24))
    since = int(time.time() - hours * 3600)
    bucket = max(60, int(hours * 3600 / max(10, int(points))))
    rows = _exec("SELECT (ts/?)*? AS b, AVG(cpu), AVG(ram), AVG(down), AVG(up), AVG(ping), AVG(wifi), AVG(cpu_temp) "
                 "FROM metrics WHERE ts >= ? GROUP BY b ORDER BY b", (bucket, bucket, since))
    keys = ("ts", "cpu", "ram", "down", "up", "ping", "wifi", "cpu_temp")
    return {"hours": hours, "bucket": bucket, "rows": [dict(zip(keys, r)) for r in rows]}


def _csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _iso(ts):
    from datetime import datetime

    from .config import WIB
    return datetime.fromtimestamp(ts, WIB).strftime("%Y-%m-%d %H:%M:%S") if ts else ""


def export_csv(kind, days=RETENTION_DAYS):
    since = time.time() - max(1, min(int(days), 365)) * 86400
    if kind == "events":
        rows = _exec("SELECT ts,kind,alert_id,level,title,detail FROM events WHERE ts>=? ORDER BY ts", (since,))
        return _csv(["waktu_wib", "jenis", "id", "level", "judul", "detail"], [[_iso(r[0])] + list(r[1:]) for r in rows])
    if kind == "metrics":
        rows = _exec("SELECT ts,cpu,ram,down,up,ping,wifi,cpu_temp FROM metrics WHERE ts>=? ORDER BY ts", (since,))
        return _csv(["waktu_wib", "cpu_pct", "ram_pct", "down_Bps", "up_Bps", "ping_ms", "wifi_pct", "cpu_temp_c"],
                    [[_iso(r[0])] + [("" if v is None else round(v, 2)) for v in r[1:]] for r in rows])
    if kind == "devices":
        rows = _exec("SELECT ts,mac,ip,name,action FROM devlog WHERE ts>=? ORDER BY ts", (since,))
        return _csv(["waktu_wib", "mac", "ip", "nama", "aksi"], [[_iso(r[0])] + list(r[1:]) for r in rows])
    raise KeyError(kind)


def export_json(days=RETENTION_DAYS):
    return json.dumps({"events": _exec("SELECT ts,kind,alert_id,level,title,detail FROM events WHERE ts>=? ORDER BY ts",
                                       (time.time() - days * 86400,)),
                       "metrics": query_metrics(days * 24, 1000)["rows"]}, ensure_ascii=False)
