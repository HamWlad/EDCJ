"""Markt-API (/api/market): Handel, Warenfinder, Rundkurse, Ausrüstung."""

from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import career_ingest, database, helpers, timefmt


def _capacity(lo, p):
    """(wirksame Menge, Frachtraum des Schiffs, eigene Menge): eine eigene Menge ersetzt den Frachtraum des aktuellen Schiffs."""
    ship = int(lo.get("CargoCapacity") or 0) if lo else 0
    try:
        own = max(0, min(100000, int(float(p.get("qty") or 0))))
    except (TypeError, ValueError):
        own = 0
    return (own or ship), ship, own


def market_api(p):
    op, c = p.get("op", ""), database._mdb()
    rows = lambda cur: [dict(r) for r in cur.fetchall()]
    try:
        if op == "stations":
            sysn = p.get("system", "")
            return {"stations": rows(c.execute("""SELECT s.market_id, s.name, s.system, s.type,
                (SELECT MAX(seen) FROM snap WHERE market_id=s.market_id) AS seen,
                (SELECT COUNT(*) FROM snap WHERE market_id=s.market_id) AS n,
                p.s AS pad_s, p.m AS pad_m, p.l AS pad_l,
                (SELECT txt FROM notes WHERE kind='station' AND name=s.name) AS note
                FROM station s LEFT JOIN pads p ON p.market_id=s.market_id WHERE (?='' OR s.system=?) ORDER BY seen DESC""", (sysn, sysn)))}
        if op == "snapshot":
            mid, sid = p.get("market_id"), p.get("snap")
            st = c.execute("SELECT st.*, p.s AS pad_s, p.m AS pad_m, p.l AS pad_l FROM station st LEFT JOIN pads p ON p.market_id=st.market_id WHERE st.market_id=?", (mid,)).fetchone()
            snap = (c.execute("SELECT id, ts, seen FROM snap WHERE id=? AND market_id=?", (sid, mid)).fetchone() if sid else
                    c.execute("SELECT id, ts, seen FROM snap WHERE market_id=? ORDER BY ts DESC, id DESC LIMIT 1", (mid,)).fetchone())
            if not snap:
                return {"station": dict(st) if st else None, "snaps": [], "items": [], "snap": None}
            return {"station": dict(st), "snap": dict(snap),
                    "snaps": rows(c.execute("SELECT id, ts, seen FROM snap WHERE market_id=? ORDER BY ts DESC", (mid,))),
                    "items": rows(c.execute("""SELECT cid, name, cat, buy, sell, mean, stock, demand FROM item
                                               WHERE snap_id=? ORDER BY name""", (snap["id"],))),
                    "cap": _capacity(helpers._cur_loadout(c), p)[0],
                    "best": helpers._best(rows(c.execute(f"SELECT {database.MK_COLS} {database.MK_CURRENT}")), mid, helpers._num_range(p.get("range")), helpers._dist_fn(c))}
        if op == "map":
            pos, here, hs = helpers._posmap(c)
            vis = {r["k1"]: r["n"] for r in c.execute("SELECT k1, COUNT(*) AS n FROM ce WHERE kind='jump' GROUP BY k1")}
            return {"points": [[nm, x, y, z, vis.get(nm, 0)] for nm, (x, y, z) in pos.items()],
                    "cur": ([hs] + list(here)) if here else None}
        if op == "modstations":
            return {"stations": rows(c.execute("SELECT market_id, name, system, MAX(ts) AS ts FROM modst GROUP BY market_id ORDER BY name COLLATE NOCASE"))}
        if op == "mods":
            kind = p.get("kind", "")
            where, args = ["1=1"], []
            if kind in ("m", "s"):
                where.append("m.kind=?"); args.append(kind)
            if p.get("scope") != "all":
                where.append("m.market_id=?"); args.append(p.get("market_id"))
            allrows = rows(c.execute("""SELECT m.market_id, m.kind, m.code, m.label, m.cat, m.cls, m.price, m.merc, t.name AS station, t.system, t.ts,
                    pd.s AS pad_s, pd.m AS pad_m, pd.l AS pad_l FROM gear m JOIN modst t ON t.market_id=m.market_id AND t.kind=m.kind
                    LEFT JOIN pads pd ON pd.market_id=m.market_id WHERE """ + " AND ".join(where), args))
            labels = sorted({r["label"] for r in allrows}, key=str.lower)
            toks = (p.get("q") or "").lower().split()
            dfn, lim = helpers._dist_fn(c), (helpers._num_range(p.get("range")) if p.get("scope") == "all" else 0)
            out = []
            for r in allrows:
                if toks and not all(t in (r["label"] + " " + r["code"] + " " + r["cat"] + " " + r["cls"]).lower() for t in toks):
                    continue
                r["dist"] = dfn(r["system"])
                if helpers._in_range(r["dist"], lim):
                    out.append(r)
            grp_all = {}
            for g in c.execute("SELECT kind, label, cls, price, merc FROM gear"):
                if (g["price"] or 0) > 0 or (g["merc"] or 0) > 0:
                    grp_all.setdefault((g["kind"], g["label"], g["cls"], (g["merc"] or 0) > 0), []).append(g["merc"] if g["merc"] else g["price"])
            grp_in = {}
            for r in out:
                v = r["merc"] if r["merc"] else r["price"]
                if v > 0:
                    grp_in.setdefault((r["kind"], r["label"], r["cls"], r["merc"] > 0), []).append(v)
            for r in out:
                k = (r["kind"], r["label"], r["cls"], r["merc"] > 0)
                v = r["merc"] if r["merc"] else r["price"]
                allv = grp_all.get(k, [])
                r["avg"] = sum(allv) / len(allv) if len(allv) >= 2 else None
                r["n_all"] = len(allv)
                r["dpct"] = (v - r["avg"]) / r["avg"] * 100 if r["avg"] and v > 0 else None
                r["cheapest"] = bool(v > 0 and len(grp_in.get(k, [])) > 1 and v == min(grp_in[k]))
            out.sort(key=lambda r: (r["label"].lower(), r["cls"], r["merc"] > 0, r["price"] or r["merc"], r["dist"] is None, r["dist"] or 0))
            return {"rows": out[:3000], "total": len(out), "labels": labels}
        if op == "commodities":
            mid = p.get("market_id", "")
            return {"items": rows(c.execute("""SELECT DISTINCT i.name, i.cat FROM item i JOIN snap s ON s.id=i.snap_id
                                               WHERE (?='' OR s.market_id=?) ORDER BY i.name""", (mid, mid)))}
        if op == "history":
            return {"points": rows(c.execute("""SELECT s.ts, s.seen, i.buy, i.sell, i.mean, i.stock, i.demand
                FROM item i JOIN snap s ON s.id=i.snap_id WHERE s.market_id=? AND i.name=? AND s.ts>=? ORDER BY s.ts""",
                                             (p.get("market_id"), p.get("commodity"), helpers._cutoff(p.get("days")))))}
        if op == "fdetail":
            return {"points": rows(c.execute("""SELECT ts, inf, state, active, gov, rep, ctrl FROM fac
                WHERE system=? AND name=? AND ts>=? ORDER BY ts""", (p.get("system"), p.get("name"), helpers._cutoff(p.get("days")))))}
        if op == "station_table":
            cut = helpers._cutoff(p.get("days"))
            res = rows(c.execute("""SELECT s.ts, s.seen, i.name, i.cat, i.buy, i.sell, i.stock, i.demand, i.mean
                FROM item i JOIN snap s ON s.id=i.snap_id WHERE s.market_id=? AND s.ts>=? ORDER BY s.ts DESC, i.name LIMIT 6001""",
                                 (p.get("market_id"), cut)))
            return {"rows": res[:6000], "total": len(res)}
        if op == "fsystems":
            return {"systems": rows(c.execute("""SELECT system, MAX(ts) AS last, COUNT(DISTINCT ts) AS n FROM fac
                                                  GROUP BY system ORDER BY last DESC"""))}
        if op == "sysstations":
            sysn = p.get("system", "")
            last = c.execute("SELECT MAX(ts) m FROM fac WHERE system=?", (sysn,)).fetchone()["m"]
            facs = rows(c.execute("SELECT name, ctrl FROM fac WHERE system=? AND ts=? ORDER BY ctrl DESC, inf DESC", (sysn, last))) if last else []
            sts = rows(c.execute("SELECT name, type, faction, via, last FROM stdb WHERE system=? ORDER BY name COLLATE NOCASE", (sysn,)))
            ctrl = next((f["name"] for f in facs if f["ctrl"]), "")
            for x in sts:
                x["ctrl"] = bool(ctrl and x["faction"] == ctrl)
            return {"system": sysn, "stations": sts, "factions": [f["name"] for f in facs], "ctrl": ctrl}
        if op == "fhistory":
            sysn, cut = p.get("system", ""), helpers._cutoff(p.get("days"))
            allr = rows(c.execute("SELECT ts, name, inf, state, active, gov, rep, ctrl FROM fac WHERE system=? ORDER BY ts", (sysn,)))
            if not allr:
                return {"system": sysn, "rows": [], "summary": [], "latest": None, "n_measure": 0}
            latest = max(r["ts"] for r in allr)
            now = {r["name"]: r for r in allr if r["ts"] == latest}
            prev, hist, series = {}, [], {}
            pct = lambda a, b: round((a - b) / b * 100, 1) if b else None
            for r in allr:  # aufsteigend: "davor" je Fraktion
                pv = prev.get(r["name"])
                r["d_prev"] = round(r["inf"] - pv, 2) if pv is not None else None
                prev[r["name"]] = r["inf"]
                n = now.get(r["name"])
                r["d_now"] = round(n["inf"] - r["inf"], 2) if n else None
                r["d_now_pct"] = pct(n["inf"], r["inf"]) if n else None
                series.setdefault(r["name"], []).append(r)
                if r["ts"] >= cut:
                    hist.append(r)
            hist.sort(key=lambda r: (r["ts"], r["inf"]), reverse=True)
            summ = []
            for name, n in sorted(now.items(), key=lambda kv: -kv[1]["inf"]):
                sr = series[name]
                pr = sr[-2] if len(sr) >= 2 else None
                inr = [r for r in sr if r["ts"] >= cut]
                fi = inr[0] if inr and inr[0]["ts"] != latest else None
                mk_ = lambda r: {"inf": r["inf"], "ts": r["ts"], "d_pp": round(n["inf"] - r["inf"], 2), "d_pct": pct(n["inf"], r["inf"])} if r else None
                summ.append({"name": name, "state": n["state"], "active": n["active"], "ctrl": n["ctrl"], "now": n["inf"],
                             "prev": mk_(pr), "first": mk_(fi), "n": len(inr)})
            return {"system": sysn, "latest": latest, "rows": hist[:3000], "summary": summ,
                    "n_measure": len({r["ts"] for r in hist})}
        if op == "trades":
            lo = helpers._cur_loadout(c)
            cap, ship_cap, own_qty = _capacity(lo, p)
            need = helpers._ship_need(lo.get("Ship", ""))
            padmode = p.get("pad", "loose")
            lim, leg, maxage = helpers._num_range(p.get("range")), helpers._num_range(p.get("leg")), helpers._num_range(p.get("age"))
            pos, here, _cs = helpers._posmap(c)
            pads = {r["market_id"]: (r["s"], r["m"], r["l"]) for r in c.execute("SELECT market_id, s, m, l FROM pads")}
            now = datetime.now(timezone.utc)
            age_h = lambda iso: max(0.0, (now - timefmt.parse_ts(iso)).total_seconds() / 3600) if iso else 1e9

            def padok(mid):
                f = helpers._pad_fits(need, pads.get(mid))
                return True if padmode == "off" or f is True else (f is None and padmode == "loose")
            byn = {}
            for r in rows(c.execute(f"SELECT {database.MK_COLS} {database.MK_CURRENT}")):
                r["age"] = age_h(r["seen"])
                r["pad"] = pads.get(r["market_id"])
                r["dme"] = helpers._d3(here, pos.get(r["system"]))
                if (maxage and r["age"] > maxage) or not padok(r["market_id"]):
                    continue
                byn.setdefault(r["name"], []).append(r)
            res = []

            def side(r, dist):
                return {"price": r["buy"] if dist is None else r["sell"], "station": r["station"], "system": r["system"], "seen": r["seen"],
                        "market_id": r["market_id"], "pad": r["pad"], "age": r["age"]}
            for name, rs in byn.items():
                cand = []
                for b in (r for r in rs if r["buy"] > 0 and r["stock"] > 0 and helpers._in_range(r["dme"], lim)):
                    for sl in (r for r in rs if r["sell"] > 0 and r["demand"] > 0 and r["market_id"] != b["market_id"]):
                        dl = 0.0 if b["system"] == sl["system"] else helpers._d3(pos.get(b["system"]), pos.get(sl["system"]))
                        if not helpers._in_range(dl, leg):
                            continue
                        pr = sl["sell"] - b["buy"]
                        if pr <= 0:
                            continue
                        q = min(b["stock"], sl["demand"], cap) if cap else min(b["stock"], sl["demand"])
                        cand.append((pr * q if cap else pr, pr, q, b, sl, dl))
                cand.sort(key=lambda t: -t[0])
                for _k, pr, q, b, sl, dl in cand[:3]:
                    bs, ss = side(b, None), side(sl, 1)
                    bs.update(qty=b["stock"], dist=b["dme"])
                    ss.update(qty=sl["demand"], dist=dl)
                    tot = pr * q if cap else None
                    res.append({"name": name, "cat": b["cat"], "profit": pr, "qty": q if cap else None, "total": tot, "buy": bs, "sell": ss,
                                "leg": dl, "ly_t": (pr / dl) if dl else None, "ly": (tot / dl) if (dl and cap) else None,
                                "age": max(b["age"], sl["age"])})
            res.sort(key=lambda t: -(t["total"] if cap else t["profit"]))
            return {"trades": res[:300], "ctx": {"cap": cap, "ship_cap": ship_cap, "own": own_qty, "ship": career_ingest.ship_name(lo) if lo else "", "need": helpers.PAD_NAME.get(need, ""),
                                                 "pos": here is not None}}
        if op == "loops":
            lo = helpers._cur_loadout(c)
            cap, ship_cap, own_qty = _capacity(lo, p)
            need = helpers._ship_need(lo.get("Ship", ""))
            padmode = p.get("pad", "loose")
            lim, leg, maxage = helpers._num_range(p.get("range")), helpers._num_range(p.get("leg")), helpers._num_range(p.get("age"))
            pos, here, _cs = helpers._posmap(c)
            pads = {r["market_id"]: (r["s"], r["m"], r["l"]) for r in c.execute("SELECT market_id, s, m, l FROM pads")}
            now = datetime.now(timezone.utc)
            age_h = lambda iso: max(0.0, (now - timefmt.parse_ts(iso)).total_seconds() / 3600) if iso else 1e9
            sts = {}
            for r in rows(c.execute(f"SELECT {database.MK_COLS} {database.MK_CURRENT}")):
                f_ = helpers._pad_fits(need, pads.get(r["market_id"]))
                if padmode != "off" and not (f_ is True or (f_ is None and padmode == "loose")):
                    continue
                r["age"] = age_h(r["seen"])
                if maxage and r["age"] > maxage:
                    continue
                o = sts.setdefault(r["market_id"], {"st": r["station"], "sy": r["system"], "pad": pads.get(r["market_id"]), "age": 0, "it": {},
                                                   "dme": helpers._d3(here, pos.get(r["system"]))})
                o["it"][r["name"]] = r
                o["age"] = max(o["age"], r["age"])
            ids = list(sts)[:600]

            def bestleg(a, b):
                bst = None
                for nm, ia in a["it"].items():
                    ib = b["it"].get(nm)
                    if not ib or ia["buy"] <= 0 or ia["stock"] <= 0 or ib["sell"] <= 0 or ib["demand"] <= 0:
                        continue
                    pr = ib["sell"] - ia["buy"]
                    if pr <= 0:
                        continue
                    q = min(ia["stock"], ib["demand"], cap) if cap else min(ia["stock"], ib["demand"])
                    key = pr * q if cap else pr
                    if bst is None or key > bst[0]:
                        bst = (key, nm, pr, q, ia["buy"], ib["sell"])
                return bst
            res = []
            for i, ma in enumerate(ids):
                for mb in ids[i + 1:]:
                    a, b = sts[ma], sts[mb]
                    if not (helpers._in_range(a["dme"], lim) or helpers._in_range(b["dme"], lim)):
                        continue
                    dl = 0.0 if a["sy"] == b["sy"] else helpers._d3(pos.get(a["sy"]), pos.get(b["sy"]))
                    if not helpers._in_range(dl, leg):
                        continue
                    o1, o2 = bestleg(a, b), bestleg(b, a)
                    if not o1 or not o2:
                        continue
                    if (b["dme"] is not None and (a["dme"] is None or b["dme"] < a["dme"])):
                        a, b, o1, o2 = b, a, o2, o1
                    tot = (o1[2] * o1[3] + o2[2] * o2[3]) if cap else None
                    res.append({"a": {"station": a["st"], "system": a["sy"], "pad": a["pad"], "dist": a["dme"]},
                                "b": {"station": b["st"], "system": b["sy"], "pad": b["pad"], "dist": b["dme"]}, "leg": dl,
                                "out": {"name": o1[1], "profit": o1[2], "qty": o1[3], "buy": o1[4], "sell": o1[5]},
                                "back": {"name": o2[1], "profit": o2[2], "qty": o2[3], "buy": o2[4], "sell": o2[5]},
                                "total": tot, "trip": 2 * dl,
                                "in_ly": (tot / (a["dme"] + 2 * dl)) if (cap and a["dme"] is not None and (a["dme"] + 2 * dl) > 0) else None,
                                "in_ly_t": ((o1[2] + o2[2]) / (a["dme"] + 2 * dl)) if (a["dme"] is not None and (a["dme"] + 2 * dl) > 0) else None,
                                "per_ly": (tot / (2 * dl)) if (dl and cap) else None, "ly_t": ((o1[2] + o2[2]) / (2 * dl)) if dl else None, "age": max(a["age"], b["age"]),
                                "sum_t": o1[2] + o2[2]})
            res.sort(key=lambda t: -(t["total"] if cap else t["sum_t"]))
            return {"loops": res[:200], "ctx": {"cap": cap, "ship_cap": ship_cap, "own": own_qty, "ship": career_ingest.ship_name(lo) if lo else "", "need": helpers.PAD_NAME.get(need, ""), "pos": here is not None,
                                                 "n": len(ids)}}
        if op == "compare":
            lo = helpers._cur_loadout(c)
            cap, ship_cap, own_qty = _capacity(lo, p)
            try:
                free = max(0, min(100000, int(float(p.get("free") or 0))))
            except (TypeError, ValueError):
                free = 0
            room = free or cap
            now = datetime.now(timezone.utc)
            age_h = lambda iso: max(0.0, (now - timefmt.parse_ts(iso)).total_seconds() / 3600) if iso else 1e9
            pos, here, _cs = helpers._posmap(c)
            sts, its = {}, {}
            for key in ("a", "b"):
                mid = p.get(key, "")
                st = c.execute("SELECT st.market_id, st.name, st.system, st.type, p.s AS pad_s, p.m AS pad_m, p.l AS pad_l FROM station st LEFT JOIN pads p ON p.market_id=st.market_id WHERE st.market_id=?", (mid,)).fetchone()
                sts[key] = dict(st) if st else None
                its[key] = {r["name"]: r for r in rows(c.execute(f"SELECT {database.MK_COLS} {database.MK_CURRENT} AND s.market_id=?", (mid,)))} if st else {}
            if not (sts["a"] and sts["b"]):
                return {"ok": False, "stations": sts}

            def leg(x, y):
                ia, ib = its[x], its[y]
                out = []
                for nm, a in ia.items():
                    b = ib.get(nm)
                    if not b or a["buy"] <= 0 or a["stock"] <= 0 or b["sell"] <= 0 or b["demand"] <= 0:
                        continue
                    pr = b["sell"] - a["buy"]
                    if pr <= 0:
                        continue
                    out.append({"name": nm, "cat": a["cat"], "buy": a["buy"], "stock": a["stock"], "sell": b["sell"], "demand": b["demand"],
                                "profit": pr, "max": min(a["stock"], b["demand"])})
                out.sort(key=lambda t: -t["profit"])
                left = room
                for t in out:
                    t["qty"] = min(t["max"], left) if room else 0
                    left -= t["qty"]
                    t["total"] = t["qty"] * t["profit"]
                return {"items": out, "total": sum(t["total"] for t in out), "used": (room - left) if room else 0,
                        "cost": sum(t["qty"] * t["buy"] for t in out)}
            ages = {}
            for k in ("a", "b"):
                sn = c.execute("SELECT MAX(seen) AS s FROM snap WHERE market_id=?", (p.get(k),)).fetchone()
                ages[k] = {"seen": sn["s"], "age": age_h(sn["s"])}
            dl = 0.0 if sts["a"]["system"] == sts["b"]["system"] else helpers._d3(pos.get(sts["a"]["system"]), pos.get(sts["b"]["system"]))
            return {"ok": True, "stations": sts, "ages": ages, "dist": dl, "ab": leg("a", "b"), "ba": leg("b", "a"),
                    "ctx": {"room": room, "free": free, "cap": cap, "ship_cap": ship_cap, "own": own_qty, "ship": career_ingest.ship_name(lo) if lo else ""}}
        if op == "commodity":
            res = rows(c.execute(f"SELECT {database.MK_COLS} {database.MK_CURRENT} AND i.name=?", (p.get("name", ""),)))
            dfn = helpers._dist_fn(c)
            for r in res:
                r["dist"] = dfn(r["system"])
            return {"rows": res}
        if op == "search":
            terms = [t for t in p.get("q", "").lower().split() if t][:6]
            if not terms:
                return {"total": 0, "results": [], "terms": []}
            cond = " AND lower(i.name||' '||i.cat||' '||st.name||' '||st.system) LIKE ?" * len(terms)
            res = rows(c.execute(f"SELECT {database.MK_COLS} {database.MK_LATEST}{cond} ORDER BY s.seen DESC LIMIT 301", [f"%{t}%" for t in terms]))
            return {"total": len(res), "results": res[:300], "terms": terms, "more": len(res) > 300}
        return {"error": "unbekannte Abfrage"}
    finally:
        c.close()
