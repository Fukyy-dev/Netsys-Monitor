import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from netsys_monitor.hwmon import _lhm_num, _lhm_row, _lhm_type, hwmon_summarize, lhm_fetch_web, merge_gpus


@pytest.fixture()
def lhm(lhm_json):
    """Server LHM palsu yang menyajikan data.json yang dipilih."""
    payload = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            b = json.dumps(payload["j"]).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(name):
        payload["j"] = lhm_json(name)
        return hwmon_summarize(lhm_fetch_web(f"http://127.0.0.1:{srv.server_address[1]}/data.json"))
    yield get
    srv.shutdown()


@pytest.mark.parametrize("s,v", [("58,5 °C", 58.5), ("1.250 RPM", 1250.0), ("1,200 RPM", 1200.0), ("0.004 V", 0.004),
                                 ("-1.000", -1.0), ("7686.7 MB", 7686.7), ("x", None)])
def test_lhm_num(s, v):
    assert _lhm_num(s) == v


def test_amd_igpu_real_structure(lhm):
    s = lhm("lhm_amd_igpu.json")
    assert s["cpu_temp"] == 64.5 and s["cpu_power"] == 12.5
    assert [f["rpm"] for f in s["fans"]] == [1250.0, 0.0] and s["fans"][0]["cpu"] is True
    (g,) = s["gpus"]
    assert g["name"] == "AMD Radeon(TM) Graphics" and g["util"] == 1.0
    assert (g["vram_used"], g["vram_total"]) == (384 * 2**20, 512 * 2**20)
    assert g["clock"] == 400 and g["clock_mem"] == 1600
    assert g["shared_total"] == pytest.approx(7886.7 * 2**20)
    # LHM tidak punya sensor suhu iGPU AMD -> pakai suhu APU (CPU) dan ditandai
    assert g["temp"] == 64.5 and g["temp_shared"] is True and g["power"] is None


def test_hybrid_laptop_decimal_comma_no_sensor_ids(lhm):
    s = lhm("lhm_laptop_hybrid.json")
    assert s["cpu_temp"] == 58.5  # "Distance to TjMax" harus diabaikan
    by = {g["name"]: g for g in s["gpus"]}
    nv = by["NVIDIA GeForce RTX 3060 Laptop GPU"]
    assert (nv["temp"], nv["hotspot"], nv["util"], nv["power"], nv["fan"]) == (61.0, 72.0, 35.0, 48.2, 41.0)
    assert nv["vram_used"] == 1536 * 2**20 and nv["vram_total"] == 6 * 2**30 and "temp_shared" not in nv
    ig = by["Intel(R) UHD Graphics"]
    assert ig["util"] == 12.0 and ig["temp"] == 58.5 and ig["temp_shared"] is True


def test_merge_into_nvml_base_and_adds_igpu(lhm):
    s = lhm("lhm_laptop_hybrid.json")
    base = [{"id": 0, "name": "NVIDIA GeForce RTX 3060 Laptop GPU", "util": 30, "mem_util": None, "vram_used": None,
             "vram_total": None, "temp": None, "power": None, "power_limit": None, "fan": None, "clock": None,
             "clock_mem": None}]
    out = merge_gpus(base, s["gpus"])
    assert len(out) == 2 and out[0]["util"] == 30 and out[0]["temp"] == 61.0 and out[0]["vram_total"] == 6 * 2**30
    assert out[1]["name"].startswith("Intel")


def test_merge_winperf_prefers_lhm_util(lhm):
    s = lhm("lhm_amd_igpu.json")
    wp = [{"id": 0, "name": "AMD Radeon(TM) Graphics", "util": 99.0, "mem_util": None, "vram_used": None,
           "vram_total": None, "temp": None, "power": None, "power_limit": None, "fan": None, "clock": None,
           "clock_mem": None, "src": "winperf"}]
    (g,) = merge_gpus(wp, s["gpus"])
    assert g["util"] == 1.0 and g["vram_used"] == 384 * 2**20 and g["src"] == "winperf+LHM"
    assert merge_gpus([], []) == []


def test_wmi_style_rows():
    rows = [_lhm_row([], "/gpu-amd/0/temperature/0", "GPU Core", _lhm_type("", "Temperature", "GPU Core"), "", 55.0, "Temperature"),
            _lhm_row([], "/gpu-amd/0/smalldata/0", "GPU Memory Used", _lhm_type("", "SmallData", "x"), "", 2048.0, "SmallData"),
            _lhm_row([], "/gpu-amd/0/smalldata/1", "GPU Memory Total", _lhm_type("", "SmallData", "x"), "", 8192.0, "SmallData"),
            _lhm_row([], "/gpu-amd/0/load/0", "GPU Core", _lhm_type("", "Load", "GPU Core"), "", 77.0, "Load")]
    (g,) = hwmon_summarize(rows)["gpus"]
    assert g["temp"] == 55.0 and g["util"] == 77.0 and g["vram_total"] == 8192 * 2**20
