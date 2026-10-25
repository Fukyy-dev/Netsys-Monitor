"""Titik masuk baris perintah."""
from __future__ import annotations

import argparse
import threading

from .appctl import (
    acquire_single_instance,
    autostart_command,
    fatal,
    msgbox,
    read_instance_url,
    say,
    set_autostart,
    setup_logging,
    write_instance_url,
)
from .config import APP_NAME, APP_VERSION, DEFAULT_DOMAIN, DEFAULT_PORT, FALLBACK_DOMAIN, FROZEN, HOSTS_PATH, IS_WIN, STATE, USAGE_FILE
from .devices import load_devices
from .gpu import GPUReader
from .guard import GUARD_DEFAULT, GUARD_MAX, GUARD_MIN, KNOWN, KNOWN_LOCK, guard_loop, load_known, save_known
from .hwmon import HW_CFG, LHM_DEFAULT_URL, hwmon_loop
from .launcher import ensure_hosts, open_ui, remove_hosts
from .notify import start as notify_start
from .sampler import public_ip_loop, sampler, slow_loop, start_latency_monitors
from .server import INFO, SEC, Handler, Server, configure_security, system_info
from .tray import make_ico, run_tray, tray_available
from .updater import update_loop
from .usage import USAGE
from .util import _clamp_int, iface_meta, local_ip
from .wifi import wifi_loop


def build_parser():
    ap = argparse.ArgumentParser(prog="netsys-monitor", description="Netsys Monitor - dashboard jaringan & sistem")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    ap.add_argument("--host", default="127.0.0.1",
                    help="alamat bind. Default 127.0.0.1 (hanya PC ini). 0.0.0.0 = bisa diakses dari LAN; token otomatis diwajibkan")
    ap.add_argument("--port", type=int, default=0, help=f"default: {DEFAULT_PORT} (bila terpakai, coba port berikutnya)")
    ap.add_argument("--token", default=None, metavar="TOKEN",
                    help="wajibkan token untuk membuka dashboard/API ('auto' = buat acak). Otomatis aktif bila --host bukan loopback")
    ap.add_argument("--hosts", action="store_true",
                    help="daftarkan nama --domain ke hosts file (butuh Administrator) agar bisa dibuka lewat nama itu")
    ap.add_argument("--domain", default=DEFAULT_DOMAIN, help=f"nama alamat dashboard untuk --hosts (default {DEFAULT_DOMAIN})")
    ap.add_argument("--no-hosts", action="store_true", help=argparse.SUPPRESS)  # kompatibilitas v2.x: sekarang default
    ap.add_argument("--remove-hosts", action="store_true", help="hapus entri domain dari hosts file lalu keluar")
    ap.add_argument("--tab", action="store_true", help="buka di tab browser biasa, bukan jendela aplikasi")
    ap.add_argument("--no-browser", action="store_true", help="jangan buka jendela otomatis")
    ap.add_argument("--no-public-ip", action="store_true", help="jangan cek IP publik (menghubungi api.ipify.org)")
    ap.add_argument("--scan-interval", type=int, default=None, metavar="DETIK",
                    help=f"jeda pindai otomatis penjaga WiFi ({GUARD_MIN}-{GUARD_MAX} dtk, default tersimpan/{GUARD_DEFAULT}); 0 = matikan")
    ap.add_argument("--lhm-url", default=None, metavar="URL",
                    help=f"alamat Remote Web Server LibreHardwareMonitor (default {LHM_DEFAULT_URL}, hanya Windows)")
    ap.add_argument("--no-lhm", action="store_true", help="jangan baca sensor dari LibreHardwareMonitor")
    ap.add_argument("--tray", action="store_true", help="jalan di system tray (default untuk .exe di Windows)")
    ap.add_argument("--no-tray", action="store_true", help="jangan pakai ikon tray")
    ap.add_argument("--background", action="store_true", help="mulai diam-diam di tray tanpa membuka jendela (dipakai auto-start)")
    ap.add_argument("--no-single", action="store_true", help="izinkan lebih dari satu instance")
    ap.add_argument("--install-autostart", action="store_true", help="aktifkan auto-start Windows (tanpa admin) lalu keluar")
    ap.add_argument("--remove-autostart", action="store_true", help="matikan auto-start Windows lalu keluar")
    ap.add_argument("--make-icon", nargs="?", const="netsys.ico", metavar="FILE", help="buat file ikon .ico (untuk PyInstaller) lalu keluar")
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="tingkat detail log")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)

    if args.make_icon:
        try:
            make_ico(args.make_icon)
            say(f"Ikon dibuat: {args.make_icon}")
        except Exception as e:
            say(f"Gagal membuat ikon (butuh: pip install pillow): {e}")
        return
    if args.install_autostart or args.remove_autostart:
        ok, err = set_autostart(bool(args.install_autostart))
        say(("Auto-start " + ("diaktifkan: " + autostart_command() if args.install_autostart else "dimatikan."))
            if ok else f"Gagal: {err}")
        return
    if args.remove_hosts:
        ok = remove_hosts(args.domain)
        say("Entri hosts dihapus." if ok else f"Gagal mengubah {HOSTS_PATH} (jalankan sebagai Administrator/root).")
        return

    want_tray = (args.tray or args.background or (FROZEN and IS_WIN)) and not args.no_tray
    if want_tray and not tray_available():
        msg = "Ikon tray butuh paket pystray dan pillow:  pip install pystray pillow"
        say("Info: " + msg)
        if FROZEN or args.background:
            msgbox(APP_NAME, msg)
        want_tray = False

    if not args.no_single and not acquire_single_instance():
        url = read_instance_url() or f"http://{FALLBACK_DOMAIN}:{DEFAULT_PORT}"
        say(f"{APP_NAME} sudah berjalan di {url}.")
        if not args.background and not args.no_browser:
            open_ui(url, not args.tab)
        return

    INFO.update(system_info())
    load_devices()
    load_known()
    if args.scan_interval is not None:
        with KNOWN_LOCK:
            if args.scan_interval <= 0:
                KNOWN["config"]["enabled"] = False
            else:
                KNOWN["config"].update(enabled=True, interval=_clamp_int(args.scan_interval, GUARD_MIN, GUARD_MAX, GUARD_DEFAULT))
    lhm_url = args.lhm_url if args.lhm_url is not None else (LHM_DEFAULT_URL if IS_WIN else "")
    HW_CFG.update(url=lhm_url or LHM_DEFAULT_URL, enabled=bool(lhm_url) and not args.no_lhm)
    gpu = GPUReader()
    STATE["slow"] = {"ifaces_meta": iface_meta()}

    domain = args.domain if args.hosts and not args.no_hosts else None
    token = configure_security(args.host, domain, args.token)

    server, port = None, None
    for p in ([args.port] if args.port else range(DEFAULT_PORT, DEFAULT_PORT + 10)):
        try:
            server, port = Server((args.host, p), Handler), p
            break
        except OSError:
            continue
    if not server:
        fatal("Gagal membuka port. Coba --port lain.")

    threads = [threading.Thread(target=sampler, args=(gpu,), daemon=True),
               threading.Thread(target=slow_loop, daemon=True),
               threading.Thread(target=wifi_loop, daemon=True),
               threading.Thread(target=guard_loop, daemon=True)]
    threads.append(threading.Thread(target=update_loop, daemon=True))
    if HW_CFG["enabled"]:
        threads.append(threading.Thread(target=hwmon_loop, daemon=True))
    if not args.no_public_ip:
        threads.append(threading.Thread(target=public_ip_loop, daemon=True))
    for t in threads:
        t.start()
    start_latency_monitors()
    notify_start()

    shown = FALLBACK_DOMAIN
    if domain:
        if ensure_hosts(domain):
            shown = domain
        else:
            say(f"Info: nama '{domain}' belum terdaftar (butuh hak Administrator sekali saja). "
                f"Atau tambahkan manual ke {HOSTS_PATH}:   127.0.0.1    {domain}")
    suffix = "" if port == 80 else f":{port}"
    qs = f"/?token={token}" if token else ""
    url = f"http://{shown}{suffix}{qs}"
    write_instance_url(url)

    say(f"{APP_NAME} {APP_VERSION} jalan di {url}  (GPU mode: {gpu.mode or 'tidak ada'})  -- Ctrl+C untuk berhenti")
    if SEC["lan"]:
        lip = local_ip() or "IP-PC-ini"
        say(f"LAN: http://{lip}{suffix}/?token={token}   (token wajib; jangan bagikan tautan ini ke sembarang orang)")
    if not args.no_browser and not args.background:
        threading.Timer(1.2, lambda: open_ui(url, not args.tab)).start()
    try:
        if want_tray:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            run_tray(url)  # blok sampai "Keluar" dipilih dari menu tray
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if want_tray:
            server.shutdown()
        server.server_close()
        USAGE.save()
        save_known()
        say(f"Berhenti. Data pemakaian tersimpan di {USAGE_FILE}")


if __name__ == "__main__":
    main()
