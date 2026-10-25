import http.client
import json

import pytest

from netsys_monitor import server as srv

J = {"X-Netsys": "1", "Content-Type": "application/json"}


def req(port, method, path, body=None, headers=None, host=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{port}"}
    h.update(headers or {})
    c.request(method, path, body, h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, dict(r.getheaders()), data


def test_index_and_static(server):
    s, h, d = req(server, "GET", "/")
    assert s == 200 and b"/static/app.js?v=" in d and b"__VERSION__" not in d
    assert "default-src 'self'" in h["Content-Security-Policy"] and h["X-Frame-Options"] == "DENY"
    for p, ct in (("/static/style.css", "text/css"), ("/static/app.js", "text/javascript"), ("/static/fonts/ChakraPetch-Bold.woff2", "font/woff2")):
        s, h, d = req(server, "GET", p)
        assert s == 200 and h["Content-Type"].startswith(ct) and d


@pytest.mark.parametrize("p", ["/static/../config.py", "/static/%2e%2e/config.py", "/static//etc/passwd", "/static/nope.css"])
def test_static_traversal_blocked(server, p):
    assert req(server, "GET", p)[0] == 404


def test_no_external_requests_in_ui(server):
    for p in ("/", "/static/style.css", "/static/app.js"):
        body = req(server, "GET", p)[2].decode()
        assert "googleapis" not in body and "gstatic" not in body


def test_health_and_stats(server):
    assert json.loads(req(server, "GET", "/api/health")[2])["ok"] is True
    s, _, d = req(server, "GET", "/api/stats")
    assert s == 200 and {"guard", "wifi", "trace", "dns", "hwmon", "app"} <= set(json.loads(d))


def test_dns_rebinding_host_blocked(server):
    assert req(server, "GET", "/api/stats", host="evil.example")[0] == 403
    assert req(server, "POST", "/api/guard/config", "{}", J, host="evil.example")[0] == 403


def test_post_requires_header_and_same_origin(server):
    assert req(server, "POST", "/api/guard/config", "{}", {})[0] == 403
    assert req(server, "POST", "/api/guard/config", "{}", dict(J, Origin="http://evil.example"))[0] == 403
    assert req(server, "POST", "/api/guard/config", "{}", dict(J, Origin=f"http://127.0.0.1:{server}"))[0] == 200
    assert req(server, "POST", "/api/guard/config", "[1]", J)[0] == 400
    assert req(server, "POST", "/api/nope", "{}", J)[0] == 404


def test_rate_limit_and_target_validation(server, monkeypatch):
    monkeypatch.setattr(srv, "diag_trace_start", lambda b: (202, {"ok": True}))
    monkeypatch.setitem(srv.ROUTES, "/api/diag/trace", lambda b: (202, {"ok": True}))
    assert req(server, "POST", "/api/diag/trace", '{"target":"1.1.1.1"}', J)[0] == 202
    assert req(server, "POST", "/api/diag/trace", '{"target":"1.1.1.1"}', J)[0] == 429


def test_trace_rejects_option_injection(server):
    s, _, d = req(server, "POST", "/api/diag/trace", '{"target":"-oX /tmp/x"}', J)
    assert s == 400 and b"valid" in d


def test_token_mode():
    srv.configure_security("0.0.0.0", None, None)  # bind LAN -> token otomatis
    try:
        tok = srv.SEC["token"]
        assert tok and srv.SEC["lan"]
        import threading
        httpd = srv.Server(("127.0.0.1", 0), srv.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        port = httpd.server_address[1]
        assert req(port, "GET", "/")[0] == 401 and req(port, "GET", "/api/stats")[0] == 401
        s, h, _ = req(port, "GET", f"/?token={tok}")
        assert s == 302 and "netsys_token=" in h["Set-Cookie"] and "HttpOnly" in h["Set-Cookie"]
        cookie = {"Cookie": f"netsys_token={tok}"}
        assert req(port, "GET", "/api/stats", headers=cookie)[0] == 200
        assert req(port, "GET", "/api/stats", headers={"Cookie": "netsys_token=salah"})[0] == 401
        assert req(port, "POST", "/api/guard/config", "{}", dict(J, **cookie))[0] == 200
        assert req(port, "POST", "/api/guard/config", "{}", J)[0] == 401
        assert req(port, "GET", "/static/app.js")[0] == 200  # aset statis tidak rahasia
        httpd.shutdown()
        httpd.server_close()
    finally:
        srv.configure_security("127.0.0.1", None, None)


# ---------- fase 2: pengaturan, riwayat, ekspor ----------
def test_settings_api_roundtrip_and_validation(server):
    s, _, d = req(server, "GET", "/api/settings")
    assert s == 200 and json.loads(d)["theme"] in ("auto", "light", "dark") and "thresholds" in json.loads(d)
    s, _, d = req(server, "POST", "/api/settings", json.dumps({"theme": "dark", "thresholds": {"cpu": [70, 90]}}), J)
    assert s == 200 and json.loads(d)["thresholds"]["cpu"] == [70, 90]
    s, _, d = req(server, "POST", "/api/settings", json.dumps({"thresholds": {"cpu": [90, 70]}}), J)
    assert s == 400 and "kritis" in json.loads(d)["error"]
    req(server, "POST", "/api/settings/reset-thresholds", "{}", J)
    req(server, "POST", "/api/settings", json.dumps({"theme": "auto"}), J)


def test_secrets_never_returned(server):
    req(server, "POST", "/api/settings", json.dumps({"webhook": {"url": "https://h.example/TOPSECRET", "token": "TOK"}}), J)
    body = req(server, "GET", "/api/settings")[2].decode() + req(server, "GET", "/api/stats")[2].decode()
    assert "TOPSECRET" not in body and "TOK\"" not in body
    req(server, "POST", "/api/settings", json.dumps({"webhook": {"url": "", "token": ""}}), J)


def test_export_and_history_endpoints(server):
    from netsys_monitor import history
    history.log_event("start", "cpu", "warn", "CPU tinggi", "uji")
    s, h, d = req(server, "GET", "/api/export/events.csv")
    assert s == 200 and h["Content-Type"].startswith("text/csv") and "attachment" in h["Content-Disposition"] and b"CPU tinggi" in d
    assert req(server, "GET", "/api/export/all.json")[0] == 200
    assert req(server, "GET", "/api/export/bogus.csv")[0] == 404
    s, _, d = req(server, "GET", "/api/history/metrics?hours=abc")
    assert s == 200 and "rows" in json.loads(d)


def test_new_actions_validate_input(server):
    assert req(server, "POST", "/api/guard/wake", '{"mac":"bukan-mac"}', J)[0] == 400
    assert req(server, "POST", "/api/guard/ack", '{"id":"x"}', J)[0] == 404
    s, _, d = req(server, "POST", "/api/settings/test-webhook", "{}", J)
    assert s == 502 and "belum lengkap" in json.loads(d)["error"]
    s, _, d = req(server, "POST", "/api/update/check", "{}", J)
    assert s == 200 and json.loads(d)["error"]  # repo belum diatur
