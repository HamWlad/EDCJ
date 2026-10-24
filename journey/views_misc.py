"""Ansichten: Flugschreiber, Lücken-Liste, Bio-Atlas, Fraktions-Verlauf."""

import sqlite3
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import helpers, timefmt
from . import timefmt as _tf


def replay_view(c, p):
    """Flugschreiber: Sessions (= Journal-Dateien) und deren Ereignisse samt Positionspfad."""
    c.row_factory = sqlite3.Row
    if p.get("op") == "replay_list":
        rows = []
        for r in c.execute("SELECT name, first, last FROM jc WHERE first != '' ORDER BY first DESC"):
            n = {k: v for k, v in c.execute("SELECT kind, COUNT(*) FROM ce WHERE file=? AND kind IN ('jump','kill','trade','stn') GROUP BY kind", (r["name"],))}
            rows.append({"file": r["name"], "first": r["first"], "last": r["last"], "jumps": n.get("jump", 0), "kills": n.get("kill", 0),
                         "trades": n.get("trade", 0), "stations": n.get("stn", 0)})
        return {"sessions": rows}
    f = p.get("file", "")
    jr = c.execute("SELECT first, last FROM jc WHERE name=?", (f,)).fetchone()
    if not jr:
        return {"error": "Session nicht gefunden"}
    ev, path = [], []
    for r in c.execute("SELECT ts, kind, sys, k1, k2, k3, x, n1, n2, n3 FROM ce WHERE file=? ORDER BY ts, pos", (f,)):
        k, t = r["kind"], None
        if k == "pos":
            path.append([r["ts"], r["k1"] or r["sys"], r["n1"], r["n2"], r["n3"]])
        elif k == "jump":
            t = ("jump", "Sprung nach " + (r["k1"] or "?") + (" (%.1f Ly)" % r["n1"] if r["n1"] else ""), 0)
        elif k == "stn":
            t = ("dock", "Station: " + (r["k1"] or "?") + (" · " + r["k3"] if r["k3"] else ""), 0)
        elif k == "kill":
            t = ("kill", "Abschuss: " + (r["k1"] or "?") + (" – " + str(int(r["n1"])) + " Cr" if r["n1"] else ""), r["n1"] or 0)
        elif k == "trade":
            sell = r["k3"] == "sell"
            t = ("sell" if sell else "buy", ("Verkauf " if sell else "Kauf ") + str(int(r["n1"] or 0)) + " t " + (r["k1"] or "?") + " – " + str(int(r["n2"] or 0)) + " Cr",
                 (r["n2"] or 0) if sell else -(r["n2"] or 0))
        elif k == "touch":
            t = ("land", "Landung: " + (r["k1"] or "?"), 0)
        elif k == "bio":
            t = ("bio", "Bio analysiert: " + (r["k2"] or r["k1"] or "?"), 0)
        elif k == "mapd":
            t = ("map", "Kartiert: " + (r["k1"] or "?"), 0)
        elif k == "intd":
            t = ("intd", {"interdicted": "Abgefangen von ", "interdiction": "Abgefangen (aktiv): ", "escaped": "Entkommen: "}.get(r["k1"], "") + (r["k2"] or ""), 0)
        elif k == "mine":
            continue
        if t:
            ev.append({"ts": r["ts"], "k": t[0], "t": t[1], "cr": t[2], "sys": r["sys"]})
    return {"file": f, "first": jr["first"], "last": jr["last"], "events": ev[:5000], "path": path[:5000]}


def gaps_view(c, op):
    c.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)
    if op == "g_mk":
        st = {r["market_id"]: r for r in c.execute("""SELECT st.market_id, st.name, st.system, st.type, (SELECT MAX(ts) FROM snap WHERE market_id=st.market_id) AS last FROM station st""")}
        none, old = [], []
        for r in c.execute("SELECT system, name, market_id, type, via, last FROM stdb ORDER BY system, name"):
            mid = r["market_id"]
            if mid and mid in st and st[mid]["last"]:
                continue
            none.append([r["system"], r["name"], r["type"] or "-", "angedockt" if r["via"] == "docked" else "nur angeflogen", r["last"] or "-"])
        for mid, r in st.items():
            if not r["last"]:
                continue
            try:
                age = (now - timefmt.parse_ts(r["last"])).total_seconds() / 86400
            except Exception:
                continue
            if age > 7:
                old.append([r["system"], r["name"], r["type"] or "-", r["last"], round(age)])
        old.sort(key=lambda x: -x[4])
        return {"kpi": [["Stationen ohne Marktdaten", len(none), "n"], ["Märkte älter als 7 Tage", len(old), "n"], ["Märkte insgesamt", sum(1 for r in st.values() if r["last"]), "n"]],
                "blocks": [helpers._block("Besuchte Stationen ohne Markt-Aufzeichnung", [["System", "t"], ["Station", "t"], ["Typ", "t"], ["Besuch", "t"], ["Zuletzt", "d"]], none,
                                  "Siedlungen und Stationen ohne Markt (z. B. Außenposten ohne Händler) erscheinen hier ebenfalls – nicht jede Lücke ist ein Fehler."),
                           helpers._block("Märkte älter als eine Woche", [["System", "t"], ["Station", "t"], ["Typ", "t"], ["Letzte Aufzeichnung", "d"], ["Alter (Tage)", "n"]], old)]}
    if op == "g_pos":
        have = {r[0] for r in c.execute("SELECT system FROM syspos")}
        seen = {}
        for q in ("SELECT system AS s, MAX(last) AS t FROM stdb GROUP BY system", "SELECT system AS s, MAX(last_ts) AS t FROM station GROUP BY system",
                  "SELECT system AS s, MAX(ts) AS t FROM fac GROUP BY system", "SELECT sys AS s, MAX(ts) AS t FROM ce WHERE sys IS NOT NULL AND sys != '' GROUP BY sys"):
            for r in c.execute(q):
                if r["s"] and (r["s"] not in seen or (r["t"] or "") > seen[r["s"]]):
                    seen[r["s"]] = r["t"] or ""
        miss = sorted(([k, v or "-"] for k, v in seen.items() if k not in have), key=lambda x: x[1], reverse=True)
        return {"kpi": [["Systeme bekannt", len(seen), "n"], ["Mit Koordinaten", len(seen) - len(miss), "n"], ["Ohne Koordinaten", len(miss), "n"]],
                "blocks": [helpers._block("Systeme ohne Koordinaten", [["System", "t"], ["Zuletzt gesehen", "d"]], miss[:1000],
                                  "Ohne Koordinaten können Entfernungen (Handel, Rundkurse, Reisekarte) nicht berechnet werden. Sie kommen mit jedem Sprung ins System oder mit einer Route (NavRoute).")]}
    return {"error": "unbekannte Abfrage"}


def bio_view(c, op):
    c.row_factory = sqlite3.Row
    de = lambda v, d=0: _tf.deN(("{:,.%df}" % d).format(v or 0))
    body = {}
    for r in c.execute("SELECT sys, k1, k2, k3, x, y, n1 FROM ce WHERE kind='scan' ORDER BY ts"):
        try:
            tmp = float(r["y"]) if r["y"] not in (None, "") else None
        except ValueError:
            tmp = None
        body[r["k1"]] = {"cls": r["k2"], "atm": r["x"] or "", "t": tmp, "g": r["n1"] or None, "sys": r["sys"]}
    sale = {}
    for r in c.execute("SELECT k1, k2, n1, n2, n3 FROM ce WHERE kind='bsell'"):
        o = sale.setdefault((r["k1"], r["k2"]), [0, 0, 0])
        o[0] += r["n3"] or 0
        o[1] += r["n1"] or 0
        o[2] += r["n2"] or 0
    sp = {}
    for r in c.execute("SELECT ts, sys, k1, k2, k3, x FROM ce WHERE kind='bio' ORDER BY ts"):
        o = sp.setdefault((r["k1"], r["k2"]), {"n": 0, "bodies": {}, "vars": set(), "last": ""})
        o["n"] += 1
        o["last"] = r["ts"]
        if r["x"]:
            o["vars"].add(r["x"])
        o["bodies"].setdefault(r["k3"] or "unbekannt", r["sys"])
    if not sp:
        return {"kpi": [], "blocks": [], "note": "Noch keine analysierten Biologie-Proben im Journal (ScanOrganic mit „Analyse“)."}

    def rng(vals, d=2, unit=""):
        vals = [v for v in vals if v is not None]
        if not vals:
            return "-"
        lo, hi = min(vals), max(vals)
        f = lambda v: de(v, d) + unit
        return f(lo) if round(lo, d) == round(hi, d) else f(lo) + " – " + f(hi)

    if op == "bi_species":
        rows = []
        for (ge, spc), o in sorted(sp.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            bs = [body.get(b) for b in o["bodies"]]
            bs = [b for b in bs if b]
            sv = [v for (k1, k2), v in sale.items() if k1 == ge and (k2 == spc or k2 in o["vars"])]
            val = sum(v[0] for v in sv)
            cnt = sum(v[2] for v in sv)
            rows.append([ge, spc, o["n"], len(o["bodies"]), rng([b["g"] for b in bs], 2, " g"), ", ".join(sorted({b["atm"] or "keine" for b in bs})) or "-",
                         rng([b["t"] for b in bs], 0, " K"), (val / cnt) if cnt else None, cnt, o["last"]])
        return {"kpi": [["Arten", len(sp), "n"], ["Analysen", sum(o["n"] for o in sp.values()), "n"], ["Fundkörper", len({b for o in sp.values() for b in o["bodies"]}), "n"],
                        ["Verkaufserlös", sum(v[0] + v[1] for v in sale.values()), "cr"]],
                "blocks": [helpers._block("Bio-Atlas: Arten", [["Gattung", "t"], ["Art", "t"], ["Analysen", "n"], ["Körper", "n"], ["Schwerkraft", "t"], ["Atmosphäre", "t"], ["Temperatur", "t"],
                                                       ["Ø Verkaufswert", "cr"], ["Verkäufe", "n"], ["Zuletzt", "d"]], rows,
                                  "Schwerkraft, Atmosphäre und Temperatur nur von Körpern, die du gescannt hast. Verkaufswert = Ø der tatsächlich gemeldeten Verkäufe (ohne Bonus); keine Regeln dazugedichtet.")]}
    rows = []
    for (ge, spc), o in sp.items():
        for bn, sy in o["bodies"].items():
            b = body.get(bn) or {}
            rows.append([ge, spc, sy or b.get("sys") or "-", bn, b.get("cls") or "-", (b.get("g") and de(b["g"], 2) + " g") or "-", b.get("atm") or ("keine" if b else "-"),
                         (b.get("t") is not None and de(b["t"], 0) + " K") or "-", o["last"]])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return {"kpi": [["Fundorte", len(rows), "n"]], "blocks": [helpers._block("Bio-Atlas: Fundorte", [["Gattung", "t"], ["Art", "t"], ["System", "t"], ["Körper", "t"], ["Klasse", "t"], ["Schwerkraft", "t"],
                                                                                          ["Atmosphäre", "t"], ["Temperatur", "t"], ["Zuletzt", "d"]], rows)]}


def bgs_view(c, op):
    c.row_factory = sqlite3.Row
    addr = {str(r["addr"]): r["system"] for r in c.execute("SELECT DISTINCT addr, system FROM fac")}
    acts = []  # (ts, system, faction, art, detail, wert)
    for r in c.execute("SELECT ts, sys, k1, k2, k3, x, y, n2 FROM ce WHERE kind='bgs' ORDER BY ts"):
        sysn = addr.get(r["x"]) or r["sys"] or "?"
        plus = r["k2"] or ""
        acts.append((r["ts"], sysn, r["k1"], "Mission", (r["y"] or "") + (" | Einfluss " + plus if plus else "") + (" (" + r["k3"] + ")" if r["k3"] else ""), plus.count("+")))
    kills = {}
    for r in c.execute("SELECT ts, sys, k1, k2, k3, n1 FROM ce WHERE kind='kill' ORDER BY ts"):
        # Abschuss zaehlt fuer die belohnende Fraktion als Hilfe, der Opfer-Fraktion schadet er
        acts.append((r["ts"], r["sys"] or "?", r["k1"], "Abschuss (Opfer-Fraktion)", "Kopfgeld/Bond von " + str(r["k2"] or "?") + " | " + str(int(r["n1"] or 0)) + " Cr", -1))
    if not acts:
        return {"kpi": [], "blocks": [], "note": "Noch keine eigenen Eingriffe im Journal (abgeschlossene Missionen mit Einflussänderung, Abschüsse)."}
    meas = {}
    for r in c.execute("SELECT system, name, ts, inf FROM fac ORDER BY ts"):
        meas.setdefault((r["system"], r["name"]), []).append((r["ts"], r["inf"]))
    keys = {}
    for a in acts:
        keys.setdefault((a[1], a[2]), []).append(a)
    if op == "b_over":
        rows = []
        for (sy, fa), L in sorted(keys.items(), key=lambda kv: -len(kv[1])):
            ms = [a for a in L if a[3] == "Mission"]
            ks = [a for a in L if a[3].startswith("Abschuss")]
            m = meas.get((sy, fa), [])
            first = m[0][1] if m else None
            last = m[-1][1] if m else None
            rows.append([sy, fa, len(ms), sum(a[5] for a in ms), len(ks), len(m), first, last, (last - first) if m and len(m) > 1 else None,
                         max(a[0] for a in L)])
        return {"kpi": [["Eingriffe gesamt", len(acts), "n"], ["Systeme/Fraktionen", len(keys), "n"],
                        ["Abgeschl. Missionen mit Wirkung", sum(1 for a in acts if a[3] == "Mission"), "n"], ["Abschüsse", sum(1 for a in acts if a[3].startswith("Abschuss")), "n"]],
                "blocks": [helpers._block("Eigene Eingriffe je System und Fraktion", [["System", "t"], ["Fraktion", "t"], ["Missionen", "n"], ["Einfluss-Plus (Summe +)", "n"], ["Abschüsse", "n"],
                                                                             ["Messungen", "n"], ["Einfluss erste %", "r"], ["Einfluss letzte %", "r"], ["Δ Punkte", "r"], ["Letzter Eingriff", "d"]], rows,
                                  "Einfluss-Plus: die Plus-Zeichen, die das Spiel bei der Missionsabgabe nennt (+ bis +++++). Messungen kommen aus deinen Besuchen. Ob eine Änderung von dir stammt, belegt das Journal nicht – es zeigt nur beides nebeneinander.")]}
    if op == "b_log":
        ev = []
        for (sy, fa), L in keys.items():
            ev += [[a[0], sy, fa, a[3], a[4], None] for a in L]
            ev += [[t, sy, fa, "Messung", "Einfluss " + str(round(v, 2)) + " %", v] for t, v in meas.get((sy, fa), [])]
        ev.sort(key=lambda r: r[0], reverse=True)
        return {"kpi": [], "blocks": [helpers._block("Verlauf: Eingriffe und Einfluss-Messungen", [["Zeit", "d"], ["System", "t"], ["Fraktion", "t"], ["Art", "t"], ["Detail", "t"], ["Einfluss %", "r"]], ev[:600])]}
    return {"error": "unbekannte Abfrage"}
