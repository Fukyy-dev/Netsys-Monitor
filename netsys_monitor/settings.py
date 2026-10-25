"""Pengaturan pengguna (settings.json di folder data): notifikasi, jam tenang, ambang peringatan, webhook, tema."""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import threading

from .alerts import TH
from .config import DATA_DIR

log = logging.getLogger("netsys")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
_LOCK = threading.RLock()
_DEFAULT_TH = {k: list(v) for k, v in TH.items()}
DEFAULTS = {
    "notify": True,
    "quiet": {"enabled": False, "start": "23:00", "end": "07:00"},
    "thresholds": _DEFAULT_TH,
    "theme": "auto",
    "webhook": {"enabled": False, "kind": "discord", "url": "", "token": "", "chat_id": "", "min_level": "crit"},
    "update_check": False,
    "idle_mode": True,
}
SECRET_KEYS = (("webhook", "url"), ("webhook", "token"))
MASK = "••••"
# (batas bawah, batas atas, lebih kecil = lebih buruk?)
TH_RULES = {"cpu": (1, 100, False), "ram": (1, 100, False), "disk": (1, 100, False), "gpu_temp": (30, 120, False),
            "cpu_temp": (30, 120, False), "loss": (0, 100, False), "latency": (10, 5000, False),
            "battery": (1, 100, True), "wifi": (1, 100, True)}
_S = copy.deepcopy(DEFAULTS)
_loaded = [False]


def _merge(base, patch):
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        elif k in base:
            base[k] = v
    return base


def apply_thresholds():
    for k, (w, c) in _S["thresholds"].items():
        if k in TH:
            TH[k] = (w, c)


def load():
    with _LOCK:
        _loaded[0] = True
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _merge(_S, validate(data, strict=False))
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning("settings.json tidak terbaca (%s); memakai default", e)
        apply_thresholds()


def save():
    with _LOCK:
        try:
            tmp = SETTINGS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_S, f, ensure_ascii=False, indent=1)
            os.replace(tmp, SETTINGS_FILE)
        except OSError as e:
            log.warning("gagal menyimpan settings: %s", e)


def _choice(opts, msg):
    def f(v):
        if v not in opts:
            raise ValueError(msg)
        return v
    return f


def _hhmm(v):
    if not isinstance(v, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
        raise ValueError("Jam harus berformat HH:MM (00:00-23:59)")
    return v


def _num(v, lo, hi, name):
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Nilai {name} harus angka")
    if not lo <= f <= hi:
        raise ValueError(f"Nilai {name} harus antara {lo} dan {hi}")
    return int(f) if f == int(f) else f


def validate(patch, strict=True):
    """Bersihkan & validasi potongan pengaturan. strict=False (saat memuat file): buang yang rusak, jangan error."""
    out = {}

    def put(path, fn):
        try:
            cur = out
            for p in path[:-1]:
                cur = cur.setdefault(p, {})
            src = patch
            for p in path:
                src = src[p]
            cur[path[-1]] = fn(src)
        except KeyError:
            pass
        except (ValueError, TypeError) as e:
            if strict:
                raise ValueError(str(e))

    put(("notify",), bool)
    put(("update_check",), bool)
    put(("idle_mode",), bool)
    put(("quiet", "enabled"), bool)
    put(("quiet", "start"), _hhmm)
    put(("quiet", "end"), _hhmm)
    put(("theme",), _choice(("auto", "light", "dark"), "Tema tidak dikenal"))
    put(("webhook", "enabled"), bool)
    put(("webhook", "kind"), _choice(("discord", "telegram", "generic"), "Jenis webhook tidak dikenal"))
    put(("webhook", "min_level"), _choice(("warn", "crit"), "Level minimum harus warn/crit"))
    put(("webhook", "chat_id"), lambda v: str(v).strip()[:64])

    def url(v):
        v = str(v).strip()
        if v and v != MASK and not re.match(r"^https?://[^\s]+$", v):
            raise ValueError("URL webhook harus diawali http:// atau https://")
        return v[:600]
    put(("webhook", "url"), url)
    put(("webhook", "token"), lambda v: str(v).strip()[:200])
    th = patch.get("thresholds") if isinstance(patch, dict) else None
    if isinstance(th, dict):
        for k, pair in th.items():
            if k not in TH_RULES:
                continue
            try:
                lo, hi, low_bad = TH_RULES[k]
                w, c = _num(pair[0], lo, hi, f"{k} (peringatan)"), _num(pair[1], lo, hi, f"{k} (kritis)")
                if (w > c) if not low_bad else (w < c):
                    raise ValueError(f"Ambang {k}: nilai kritis harus {'lebih kecil' if low_bad else 'lebih besar'} dari peringatan")
                out.setdefault("thresholds", {})[k] = [w, c]
            except (ValueError, TypeError, IndexError, KeyError) as e:
                if strict:
                    raise ValueError(str(e) if isinstance(e, ValueError) else f"Ambang {k} tidak valid")
    return out


def apply(patch):
    """Terapkan potongan pengaturan (sudah divalidasi). Nilai rahasia berisi MASK diabaikan."""
    clean = validate(patch)
    for sec, key in SECRET_KEYS:
        if clean.get(sec, {}).get(key) == MASK:
            del clean[sec][key]
    with _LOCK:
        _merge(_S, clean)
        apply_thresholds()
        save()
    return snapshot()


def reset_thresholds():
    with _LOCK:
        _S["thresholds"] = copy.deepcopy(_DEFAULT_TH)
        apply_thresholds()
        save()


def get(*path, default=None):
    with _LOCK:
        cur = _S
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return default
            cur = cur[p]
        return copy.deepcopy(cur)


def set_value(key, value):
    with _LOCK:
        _S[key] = value
        save()


def snapshot(reveal=False):
    """Salinan pengaturan; token/URL webhook disamarkan kecuali reveal=True (hanya internal)."""
    with _LOCK:
        s = copy.deepcopy(_S)
    if not reveal:
        for sec, key in SECRET_KEYS:
            if s[sec].get(key):
                s[sec][key] = MASK
    s["defaults"] = {"thresholds": _DEFAULT_TH}
    return s


load()
