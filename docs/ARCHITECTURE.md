# Arsitektur

```
netsys_monitor/
  config.py     konstanta, path data (DATA_DIR), waktu WIB, state bersama (STATE, LAT, HIST, ALERTS, SCAN ...)
  util.py       helper: run_cmd, format, jaringan dasar (ping, gateway, MAC)
  hwmon.py      LibreHardwareMonitor (web/WMI): suhu, fan, GPU; merge_gpus; suhu CPU (psutil fallback)
  usage.py      pelacak pemakaian data (sesi/harian/bulanan, CSV)
  gpu.py        GPUReader (NVML / nvidia-smi / Windows perf counter) + gabung data LHM
  alerts.py     mesin peringatan: ambang, debounce, diagnosis, skor kesehatan
  devices.py    pindai ARP/LAN, perangkat yang dipantau (ping/jitter/loss)
  guard.py      penjaga WiFi: daftar MAC dikenal per jaringan, alert perangkat asing
  wifi.py       info WiFi PC ini (netsh/nmcli) - parser tidak bergantung bahasa Windows
  diag.py       traceroute + benchmark DNS (query UDP mentah)
  sampler.py    thread latar: sampler 1 dtk, loop lambat, monitor latency, speedtest, IP publik
  launcher.py   hosts file (opsional), pembuka jendela UI, fokus jendela yang ada
  appctl.py     logging, auto-start (HKCU Run), pengaturan, instance tunggal
  server.py     HTTP server: API JSON + berkas statis, keamanan (Host/Origin/token/rate limit/CSP)
  tray.py       ikon system tray (pystray)
  cli.py        argparse + orkestrasi start/stop
  static/       index.html, style.css, app.js, fonts/  (tanpa dependensi CDN)
```

## Aliran data
`sampler` (1 Hz) mengisi `STATE["latest"]`; `slow_loop` mengisi `STATE["slow"]` (disk, proses, koneksi). Thread lain
(`wifi_loop`, `guard_loop`, `hwmon_loop`) memperbarui state modulnya. `update_alerts` dijalankan tiap detik dan
menyusun peringatan dari seluruh state. UI melakukan polling `GET /api/stats` (1 detik) dan menggambar ulang.

## Urutan impor (tanpa siklus)
`config → util → hwmon → usage → gpu → alerts → devices → guard → wifi → diag → sampler → launcher → appctl → server → tray → cli`.
Satu-satunya impor lokal (dalam fungsi) adalah `devices.run_scan → guard.guard_ingest`.

## Tes
`pytest` memakai folder data sementara (`NETSYS_DATA`). Parser diuji dengan sampel nyata di `tests/data/`.
Server diuji end-to-end pada port acak (keamanan, statis, rate limit, token).
