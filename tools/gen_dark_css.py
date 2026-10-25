"""Hasilkan blok tema gelap di style.css dari aturan tema terang (warna hardcode -> padanan gelap).
Jalankan ulang setiap mengubah style.css:  python tools/gen_dark_css.py
Blok dibatasi penanda DARK-BEGIN/DARK-END dan dibangun ulang tiap kali (idempoten)."""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "netsys_monitor" / "static" / "style.css"
BEGIN, END = "/* DARK-BEGIN (dihasilkan tools/gen_dark_css.py, jangan diedit manual) */", "/* DARK-END */"
MAP = {
    "#fff": "var(--panel)", "#ffffff": "var(--panel)",
    "#f8fafd": "#16213a", "#f3f6fb": "#16213a", "#fbfcfe": "#16213a", "#eef2f8": "#1b2740", "#eef2f7": "#1f2b44",
    "#dbe3ef": "#2a3a5c", "#e4e9f1": "#1f2b44",
    "#e4f6ef": "rgba(52,211,153,.14)", "#fdf0dd": "rgba(245,158,11,.14)", "#fff7e8": "rgba(245,158,11,.12)",
    "#fde7e4": "rgba(239,68,68,.16)", "#fff1f0": "rgba(239,68,68,.14)", "#fff7f6": "rgba(239,68,68,.10)", "#fffafa": "rgba(239,68,68,.08)",
    "#ece7fd": "rgba(151,117,250,.18)", "#e3effd": "rgba(56,189,248,.16)",
    "#f6d9a8": "rgba(245,158,11,.38)", "#f5c2bd": "rgba(239,68,68,.42)", "#fcd34d": "rgba(245,158,11,.5)", "#fda4af": "rgba(239,68,68,.45)",
    "#3b4a66": "#c3d0e6", "#b42318": "#ff8a80", "#a35504": "#fbbf6a", "#07785a": "#6ee7b7", "#1a5fb4": "#7cc0ff",
    "#5b3ad1": "#b9a4ff", "#c77a07": "#fbbf24",
}
PROPS = re.compile(r"^\s*(background(?:-color)?|border(?:-[a-z]+)*|color|outline(?:-color)?|box-shadow|stroke|fill)\s*:", re.I)


def convert(decl):
    out = decl
    is_bg = decl.lstrip().lower().startswith("background")
    for k, v in MAP.items():
        if k in ("#fff", "#ffffff") and not is_bg:
            continue  # teks/garis putih ada di atas latar gelap (banner, tombol berwarna): jangan diubah
        out = re.sub(re.escape(k) + r"(?![0-9a-fA-F])", v, out, flags=re.I)
    return out


def main():
    css = CSS.read_text(encoding="utf-8")
    if BEGIN in css:
        css = css[: css.index(BEGIN)].rstrip() + "\n"
    rules = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel, body = m.group(1).strip(), m.group(2)
        sel = re.sub(r"/\*.*?\*/", "", sel, flags=re.S).strip()
        if not sel or sel.startswith("@") or re.fullmatch(r"(from|to|\d+%)(\s*,\s*(from|to|\d+%))*", sel):
            continue
        decls = [d.strip() for d in body.split(";") if d.strip()]
        changed = [convert(d) for d in decls if PROPS.match(d) and convert(d) != d]
        if changed:
            sels = ", ".join(f'html[data-theme="dark"] {s.strip()}' for s in sel.split(",") if s.strip())
            rules.append(f"{sels}{{{';'.join(changed)}}}")
    block = "\n".join([BEGIN] + rules + [END])
    CSS.write_text(css + "\n" + block + "\n", encoding="utf-8")
    print(f"{len(rules)} aturan gelap dihasilkan", file=sys.stderr)


if __name__ == "__main__":
    main()
