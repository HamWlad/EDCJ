"""System-, Körper- und Ring-Daten aus dem Journal (Diplomatie, Planeten & Ringe)."""

import json
import os
import re
import sqlite3

from . import config, database, hotx, timefmt


STATE_DE = {
    "None": "Keiner", "Boom": "Boom", "Bust": "Rezession", "CivilUnrest": "Unruhen",
    "CivilWar": "Bürgerkrieg", "Election": "Wahl", "Expansion": "Expansion",
    "Famine": "Hungersnot", "Investment": "Investition", "Lockdown": "Abriegelung",
    "Outbreak": "Seuche", "Retreat": "Rückzug", "War": "Krieg", "Drought": "Dürre",
    "Blight": "Pflanzenbefall", "Terrorism": "Terror", "NaturalDisaster": "Naturkatastrophe",
    "PirateAttack": "Piratenangriff", "PublicHoliday": "Feiertag", "InfrastructureFailure": "Infrastrukturausfall",
    "ColdWar": "Kalter Krieg", "TradeWar": "Handelskrieg", "Terrorism": "Terror",
}
ALLEG_DE = {"Federation": "Föderation", "Empire": "Imperium", "Alliance": "Allianz",
            "Independent": "Unabhängig", "Thargoid": "Thargoiden", "Guardian": "Wächter",
            "PlayerPilots": "Spieler", "": ""}
WAR_DE = {"war": "Krieg", "civilwar": "Bürgerkrieg", "election": "Wahl"}


def _state_list(items):
    return [STATE_DE.get(i.get("State"), i.get("State")) for i in (items or []) if i.get("State")]


def _loc(ev, key):
    """Bevorzugt die lokalisierte Variante eines Feldes, sonst den Rohwert ohne $...;"""
    v = ev.get(key + "_Localised") or ev.get(key) or ""
    return "" if str(v).startswith("$") else v


def _system_from(ev):
    sysfac = ev.get("SystemFaction") or {}
    controlling = sysfac.get("Name", "")
    factions = []
    for f in ev.get("Factions") or []:
        gov = f.get("Government_Localised") or f.get("Government") or ""
        factions.append({
            "name": f.get("Name", "?"),
            "state": STATE_DE.get(f.get("FactionState"), f.get("FactionState") or ""),
            "active": _state_list(f.get("ActiveStates")),
            "pending": _state_list(f.get("PendingStates")),
            "recovering": _state_list(f.get("RecoveringStates")),
            "influence": round((f.get("Influence") or 0) * 100, 1),
            "reputation": round(f.get("MyReputation") or 0),
            "government": "" if str(gov).startswith("$") else gov,
            "controlling": f.get("Name") == controlling,
        })
    factions.sort(key=lambda f: -f["influence"])

    conflicts = []
    for c in ev.get("Conflicts") or []:
        f1, f2 = c.get("Faction1") or {}, c.get("Faction2") or {}
        conflicts.append({
            "type": WAR_DE.get(c.get("WarType"), c.get("WarType") or ""),
            "status": c.get("Status") or "",
            "f1": f1.get("Name", "?"), "w1": f1.get("WonDays", 0),
            "f2": f2.get("Name", "?"), "w2": f2.get("WonDays", 0),
        })

    station = ev.get("StationName") if ev.get("Docked") else None
    allegiance = ev.get("SystemAllegiance", "")
    return {
        "name": ev.get("StarSystem", "?"),
        "addr": ev.get("SystemAddress"),
        "allegiance": ALLEG_DE.get(allegiance, allegiance),
        "government": _loc(ev, "SystemGovernment"),
        "economy": _loc(ev, "SystemEconomy"),
        "economy2": _loc(ev, "SystemSecondEconomy"),
        "security": _loc(ev, "SystemSecurity"),
        "population": ev.get("Population", 0),
        "controlling": controlling,
        "controlling_state": STATE_DE.get(sysfac.get("FactionState"), sysfac.get("FactionState") or ""),
        "power": ev.get("ControllingPower") or ", ".join(ev.get("Powers") or []),
        "station": station,
        "station_type": ev.get("StationType") if station else None,
        "factions": factions,
        "conflicts": conflicts,
        "as_of": ev.get("timestamp"),
    }


def current_system(events):
    """Letztes bekanntes System: Location / FSDJump / CarrierJump, Station per Docked/Undocked."""
    cur = None
    for ev in events:
        e = ev.get("event")
        if e in ("Location", "FSDJump", "CarrierJump"):
            cur = _system_from(ev)
        elif cur and e == "Docked":
            cur["station"], cur["station_type"] = ev.get("StationName"), ev.get("StationType")
        elif cur and e == "Undocked":
            cur["station"], cur["station_type"] = None, None
    return cur


PC_DE = {"Earthlike body": "Erdähnliche Welt", "Water world": "Wasserwelt", "Ammonia world": "Ammoniakwelt",
         "High metal content body": "Metallreich", "Metal rich body": "Metallreicher Körper",
         "Rocky body": "Felsig", "Icy body": "Eisig", "Rocky ice body": "Felsig-Eis",
         "Water giant": "Wasserriese", "Helium rich gas giant": "Heliumreicher Gasriese",
         "Gas giant with water based life": "Gasriese (Wasserleben)",
         "Gas giant with ammonia based life": "Gasriese (Ammoniakleben)"}


def _pclass(c):
    m = re.match(r"Sudarsky class (\w+) gas giant", c or "")
    return f"Gasriese Klasse {m.group(1)}" if m else PC_DE.get(c, c or "")


RC_DE = {"Metalic": "Metallisch", "MetalRich": "Metallreich", "Rocky": "Felsig", "Icy": "Eisig"}
RES_DE = {"Pristine": "Unberührt", "Major": "Reichhaltig", "Common": "Normal", "Low": "Gering", "Depleted": "Erschöpft"}
RING_RE = re.compile(r" [A-Z] (Ring|Belt)$")
BODY_EVENTS = ("FSSDiscoveryScan", "FSSAllBodiesFound", "Scan", "FSSBodySignals", "SAASignalsFound", "SAAScanComplete", "ScanOrganic")
BODYDB = {}
_DBC = {"mt": 0, "db": {}}


def _new_st(name):
    return {"bodies": {}, "sites": {}, "sysname": name, "total": None, "progress": 0, "all": False}


def sig_counts(lst):
    c = {"bio": 0, "geo": 0, "human": 0, "mining": 0, "other": 0}
    for x in lst or []:
        t = x.get("Type", "") + x.get("Type_Localised", "")
        k = ("mining" if "iningLocation" in t or "bbaustandort" in t else "bio" if "iolog" in t else
             "geo" if "eolog" in t else "human" if "uman" in t else "other")
        c[k] += x.get("Count", 0)
    return c

def site_counts(lst):
    return {(x.get("Type_Localised") or x.get("Type", "?")): x.get("Count", 0) for x in lst or []}


def _ring(st, name):
    return st.setdefault("rings", {}).setdefault(name, {"name": name, "cls": "", "reserve": "", "dist": None,
                                                         "scanned": False, "mapped": False, "hot": {}})


def _ring_cls(c):
    return RC_DE.get(str(c or "").replace("eRingClass_", ""), "")


def _reserve(v):
    r = re.sub("Resources$", "", v or "")
    return RES_DE.get(r, r)


def _known_ring_cls(a, name):
    return BODYDB.get(a.get("addr"), {}).get("st", {}).get("rings", {}).get(name, {}).get("cls", "")


def apply_body_event(st, ev):
    e, B, sysname = ev.get("event"), st["bodies"], st.get("sysname", "")
    nm = ev.get("BodyName", "")
    isring = bool(RING_RE.search(nm))

    def get():
        bid = ev.get("BodyID", ev.get("Body", ev.get("BodyName")))
        k = str(bid)
        if k not in B:
            B[k] = {"key": k, "id": bid if isinstance(bid, int) else 999, "full": nm,
                    "name": nm.replace(sysname, "").strip() or nm or "?", "cls": "", "star": False, "landable": False,
                    "disc": None, "mapped_before": None, "terra": False, "atmo": "", "grav": None, "dist": None,
                    "foot": None, "bio": 0, "geo": 0, "human": 0, "mining": 0, "other": 0, "mine": False, "organics": 0}
        return B[k]

    if e == "FSSDiscoveryScan":
        st.update(total=ev.get("BodyCount"), progress=ev.get("Progress", 0))
    elif e == "FSSAllBodiesFound":
        st["all"] = True
    elif e == "Scan" and isring:
        r = _ring(st, nm)
        r.update(scanned=True, dist=ev.get("DistanceFromArrivalLS"))
        r["cls"] = _ring_cls(ev.get("RingClass")) or r["cls"]
        r["reserve"] = _reserve(ev.get("ReserveLevel")) or r["reserve"]
    elif e == "Scan" and "Belt Cluster" not in nm:
        b = get()
        b["full"], b["name"] = nm, nm.replace(sysname, "").strip() or nm or "?"
        b["star"] = "StarType" in ev
        b["cls"] = "Stern " + ev["StarType"] if b["star"] else _pclass(ev.get("PlanetClass"))
        b.update(landable=bool(ev.get("Landable")), disc=ev.get("WasDiscovered"), mapped_before=ev.get("WasMapped"),
                 terra=bool(ev.get("TerraformState")), dist=ev.get("DistanceFromArrivalLS"), foot=ev.get("WasFootfalled"))
        b["atmo"] = ev.get("Atmosphere") or ev.get("AtmosphereType") or ""
        if ev.get("SurfaceGravity"):
            b["grav"] = round(ev["SurfaceGravity"] / 9.81, 2)
        for rr in ev.get("Rings") or []:
            r = _ring(st, rr.get("Name", ""))
            r["cls"] = _ring_cls(rr.get("RingClass")) or r["cls"]
    elif e in ("FSSBodySignals", "SAASignalsFound"):
        if isring:
            r_ = _ring(st, nm)
            if e == "SAASignalsFound" or not r_["hot"]:  # Detailscan ersetzt; FSS fuellt nur Luecken
                r_["hot"] = site_counts(ev.get("Signals"))
                r_["hot_ts"] = ev.get("timestamp", "")
        else:
            get().update(sig_counts(ev.get("Signals")))
    elif e == "SAAScanComplete":
        if isring:
            _ring(st, nm)["mapped"] = True
        else:
            get()["mine"] = True
    elif e == "ScanOrganic" and ev.get("ScanType") == "Analyse":
        get()["organics"] += 1

def body_list(st):
    bodies = [b for b in st["bodies"].values()
              if not (RING_RE.search(b.get("full", "")) or (not b["cls"] and RING_RE.search(b.get("name", ""))))]
    out = [dict(b, rings=[]) for b in sorted(bodies, key=lambda b: b["id"])]
    rings = dict(st.get("rings", {}))
    for rn, cnt in st.get("sites", {}).items():  # aeltere Datenbank-Eintraege
        rings.setdefault(rn, {"name": rn, "cls": "", "reserve": "", "dist": None, "scanned": False, "mapped": False, "hot": cnt})
    orph = {}
    for rn, r in sorted(rings.items()):
        parent = RING_RE.sub("", rn)
        for b in out:
            if b["full"] == parent:
                b["rings"].append(dict(r, n=rn[len(parent):].strip()))
                break
        else:  # Elternkoerper nie gescannt: Ring trotzdem unter dem richtigen Namen zeigen
            orph.setdefault(parent, []).append(dict(r, n=rn[len(parent):].strip(), orphan=True))
    sysn = st.get("sysname", "")
    for parent, rs in orph.items():
        out.append({"key": "p:" + parent, "id": 998, "full": parent, "name": parent.replace(sysn, "").strip() or parent, "cls": "", "star": False,
                    "landable": False, "disc": None, "mapped_before": None, "terra": False, "atmo": "", "grav": None, "dist": None,
                    "foot": None, "bio": 0, "geo": 0, "human": 0, "mining": 0, "other": 0, "mine": False, "organics": 0,
                    "rings": rs, "placeholder": True})
    return out

def system_bodies(events):
    st = _new_st("")
    for ev in events:
        if ev.get("event") in ("FSDJump", "CarrierJump", "Location"):
            st = _new_st(ev.get("StarSystem", ""))
        else:
            apply_body_event(st, ev)
    lst = body_list(st)
    return {"list": lst, "scanned": sum(1 for b in lst if b["cls"]), "total": st["total"], "progress": st["progress"], "all": st["all"]}


def _db_path():
    return config.CONFIG["log"] + ".bodies.json"


def load_db():
    try:
        with open(_db_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_db(db):
    tmp = _db_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f)
    os.replace(tmp, _db_path())


def _db_cached():
    try:
        mt = os.path.getmtime(_db_path())
    except OSError:
        return {}
    if mt != _DBC["mt"]:
        _DBC.update(mt=mt, db=load_db())
    return _DBC["db"]


def _db_feed(ev, a):
    e = ev.get("event")
    if e in ("FSDJump", "CarrierJump", "Location"):
        name = ev.get("StarSystem", "?")
        addr = a["addr"] = str(ev.get("SystemAddress") or name)
        ent = BODYDB.setdefault(addr, {"name": name, "visits": [], "st": _new_st(name)})
        if (e != "Location" or not ent["visits"]) and ev["timestamp"] not in ent["visits"]:
            ent["visits"] = (ent["visits"] + [ev["timestamp"]])[-30:]
    elif e in BODY_EVENTS:
        addr = str(ev.get("SystemAddress") or a.get("addr") or "")
        if addr in BODYDB:
            apply_body_event(BODYDB[addr]["st"], ev)


def _merge_ring(o, n):
    m = dict(o or {}, **(n or {}))
    for f in ("cls", "reserve"):
        m[f] = (n or {}).get(f) or (o or {}).get(f, "")
    m["hot"] = dict((n or {}).get("hot") or (o or {}).get("hot", {}))  # neuer Scan ersetzt die alten Funde komplett
    m["hot_ts"] = (n or {}).get("hot_ts") if (n or {}).get("hot") else (o or {}).get("hot_ts")
    for f in ("scanned", "mapped"):
        m[f] = bool((o or {}).get(f) or (n or {}).get(f))
    return m


def merged_bodies(events, sysinfo):
    live = system_bodies(events)
    addr = str((sysinfo or {}).get("addr") or "")
    ent = _db_cached().get(addr) if addr else None
    old = {b["key"]: b for b in body_list(ent["st"])} if ent else {}
    liv = {b["key"]: b for b in live["list"]}
    try:
        c_ = database._mdb()
        hx = hotx._hotx_load(c_)
        c_.close()
    except sqlite3.Error:
        hx = {}
    if hx:
        for lst_ in (old, liv):
            for b_ in lst_.values():
                for r_ in b_.get("rings", []):
                    full = (b_["full"] + " " + r_["n"]).strip()
                    if r_.get("hot") and hotx._hotx_hidden(hx, full, (), r_.get("hot_ts") or ""):
                        r_["hot"] = {}
                    elif r_.get("hot") and hx.get(full):
                        r_["hot"] = {k: v for k, v in r_["hot"].items() if not hotx._hotx_hidden(hx, full, (k,), r_.get("hot_ts") or "")}
    merged = []
    for k in sorted(set(old) | set(liv), key=lambda k: (old.get(k) or liv.get(k))["id"]):
        o, n = old.get(k), liv.get(k)
        b = dict(o or {}, **(n or {}))
        if o and n:
            for f in ("bio", "geo", "human", "mining", "other"):
                b[f] = max(o.get(f, 0), n.get(f, 0))
            b["cls"] = n["cls"] or o["cls"]
            ro, rn = {r["n"]: r for r in o["rings"]}, {r["n"]: r for r in n["rings"]}
            b["rings"] = [dict(_merge_ring(ro.get(k2), rn.get(k2)), n=k2) for k2 in sorted(set(ro) | set(rn))]
        b["old"] = n is None
        merged.append(b)
    prior = [v for v in (ent or {}).get("visits", []) if v < ((sysinfo or {}).get("as_of") or "9")]
    live.update(list=merged, scanned=sum(1 for b in merged if b["cls"]), prior=len(prior),
                last=prior[-1] if prior else None, from_log=sum(1 for b in merged if b["old"]),
                total=live["total"] or (ent or {}).get("st", {}).get("total"))
    return live


def all_stats(events):
    from collections import Counter
    c = Counter(ev.get("event") for ev in events)
    ev_of = lambda *n: [e for e in events if e.get("event") in n]
    jumps = ev_of("FSDJump")
    dists = [j.get("JumpDist", 0) for j in jumps]
    systems = {e.get("SystemAddress", e.get("StarSystem")) for e in ev_of("FSDJump", "Location", "CarrierJump")}
    scans = [e for e in ev_of("Scan") if "Belt Cluster" not in e.get("BodyName", "")]
    key = lambda e: (e.get("SystemAddress"), e.get("BodyID"))
    mapped = {key(e) for e in ev_of("SAAScanComplete")}
    bio = {key(e): sum(x.get("Count", 0) for x in e.get("Signals", []) if "iolog" in x.get("Type", "") + x.get("Type_Localised", ""))
           for e in ev_of("FSSBodySignals")}
    sold = Counter(); sold_cr = Counter()
    for e in ev_of("MarketSell"):
        n = e.get("Type_Localised") or e.get("Type", "?"); sold[n] += e.get("Count", 0); sold_cr[n] += e.get("TotalSale", 0)
    top_goods = [[n, f"{timefmt._nf(sold[n])} t / {timefmt._nf(v)} Cr"] for n, v in sold_cr.most_common(3)]
    first = [e for e in ev_of("MissionCompleted")]
    ts = [e["timestamp"] for e in events if "timestamp" in e]
    S = lambda title, rows: {"title": title, "rows": [[a, str(b)] for a, b in rows]}
    return [
        S("Journal", [("Ereignisse gesamt", timefmt._nf(len(events))), ("Verschiedene Ereignistypen", len(c)),
                      ("Erstes Ereignis", ts[0][11:19] if ts else "-"), ("Letztes Ereignis", ts[-1][11:19] if ts else "-"),
                      ("Spielstarts (LoadGame)", c["LoadGame"])]),
        S("Reise", [("Systeme besucht", len(systems)), ("Hyperraum-Sprünge", len(jumps)),
                    ("Gesamtstrecke", timefmt._nf(sum(dists), 1) + " Ly"), ("Weitester Sprung", timefmt._nf(max(dists, default=0), 1) + " Ly"),
                    ("Ø Sprungweite", timefmt._nf(sum(dists) / len(dists), 1) + " Ly" if dists else "-"),
                    ("Treibstoff verbraucht", timefmt._nf(sum(j.get("FuelUsed", 0) for j in jumps), 1) + " t"),
                    ("Getankt (Scoop)", timefmt._nf(sum(e.get("Scooped", 0) for e in ev_of("FuelScoop")), 1) + " t"),
                    ("Supercruise-Einflüge", c["SupercruiseEntry"]), ("Trägersprünge", c["CarrierJump"])]),
        S("Exploration", [("FSS-Systemscans", c["FSSDiscoveryScan"]), ("Körper gescannt", len(scans)),
                          ("  davon Sterne", sum(1 for e in scans if "StarType" in e)),
                          ("  davon landbar", sum(1 for e in scans if e.get("Landable"))),
                          ("  davon terraformbar", sum(1 for e in scans if e.get("TerraformState"))),
                          ("Erstentdeckungen", sum(1 for e in scans if e.get("WasDiscovered") is False)),
                          ("Kartiert (DSS)", len(mapped)),
                          ("Oberflächen-Abbaustandorte", sum({(e.get("SystemAddress"), e.get("BodyID")): sum(x.get("Count", 0) for x in e.get("Signals", []) if "iningLocation" in x.get("Type", ""))
                                                              for e in ev_of("FSSBodySignals")}.values())),
                          ("Erstkartierungen", sum(1 for e in scans if e.get("WasMapped") is False and key(e) in mapped)),
                          ("Biosignale gefunden", sum(bio.values())),
                          ("Geosignale gefunden", sum(x.get("Count", 0) for e in ev_of("FSSBodySignals") for x in e.get("Signals", [])
                                                      if "eolog" in x.get("Type", "") + x.get("Type_Localised", ""))),
                          ("Hotspots (Ringe)", sum({e.get("BodyName"): sum(x.get("Count", 0) for x in e.get("Signals", []))
                                                                 for e in ev_of("FSSBodySignals", "SAASignalsFound") if RING_RE.search(e.get("BodyName", ""))}.values())), ("Organische Proben analysiert", sum(1 for e in ev_of("ScanOrganic") if e.get("ScanType") == "Analyse"))]),
        S("Handel", [("Verkauft", timefmt._nf(sum(e.get("Count", 0) for e in ev_of("MarketSell"))) + " t"),
                     ("Gekauft", timefmt._nf(sum(e.get("Count", 0) for e in ev_of("MarketBuy"))) + " t"),
                     ("Verkaufserlös", timefmt._nf(sum(e.get("TotalSale", 0) for e in ev_of("MarketSell"))) + " Cr"),
                     ("Einkaufskosten", timefmt._nf(sum(e.get("TotalCost", 0) for e in ev_of("MarketBuy"))) + " Cr")]
                      + [(f"Top-Ware {i + 1}: {n}", v) for i, (n, v) in enumerate(top_goods)]),
        S("Kampf", [("Kopfgeld-Abschüsse", c["Bounty"]), ("Kampfbonds", c["FactionKillBond"]),
                    ("Kopfgelder gesamt", timefmt._nf(sum(e.get("TotalReward", e.get("Reward", 0)) for e in ev_of("Bounty"))) + " Cr"),
                    ("Abgefangen worden", c["Interdicted"]), ("Selbst abgefangen", c["Interdiction"]),
                    ("Rumpfschäden", c["HullDamage"]), ("Schiff zerstört", c["Died"]),
                    ("Bond-Belohnungen", timefmt._nf(sum(e.get("Reward", 0) for e in ev_of("FactionKillBond"))) + " Cr"),
                    ("Powerplay-Merits", timefmt._nf(sum(e.get("MeritsGained", 0) for e in ev_of("PowerplayMerits")))),
                    ("Ziele gescannt", sum(1 for e in ev_of("ShipTargeted") if e.get("ScanStage", 0) >= 3)),
                    ("Verbrechen", c["CommitCrime"])]),
        S("Missionen", [("Angenommen", c["MissionAccepted"]), ("Abgeschlossen", c["MissionCompleted"]),
                        ("Gescheitert", c["MissionFailed"]), ("Aufgegeben", c["MissionAbandoned"]),
                        ("Belohnungen", timefmt._nf(sum(e.get("Reward", 0) for e in first)) + " Cr")]),
        S("Bergbau & Material", [("Materialien gesammelt", timefmt._nf(sum(e.get("Count", 0) for e in ev_of("MaterialCollected")))),
                                 ("Fracht aufgesammelt", c["CollectCargo"]), ("Erz raffiniert", c["MiningRefined"]),
                                 ("Asteroiden analysiert", c["ProspectedAsteroid"])]),
        S("Station & Schiff", [("Andockungen", c["Docked"]), ("Landungen", c["Touchdown"]), ("Starts", c["Liftoff"]),
                               ("SRV gestartet", c["LaunchSRV"]), ("Jäger gestartet", c["LaunchFighter"]),
                               ("Betankungen", c["RefuelAll"] + c["RefuelPartial"]), ("Reparaturen", c["RepairAll"] + c["Repair"]),
                               ("Screenshots", c["Screenshot"])]),
        S("Häufigste Ereignisse", [(n, timefmt._nf(v)) for n, v in c.most_common(12)]),
    ]
