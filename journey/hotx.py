"""Manuell ausgeblendete Ring-Hotspots."""

import sqlite3
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import database


def _hotx_load(c):
    """{ring: {mineral oder '*': ts}} der manuell ausgeblendeten Ring-Funde."""
    d = {}
    for r in c.execute("SELECT ring, mineral, ts FROM hotx"):
        d.setdefault(r[0], {})[r[1]] = r[2]
    return d


def _hotx_hidden(hx, ring, names, ts):
    """True, wenn ein Fund (Ring, Mineralnamen) vor dem Loeschzeitpunkt erfasst wurde und ausgeblendet ist."""
    m = hx.get(ring)
    if not m:
        return False
    for k in ("*",) + tuple(n for n in names if n):
        t = m.get(k)
        if t and (not ts or ts <= t):
            return True
    return False


def hotx_api(body=None):
    c = database._mdb()
    c.row_factory = sqlite3.Row
    try:
        if body:
            ring = str(body.get("ring", "")).strip()[:200]
            op = body.get("op")
            names = [str(n)[:120] for n in (body.get("minerals") or []) if n]
            if not ring or op not in ("del", "restore") or (not names and not body.get("all")):
                return {"error": "ungueltig"}
            keys = ["*"] if body.get("all") else names
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for k in keys:
                if op == "del":
                    c.execute("INSERT OR REPLACE INTO hotx VALUES(?,?,?)", (ring, k, now))
                else:
                    c.execute("DELETE FROM hotx WHERE ring=? AND mineral=?", (ring, k))
            if op == "restore" and body.get("all"):
                c.execute("DELETE FROM hotx WHERE ring=?", (ring,))
            c.commit()
        return {"hidden": [dict(r) for r in c.execute("SELECT ring, mineral, ts FROM hotx ORDER BY ts DESC")]}
    finally:
        c.close()
