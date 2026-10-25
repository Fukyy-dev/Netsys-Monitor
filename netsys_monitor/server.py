"""Server HTTP & API."""
from __future__ import annotations

import getpass
import json
import logging
import platform
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import psutil

from .appctl import app_autostart, app_setting, app_status
from .config import ALERTS, APP_NAME, APP_VERSION, FALLBACK_DOMAIN, FROZEN, HIST, HISTORY_LEN, IS_WIN, LAT, LOCK, SCAN, ST, STATE
from .devices import dev_add, dev_remove, dev_update, device_snapshot, run_scan
from .diag import DNSB, diag_dns_start, diag_trace_start, trace_snapshot
from .guard import guard_config, guard_forget, guard_reset, guard_snapshot, guard_trust, guard_untrust
from .hwmon import hwmon_status
from .sampler import run_speedtest
from .usage import USAGE
from .util import cpu_name
from .wifi import wifi_snapshot


# --------------------------------------------------------------------------- web server
def os_release():
    rel = platform.release()
    if IS_WIN:
        try:  # Python lama melaporkan Windows 11 sebagai "10"
            if int(platform.version().split(".")[2]) >= 22000:
                rel = "11"
        except Exception:
            pass
    return rel


def _safe_user():
    try:
        return getpass.getuser()
    except Exception:
        return "-"


def system_info():
    return {
        "app": APP_NAME,
        "host": socket.gethostname(),
        "os": f"{platform.system()} {os_release()}",
        "os_name": platform.system(),
        "os_rel": os_release(),
        "os_ver": platform.version(),
        "arch": platform.machine(),
        "user": _safe_user(),
        "cpu": cpu_name(),
        "cores_phys": psutil.cpu_count(logical=False),
        "cores_log": psutil.cpu_count(),
        "ram_total": psutil.virtual_memory().total,
        "boot": psutil.boot_time(),
        "history_len": HISTORY_LEN,
        "version": APP_VERSION,
        "frozen": FROZEN,
    }


from . import history, oui, settings
from .config import ACTIVITY
from .guard import guard_ack, guard_wake
from .notify import send_test
from .updater import check

log = logging.getLogger("netsys")
INFO = {}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Windows: SO_REUSEADDR mengizinkan dua proses berbagi port yang sama -> matikan
    allow_reuse_address = not IS_WIN


# --------------------------------------------------------------------------- keamanan
STATIC_DIR = Path(__file__).resolve().parent / "static"
SEC = {"token": None, "hosts": set(), "lan": False}
_RATE = {}
_RATE_LOCK = threading.Lock()
MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8", ".woff2": "font/woff2", ".svg": "image/svg+xml",
        ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json; charset=utf-8"}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
# batas jeda minimum per aksi (detik): mencegah tombol yang dispam / skrip liar membebani PC atau jaringan
RATE_LIMITS = {"/api/settings/test-webhook": 5.0, "/api/oui/download": 10.0, "/api/update/check": 10.0, "/api/guard/wake": 2.0, "/api/diag/trace": 3.0, "/api/diag/dns": 5.0, "/api/speedtest": 5.0, "/api/devices/scan": 3.0,
               "/api/guard/reset": 3.0}


def configure_security(bind_host, domain, token=None):
    """Daftar Host yang sah + token. Bind non-loopback (akses dari LAN) otomatis mewajibkan token."""
    loop = bind_host in ("127.0.0.1", "localhost", "::1")
    SEC["hosts"] = {"127.0.0.1", "localhost", "[::1]", "::1", "netsys-monitor.localhost", FALLBACK_DOMAIN.lower(), (domain or "").lower()}
    SEC["lan"] = not loop
    if token == "auto" or (SEC["lan"] and not token):
        token = secrets.token_urlsafe(16)
    SEC["token"] = token or None
    return SEC["token"]


def rate_ok(path):
    gap = RATE_LIMITS.get(path)
    if not gap:
        return True
    now = time.monotonic()
    with _RATE_LOCK:
        if now - _RATE.get(path, -1e9) < gap:
            return False
        _RATE[path] = now
    return True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        log.debug("http %s", fmt % a)

    # ----- util kirim
    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        hdr = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
               "Referrer-Policy": "no-referrer", "Content-Security-Policy": CSP, "Cross-Origin-Resource-Policy": "same-origin"}
        hdr.update(headers or {})
        for k, v in hdr.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _redirect(self, to, headers=None):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()

    # ----- pemeriksaan
    def _host_ok(self):
        """Tolak Host asing: melindungi dari DNS rebinding (situs jahat yang diarahkan ke 127.0.0.1)."""
        if SEC["lan"]:
            return True  # akses LAN memang memakai IP/nama PC; dijaga token
        host = (self.headers.get("Host") or "").lower()
        host = host.rsplit(":", 1)[0] if not host.endswith("]") else host.split("]")[0] + "]"
        return host in SEC["hosts"]

    def _cookie_token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "netsys_token":
                return v
        return ""

    def _authed(self):
        tok = SEC["token"]
        if not tok:
            return True
        given = self.headers.get("X-Netsys-Token") or self._cookie_token()
        return bool(given) and secrets.compare_digest(given, tok)

    def _origin_ok(self):
        o = self.headers.get("Origin")
        if not o:
            return True
        host = self.headers.get("Host") or ""
        return o.split("://", 1)[-1] == host

    def _static(self, rel):
        f = (STATIC_DIR / rel).resolve()
        if STATIC_DIR not in f.parents or not f.is_file():
            return self._send(404, '{"error":"not found"}')
        cache = "public, max-age=31536000, immutable" if f.suffix == ".woff2" else "no-cache"
        self._send(200, f.read_bytes(), MIME.get(f.suffix.lower(), "application/octet-stream"), {"Cache-Control": cache})

    # ----- GET
    def do_GET(self):
        path, _, query = self.path.partition("?")
        if not self._host_ok():
            return self._send(403, '{"error":"host tidak diizinkan"}')
        if SEC["token"] and path in ("/", "/index.html"):
            qs = parse_qs(query)
            tk = (qs.get("token") or [""])[0]
            if tk and secrets.compare_digest(tk, SEC["token"]):  # tautan ber-token -> simpan cookie lalu bersihkan URL
                return self._redirect("/", {"Set-Cookie": f"netsys_token={SEC['token']}; Path=/; HttpOnly; SameSite=Strict"})
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if not self._authed():
            if path in ("/", "/index.html"):
                return self._send(401, "<!doctype html><meta charset=utf-8><title>Netsys Monitor</title>"
                                       "<body style='font:15px system-ui;padding:40px'><h2>Token diperlukan</h2>"
                                       "<p>Buka tautan lengkap (dengan <code>?token=...</code>) yang tercetak di console.</p>",
                                  "text/html; charset=utf-8")
            return self._send(401, '{"error":"unauthorized"}')
        if path in ("/", "/index.html"):
            html = (STATIC_DIR / "index.html").read_text(encoding="utf-8").replace("__VERSION__", APP_VERSION)
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/api/health":
            self._send(200, json.dumps({"ok": True, "app": APP_NAME, "version": APP_VERSION}))
        elif path == "/api/info":
            self._send(200, json.dumps(INFO))
        elif path == "/api/history":
            with LOCK:
                h = {k: list(v) for k, v in HIST.items()}
            self._send(200, json.dumps(h))
        elif path == "/api/settings":
            self._send(200, json.dumps(settings.snapshot()))
        elif path == "/api/history/metrics":
            qs = parse_qs(query)
            try:
                hours = int((qs.get("hours") or ["24"])[0])
            except ValueError:
                hours = 24
            self._send(200, json.dumps(history.query_metrics(hours)))
        elif path.startswith("/api/export/"):
            name = path[len("/api/export/"):]
            qs = parse_qs(query)
            try:
                days = int((qs.get("days") or ["30"])[0])
            except ValueError:
                days = 30
            if name == "all.json":
                self._send(200, history.export_json(days), "application/json; charset=utf-8",
                           {"Content-Disposition": 'attachment; filename="netsys-export.json"'})
            elif name in ("events.csv", "metrics.csv", "devices.csv"):
                self._send(200, history.export_csv(name[:-4], days), "text/csv; charset=utf-8",
                           {"Content-Disposition": f'attachment; filename="netsys-{name}"'})
            else:
                self._send(404, '{"error":"not found"}')
        elif path == "/api/stats":
            ACTIVITY["last"] = time.time()
            with LOCK:
                payload = {
                    "latest": STATE["latest"], "slow": STATE["slow"], "lat": dict(LAT),
                    "speedtest": ST, "usage": USAGE.summary(), "public_ip": STATE["public_ip"],
                    "alerts": ALERTS, "scan": SCAN,
                }
                payload["devices"] = device_snapshot()
                payload.update(guard=guard_snapshot(), wifi=wifi_snapshot(), trace=trace_snapshot(),
                               dns=dict(DNSB), hwmon=hwmon_status(), app=app_status())
                body = json.dumps(payload, default=str)
            self._send(200, body)
        elif path == "/api/usage.csv":
            self._send(200, USAGE.csv_text(), "text/csv; charset=utf-8",
                       {"Content-Disposition": 'attachment; filename="netsys-usage.csv"'})
        else:
            self._send(404, '{"error":"not found"}')

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = 0
        if n > 4096:
            return None
        try:
            return json.loads((self.rfile.read(n) if n else b"{}").decode("utf-8") or "{}")
        except Exception:
            return None

    # ----- POST
    def do_POST(self):
        path = self.path.split("?")[0]
        if not self._host_ok():
            return self._send(403, '{"error":"host tidak diizinkan"}')
        # Header kustom memaksa preflight CORS; Origin harus sama dengan Host -> situs lain tidak bisa memicu aksi ini
        if self.headers.get("X-Netsys") != "1" or not self._origin_ok():
            return self._send(403, '{"error":"forbidden"}')
        if not self._authed():
            return self._send(401, '{"error":"unauthorized"}')
        body = self._body()
        if body is None or not isinstance(body, dict):
            return self._send(400, '{"error":"bad request"}')
        if not rate_ok(path):
            return self._send(429, '{"error":"Terlalu sering. Tunggu beberapa detik lalu coba lagi."}')
        if path == "/api/speedtest":
            if not ST["running"]:
                threading.Thread(target=run_speedtest, daemon=True).start()
            return self._send(202, '{"ok":true}')
        if path == "/api/devices/scan":
            if not SCAN["running"]:
                threading.Thread(target=run_scan, daemon=True).start()
            return self._send(202, '{"ok":true}')
        fn = ROUTES.get(path)
        if not fn:
            return self._send(404, '{"error":"not found"}')
        code, res = fn(body)
        self._send(code, json.dumps(res))


def settings_apply(b):
    try:
        return 200, settings.apply(b)
    except ValueError as e:
        return 400, {"error": str(e)}


def settings_reset_th(b):
    settings.reset_thresholds()
    return 200, settings.snapshot()


def webhook_test(b):
    ok, msg = send_test()
    return (200 if ok else 502), ({"ok": True, "message": msg} if ok else {"error": msg})


def oui_download(b):
    ok, msg = oui.download()
    return (200 if ok else 502), ({"ok": True, "message": msg} if ok else {"error": msg})


def update_check(b):
    return 200, check()


ROUTES = {"/api/settings": settings_apply, "/api/settings/reset-thresholds": settings_reset_th,
          "/api/settings/test-webhook": webhook_test, "/api/oui/download": oui_download, "/api/update/check": update_check,
          "/api/guard/ack": guard_ack, "/api/guard/wake": guard_wake,
          "/api/devices/add": dev_add, "/api/devices/update": dev_update, "/api/devices/remove": dev_remove,
          "/api/guard/trust": guard_trust, "/api/guard/untrust": guard_untrust,
          "/api/guard/forget": guard_forget, "/api/guard/reset": guard_reset, "/api/guard/config": guard_config,
          "/api/diag/trace": diag_trace_start, "/api/diag/dns": diag_dns_start,
          "/api/app/autostart": app_autostart, "/api/app/setting": app_setting}
