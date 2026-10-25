import ipaddress

from netsys_monitor import guard
from netsys_monitor.alerts import evaluate

NET1 = ipaddress.ip_network("192.168.1.0/24")
NET2 = ipaddress.ip_network("10.0.0.0/24")
LAT0 = {"cpu": {"total": 5, "cores": [5], "freq": None}, "mem": {"percent": 10, "used": 1, "total": 2, "swap_percent": 0},
        "net": {"down": 0, "up": 0}, "gpu": []}


def dev(ip, mac, **k):
    return {"ip": ip, "mac": mac, "name": k.get("name"), "random": k.get("random", False),
            "router": k.get("router", False), "self": False}


def reset():
    with guard.KNOWN_LOCK:
        guard.KNOWN["networks"] = {}
        guard.GUARD.update(net=None, online=set())


def test_baseline_then_new_device_then_trust():
    reset()
    base = [dev("192.168.1.1", "AA:00:00:00:00:01", router=True), dev("192.168.1.20", "AA:00:00:00:00:02")]
    guard.guard_ingest(base, NET1, "AA:00:00:00:00:01")
    st = guard.guard_alert_state()
    assert st["unknown"] == [] and st["scanned"] and st["known"] == 2

    guard.guard_ingest(base + [dev("192.168.1.77", "DE:AD:BE:EF:00:01"), dev("192.168.1.78", "DA:AD:BE:EF:00:02", random=True)],
                       NET1, "AA:00:00:00:00:01")
    st = guard.guard_alert_state()
    assert {u["mac"] for u in st["unknown"]} == {"DE:AD:BE:EF:00:01", "DA:AD:BE:EF:00:02"}

    alerts, checks = evaluate(LAT0, {}, {}, [], st, None)
    lv = {a["id"]: a["level"] for a in alerts if a["id"].startswith("intruder_")}
    assert lv == {"intruder_DE_AD_BE_EF_00_01": "crit", "intruder_DA_AD_BE_EF_00_02": "warn"}  # MAC acak = kuning
    assert [c["state"] for c in checks if c["id"] == "guard"] == ["crit"]

    assert guard.guard_trust({"mac": "DE:AD:BE:EF:00:01"})[0] == 200
    assert [u["mac"] for u in guard.guard_alert_state()["unknown"]] == ["DA:AD:BE:EF:00:02"]
    assert guard.guard_untrust({"mac": "DE:AD:BE:EF:00:01"})[0] == 200
    assert len(guard.guard_alert_state()["unknown"]) == 2
    assert guard.guard_trust({"all": True})[0] == 200 and guard.guard_alert_state()["unknown"] == []


def test_other_network_gets_its_own_baseline():
    reset()
    guard.guard_ingest([dev("192.168.1.1", "AA:00:00:00:00:01", router=True)], NET1, "AA:00:00:00:00:01")
    guard.guard_ingest([dev("10.0.0.1", "BB:00:00:00:00:01", router=True), dev("10.0.0.5", "BB:00:00:00:00:09")], NET2, "BB:00:00:00:00:01")
    assert guard.guard_alert_state()["unknown"] == [] and len(guard.KNOWN["networks"]) == 2


def test_empty_first_scan_does_not_finish_baseline():
    reset()
    guard.guard_ingest([], NET1, "AA:00:00:00:00:01")
    assert guard.guard_alert_state()["scanned"] is False
    guard.guard_ingest([dev("192.168.1.9", "AA:00:00:00:00:09")], NET1, "AA:00:00:00:00:01")
    assert guard.guard_alert_state()["unknown"] == []  # perangkat pertama tetap baseline, bukan asing


def test_persistence_roundtrip_and_forget_reset():
    reset()
    guard.guard_ingest([dev("192.168.1.1", "AA:00:00:00:00:01", router=True), dev("192.168.1.5", "AA:00:00:00:00:05")], NET1, "AA:00:00:00:00:01")
    with guard.KNOWN_LOCK:
        guard.KNOWN["networks"] = {}
    guard.load_known()
    assert len(guard.KNOWN["networks"]) == 1
    assert guard.guard_forget({"mac": "AA:00:00:00:00:05"})[0] == 200
    assert guard.guard_forget({"mac": "AA:00:00:00:00:05"})[0] == 404
    assert guard.guard_trust({"mac": "zz"})[0] == 404


def test_config_is_clamped():
    guard.guard_config({"interval": 99999, "enabled": True})
    assert guard.KNOWN["config"]["interval"] == guard.GUARD_MAX
    guard.guard_config({"interval": 1})
    assert guard.KNOWN["config"]["interval"] == guard.GUARD_MIN


def test_weak_wifi_alert():
    w = {"connected": True, "signal": 28.0, "ssid": "X", "band": "2.4 GHz", "channel": 6, "rx": 50, "tx": 40, "dbm": -86}
    alerts, _ = evaluate(LAT0, {}, {}, [], None, w)
    a = next(a for a in alerts if a["id"] == "wifi_signal")
    assert a["level"] == "crit"
    ok, checks = evaluate(LAT0, {}, {}, [], None, dict(w, signal=80.0))
    assert not any(a["id"] == "wifi_signal" for a in ok)
