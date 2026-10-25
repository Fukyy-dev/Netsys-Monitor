# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller --noconfirm --clean packaging/netsys_monitor.spec
# Ganti ONEFILE ke False untuk mode --onedir (startup lebih cepat, lebih jarang kena false-positive antivirus).
from pathlib import Path

ONEFILE = True
root = Path(SPECPATH).parent
icon = root / "netsys.ico"

a = Analysis(
    [str(root / "packaging" / "run_netsys.py")],
    pathex=[str(root)],
    datas=[(str(root / "netsys_monitor" / "static"), "netsys_monitor/static")],
    hiddenimports=["pystray._win32", "pynvml", "speedtest"],
    excludes=["tkinter", "unittest", "pydoc"],
)
pyz = PYZ(a.pure)
if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="NetsysMonitor", console=False, upx=False,
              icon=str(icon) if icon.exists() else None)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NetsysMonitor", console=False, upx=False,
              icon=str(icon) if icon.exists() else None)
    coll = COLLECT(exe, a.binaries, a.datas, name="NetsysMonitor")
