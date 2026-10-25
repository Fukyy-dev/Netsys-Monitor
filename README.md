# Netsys Monitor

[Bahasa Indonesia](README.id.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

A local, privacy-friendly dashboard for **network and system monitoring** on Windows (Linux/macOS: core features).
Live latency/jitter/loss, WiFi quality, CPU/GPU/RAM/disk, **unknown-device detection on your WiFi**, traceroute, DNS benchmark,
alerts with diagnosis, a system-tray app and a single-file `.exe`. No cloud, no account, no telemetry.

<p align="center"><img src="docs/screenshots/network.png" alt="Network tab" width="820"><br><sub>Screenshots: see <a href="docs/screenshots/README.md">docs/screenshots</a></sub></p>

## Features
| Area | What you get |
|---|---|
| Network | realtime speed, latency/jitter/loss to router + Cloudflare + Google, data usage (session/day/month, CSV), active connections with process names, speedtest |
| **WiFi guard** | periodic ARP scan; new MAC address → alert until you click *Trust*; per-network lists; handles MAC randomization; vendor names (IEEE OUI, downloaded on demand); Wake-on-LAN; **gateway-MAC change** alert (ARP-spoofing hint) |
| **This PC's WiFi** | signal %, ≈dBm, band, channel, link speed, BSSID (`netsh wlan` / `nmcli`), weak-signal alert |
| Diagnostics | traceroute (live, per-hop loss and latency jump) and DNS benchmark (uncached vs cached, vs public resolvers) |
| Hardware | CPU temperature/fan/power and GPU load/VRAM/temperature/power/fan/clock via [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor); NVIDIA via NVML |
| Alerts | thresholds with debounce, probable cause (router vs ISP), top offending processes, suggested actions, event history, health score |
| Settings | light/dark/auto theme, quiet hours, per-metric thresholds, Discord/Telegram/JSON **webhook** alerts, optional update check |
| History | 30-day SQLite history (CPU/RAM/latency/WiFi charts), event log, CSV/JSON export |
| Desktop | tray icon with live tooltip, notifications, autostart (no admin), single instance, focuses the existing window |
| Privacy | one-key *hide IPs* mode (IP/MAC/SSID/PC name masked) for screenshots; fonts self-hosted; strict CSP |

## Install
**Windows exe (recommended):** download `NetsysMonitor-Setup-x.y.z.exe` (or the portable `NetsysMonitor.exe`) from [Releases](../../releases).
Verify with `SHA256SUMS.txt`. The exe is not code-signed, so SmartScreen/antivirus may warn; see [SECURITY.md](SECURITY.md).

**From source:**
```bash
pip install .            # or: pip install -r requirements.txt
python -m netsys_monitor            # console
python -m netsys_monitor --tray     # system tray
python -m netsys_monitor --install-autostart   # start with Windows (HKCU, no admin)
```
Default address: `http://127.0.0.1:8765` (opens as an app window in Edge/Chrome; use `--tab` for a normal tab).

## CPU/GPU temperature on Windows
Windows does not expose them to Python, so run **LibreHardwareMonitor as Administrator** and enable
*Options → Remote Web Server → Run* (port 8085). Netsys Monitor connects automatically (WMI fallback). AMD/Intel iGPUs often have no
temperature sensor; for APUs the CPU temperature is shown and labelled *suhu APU*.

## Command line
`--port`, `--host`, `--token`, `--hosts/--domain`, `--tab`, `--no-browser`, `--tray/--no-tray/--background`, `--scan-interval SEC`,
`--lhm-url`, `--no-lhm`, `--no-public-ip`, `--install-autostart/--remove-autostart`, `--log-level`. See `--help`.

## Security notes
Binds to `127.0.0.1` by default; checks `Host`/`Origin`; rate-limits heavy actions. `--host 0.0.0.0` (LAN) automatically **requires a token**.
No HTTPS: never expose it to the internet. Details in [SECURITY.md](SECURITY.md).

## Limits (honest)
- Unknown-device detection reads the ARP table: a phone asleep during a scan can be missed; phones with *private/rotating MAC* can appear as new devices.
- Per-process bandwidth is not available (psutil has no per-process network I/O).
- Developed and tested mostly on Windows 10/11 and Linux; parsers are tested with real samples, but hardware sensor coverage varies by machine. Please open a *Sensor not detected* issue with a `data.json` excerpt.

## Development
```bash
pip install -e ".[dev]" && ruff check . && pytest
```
Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). License: [MIT](LICENSE); third-party: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
