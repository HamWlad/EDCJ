"""Sitzungen, Team und Kampfanalyse: liest die Journale direkt (nur eigene Daten) und fasst sie pro Spielsitzung zusammen.

Eine Sitzung ist eine Journaldatei (das Spiel legt bei jedem Start eine neue an). Die Ergebnisse je Datei werden
im Speicher gehalten und nur neu berechnet, wenn sich Groesse oder Aenderungszeit der Datei geaendert haben.
"""

import glob
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone

from . import career_ingest, config, timefmt

_WANT = re.compile(rb'"event"\s*:\s*"(?:' + b"|".join(x.encode() for x in (
    "LoadGame", "Loadout", "Location", "FSDJump", "CarrierJump", "Bounty", "FactionKillBond", "RedeemVoucher",
    "ShipTargeted", "ShieldState", "HullDamage", "UnderAttack", "HeatWarning", "HeatDamage", "Interdicted", "EscapeInterdiction", "Died",
    "CommitCrime", "CrimeVictim", "PowerplayMerits", "Powerplay", "WingAdd", "WingJoin", "WingLeave", "MarketSell", "MarketBuy",
    "MissionCompleted", "SellExplorationData", "MultiSellExplorationData", "SellOrganicData", "CommunityGoalReward", "SearchAndRescue",
    "RepairAll", "Repair", "RefuelAll", "RefuelPartial", "BuyAmmo", "RestockVehicle", "NpcCrewPaidWage", "PayFines", "PayBounties",
    "ModuleBuy", "ShipyardBuy", "ModuleSell", "ShipyardSell")) + rb')"')

_TS = re.compile(rb'"timestamp"\s*:\s*"([^"]+)"')
_CACHE = {}
_LOCK = threading.Lock()


def _num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _parse(path):
    """Eine Journaldatei -> Rohdaten der Sitzung (Listen mit Zeitstempel)."""
    s = {"file": os.path.basename(path), "start": None, "end": None, "ship": "", "ships": [], "jumps": 0, "ly": 0.0, "systems": set(),
         "inc": [], "exp": [], "kills": [], "targets": {}, "shield": [], "hull": [], "attacks": [], "heat": [], "intd": [], "died": [],
         "crimes": [], "victim": 0, "merits": [], "power": "", "total_merits": None, "wing": [], "missions": [], "credits": None, "cmdr": ""}
    cur_sys = ""
    open_wing = None
    members = set()
    try:
        fh = open(path, "rb")
    except OSError:
        return s
    with fh:
        for raw in fh:
            if len(raw) < 20:
                continue
            t = _TS.search(raw)
            if not t:
                continue
            ts = t.group(1).decode()
            if s["start"] is None:
                s["start"] = ts
            s["end"] = ts
            if not _WANT.search(raw):
                continue
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            e = ev.get("event")
            if e == "LoadGame":
                s["ship"] = s["ship"] or career_ingest.ship_name(ev)
                s["credits"] = ev.get("Credits") if s["credits"] is None else s["credits"]
                s["cmdr"] = ev.get("Commander", s["cmdr"])
            elif e == "Loadout":
                nm = career_ingest.ship_name(ev)
                lbl = (nm + (" „" + str(ev.get("ShipName")).strip() + "“" if str(ev.get("ShipName") or "").strip() else "")) if nm else ""
                if lbl and lbl not in s["ships"]:
                    s["ships"].append(lbl)
            elif e in ("Location", "FSDJump", "CarrierJump"):
                if ev.get("StarSystem"):
                    cur_sys = ev["StarSystem"]
                    s["systems"].add(cur_sys)
                if e != "Location":
                    s["jumps"] += 1
                    s["ly"] += float(ev.get("JumpDist") or 0)
            elif e == "Bounty":
                s["kills"].append({"ts": ts, "kind": "bounty", "reward": _num(ev.get("TotalReward")), "ship": career_ingest.ship_name(ev, "Target") if ev.get("Target") else "",
                                   "faction": ev.get("VictimFaction", ""), "sys": cur_sys})
            elif e == "FactionKillBond":
                s["kills"].append({"ts": ts, "kind": "bond", "reward": _num(ev.get("Reward")), "ship": "", "faction": ev.get("VictimFaction", ""), "sys": cur_sys})
            elif e == "RedeemVoucher":
                s["inc"].append((ts, "Gutscheine eingelöst (Kopfgeld, Kampfanleihen)", _num(ev.get("Amount"))))
            elif e == "MarketSell":
                s["inc"].append((ts, "Warenverkauf", _num(ev.get("TotalSale"))))
            elif e == "MarketBuy":
                s["exp"].append((ts, "Wareneinkauf", _num(ev.get("TotalCost"))))
            elif e == "MissionCompleted":
                rw, dn = _num(ev.get("Reward")), _num(ev.get("Donated"))
                if rw:
                    s["inc"].append((ts, "Missionsbelohnungen", rw))
                if dn:
                    s["exp"].append((ts, "Spenden", dn))
                s["missions"].append({"ts": ts, "name": ev.get("LocalisedName") or ev.get("Name", ""), "reward": rw})
            elif e in ("SellExplorationData", "MultiSellExplorationData"):
                s["inc"].append((ts, "Erkundungsdaten", _num(ev.get("TotalEarnings"))))
            elif e == "SellOrganicData":
                s["inc"].append((ts, "Exobiologie", sum(_num(b.get("Value")) + _num(b.get("Bonus")) for b in ev.get("BioData", []))))
            elif e == "CommunityGoalReward":
                s["inc"].append((ts, "Community Goal", _num(ev.get("Reward"))))
            elif e == "SearchAndRescue":
                s["inc"].append((ts, "Rettung & Bergung", _num(ev.get("Reward"))))
            elif e == "ModuleSell" or e == "ShipyardSell":
                s["inc"].append((ts, "Verkauf Schiffe/Module", _num(ev.get("SellPrice") or ev.get("ShipPrice"))))
            elif e in ("RepairAll", "Repair"):
                s["exp"].append((ts, "Reparatur", _num(ev.get("Cost"))))
            elif e in ("RefuelAll", "RefuelPartial"):
                s["exp"].append((ts, "Treibstoff", _num(ev.get("Cost"))))
            elif e in ("BuyAmmo", "RestockVehicle"):
                s["exp"].append((ts, "Munition & Fahrzeuge", _num(ev.get("Cost"))))
            elif e == "NpcCrewPaidWage":
                s["exp"].append((ts, "Crew-Löhne", _num(ev.get("Amount"))))
            elif e in ("PayFines", "PayBounties"):
                s["exp"].append((ts, "Strafen & Kopfgelder bezahlt", _num(ev.get("Amount"))))
            elif e == "ModuleBuy":
                s["exp"].append((ts, "Käufe Schiffe/Module", _num(ev.get("BuyPrice"))))
            elif e == "ShipyardBuy":
                s["exp"].append((ts, "Käufe Schiffe/Module", _num(ev.get("ShipPrice"))))
            elif e == "ShipTargeted":
                if _num(ev.get("ScanStage")) >= 3 and ev.get("Ship"):
                    pn = ev.get("PilotName_Localised") or ev.get("PilotName") or "?"
                    k = (pn, ev["Ship"])
                    if k not in s["targets"]:
                        s["targets"][k] = {"ts": ts, "ship": career_ingest.ship_name(ev), "legal": ev.get("LegalStatus", ""), "bounty": _num(ev.get("Bounty")),
                                           "faction": ev.get("Faction", ""), "power": ev.get("Power", ""), "rank": ev.get("PilotRank", "")}
            elif e == "ShieldState":
                if ev.get("ShieldsUp") is False:
                    s["shield"].append((ts, cur_sys))
            elif e == "HullDamage":
                if ev.get("PlayerPilot") and not ev.get("Fighter"):
                    s["hull"].append((ts, float(ev.get("Health") or 0)))
            elif e == "UnderAttack":
                if ev.get("Target") == "You":
                    s["attacks"].append(ts)
            elif e in ("HeatWarning", "HeatDamage"):
                s["heat"].append((ts, cur_sys, e))
            elif e in ("Interdicted", "EscapeInterdiction"):
                s["intd"].append((ts, e, bool(ev.get("Submitted")), ev.get("IsPlayer")))
            elif e == "Died":
                s["died"].append(ts)
            elif e == "CommitCrime":
                s["crimes"].append((ts, ev.get("CrimeType", ""), _num(ev.get("Bounty") or ev.get("Fine"))))
            elif e == "CrimeVictim":
                s["victim"] += 1
            elif e == "PowerplayMerits":
                s["merits"].append((ts, _num(ev.get("MeritsGained"))))
                s["total_merits"] = ev.get("TotalMerits")
                s["power"] = ev.get("Power", s["power"])
            elif e == "Powerplay":
                s["power"] = ev.get("Power", s["power"])
                if s["total_merits"] is None:
                    s["total_merits"] = ev.get("Merits")
            elif e in ("WingAdd", "WingJoin"):
                if open_wing is None:
                    open_wing = ts
                    members = set()
                if e == "WingAdd" and ev.get("Name"):
                    members.add(ev["Name"])
                if e == "WingJoin":
                    members.update(n for n in ev.get("Others", []) if n)
            elif e == "WingLeave":
                if open_wing is not None:
                    s["wing"].append({"start": open_wing, "end": ts, "members": sorted(members)})
                open_wing, members = None, set()
    if open_wing is not None:
        s["wing"].append({"start": open_wing, "end": s["end"], "members": sorted(members)})
    s["systems"] = len(s["systems"])
    return s


def _files():
    d = config._journal_dir()
    if config.CONFIG["file"]:
        return [config.CONFIG["file"]]
    return sorted(glob.glob(os.path.join(d, "Journal*.log")), key=os.path.basename) if d else []


def _load():
    out = []
    with _LOCK:
        for p in _files():
            try:
                st = os.stat(p)
            except OSError:
                continue
            key = (st.st_size, st.st_mtime_ns)
            c = _CACHE.get(p)
            if not c or c[0] != key:
                c = _CACHE[p] = (key, _parse(p))
            out.append(c[1])
    return [s for s in out if s["start"]]


def _mins(a, b):
    try:
        return max(0.0, (timefmt.parse_ts(b) - timefmt.parse_ts(a)).total_seconds() / 60)
    except Exception:
        return 0.0


def _in(ts, ivs):
    return any(a <= ts <= b for a, b in ivs)


def _sum(rows, ivs=None):
    return sum(r[-1] for r in rows if ivs is None or _in(r[0], ivs))


def _session(s):
    inc, exp = {}, {}
    for _t, k, v in s["inc"]:
        inc[k] = inc.get(k, 0) + v
    for _t, k, v in s["exp"]:
        exp[k] = exp.get(k, 0) + v
    ti, te = sum(inc.values()), sum(exp.values())
    mins = _mins(s["start"], s["end"])
    kills = s["kills"]
    return {"file": s["file"], "start": s["start"], "end": s["end"], "mins": round(mins, 1), "ship": s["ship"], "ships": s["ships"],
            "jumps": s["jumps"], "ly": round(s["ly"], 1), "systems": s["systems"], "inc": inc, "exp": exp, "income": ti, "expense": te, "net": ti - te,
            "credits": s["credits"], "kills": len(kills), "kill_credits": sum(k["reward"] for k in kills), "scans": len(s["targets"]),
            "shield": len(s["shield"]), "hull": len(s["hull"]), "min_hull": round(min((h for _t, h in s["hull"]), default=1.0) * 100),
            "attacks": len(s["attacks"]), "heat": len([h for h in s["heat"] if h[2] == "HeatWarning"]), "heat_dmg": len([h for h in s["heat"] if h[2] == "HeatDamage"]),
            "interdicted": len([i for i in s["intd"] if i[1] == "Interdicted"]), "escaped": len([i for i in s["intd"] if i[1] == "EscapeInterdiction"]),
            "died": len(s["died"]), "crimes": len(s["crimes"]), "crime_bounty": sum(c[2] for c in s["crimes"]), "victim": s["victim"],
            "merits": sum(m[1] for m in s["merits"]), "total_merits": s["total_merits"], "power": s["power"], "missions": s["missions"][:12],
            "n_missions": len(s["missions"]), "wing": [{"start": w["start"], "end": w["end"], "members": w["members"], "mins": round(_mins(w["start"], w["end"]), 1)} for w in s["wing"]],
            "wing_mins": round(sum(_mins(w["start"], w["end"]) for w in s["wing"]), 1)}


def _team(ses):
    """Mit wem geflogen, und Flügel gegen Solo (je Stunde)."""
    mem, rows = {}, []
    w = {"mins": 0.0, "kills": 0, "kill_credits": 0, "income": 0, "expense": 0, "scans": 0, "hull": 0, "shield": 0, "attacks": 0, "heat": 0, "crimes": 0, "merits": 0}
    o = {k: (0.0 if k == "mins" else 0) for k in w}
    for s in ses:
        ivs = [(x["start"], x["end"]) for x in s["wing"]]
        total_m = _mins(s["start"], s["end"])
        wm = sum(_mins(a, b) for a, b in ivs)
        for tag, flt in (("w", lambda t: _in(t, ivs)), ("o", lambda t: not _in(t, ivs))):
            d = w if tag == "w" else o
            d["mins"] += wm if tag == "w" else max(0.0, total_m - wm)
            ks = [k for k in s["kills"] if flt(k["ts"])]
            d["kills"] += len(ks)
            d["kill_credits"] += sum(k["reward"] for k in ks)
            d["income"] += sum(v for t, _k, v in s["inc"] if flt(t))
            d["expense"] += sum(v for t, _k, v in s["exp"] if flt(t))
            d["scans"] += len([1 for v in s["targets"].values() if flt(v["ts"])])
            d["hull"] += len([1 for t, _h in s["hull"] if flt(t)])
            d["shield"] += len([1 for t, _y in s["shield"] if flt(t)])
            d["attacks"] += len([1 for t in s["attacks"] if flt(t)])
            d["heat"] += len([1 for t, _y, e in s["heat"] if e == "HeatWarning" and flt(t)])
            d["crimes"] += len([1 for t, _c, _b in s["crimes"] if flt(t)])
            d["merits"] += sum(v for t, v in s["merits"] if flt(t))
        for x in s["wing"]:
            a, b = x["start"], x["end"]
            ks = [k for k in s["kills"] if a <= k["ts"] <= b]
            mn = _mins(a, b)
            rows.append({"start": a, "end": b, "mins": round(mn, 1), "members": x["members"], "kills": len(ks), "kill_credits": sum(k["reward"] for k in ks),
                         "income": sum(v for t, _k, v in s["inc"] if a <= t <= b), "expense": sum(v for t, _k, v in s["exp"] if a <= t <= b),
                         "scans": len([1 for v in s["targets"].values() if a <= v["ts"] <= b]), "shield": len([1 for t, _y in s["shield"] if a <= t <= b]),
                         "hull": len([1 for t, _h in s["hull"] if a <= t <= b]), "heat": len([1 for t, _y, e in s["heat"] if e == "HeatWarning" and a <= t <= b]),
                         "crimes": len([1 for t, _c, _b in s["crimes"] if a <= t <= b]), "merits": sum(v for t, v in s["merits"] if a <= t <= b), "file": s["file"]})
            for n in x["members"]:
                m = mem.setdefault(n, {"name": n, "mins": 0.0, "n": 0, "last": ""})
                m["mins"] += mn
                m["n"] += 1
                m["last"] = max(m["last"], b)
    for d in (w, o):
        d["mins"] = round(d["mins"], 1)
    return {"members": sorted(({**m, "mins": round(m["mins"], 1)} for m in mem.values()), key=lambda m: -m["mins"]), "wings": sorted(rows, key=lambda r: r["start"], reverse=True),
            "wing": w, "solo": o}


def _combat(ses):
    ships, legal, fac, kship, kfac, daily, heat, shield_sys, bysess = {}, {}, {}, {}, {}, {}, {}, {}, []
    kills_all = []
    for s in ses:
        for t in s["targets"].values():
            ships[t["ship"]] = ships.get(t["ship"], 0) + 1
            legal[t["legal"] or "?"] = legal.get(t["legal"] or "?", 0) + 1
            if t["faction"]:
                fac[t["faction"]] = fac.get(t["faction"], 0) + 1
        for k in s["kills"]:
            kills_all.append(k)
            if k["ship"]:
                a = kship.setdefault(k["ship"], [0, 0])
                a[0] += 1
                a[1] += k["reward"]
            if k["faction"]:
                a = kfac.setdefault(k["faction"], [0, 0])
                a[0] += 1
                a[1] += k["reward"]
            d = timefmt.parse_ts(k["ts"]).astimezone().strftime("%Y-%m-%d")
            a = daily.setdefault(d, [0, 0])
            a[0] += 1
            a[1] += k["reward"]
        for t, y, e in s["heat"]:
            if e == "HeatWarning":
                a = heat.setdefault(y or "?", [0, ""])
                a[0] += 1
                a[1] = max(a[1], t)
        for _t, y in s["shield"]:
            shield_sys[y or "?"] = shield_sys.get(y or "?", 0) + 1
        if s["kills"] or s["shield"] or s["heat"] or s["hull"] or s["targets"]:
            mins = _mins(s["start"], s["end"])
            ks = sorted(s["kills"], key=lambda k: k["ts"])
            span = _mins(ks[0]["ts"], ks[-1]["ts"]) if len(ks) > 1 else 0.0
            cr = sum(k["reward"] for k in ks)
            bysess.append({"start": s["start"], "mins": round(mins, 1), "kills": len(ks), "credits": cr, "scans": len(s["targets"]),
                           "shield": len(s["shield"]), "hull": len(s["hull"]), "attacks": len(s["attacks"]),
                           "heat": len([1 for h in s["heat"] if h[2] == "HeatWarning"]),
                           "cr_h": round(cr / (mins / 60)) if mins >= 1 and cr else None, "cr_kill": round(cr / len(ks)) if ks else None,
                           "span_h": round(span / 60, 2), "cr_span_h": round(cr / (span / 60)) if span >= 5 else None})
    top = lambda d, n=12: [{"name": k, "n": v} for k, v in sorted(d.items(), key=lambda t: -t[1])[:n]]
    tot_k = len(kills_all)
    tot_c = sum(k["reward"] for k in kills_all)
    mins_k = sum(b["mins"] for b in bysess if b["kills"])
    return {"ships": top(ships), "legal": top(legal), "factions": top(fac, 8), "kills": tot_k, "credits": tot_c, "cr_kill": round(tot_c / tot_k) if tot_k else None,
            "cr_h": round(tot_c / (mins_k / 60)) if mins_k >= 1 and tot_c else None, "sessions_kills": len([b for b in bysess if b["kills"]]),
            "kship": [{"name": k, "n": a[0], "cr": a[1], "avg": round(a[1] / a[0])} for k, a in sorted(kship.items(), key=lambda t: -t[1][1])[:12]],
            "kfac": [{"name": k, "n": a[0], "cr": a[1]} for k, a in sorted(kfac.items(), key=lambda t: -t[1][1])[:8]],
            "daily": [{"day": d, "n": a[0], "cr": a[1]} for d, a in sorted(daily.items())][-30:],
            "heat": [{"sys": k, "n": a[0], "last": a[1]} for k, a in sorted(heat.items(), key=lambda t: -t[1][0])[:10]],
            "shield_sys": [{"sys": k, "n": n} for k, n in sorted(shield_sys.items(), key=lambda t: -t[1])[:10]],
            "sessions": sorted(bysess, key=lambda b: b["start"], reverse=True)[:40]}


def sitzungen_api(q):
    ses = _load()
    try:
        days = int(q.get("days") or 0)
    except ValueError:
        days = 0
    if days > 0:
        lim = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ses = [s for s in ses if s["end"] >= lim]
    ses = sorted(ses, key=lambda s: s["start"], reverse=True)
    return {"sessions": [_session(s) for s in ses[:60]], "n": len(ses), "team": _team(ses), "combat": _combat(ses)}
