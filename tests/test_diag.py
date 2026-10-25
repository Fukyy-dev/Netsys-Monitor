import socket
import threading

import pytest

from netsys_monitor.diag import dns_bench_one, dns_query, parse_trace_line, valid_target


def test_trace_windows_lines():
    h = parse_trace_line("  1    <1 ms    <1 ms    <1 ms  192.168.1.1", "192.168.1.1")
    assert h["n"] == 1 and h["ip"] == "192.168.1.1" and h["tag"] == "Router" and h["loss"] == 0
    h = parse_trace_line("  2     *        *        *     Request timed out.")
    assert h["ip"] is None and h["avg"] is None and h["loss"] == 100
    h = parse_trace_line("  4     8 ms     *        9 ms  100.64.1.1")
    assert h["tag"] == "CGNAT ISP" and h["loss"] == pytest.approx(100 / 3)


def test_trace_linux_and_decimal_comma():
    h = parse_trace_line(" 5  8.8.8.8  20.1 ms  21 ms  22,5 ms")
    assert h["ip"] == "8.8.8.8" and h["tag"] == "" and h["max"] == 22.5


def test_trace_ignores_headers():
    assert parse_trace_line("Tracing route to one.one.one.one [1.1.1.1]") is None
    assert parse_trace_line("over a maximum of 20 hops:") is None


@pytest.mark.parametrize("t,ok", [("1.1.1.1", True), ("google.com", True), ("::1", True), ("a-b.example.co.id", True),
                                  ("-oX", False), ("a b", False), ("x;rm -rf", False), ("a..b", False), ("", False),
                                  ("x" * 300, False)])
def test_valid_target(t, ok):
    assert valid_target(t) is ok


@pytest.fixture()
def fake_dns():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    rcode = {"v": 3}  # NXDOMAIN dianggap sukses

    def run():
        while True:
            try:
                d, a = s.recvfrom(512)
            except OSError:
                return
            s.sendto(d[:2] + bytes([0x81, 0x80 | rcode["v"]]) + d[4:], a)

    threading.Thread(target=run, daemon=True).start()
    yield s.getsockname()[1], rcode
    s.close()


def test_dns_query_ok_and_servfail(fake_dns):
    port, rcode = fake_dns
    assert dns_query("127.0.0.1", "abc.example.com", 1.0, port) is not None
    rcode["v"] = 2  # SERVFAIL -> gagal
    assert dns_query("127.0.0.1", "abc.example.com", 1.0, port) is None


def test_dns_query_timeout():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))  # tidak membalas
    assert dns_query("127.0.0.1", "example.com", 0.2, s.getsockname()[1]) is None
    s.close()


def test_dns_bench_one_unreachable(monkeypatch):
    monkeypatch.setattr("netsys_monitor.diag.dns_query", lambda *a, **k: None)
    r = dns_bench_one("x", "203.0.113.9", "public")
    assert r["ok"] == 0 and r["cold"] is None and r["score"] >= 9999
