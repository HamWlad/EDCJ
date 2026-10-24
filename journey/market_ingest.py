"""Märkte, Module, Fraktionen aus Journal und Market.json in die Datenbank übernehmen."""

import glob
import hashlib
import json
import os
import re
import time

from . import bodydata, captain, config, database


def store_snapshot(d):
    rows = []
    for it in d.get("Items", []):
        stock, demand = int(it.get("Stock", 0) or 0), int(it.get("Demand", 0) or 0)
        # Market.json fuehrt alle ~390 Waren mit Preisen. Preis zaehlt nur mit Bestand (kaufen) bzw. Nachfrage (verkaufen).
        b = int(it.get("BuyPrice", 0) or 0) if stock > 0 else 0
        sl = int(it.get("SellPrice", 0) or 0) if demand > 0 else 0
        nm = it.get("Name_Localised") or re.sub(r"^\$|_name;$", "", it.get("Name", ""))
        rows.append((it.get("id"), nm, it.get("Category_Localised") or "", b, sl, int(it.get("MeanPrice", 0) or 0),
                     stock, demand, it.get("StockBracket", 0), it.get("DemandBracket", 0)))
    mid, ts = d.get("MarketID"), d.get("timestamp", "")
    c = database._mdb()
    try:
        # Waren, die an dieser Station schon einmal handelbar waren, werden auch mit Menge 0 weitergefuehrt (Luecken im Verlauf)
        known = {r[0] for r in c.execute("""SELECT DISTINCT i.name FROM item i JOIN snap s ON s.id = i.snap_id
                                            WHERE s.market_id = ?""", (mid,))}
        items = [r for r in rows if r[3] > 0 or r[4] > 0 or r[1] in known]
        if not items:
            return
        h = hashlib.md5(json.dumps([(i[0], i[3], i[4], i[6], i[7]) for i in items]).encode()).hexdigest()
        c.execute("""INSERT INTO station(market_id, name, system, type, last_ts) VALUES(?,?,?,?,?)
                     ON CONFLICT(market_id) DO UPDATE SET name=excluded.name, system=excluded.system,
                     type=excluded.type, last_ts=excluded.last_ts""",
                  (mid, d.get("StationName", "?"), d.get("StarSystem", "?"), d.get("StationType", ""), ts))
        last = c.execute("SELECT id, hash, ts FROM snap WHERE market_id=? ORDER BY ts DESC, id DESC LIMIT 1", (mid,)).fetchone()
        if last and last["ts"] == ts:
            pass  # schon gespeichert
        elif last and last["hash"] == h:  # Preise und Mengen unveraendert: nur "Stand" aktualisieren
            c.execute("UPDATE snap SET seen=? WHERE id=?", (ts, last["id"]))
        else:
            cur = c.execute("INSERT INTO snap(market_id, ts, seen, hash) VALUES(?,?,?,?)", (mid, ts, ts, h))
            c.executemany("INSERT INTO item VALUES(?,?,?,?,?,?,?,?,?,?,?)", [(cur.lastrowid,) + i for i in items])
        c.commit()
    finally:
        c.close()


_MOD_TYPES = {
    "pulselaser": "Pulslaser", "beamlaser": "Strahllaser", "burstlaser": "Impulslaser", "multicannon": "Mehrfachkanone",
    "cannon": "Kanone", "fragcannon": "Splitterkanone", "slugshot": "Splitterkanone", "plasmaaccelerator": "Plasmabeschleuniger",
    "railgun": "Railgun", "basicmissilerack": "Raketenwerfer", "drunkmissilerack": "Suchraketen-Werfer",
    "dumbfiremissilerack": "Raketenwerfer (ungelenkt)", "advancedtorppylon": "Torpedo-Pylon", "mining_abrblstr": "Abbau-Sprenger",
    "mininglaser": "Abbaulaser", "mining_seismchrgwarhd": "Seismische Ladung", "mining_subsurfdispmisle": "Subsurface-Rakete",
    "plasmashockcannon": "Plasma-Schockkanone", "flakmortar": "Flak-Mörser", "flechettelauncher": "Flechette-Werfer",
    "shieldbooster": "Schildverstärker", "heatsinklauncher": "Kühlkörper-Werfer", "chafflauncher": "Düppel-Werfer",
    "plasmapointdefence": "Plasma-Punktverteidigung", "electroniccountermeasure": "Elektronische Gegenmaßnahme",
    "causticsinklauncher": "Ätz-Kühlkörper-Werfer", "cloudscanner": "Wake-Scanner", "crimescanner": "Kopfgeld-Scanner",
    "cargoscanner": "Fracht-Scanner", "shieldgenerator": "Schildgenerator", "powerplant": "Kraftwerk", "engine": "Triebwerke",
    "hyperdrive": "Frame-Shift-Antrieb", "hyperdrive_overcharged": "Frame-Shift-Antrieb (überladen)", "lifesupport": "Lebenserhaltung",
    "powerdistributor": "Energieverteiler", "sensors": "Sensoren", "cargorack": "Frachtgestell", "corrosionproofcargorack": "Frachtgestell (korrosionsfest)",
    "fuelscoop": "Treibstoff-Scoop", "fueltank": "Treibstofftank", "repairer": "Reparaturmodul", "detailedsurfacescanner": "Detail-Oberflächenscanner",
    "dockingcomputer_standard": "Dockingcomputer", "dockingcomputer_advanced": "Dockingcomputer (erweitert)",
    "supercruiseassist": "Supercruise-Assistent", "hullreinforcement": "Rumpfverstärkung", "modulereinforcement": "Modulverstärkung",
    "guardianhullreinforcement": "Guardian-Rumpfverstärkung", "guardianmodulereinforcement": "Guardian-Modulverstärkung",
    "guardianshieldreinforcement": "Guardian-Schildverstärkung", "guardianfsdbooster": "Guardian-FSD-Verstärker",
    "passengercabin": "Passagierkabine", "refinery": "Raffinerie", "buggybay": "SRV-Hangar", "fighterbay": "Jäger-Hangar",
    "collection": "Sammeldrohnen", "hackinglimpet": "Hacking-Drohnen", "prospector": "Prospektor-Drohnen",
    "fuelTransfer": "Treibstoff-Transfer-Drohnen", "fueltransfer": "Treibstoff-Transfer-Drohnen", "decontamination": "Dekontaminations-Drohnen",
    "repair": "Reparatur-Drohnen", "recon": "Aufklärungsdrohnen", "universal": "Universal-Drohnen", "research": "Forschungsdrohnen",
    "meta_alloy": "Metalllegierung", "stellarbodydiscoveryscanner": "Astro-Scanner", "planetapproachsuite": "Planetenanflug-Paket",
    "shieldcellbank": "Schildzellenbank", "dronecontrol": "Drohnensteuerung", "xenoscanner": "Xeno-Scanner",
    "metaalloyhullreinforcement": "Metalllegierungs-Rumpfverstärkung", "antiunknownshutdown": "Shutdown-Neutralisator",
    "pulselaserburst": "Impulslaser (Burst)", "minelauncher": "Minenwerfer", "railgun": "Railgun",
    "fsdinterdictor": "FSD-Interdiktor", "largebuggybay": "SRV-Hangar (groß)", "mkiilargebuggybay": "SRV-Hangar Mk II (groß)",
    "largecargorack": "Frachtgestell (groß)", "hyperdrive_overcharge": "Frame-Shift-Antrieb (überladen)",
    "dronecontrol_resourcesiphon": "Drohnensteuerung: Ressourcen-Sauger", "dronecontrol_collection": "Drohnensteuerung: Sammeldrohnen",
    "dronecontrol_prospector": "Drohnensteuerung: Prospektor", "dronecontrol_recon": "Drohnensteuerung: Aufklärung",
    "dronecontrol_fueltransfer": "Drohnensteuerung: Treibstofftransfer", "dronecontrol_repair": "Drohnensteuerung: Reparatur",
    "dronecontrol_decontamination": "Drohnensteuerung: Dekontamination", "dronecontrol_hackinglimpet": "Drohnensteuerung: Hacking",
    "multidronecontrol_rescue": "Multi-Drohnensteuerung: Rettung", "multidronecontrol_mining": "Multi-Drohnensteuerung: Bergbau",
    "multidronecontrol_xeno": "Multi-Drohnensteuerung: Xeno", "multidronecontrol_universal": "Multi-Drohnensteuerung: Universal",
    "fighterbaymk2": "Jäger-Hangar Mk II", "detailedsurfacescanner_tiny": "Detail-Oberflächenscanner",
    "planetapproachsuite_advanced": "Planetenanflug-Paket (erweitert)", "mining_abrblstr_fixed": "Abbau-Sprenger",
    "mining_subsurfdispmisle": "Subsurface-Rakete", "mining_seismchrgwarhd": "Seismische Ladung",
}
_MOD_SIZE = {"tiny": "Utility", "small": "Klein", "medium": "Mittel", "large": "Groß", "huge": "Riesig"}
_MOD_MOUNT = {"fixed": "Starr", "gimbal": "Kardanisch", "turret": "Turm"}
_MOD_CORE = {"powerplant", "engine", "hyperdrive", "hyperdrive_overcharged", "lifesupport", "powerdistributor", "sensors"}
_MOD_SHIPS = {"explorer_nx": "Caspian Explorer", "federation_dropship": "Federal Dropship", "independant_trader": "Keelback",
              "krait_mkii": "Krait Mk II", "cobramkiii": "Cobra Mk III", "cobramkv": "Cobra Mk V", "type6": "Type-6", "type7": "Type-7",
              "type8": "Type-8", "asp": "Asp Explorer", "diamondback": "Diamondback Scout", "hauler": "Hauler"}
_MOD_ARMOUR = {"grade1": "Leichtbau", "grade2": "Verstärkt", "grade3": "Militär", "mirrored": "Spiegelpanzer", "reactive": "Reaktivpanzer"}


def mod_info(code):
    """(Bezeichnung, Kategorie, Klasse) aus dem internen Modulnamen; unbekannte Namen werden nur lesbar gemacht."""
    c = str(code or "").lower()
    parts = c.split("_")
    pretty = lambda t: " ".join(w.capitalize() for w in t.replace("_", " ").split())
    rating = {"1": "E", "2": "D", "3": "C", "4": "B", "5": "A"}
    size = cls = ""
    mount = ""
    core = []
    suffix = ""
    for w in parts[1:]:
        if w == "fast" and parts[0] == "int":
            suffix = " (Bi-Weave)"
        elif w == "free":
            suffix = " (kostenlos)"
        elif w == "impulse":
            suffix = " (Impuls)"
        elif w.startswith("size") and w[4:].isdigit():
            size = w[4:]
        elif w.startswith("class") and w[5:].isdigit():
            cls = w[5:]
        elif w in _MOD_MOUNT:
            mount = w
        elif w in _MOD_SIZE and parts[0] == "hpt":
            size = w
        else:
            core.append(w)
    typ = "_".join(core)
    if "armour" in parts[1:-1]:
        k = parts.index("armour", 1)
        grade = _MOD_ARMOUR.get(parts[k + 1], pretty(parts[k + 1]))
        ship = _MOD_SHIPS.get("_".join(parts[:k])) or pretty("_".join(parts[:k]))
        return "Panzerung: " + grade + " (" + ship + ")", "Panzerung", ""
    name = (_MOD_TYPES.get(typ) or _MOD_TYPES.get(typ.replace("_", "")) or pretty(typ or c)) + suffix
    if parts[0] == "hpt":
        if size == "tiny" or (not mount and not size.isdigit() and size != "tiny" and typ in ("shieldbooster",)):
            cat = "Utility"
        elif typ in ("heatsinklauncher", "chafflauncher", "electroniccountermeasure", "plasmapointdefence", "causticsinklauncher",
                     "cloudscanner", "crimescanner", "cargoscanner", "shieldbooster", "xenoscanner", "antiunknownshutdown"):
            cat = "Utility"
        else:
            cat = "Waffe"
        if cat == "Utility":
            k = (size if size.isdigit() and size != "0" else "") + rating.get(cls, cls)
            return name, cat, " ".join(x for x in (k, _MOD_MOUNT.get(mount, "")) if x)
        return name, cat, " ".join(x for x in (_MOD_SIZE.get(size, ("Größe " + size) if size else ""), _MOD_MOUNT.get(mount, "")) if x)
    if parts[0] == "int":
        cat = "Kernmodul" if typ in _MOD_CORE or typ == "hyperdrive_overcharge" else "Optionalmodul"
        return name, cat, ((size if size.isdigit() else "") + rating.get(cls, cls))
    return name, "Sonstiges", ""


def _store_mods(kind, d):
    mid = d.get("MarketID")
    if not mid:
        return
    if kind == "m":
        rows = [(it.get("Name"), it.get("BuyPrice", 0), None, it.get("id", 0), it.get("BuyMercCoinsPrice", 0)) for it in d.get("Items") or [] if it.get("Name")]
    else:
        rows = [(it.get("ShipType"), it.get("ShipPrice", 0), it.get("ShipType_Localised"), it.get("id", 0), 0) for it in d.get("PriceList") or [] if it.get("ShipType")]
    c = database._mdb()
    try:
        c.execute("DELETE FROM gear WHERE market_id=? AND kind=?", (mid, kind))
        for r in rows:
            if kind == "m":
                lab, cat, cls = mod_info(r[0])
            else:
                lab, cat, cls = (r[2] or " ".join(w.capitalize() for w in str(r[0]).replace("_", " ").split())), "Schiff", ""
            c.execute("INSERT OR REPLACE INTO gear VALUES(?,?,?,?,?,?,?,?,?)", (mid, kind, int(r[3] or 0), r[0], lab, cat, cls, int(r[1] or 0), int(r[4] or 0)))
        c.execute("INSERT OR REPLACE INTO modst VALUES(?,?,?,?,?)",
                  (mid, kind, d.get("StationName", "?"), d.get("StarSystem", "?"), d.get("timestamp", "")))
        c.commit()
    finally:
        c.close()


OSM = {"Outfitting.json": 0, "Shipyard.json": 0}


def ingest_outfitting(directory):
    for fn, kind, ev in (("Outfitting.json", "m", "Outfitting"), ("Shipyard.json", "s", "Shipyard")):
        path = os.path.join(directory, fn)
        try:
            mt = os.path.getmtime(path)
        except OSError:
            continue
        if mt == OSM[fn]:
            continue
        try:
            with open(path, encoding="utf-8-sig") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        OSM[fn] = mt
        if d.get("event") == ev:
            _store_mods(kind, d)


def ingest_market(directory):
    if not directory:
        return
    try:
        ingest_outfitting(directory)
    except Exception:
        pass
    _ingest_market_json(directory)


def _ingest_market_json(directory):
    path = os.path.join(directory, "Market.json")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return
    if mt == database.MK["mt"]:
        return
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return  # evtl. halb geschrieben, naechster Durchlauf
    database.MK["mt"] = mt
    if d.get("event") == "Market" and d.get("MarketID"):
        store_snapshot(d)


def ingest_factions(directory):
    """Fraktions-Messwerte (Einfluss/Status) aus allen Journalen in die Datenbank uebernehmen, inkrementell."""
    if not directory:
        return
    files = sorted(glob.glob(os.path.join(directory, "Journal*.log")), key=os.path.getmtime)
    c = database._mdb()
    try:
        state = {r["name"]: r["off"] for r in c.execute("SELECT name, off FROM jstate")}
        for f in files:
            name, size = os.path.basename(f), os.path.getsize(f)
            off = state.get(name, 0)
            if size <= off:
                continue
            with open(f, "rb") as fh:
                fh.seek(off)
                data = fh.read(size - off)
            cut = data.rfind(b"\n")
            if cut < 0:
                continue
            out = []
            for line in data[:cut + 1].split(b"\n"):
                if b'"Factions"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("event") not in ("FSDJump", "Location", "CarrierJump") or not ev.get("Factions"):
                    continue
                ctrl = (ev.get("SystemFaction") or {}).get("Name")
                for fa in ev["Factions"]:
                    gov = fa.get("Government_Localised") or fa.get("Government") or ""
                    out.append((ev.get("SystemAddress"), ev.get("StarSystem", "?"), ev["timestamp"], fa.get("Name", "?"),
                                round((fa.get("Influence") or 0) * 100, 2), bodydata.STATE_DE.get(fa.get("FactionState"), fa.get("FactionState") or ""),
                                ", ".join(bodydata._state_list(fa.get("ActiveStates"))), "" if str(gov).startswith("$") else gov,
                                fa.get("MyReputation"), 1 if fa.get("Name") == ctrl else 0))
            if out:
                c.executemany("INSERT OR IGNORE INTO fac VALUES(?,?,?,?,?,?,?,?,?,?)", out)
            c.execute("INSERT OR REPLACE INTO jstate VALUES(?,?)", (name, off + cut + 1))
            c.commit()
    finally:
        c.close()


def faction_worker():
    while True:
        try:
            ingest_factions(config._journal_dir())
        except Exception as exc:
            captain.LOG_STATE["error"] = f"Fraktionen: {exc}"
        time.sleep(10)
