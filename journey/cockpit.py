"""Cockpit: Lage-Erkennung und Status/Fracht/Route."""

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import bodydata, career_ingest, config, database, helpers, hotx, mining, status, timefmt


def _maint(c, st, out, lo, lots):
    """Wartung vor dem Flug: nur aus Status und Journal-Staenden abgeleitet. Rueckgabe: Liste {label, state(ok/warn/bad), text}."""
    items = []
    if out.get("mode") != "ship":
        return items
    kvt = lambda k: (c.execute("SELECT ts, js FROM snapkv WHERE k=?", (k,)).fetchone())
    fm = (st.get("Fuel") or {}).get("FuelMain")
    cap = (out.get("ship") or {}).get("fuel_cap")
    if fm is not None and cap:
        pct = fm / cap * 100
        stt = "ok" if pct >= 75 else "warn" if pct >= 40 else "bad"
        txt = f"{fm:.1f} von {cap:g} t ({pct:.0f} %)"
        rt = out.get("route") or {}
        fc = out.get("fuelcalc") or {}
        if rt.get("short") is not None:
            stt = "bad"
            txt += f" · reicht nicht bis zum Ziel der Route (Engpass: {rt['items'][rt['short']]['name']})"
        elif fc.get("route_full"):
            txt += " · reicht für die geplante Route"
        elif stt != "ok":
            txt += " · tanken sinnvoll"
        items.append({"label": "Treibstoff", "state": stt, "text": txt})
    hh = kvt("HullHP")
    if hh:
        v = json.loads(hh["js"]).get("v", 1)
        items.append({"label": "Rumpf", "state": "ok" if v >= 0.99 else "warn" if v >= 0.7 else "bad",
                      "text": f"{v * 100:.0f} %" + ("" if v >= 0.99 else " · Reparatur an der Station"), "ts": hh["ts"]})
    lts = lots[0] if lots else ""
    rep = kvt("RepAll")
    repaired = bool(rep and lts and rep["ts"] > lts)
    if lo and lo.get("Modules"):
        worn = sorted(((m.get("Health", 1) or 0), career_ingest.pretty_item(m.get("Item")), m.get("Slot", "")) for m in lo["Modules"] if (m.get("Health", 1) or 0) < 0.9)
        if repaired and worn:
            items.append({"label": "Module", "state": "ok", "text": "seit dem letzten Loadout komplett repariert"})
        elif worn:
            txt = ", ".join(f"{n} {h * 100:.0f} %" for h, n, _ in worn[:4]) + (f" und {len(worn) - 4} weitere" if len(worn) > 4 else "")
            items.append({"label": "Module", "state": "bad" if worn[0][0] < 0.6 else "warn", "text": txt + " · Reparatur an der Station"})
        else:
            items.append({"label": "Module", "state": "ok", "text": "alle über 90 %"})
        buy = kvt("AmmoBuy")
        restocked = bool(buy and lts and buy["ts"] > lts)
        low = []
        for m in lo["Modules"]:
            if "AmmoInClip" in m or "AmmoInHopper" in m:
                cur = (m.get("AmmoInClip") or 0) + (m.get("AmmoInHopper") or 0)
                mx = c.execute("SELECT MAX(n1) FROM ce WHERE kind='ammo' AND k1=?", (m.get("Item"),)).fetchone()[0] or 0
                if mx and cur < 0.8 * mx:
                    low.append((cur / mx, career_ingest.pretty_item(m.get("Item")), cur, mx))
        if restocked and low:
            items.append({"label": "Munition", "state": "ok", "text": "seit dem letzten Loadout nachgekauft"})
        elif low:
            low.sort()
            items.append({"label": "Munition", "state": "bad" if low[0][0] < 0.5 else "warn",
                          "text": ", ".join(f"{n} {cur:g}/{mx:g}" for _, n, cur, mx in low[:4]) + " · nachkaufen (Maß: höchster bisher gesehener Stand)"})
        elif any(("AmmoInClip" in m or "AmmoInHopper" in m) for m in lo["Modules"]):
            items.append({"label": "Munition", "state": "ok", "text": "gefüllt"})
    rb, bal = (lo or {}).get("Rebuy"), st.get("Balance")
    if rb and bal is not None:
        items.append({"label": "Rebuy", "state": "ok" if bal >= rb else "bad",
                      "text": f"{timefmt._nf(rb)} Cr · Kontostand {timefmt._nf(bal)} Cr" + ("" if bal >= rb else " · reicht nicht")})
    return items


def lage_info(c, st, out):
    """Kontext-Cockpit: erkennt die Lage (Ring / Station / Planet / Raum) und sucht dazu nur eigene, gespeicherte Daten."""
    c.row_factory = sqlite3.Row
    state, body, sysn = out.get("state"), st.get("BodyName") or "", out.get("system") or ""
    now = datetime.now(timezone.utc)
    ageof = lambda ts: round((now - timefmt.parse_ts(ts)).total_seconds() / 3600, 1) if ts else None
    if body and bodydata.RING_RE.search(body) and state != "Angedockt":
        res = {"kind": "ring", "title": body, "sys": sysn}
        newest = {}
        evs = {}
        for r in c.execute("SELECT ts, file, pos, k2, k3, x, n1 FROM ce WHERE kind='hot' AND k1=? ORDER BY ts, file, pos", (body,)):
            evs.setdefault((r["file"], r["pos"]), []).append(r)
        for lst in evs.values():
            rank = (1 if lst[0]["k3"] == "DSS" else 0, lst[0]["ts"])
            if not newest or rank >= newest["rank"]:
                newest = {"rank": rank, "lst": lst}
        hx = hotx._hotx_load(c)
        hot = []
        for r in (newest.get("lst") or []):
            if not hotx._hotx_hidden(hx, body, (r["x"], r["k2"]), r["ts"]):
                hot.append({"mineral": r["k2"], "count": int(r["n1"])})
        ri = c.execute("SELECT k2, k3, n1 FROM ce WHERE kind='ring' AND k1=? AND x != 'p' ORDER BY ts DESC LIMIT 1", (body,)).fetchone()
        cl_ = c.execute("SELECT k2 FROM ce WHERE kind='ring' AND k1=? AND k2 != '' ORDER BY ts DESC LIMIT 1", (body,)).fetchone()
        rs_ = c.execute("SELECT k3 FROM ce WHERE kind='ring' AND k1=? AND k3 != '' ORDER BY ts DESC LIMIT 1", (body,)).fetchone()
        res["ring"] = {"cls": cl_[0] if cl_ else "", "res": rs_[0] if rs_ else "", "ls": ri["n1"]} if ri else None
        res["hot"] = hot
        res["hot_src"] = newest["lst"][0]["k3"] if newest else ""
        res["hot_ts"] = newest["lst"][0]["ts"] if newest else ""
        try:
            md = mining.mining_data(c, (now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ"))
            ss = [x for x in md["sessions"] if x["ring"] == body]
            if ss:
                x = ss[-1]
                res["mining"] = {"tons": x["tons"], "tph": round(x["tph"]), "drones": sum(x["drones"].values()), "prosp": x["prosp"], "min": round(x["minutes"]),
                                 "ore": sorted(x["ore"].items(), key=lambda kv: -kv[1])[:5], "start": x["start"]}
        except Exception:
            pass
        res["cargo"] = {"count": out.get("cargo", {}).get("count"), "cap": (out.get("ship") or {}).get("cargo_cap")}
        return res
    if state == "Angedockt":
        r = c.execute("SELECT station, sys FROM jc WHERE station != '' ORDER BY last DESC LIMIT 1").fetchone()
        if r:
            nm, sy = r["station"], r["sys"] or sysn
            res = {"kind": "station", "title": nm, "sys": sy}
            n = c.execute("SELECT txt, ts FROM notes WHERE kind='station' AND name=?", (nm,)).fetchone()
            res["note"] = dict(n) if n else None
            sd = c.execute("SELECT type, faction, gov, eco, market_id FROM stdb WHERE name=? AND system=?", (nm, sy)).fetchone() or c.execute("SELECT type, faction, gov, eco, market_id FROM stdb WHERE name=?", (nm,)).fetchone()
            res["info"] = dict(sd) if sd else None
            mid = sd["market_id"] if sd and sd["market_id"] else (c.execute("SELECT market_id FROM station WHERE name=? AND system=?", (nm, sy)).fetchone() or [None])[0]
            pd = c.execute("SELECT s, m, l FROM pads WHERE market_id=?", (mid,)).fetchone() if mid else None
            res["pads"] = dict(pd) if pd else None
            ls = c.execute("SELECT COALESCE(MAX(seen), MAX(ts)) t FROM snap WHERE market_id=?", (mid,)).fetchone() if mid else None
            res["market_ts"] = ls["t"] if ls and ls["t"] else None
            res["market_h"] = ageof(res["market_ts"])
            done = {str(x[0]) for x in c.execute("SELECT y FROM ce WHERE kind='mis'")}
            ms = [r_ for r_ in c.execute("SELECT k1, k2, x, y, n1 FROM ce WHERE kind='mdet' AND k3=?", (nm,)) if r_["k1"] not in done]
            res["missions"] = len(ms)
            res["mission_cr"] = sum(r_["n1"] or 0 for r_ in ms)
            return res
    if body and state in ("Gelandet", "Im SRV", "Zu Fuß"):
        res = {"kind": "planet", "title": body, "sys": sysn}
        sc = c.execute("SELECT k2, x, y, n1 FROM ce WHERE kind='scan' AND k1=? ORDER BY ts DESC LIMIT 1", (body,)).fetchone()
        res["scan"] = {"cls": sc["k2"], "atm": sc["x"], "temp": sc["y"], "g": sc["n1"]} if sc else None
        b = None
        for v in bodydata.BODYDB.values():
            for bb in v["st"]["bodies"].values():
                if bb.get("full") == body:
                    b = bb
        res["sig"] = {k: b.get(k, 0) for k in ("bio", "geo", "human", "mining", "other")} if b else None
        bio = c.execute("SELECT k2, x FROM ce WHERE kind='bio' AND k3=? ORDER BY ts", (body,)).fetchall()
        res["bio_done"] = sorted({r["k2"] for r in bio})
        tc = c.execute("SELECT ts FROM ce WHERE kind='touch' AND k1=? ORDER BY ts DESC LIMIT 1", (body,)).fetchone()
        res["touch"] = tc["ts"] if tc else None
        return res
    return {"kind": "raum", "title": sysn or "-", "sys": sysn, "state": state, "body": body, "dest": out.get("dest")}


def cockpit_api(rng=0):
    d = config._journal_dir()
    if not d:
        return {"error": "Journal-Ordner nicht gefunden"}
    out = {"now": time.time()}
    sp = os.path.join(d, "Status.json")
    st = status._read_json_file(sp) or {}
    try:
        out["age"] = max(0, time.time() - os.path.getmtime(sp))
    except OSError:
        out["age"] = None
    f, f2 = st.get("Flags", 0) or 0, st.get("Flags2", 0) or 0
    mode = status.status_mode(st)
    flags = [[n, 1 if ("1", b) in status.FLAG_WARN else 0] for b, n in status.FLAG1.items() if f & (1 << b)]
    flags += [[n, 1 if ("2", b) in status.FLAG_WARN else 0] for b, n in status.FLAG2.items() if f2 & (1 << b) and b != 0]
    state = "Unbekannt"
    if mode == "foot":
        state = "Zu Fuß"
    elif mode == "srv":
        state = "Im SRV"
    elif mode == "ship":
        state = ("Angedockt" if f & 1 else "Gelandet" if f & 2 else "Supercruise" if f & 16 else
                 "Im Jäger" if f & (1 << 25) and not f & (1 << 24) else "Im Normalraum")
    out.update(mode=mode, state=state, flags=flags, pips=st.get("Pips"), legal=st.get("LegalState"),
               balance=st.get("Balance"), dest=(st.get("Destination") or {}).get("Name"), body=st.get("BodyName"),
               gui=st.get("GuiFocus"), fuel=st.get("Fuel"), cargo_t=st.get("Cargo"), health=st.get("Health"),
               oxygen=st.get("Oxygen"))
    c = database._mdb()
    try:
        r = c.execute("SELECT js FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC LIMIT 1").fetchone()
        lo = json.loads(r["js"]) if r else {}
        fc = lo.get("FuelCapacity")
        cap = fc.get("Main") if isinstance(fc, dict) else fc
        jr = [x["n2"] for x in c.execute("SELECT n2 FROM ce WHERE kind='jump' AND n2>0 ORDER BY ts DESC, id DESC LIMIT 10")]
        per = sum(jr) / len(jr) if jr else 0
        fm = (st.get("Fuel") or {}).get("FuelMain")
        out["ship"] = {"name": career_ingest.ship_name(lo) if lo else "", "ident": lo.get("ShipIdent", ""), "label": lo.get("ShipName", ""),
                       "range": lo.get("MaxJumpRange"), "cargo_cap": lo.get("CargoCapacity"), "fuel_cap": cap}
        # Sprungweite mit aktueller Masse: Loadout-Weite gilt bei Leermasse + Treibstoff fuer einen Maximalsprung (am Spiel geprueft)
        try:
            um, r0 = float(lo.get("UnladenMass") or 0), float(lo.get("MaxJumpRange") or 0)
            shp = career_ingest.ship_name(lo) if lo else ""
            fmx = c.execute("SELECT MAX(n2) m FROM ce WHERE kind='jump' AND ship=?", (shp,)).fetchone()["m"] or 0.0
            fnow = sum(float(x or 0) for x in (st.get("Fuel") or {}).values())
            if um > 0 and r0 > 0 and st.get("Fuel"):
                out["ship"]["range_now"] = r0 * (um + fmx) / (um + float(st.get("Cargo") or 0) + fnow)
                out["ship"]["range_est"] = fmx <= 0
        except Exception:
            pass
        out["fuelcalc"] = {"per_jump": per, "jumps": (fm / per) if (fm is not None and per) else None,
                           "pct": (fm / cap * 100) if (fm is not None and cap) else None}
        sysr = c.execute("SELECT sys FROM jc WHERE sys != '' ORDER BY last DESC LIMIT 1").fetchone()
        out["system"] = sysr["sys"] if sysr else ""
        cg = status._read_json_file(os.path.join(d, "Cargo.json")) or {}
        items = []
        total_v = 0
        dfn = helpers._dist_fn(c)
        for it in cg.get("Inventory", []) or []:
            nm = it.get("Name_Localised") or str(it.get("Name", "?")).title()
            rows = c.execute("SELECT " + database.MK_COLS + " " + database.MK_CURRENT + " AND (i.name = ? COLLATE NOCASE OR i.name = ? COLLATE NOCASE)",
                             (nm, str(it.get("Name", "")))).fetchall()
            best = None
            for x in rows:
                if not helpers._in_range(dfn(x["system"]), rng):
                    continue
                if x["sell"] > 0 and x["demand"] > 0 and (not best or x["sell"] > best["sell"]):
                    best = x
            cnt = it.get("Count", 0)
            if best:
                total_v += best["sell"] * cnt
            items.append({"name": nm, "count": cnt, "stolen": bool(it.get("Stolen")), "mission": bool(it.get("MissionID")),
                          "best": ({"price": best["sell"], "station": best["station"], "system": best["system"],
                                    "seen": best["seen"], "demand": best["demand"], "dist": dfn(best["system"])} if best else None)})
        out["cargo"] = {"vessel": cg.get("Vessel"), "count": cg.get("Count", 0), "items": items, "value": total_v}
        try:
            out["lage"] = lage_info(c, st, out)
        except Exception as exc:
            out["lage"] = {"kind": "fehler", "title": str(exc)}
        nv = status._read_json_file(os.path.join(d, "NavRoute.json")) or {}
        route, tot, prev, bad = [], 0.0, None, 0
        for s in nv.get("Route", []) or []:
            pos = s.get("StarPos") or [0, 0, 0]
            leg = (sum((a - b) ** 2 for a, b in zip(pos, prev)) ** 0.5) if prev else 0.0
            prev = pos
            tot += leg
            sc = s.get("StarClass", "") in status.SCOOPABLE
            bad += 0 if sc else 1
            route.append({"name": s.get("StarSystem", "?"), "cls": s.get("StarClass", ""), "leg": leg, "scoop": sc})
        # Aktuelle Position auf der Route: Das Spiel schreibt NavRoute.json nur beim Planen, nicht nach jedem Sprung.
        here_name = out.get("system") or helpers._posmap(c)[2] or ""
        idx = next((i for i, r in enumerate(route) if r["name"] == here_name), None)
        cur = idx if idx is not None else 0
        for i, r in enumerate(route):
            r["done"] = i < cur
            r["here"] = idx is not None and i == idx
        rest = route[cur + 1:]
        out["route"] = {"jumps": max(0, len(route) - 1), "dist": tot, "noscoop": bad, "items": route,
                        "on_route": idx is not None, "cur": cur, "here": here_name,
                        "rem_jumps": len(rest), "rem_dist": sum(r["leg"] for r in rest), "rem_noscoop": sum(0 if r["scoop"] else 1 for r in rest)}
        # Sprünge bis leer: Verbrauch je Sprung aus Distanz (Potenzgesetz aus eigenen letzten Sprüngen) entlang der Route,
        # danach Sprünge mit aktueller maximaler Sprungweite
        try:
            q = "SELECT n1, n2 FROM ce WHERE kind='jump' AND n1>0 AND n2>0 %s ORDER BY ts DESC, id DESC LIMIT 30"
            hist = []
            if out["ship"].get("name"):
                hist = [(x["n1"], x["n2"]) for x in c.execute(q % "AND ship=?", (out["ship"]["name"],))]
            if len(hist) < 3:
                hist = [(x["n1"], x["n2"]) for x in c.execute(q % "")]
            rng = out["ship"].get("range") or 0
            fm = (st.get("Fuel") or {}).get("FuelMain")
            if hist and fm is not None:
                import math
                pw, how = 2.0, "mean"
                ds = [h[0] for h in hist]
                if len(hist) >= 6 and max(ds) > 1.3 * min(ds):
                    lx = [math.log(h[0]) for h in hist]; ly = [math.log(h[1]) for h in hist]
                    mx, my = sum(lx) / len(lx), sum(ly) / len(ly)
                    vx = sum((a - mx) ** 2 for a in lx)
                    if vx > 1e-9:
                        pw = sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / vx
                        if 1.0 <= pw <= 3.5:
                            how = "fit"
                        else:
                            pw = 2.0
                if how == "fit":
                    kk = math.exp(my - pw * mx)
                else:
                    kk = None
                    pw = 2.0
                    avg = sum(h[1] for h in hist) / len(hist)
                    avd = sum(h[0] for h in hist) / len(hist)
                    kk = avg / (avd ** pw)
                need = lambda dd: kk * (dd ** pw)
                left, done = fm, 0
                legs = [r["leg"] for r in route[cur + 1:] if r["leg"] > 0]
                for lg in legs:
                    nd = need(lg)
                    if nd > left: break
                    left -= nd; done += 1
                full = (done == len(legs)) and bool(legs)
                extra = 0
                if (full or not legs) and rng:
                    nd = need(rng)
                    extra = int(left // nd) if nd > 0 else 0
                out["fuelcalc"].update(route_jumps=len(legs), route_done=done, route_full=full, extra=extra,
                                       left_after=left if full else 0, model=how, exp=round(pw, 2))
                # Planer: Verbrauch je Etappe, Rest ohne Scoopen, erster Engpass und letzter Scoop-Stern davor
                rt, left2, short = out["route"]["items"], fm, None
                for i, r in enumerate(rt):
                    if i < cur:  # schon geflogen: keine Berechnung mehr
                        r["fuel"], r["left"] = None, None
                        continue
                    if i == cur:
                        r["fuel"], r["left"] = 0.0, left2
                        continue
                    nd = need(r["leg"])
                    left2 -= nd
                    r["fuel"], r["left"] = nd, left2
                    if left2 < 0 and short is None:
                        short = i
                stop = None
                if short is not None:
                    stop = next((i for i in range(short - 1, cur - 1, -1) if rt[i]["scoop"]), None)
                out["route"].update(short=short, scoop_stop=stop, fuel_total=sum((r.get("fuel") or 0) for r in rt),
                                    per_tank=int(cap // need(rng)) if (cap and rng and need(rng) > 0) else None)
        except Exception:
            pass
        try:
            lots = c.execute("SELECT ts FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC LIMIT 1").fetchone()
            out["maint"] = _maint(c, st, out, lo, [lots["ts"]] if lots else [])
        except Exception as exc:
            out["maint"] = [{"label": "Wartung", "state": "warn", "text": "nicht auswertbar: " + str(exc)}]
    finally:
        c.close()
    return out
