"""Status.json: Modus und Warnflags."""

import json
import os
import time

from . import config, database


# ---------------------------------------------------------------------------
# Cockpit: Status.json / Cargo.json / NavRoute.json live lesen; Modus (Schiff/SRV/Fuss) mitschreiben
# ---------------------------------------------------------------------------
FLAG1 = {0: "Angedockt", 1: "Gelandet", 2: "Fahrwerk draußen", 3: "Schilde aktiv", 4: "Supercruise", 5: "Flugassistent aus",
         6: "Waffen ausgefahren", 7: "Im Wing", 8: "Lichter an", 9: "Frachtschaufel offen", 10: "Lautlos", 11: "Tankt (Scoop)",
         12: "SRV-Handbremse", 16: "Massenschatten", 17: "FSD lädt", 18: "FSD kühlt ab", 19: "Wenig Treibstoff",
         20: "Überhitzung", 22: "In Gefahr", 23: "Wird abgefangen", 30: "Hyperraumsprung"}
FLAG2 = {0: "Zu Fuß", 1: "Im Taxi", 2: "Mehrbesatzung", 3: "Zu Fuß in Station", 4: "Zu Fuß auf Planet", 6: "Wenig Sauerstoff",
         7: "Wenig Gesundheit", 8: "Kalt", 9: "Heiß", 10: "Sehr kalt", 11: "Sehr heiß", 12: "Gleitflug"}
FLAG_WARN = {("1", 19), ("1", 20), ("1", 22), ("1", 23), ("2", 6), ("2", 7), ("2", 10), ("2", 11)}
SCOOPABLE = set("OBAFGKM")
_STW = {"mt": 0, "last": None, "wrote": 0.0}


def _read_json_file(path):
    for _ in range(3):
        try:
            with open(path, encoding="utf-8-sig") as f:
                txt = f.read()
            return json.loads(txt) if txt.strip() else None
        except ValueError:
            time.sleep(0.05)  # Spiel schreibt gerade
        except OSError:
            return None
    return None


def status_mode(st):
    f, f2 = st.get("Flags", 0) or 0, st.get("Flags2", 0) or 0
    if f2 & 1:
        return "foot"
    if f & (1 << 26):
        return "srv"
    if f & ((1 << 24) | (1 << 25)):
        return "ship"
    return None


def status_tick(directory):
    """Modus aus Status.json bei Aenderung (und als Herzschlag je Minute) festhalten - macht die Boden/Raum-Trennung exakt."""
    path = os.path.join(directory, "Status.json")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return
    if mt == _STW["mt"] and time.time() - _STW["wrote"] < 60:
        return
    _STW["mt"] = mt
    st = _read_json_file(path)
    if not st or not st.get("timestamp"):
        return
    m = status_mode(st)
    if not m or time.time() - mt > 300:
        return
    if m != _STW["last"] or time.time() - _STW["wrote"] >= 60:
        c = database._mdb()
        try:
            c.execute("INSERT OR IGNORE INTO modelog VALUES(?,?)", (st["timestamp"], m))
            c.commit()
        finally:
            c.close()
        _STW["last"], _STW["wrote"] = m, time.time()


def status_worker():
    while True:
        try:
            d = config._journal_dir()
            if d:
                status_tick(d)
        except Exception:
            pass
        time.sleep(1)
