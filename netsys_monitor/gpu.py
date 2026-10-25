"""Pembaca GPU (NVML/nvidia-smi/winperf)."""
from __future__ import annotations

import shutil
import threading
import time

from .config import IS_WIN, run_cmd, to_float
from .hwmon import hwmon_gpus, merge_gpus


# --------------------------------------------------------------------------- GPU
class GPUReader:
    def __init__(self):
        self.mode = None
        self.nv = None
        self.handles = []
        self.win_cache = []
        try:
            import pynvml
            pynvml.nvmlInit()
            n = pynvml.nvmlDeviceGetCount()
            if n > 0:
                self.nv = pynvml
                self.handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(n)]
                self.mode = "nvml"
        except Exception:
            pass
        if not self.mode and shutil.which("nvidia-smi"):
            self.mode = "smi"
        if not self.mode and IS_WIN:
            self.mode = "winperf"
            threading.Thread(target=self._winperf_loop, daemon=True).start()

    def _safe(self, fn, *a):
        try:
            return fn(*a)
        except Exception:
            return None

    def read(self):
        try:
            if self.mode == "nvml":
                base = self._read_nvml()
            elif self.mode == "smi":
                base = self._read_smi()
            elif self.mode == "winperf":
                base = [dict(g, src="winperf") for g in self.win_cache]
            else:
                base = []
        except Exception:
            base = []
        try:  # lengkapi/tambah dari LibreHardwareMonitor (VRAM, suhu, daya, fan, GPU AMD/Intel)
            return merge_gpus(base, hwmon_gpus())
        except Exception:
            return base

    def _read_nvml(self):
        nv, out = self.nv, []
        for i, h in enumerate(self.handles):
            name = self._safe(nv.nvmlDeviceGetName, h)
            if isinstance(name, bytes):
                name = name.decode(errors="ignore")
            util = self._safe(nv.nvmlDeviceGetUtilizationRates, h)
            mem = self._safe(nv.nvmlDeviceGetMemoryInfo, h)
            pw = self._safe(nv.nvmlDeviceGetPowerUsage, h)
            pl = self._safe(nv.nvmlDeviceGetEnforcedPowerLimit, h)
            out.append({
                "id": i, "name": name or "NVIDIA GPU",
                "util": util.gpu if util else None,
                "mem_util": util.memory if util else None,
                "vram_used": mem.used if mem else None,
                "vram_total": mem.total if mem else None,
                "temp": self._safe(nv.nvmlDeviceGetTemperature, h, nv.NVML_TEMPERATURE_GPU),
                "power": pw / 1000 if pw is not None else None,
                "power_limit": pl / 1000 if pl is not None else None,
                "fan": self._safe(nv.nvmlDeviceGetFanSpeed, h),
                "clock": self._safe(nv.nvmlDeviceGetClockInfo, h, nv.NVML_CLOCK_GRAPHICS),
                "clock_mem": self._safe(nv.nvmlDeviceGetClockInfo, h, nv.NVML_CLOCK_MEM),
            })
        return out

    def _read_smi(self):
        q = ("name,utilization.gpu,utilization.memory,memory.used,memory.total,"
             "temperature.gpu,power.draw,power.limit,fan.speed,clocks.gr,clocks.mem")
        txt = run_cmd(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"], 3)
        out = []
        for i, line in enumerate(l for l in txt.splitlines() if l.strip()):
            p = [x.strip() for x in line.split(",")]
            if len(p) < 11:
                continue
            f = to_float
            vu, vt = f(p[3]), f(p[4])
            out.append({
                "id": i, "name": p[0], "util": f(p[1]), "mem_util": f(p[2]),
                "vram_used": vu * 1048576 if vu is not None else None,
                "vram_total": vt * 1048576 if vt is not None else None,
                "temp": f(p[5]), "power": f(p[6]), "power_limit": f(p[7]),
                "fan": f(p[8]), "clock": f(p[9]), "clock_mem": f(p[10]),
            })
        return out

    def _winperf_loop(self):
        name_cmd = ["powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '|'"]
        names = [n for n in run_cmd(name_cmd, 8).split("|") if n]
        name = names[0] if names else "GPU"
        script = (r"$s=(Get-Counter '\GPU Engine(*engtype_3D)\Utilization Percentage' "
                  r"-ErrorAction SilentlyContinue).CounterSamples; "
                  r"if($s){($s|Measure-Object CookedValue -Sum).Sum}else{0}")
        while True:
            val = to_float(run_cmd(["powershell", "-NoProfile", "-Command", script], 8))
            if val is not None:
                self.win_cache = [{
                    "id": 0, "name": name, "util": min(100.0, val), "mem_util": None,
                    "vram_used": None, "vram_total": None, "temp": None, "power": None,
                    "power_limit": None, "fan": None, "clock": None, "clock_mem": None,
                }]
            time.sleep(1)
