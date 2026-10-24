"""Gemeinsame Helfer für Abfragen (Entfernung, Zeitraum, Blöcke, Landeplätze)."""

import json
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import timefmt


def _dist_fn(c):
    """Entfernung (Ly) vom aktuellen System (letztes Journal-System) zu einem System; None wenn Koordinaten unbekannt."""
    pos = {r["system"]: (r["x"], r["y"], r["z"]) for r in c.execute("SELECT system, x, y, z FROM syspos")}
    cur = c.execute("SELECT sys FROM jc WHERE sys != '' ORDER BY last DESC LIMIT 1").fetchone()
    a = pos.get(cur["sys"]) if cur else None

    def f(system):
        b = pos.get(system)
        if a is None or b is None:
            return None
        return sum((u - v) ** 2 for u, v in zip(a, b)) ** 0.5
    return f


def _in_range(dist, lim):
    """lim 0 = unbegrenzt (auch Orte mit unbekannter Entfernung); sonst nur bekannte Entfernungen innerhalb lim."""
    return not lim or (dist is not None and dist <= lim)


def _cutoff(days):
    d = int(days or 0)
    return (datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ") if d > 0 else ""


SHIP_PAD = {  # Landeplatz-Bedarf: 1 = klein, 2 = mittel, 3 = gross (Spielwissen, nicht aus Dateien)
    "sidewinder": 1, "eagle": 1, "empire_eagle": 1, "imperial_eagle": 1, "viper": 1, "viper_mkiv": 1, "cobramkiii": 1, "cobramkiv": 1,
    "cobramkv": 1, "adder": 1, "hauler": 1, "vulture": 1, "dolphin": 1, "empire_courier": 1, "diamondback": 1, "diamondbackxl": 1,
    "independant_trader": 2, "asp": 2, "asp_scout": 2, "federation_dropship": 2, "federation_dropship_mkii": 2, "federation_gunship": 2,
    "type6": 2, "typex": 2, "typex_2": 2, "typex_3": 2, "python": 2, "python_nx": 2, "krait_mkii": 2, "krait_light": 2, "mamba": 2,
    "ferdelance": 2, "mandalay": 2, "type7": 3, "type8": 3, "type9": 3, "type9_military": 3, "federation_corvette": 3, "empire_trader": 3,
    "cutter": 3, "anaconda": 3, "belugaliner": 3, "orca": 3, "explorer_nx": 3, "smallcombat01_nx": 1, "panthermkii": 3, "corsair": 2,
}
def _ship_need(code):
    code = str(code or "").lower()
    if code in SHIP_PAD:
        return SHIP_PAD[code]
    if code.startswith("anaconda"):  # Anaconda Mk II: laut Nutzer grosser Landeplatz
        return 3
    return 0


PAD_NAME = {1: "Klein", 2: "Mittel", 3: "Groß"}


def _pad_fits(need, pd):
    """pd = (s, m, l) oder None (unbekannt). Rueckgabe True/False/None(unbekannt)."""
    if pd is None or not need:
        return None
    s_, m_, l_ = (pd[0] or 0), (pd[1] or 0), (pd[2] or 0)
    return (l_ > 0) if need == 3 else (m_ + l_ > 0) if need == 2 else (s_ + m_ + l_ > 0)


def _cur_loadout(c):
    r = c.execute("SELECT js FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC LIMIT 1").fetchone()
    return json.loads(r["js"]) if r else {}


def _posmap(c):
    pos = {r["system"]: (r["x"], r["y"], r["z"]) for r in c.execute("SELECT system, x, y, z FROM syspos")}
    cur = c.execute("SELECT sys FROM jc WHERE sys != '' ORDER BY last DESC LIMIT 1").fetchone()
    return pos, (pos.get(cur["sys"]) if cur else None), (cur["sys"] if cur else "")


def _d3(a, b):
    return None if a is None or b is None else sum((u - v) ** 2 for u, v in zip(a, b)) ** 0.5


def _num_range(v):
    try:
        return max(0.0, float(v or 0))
    except (TypeError, ValueError):
        return 0.0


def _best(rows, exclude=None, lim=0, dfn=None):
    """Pro Ware: guenstigster Einkauf (Bestand>0) und hoechster Verkauf (Nachfrage>0) ueber alle gespeicherten Stationen."""
    out = {}
    for r in rows:
        if exclude is not None and str(r["market_id"]) == str(exclude):
            continue
        o = out.setdefault(r["name"], {"buy": None, "sell": None})
        dd = dfn(r["system"]) if dfn else None
        if not _in_range(dd, lim):
            continue
        if r["buy"] > 0 and r["stock"] > 0 and (not o["buy"] or r["buy"] < o["buy"]["price"]):
            o["buy"] = {"price": r["buy"], "qty": r["stock"], "station": r["station"], "system": r["system"],
                        "seen": r["seen"], "market_id": r["market_id"], "dist": dd}
        if r["sell"] > 0 and r["demand"] > 0 and (not o["sell"] or r["sell"] > o["sell"]["price"]):
            o["sell"] = {"price": r["sell"], "qty": r["demand"], "station": r["station"], "system": r["system"],
                         "seen": r["seen"], "market_id": r["market_id"], "dist": dd}
    return out


# ---------------------------------------------------------------------------
# Karriere-API: liefert generische Bloecke {title, cols[[label,typ]], rows, note} fuer die Tabellen-Oberflaeche
# Typen: t=Text, n=Zahl, cr=Credits, p=Prozent, d=Datum/Zeit, h=Stunden, s=Sekunden/Dauer, r=Zahl mit 1 Nachkomme
# ---------------------------------------------------------------------------
def _lts(ts):
    return timefmt.parse_ts(ts).astimezone()


def _block(title, cols, rows, note="", sort=None):
    return {"title": title, "cols": cols, "rows": rows, "note": note, "sort": sort}


def _jload(c, key):
    r = c.execute("SELECT ts, js FROM snapkv WHERE k=?", (key,)).fetchone()
    return (r["ts"], json.loads(r["js"])) if r else (None, None)


def _active(c, cut):
    """Aktive Zeit: Zehn-Minuten-Raster, in dem das Journal Ereignisse hatte."""
    q = "SELECT b FROM act" + (" WHERE b >= ?" if cut else "")
    return [r["b"] for r in c.execute(q, ((cut[:15],) if cut else ()))]


def _bdt(b):
    return timefmt.parse_ts(b + "0:00Z").astimezone()
