"""Captain's Log: fortlaufende Markdown-Datei aus den Journalen."""

import glob
import json
import os
import threading
import time

from . import bodydata, career_ingest, config, gallery, market_ingest, session, timefmt


LOG_STATE = {"error": None}
LOG_LOCK = threading.Lock()
MISSION_DE = {"delivery": "Lieferung", "courier": "Kurier", "massacre": "Massaker", "assassinate": "Attentat",
              "sightseeing": "Rundflug", "mining": "Bergbau", "collect": "Sammeln", "salvage": "Bergung",
              "passengervip": "VIP-Passagiere", "passengerbulk": "Passagiere", "altruism": "Hilfsmission",
              "rescue": "Rettung", "scan": "Scan", "hack": "Hack", "smuggle": "Schmuggel", "piracy": "Piraterie",
              "onfoot": "Zu Fuß", "disable": "Ausschalten", "longdistanceexpedition": "Expedition"}


def _lt(ev):
    return timefmt.parse_ts(ev["timestamp"]).astimezone().strftime("%H:%M")


def _elite_date(dt):
    """Datum im Elite-Universum (Jahr + 1286), Spielzeit = UTC."""
    return f"{('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')[dt.weekday()]} {dt.day:02d}.{dt.month:02d}.{dt.year + 1286}"

def _mtype(name):
    t = [x for x in (name or "").split("_") if x]
    if t and t[0].lower() == "mission":
        t = t[1:]
    k = t[0] if t else "?"
    return MISSION_DE.get(k.lower(), k)


def _mdetails(ev):
    p = []
    if ev.get("Count") and ev.get("Commodity_Localised"):
        p.append(f'{ev["Count"]}x {ev["Commodity_Localised"]}')
    if ev.get("KillCount"):
        p.append(f'{ev["KillCount"]} Abschüsse' + (f' ({ev["TargetFaction"]})' if ev.get("TargetFaction") else ""))
    if ev.get("PassengerCount"):
        p.append(f'{ev["PassengerCount"]} Passagiere')
    dst = " / ".join(x for x in (ev.get("DestinationSystem"), ev.get("DestinationStation")) if x)
    if dst:
        p.append("Ziel: " + dst)
    return " | ".join(p)


def _new_acc():
    return {"hdr": False, "done": False, "ended": False, "start": None, "last": None, "cmdr": "", "body": "",
            "systems": [], "jumps": 0, "dist": 0.0, "stations": [], "docks": 0, "landed": [], "landings": 0,
            "m": {"acc": 0, "ok": 0, "fail": 0, "abn": 0}, "mt": {}, "cats": {}}


def _add(lst, x):
    if x and x not in lst:
        lst.append(x)


def _log_event(ev, a, out, jname):
    e, ts = ev.get("event"), ev.get("timestamp")
    if not ts:
        return
    a["last"] = ts
    L = lambda t: out.append(f"- {_lt(ev)} {t}")
    if e == "LoadGame" and not a["hdr"]:
        a.update(hdr=True, start=ts, cmdr=ev.get("Commander", ""))
        dt = timefmt.parse_ts(ts).astimezone()
        out.append(f"\n## Sternzeit {_elite_date(timefmt.parse_ts(ts))} | {dt:%d.%m.%Y %H:%M} | CMDR {a['cmdr']} | {jname}")
        L(f"Spiel geladen mit {ev.get('Ship_Localised') or ev.get('Ship', '?')}, Kontostand {timefmt._nf(ev.get('Credits', 0))} Cr")
        return
    if not a["hdr"]:
        return
    bodydata._db_feed(ev, a)
    if e in ("FSDJump", "CarrierJump", "Location"):
        sysn = ev.get("StarSystem", "?")
        _add(a["systems"], sysn)
        a["sysname"] = sysn
        a["body"] = ev.get("Body", "") if e == "Location" else ""
        if e == "FSDJump":
            a["jumps"] += 1
            a["dist"] += ev.get("JumpDist", 0) or 0
            L(f"Sprung nach {sysn} ({timefmt._nf(ev.get('JumpDist', 0), 1)} Ly)")
        elif e == "CarrierJump":
            L(f"Flottenträger-Sprung nach {sysn}")
        else:
            L(f"Position: {sysn}")
        if e != "FSDJump" and ev.get("Docked") and ev.get("StationName"):
            _add(a["stations"], f"{ev['StationName']} ({sysn})")
    elif e == "Docked":
        a["docks"] += 1
        st, sysn = ev.get("StationName", "?"), ev.get("StarSystem", "?")
        _add(a["stations"], f"{st} ({sysn})")
        typ = ev.get("StationType_Localised") or ev.get("StationType") or ""
        L(f"Angedockt: {st}{' (' + typ + ')' if typ else ''} in {sysn}")
    elif e == "ApproachBody" or (e == "SupercruiseExit" and ev.get("BodyType") == "Planet"):
        a["body"] = ev.get("Body") or a["body"]
    elif e == "Touchdown":
        a["landings"] += 1
        b = a["body"] or "unbekanntem Körper"
        _add(a["landed"], b)
        L(f"Gelandet auf {b}" + (f" ({ev['Latitude']:.2f}, {ev['Longitude']:.2f})" if "Latitude" in ev else ""))
    elif e == "MissionAccepted":
        t = _mtype(ev.get("Name"))
        a["m"]["acc"] += 1
        a["mt"][t] = a["mt"].get(t, 0) + 1
        d = _mdetails(ev)
        L(f"Mission angenommen [{t}]: {ev.get('LocalisedName', '?')} für {ev.get('Faction', '?')}" + (f" | {d}" if d else "")
          + (f" | Belohnung {timefmt._nf(ev['Reward'])} Cr" if ev.get("Reward") else ""))
    elif e == "MissionCompleted":
        a["m"]["ok"] += 1
        d = _mdetails(ev)
        L(f"Mission abgeschlossen [{_mtype(ev.get('Name'))}]: {ev.get('LocalisedName', '?')}" + (f" | {d}" if d else "")
          + f" | +{timefmt._nf(ev.get('Reward', 0))} Cr")
    elif e == "MissionFailed":
        a["m"]["fail"] += 1
        L(f"Mission gescheitert: {ev.get('LocalisedName', '?')}")
    elif e == "MissionAbandoned":
        a["m"]["abn"] += 1
        L(f"Mission aufgegeben: {ev.get('LocalisedName', '?')}")
    elif e == "Scan" and bodydata.RING_RE.search(ev.get("BodyName", "")):
        k = "ring:" + ev["BodyName"]
        if k not in a.setdefault("sig", {}):
            a["sig"][k] = 1
            cl, res = bodydata._known_ring_cls(a, ev["BodyName"]), bodydata._reserve(ev.get("ReserveLevel"))
            L(f"Ring gescannt: {ev['BodyName']} - {cl or 'Ring'}" + (f", Reserven {res}" if res else "") + f" | System: {a.get('sysname', '?')}")
    elif e == "Scan" and "PlanetClass" in ev and "Belt Cluster" not in ev.get("BodyName", ""):
        a["pl"] = a.get("pl", 0) + 1
        fl = [x for x in (bodydata._pclass(ev["PlanetClass"]), "landbar" if ev.get("Landable") else "",
                          "terraformbar" if ev.get("TerraformState") else "",
                          f"{len(ev['Rings'])} Ring(e)" if ev.get("Rings") else "",
                          "Erstentdeckung" if ev.get("WasDiscovered") is False else "",
                          "Footfall frei" if ev.get("Landable") and ev.get("WasFootfalled") is False else "") if x]
        L(f"Planet gescannt: {ev.get('BodyName', '?')} - " + ", ".join(fl) + f" | System: {a.get('sysname', '?')}")
    elif e in ("FSSBodySignals", "SAASignalsFound"):
        nm, lst = ev.get("BodyName", "?"), ev.get("Signals") or []
        sysx = f" | System: {a.get('sysname', '?')}"
        if bodydata.RING_RE.search(nm):
            cnt, cl = bodydata.site_counts(lst), bodydata._known_ring_cls(a, nm)
            txt = (f"Hotspots {nm}" + (f" ({cl})" if cl else "") + ": " + ", ".join(f"{k} x{v}" for k, v in cnt.items()) + sysx) if cnt else ""
            vals = [0, 0, sum(cnt.values()), 0]
        else:
            c = bodydata.sig_counts(lst)
            parts = [f"{lab} {c[k]}" for k, lab in (("bio", "Bio"), ("geo", "Geologisch"), ("mining", "Abbaustandorte"),
                                                   ("human", "Mensch"), ("other", "Andere")) if c[k]]
            txt = (f"Signale auf {nm}: " + ", ".join(parts) + sysx) if parts else ""
            vals = [c["bio"], c["geo"], 0, c["mining"]]
        if txt and a.setdefault("sig", {}).get(nm) != txt:
            a["sig"][nm] = txt
            a.setdefault("bgs", {})[nm] = vals
            L(txt)
    elif e == "FactionKillBond":
        a["kills"] = a.get("kills", 0) + 1
        a["kcr"] = a.get("kcr", 0) + (ev.get("Reward", 0) or 0)
        L(f"Abschuss (Kampfbond): {ev.get('VictimFaction', '?')} | +{timefmt._nf(ev.get('Reward', 0))} Cr von {ev.get('AwardingFaction', '?')}"
          f" | System: {a.get('sysname', '?')}")
    elif e == "Bounty":
        tot = ev.get("TotalReward", ev.get("Reward", 0)) or 0
        a["kills"] = a.get("kills", 0) + 1
        a["kcr"] = a.get("kcr", 0) + tot
        L(f"Abschuss (Kopfgeld): {ev.get('Target_Localised') or ev.get('Target', '?')} von {ev.get('VictimFaction', '?')} | +{timefmt._nf(tot)} Cr"
          f" | System: {a.get('sysname', '?')}")
    elif e == "PowerplayMerits":
        a["merits"] = a.get("merits", 0) + (ev.get("MeritsGained", 0) or 0)
    elif e == "Promotion":
        for cat in career_ingest.RANKS:
            if cat in ev:
                L(f"Beförderung ({career_ingest.RANK_DE.get(cat, cat)}): {career_ingest.rank_name(cat, ev[cat])}")
    elif e == "ShipyardSwap":
        L(f"Schiffswechsel: {career_ingest.ship_name(ev, 'ShipType')}")
    elif e == "CommitCrime":
        a["crimes"] = a.get("crimes", 0) + 1
        amt = ev.get("Fine", ev.get("Bounty", 0)) or 0
        L(f"Verbrechen: {ev.get('CrimeType', '?')}" + (f" gegen {ev['Faction']}" if ev.get("Faction") else "")
          + (f" | Strafe {timefmt._nf(amt)} Cr" if amt else "") + f" | System: {a.get('sysname', '?')}")
    elif e == "Interdicted":
        a["intd"] = a.get("intd", 0) + 1
        L(f"Abgefangen von {ev.get('Interdictor_Localised') or ev.get('Interdictor', '?')} ({'ergeben' if ev.get('Submitted') else 'Kampf'})")
    elif e == "Died":
        a["deaths"] = a.get("deaths", 0) + 1
        ks = ev.get("Killers") or []
        by = ", ".join(f"{k.get('Name', '?')} ({k.get('Ship', '?')})" for k in ks) or ev.get("KillerName_Localised") or ""
        L("Schiff zerstört" + (f" von {by}" if by else "") + f" | System: {a.get('sysname', '?')}")
    elif e == "Shutdown":
        L("Spiel beendet")
        a["ended"] = True
    for cat, amt in session.credit_changes(ev):
        if not amt:
            continue
        a["cats"][cat] = a["cats"].get(cat, 0) + amt
        if amt > 0 and e != "MissionCompleted":
            extra = f" - {ev.get('Count', 0)} t {ev.get('Type_Localised') or ev.get('Type', '')}" if e == "MarketSell" else ""
            L(f"Einnahme ({cat}): +{timefmt._nf(amt)} Cr{extra}")


def _summary(a):
    inc = sum(v for v in a["cats"].values() if v > 0)
    exp = sum(v for v in a["cats"].values() if v < 0)
    net = inc + exp
    sy, m = a["systems"], a["m"]
    shown = ", ".join(sy[:40]) + (f" (+{len(sy) - 40} weitere)" if len(sy) > 40 else "")
    mt = ", ".join(f"{k} x{v}" for k, v in sorted(a["mt"].items(), key=lambda kv: -kv[1]))
    cats = ", ".join(f"{k} {'+' if v > 0 else ''}{timefmt._nf(v)}" for k, v in sorted(a["cats"].items(), key=lambda kv: -kv[1]))
    return ["### Zusammenfassung der Session",
            f"- Dauer: {timefmt.fmt_dur(timefmt.parse_ts(a['last']) - timefmt.parse_ts(a['start']))}",
            f"- Systeme besucht ({len(sy)}): {shown or '-'}",
            f"- Sprünge: {a['jumps']} | Strecke: {timefmt._nf(a['dist'], 1)} Ly",
            f"- Stationen angedockt ({a['docks']}): {', '.join(a['stations']) or '-'}",
            f"- Landungen ({a['landings']}): {', '.join(a['landed']) or '-'}",
            f"- Missionen: {m['acc']} angenommen, {m['ok']} abgeschlossen, {m['fail']} gescheitert, {m['abn']} aufgegeben"
            + (f" | Arten: {mt}" if mt else ""),
            f"- Credits: Einnahmen {timefmt._nf(inc)} Cr | Ausgaben {timefmt._nf(abs(exp))} Cr | Netto {'+' if net > 0 else ''}{timefmt._nf(net)} Cr",
            f"- Exploration: {a.get('pl', 0)} Planeten gescannt | Biosignale {sum(v[0] for v in a.get('bgs', {}).values())}"
            f" | Geosignale {sum(v[1] for v in a.get('bgs', {}).values())} | Ring-Hotspots {sum(v[2] for v in a.get('bgs', {}).values())}"
            f" | Oberflächen-Abbaustandorte {sum(v[3] for v in a.get('bgs', {}).values() if len(v) > 3)}",
            f"- Kampf: {a.get('kills', 0)} Abschüsse ({timefmt._nf(a.get('kcr', 0))} Cr Belohnungen) | {a.get('deaths', 0)} Tode"
            f" | {a.get('intd', 0)} Abfangmanöver | {a.get('crimes', 0)} Verbrechen | Powerplay-Merits {timefmt._nf(a.get('merits', 0))}",
            f"- Nach Kategorie: {cats or '-'}", ""]


def process_journals():
    bodydata.BODYDB = bodydata.load_db()
    path = config.CONFIG["log"]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    st_path = path + ".state.json"
    try:
        with open(st_path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {"journals": {}}
    js = state["journals"]
    if config.CONFIG["file"]:
        files = [config.CONFIG["file"]]
    else:
        d = config.find_journal_dir(config.CONFIG["dir"])
        files = sorted(glob.glob(os.path.join(d, "Journal*.log")), key=os.path.getmtime) if d else []
    if not js and len(files) > 1 + config.CONFIG["backfill"]:  # erster Start: aeltere Journale nicht nachtragen
        for f in files[:-(1 + config.CONFIG["backfill"])]:
            js[os.path.basename(f)] = {"offset": os.path.getsize(f), "skip": True}
    # Aeltere, fuer das Captain's Log uebersprungene Journale: nur die Koerper-/Scan-Daten einmalig uebernehmen
    bf = state.setdefault("bf", {})
    bf_new = False
    for f in files:
        name = os.path.basename(f)
        if js.get(name, {}).get("skip") and name not in bf:
            a0 = {"addr": None}
            with open(f, "rb") as fh:
                for line in fh:
                    if b'"event"' not in line or not line.endswith(b"\n"):
                        continue
                    if not any(k in line for k in (b"FSDJump", b"CarrierJump", b"Location", b"Scan", b"FSS", b"SAA")):
                        continue
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if ev.get("event") in ("FSDJump", "CarrierJump", "Location") + bodydata.BODY_EVENTS:
                        bodydata._db_feed(ev, a0)
            bf[name] = 1
            bf_new = True
    out = []
    progressed = False
    for idx, f in enumerate(files):
        name = os.path.basename(f)
        j = js.setdefault(name, {"offset": 0, "acc": _new_acc()})
        if j.get("skip"):
            continue
        a, size = j["acc"], os.path.getsize(f)
        if size > j["offset"]:
            with open(f, "rb") as fh:
                fh.seek(j["offset"])
                data = fh.read(size - j["offset"])
            cut = data.rfind(b"\n")
            if cut >= 0:  # nur vollstaendige Zeilen verarbeiten
                progressed = True
                j["offset"] += cut + 1
                for line in data[:cut + 1].decode("utf-8", "replace").splitlines():
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    _log_event(ev, a, out, name)
        if a["hdr"] and not a["done"] and (a["ended"] or idx < len(files) - 1):
            out += _summary(a)
            a["done"] = True
    if out:
        new = not os.path.exists(path) or os.path.getsize(path) == 0
        with open(path, "a", encoding="utf-8") as fh:
            if new:
                fh.write("# Captain's Log\n")
            fh.write("\n".join(out) + "\n")
    if out or bf_new or progressed:  # auch Scan-Ereignisse ohne Log-Zeile (z.B. DSS-Kartierung) sichern
        bodydata.save_db(bodydata.BODYDB)
    tmp = st_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, st_path)


def log_worker():
    while True:
        try:
            with LOG_LOCK:
                process_journals()
            LOG_STATE["error"] = None
        except Exception as exc:
            LOG_STATE["error"] = str(exc)
        try:
            market_ingest.ingest_market(config._journal_dir())
        except Exception as exc:
            LOG_STATE["error"] = f"Markt: {exc}"
        try:
            gallery.scan()
        except Exception as exc:
            LOG_STATE["error"] = f"Galerie: {exc}"
        time.sleep(4)
