"""Kolonien: Baustellen aus ColonisationConstructionDepot (eigenes Journal) mit Bezugsorten aus den eigenen Märkten."""
import json
import math
import sqlite3
from datetime import datetime, timezone

from . import database, helpers

OPS = ("ko_bau", "ko_meine")


_START = "__start__"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _start(c):
    """Zeitpunkt, ab dem EDCJ Transfers mitzählt (erstes Öffnen der Bestandsseite oder der Baustellen)."""
    r = c.execute("SELECT since FROM ckstock WHERE ware=?", (_START,)).fetchone()
    if r:
        return r["since"]
    t = _now()
    try:
        c.execute("INSERT OR IGNORE INTO ckstock VALUES(?,0,?)", (_START, t))
        c.commit()
    except sqlite3.Error:
        pass
    return t


def _stock(c):
    """Aktueller Carrier-Bestand je Ware: zuletzt von Hand gesetzter Stand plus Transfers seitdem (ohne Eintrag: ab Startzeitpunkt)."""
    start = _start(c)
    rows = {r["ware"]: (r["base"], r["since"]) for r in c.execute("SELECT ware, base, since FROM ckstock WHERE ware != ?", (_START,))}
    wares = set(rows) | {r["k1"] for r in c.execute("SELECT DISTINCT k1 FROM ce WHERE kind='ctr' AND ts > ?", (start,))}
    out = {}
    for w in wares:
        base, since = rows.get(w, (0, start))
        d = 0
        for t in c.execute("SELECT k3, SUM(n1) n FROM ce WHERE kind='ctr' AND k1=? AND ts>? GROUP BY k3", (w, since)):
            d += t["n"] if t["k3"] == "tocarrier" else -t["n"] if t["k3"] == "toship" else 0
        out[w] = max(0, base + d)
    return out


def set_stock(body):
    """Carrier-Bestand einer Ware ändern (delta) oder setzen (stock); Transfers danach zählt EDCJ selbst dazu."""
    body = body or {}
    ware = str(body.get("ware", "")).strip()[:100]
    if not ware:
        return {"error": "ungueltig"}
    c = database._mdb()
    c.row_factory = sqlite3.Row
    try:
        cur = _stock(c).get(ware, 0)
        try:
            new = max(0, cur + float(body["delta"])) if "delta" in body else max(0, float(body.get("stock")))
        except (TypeError, ValueError):
            return {"error": "ungueltig"}
        c.execute("INSERT OR REPLACE INTO ckstock VALUES(?,?,?)", (ware, new, _now()))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "stock": new}


def _open_sites(c):
    out = []
    for r in c.execute("SELECT js FROM snapkv WHERE k LIKE 'Depot:%'"):
        ev = json.loads(r["js"])
        if not ev.get("ConstructionComplete") and not ev.get("ConstructionFailed"):
            out.append(ev)
    return out


def stock_view(c):
    """Fleet Carrier: Bestandsliste aller bekannten Waren (Reiter Schiff, Fleet Carrier, Bestand)."""
    st = _stock(c)
    cat = {r["name"]: r["cat"] for r in c.execute("SELECT name, MAX(cat) cat FROM item GROUP BY name")}
    fehlt = {}
    for ev in _open_sites(c):
        for q in ev.get("ResourcesRequired") or []:
            w = q.get("Name_Localised") or q.get("Name")
            fehlt[w] = fehlt.get(w, 0) + max(0, q["RequiredAmount"] - q["ProvidedAmount"])
    wares = set(cat) | set(st) | set(fehlt) | {r["k1"] for r in c.execute("SELECT DISTINCT k1 FROM ce WHERE kind='ctr'")}
    rows = [[w, cat.get(w, ""), st.get(w, 0), fehlt.get(w, 0)] for w in wares]
    rows.sort(key=lambda r: (-(r[2] > 0), -r[2], -(r[3] > 0), r[0].lower()))
    kpi = [["Waren mit Bestand", sum(1 for r in rows if r[2] > 0), "n"], ["Tonnen laut Liste", sum(r[2] for r in rows), "n"]]
    try:
        j = json.loads(c.execute("SELECT y FROM ce WHERE kind='cstat' ORDER BY ts DESC LIMIT 1").fetchone()["y"] or "{}")
        game = (j.get("SpaceUsage") or {}).get("Cargo")
        if game is not None:
            kpi.append(["Fracht laut Carrier-Verwaltung", game, "n"])
    except Exception:
        pass
    return {"kpi": kpi, "blocks": [{"title": "Bestand im Fleet Carrier", "stock": {"rows": rows},
            "note": "Alle Waren, die du von deinen Märkten kennst. Trage unter „Ändern“ ein, wie viel du hinzugefügt (+) oder genommen (−) hast; der Bestand zeigt dann die neue Menge. "
                    "Transfers in den Carrier und heraus zählt EDCJ ab dem ersten Öffnen dieser Seite selbst mit. Die Baustellen-Ansicht nutzt diesen Bestand."}]}


def _cap(c):
    r = c.execute("SELECT js FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC LIMIT 1").fetchone()
    try:
        return int(json.loads(r["js"]).get("CargoCapacity") or 0) if r else 0
    except Exception:
        return 0


def _name(c, mid):
    r = c.execute("SELECT k1, sys FROM ce WHERE kind='stn' AND n2=? ORDER BY ts DESC LIMIT 1", (mid,)).fetchone()
    return (r["k1"], r["sys"]) if r else (f"Baustelle {mid}", "")


def _source(c, ware):
    r = c.execute(f"SELECT i.buy, i.stock, s.seen, st.name AS station, st.system {database.MK_CURRENT} AND i.name=? AND i.buy>0 AND i.stock>0 "
                  "ORDER BY i.buy LIMIT 1", (ware,)).fetchone()
    return r


def _cover(c, miss, info):
    """Wenige Märkte: Märkte nach abgedeckten Tonnen (größter zuerst), jede Ware beim ersten Markt, der sie liefern kann."""
    mk = {}
    for r in c.execute(f"SELECT i.name, i.buy, i.stock, s.seen, s.market_id, st.name AS station, st.system {database.MK_CURRENT} AND i.stock>0 AND i.buy>0"):
        if r["name"] in miss:
            mk.setdefault(r["market_id"], {"station": r["station"], "system": r["system"], "seen": r["seen"], "items": {}})["items"][r["name"]] = (r["buy"], r["stock"])
    rem = dict(miss)
    cols = [["Ware", "t"], ["Benötigt t", "n"], ["Im Carrier t", "n"], ["Geliefert t", "n"], ["Fehlt t", "n"], ["Noch kaufen t", "n"], ["Hier holen t", "n"],
            ["Preis", "n"], ["Bestand", "n"], ["Deckt", "t"], ["Marktstand", "d"]]
    groups = []
    for _ in range(12):
        best, bs = None, (0, 0, 0)
        for mid, m in mk.items():
            cov = sum(min(rem[w], st) for w, (_, st) in m["items"].items() if w in rem)
            n = sum(1 for w in m["items"] if w in rem)
            cost = -sum(min(rem[w], st) * pr for w, (pr, st) in m["items"].items() if w in rem)
            if (cov, n, cost) > bs:
                best, bs = mid, (cov, n, cost)
        if best is None or bs[0] <= 0:
            break
        m = mk.pop(best)
        rows, tons = [], 0
        for w, (pr, st) in sorted(m["items"].items(), key=lambda kv: -min(rem.get(kv[0], 0), kv[1][1])):
            if w not in rem:
                continue
            take = min(rem[w], st)
            q, ca, pv, fe = info[w]
            rows.append([w, q, ca, pv, fe, rem[w], take, pr, st, "Komplett" if take >= rem[w] else "Teilweise", m["seen"]])
            rem[w] -= take
            tons += take
            if rem[w] <= 0:
                del rem[w]
        groups.append({"label": m["station"], "sys": m["system"], "open": not groups, "sum": [[len(rows), "Waren"], [tons, "t"]], "cols": cols, "rows": rows})
    if rem:
        groups.append({"label": "Nicht auf deinen Märkten", "open": True, "sum": [[len(rem), "Waren"], [sum(rem.values()), "t"]],
                       "cols": [["Ware", "t"], ["Benötigt t", "n"], ["Im Carrier t", "n"], ["Geliefert t", "n"], ["Fehlt t", "n"], ["Noch offen t", "n"]],
                       "rows": [[w, *info[w], m] for w, m in sorted(rem.items(), key=lambda kv: -kv[1])]})
    return groups


def ko_view(c, op, cut):
    cap = _cap(c)
    stock = _stock(c)
    sites = []
    for r in c.execute("SELECT k, ts, js FROM snapkv WHERE k LIKE 'Depot:%' ORDER BY ts DESC"):
        ev = json.loads(r["js"])
        nm, sy = _name(c, ev.get("MarketID"))
        res = ev.get("ResourcesRequired") or []
        miss = sum(max(0, x["RequiredAmount"] - x["ProvidedAmount"]) for x in res)
        buy = sum(max(0, x["RequiredAmount"] - x["ProvidedAmount"] - stock.get(x.get("Name_Localised") or x.get("Name"), 0)) for x in res)
        val = sum(max(0, x["RequiredAmount"] - x["ProvidedAmount"]) * x["Payment"] for x in res)
        sites.append({"ev": ev, "name": nm, "sys": sy, "ts": r["ts"], "res": res, "miss": miss, "buy": buy, "val": val})
    sites = [x for x in sites if not x["ev"].get("ConstructionComplete") and not x["ev"].get("ConstructionFailed")]
    if not sites:
        return {"blocks": [helpers._block("Im Bau", [["Hinweis", "t"]], [["Keine Baustelle im Bau erfasst. Fliege eine Baustelle an und öffne das Kolonisierungs-Menü, dann erscheint sie hier."]])]}
    open_ = sites
    kpi = [["Baustellen im Bau", len(open_), "n"], ["Fehlende Tonnen", sum(x["miss"] for x in open_), "n"], ["Noch zu kaufen", sum(x["buy"] for x in open_), "n"],
           ["Warenwert (fehlt)", sum(x["val"] for x in open_), "cr"], ["Frachtraum", cap, "n"]]
    rows = []
    for x in sites:
        ev = x["ev"]
        rows.append([x["name"], x["sys"], "Im Bau", ev.get("ConstructionProgress") or 0, x["miss"], x["buy"], math.ceil(x["buy"] / cap) if cap and x["buy"] else None, x["val"], x["ts"]])
    blocks = [helpers._block("Baustellen", [["Baustelle", "t"], ["Im System", "t"], ["Stand", "t"], ["Fortschritt", "f"], ["Fehlt t", "n"], ["Noch kaufen t", "n"], ["Fahrten", "n"], ["Warenwert fehlt", "cr"], ["Letzter Stand", "d"]],
                             rows, "Fahrten = Tonnen, die du noch kaufen musst, geteilt durch deinen Frachtraum (aus der letzten Ausrüstung). Der Stand kommt nur, wenn du das Kolonisierungs-Menü öffnest.")]
    for x in sites[:5]:
        rr, need, info = [], {}, {}
        for q in x["res"]:
            nm_ = q.get("Name_Localised") or q.get("Name")
            m = max(0, q["RequiredAmount"] - q["ProvidedAmount"])
            ca = stock.get(nm_, 0)
            k = max(0, m - ca)
            s = _source(c, q.get("Name_Localised") or "") if k else None
            info[nm_] = (q["RequiredAmount"], ca, q["ProvidedAmount"], m)
            if k:
                need[nm_] = k
            rr.append([nm_, q["RequiredAmount"], ca, k, q["ProvidedAmount"], m, q["Payment"], m * q["Payment"],
                       s["station"] if s else None, s["system"] if s else None, s["buy"] if s else None, s["stock"] if s else None, s["seen"] if s else None])
        rr.sort(key=lambda r: (-r[3], -r[5]))
        ov = []
        for r_ in rr:
            st_ = "fertig" if r_[5] == 0 else "im Carrier gedeckt" if r_[3] == 0 else "teils im Carrier" if r_[2] else "offen"
            ov.append([r_[0], r_[1], r_[4], r_[5], r_[2], r_[3], (r_[4] / r_[1]) if r_[1] else 1, st_])
        ov.sort(key=lambda r: ({"offen": 0, "teils im Carrier": 1, "im Carrier gedeckt": 2, "fertig": 3}[r[7]], -r[3]))
        ov.append(["Summe", sum(r[1] for r in ov), sum(r[2] for r in ov), sum(r[3] for r in ov), sum(r[4] for r in ov), sum(r[5] for r in ov),
                   (sum(r[2] for r in ov) / sum(r[1] for r in ov)) if sum(r[1] for r in ov) else 1, ""])
        t0 = helpers._block("", [["Ware", "t"], ["Benötigt t", "n"], ["Geliefert t", "n"], ["Fehlt t", "n"], ["Im Carrier t", "n"], ["Noch kaufen t", "n"], ["Fortschritt", "f"], ["Status", "t"]], ov,
                            "Unabhängig von Markt und Preis. Fehlt = Benötigt minus Geliefert. Im Carrier = dein Bestand aus Schiff, Fleet Carrier, Bestand. Noch kaufen = Fehlt minus Im Carrier. Offene Waren stehen oben.")
        t0["label"] = "Überblick"
        t1 = helpers._block("", [["Ware", "t"], ["Benötigt t", "n"], ["Im Carrier t", "n"], ["Noch kaufen t", "n"], ["Geliefert t", "n"], ["Fehlt t", "n"], ["Cr / t", "n"], ["Wert fehlt", "n"],
                                 ["Günstigster Bezug", "t"], ["Im System", "t"], ["Preis", "n"], ["Bestand", "n"], ["Marktstand", "d"]], rr,
                            "Im Carrier = dein Bestand aus Schiff, Fleet Carrier, Bestand. Noch kaufen = Fehlt minus Im Carrier. Fracht, die gerade im Schiff liegt, ist nicht eingerechnet. "
                            "Bezug = günstigster Kaufpreis mit Bestand auf deinen gespeicherten Märkten (Marktstand = zuletzt geöffnet). Cr / t ist der Wert, den das Spiel für die Ware angibt.")
        t1["label"] = "Günstigster Preis"
        t2 = {"label": "Wenige Märkte", "groups": _cover(c, need, info),
              "note": "Egal zu welchem Preis: Die Märkte stehen nach abgedeckten Tonnen geordnet, der größte zuerst. Jede Ware steht nur beim ersten Markt, der sie liefern kann. Es zählt, was du noch kaufen musst (nach Abzug des Carrier-Bestands). Bestand und Preis laut zuletzt geöffnetem Marktstand."}
        blocks.append({"title": f"Benötigt: {x['name']}", "alts": [t0, t1, t2]})
    lt = c.execute("SELECT ts, k1, k2, n1 FROM ce WHERE kind='ccon' ORDER BY ts DESC").fetchall()
    if lt:
        days = {}
        for r in lt:
            days.setdefault(helpers._lts(r["ts"]).strftime("%d.%m.%Y"), []).append(r)
        groups = []
        for d, rs in days.items():
            sites_ = {_name(c, int(r["k1"]) if r["k1"].isdigit() else 0)[0] for r in rs}
            groups.append({"label": d, "sum": [[len({r["ts"] for r in rs}), "Lieferungen"], [sum(r["n1"] for r in rs), "t"], [len({r["k2"] for r in rs}), "Waren"]],
                           "cols": [["Zeit", "d"], ["Baustelle", "t"], ["Ware", "t"], ["Tonnen", "n"]],
                           "rows": [[r["ts"], _name(c, int(r["k1"]) if r["k1"].isdigit() else 0)[0], r["k2"], r["n1"]] for r in rs]})
        blocks.append({"title": "Lieferungen", "groups": groups, "note": "Je Tag zusammengefasst. Tag anklicken für die einzelnen Lieferungen."})
    return {"kpi": kpi, "blocks": blocks}


# Meine Kolonien: Systeme laut Spiel-Bildschirm "Meine Kolonien" (Stand 25.10.2026). Weitere Systeme trägt Claude auf Zuruf nach.
_SEED = [("Pegasi Sector GO-E a13-2", 1, 11, 0, 24, 1), ("Col 285 Sector TY-K b23-3", 1, 20, 2, 19, None), ("Col 285 Sector DD-I c10-4", 2, 50, 2, 31, None)]


def _seed(c):
    if c.execute("SELECT COUNT(*) FROM colonies").fetchone()[0]:
        return
    try:
        c.executemany("INSERT OR IGNORE INTO colonies VALUES(?,?,?,?,?,?,'')", _SEED)
        c.commit()
    except sqlite3.Error:
        pass


def _clean(n):
    return n.replace("$EXT_PANEL_ColonisationShip;", "Kolonisierungsschiff:").replace("Planetary Construction Site:", "Baustelle:")


def meine_view(c):
    _seed(c)
    cols = c.execute("SELECT * FROM colonies ORDER BY rowid").fetchall()
    nf = lambda v, d=0: ("{:,.%df}" % d).format(v).replace(",", "X").replace(".", ",").replace("X", ".")
    deps = {}
    for r in c.execute("SELECT js FROM snapkv WHERE k LIKE 'Depot:%'"):
        ev = json.loads(r["js"])
        deps[ev.get("MarketID")] = ev
    over, blocks = [], []
    for col in cols:
        sy = col["system"]
        info = {}
        r = c.execute("SELECT ts, js FROM snapkv WHERE k=?", ("Sys:" + sy,)).fetchone()
        if r:
            info = json.loads(r["js"])
        jr = c.execute("SELECT COUNT(*) n, MIN(ts) f, MAX(ts) l, COUNT(DISTINCT substr(ts,1,10)) d FROM ce WHERE kind='jump' AND k1=?", (sy,)).fetchone()
        over.append([sy, f"{col['a']} / {col['amax']}", f"{col['b']} / {col['bmax']}", col["build"], info.get("pop"), info.get("fac") or None, info.get("gov") or None,
                     info.get("eco") or None, jr["n"], jr["f"], jr["l"]])
        pos = info.get("pos") or []
        if not pos:
            p_ = c.execute("SELECT x, y, z FROM syspos WHERE system=?", (sy,)).fetchone()
            pos = list(p_) if p_ else []
        kv = [["Plätze (Raute-Symbol im Spiel)", f"{col['a']} von {col['amax']}"], ["Plätze (Gebäude-Symbol im Spiel)", f"{col['b']} von {col['bmax']}"],
              ["Im Bau (Kran-Symbol im Spiel)", "-" if col["build"] is None else str(col["build"])]]
        if info:
            kv += [["Einwohner", nf(info.get("pop") or 0)], ["Kontrollierende Fraktion", info.get("fac") or "-"], ["Zustand der Fraktion", info.get("fst") or "-"], ["Regierung", info.get("gov") or "-"],
                   ["Wirtschaft", ", ".join(x for x in (info.get("eco"), info.get("eco2")) if x and x != "n/v") or "-"], ["Sicherheit", info.get("sec") or "-"], ["Allianz", info.get("alleg") or "-"]]
            if info.get("power") or info.get("pp"):
                kv.append(["Powerplay", " · ".join(x for x in (info.get("pp"), info.get("power")) if x)])
        else:
            kv.append(["Systemdaten", "noch nicht erfasst (erscheinen beim nächsten Sprung oder Start im System)"])
        if len(pos) == 3:
            kv += [["Koordinaten (x / y / z)", " / ".join(nf(v, 2) for v in pos)], ["Entfernung zu Sol", nf(sum(v * v for v in pos) ** 0.5, 1) + " Ly"]]
        kv += [["Sprünge ins System", f"{jr['n']} an {jr['d']} Tagen"]]
        groups = [{"label": "Daten", "open": True, "sum": [], "cols": [["Merkmal", "t"], ["Wert", "t"]], "rows": kv}]
        # Stationen
        st = [[_clean(r_["name"]), r_["type"], r_["faction"], r_["gov"], r_["eco"], r_["first"], r_["last"]] for r_ in
              c.execute("SELECT name, type, faction, gov, eco, first, last FROM stdb WHERE system=? ORDER BY first", (sy,))]
        groups.append({"label": "Stationen und Siedlungen", "open": bool(st), "sum": [[len(st), "Einträge"]],
                       "cols": [["Name", "t"], ["Art", "t"], ["Fraktion", "t"], ["Regierung", "t"], ["Wirtschaft", "t"], ["Erstmals gesehen", "d"], ["Zuletzt gesehen", "d"]], "rows": st})
        # Spuren der Entstehung
        sp = []
        for r_ in c.execute("SELECT name, type, market_id, first, last FROM stdb WHERE system=? AND (name LIKE '%ColonisationShip%' OR type LIKE '%Construction%' OR faction='Brewer Corporation') ORDER BY first", (sy,)):
            ev = deps.get(r_["market_id"]) if r_["market_id"] else None
            if "ColonisationShip" in r_["name"]:
                art, stand = "Kolonisierungsschiff", "-"
            else:
                art = "Baustelle"
                stand = "-" if not ev else ("fertig" if ev.get("ConstructionComplete") else "gescheitert" if ev.get("ConstructionFailed") else f"{(ev.get('ConstructionProgress') or 0) * 100:.0f} %")
            sp.append([_clean(r_["name"]), art, r_["first"], r_["last"], stand])
        groups.append({"label": "Spuren der Entstehung", "open": bool(sp), "sum": [[len(sp), "Einträge"]],
                       "cols": [["Name", "t"], ["Art", "t"], ["Erstmals gesehen", "d"], ["Zuletzt gesehen", "d"], ["Stand", "t"]], "rows": sp})
        # Fraktionen (letzte Messung)
        fr = []
        last = c.execute("SELECT MAX(ts) t FROM fac WHERE system=?", (sy,)).fetchone()["t"]
        if last:
            fr = [[r_["name"], r_["gov"], r_["state"], r_["inf"], r_["rep"]] for r_ in c.execute("SELECT name, gov, state, inf, rep FROM fac WHERE system=? AND ts=? ORDER BY inf DESC", (sy, last))]
        groups.append({"label": "Fraktionen", "open": False, "sum": [[len(fr), "Fraktionen"]],
                       "cols": [["Fraktion", "t"], ["Regierung", "t"], ["Zustand", "t"], ["Einfluss %", "r"], ["Ruf", "r"]], "rows": fr})
        # Aktivität
        ak = []
        k_ = c.execute("SELECT COUNT(*) n, SUM(n1) s FROM ce WHERE kind='kill' AND sys=?", (sy,)).fetchone()
        ak.append(["Abschüsse", k_["n"], k_["s"] or 0])
        t_ = c.execute("SELECT COUNT(*) n, SUM(n3) s FROM ce WHERE kind='trade' AND k3='sell' AND sys=?", (sy,)).fetchone()
        ak.append(["Verkäufe (Gewinn)", t_["n"], t_["s"] or 0])
        b_ = c.execute("SELECT COUNT(*) n, SUM(n1) s FROM ce WHERE kind='trade' AND k3='buy' AND sys=?", (sy,)).fetchone()
        ak.append(["Einkäufe (Ausgaben)", b_["n"], b_["s"] or 0])
        m_ = c.execute("SELECT COUNT(*) n FROM ce WHERE kind='mine' AND sys=?", (sy,)).fetchone()
        ak.append(["Abgebautes Material", m_["n"], 0])
        cr = c.execute("SELECT COUNT(*) n, MIN(ts) f, MAX(ts) l FROM ce WHERE kind='stn' AND k3='FleetCarrier' AND sys=?", (sy,)).fetchone()
        ak.append(["Carrier-Besuche", cr["n"], 0])
        groups.append({"label": "Deine Aktivität im System", "open": False, "sum": [], "cols": [["Art", "t"], ["Anzahl", "n"], ["Credits", "cr"]], "rows": ak})
        blocks.append({"title": sy, "groups": groups})
    head = helpers._block("Meine Kolonien", [["System", "t"], ["Raute", "t"], ["Gebäude", "t"], ["Im Bau", "n"], ["Einwohner", "n"], ["Fraktion", "t"], ["Regierung", "t"], ["Wirtschaft", "t"],
                                           ["Sprünge", "n"], ["Erster Besuch", "d"], ["Letzter Besuch", "d"]], over,
                          "Plätze, Gebäude und Im-Bau-Zahlen stammen aus deinem Spiel-Bildschirm „Meine Kolonien“ (Stand 25.10.2026), die Symbole sind dort nicht beschriftet. Alles andere kommt aus deinem Journal. Wer Architekt ist, schreibt das Journal nicht.")
    return {"blocks": [head] + blocks}
