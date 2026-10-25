from netsys_monitor.wifi import parse_netsh_wlan, parse_nmcli_wifi


def test_netsh_english(data_dir):
    w = parse_netsh_wlan((data_dir / "netsh_en.txt").read_text())
    assert w["connected"] and w["ssid"] == "RumahKu" and w["bssid"] == "11:22:33:44:55:66"
    assert (w["signal"], w["channel"], w["band"], w["radio"]) == (74.0, 36, "5 GHz", "802.11ax")
    assert (w["rx"], w["tx"]) == (866.7, 729.4)
    assert w["dbm"] == -63 and w["quality"] == "Kuat"


def test_netsh_indonesian_labels(data_dir):
    w = parse_netsh_wlan((data_dir / "netsh_id.txt").read_text())
    assert w["connected"] and w["ssid"] == "Kos Budi"
    assert (w["signal"], w["channel"], w["rx"], w["tx"]) == (38.0, 6, 144.4, 130.0)
    assert w["band"] == "2.4 GHz"  # diturunkan dari channel karena tidak ada baris Band


def test_netsh_unknown_language_falls_back_to_position(data_dir):
    txt = (data_dir / "netsh_id.txt").read_text()
    for lbl in ("Saluran", "Kecepatan terima (Mbps)", "Kecepatan kirim (Mbps) "):
        txt = txt.replace(lbl, "Xx" + str(len(lbl)))
    w = parse_netsh_wlan(txt)
    assert (w["channel"], w["rx"], w["tx"]) == (6, 144.4, 130.0)


def test_netsh_disconnected():
    w = parse_netsh_wlan("    Name : Wi-Fi\n    State : disconnected\n")
    assert w is not None and w["connected"] is False


def test_netsh_garbage():
    assert parse_netsh_wlan("The Wireless AutoConfig Service (wlansvc) is not running.") is None


def test_nmcli():
    out = "no:Other:AA\\:BB\\:CC\\:DD\\:EE\\:02:1:2412 MHz:54 Mbit/s:30:WPA2\nyes:Cafe:AA\\:BB\\:CC\\:DD\\:EE\\:FF:36:5180 MHz:540 Mbit/s:81:WPA2"
    w = parse_nmcli_wifi(out)
    assert w["ssid"] == "Cafe" and w["bssid"] == "AA:BB:CC:DD:EE:FF" and w["band"] == "5 GHz"
    assert w["signal"] == 81.0 and w["channel"] == 36
    assert parse_nmcli_wifi("no:Other:AA\\:BB\\:CC\\:DD\\:EE\\:02:1:2412 MHz:54 Mbit/s:30:WPA2") is None
