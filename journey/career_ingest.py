"""Karriere-Datenbank: Journal-Ereignisse einlesen (career_events, ingest_career)."""

import bisect
import glob
import json
import os
import re
import time

from . import bodydata, captain, config, database, session, timefmt


# ---------------------------------------------------------------------------
# Karriere-Datenbank: Kampf, Powerplay, Raenge, Handelsgewinn, Missionen, Flotte ... aus allen Journalen
# ---------------------------------------------------------------------------
CAREER_VER = "22"
CAREER = {"state": "wartet", "done": 0, "total": 0, "files": 0, "rows": 0, "error": None}
SHIP_DE = {"sidewinder": "Sidewinder", "eagle": "Eagle", "hauler": "Hauler", "adder": "Adder", "viper": "Viper Mk III",
           "viper_mkiv": "Viper Mk IV", "cobramkiii": "Cobra Mk III", "cobramkiv": "Cobra Mk IV", "cobramkv": "Cobra Mk V",
           "diamondback": "Diamondback Scout", "diamondbackxl": "Diamondback Explorer", "empire_eagle": "Imperial Eagle",
           "empire_courier": "Imperial Courier", "empire_trader": "Imperial Clipper", "federation_dropship": "Federal Dropship",
           "federation_dropship_mkii": "Federal Assault Ship", "federation_gunship": "Federal Gunship",
           "federation_corvette": "Federal Corvette", "independant_trader": "Keelback", "asp": "Asp Explorer",
           "asp_scout": "Asp Scout", "vulture": "Vulture", "type6": "Type-6 Transporter", "type7": "Type-7 Transporter",
           "type9": "Type-9 Heavy", "type9_military": "Type-10 Defender", "typex": "Alliance Chieftain",
           "typex_2": "Alliance Crusader", "typex_3": "Alliance Challenger", "anaconda": "Anaconda", "python": "Python",
           "python_nx": "Python Mk II", "krait_mkii": "Krait Mk II", "krait_light": "Krait Phantom", "mamba": "Mamba",
           "ferdelance": "Fer-de-Lance", "dolphin": "Dolphin", "orca": "Orca", "belugaliner": "Beluga Liner",
           "cutter": "Imperial Cutter", "testbuggy": "SRV", "scarab": "Scarab", "empire_fighter": "Imperial Fighter",
           "federation_fighter": "F63 Condor", "independent_fighter": "Taipan", "mandalay": "Mandalay",
           "corsair": "Corsair", "anacondamkii": "Anaconda Mk II", "smallcombat01_nx": "Kestrel Mk II", "explorer_nx": "Caspian Explorer", "panthermkii": "Panther Clipper Mk II", "lakonminer": "Type-11 Prospector"}
RANKS = {
    "Combat": "Harmless,Mostly Harmless,Novice,Competent,Expert,Master,Dangerous,Deadly,Elite,Elite I,Elite II,Elite III,Elite IV,Elite V",
    "Trade": "Penniless,Mostly Penniless,Peddler,Dealer,Merchant,Broker,Entrepreneur,Tycoon,Elite,Elite I,Elite II,Elite III,Elite IV,Elite V",
    "Explore": "Aimless,Mostly Aimless,Scout,Surveyor,Trailblazer,Pathfinder,Ranger,Pioneer,Elite,Elite I,Elite II,Elite III,Elite IV,Elite V",
    "Soldier": "Defenceless,Mostly Defenceless,Rookie,Soldier,Gunslinger,Warrior,Gladiator,Deadeye,Elite,Elite I,Elite II,Elite III,Elite IV,Elite V",
    "Exobiologist": "Directionless,Mostly Directionless,Compiler,Collector,Cataloguer,Taxonomist,Ecologist,Geneticist,Elite,Elite I,Elite II,Elite III,Elite IV,Elite V",
    "CQC": "Helpless,Mostly Helpless,Amateur,Semi Professional,Professional,Champion,Hero,Legend,Elite,Elite I,Elite II,Elite III,Elite IV,Elite V",
    "Empire": "None,Outsider,Serf,Master,Squire,Knight,Lord,Baron,Viscount,Count,Earl,Marquis,Duke,Prince,King",
    "Federation": "None,Recruit,Cadet,Midshipman,Petty Officer,Chief Petty Officer,Warrant Officer,Ensign,Lieutenant,Lieutenant Commander,Post Commander,Post Captain,Rear Admiral,Vice Admiral,Admiral",
}
RANKS = {k: v.split(",") for k, v in RANKS.items()}
RANK_DE = {"Combat": "Kampf", "Trade": "Handel", "Explore": "Exploration", "Soldier": "Söldner", "Exobiologist": "Exobiologie",
           "CQC": "CQC", "Empire": "Imperium", "Federation": "Föderation"}
CAREER_EVENTS = {
    "LoadGame", "Location", "FSDJump", "CarrierJump", "Docked", "Undocked", "Loadout", "ShipyardSwap", "ShipyardBuy",
    "ShipyardNew", "ShipyardSell", "SellShipOnRebuy", "Rank", "Progress", "Reputation", "Promotion", "Statistics", "Powerplay",
    "PowerplayMerits", "PowerplayCollect", "PowerplayDeliver", "PowerplayFastTrack", "PowerplaySalary", "PowerplayVote",
    "PowerplayJoin", "PowerplayLeave", "PowerplayDefect", "FactionKillBond", "Bounty", "RedeemVoucher", "ShipTargeted",
    "UnderAttack", "HullDamage", "ShieldState", "Interdicted", "Interdiction", "EscapeInterdiction", "Died", "CommitCrime",
    "PayFines", "PayBounties", "MarketSell", "MarketBuy", "MissionAccepted", "MissionCompleted", "MissionFailed",
    "MissionAbandoned", "MiningRefined", "SupercruiseDestinationDrop", "FSSSignalDiscovered", "StoredShips", "Materials",
    "MaterialCollected", "MaterialDiscarded", "Synthesis", "MaterialTrade", "TechnologyBroker", "EngineerProgress", "EngineerCraft", "Commander", "Resurrect",
    "SellExplorationData", "MultiSellExplorationData", "SellOrganicData", "CommunityGoalReward", "SearchAndRescue",
    "CapShipBond", "ShipyardSell", "ModuleSell", "ModuleSellRemote", "SellDrones", "BuyDrones", "BuyAmmo", "RefuelAll",
    "RefuelPartial", "Repair", "RepairAll", "RestockVehicle", "BuyExplorationData", "BuyTradeData", "ModuleRetrieve",
    "ModuleBuy", "ShipyardTransfer", "FetchRemoteModule", "NpcCrewPaidWage", "Disembark", "Embark", "LaunchSRV", "DockSRV", "BackpackChange", "CollectItems", "DropItems",
    "UseConsumable", "BookDropship", "DropshipDeploy", "Liftoff", "Touchdown", "SupercruiseEntry", "SupercruiseExit",
    "StartJump", "DockingRequested", "SwitchSuitLoadout", "ApproachSettlement", "Scan", "SAAScanComplete", "ScanOrganic", "ApproachBody", "LeaveBody", "FSSBodySignals", "SAASignalsFound", "ProspectedAsteroid", "LaunchDrone", "AsteroidCracked", "Missions", "MissionRedirected", "CarrierStats", "CarrierJumpRequest", "CarrierLocation", "CarrierDepositFuel", "CarrierBankTransfer", "CarrierFinance", "CarrierTradeOrder", "CarrierJumpCancelled", "CarrierDecommission", "CarrierCancelDecommission", "ColonisationConstructionDepot", "ColonisationContribution", "CargoTransfer"}
_RE_EVENT = re.compile(rb'"event"\s*:\s*"(\w+)"')
_RE_TS = re.compile(rb'"timestamp"\s*:\s*"([^"]+)"')


def ship_name(ev, key="Ship"):
    loc = ev.get(key + "_Localised")
    if loc:
        return loc
    raw = str(ev.get(key) or "")
    if not raw:
        return ""
    return SHIP_DE.get(raw.lower(), raw.replace("_", " ").title())


def rank_name(cat, val):
    names = RANKS.get(cat)
    if names is None or val is None:
        return str(val)
    return names[val] if 0 <= val < len(names) else f"Rang {val}"


def mission_type(name):
    n = re.sub(r"^Mission_", "", str(name or "")).lower()
    for key, de in sorted(captain.MISSION_DE.items(), key=lambda kv: -len(kv[0])):
        if key in n:
            return de
    return "Sonstige"


ITEM_WORDS = {"plasmashockautocannon": "plasma shock autocannon", "heatsinklauncher": "heat sink launcher",
              "pulselaser": "pulse laser", "beamlaser": "beam laser", "multicannon": "multicannon", "railgun": "rail gun",
              "plasmaaccelerator": "plasma accelerator", "slugshot": "frag cannon", "minelauncher": "mine launcher",
              "missilerack": "missile rack", "torpedopylon": "torpedo pylon", "chafflauncher": "chaff launcher",
              "electroniccountermeasure": "electronic countermeasure", "causticsinklauncher": "caustic sink launcher",
              "hullreinforcement": "hull reinforcement", "modulereinforcement": "module reinforcement",
              "shieldcellbank": "shield cell bank", "shieldgenerator": "shield generator", "powerplant": "power plant",
              "powerdistributor": "power distributor", "lifesupport": "life support", "cargorack": "cargo rack",
              "fuelscoop": "fuel scoop", "fueltank": "fuel tank", "dockingcomputer": "docking computer",
              "detailedsurfacescanner": "detailed surface scanner", "buggybay": "SRV hangar", "fighterbay": "fighter hangar",
              "guardianfsdbooster": "guardian FSD booster", "repairer": "auto field-maintenance unit", "planetapproachsuite": "planetary approach suite",
              "stellarbodydiscoveryscanner": "discovery scanner", "refinery": "refinery", "hyperdrive": "frame shift drive",
              "mkii": "mk II", "mkiii": "mk III", "mkiv": "mk IV", "supercruiseassist": "supercruise assist",
              "corrosionproofcargorack": "corrosion resistant cargo rack", "paintjob": "paint job", "shipkit": "ship kit"}
_ITEM_RE = re.compile("|".join(sorted(map(re.escape, ITEM_WORDS), key=len, reverse=True)))


def pretty_item(item):
    s = re.sub(r"^\$|_name;$", "", str(item or "")).lower()
    s = re.sub(r"^(hpt|int|ext)_", "", s)
    s = _ITEM_RE.sub(lambda m: " " + ITEM_WORDS[m.group(0)] + " ", s.replace("_", " "))
    return re.sub(r"\s+", " ", s).strip().title().replace("Fsd", "FSD").replace("Srv", "SRV").replace("Mk Ii", "Mk II")


def _career_ctx_row(c, name):
    r = c.execute("SELECT * FROM jc WHERE name=?", (name,)).fetchone()
    if r:
        ctx = {"off": r["off"], "sys": r["sys"] or "", "ship": r["ship"] or "", "station": r["station"] or "",
                "zone": r["zone"] or "", "first": r["first"] or "", "last": r["last"] or "",
                "rank": json.loads(r["rank"] or "{}")}
        ctx["mode"] = ctx["rank"].pop("_mode", "ship")
        ctx["body"] = ctx["rank"].pop("_body", "")
        return ctx
    return {"off": 0, "sys": "", "ship": "", "station": "", "zone": "", "first": "", "last": "", "rank": {}, "mode": "ship", "body": ""}


def _stn_args(ev):
    eco = ", ".join(str(x.get("Name_Localised") or x.get("Name", "")).replace("$economy_", "").replace(";", "").title()
                    for x in ev.get("StationEconomies") or [])
    gov = ev.get("StationGovernment_Localised") or str(ev.get("StationGovernment", "")).replace("$government_", "").replace(";", "")
    fa = (ev.get("StationFaction") or {}).get("Name", "")
    return ev.get("StationName"), fa, ev.get("StationType_Localised") or ev.get("StationType"), gov, eco, ev.get("DistFromStarLS", 0), ev.get("MarketID", 0)


def _pad_row(R, ev, sn, mid):
    sv = ev.get("StationServices")
    if sn and isinstance(sv, list) and sv:
        R("svc", sn, "", "", ",".join(str(x) for x in sv))
    lp = ev.get("LandingPads")
    if isinstance(lp, dict) and mid and sn:
        R("pad", sn, "", "", str(mid), "", int(lp.get("Small", 0) or 0), int(lp.get("Medium", 0) or 0), int(lp.get("Large", 0) or 0))


def _pos_put(c, rows):
    for r in rows:
        if r[3] == "pos":
            c.execute("INSERT OR REPLACE INTO syspos VALUES(?,?,?,?)", (r[6], r[11], r[12], r[13]))


def _pads_put(c, rows):
    for r in rows:
        if r[3] != "pad":
            continue
        c.execute("""INSERT INTO pads(market_id, name, system, s, m, l, ts) VALUES(?,?,?,?,?,?,?)
                     ON CONFLICT(market_id) DO UPDATE SET name=excluded.name, system=excluded.system, s=excluded.s, m=excluded.m,
                     l=excluded.l, ts=excluded.ts WHERE excluded.ts >= pads.ts""", (int(r[9]), r[6], r[4], r[11], r[12], r[13], r[0]))


def _stdb_put(c, rows):
    """Eigener, dauerhafter Bestand der besuchten Stationen/Siedlungen (bleibt auch ohne die alten Journale erhalten)."""
    for r in rows:
        if r[3] != "stn":
            continue
        ts, sysn, name, fac, typ, gov, eco, dist, mid = r[0], r[4], r[6], r[7], r[8], r[9], r[10], r[11], int(r[12] or 0)
        if not name or not sysn or "Carrier" in str(typ) or fac == "FleetCarrier" or gov == "Privateigentum":
            continue  # Flottentraeger gehoeren keiner Systemfraktion
        via = "approach" if typ == "Siedlung" else "docked"
        c.execute("""INSERT INTO stdb(system, name, market_id, type, faction, gov, eco, dist, via, first, last) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(system, name) DO UPDATE SET
                       market_id = CASE WHEN excluded.market_id > 0 THEN excluded.market_id ELSE market_id END,
                       type = CASE WHEN excluded.type = 'Siedlung' AND COALESCE(type, '') != '' THEN type ELSE COALESCE(NULLIF(excluded.type, ''), type) END,
                       faction = COALESCE(NULLIF(excluded.faction, ''), faction), gov = COALESCE(NULLIF(excluded.gov, ''), gov),
                       eco = COALESCE(NULLIF(excluded.eco, ''), eco), dist = CASE WHEN excluded.dist > 0 THEN excluded.dist ELSE dist END,
                       via = CASE WHEN excluded.via = 'docked' THEN 'docked' ELSE via END,
                       first = MIN(first, excluded.first), last = MAX(last, excluded.last)""",
                  (sysn, name, mid, typ or "", fac or "", gov or "", eco or "", dist or 0, via, ts, ts))


def career_events(ev, ctx, kv, wealth):
    """Ein Journal-Ereignis -> Liste von (kind, k1, k2, k3, x, y, n1, n2, n3); Kontext/Schnappschuesse werden nebenbei gepflegt."""
    e, g, ts = ev.get("event"), ev.get, ev.get("timestamp", "")
    out = []
    R = lambda kind, k1="", k2="", k3="", x="", y="", n1=0, n2=0, n3=0: out.append(
        (kind, str(k1 or ""), str(k2 or ""), str(k3 or ""), str(x or ""), str(y or ""), n1 or 0, n2 or 0, n3 or 0))
    num = lambda v: v if isinstance(v, (int, float)) else 0
    if e in ("ApproachBody", "SupercruiseExit", "Location") and g("Body") and g("BodyType", "Planet") in ("Planet", "PlanetaryRing"):
        ctx["body"] = g("Body")
    elif e in ("LeaveBody", "FSDJump", "CarrierJump"):
        ctx["body"] = ""
    if e in ("FSDJump", "Location", "CarrierJump") and g("StarSystem") and g("SystemEconomy_Localised") is not None:
        kv[f"Sys:{g('StarSystem')}"] = (ts, json.dumps({
            "pop": num(g("Population")), "alleg": g("SystemAllegiance") or "", "gov": g("SystemGovernment_Localised") or "", "eco": g("SystemEconomy_Localised") or "",
            "eco2": g("SystemSecondEconomy_Localised") or "", "sec": g("SystemSecurity_Localised") or "", "fac": (g("SystemFaction") or {}).get("Name", ""),
            "fst": (g("SystemFaction") or {}).get("FactionState", ""), "pos": g("StarPos") or [], "pp": g("PowerplayState") or "",
            "power": g("ControllingPower") or "", "powers": g("Powers") or []}, ensure_ascii=False))
    if e == "LoadGame":
        ctx["ship"] = ship_name(ev) or ctx["ship"]
        ctx["station"] = ""
        ctx["mode"] = "foot" if g("OnFoot") else "ship"
        if g("Credits") is not None:
            wealth.append((ts, "credits", g("Credits")))
    elif e in ("BookDropship", "DropshipDeploy", "UseConsumable", "CollectItems", "DropItems", "BackpackChange", "SwitchSuitLoadout"):
        ctx["mode"] = "foot"  # reine Odyssey-Fussereignisse
    elif e in ("SupercruiseEntry", "SupercruiseExit", "StartJump", "DockingRequested"):
        ctx["mode"] = "ship"
    elif e in ("Liftoff", "Touchdown") and g("PlayerControlled", True) and ctx.get("mode") != "srv":
        ctx["mode"] = "ship"
        if e == "Touchdown" and g("OnPlanet", True):
            R("touch", ctx.get("body", ""), g("NearestDestination_Localised") or g("NearestDestination") or "", "", "", "",
              num(g("Latitude")), num(g("Longitude")))
    elif e in ("Disembark", "Embark", "LaunchSRV", "DockSRV"):
        ctx["mode"] = "srv" if (e == "LaunchSRV" or (e in ("Disembark", "Embark") and g("SRV"))) else \
            ("foot" if e == "Disembark" else "ship")
    elif e in ("Location", "FSDJump", "CarrierJump"):
        if e == "Location" and "OnFoot" in ev:
            ctx["mode"] = "foot" if g("OnFoot") else "ship"
        ctx["sys"], ctx["zone"] = g("StarSystem", ctx["sys"]), ""
        ctx["station"] = g("StationName", "") if g("Docked") else ""
        sp = ev.get("StarPos")
        if isinstance(sp, list) and len(sp) == 3 and g("StarSystem"):
            R("pos", g("StarSystem"), n1=sp[0], n2=sp[1], n3=sp[2])
        if e == "CarrierJump":
            R("cjump", g("StarSystem"), g("Body"), g("StationName"))
        if e == "FSDJump":
            R("jump", g("StarSystem"), n1=g("JumpDist", 0), n2=g("FuelUsed", 0))
        elif g("Docked") and g("StationName"):
            sn, fa, ty, gv, ec, ds, mid = _stn_args(ev)
            R("stn", sn, fa, ty, gv, ec, ds, mid)
            _pad_row(R, ev, sn, mid)
        for cf in ev.get("Conflicts") or []:
            f1, f2 = cf.get("Faction1") or {}, cf.get("Faction2") or {}
            R("conf", f1.get("Name"), f2.get("Name"), cf.get("Status"), f"{cf.get('WarType', '')}|{f1.get('Stake', '')}|{f2.get('Stake', '')}",
              "", num(f1.get("WonDays")), num(f2.get("WonDays")))
    elif e == "Docked":
        ctx["station"] = g("StationName", "")
        sn, fa, ty, gv, ec, ds, mid = _stn_args(ev)
        R("stn", sn, fa, ty, gv, ec, ds, mid)
        _pad_row(R, ev, sn, mid)
    elif e == "Undocked":
        ctx["station"] = ""
    elif e == "Loadout":
        ctx["ship"] = ship_name(ev) or ctx["ship"]
        kv[f"Loadout:{g('ShipID')}"] = (ts, json.dumps(ev, ensure_ascii=False))
        if g("HullHealth") is not None:
            kv["HullHP"] = (ts, json.dumps({"v": g("HullHealth")}))
        for m_ in ev.get("Modules") or []:
            if "AmmoInClip" in m_ or "AmmoInHopper" in m_:
                R("ammo", m_.get("Item"), m_.get("Slot"), n1=(m_.get("AmmoInClip") or 0) + (m_.get("AmmoInHopper") or 0))
    elif e == "RepairAll":
        kv["RepAll"] = (ts, json.dumps({"cost": g("Cost", 0)}))
        kv["HullHP"] = (ts, json.dumps({"v": 1.0}))
    elif e == "Repair":
        if any(str(i).lower() == "hull" for i in g("Items") or []) or str(g("Item", "")).lower() in ("hull", "wholeship", "all"):
            kv["HullHP"] = (ts, json.dumps({"v": 1.0}))
    elif e in ("BuyAmmo", "RestockVehicle"):
        kv["AmmoBuy"] = (ts, json.dumps({"cost": g("Cost", 0)}))
    elif e == "ShipyardSwap":
        ctx["ship"] = ship_name(ev, "ShipType") or ctx["ship"]
        R("ship", "swap", ctx["ship"])
    elif e in ("ShipyardBuy", "ShipyardNew", "ShipyardSell", "SellShipOnRebuy"):
        R("ship", e, ship_name(ev, "ShipType") or ship_name(ev, "SellShipType"), n1=g("ShipPrice", 0))
    elif e in ("Rank", "Progress", "Reputation"):
        kv[e] = (ts, json.dumps(ev, ensure_ascii=False))
        if e == "Rank":
            ctx["rank"] = {k: v for k, v in ev.items() if k in RANKS}
        elif e == "Progress":
            for cat in RANKS:
                if cat in ev:
                    R("prog", cat, n1=ctx["rank"].get(cat, 0), n2=ev[cat])
    elif e == "Promotion":
        for cat in RANKS:
            if cat in ev:
                ctx["rank"][cat] = ev[cat]
                R("promo", cat, rank_name(cat, ev[cat]), n1=ev[cat])
    elif e == "Statistics":
        kv["Statistics"] = (ts, json.dumps(ev, ensure_ascii=False))
        w = (ev.get("Bank_Account") or {}).get("Current_Wealth")
        if w is not None:
            wealth.append((ts, "wealth", w))
    elif e == "Powerplay":
        kv["Powerplay"] = (ts, json.dumps(ev, ensure_ascii=False))
    elif e == "PowerplayMerits":
        R("merit", g("Power"), n1=g("MeritsGained", 0), n2=g("TotalMerits", 0))
    elif e.startswith("Powerplay") and e != "PowerplayMerits":
        R("ppx", e[9:] or e, g("Type_Localised") or g("Type") or g("Power"), n1=g("Count", g("Salary", 1)))
    elif e == "FactionKillBond":
        R("kill", g("VictimFaction"), g("AwardingFaction"), ctx["zone"], "bond", "", g("Reward", 0))
    elif e == "Bounty":
        rw = (ev.get("Rewards") or [{}])[0].get("Faction", "")
        R("kill", g("VictimFaction"), rw, ctx["zone"], "bounty", g("Target_Localised") or g("Target"),
          g("TotalReward", g("Reward", 0)))
    elif e == "RedeemVoucher":
        fa = g("Faction") or ", ".join(str(f.get("Faction", "")) for f in ev.get("Factions") or [])
        R("vouch", g("Type"), fa, n1=g("Amount", 0))
    elif e == "ShipTargeted":
        if ctx.get("mode") == "foot":
            ctx["mode"] = "ship"
        if g("ScanStage", 0) >= 3:
            R("target", g("Ship_Localised") or g("Ship"), g("PilotRank"), g("Faction"), g("LegalStatus"),
              g("PilotName_Localised") or g("PilotName"), num(g("HullHealth")) * 100, num(g("ShieldHealth")) * 100)
    elif e == "UnderAttack":
        R("hit", g("Target"))
    elif e == "HullDamage":
        if g("PlayerPilot") and not g("Fighter"):
            kv["HullHP"] = (ts, json.dumps({"v": num(g("Health"))}))
        R("hull", "Spieler" if g("PlayerPilot") else "Jaeger", n1=num(g("Health")) * 100)
    elif e == "ShieldState":
        R("shield", "up" if g("ShieldsUp") else "down")
    elif e == "Interdicted":
        R("intd", "interdicted", g("Interdictor_Localised") or g("Interdictor"), g("Faction"),
          "submit" if g("Submitted") else "fight", n1=1 if g("IsPlayer") else 0)
    elif e == "Interdiction":
        R("intd", "interdiction", g("Interdicted_Localised") or g("Interdicted"), g("Faction"),
          "success" if g("Success") else "fail", n1=1 if g("IsPlayer") else 0)
    elif e == "EscapeInterdiction":
        R("intd", "escaped", g("Interdictor_Localised") or g("Interdictor"), n1=1 if g("IsPlayer") else 0)
    elif e == "Died":
        ks = ev.get("Killers") or [{"Name": g("KillerName_Localised") or g("KillerName"), "Ship": g("KillerShip")}]
        R("death", ", ".join(str(k.get("Name", "?")) for k in ks), ", ".join(str(k.get("Ship", "")) for k in ks),
          n1=len(ks))
    elif e == "CommitCrime":
        R("crime", g("CrimeType"), g("Faction"), g("Victim"), n1=g("Fine", g("Bounty", 0)))
    elif e in ("PayFines", "PayBounties"):
        R("fine", e, n1=g("Amount", 0))
    elif e == "Resurrect":
        R("fine", e, n1=g("Cost", 0))
    elif e == "MarketSell":
        fl = ",".join(f for f in ("BlackMarket", "IllegalGoods", "StolenGoods") if g(f))
        cnt, tot = g("Count", 0), g("TotalSale", 0)
        avg = g("AvgPricePaid", 0) or 0
        R("trade", g("Type_Localised") or str(g("Type", "?")).title(), ctx["station"], "sell", fl, "",
          cnt, tot, tot - avg * cnt)
    elif e == "MarketBuy":
        R("trade", g("Type_Localised") or str(g("Type", "?")).title(), ctx["station"], "buy", "", "",
          g("Count", 0), g("TotalCost", 0), 0)
    elif e == "MissionAccepted":
        R("mis", g("LocalisedName") or g("Name"), g("Faction"), "accepted", mission_type(g("Name")), g("MissionID"),
          g("Reward", 0), g("KillCount", 0))
        R("mdet", g("MissionID"), g("DestinationSystem") or "", g("DestinationStation") or g("DestinationSettlement") or "", g("Expiry") or "",
          json.dumps({"nm": g("LocalisedName") or g("Name"), "fa": g("Faction"), "ty": mission_type(g("Name")), "tf": g("TargetFaction"),
                      "tt": g("TargetType_Localised") or g("TargetType"), "kc": g("KillCount"), "cm": g("Commodity_Localised") or g("Commodity"),
                      "ct": g("Count"), "pc": g("PassengerCount"), "pt": g("PassengerType"), "tg": g("Target_Localised") or g("Target"),
                      "inf": g("Influence"), "rep": g("Reputation"), "w": g("Wing")}, ensure_ascii=False), g("Reward", 0))
    elif e == "CarrierStats":
        fi, sp = g("Finance") or {}, g("SpaceUsage") or {}
        R("cstat", g("Callsign"), g("Name"), g("DockingAccess"), "",
          json.dumps({"bal": fi.get("CarrierBalance"), "res": fi.get("ReserveBalance"), "av": fi.get("AvailableBalance"), "rp": fi.get("ReservePercent"),
                      "tax": {k_[8:]: v_ for k_, v_ in fi.items() if k_.startswith("TaxRate_")}, "cap": sp.get("TotalCapacity"), "free": sp.get("FreeSpace"),
                      "cargo": sp.get("Cargo"), "crew": sp.get("Crew"), "sp": sp.get("ShipPacks"), "mp": sp.get("ModulePacks"), "jr": g("JumpRangeCurr"),
                      "jm": g("JumpRangeMax"), "dec": g("PendingDecommission"), "notor": g("AllowNotorious"),
                      "svc": [c_.get("CrewRole") for c_ in g("Crew") or [] if c_.get("Activated")]}),
          num(g("FuelLevel")), num(fi.get("CarrierBalance")), num(fi.get("ReserveBalance")))
    elif e == "CarrierFinance":
        R("cfin", g("CarrierID"), "", "", "", "", num(g("CarrierBalance")), num(g("ReserveBalance")), num(g("AvailableBalance")))
    elif e == "CarrierJumpRequest":
        R("cjreq", g("SystemName"), g("Body"), g("DepartureTime"), "", "", num(g("SystemAddress")))
    elif e == "CarrierJumpCancelled":
        R("cjcan", g("CarrierID"))
    elif e == "CarrierLocation":
        R("cloc", g("StarSystem"), g("CarrierID"), "", "", "", num(g("BodyID")))
    elif e == "CarrierDepositFuel":
        R("cfuel", g("CarrierID"), "", "", "", "", num(g("Amount")), num(g("Total")))
    elif e == "CarrierBankTransfer":
        R("cbank", g("CarrierID"), "", "", "", "", num(g("Deposit")) - num(g("Withdraw")), num(g("PlayerBalance")), num(g("CarrierBalance")))
    elif e == "CarrierTradeOrder":
        R("ctrade", g("Commodity_Localised") or g("Commodity"), "Kauf" if g("PurchaseOrder") else "Verkauf" if g("SaleOrder") else "Abbruch",
          "Schwarzmarkt" if g("BlackMarket") else "", "", "", num(g("PurchaseOrder") or g("SaleOrder")), num(g("Price")))
    elif e in ("CarrierDecommission", "CarrierCancelDecommission"):
        R("cdec", e, "", "", "", "", num(g("ScrapTime")))
    elif e == "Missions":
        R("mact", ",".join(str(m_.get("MissionID")) for m_ in g("Active") or []), "", "", json.dumps({str(m_.get("MissionID")): m_.get("Expires") for m_ in g("Active") or []}))
    elif e == "MissionRedirected":
        R("mred", g("MissionID"), g("NewDestinationSystem"), g("NewDestinationStation"))
    elif e == "MissionCompleted":
        R("mis", g("LocalisedName") or g("Name"), g("Faction"), "completed", mission_type(g("Name")), g("MissionID"),
          g("Reward", 0), g("Donation", 0) if isinstance(g("Donation"), (int, float)) else 0)
        for fe in g("FactionEffects") or []:
            for inf_ in fe.get("Influence") or [{}]:
                R("bgs", fe.get("Faction", "?"), str(inf_.get("Influence", "")), inf_.get("Trend", ""), str(inf_.get("SystemAddress", "")),
                  g("LocalisedName") or g("Name"), 0, len(str(fe.get("Reputation", "") or "")) * (-1 if "-" in str(fe.get("Reputation", "")) else 1))
    elif e in ("MissionFailed", "MissionAbandoned"):
        R("mis", g("LocalisedName") or g("Name"), g("Faction", ""), "failed" if e == "MissionFailed" else "abandoned",
          mission_type(g("Name")), g("MissionID"), 0, g("Fine", 0))
    elif e == "MiningRefined":
        R("mine", g("Type_Localised") or re.sub(r"^\$|_name;$", "", str(g("Type", "?"))).title(), ctx.get("body", ""), n1=1)
    elif e == "ProspectedAsteroid":
        mats = g("Materials") or []
        cont = g("Content_Localised") or re.sub(r"^\$AsteroidMaterialContent_|;$", "", str(g("Content", "")))
        R("prosp", re.sub(r"^Materialgehalt:\s*", "", cont), ctx.get("body", ""), "", "", "", len(mats), num(g("Remaining")))
        for m_ in mats:
            R("pmat", m_.get("Name_Localised") or m_.get("Name"), re.sub(r"^Materialgehalt:\s*", "", cont), ctx.get("body", ""), "", "", num(m_.get("Proportion")))
    elif e == "LaunchDrone":
        R("drone", g("Type"), ctx.get("body", ""))
    elif e == "AsteroidCracked":
        R("crack", g("Body") or ctx.get("body", ""))
    elif e in ("BuyDrones", "SellDrones"):
        R("dbuy" if e == "BuyDrones" else "dsell", g("Type", "Drones"), "", "", "", "", num(g("Count")), num(g("TotalCost", g("TotalSale", 0))))
    elif e == "SupercruiseDestinationDrop":
        t = g("Type_Localised") or g("Type") or ""
        if re.search(r"arzone|onflict|Kampf", str(g("Type")) + t):
            ctx["zone"] = t
        R("drop", t)
    elif e == "FSSSignalDiscovered" and not g("IsStation"):
        R("sig", g("SignalName_Localised") or g("SignalName"), g("USSType_Localised") or g("SignalType"))
    elif e == "ApproachSettlement" and g("Name"):
        # Siedlungen nennt das Journal nur beim Anflug
        gov = g("StationGovernment_Localised") or str(g("StationGovernment", "")).replace("$government_", "").replace(";", "")
        eco = g("StationEconomy_Localised") or ", ".join(str(x.get("Name_Localised") or x.get("Name", "")) for x in ev.get("StationEconomies") or [])
        R("stn", g("Name_Localised") or g("Name"), (g("StationFaction") or {}).get("Name", ""), "Siedlung", gov, eco, 0, g("MarketID", 0))
    elif e == "ColonisationConstructionDepot" and g("MarketID"):
        mid = g("MarketID")
        kv[f"Depot:{mid}"] = (ts, json.dumps(ev, ensure_ascii=False))
        res_ = ev.get("ResourcesRequired") or []
        sig = (num(g("ConstructionProgress")), sum(num(x.get("ProvidedAmount")) for x in res_))
        seen_ = ctx.setdefault("dep", {})
        if seen_.get(mid) != sig:
            seen_[mid] = sig
            R("cdep", mid, "", "", n1=sig[0], n2=sig[1], n3=sum(num(x.get("RequiredAmount")) for x in res_))
    elif e == "ColonisationContribution" and g("MarketID"):
        for x in ev.get("Contributions") or []:
            R("ccon", g("MarketID"), x.get("Name_Localised") or str(x.get("Name", "")).replace("$", "").replace("_name;", "").title(), n1=num(x.get("Amount")))
    elif e == "CargoTransfer":
        for x in ev.get("Transfers") or []:
            dr = str(x.get("Direction", ""))
            R("ctr", x.get("Type_Localised") or str(x.get("Type", "")).title(), dr, dr, n1=num(x.get("Count")))
    elif e == "StoredShips":
        kv["StoredShips"] = (ts, json.dumps(ev, ensure_ascii=False))
    elif e == "Materials":
        kv["Materials"] = (ts, json.dumps(ev, ensure_ascii=False))
    elif e in ("MaterialCollected", "MaterialDiscarded"):
        n = g("Count", 0) * (1 if e == "MaterialCollected" else -1)
        R("mat", g("Category"), g("Name_Localised") or str(g("Name", "?")).title(), str(g("Name", "")).lower(), n1=n)
    elif e == "MaterialTrade":
        for key, sgn in (("Paid", -1), ("Received", 1)):
            d_ = g(key) or {}
            if d_.get("Material"):
                R("mat", d_.get("Category"), d_.get("Material_Localised") or str(d_["Material"]).title(), str(d_["Material"]).lower(), n1=sgn * (d_.get("Quantity") or 0))
    elif e in ("Synthesis", "TechnologyBroker"):
        for m_ in ev.get("Materials") or []:
            if m_.get("Name"):
                R("mcon", g("Name") or e, str(m_["Name"]).lower(), "", "", m_.get("Name_Localised"), m_.get("Count") or 0)
    elif e == "EngineerProgress" and ev.get("Engineers"):
        kv["Engineers"] = (ts, json.dumps(ev, ensure_ascii=False))
    elif e == "EngineerCraft":
        R("craft", g("Engineer"), g("BlueprintName"), n1=g("Level", 0))
        for m_ in ev.get("Ingredients") or []:
            if m_.get("Name"):  # Rezept aus eigenem Craft: Zutaten + Verbrauch
                R("ing", g("Engineer"), str(m_["Name"]).lower(), g("BlueprintName"), g("Module"), m_.get("Name_Localised"), m_.get("Count") or 0, g("Level", 0))
    elif e == "Scan" and bodydata.RING_RE.search(g("BodyName", "")):
        R("ring", g("BodyName"), bodydata._ring_cls(g("RingClass")), bodydata._reserve(g("ReserveLevel")), "", "", num(g("DistanceFromArrivalLS")),
          num(g("InnerRad")), num(g("OuterRad")))
    elif e in ("FSSBodySignals", "SAASignalsFound") and bodydata.RING_RE.search(g("BodyName", "")):
        for sg in ev.get("Signals") or []:
            raw = str(sg.get("Type", ""))
            R("hot", g("BodyName"), sg.get("Type_Localised") or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", re.sub(r"^\$|_Name;$", "", raw)),
              "DSS" if e == "SAASignalsFound" else "FSS", raw, "", num(sg.get("Count")))
    elif e == "Scan":
        for rr in ev.get("Rings") or []:  # Ringe aus dem Planetenscan (ohne Reserven)
            if rr.get("Name"):
                R("ring", rr.get("Name"), bodydata._ring_cls(rr.get("RingClass")), "", "p", "", 0, num(rr.get("InnerRad")), num(rr.get("OuterRad")))
        nm = g("BodyName", "")
        cls = g("PlanetClass") or (("Stern " + str(g("StarType"))) if g("StarType") else "")
        if nm and cls and "Belt Cluster" not in nm and not bodydata.RING_RE.search(nm):
            fl = []
            if g("WasDiscovered") is False:
                fl.append("erst")
            if g("WasMapped") is False:
                fl.append("unkart")
            if g("Landable"):
                fl.append("landbar")
            if g("TerraformState") == "Terraformable":
                fl.append("terra")
            sg = num(g("SurfaceGravity"))
            R("scan", nm, cls, ",".join(fl), g("Atmosphere") or (g("AtmosphereType") if g("AtmosphereType") not in (None, "None", "") else ""),
              str(round(num(g("SurfaceTemperature")))) if g("SurfaceTemperature") is not None else "", sg / 9.80665 if sg else 0, num(g("DistanceFromArrivalLS")), num(g("MassEM")) or num(g("StellarMass")))
    elif e in ("SellExplorationData", "MultiSellExplorationData"):
        syss = list(ev.get("Systems") or []) or [d_.get("SystemName") for d_ in ev.get("Discovered") or [] if isinstance(d_, dict)]
        R("xsale", len(syss), "", "", "", "", num(g("BaseValue")), num(g("Bonus")), num(g("TotalEarnings")))
        for sn_ in syss:
            if sn_:
                R("xsold", sn_)
    elif e == "SAAScanComplete":
        R("mapd", g("BodyName"), n1=num(g("ProbesUsed")), n2=num(g("EfficiencyTarget")))
    elif e == "ScanOrganic" and g("ScanType") == "Analyse":
        R("bio", g("Genus_Localised") or g("Genus"), g("Species_Localised") or g("Species"), ctx.get("body", ""),
          g("Variant_Localised") or g("Variant") or "")
    elif e == "SellOrganicData":
        agg = {}
        for b_ in ev.get("BioData") or []:
            kk = (b_.get("Genus_Localised") or b_.get("Genus") or "?", b_.get("Variant_Localised") or b_.get("Species_Localised") or b_.get("Species") or "?")
            o_ = agg.setdefault(kk, [0, 0, 0])
            o_[0] += num(b_.get("Value"))
            o_[1] += num(b_.get("Bonus"))
            o_[2] += 1
        for (ge, va), (v_, bo, n_) in agg.items():
            R("bsell", ge, va, ctx.get("station", ""), "", "", v_, bo, n_)
    elif e == "Commander":
        kv["Commander"] = (ts, json.dumps({"Name": g("Name")}))
    for cat, amt in session.credit_changes(ev):
        if amt:
            R("cash", cat, n1=amt)
    return out


def ingest_career(directory):
    """Alle Journale inkrementell in die Karriere-Tabellen einlesen (Byte-Offsets je Datei, nur vollstaendige Zeilen)."""
    if not directory:
        return
    files = sorted(glob.glob(os.path.join(directory, "Journal*.log")), key=lambda p: (os.path.basename(p), os.path.getmtime(p)))
    c = database._mdb()
    try:
        ver = c.execute("SELECT js FROM snapkv WHERE k='ver'").fetchone()
        if not ver or ver["js"] != CAREER_VER:
            c.executescript("DELETE FROM ce; DELETE FROM jc; DELETE FROM wealth; DELETE FROM act; DELETE FROM snapkv;")
            c.execute("INSERT INTO snapkv VALUES('ver','',?)", (CAREER_VER,))
            c.commit()
        modes = [(r["ts"], r["mode"]) for r in c.execute("SELECT ts, mode FROM modelog ORDER BY ts")]
        mts = [m[0] for m in modes]
        offs = {r["name"]: r["off"] for r in c.execute("SELECT name, off FROM jc")}
        todo = [f for f in files if os.path.getsize(f) > offs.get(os.path.basename(f), 0)]
        CAREER["total"] = sum(os.path.getsize(f) - offs.get(os.path.basename(f), 0) for f in todo)
        CAREER["done"], CAREER["files"] = 0, len(todo)
        if not todo:
            CAREER["state"] = "bereit"
            return
        CAREER["state"] = "importiere"
        for f in todo:
            name = os.path.basename(f)
            ctx = _career_ctx_row(c, name)
            size = os.path.getsize(f)
            with open(f, "rb") as fh:
                fh.seek(ctx["off"])
                while ctx["off"] < size:
                    data = fh.read(min(size - ctx["off"], 4 << 20))
                    cut = data.rfind(b"\n")
                    if cut < 0:
                        break
                    rows, kv, wealth, acts, pos = [], {}, [], set(), ctx["off"]
                    for line in data[:cut + 1].split(b"\n"):
                        ln = len(line) + 1
                        m = _RE_EVENT.search(line, 0, 160)
                        mt = _RE_TS.search(line, 0, 100)
                        if mt:
                            tsv = mt.group(1).decode()
                            acts.add(tsv[:15])
                            if not ctx["first"]:
                                ctx["first"] = tsv
                            ctx["last"] = tsv
                        if m and m.group(1).decode() in CAREER_EVENTS:
                            try:
                                ev = json.loads(line)
                            except ValueError:
                                ev = None
                            if ev:
                                evs = career_events(ev, ctx, kv, wealth)
                                md = ctx.get("mode")
                                if evs and mts:  # exakter Modus aus Status.json, falls fuer diesen Zeitpunkt aufgezeichnet
                                    tsv2 = ev.get("timestamp", "")
                                    i = bisect.bisect_right(mts, tsv2) - 1
                                    if i >= 0 and (timefmt.parse_ts(tsv2) - timefmt.parse_ts(mts[i])).total_seconds() <= 150:
                                        md = modes[i][1]
                                for r in evs:
                                    rows.append((ev.get("timestamp", ""), name, pos, r[0], ctx["sys"],
                                              {"foot": "Zu Fuß", "srv": "SRV"}.get(md, ctx["ship"])) + r[1:])
                        pos += ln
                    c.executemany("INSERT OR IGNORE INTO ce(ts,file,pos,kind,sys,ship,k1,k2,k3,x,y,n1,n2,n3) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                    _stdb_put(c, rows)
                    _pads_put(c, rows)
                    _pos_put(c, rows)
                    c.executemany("INSERT OR IGNORE INTO act VALUES(?)", [(a,) for a in acts])
                    c.executemany("INSERT OR REPLACE INTO wealth VALUES(?,?,?)", wealth)
                    for k, (t, js) in kv.items():
                        c.execute("""INSERT INTO snapkv VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET ts=excluded.ts, js=excluded.js
                                     WHERE excluded.ts >= snapkv.ts""", (k, t, js))
                    ctx["off"] += cut + 1
                    c.execute("INSERT OR REPLACE INTO jc VALUES(?,?,?,?,?,?,?,?,?)",
                              (name, ctx["off"], ctx["sys"], ctx["ship"], ctx["station"], ctx["zone"], ctx["first"], ctx["last"],
                               json.dumps(dict(ctx["rank"], _mode=ctx.get("mode", "ship"), _body=ctx.get("body", "")))))
                    c.commit()
                    CAREER["done"] += cut + 1
                    CAREER["rows"] += len(rows)
                    fh.seek(ctx["off"])
        CAREER["state"] = "bereit"
    finally:
        c.close()


def career_worker():
    while True:
        try:
            ingest_career(config._journal_dir())
            CAREER["error"] = None
        except Exception as exc:
            CAREER["error"] = str(exc)
            CAREER["state"] = "Fehler"
        time.sleep(6)
