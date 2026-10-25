"""Rückblick: Kalenderwochen/-monate, Gewinn je Ware und Route, Fracht gegen Weite, Vermögen nach Quellen.

Alles kommt aus dem eigenen Journal (Tabellen ce, act, wealth, syspos). Nichts wird geschätzt:
- Perioden: lokale Kalenderwochen (Mo-So) und Monate.
- Gewinn je Ware: MarketSell/MarketBuy; Gewinn = Erlös minus Einkaufspreis laut Spiel (AvgPricePaid).
- Routen: jeder Verkauf wird den früheren Käufen derselben Ware nach FIFO zugeordnet.
- Weite: Luftlinie zwischen den Systemen, nur wenn beide Koordinaten bekannt sind.
"""
from datetime import datetime, timedelta

from . import helpers, timefmt

OPS = ("rb_week", "rb_month", "rb_ware", "rb_route", "rb_fw", "rb_verm")


def _wk(d):
    return (d.date() - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def _mo(d):
    return d.strftime("%Y-%m")


def _label_week(k):
    a = timefmt.parse_ts(k + "T00:00:00Z").date()
    b = a + timedelta(days=6)
    return f"{a.strftime('%d.%m.')}–{b.strftime('%d.%m.%Y')}"


def _periods(c, keyf):
    """Kennzahlen je Periode (lokale Zeit)."""
    P = {}

    def o(k):
        return P.setdefault(k, {"inc": 0, "out": 0, "trade": 0, "bnty": 0, "kills": 0, "trit": 0, "jumps": 0, "dist": 0.0, "h": 0.0})
    for r in c.execute("SELECT ts, kind, k1, k3, n1, n3 FROM ce WHERE kind IN ('cash','kill','mine','jump','trade')"):
        if r["kind"] == "mine" and r["k1"] != "Tritium":
            continue
        if r["kind"] == "trade" and r["k3"] != "sell":
            continue
        d = o(keyf(helpers._lts(r["ts"])))
        if r["kind"] == "cash":
            d["inc" if r["n1"] > 0 else "out"] += r["n1"]
        elif r["kind"] == "kill":
            d["kills"] += 1
            d["bnty"] += r["n1"]
        elif r["kind"] == "mine":
            d["trit"] += r["n1"] or 1
        elif r["kind"] == "jump":
            d["jumps"] += 1
            d["dist"] += r["n1"]
        else:
            d["trade"] += r["n3"]
    for r in c.execute("SELECT b FROM act"):
        o(keyf(helpers._bdt(r["b"])))["h"] += 1 / 6.0
    return P


_SPEC = [("Einnahmen", "Cr", "inc"), ("Ausgaben", "Cr", "out"), ("Netto", "Cr", "net"), ("Handelsgewinn", "Cr", "trade"),
         ("Kopfgeld-Belohnungen", "Cr", "bnty"), ("Abschüsse", "", "kills"), ("Tritium abgebaut", "t", "trit"),
         ("Sprünge", "", "jumps"), ("Strecke", "Ly", "dist"), ("Aktive Zeit", "Min.", "min")]


def _val(d, k):
    if k == "net":
        return d["inc"] + d["out"]
    if k == "min":
        return d["h"] * 60
    return d[k]


def _prev_key(k, month):
    if month:
        y, m = int(k[:4]), int(k[5:7])
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        return f"{y:04d}-{m:02d}"
    return (timefmt.parse_ts(k + "T00:00:00Z").date() - timedelta(days=7)).strftime("%Y-%m-%d")


def _period_view(c, month):
    keyf = _mo if month else _wk
    P = _periods(c, keyf)
    now = datetime.now().astimezone()
    cur = keyf(now)
    prv = _prev_key(cur, month)
    empty = {"inc": 0, "out": 0, "trade": 0, "bnty": 0, "kills": 0, "trit": 0, "jumps": 0, "dist": 0.0, "h": 0.0}
    a, b = P.get(cur, empty), P.get(prv, empty)
    rows = []
    for lbl, unit, k in _SPEC:
        x, y = _val(a, k), _val(b, k)
        rows.append([lbl, unit, x, y, x - y, ((x - y) / abs(y) * 100) if y else None])
    name = "Monat" if month else "Woche"
    lab = (lambda k: k) if month else _label_week
    kpi = [[f"Netto ({name} läuft)", _val(a, "net"), "cr"], [f"Netto ({name} davor)", _val(b, "net"), "cr"],
           ["Abschüsse", a["kills"], "n"], ["Tritium", a["trit"], "n"], ["Sprünge", a["jumps"], "n"],
           ["Zeitraum aktuell", lab(cur), "t"], ["Zeitraum davor", lab(prv), "t"]]
    all_rows = []
    for k in sorted(P, reverse=True):
        d = P[k]
        all_rows.append([lab(k) + (" (läuft)" if k == cur else ""), d["inc"], d["out"], d["inc"] + d["out"], d["trade"], d["bnty"], d["kills"],
                         d["trit"], d["jumps"], d["dist"], d["h"]])
    ks = sorted(P)
    chart = {"type": "bars", "labels": [lab(k) if month else k[5:] for k in ks][-26:],
             "series": [{"name": "Einnahmen", "vals": [P[k]["inc"] for k in ks][-26:]}]}
    return {"kpi": kpi, "blocks": [
        helpers._block("Aktuelle Woche gegen die Woche davor" if not month else "Aktueller Monat gegen den Monat davor",
                       [["Kennzahl", "t"], ["Einheit", "t"], ["Aktuell", "n"], ["Davor", "n"], ["Unterschied", "n"], ["Unterschied %", "p"]], rows,
                       f"Die laufende {name} ist noch nicht zu Ende, der Vergleich fällt deshalb meist niedriger aus. Das Zeitraum-Feld gilt hier nicht."),
        {"title": "Einnahmen je Monat" if month else "Einnahmen je Woche", "chart": chart},
        helpers._block("Alle Monate" if month else "Alle Wochen",
                       [[name, "t"], ["Einnahmen", "n"], ["Ausgaben", "n"], ["Netto", "n"], ["Handelsgewinn", "n"], ["Kopfgeld", "n"],
                        ["Abschüsse", "n"], ["Tritium", "n"], ["Sprünge", "n"], ["Strecke Ly", "n"], ["Aktiv", "h"]], all_rows,
                       "Beträge in Cr, Strecke in Ly, Aktiv in Stunden.")]}


def _trades(c, cut):
    q = "SELECT ts, sys, k1, k2, k3, n1, n2, n3 FROM ce WHERE kind='trade'" + (" AND ts >= ?" if cut else "") + " ORDER BY ts, id"
    return c.execute(q, (cut,) if cut else ()).fetchall()


def _ware(c, cut):
    W = {}
    for r in _trades(c, cut):
        o = W.setdefault(r["k1"], [0, 0, 0, 0, 0, 0, 0])   # buyq, buyc, sellq, rev, profit, nsell, profit_with_cost
        if r["k3"] == "buy":
            o[0] += r["n1"]
            o[1] += r["n2"]
        else:
            o[2] += r["n1"]
            o[3] += r["n2"]
            o[4] += r["n3"]
            o[5] += 1
            if abs(r["n3"] - r["n2"]) > 1:
                o[6] += r["n3"]
    rows = [[k, v[0], v[1], v[2], v[3], v[4], v[4] / v[2] if v[2] else None, v[5]] for k, v in W.items()]
    rows.sort(key=lambda r: -r[5])
    tot = sum(v[4] for v in W.values())
    own = sum(v[3] - v[4] for v in W.values())
    nocost = sum(v[4] - v[6] for v in W.values())
    kpi = [["Handelsgewinn gesamt", tot, "cr"], ["Verkaufserlös", sum(v[3] for v in W.values()), "cr"], ["Eingekauft für", sum(v[1] for v in W.values()), "cr"],
           ["Davon ohne Einkaufspreis (z. B. abgebaut)", nocost, "cr"], ["Verkaufte Tonnen", sum(v[2] for v in W.values()), "n"]]
    return {"kpi": kpi, "blocks": [helpers._block(
        "Gewinn je Ware", [["Ware", "t"], ["Gekauft t", "n"], ["Ausgaben", "cr"], ["Verkauft t", "n"], ["Erlös", "cr"], ["Gewinn", "cr"], ["Gewinn / t", "cr"], ["Verkäufe", "n"]], rows,
        "Gewinn = Erlös minus der Einkaufspreis, den das Spiel beim Verkauf meldet. Ware ohne Einkaufspreis (abgebaut, gefunden, Mission) zählt voll als Gewinn.")]}


def _legs(c, cut):
    """Zuordnung Verkauf -> frühere Käufe derselben Ware (FIFO). Ein Leg = ein Verkauf aus einer Herkunftsstation."""
    pos = {r["system"]: (r["x"], r["y"], r["z"]) for r in c.execute("SELECT system, x, y, z FROM syspos")}

    def dist(a, b):
        if a == b:
            return 0.0
        pa, pb = pos.get(a), pos.get(b)
        return None if pa is None or pb is None else sum((u - v) ** 2 for u, v in zip(pa, pb)) ** 0.5
    # FIFO laeuft immer ueber die gesamte Historie (Kaeufe vor dem Zeitraum-Beginn muessen bekannt sein)
    q = c.execute("SELECT ts, sys, k1, k2, k3, n1, n2, n3 FROM ce WHERE kind='trade' ORDER BY ts, id").fetchall()
    stock, legs, loose = {}, [], 0
    for r in q:
        if r["k3"] == "buy":
            stock.setdefault(r["k1"], []).append([r["k2"], r["sys"], r["n1"]])
            continue
        need, tot = r["n1"], r["n1"]
        if tot <= 0:
            continue
        got = {}
        qu = stock.setdefault(r["k1"], [])
        while need > 0 and qu:
            s = qu[0]
            take = min(need, s[2])
            g = got.setdefault((s[0], s[1]), 0)
            got[(s[0], s[1])] = g + take
            s[2] -= take
            need -= take
            if s[2] <= 1e-9:
                qu.pop(0)
        loose += need
        if cut and r["ts"] < cut:
            continue
        for (st, sy), qty in got.items():
            legs.append({"ts": r["ts"], "ware": r["k1"], "von": st, "nach": r["k2"], "qty": qty, "profit": r["n3"] * qty / tot,
                         "dist": dist(sy, r["sys"]), "same": st == r["k2"]})
    return legs, loose


def _route(c, cut):
    legs, loose = _legs(c, cut)
    R = {}
    for g in legs:
        k = (g["von"], g["nach"], g["ware"])
        o = R.setdefault(k, {"q": 0, "p": 0, "n": 0, "d": g["dist"]})
        o["q"] += g["qty"]
        o["p"] += g["profit"]
        o["n"] += 1
    rows = []
    for (a, b, w), o in R.items():
        d = o["d"]
        rows.append([a, b, w, d, o["q"], o["n"], o["p"], o["p"] / o["q"] if o["q"] else None, (o["p"] / o["n"] / d) if d else None])
    rows.sort(key=lambda r: -r[6])
    tp = sum(g["profit"] for g in legs)
    kpi = [["Zugeordnete Fahrten", len(legs), "n"], ["Gewinn dieser Fahrten", tp, "cr"], ["Verschiedene Routen", len(rows), "n"],
           ["Verkauf ohne passenden Einkauf (t)", loose, "n"]]
    return {"kpi": kpi, "blocks": [helpers._block(
        "Gewinn je Route", [["Von", "t"], ["Nach", "t"], ["Ware", "t"], ["Weite Ly", "r"], ["Menge t", "n"], ["Fahrten", "n"], ["Gewinn", "cr"], ["Gewinn / t", "cr"], ["Gewinn / Ly", "cr"]], rows,
        "Jeder Verkauf wird den früheren Käufen derselben Ware zugeordnet (älteste zuerst). Weite = Luftlinie zwischen den Systemen, leer wenn Koordinaten fehlen. 'Gewinn / Ly' ist der Gewinn je Fahrt geteilt durch die Weite.")]}


_WB = [("Gleiches System", lambda d: d == 0), ("bis 10 Ly", lambda d: 0 < d <= 10), ("10–25 Ly", lambda d: 10 < d <= 25),
       ("25–50 Ly", lambda d: 25 < d <= 50), ("50–100 Ly", lambda d: 50 < d <= 100), ("über 100 Ly", lambda d: d > 100)]
_QB = [("bis 50 t", lambda q: q <= 50), ("50–100 t", lambda q: 50 < q <= 100), ("100–250 t", lambda q: 100 < q <= 250),
       ("250–500 t", lambda q: 250 < q <= 500), ("über 500 t", lambda q: q > 500)]


def _fw(c, cut):
    legs, _ = _legs(c, cut)
    known = [g for g in legs if g["dist"] is not None]
    cell = {}
    for g in known:
        wi = next(i for i, (_, f) in enumerate(_WB) if f(g["dist"]))
        qi = next(i for i, (_, f) in enumerate(_QB) if f(g["qty"]))
        for key in ((qi, wi), (qi, -1), (-1, wi), (-1, -1)):
            o = cell.setdefault(key, [0, 0.0, 0.0])
            o[0] += 1
            o[1] += g["qty"]
            o[2] += g["profit"]
    cols_ = [[f"Fracht ↓ · Weite →", "t"]] + [[n, "n"] for n, _ in _WB] + [["Alle", "n"]]
    names = [n for n, _ in _QB] + ["Alle"]
    idx = list(range(len(_QB))) + [-1]

    def mat(fn):
        rows = []
        for nm, qi in zip(names, idx):
            rows.append([nm] + [fn(cell.get((qi, wi))) for wi in list(range(len(_WB))) + [-1]])
        return rows
    kpi = [["Fahrten mit bekannter Weite", len(known), "n"], ["Ohne Koordinaten", len(legs) - len(known), "n"]]
    return {"kpi": kpi, "blocks": [
        helpers._block("Gewinn pro Tonne (Cr) – Fracht gegen Weite", cols_, mat(lambda o: (o[2] / o[1]) if o and o[1] else None),
                       "Zeile = Menge je Fahrt, Spalte = Luftlinie zwischen Einkaufs- und Verkaufssystem. Leer = noch keine Fahrt dieser Art."),
        helpers._block("Anzahl Fahrten", cols_, mat(lambda o: o[0] if o else None)),
        helpers._block("Gewinn gesamt (Cr)", cols_, mat(lambda o: o[2] if o else None))]}


_SRC = ["Handel", "Mining", "Kopfgeld", "Missionen", "Erkundung", "Sonstiges"]


def _verm(c, cut):
    W = {}
    cash = c.execute("SELECT ts, k1, n1 FROM ce WHERE kind='cash'" + (" AND ts >= ?" if cut else ""), (cut,) if cut else ()).fetchall()
    for r in cash:
        k = _wk(helpers._lts(r["ts"]))
        o = W.setdefault(k, {s: 0 for s in _SRC + ["Ausgaben"]})
        if r["n1"] < 0:
            o["Ausgaben"] += r["n1"]
            continue
        c_ = r["k1"]
        s = ("Handel" if c_ == "Handel" else "Kopfgeld" if c_.startswith("Kopfgeld") else "Missionen" if c_ == "Missionen"
             else "Erkundung" if c_ in ("Exploration", "Exobiologie") else "Sonstiges")
        o[s] += r["n1"]
    # Mining = Verkauf ohne Einkaufspreis, aus 'Handel' herausgerechnet (nur soweit dort verbucht)
    for r in c.execute("SELECT ts, n2, n3 FROM ce WHERE kind='trade' AND k3='sell'" + (" AND ts >= ?" if cut else ""), (cut,) if cut else ()):
        if r["n2"] > 0 and abs(r["n3"] - r["n2"]) <= 1:
            k = _wk(helpers._lts(r["ts"]))
            o = W.get(k)
            if o:
                m = min(r["n2"], o["Handel"])
                o["Handel"] -= m
                o["Mining"] += m
    last = {}
    for r in c.execute("SELECT ts, v FROM wealth WHERE src='wealth' ORDER BY ts"):
        last[_wk(helpers._lts(r["ts"]))] = r["v"]
    ks = sorted(set(W) | set(k for k in last if not cut or k >= _wk(helpers._lts(cut))))
    rows = []
    for k in sorted(ks, reverse=True):
        o = W.get(k, {s: 0 for s in _SRC + ["Ausgaben"]})
        inc = sum(o[s] for s in _SRC)
        rows.append([_label_week(k)] + [o[s] for s in _SRC] + [o["Ausgaben"], inc + o["Ausgaben"], last.get(k)])
    tot = {s: sum(W[k][s] for k in W) for s in _SRC}
    ti = sum(tot.values())
    kpi = [[s, tot[s], "cr"] for s in _SRC] + [["Ausgaben", sum(W[k]["Ausgaben"] for k in W), "cr"]]
    src_rows = [[s, tot[s], (tot[s] / ti) if ti else 0] for s in _SRC]
    src_rows.sort(key=lambda r: -r[1])
    wl = [(k, last[k]) for k in sorted(last) if not cut or k >= _wk(helpers._lts(cut))]
    blocks = []
    if wl:
        blocks.append({"title": "Gesamtvermögen je Woche (letzter bekannter Stand)",
                       "chart": {"type": "line", "labels": [k[5:] for k, _ in wl][-40:], "series": [{"name": "Gesamtvermögen", "vals": [v for _, v in wl][-40:]}]}})
    ks2 = sorted(W)[-26:]
    blocks.append({"title": "Einnahmen je Woche nach Quelle",
                   "chart": {"type": "stack", "labels": [k[5:] for k in ks2], "series": [{"name": s, "vals": [W[k][s] for k in ks2]} for s in _SRC]}})
    blocks.append(helpers._block("Quellen gesamt", [["Quelle", "t"], ["Einnahmen", "cr"], ["Anteil", "f"]], src_rows,
                                 "Mining = Verkäufe ohne Einkaufspreis laut Spiel (abgebaute oder gefundene Ware), aus 'Handel' herausgerechnet. Erkundung enthält Exploration und Exobiologie."))
    blocks.append(helpers._block("Je Woche", [["Woche", "t"]] + [[s, "n"] for s in _SRC] + [["Ausgaben", "n"], ["Netto", "n"], ["Gesamtvermögen", "n"]], rows,
                                 "Beträge in Cr. Gesamtvermögen kommt aus der Statistik des Spiels und liegt nur vor, wenn sie in der Woche gemeldet wurde."))
    return {"kpi": kpi, "blocks": blocks}


def rb_view(c, op, cut):
    if op == "rb_week":
        return _period_view(c, False)
    if op == "rb_month":
        return _period_view(c, True)
    if op == "rb_ware":
        return _ware(c, cut)
    if op == "rb_route":
        return _route(c, cut)
    if op == "rb_fw":
        return _fw(c, cut)
    return _verm(c, cut)
