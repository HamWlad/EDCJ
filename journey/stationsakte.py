"""Stationsakte: Steckbrief, Preis-Check gegen den eigenen Verlauf und Erholungs-Tempo. Nur eigene gespeicherte Daten."""

import statistics
from datetime import datetime, timezone

from . import database, timefmt

SERVICES = {"commodities": "Warenmarkt", "outfitting": "Ausrüster", "shipyard": "Werft", "refuel": "Tanken", "repair": "Reparatur", "rearm": "Munition",
            "missions": "Missionen", "crewlounge": "Crew-Lounge", "engineer": "Ingenieur", "tuning": "Tuning", "exploration": "Erkundungsdaten",
            "searchrescue": "Bergung", "powerplay": "Powerplay", "blackmarket": "Schwarzmarkt", "materialtrader": "Materialhändler",
            "techBroker": "Technikhändler", "facilitator": "Vermittler", "shop": "Laden", "livery": "Lackierung", "carrierfuel": "Carrier-Treibstoff",
            "carriermanagement": "Carrier-Verwaltung", "voucherredemption": "Gutscheine einlösen", "contacts": "Kontakte", "bartender": "Bar",
            "vistagenomics": "Vista Genomics", "pioneersupplies": "Pioneer Supplies", "apexinterstellar": "Apex Interstellar", "modulepacks": "Modulpakete",
            "socialspace": "Aufenthaltsbereich", "registeringcolonisation": "Kolonisierung"}
_HIDE = {"dock", "autodock", "flightcontroller", "stationoperations", "stationMenu", "missionsgenerated", "stationmenu"}


def _hours(a, b):
    try:
        return (timefmt.parse_ts(b) - timefmt.parse_ts(a)).total_seconds() / 3600
    except Exception:
        return 0.0


def _key(sysn, name):
    return f"{sysn}|{name}"


def _stations(c):
    out = {}
    for r in c.execute("SELECT system, name, market_id, type, last FROM stdb"):
        out[_key(r["system"], r["name"])] = {"key": _key(r["system"], r["name"]), "system": r["system"], "name": r["name"], "mid": r["market_id"] or 0,
                                              "type": r["type"], "last": r["last"]}
    for r in c.execute("SELECT market_id, name, system, type, last_ts FROM station"):
        k = _key(r["system"], r["name"])
        o = out.setdefault(k, {"key": k, "system": r["system"], "name": r["name"], "mid": r["market_id"], "type": r["type"], "last": r["last_ts"]})
        o["mid"] = o["mid"] or r["market_id"]
        o["market"] = True
    for r in c.execute("SELECT market_id, COUNT(*) n FROM snap GROUP BY market_id"):
        for o in out.values():
            if o["mid"] == r["market_id"]:
                o["snaps"] = r["n"]
    return out


def _series(c, mid):
    """Pro Ware die Aufnahmen (aufsteigend): (ts, buy, sell, stock, demand, mean)."""
    res = {}
    for r in c.execute("""SELECT s.ts, i.name, i.cat, i.buy, i.sell, i.stock, i.demand, i.mean FROM item i JOIN snap s ON s.id=i.snap_id
                          WHERE s.market_id=? ORDER BY s.ts, s.id""", (mid,)):
        res.setdefault(r["name"], {"cat": r["cat"], "pts": []})["pts"].append((r["ts"], r["buy"], r["sell"], r["stock"], r["demand"], r["mean"]))
    return res


def _trades(c):
    """Eigene Kaeufe und Verkaeufe (Journal) je (Station, System): Liste (ts, Ware, 'buy'|'sell', Menge), aufsteigend."""
    res = {}
    for r in c.execute("SELECT ts, k1, k2, k3, n1, sys FROM ce WHERE kind='trade' AND n1>0 ORDER BY ts"):
        res.setdefault((r["k2"], r["sys"]), []).append((r["ts"], r["k1"], r["k3"], r["n1"]))
    return res


def _recoveries(pts, kind, trades, comm):
    """Erholung nach DEINEM Kauf (Bestand) bzw. Verkauf (Nachfrage): Menge vor dem Handel laut letzter Aufnahme davor, Erwartung nach dem Handel
    (vorher minus gehandelt), Vergleich mit den Aufnahmen danach. Das Spiel schreibt den Markt nur beim Oeffnen, daher entsteht die Aufnahme danach erst beim naechsten Besuch."""
    idx = 3 if kind == "buy" else 4
    mine = [t for t in trades if t[1] == comm and t[2] == kind]
    ev = []
    for n, (ts, _c, _k, q) in enumerate(mine):
        pre = [p for p in pts if p[0] <= ts]
        if not pre or _hours(pre[-1][0], ts) > 6 or pre[-1][idx] <= 0:
            continue
        l0 = pre[-1][idx]
        low = max(0, l0 - q)
        nxt = mine[n + 1][0] if n + 1 < len(mine) else "9"
        later = [p for p in pts if p[0] > ts and _hours(ts, p[0]) >= 0.25 and p[0] < nxt]
        if not later:
            continue
        hit = next((p for p in later if p[idx] >= l0 * 0.95), None)
        p = hit or later[-1]
        h = _hours(ts, p[0])
        taken = min(q, l0)
        gain = min(taken, max(0, p[idx] - low))  # mehr als das Genommene zaehlt nicht als Erholung (Markt kann sich auch sonst verschieben)
        ev.append({"ts": p[0], "hours": round(h, 1), "taken": taken, "gain": gain, "rate": gain / h if h > 0 else 0.0, "before": l0, "low": low, "after": p[idx], "full": hit is not None})
    return ev


def _rec_summary(name, kind, ev):
    if not ev:
        return None
    rates = [e["rate"] for e in ev]
    full = [e for e in ev if e["full"]]
    last = max(ev, key=lambda e: e["ts"])
    return {"name": name, "kind": "Bestand" if kind == "buy" else "Nachfrage", "n": len(ev), "rate": round(statistics.median(rates), 1),
            "taken": round(statistics.median(e["taken"] for e in ev)), "full_n": len(full), "full_h": round(statistics.median(e["hours"] for e in full), 1) if full else None,
            "last": last["ts"], "last_ev": last}


def _all_means(c):
    """Eigener Durchschnitt je Ware ueber alle zuletzt gespeicherten Stationen (Verkauf: Nachfrage > 0, Einkauf: Bestand > 0)."""
    sell, buy = {}, {}
    for r in c.execute(f"SELECT i.name, i.buy, i.sell, i.stock, i.demand, s.market_id {database.MK_CURRENT}"):
        if r["sell"] > 0 and r["demand"] > 0:
            sell.setdefault(r["name"], []).append(r["sell"])
        if r["buy"] > 0 and r["stock"] > 0:
            buy.setdefault(r["name"], []).append(r["buy"])
    return ({k: statistics.mean(v) for k, v in sell.items() if len(v) >= 3}, {k: statistics.mean(v) for k, v in buy.items() if len(v) >= 3})


def stationsakte_api(q):
    c = database._mdb()
    try:
        op = q.get("op", "list")
        sts = _stations(c)
        if op == "list":
            lst = sorted(sts.values(), key=lambda s: ((s["system"] or "").lower(), (s["name"] or "").lower()))
            return {"stations": [{"key": s["key"], "system": s["system"], "name": s["name"], "type": s["type"], "market": bool(s.get("snaps"))} for s in lst]}
        if op == "recovery_all":
            tr, res = _trades(c), []
            for s in sts.values():
                mine = tr.get((s["name"], s["system"]))
                if not mine or not s.get("snaps"):
                    continue
                ser = _series(c, s["mid"])
                for comm in {t[1] for t in mine}:
                    for kind in ("buy", "sell"):
                        r = _rec_summary(comm, kind, _recoveries(ser.get(comm, {"pts": []})["pts"], kind, mine, comm))
                        if r:
                            r.pop("last_ev")
                            r.update(station=s["name"], system=s["system"], key=s["key"])
                            res.append(r)
            res.sort(key=lambda r: (-r["n"], r["station"], r["name"]))
            return {"rows": res[:80]}
        s = sts.get(q.get("key", ""))
        if not s:
            return {"error": "Station nicht gefunden."}
        name, sysn, mid = s["name"], s["system"], s["mid"]
        sd = c.execute("SELECT type, faction, gov, eco, dist, via, first, last FROM stdb WHERE name=? AND system=?", (name, sysn)).fetchone()
        visits = c.execute("SELECT COUNT(*) n, MIN(ts) f, MAX(ts) l FROM ce WHERE kind='stn' AND k1=? AND sys=?", (name, sysn)).fetchone()
        pad = c.execute("SELECT s, m, l FROM pads WHERE market_id=?", (mid,)).fetchone() if mid else None
        sv = c.execute("SELECT x FROM ce WHERE kind='svc' AND k1=? AND sys=? ORDER BY ts DESC LIMIT 1", (name, sysn)).fetchone()
        services = sorted({SERVICES.get(x, "") for x in (sv["x"].split(",") if sv else []) if x not in _HIDE} - {""})
        note = c.execute("SELECT txt, ts FROM notes WHERE kind='station' AND name=?", (name,)).fetchone()
        card = {"key": s["key"], "name": name, "system": sysn, "type": (sd["type"] if sd else s["type"]) or "", "faction": sd["faction"] if sd else "", "gov": sd["gov"] if sd else "",
                "eco": sd["eco"] if sd else "", "dist_ls": sd["dist"] if sd else None, "via": sd["via"] if sd else "", "first": (sd["first"] if sd else None) or visits["f"],
                "last": (sd["last"] if sd else None) or visits["l"], "visits": visits["n"], "pads": dict(pad) if pad else None, "services": services,
                "services_known": bool(sv), "note": dict(note) if note else None}
        res = {"card": card, "market": None, "prices": [], "good_sell": [], "good_buy": [], "trades": [], "recovery": []}
        tr = {}
        for r in c.execute("SELECT k1, k3, n1, n2, n3 FROM ce WHERE kind='trade' AND k2=?", (name,)):
            t = tr.setdefault(r["k1"], {"name": r["k1"], "bought": 0, "sold": 0, "profit": 0, "spent": 0, "earned": 0})
            if r["k3"] == "buy":
                t["bought"] += r["n1"]
                t["spent"] += r["n2"]
            else:
                t["sold"] += r["n1"]
                t["earned"] += r["n2"]
                t["profit"] += r["n3"]
        res["trades"] = sorted(({**t, "bought": int(t["bought"]), "sold": int(t["sold"])} for t in tr.values()), key=lambda t: -t["profit"])[:20]
        if not (mid and s.get("snaps")):
            return res
        ser = _series(c, mid)
        last_ts = max((d["pts"][-1][0] for d in ser.values()), default=None)
        res["market"] = {"snaps": s["snaps"], "last": last_ts, "first": min((d["pts"][0][0] for d in ser.values()), default=None),
                         "age_h": round(_hours(last_ts, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")), 1) if last_ts else None}
        smean, bmean = _all_means(c)
        prices, gsell, gbuy = [], [], []
        for nm, d in ser.items():
            now = d["pts"][-1]
            if now[0] != last_ts:
                continue
            hist = d["pts"][:-1]
            hs = [p[2] for p in hist if p[2] > 0]
            hb = [p[1] for p in hist if p[1] > 0]
            row = {"name": nm, "cat": d["cat"], "buy": now[1], "sell": now[2], "stock": now[3], "demand": now[4], "n": len(d["pts"])}
            if now[2] > 0 and now[4] > 0 and len(hs) >= 2:
                row.update(sell_avg=round(statistics.mean(hs)), sell_min=min(hs + [now[2]]), sell_max=max(hs + [now[2]]), sell_dev=round((now[2] / statistics.mean(hs) - 1) * 100, 1))
            if now[1] > 0 and now[3] > 0 and len(hb) >= 2:
                row.update(buy_avg=round(statistics.mean(hb)), buy_min=min(hb + [now[1]]), buy_max=max(hb + [now[1]]), buy_dev=round((now[1] / statistics.mean(hb) - 1) * 100, 1))
            if "sell_dev" in row or "buy_dev" in row:
                prices.append(row)
            if now[2] > 0 and now[4] > 0:
                base, src = (smean.get(nm), "eigener Schnitt") if nm in smean else ((now[5], "Spiel-Mittelpreis") if now[5] > 0 else (None, ""))
                if base:
                    gsell.append({"name": nm, "price": now[2], "demand": now[4], "base": round(base), "dev": round((now[2] / base - 1) * 100, 1), "src": src})
            if now[1] > 0 and now[3] > 0:
                base, src = (bmean.get(nm), "eigener Schnitt") if nm in bmean else ((now[5], "Spiel-Mittelpreis") if now[5] > 0 else (None, ""))
                if base:
                    gbuy.append({"name": nm, "price": now[1], "stock": now[3], "base": round(base), "dev": round((now[1] / base - 1) * 100, 1), "src": src})
        res["prices"] = sorted(prices, key=lambda r: -max(abs(r.get("sell_dev", 0)), abs(r.get("buy_dev", 0))))[:40]
        res["good_sell"] = sorted(gsell, key=lambda r: -(r["price"] - r["base"]))[:8]
        res["good_buy"] = sorted(gbuy, key=lambda r: r["price"] - r["base"])[:8]
        rec = []
        mine = _trades(c).get((name, sysn), [])
        for comm in {t[1] for t in mine}:
            for kind in ("buy", "sell"):
                r = _rec_summary(comm, kind, _recoveries(ser.get(comm, {"pts": []})["pts"], kind, mine, comm))
                if r:
                    rec.append(r)
        for r in rec:
            r.pop("last_ev", None)
        res["recovery"] = sorted(rec, key=lambda r: (-r["n"], r["name"]))[:30]
        return res
    finally:
        c.close()
