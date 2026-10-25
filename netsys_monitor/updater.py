"""Cek versi baru di GitHub Releases (opsional, mati secara default)."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request

from . import settings
from .config import APP_VERSION

log = logging.getLogger("netsys")
# Isi dengan "pemilik/repo" setelah repo dibuat, atau set variabel lingkungan NETSYS_REPO.
GITHUB_REPO = os.environ.get("NETSYS_REPO", "")
API_BASE = os.environ.get("NETSYS_API_BASE", "https://api.github.com")
UPDATE = {"checked": None, "available": False, "version": None, "url": None, "error": None, "configured": bool(GITHUB_REPO)}


def parse_version(v):
    nums = re.findall(r"\d+", str(v).split("-")[0])
    return tuple(int(x) for x in nums[:4]) + (0,) * max(0, 3 - len(nums))


def is_newer(remote, local=APP_VERSION):
    return parse_version(remote) > parse_version(local)


def check(repo=None):
    repo = repo or GITHUB_REPO
    UPDATE["configured"] = bool(repo)
    if not repo or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        UPDATE.update(error="Repo GitHub belum diatur", checked=time.time())
        return dict(UPDATE)
    try:
        req = urllib.request.Request(f"{API_BASE}/repos/{repo}/releases/latest",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "NetsysMonitor"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        tag = str(data.get("tag_name") or "")
        UPDATE.update(checked=time.time(), error=None, version=tag.lstrip("v"), url=data.get("html_url"),
                      available=bool(tag) and is_newer(tag))
    except Exception as e:
        UPDATE.update(checked=time.time(), error=f"{type(e).__name__}")
        log.info("cek update gagal: %s", e)
    return dict(UPDATE)


def update_loop():
    time.sleep(30)
    while True:
        if settings.get("update_check", default=False):
            check()
        time.sleep(6 * 3600)


def check_async():
    threading.Thread(target=check, daemon=True).start()
