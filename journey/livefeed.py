"""Live-Daten für die Oberfläche (/api/stats) und Sprachausgabe-Feed."""

import os
import time

from . import bodydata, config, session


def voice_feed(events):
    """Die letzten Ereignisse, die per Sprachausgabe gemeldet werden koennen (id = Zeit+Art+Name, damit nichts doppelt gesprochen wird)."""
    out = []
    for ev in events[-400:]:
        e = ev.get("event")
        ts = ev.get("timestamp", "")
        if e == "Scan" and bodydata.RING_RE.search(ev.get("BodyName", "")):
            out.append({"id": ts + e + ev.get("BodyName", ""), "k": "ring", "t": "Ring gescannt"})
        elif e == "SAAScanComplete":
            out.append({"id": ts + e + str(ev.get("BodyName", "")), "k": "mapped", "t": "Oberfläche kartiert"})
        elif e == "FSDJump":
            out.append({"id": ts + e + ev.get("StarSystem", ""), "k": "jump", "t": "Sprung nach " + ev.get("StarSystem", "") + " abgeschlossen"})
        elif e == "Docked":
            out.append({"id": ts + e + ev.get("StationName", ""), "k": "dock", "t": "Angedockt in " + ev.get("StationName", "")})
        elif e == "ScanOrganic" and ev.get("ScanType") == "Analyse":
            out.append({"id": ts + e + str(ev.get("Species", "")), "k": "bio", "t": "Biologische Probe analysiert"})
        elif e == "MissionCompleted":
            out.append({"id": ts + e + str(ev.get("MissionID", "")), "k": "mission", "t": "Mission abgeschlossen"})
        elif e == "MiningRefined" and False:
            pass
    return out[-12:]


def build_payload(window_min):
    if config.CONFIG["file"]:
        journal_path = config.CONFIG["file"]
        directory = os.path.dirname(os.path.abspath(journal_path))
    else:
        directory = config.find_journal_dir(config.CONFIG["dir"])
        if not directory or not os.path.isdir(directory):
            return {"error": "Journal-Ordner nicht gefunden. Unter Settings → Journal-Ordner den Pfad eintragen.", "jd": True}
        journal_path = config.latest_journal(directory)
    if not journal_path or not os.path.exists(journal_path):
        return {"error": "Keine Journal-Datei im Ordner " + str(directory) + " gefunden. Unter Settings → Journal-Ordner den richtigen Pfad eintragen.", "jd": True}

    events = session.read_events(journal_path)
    live = (time.time() - os.path.getmtime(journal_path)) < 600
    r = session.analyse(events, window_min, live)
    if r is None:
        return {"error": "Journal ist noch leer"}

    r["start_ts"] = r["start_ts"].isoformat()
    r["elapsed_s"] = r["elapsed"].total_seconds()
    for k in ("end_ts", "elapsed"):
        r.pop(k, None)
    r["live"] = live
    r["balance"] = session.read_status_balance(directory) if live else None
    r["journal"] = os.path.basename(journal_path)
    r["system"] = bodydata.current_system(events)
    r["bodies"] = bodydata.merged_bodies(events, r["system"])
    r["allstats"] = bodydata.all_stats(events)
    r["feed"] = voice_feed(events)
    return r
