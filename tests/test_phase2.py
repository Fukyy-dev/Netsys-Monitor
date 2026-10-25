import csv
import io
import ipaddress
import json
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from netsys_monitor import guard, history, notify, oui, settings, updater, wol
from netsys_monitor.alerts import TH, evaluate


@pytest.fixture(autouse=True)
def clean_settings():
    with settings._LOCK:
        import copy
        settings._S.clear()
        settings._S.update(copy.deepcopy(settings.DEFAULTS))
        settings.apply_thresholds()
    yield


# ---------- settings ----------
def test_settings_validation():
    s = settings.apply({"theme": "dark", "quiet": {"enabled": True, "start": "22:30", "end": "06:00"}})
    assert s["theme"] == "dark" and s["quiet"]["start"] == "22:30"
    for bad in ({"theme": "neon"}, {"quiet": {"start": "25:00"}}, {"webhook": {"url": "javascript:alert(1)"}},
                {"webhook": {"kind": "sms"}}, {"thresholds": {"cpu": [95, 85]}}, {"thresholds": {"wifi": [30, 50]}},
                {"thresholds": {"cpu": ["a", 90]}}):
        with pytest.raises(ValueError):
            settings.apply(bad)
    assert settings.get("theme") == "dark"  # input buruk tidak mengubah apa pun


def test_thresholds_drive_alert_engine():
    settings.apply({"thresholds": {"cpu": [50, 60]}})
    assert TH["cpu"] == (50, 60)
    L = {"cpu": {"total": 55, "cores": [55], "freq": None}, "mem": {"percent": 10, "used": 1, "total": 2, "swap_percent": 0},
         "net": {"down": 0, "up": 0}, "gpu": []}
    out, _ = evaluate(L, {}, {}, [], None, None)
    assert any(a["id"] == "cpu" and a["level"] == "warn" for a in out)
    settings.reset_thresholds()
    assert TH["cpu"] == (85, 95)


def test_secrets_are_masked_and_mask_ignored():
    settings.apply({"webhook": {"url": "https://example.com/hook/SECRET", "token": "tok123"}})
    snap = settings.snapshot()
    assert snap["webhook"]["url"] == settings.MASK and snap["webhook"]["token"] == settings.MASK and "SECRET" not in json.dumps(snap)
    settings.apply({"webhook": {"url": settings.MASK, "token": settings.MASK, "enabled": True}})
    assert settings.snapshot(reveal=True)["webhook"]["url"].endswith("SECRET")


# ---------- jam tenang ----------
@pytest.mark.parametrize("hhmm,quiet", [("23:30", True), ("03:00", True), ("07:00", False), ("12:00", False), ("22:59", False)])
def test_quiet_hours_across_midnight(hhmm, quiet):
    settings.apply({"quiet": {"enabled": True, "start": "23:00", "end": "07:00"}})
    h, m = map(int, hhmm.split(":"))
    assert notify.in_quiet_hours(datetime(2026, 1, 1, h, m)) is quiet
    settings.apply({"quiet": {"enabled": False}})
    assert notify.in_quiet_hours(datetime(2026, 1, 1, h, m)) is False


# ---------- webhook ----------
@pytest.fixture()
def hook():
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            got.append((self.path, json.loads(self.rfile.read(n))))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", got
    srv.shutdown()


A = {"id": "intruder_X", "level": "crit", "title": "Perangkat asing", "value": "Baru", "detail": "MAC aa:bb"}


def test_webhook_discord_generic_telegram(hook, monkeypatch):
    base, got = hook
    settings.apply({"webhook": {"enabled": True, "kind": "discord", "url": base + "/d"}})
    assert notify.send_webhook(A)[0] and "content" in got[-1][1] and got[-1][0] == "/d"
    settings.apply({"webhook": {"kind": "generic", "url": base + "/g"}})
    assert notify.send_webhook(A)[0] and got[-1][1]["id"] == "intruder_X" and got[-1][1]["level"] == "crit"
    monkeypatch.setattr(notify, "TELEGRAM_API", base)
    settings.apply({"webhook": {"kind": "telegram", "token": "123:ABC", "chat_id": "42"}})
    assert notify.send_webhook(A)[0] and got[-1][0] == "/bot123:ABC/sendMessage" and got[-1][1]["chat_id"] == "42"


def test_webhook_failure_does_not_leak_secret():
    settings.apply({"webhook": {"enabled": True, "kind": "generic", "url": "http://127.0.0.1:1/SECRETPATH"}})
    ok, msg = notify.send_webhook(A)
    assert not ok and "SECRETPATH" not in msg and notify.WEBHOOK["ok"] is False
    settings.apply({"webhook": {"kind": "telegram", "token": "", "chat_id": ""}})
    assert notify.send_webhook(A)[0] is False


def test_dispatch_rules(hook, monkeypatch):
    base, got = hook
    notify._sent.clear()
    monkeypatch.setattr(notify, "_T0", time.time() - 3600)
    shown = []
    notify.set_desktop_handler(lambda t, m: shown.append(t))
    settings.apply({"webhook": {"enabled": True, "kind": "generic", "url": base + "/x", "min_level": "crit"}})
    assert notify.dispatch(A) == ["desktop", "webhook"]
    assert notify.dispatch(dict(A, id="cpu", level="warn")) == []            # warn biasa tidak mengganggu
    assert notify.dispatch(dict(A, id="intruder_Y", level="warn")) == ["desktop", "webhook"]  # tamu asing selalu penting
    settings.apply({"notify": False})
    assert notify.dispatch(dict(A, id="z")) == ["webhook"]
    settings.apply({"quiet": {"enabled": True, "start": "00:00", "end": "23:59"}})
    assert notify.dispatch(A) == []
    monkeypatch.setattr(notify, "_T0", time.time())                            # 45 dtk pertama setelah start
    settings.apply({"quiet": {"enabled": False}, "notify": True})
    assert notify.dispatch(dict(A, id="cpu2")) == []
    assert notify.dispatch(A) != []
    notify.set_desktop_handler(None)


def test_webhook_rate_cap(monkeypatch):
    notify._sent.clear()
    assert [notify._webhook_allowed() for _ in range(8)].count(True) == 6


# ---------- riwayat ----------
def test_history_roundtrip_and_export():
    history.log_metrics({"cpu": {"total": 12.0, "temp": 55.0}, "mem": {"percent": 40.0}, "net": {"down": 10, "up": 5}},
                        {"Cloudflare": {"last": 21.0}}, {"signal": 70.0}, ts=time.time() - 30)
    history.log_event("start", "cpu", "warn", "CPU tinggi", "x")
    history.log_dev("AA:BB:CC:DD:EE:FF", "192.168.1.9", "hp", "percayai")
    m = history.query_metrics(1)
    assert m["rows"] and m["rows"][-1]["cpu"] == 12.0 and m["rows"][-1]["wifi"] == 70.0
    rows = list(csv.reader(io.StringIO(history.export_csv("events"))))
    assert rows[0][:2] == ["waktu_wib", "jenis"] and any("CPU tinggi" in r for r in rows)
    assert "percayai" in history.export_csv("devices") and "cpu_pct" in history.export_csv("metrics")
    assert "events" in json.loads(history.export_json(1))
    with pytest.raises(KeyError):
        history.export_csv("nope")
    history.prune(days=0)
    assert len(list(csv.reader(io.StringIO(history.export_csv("events", 1))))) == 1  # tinggal header


# ---------- vendor OUI ----------
CSV = ('Registry,Assignment,Organization Name,Organization Address\n'
       'MA-L,F4F5D8,"Google, Inc.",x\nMA-L,3C5A37,Samsung Electronics Co.,Ltd.,x\n' + "".join(f"MA-L,{i:06X},V{i},x\n" for i in range(1, 1100)))


def test_oui_parse_and_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(oui, "OUI_FILE", str(tmp_path / "oui.csv"))
    oui._DB.update(map=None, mtime=0)
    assert oui.vendor_of("F4:F5:D8:00:00:01") is None  # belum ada database
    (tmp_path / "oui.csv").write_text(CSV, encoding="utf-8")
    assert oui.vendor_of("F4:F5:D8:00:00:01") == "Google"
    assert oui.vendor_of("f4-f5-d8-aa-bb-cc") == "Google"
    assert oui.vendor_of("FA:F5:D8:00:00:01") is None  # bit "locally administered" = MAC acak
    assert oui.vendor_of("zz") is None and oui.status()["loaded"] > 1000


def test_oui_download_validates(tmp_path, monkeypatch):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = (CSV if self.path == "/ok" else "bukan csv").encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(oui, "OUI_FILE", str(tmp_path / "oui.csv"))
    monkeypatch.setattr(oui, "OUI_URL", f"http://127.0.0.1:{srv.server_address[1]}/bad")
    assert oui.download()[0] is False and not (tmp_path / "oui.csv").exists()
    monkeypatch.setattr(oui, "OUI_URL", f"http://127.0.0.1:{srv.server_address[1]}/ok")
    assert oui.download()[0] is True and (tmp_path / "oui.csv").exists()
    srv.shutdown()


# ---------- WoL ----------
def test_wol_packet_and_validation():
    p = wol.magic_packet("aa:bb:cc:dd:ee:ff")
    assert len(p) == 102 and p[:6] == b"\xff" * 6 and p[6:12] == bytes.fromhex("aabbccddeeff")
    assert wol.send_wol("nope") == (False, "MAC tidak valid")
    assert wol.send_wol("aa:bb:cc:dd:ee:ff", "192.168.1.0/24")[0] in (True, False)


# ---------- update checker ----------
def test_version_compare():
    assert updater.is_newer("v2.3.0", "2.2") and updater.is_newer("2.2.1", "2.2.0") and updater.is_newer("3", "2.9.9")
    assert not updater.is_newer("2.2", "2.2.0") and not updater.is_newer("v2.1.9", "2.2")


def test_update_check_against_fake_github(monkeypatch):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"tag_name": "v9.9.9", "html_url": "https://github.com/o/r/releases/tag/v9.9.9"}).encode()
            self.send_response(200 if self.path.endswith("/o/r/releases/latest") else 404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(updater, "API_BASE", f"http://127.0.0.1:{srv.server_address[1]}")
    r = updater.check("o/r")
    assert r["available"] and r["version"] == "9.9.9" and r["url"].endswith("v9.9.9")
    assert updater.check("")["error"] and updater.check("bad repo")["error"]
    srv.shutdown()


# ---------- anomali gateway ----------
def test_gateway_mac_change_raises_critical_alert(monkeypatch):
    monkeypatch.setattr(guard, "wifi_snapshot", lambda: {"connected": True, "ssid": "Rumah"})
    with guard.KNOWN_LOCK:
        guard.KNOWN.update(networks={}, gateways={}, anomalies={})
        guard.GUARD.update(net=None, online=set())
    net = ipaddress.ip_network("192.168.1.0/24")
    dev = lambda ip, mac, r=False: {"ip": ip, "mac": mac, "name": None, "random": False, "router": r, "self": False}  # noqa: E731
    guard.guard_ingest([dev("192.168.1.1", "AA:00:00:00:00:01", True)], net, "AA:00:00:00:00:01")
    assert guard.guard_alert_state()["anomalies"] == []
    guard.guard_ingest([dev("192.168.1.1", "BB:00:00:00:00:99", True)], net, "BB:00:00:00:00:99")  # MAC router berubah
    st = guard.guard_alert_state()
    assert len(st["anomalies"]) == 1 and st["anomalies"][0]["new"] == "BB:00:00:00:00:99"
    L = {"cpu": {"total": 5, "cores": [5], "freq": None}, "mem": {"percent": 10, "used": 1, "total": 2, "swap_percent": 0},
         "net": {"down": 0, "up": 0}, "gpu": []}
    out, _ = evaluate(L, {}, {}, [], st, None)
    a = next(a for a in out if a["id"].startswith("gwchg_"))
    assert a["level"] == "crit" and "ARP spoofing" in a["detail"]
    assert guard.guard_ack({"id": a["id"]})[0] == 200 and guard.guard_alert_state()["anomalies"] == []
    guard.guard_ingest([dev("192.168.1.1", "BB:00:00:00:00:99", True)], net, "BB:00:00:00:00:99")
    assert guard.guard_alert_state()["anomalies"] == []  # sudah dipercaya
    assert guard.guard_ack({"id": "nope"})[0] == 404


def test_other_ssid_same_subnet_is_not_an_anomaly(monkeypatch):
    with guard.KNOWN_LOCK:
        guard.KNOWN.update(networks={}, gateways={}, anomalies={})
    net = ipaddress.ip_network("192.168.1.0/24")
    r = {"ip": "192.168.1.1", "name": None, "random": False, "router": True, "self": False}
    monkeypatch.setattr(guard, "wifi_snapshot", lambda: {"connected": True, "ssid": "Rumah"})
    guard.guard_ingest([dict(r, mac="AA:00:00:00:00:01")], net, "AA:00:00:00:00:01")
    monkeypatch.setattr(guard, "wifi_snapshot", lambda: {"connected": True, "ssid": "Kafe"})
    guard.guard_ingest([dict(r, mac="CC:00:00:00:00:02")], net, "CC:00:00:00:00:02")
    assert guard.guard_alert_state()["anomalies"] == []
