"""Ikon system tray."""
from __future__ import annotations

import logging
import os
import threading

from .appctl import TRAY, autostart_state, get_setting, set_autostart, set_setting
from .config import ALERTS, APP_NAME, DATA_DIR, IS_WIN, LAT, LOCK, SCAN, STATE
from .devices import run_scan
from .launcher import open_ui
from .notify import set_desktop_handler

log = logging.getLogger("netsys")


def make_tray_image(state="ok", size=64):
    """Logo Netsys (sama dengan di banner) + titik status: kuning = peringatan, merah = kritis."""
    from PIL import Image, ImageDraw
    S = 256
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, S - 8, S - 8), radius=64, fill=(15, 23, 42, 255), outline=(255, 255, 255, 70), width=4)
    pts = [(48, 168), (88, 112), (120, 144), (160, 80), (208, 152)]
    d.line(pts, fill=(56, 189, 248, 255), width=22, joint="curve")
    for x, y in pts[:1]:
        d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(56, 189, 248, 255))
    d.ellipse((190, 134, 226, 170), fill=(244, 114, 182, 255))
    if state in ("warn", "crit"):
        col = (239, 68, 68, 255) if state == "crit" else (245, 158, 11, 255)
        d.ellipse((150, 150, 246, 246), fill=col, outline=(255, 255, 255, 255), width=8)
    if size != S:
        img = img.resize((size, size), getattr(Image, "Resampling", Image).LANCZOS)
    return img


def make_ico(path):
    img = make_tray_image("ok", 256)
    img.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def tray_available():
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


def live_summary():
    """Ringkasan live untuk tooltip & menu tray."""
    L = STATE.get("latest") or {}
    try:
        s = f"CPU {L['cpu']['total']:.0f}% · RAM {L['mem']['percent']:.0f}%"
        ping = (LAT.get("Cloudflare") or {}).get("last")
        if ping is not None:
            s += f" · Ping {ping:.0f} ms"
        n = L.get("net") or {}
        if n:
            s += f" · ↓{n['down'] * 8 / 1e6:.1f} ↑{n['up'] * 8 / 1e6:.1f} Mbps"
        return s
    except Exception:
        return "Memuat data..."


def run_tray(url, on_quit_cb=None):
    """Ikon system tray. Klik kiri = fokus ke jendela dashboard yang sudah terbuka (atau buka bila belum ada).
    Blok sampai pengguna memilih Keluar."""
    import pystray
    from pystray import Menu
    from pystray import MenuItem as Item
    stop = threading.Event()
    status = [live_summary()]

    def on_open(icon, item):
        open_ui(url, True)

    def on_scan(icon, item):
        if not SCAN["running"]:
            threading.Thread(target=run_scan, daemon=True).start()

    def on_notify(icon, item):
        set_setting("notify", not get_setting("notify", True))

    def on_auto(icon, item):
        en, stale = autostart_state()
        ok, err = set_autostart((not en) or stale)
        if not ok:
            notify(icon, "Auto-start gagal", err)

    def on_data(icon, item):
        try:
            os.startfile(DATA_DIR)  # noqa: S606 - hanya Windows
        except Exception:
            pass

    def on_quit(icon, item):
        stop.set()
        icon.stop()

    def notify(icon, title, msg):
        try:
            icon.notify(str(msg)[:240], str(title)[:60])
        except Exception:
            pass

    menu = Menu(
        Item(lambda item: status[0], None, enabled=False),
        Menu.SEPARATOR,
        Item("Buka dashboard", on_open, default=True),
        Item("Pindai jaringan sekarang", on_scan),
        Menu.SEPARATOR,
        Item("Notifikasi peringatan", on_notify, checked=lambda item: bool(get_setting("notify", True))),
        Item("Mulai otomatis dengan Windows", on_auto, checked=lambda item: autostart_state()[0], visible=IS_WIN),
        Item("Buka folder data", on_data, visible=IS_WIN),
        Menu.SEPARATOR,
        Item("Keluar", on_quit))
    icon = pystray.Icon("NetsysMonitor", make_tray_image("ok"), APP_NAME, menu)

    def watcher(icon):
        icon.visible = True
        TRAY["active"] = True
        last_state = None
        set_desktop_handler(lambda title, msg: notify(icon, title, msg))
        while not stop.wait(2.0):
            try:
                with LOCK:
                    active = [(a["id"], a["level"], a["title"], a["value"], a["detail"]) for a in ALERTS.get("active", [])]
                state = "crit" if any(a[1] == "crit" for a in active) else "warn" if active else "ok"
                if state != last_state:
                    icon.icon, last_state = make_tray_image(state), state
                status[0] = live_summary()
                head = f"{len(active)} peringatan: {active[0][2]}" if active else "semua normal"
                icon.title = f"{APP_NAME} — {head}\n{status[0]}"[:120]
                try:
                    icon.update_menu()  # teks status di menu ikut diperbarui
                except Exception:
                    pass
            except Exception as e:
                log.exception("tray error: %s", e)

    try:
        icon.run(setup=watcher)
    finally:
        TRAY["active"] = False
        stop.set()
        if on_quit_cb:
            on_quit_cb()
