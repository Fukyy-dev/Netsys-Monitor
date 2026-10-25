"""Pelacak pemakaian data jaringan."""
from __future__ import annotations

import csv
import io
import json
import os
import time
from datetime import timedelta

from .config import USAGE_FILE, wib_now


# --------------------------------------------------------------------------- usage tracker
class UsageTracker:
    def __init__(self, path):
        self.path = path
        self.data = {}
        self.last = None
        self.dirty = False
        self.last_save = 0
        self.session_sent = 0
        self.session_recv = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}
        cutoff = (wib_now().date() - timedelta(days=400)).isoformat()
        self.data = {k: v for k, v in self.data.items() if k >= cutoff}

    def update(self, sent, recv):
        if self.last is not None:
            ds, dr = sent - self.last[0], recv - self.last[1]
            if ds < 0:  # counter reset (adapter restart)
                ds = sent
            if dr < 0:
                dr = recv
            d = self.data.setdefault(wib_now().date().isoformat(), {"sent": 0, "recv": 0})
            d["sent"] += ds
            d["recv"] += dr
            self.session_sent += ds
            self.session_recv += dr
            self.dirty = True
        self.last = (sent, recv)
        if self.dirty and time.time() - self.last_save > 30:
            self.save()

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
            os.replace(tmp, self.path)
            self.dirty = False
            self.last_save = time.time()
        except Exception:
            pass

    def summary(self):
        today = wib_now().date()
        key = today.isoformat()
        month = key[:7]
        t = self.data.get(key, {"sent": 0, "recv": 0})
        ms = sum(v["sent"] for k, v in self.data.items() if k.startswith(month))
        mr = sum(v["recv"] for k, v in self.data.items() if k.startswith(month))
        days = []
        for i in range(6, -1, -1):
            d = (today - timedelta(days=i)).isoformat()
            v = self.data.get(d, {"sent": 0, "recv": 0})
            days.append({"d": d[5:], "sent": v["sent"], "recv": v["recv"]})
        return {
            "session": {"sent": self.session_sent, "recv": self.session_recv},
            "today": t, "month": {"sent": ms, "recv": mr}, "days": days,
            "since": min(self.data) if self.data else key,
        }

    def csv_text(self):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["date", "download_bytes", "upload_bytes", "download_MB", "upload_MB"])
        for k in sorted(self.data):
            v = self.data[k]
            w.writerow([k, int(v["recv"]), int(v["sent"]),
                        round(v["recv"] / 1e6, 2), round(v["sent"] / 1e6, 2)])
        return buf.getvalue()


USAGE = UsageTracker(USAGE_FILE)
