"""Mining-Auswertung."""

from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import database, helpers, timefmt
from . import timefmt as _tf


def _clean_min(x):
    return str(x or "").strip().lower()


def mining_data(c, cut):
    """Sessions und Kennzahlen des Bergbaus aus den Karriere-Ereignissen."""
    W, A = (" AND ts >= ?", (cut,)) if cut else ("", ())
    rows = c.execute(f"SELECT ts, file, pos, kind, sys, ship, k1, k2, k3, n1, n2, n3 FROM ce WHERE kind IN ('mine','prosp','drone','crack') {W} ORDER BY ts, file, pos", A).fetchall()
    pm = {}
    for r in c.execute(f"SELECT file, pos, k1, k2, n1 FROM ce WHERE kind='pmat' {W}", A):
        pm.setdefault((r["file"], r["pos"]), []).append((r["k1"], r["n1"]))
    sess, cur = [], None
    for r in rows:
        ring = r["k2"] if r["kind"] in ("mine", "drone") else r["k2"] if r["kind"] == "prosp" else r["k1"]
        t = timefmt.parse_ts(r["ts"])
        new = cur is None or (t - cur["last_t"]).total_seconds() > 1200 or (ring and cur["ring"] and ring != cur["ring"])
        if new:
            cur = {"start": r["ts"], "start_t": t, "last_t": t, "end": r["ts"], "ring": ring or "", "sys": r["sys"], "ship": r["ship"],
                   "ore": {}, "tons": 0, "drones": {}, "prosp": 0, "content": {}, "cracks": 0, "last_mine": None, "first_mine": None,
                   "pm": []}
            sess.append(cur)
        cur["last_t"] = t
        cur["end"] = r["ts"]
        if ring and not cur["ring"]:
            cur["ring"] = ring
        if r["kind"] == "mine":
            cur["tons"] += 1
            cur["ore"][r["k1"]] = cur["ore"].get(r["k1"], 0) + 1
            cur["last_mine"] = t
            cur["first_mine"] = cur["first_mine"] or t
        elif r["kind"] == "drone":
            cur["drones"][r["k1"]] = cur["drones"].get(r["k1"], 0) + 1
        elif r["kind"] == "prosp":
            cur["prosp"] += 1
            cur["content"][r["k1"]] = cur["content"].get(r["k1"], 0) + 1
            cur["pm"].append(pm.get((r["file"], r["pos"]), []))
        elif r["kind"] == "crack":
            cur["cracks"] += 1
    for x in sess:
        end = x["last_mine"] or x["last_t"]
        x["minutes"] = max(0.0, (end - x["start_t"]).total_seconds() / 60.0)
        x["tph"] = x["tons"] / (x["minutes"] / 60.0) if x["minutes"] >= 1 and x["tons"] else 0
    buy = c.execute(f"SELECT SUM(n1) AS n, SUM(n2) AS cr FROM ce WHERE kind='dbuy'").fetchone()
    price = (buy["cr"] / buy["n"]) if buy and buy["n"] else 0
    return {"sessions": sess, "drone_price": price}


def mining_view(c, op, md):
    ss = md["sessions"]
    dn = lambda v, d=1: _tf.deN(("{:,.%df}" % d).format(v))
    tot = sum(x["tons"] for x in ss)
    mins = sum(x["minutes"] for x in ss if x["tons"])
    dr = sum(sum(x["drones"].values()) for x in ss)
    price = md["drone_price"]
    ore = {}
    for x in ss:
        for k, v in x["ore"].items():
            ore[k] = ore.get(k, 0) + v
    # Verkaeufe der abgebauten Waren
    names = {_clean_min(k): k for k in ore}
    sold = {}
    for r in c.execute("SELECT k1, SUM(n1) AS t, SUM(n2) AS cr FROM ce WHERE kind='trade' AND k3='sell' GROUP BY k1"):
        if _clean_min(r["k1"]) in names:
            sold[names[_clean_min(r["k1"])]] = (r["t"] or 0, r["cr"] or 0)
    rev = sum(v[1] for v in sold.values())
    if not ss:
        return {"kpi": [], "blocks": [], "note": "Noch kein Bergbau gespeichert. Raffinierte Tonnen, Prospektoren und Drohnen erscheinen hier, sobald du gebaut hast."}
    if op == "m_over":
        days = {}
        for x in ss:
            d_ = helpers._lts(x["start"]).strftime("%Y-%m-%d")
            o = days.setdefault(d_, [0, 0.0, 0, 0])
            o[0] += x["tons"]; o[1] += x["minutes"] / 60.0; o[2] += sum(x["drones"].values()); o[3] += x["prosp"]
        drows = [[k, v[0], v[1], v[0] / v[1] if v[1] else 0, v[3], v[2]] for k, v in sorted(days.items(), reverse=True)]
        best = max((x for x in ss if x["tph"]), key=lambda x: x["tph"], default=None)
        kpi = [["Abgebaut (t)", tot, "n"], ["Sessions", sum(1 for x in ss if x["tons"]), "n"], ["Abbau-Zeit", mins / 60.0, "h"],
               ["Ø Tonnen / h", tot / (mins / 60.0) if mins else 0, "r"], ["Beste Session (t/h)", best["tph"] if best else 0, "r"],
               ["Drohnen gestartet", dr, "n"], ["Drohnen / Tonne", dr / tot if tot else 0, "r"],
               ["Drohnenkosten (geschätzt)", dr * price, "cr"], ["Prospektoren-Treffer", sum(x["prosp"] for x in ss), "n"],
               ["Verkauft (t)", sum(v[0] for v in sold.values()), "n"], ["Erlös", rev, "cr"], ["Verdienst / Abbau-Stunde", (rev / sum(v[0] for v in sold.values())) * (tot / (mins / 60.0)) if mins and sold and sum(v[0] for v in sold.values()) else 0, "cr"]]
        return {"kpi": kpi, "blocks": [helpers._block("Pro Tag", [["Datum", "t"], ["Tonnen", "n"], ["Abbau-Zeit", "h"], ["Tonnen / h", "r"], ["Prospektoren-Funde", "n"], ["Drohnen", "n"]], drows,
                       "Abbau-Zeit = von der ersten Aktion (Prospektor/Drohne) bis zur letzten Raffinierung der Session.")],
                "note": "Drohnenkosten = gestartete Drohnen × Ø Kaufpreis aus deinen BuyDrones-Käufen (Schätzung, nicht jede Drohne geht verloren). Erlös zählt nur bereits verkaufte Mining-Waren. Verdienst/Abbau-Stunde = Ø erzielter Preis pro Tonne × Tonnen pro Stunde."}
    if op == "m_sess":
        rws = []
        for x in sorted(ss, key=lambda x: x["start"], reverse=True):
            top = ", ".join(f"{k} {v}" for k, v in sorted(x["ore"].items(), key=lambda kv: -kv[1])[:3]) or "-"
            pc = sum(v for k, v in x["drones"].items() if k == "Prospector")
            cc = sum(v for k, v in x["drones"].items() if k == "Collection")
            rws.append([x["start"], x["ring"] or "unbekannt", x["sys"], x["ship"], x["tons"], x["minutes"], x["tph"], pc, cc,
                        (sum(x["drones"].values()) / x["tons"]) if x["tons"] else 0, x["cracks"], top])
        return {"kpi": [["Sessions", len(ss), "n"], ["Tonnen", tot, "n"], ["Abbau-Zeit", mins / 60.0, "h"]], "blocks": [helpers._block("Sessions",
                [["Start", "d"], ["Ring", "t"], ["System", "t"], ["Schiff", "t"], ["Tonnen", "n"], ["Minuten", "r"], ["Tonnen / h", "r"], ["Prospektoren", "n"], ["Sammler", "n"],
                 ["Drohnen / t", "r"], ["Kerne", "n"], ["Erz", "t"]], rws,
                "Eine Session endet nach 20 Minuten Pause oder beim Wechsel des Rings. 'Kerne' = geknackte Asteroidenkerne.")]}
    if op == "m_ore":
        am, cont, asts = {}, {}, 0
        for x in ss:
            for k, v in x["content"].items():
                cont[k] = cont.get(k, 0) + v
            for lst in x["pm"]:
                asts += 1
                best_ = max((p_ for _m, p_ in lst), default=0)
                for m_, p_ in lst:
                    o = am.setdefault(m_, [0, 0.0, 0.0])
                    o[0] += 1; o[1] += p_; o[2] = max(o[2], p_)
        mrows = [[k, v[0], v[0] / asts if asts else 0, v[1] / v[0], v[2], ore.get(k, 0)] for k, v in sorted(am.items(), key=lambda kv: -kv[1][0])]
        crows = [[k, v, v / asts if asts else 0] for k, v in sorted(cont.items(), key=lambda kv: -kv[1])]
        orows = [[k, v, v / tot if tot else 0] for k, v in sorted(ore.items(), key=lambda kv: -kv[1])]
        return {"kpi": [["Prospektoren-Funde", asts, "n"], ["Verschiedene Materialien", len(am), "n"], ["Abgebaut (t)", tot, "n"], ["Kerne geknackt", sum(x["cracks"] for x in ss), "n"]],
                "blocks": [helpers._block("Abgebaut", [["Erz", "t"], ["Tonnen", "n"], ["Anteil", "f"]], orows),
                           helpers._block("Materialien in den Asteroiden", [["Material", "t"], ["Asteroiden mit Fund", "n"], ["Trefferquote", "f"], ["Ø Anteil %", "r"], ["Max Anteil %", "r"], ["Abgebaut t", "n"]], mrows,
                                  "Trefferquote = Anteil der geprospekteten Asteroiden, in denen das Material vorkam. Ø/Max = Prozentanteil im Asteroiden."),
                           helpers._block("Materialgehalt der Asteroiden", [["Gehalt", "t"], ["Asteroiden", "n"], ["Anteil", "f"]], crows)]}
    if op == "m_ring":
        hot = {}
        for r in c.execute("SELECT k1, k2, n1, ts FROM ce WHERE kind='hot' ORDER BY ts"):
            hot.setdefault(r["k1"], {})[r["k2"]] = int(r["n1"])
        ri = {}
        for r in c.execute("SELECT k1, k2, k3 FROM ce WHERE kind='ring' ORDER BY ts"):
            o = ri.setdefault(r["k1"], ["", ""])
            o[0] = r["k2"] or o[0]; o[1] = r["k3"] or o[1]
        g_ = {}
        for x in ss:
            if not x["tons"]:
                continue
            o = g_.setdefault(x["ring"] or "unbekannt", {"s": 0, "t": 0, "m": 0.0, "ore": {}, "sys": x["sys"], "last": x["start"]})
            o["s"] += 1; o["t"] += x["tons"]; o["m"] += x["minutes"]
            o["last"] = max(o["last"], x["start"])
            for k, v in x["ore"].items():
                o["ore"][k] = o["ore"].get(k, 0) + v
        rr = []
        for rn, o in sorted(g_.items(), key=lambda kv: -(kv[1]["t"] / kv[1]["m"] if kv[1]["m"] else 0)):
            h = hot.get(rn, {})
            rr.append([rn, o["sys"], ri.get(rn, ["", ""])[0] or "-", ri.get(rn, ["", ""])[1] or "-", o["s"], o["t"], o["m"] / 60.0, o["t"] / (o["m"] / 60.0) if o["m"] else 0,
                       ", ".join(f"{k} {v}" for k, v in sorted(o["ore"].items(), key=lambda kv: -kv[1])[:3]),
                       ", ".join(f"{k} {v}" for k, v in sorted(h.items(), key=lambda kv: -kv[1])) or "-", o["last"]])
        return {"kpi": [["Ringe abgebaut", len(g_), "n"], ["Tonnen", tot, "n"]], "blocks": [helpers._block("Ringe nach Ertrag",
                [["Ring", "t"], ["System", "t"], ["Ringtyp", "t"], ["Reserven", "t"], ["Sessions", "n"], ["Tonnen", "n"], ["Stunden", "h"], ["Tonnen / h", "r"], ["Abgebaut", "t"], ["Hotspots im Ring", "t"], ["Zuletzt", "d"]], rr,
                "Sortiert nach Tonnen pro Stunde. Hotspots stammen aus deinem Detailscan des Rings (siehe Navigation → Hotspots).")]}
    if op == "m_sell":
        pos, here, _hs = helpers._posmap(c)
        now = datetime.now(timezone.utc)
        mk = {}
        for r in c.execute(f"SELECT {database.MK_COLS} {database.MK_CURRENT}"):
            k = _clean_min(r["name"])
            if k in names and r["sell"] > 0 and r["demand"] > 0:
                mk.setdefault(k, []).append(r)
        arows, brows = [], []
        for k, t_ in sorted(ore.items(), key=lambda kv: -kv[1]):
            sv = sold.get(k, (0, 0))
            arows.append([k, t_, sv[0], sv[1], sv[1] / sv[0] if sv[0] else 0, max(0, t_ - sv[0])])
            for r in sorted(mk.get(_clean_min(k), []), key=lambda r: -r["sell"])[:5]:
                dl = helpers._d3(here, pos.get(r["system"]))
                age = max(0.0, (now - timefmt.parse_ts(r["seen"])).total_seconds() / 3600) if r["seen"] else None
                brows.append([k, r["sell"], r["demand"], r["station"], r["system"], dl, age])
        return {"kpi": [["Abgebaut (t)", tot, "n"], ["Verkauft (t)", sum(v[0] for v in sold.values()), "n"], ["Erlös", rev, "cr"],
                        ["Noch offen (t, geschätzt)", sum(max(0, t_ - sold.get(k, (0, 0))[0]) for k, t_ in ore.items()), "n"]],
                "blocks": [helpers._block("Verkauf der abgebauten Waren", [["Ware", "t"], ["Abgebaut t", "n"], ["Verkauft t", "n"], ["Erlös", "cr"], ["Ø Preis / t", "cr"], ["Noch offen t", "n"]], arows,
                                  "Verkäufe zählen nach Warenname, auch wenn sie nicht aus der gleichen Session stammen. 'Noch offen' = abgebaut minus verkauft, nicht gleich Laderaum."),
                           helpers._block("Beste bekannte Abnehmer (aus deinen Märkten)", [["Ware", "t"], ["Preis / t", "cr"], ["Nachfrage", "n"], ["Station", "t"], ["System", "t"], ["Entfernung (Ly)", "r"], ["Alter (Std.)", "r"]], brows,
                                  "Nur Stationen, deren Markt du gespeichert hast. Alter = seit der letzten Bestätigung des Preises.")]}
    return {"error": "unbekannte Abfrage"}
