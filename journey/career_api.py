"""Karriere-API: liefert Blöcke für die Tabellen-Oberfläche (/api/career)."""

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import bodydata, career_ingest, carrier, database, dienstakte, explval, helpers, hotx, kolonien, market_ingest, mining, missions, rueckblick, timefmt, views_misc
from . import timefmt as _tf


def _side_by_side(rows):
    """Schiffe als Spalten, Kernmodule/Schild/Waffen als Zeilen (aus dem letzten gespeicherten Loadout je Schiff)."""
    fm = lambda x, d=1: (f"{x:.{d}f}").replace(".", ",")
    ships = []
    for i, r in enumerate(rows):
        lo = json.loads(r["js"])
        mods = lo.get("Modules", [])
        mi = market_ingest.mod_info
        core = {}
        weap, util, opt = {}, {}, {}
        boosters, eng_n = 0, 0
        for m in mods:
            it = str(m.get("Item", "")).lower()
            slot = str(m.get("Slot", ""))
            name, cat, cls = mi(it)
            en = m.get("Engineering")
            tag = (" ✎G" + str(en.get("Level", ""))) if en else ""
            eng_n += 1 if en else 0
            lab = (name + " " + cls).strip() + tag
            if "shieldbooster" in it:
                boosters += 1
            elif "shieldgenerator" in it:
                core["Schild"] = lab
            elif "powerplant" in it:
                core["Kraftwerk"] = lab
            elif "_engine" in it:
                core["Triebwerk"] = lab
            elif "hyperdrive" in it:
                core["FSD"] = lab
            elif "lifesupport" in it:
                core["Lebenserhaltung"] = lab
            elif "powerdistributor" in it:
                core["Energieverteiler"] = lab
            elif "sensors" in it or "_sensor" in it:
                core["Sensoren"] = lab
            elif "armour" in it:
                core["Panzerung"] = name.replace("Panzerung: ", "") + tag
            elif it.startswith("hpt_"):
                (util if cat == "Utility" else weap)[lab] = (util if cat == "Utility" else weap).get(lab, 0) + 1
            elif it.startswith("int_") and "fueltank" not in it and "cockpit" not in it:
                opt[lab] = opt.get(lab, 0) + 1
        fcap = lo.get("FuelCapacity")
        tank = fcap.get("Main", 0) if isinstance(fcap, dict) else (fcap or 0)
        need = helpers._ship_need(str(lo.get("Ship", "")).lower())
        grp = lambda d: ", ".join(f"{k} ×{v}" if v > 1 else k for k, v in sorted(d.items())) or "-"
        hull = lo.get("HullHealth")
        ships.append({
            "title": ("▶ " if i == 0 else "") + career_ingest.ship_name(lo) + ((" „" + lo["ShipName"] + "“") if lo.get("ShipName") else ""),
            "v": [fm(lo.get("MaxJumpRange", 0) or 0) + " Ly", str(lo.get("CargoCapacity", 0) or 0) + " t", fm(tank, 0 if float(tank).is_integer() else 1) + " t",
                  fm(lo.get("UnladenMass", 0) or 0) + " t", f"{round((hull if hull is not None else 1) * 100)} %",
                  core.get("Triebwerk", "-"), core.get("FSD", "-"), core.get("Kraftwerk", "-"), core.get("Energieverteiler", "-"),
                  core.get("Sensoren", "-"), core.get("Lebenserhaltung", "-"), core.get("Panzerung", "-"), core.get("Schild", "-"), str(boosters),
                  grp(weap), grp(util), grp(opt), str(eng_n),
                  timefmt._nf((lo.get("HullValue", 0) or 0) + (lo.get("ModulesValue", 0) or 0)) + " Cr", timefmt._nf(lo.get("Rebuy", 0) or 0) + " Cr",
                  helpers.PAD_NAME.get(need, "unbekannt")]})
    labels = ["Sprungweite (laut Loadout)", "Fracht", "Tank", "Leermasse", "Rumpfzustand (Stand Loadout)", "Triebwerk", "FSD", "Kraftwerk", "Energieverteiler",
              "Sensoren", "Lebenserhaltung", "Panzerung", "Schildgenerator", "Schildverstärker", "Waffen", "Utility", "Optionale Module", "Modifizierte Module",
              "Wert", "Rebuy", "Landeplatz"]
    body = [[lab] + [sh["v"][j] for sh in ships] for j, lab in enumerate(labels)]
    return helpers._block("Schiffe nebeneinander (letzter bekannter Loadout je Schiff)", [["", "t"]] + [[sh["title"], "t"] for sh in ships], body,
                          "▶ = zuletzt gewechseltes Schiff. ✎G = Engineering-Stufe. Sprungweite, Rumpfzustand und Modulwerte stammen aus dem Loadout-Ereignis; Schildstärke, Panzerungswerte und Geschwindigkeit stehen nicht im Journal und werden nicht geraten.")


def _mat_stock(c):
    """Materialbestand nach internem Namen: Stand des letzten Materials-Ereignisses plus gesammelt/getauscht minus verbraucht.
    Rueckgabe: (ts, {name: [Kategorie, Anzeigename, Menge]})"""
    c.row_factory = sqlite3.Row
    ts, m = helpers._jload(c, "Materials")
    cur = {}
    for cat in ("Raw", "Manufactured", "Encoded"):
        for it in (m or {}).get(cat, []):
            nm = str(it.get("Name", "")).lower()
            if nm:
                cur[nm] = [cat, it.get("Name_Localised") or str(it.get("Name", "?")).title(), it.get("Count", 0)]
    disp = {}
    for r in c.execute("SELECT k1, k2, k3 FROM ce WHERE kind='mat' AND k3!='' GROUP BY k3"):
        disp[r["k3"]] = (r["k1"], r["k2"])
    for r in c.execute("SELECT k2, y FROM ce WHERE kind IN ('ing','mcon') AND y!='' GROUP BY k2"):
        disp.setdefault(r["k2"], ("", r["y"]))
    if ts:
        for r in c.execute("SELECT k3, SUM(n1) s FROM ce WHERE kind='mat' AND k3!='' AND ts > ? GROUP BY k3", (ts,)):
            o = cur.setdefault(r["k3"], [disp.get(r["k3"], ("", ""))[0], disp.get(r["k3"], ("", r["k3"].title()))[1], 0])
            o[2] = max(0, o[2] + r["s"])
        for r in c.execute("SELECT k2, SUM(n1) s FROM ce WHERE kind IN ('ing','mcon') AND ts > ? GROUP BY k2", (ts,)):
            o = cur.setdefault(r["k2"], [disp.get(r["k2"], ("", ""))[0], disp.get(r["k2"], ("", r["k2"].title()))[1], 0])
            o[2] = max(0, o[2] - r["s"])
    for k, o in cur.items():
        o[2] = int(o[2])
        if not o[1] or o[1] == k.title():
            o[1] = disp.get(k, ("", o[1] or k.title()))[1] or k.title()
        if not o[0]:
            o[0] = disp.get(k, ("", ""))[0]
    return ts, cur


def career_api(p):
    op = p.get("op", "")
    cut = helpers._cutoff(p.get("days"))
    c = database._mdb()
    c.row_factory = sqlite3.Row
    try:
        W = " AND ts >= ?" if cut else ""
        A = (cut,) if cut else ()
        mode = p.get("mode", "")
        GROUND = "('Zu Fuß','SRV')"
        MF = (f" AND ship NOT IN {GROUND}" if mode == "space" else f" AND ship IN {GROUND}" if mode == "ground" else "")
        KMODE = {"kill", "target", "hit", "hull", "shield", "intd", "death"}

        def Q(sql, *args):
            return c.execute(sql, args).fetchall()

        def K(kind, extra="", *args):
            return c.execute(f"SELECT * FROM ce WHERE kind=?{W}{MF if kind in KMODE else ''} {extra}", (kind,) + A + args).fetchall()

        def hours():
            return len(helpers._active(c, cut)) / 6.0

        def hours_of(files):
            """Aktive Zeit nur innerhalb der Journal-Dateien (Sessions), die das jeweilige Ereignis enthalten."""
            n = 0
            for r in Q("SELECT first, last FROM jc WHERE name IN (%s)" % ",".join("?" * len(files)), *files) if files else []:
                lo = max((r["first"] or "")[:15], cut[:15] if cut else "")
                n += c.execute("SELECT COUNT(*) FROM act WHERE b BETWEEN ? AND ?", (lo, (r["last"] or "")[:15])).fetchone()[0]
            return n / 6.0

        def day_active():
            d = {}
            for b in helpers._active(c, cut):
                k = helpers._bdt(b).strftime("%Y-%m-%d")
                d[k] = d.get(k, 0) + 1 / 6.0
            return d

        def ldate(ts):
            return helpers._lts(ts).strftime("%Y-%m-%d")

        if op == "status":
            n = c.execute("SELECT COUNT(*) FROM ce").fetchone()[0]
            return {"state": career_ingest.CAREER["state"], "done": career_ingest.CAREER["done"], "total": career_ingest.CAREER["total"], "files": career_ingest.CAREER["files"],
                    "rows": n, "error": career_ingest.CAREER["error"]}

        # ---------------------------------------------------------------- Kampf
        if op == "k_over":
            ks = K("kill")
            bonds = [r for r in ks if r["x"] == "bond"]
            bnty = [r for r in ks if r["x"] != "bond"]
            tot = sum(r["n1"] for r in ks)
            vo = sum(r["n1"] for r in K("vouch"))
            h = hours()
            deaths = len(K("death"))
            h = hours_of(sorted({r["file"] for r in ks}))
            kpi = [["Abschüsse gesamt", len(ks), "n"], ["Kampfbonds", len(bonds), "n"], ["Kopfgeld-Abschüsse", len(bnty), "n"],
                   ["Belohnungen verdient", tot, "cr"], ["Davon Bonds", sum(r["n1"] for r in bonds), "cr"],
                   ["Davon Kopfgelder", sum(r["n1"] for r in bnty), "cr"], ["Gutscheine eingelöst", vo, "cr"],
                   ["Verdient − eingelöst", tot - vo, "cr"], ["Aktive Zeit (Kampf-Sessions)", h, "h"],
                   ["Abschüsse / h", len(ks) / h if h else 0, "r"], ["Kampf-Credits / h", tot / h if h else 0, "cr"],
                   ["Ø pro Abschuss", tot / len(ks) if ks else 0, "cr"],
                   ["Abschüsse Raumschiff (alle)", c.execute(f"SELECT COUNT(*) FROM ce WHERE kind='kill'{W} AND ship NOT IN {GROUND}", A).fetchone()[0], "n"],
                   ["Abschüsse zu Fuß/SRV (alle)", c.execute(f"SELECT COUNT(*) FROM ce WHERE kind='kill'{W} AND ship IN {GROUND}", A).fetchone()[0], "n"], ["Scans Zielschiffe", len(K("target")), "n"],
                   ["Zerstört (Tode)", deaths, "n"]]
            days, act = {}, day_active()
            for r in ks:
                d = days.setdefault(ldate(r["ts"]), [0, 0, 0, 0])
                d[0] += 1
                d[1 if r["x"] == "bond" else 2] += r["n1"]
                d[3] += r["n1"]
            rows = [[k, v[0], v[1], v[2], v[3], act.get(k, 0), v[3] / act[k] if act.get(k) else 0,
                     v[0] / act[k] if act.get(k) else 0] for k, v in sorted(days.items(), reverse=True)]
            return {"kpi": kpi, "blocks": [helpers._block("Kampf pro Tag", [["Datum", "t"], ["Abschüsse", "n"], ["Bonds", "cr"],
                    ["Kopfgelder", "cr"], ["Gesamt", "cr"], ["Aktiv", "h"], ["Cr / h", "cr"], ["Kills / h", "r"]], rows)]}
        if op == "k_enemy":
            ks = K("kill")
            f1, f2, shp, sol = {}, {}, {}, {}
            for r in ks:
                for d, key in ((f1, r["k1"]), (f2, r["k2"])):
                    o = d.setdefault(key or "?", [0, 0])
                    o[0] += 1
                    o[1] += r["n1"]
                if r["y"]:
                    o = shp.setdefault(r["y"].replace("_", " ").title() if "_" in r["y"] else r["y"], [0, 0])
                    o[0] += 1
                    o[1] += r["n1"]
            mk = lambda d: [[k, v[0], v[1], v[1] / v[0]] for k, v in sorted(d.items(), key=lambda kv: -kv[1][1])]
            cols = lambda t: [[t, "t"], ["Abschüsse", "n"], ["Belohnung", "cr"], ["Ø", "cr"]]
            tg = K("target")
            ts, tr, tf, tl = {}, {}, {}, {}
            for r in tg:
                o = ts.setdefault(r["k1"] or "?", [0, 0, 0])
                o[0] += 1
                o[1] += r["n1"]
                o[2] += r["n2"]
                tr[r["k2"] or "?"] = tr.get(r["k2"] or "?", 0) + 1
                tl[r["x"] or "?"] = tl.get(r["x"] or "?", 0) + 1
                o = tf.setdefault(r["k3"] or "(keine)", [0, 0])
                o[0] += 1
                o[1] += 1 if "anted" in (r["x"] or "") else 0
            bl = [helpers._block("Gegnerfraktionen (Opfer)", cols("Fraktion"), mk(f1)),
                  helpers._block("Auftraggeber der Belohnung", cols("Fraktion"), mk(f2)),
                  helpers._block("Kopfgeld-Ziele nach Schiff", cols("Schiff"), mk(shp))]
            bl.append(helpers._block("Gescannte Zielschiffe", [["Schiff", "t"], ["Scans", "n"], ["Ø Rumpf", "p"], ["Ø Schild", "p"]],
                             [[k, v[0], v[1] / v[0], v[2] / v[0]] for k, v in sorted(ts.items(), key=lambda kv: -kv[1][0])]))
            bl.append(helpers._block("Pilotränge der Ziele", [["Rang", "t"], ["Scans", "n"]], sorted([[k, v] for k, v in tr.items()], key=lambda r: -r[1])))
            bl.append(helpers._block("Rechtsstatus der Ziele", [["Status", "t"], ["Scans", "n"]], sorted([[k, v] for k, v in tl.items()], key=lambda r: -r[1])))
            bl.append(helpers._block("Fraktionen der Ziele", [["Fraktion", "t"], ["Scans", "n"], ["Gesucht", "n"]],
                             sorted([[k, v[0], v[1]] for k, v in tf.items()], key=lambda r: -r[1])))
            return {"blocks": bl}
        if op == "k_places":
            ks = K("kill")
            sy, zo = {}, {}
            for r in ks:
                o = sy.setdefault(r["sys"] or "?", [0, 0, 0, 0])
                o[0] += 1
                o[1 if r["x"] == "bond" else 2] += r["n1"]
                o[3] += r["n1"]
                z = zo.setdefault(r["k3"] or "(kein Kampfbereich)", [0, 0])
                z[0] += 1
                z[1] += r["n1"]
            dr = {}
            for r in K("drop"):
                dr[r["k1"] or "?"] = dr.get(r["k1"] or "?", 0) + 1
            return {"blocks": [
                helpers._block("Systeme", [["System", "t"], ["Abschüsse", "n"], ["Bonds", "cr"], ["Kopfgelder", "cr"], ["Gesamt", "cr"]],
                       [[k] + v for k, v in sorted(sy.items(), key=lambda kv: -kv[1][3])]),
                helpers._block("Kampfbereiche (Intensität)", [["Typ", "t"], ["Abschüsse", "n"], ["Belohnung", "cr"], ["Ø", "cr"]],
                       [[k, v[0], v[1], v[1] / v[0]] for k, v in sorted(zo.items(), key=lambda kv: -kv[1][1])]),
                helpers._block("Eingeflogene Zielorte (Supercruise)", [["Typ", "t"], ["Anzahl", "n"]],
                       sorted([[k, v] for k, v in dr.items()], key=lambda r: -r[1]))]}
        if op == "k_sess":
            ks, mer = {}, {}
            for r in K("kill"):
                o = ks.setdefault(r["file"], [0, 0])
                o[0] += 1
                o[1] += r["n1"]
            for r in K("merit"):
                mer[r["file"]] = mer.get(r["file"], 0) + r["n1"]
            dth = {}
            for r in K("death"):
                dth[r["file"]] = dth.get(r["file"], 0) + 1
            rows = []
            for r in Q("SELECT name, first, last FROM jc ORDER BY first DESC"):
                if r["name"] not in ks and r["name"] not in mer:
                    continue
                if cut and (r["last"] or "") < cut:
                    continue
                dur = (timefmt.parse_ts(r["last"]) - timefmt.parse_ts(r["first"])).total_seconds() if r["first"] else 0
                k = ks.get(r["name"], [0, 0])
                rows.append([r["first"], dur, k[0], k[1], k[1] / (dur / 3600) if dur > 60 else 0,
                             k[0] / (dur / 3600) if dur > 60 else 0, mer.get(r["name"], 0), dth.get(r["name"], 0)])
            return {"blocks": [helpers._block("Kampf-Sessions (Journal-Dateien)", [["Start", "d"], ["Dauer", "s"], ["Abschüsse", "n"],
                    ["Belohnung", "cr"], ["Cr / h", "cr"], ["Kills / h", "r"], ["Merits", "n"], ["Tode", "n"]], rows)]}
        if op == "k_conf":
            rows = []
            kills = {}
            for r in Q("SELECT sys, k1, COUNT(*) n, SUM(n1) s FROM ce WHERE kind='kill'" + MF + " GROUP BY sys, k1"):
                kills[(r["sys"], r["k1"])] = (r["n"], r["s"])
            seen = set()
            for r in Q("SELECT * FROM ce WHERE kind='conf' ORDER BY ts DESC, id DESC"):
                key = (r["sys"], r["k1"], r["k2"])
                if key in seen:
                    continue
                seen.add(key)
                if cut and r["ts"] < cut:
                    continue
                wt, s1, s2 = (r["x"].split("|") + ["", "", ""])[:3]
                k1, k2 = kills.get((r["sys"], r["k1"]), (0, 0)), kills.get((r["sys"], r["k2"]), (0, 0))
                rows.append([r["ts"], r["sys"], bodydata.STATE_DE.get(wt.title().replace(" ", ""), wt), r["k3"], r["k1"], r["n1"], s1,
                             r["k2"], r["n2"], s2, k1[0] + k2[0], k1[1] + k2[1]])
            return {"blocks": [helpers._block("Konflikte in besuchten Systemen (jüngster Stand)", [["Stand", "d"], ["System", "t"], ["Art", "t"],
                    ["Status", "t"], ["Fraktion 1", "t"], ["Tage", "n"], ["Einsatz", "t"], ["Fraktion 2", "t"], ["Tage", "n"],
                    ["Einsatz", "t"], ["Meine Abschüsse", "n"], ["Verdient", "cr"]], rows)],
                    "note": "Tage = Gewinntage des Konflikts; Abschüsse = mein Beitrag gegen eine der Parteien im System."}
        if op == "k_loss":
            dth = [[r["ts"], r["sys"], r["ship"], r["k1"], r["k2"]] for r in K("death", "ORDER BY ts DESC")]
            cr = [[r["ts"], r["sys"], r["k1"], r["k2"], r["k3"], r["n1"]] for r in K("crime", "ORDER BY ts DESC")]
            ia = {}
            for r in K("intd"):
                o = ia.setdefault((r["k1"], r["x"]), 0)
                ia[(r["k1"], r["x"])] = o + 1
            names = {"interdicted": "Von NPC/Spieler abgefangen", "interdiction": "Selbst abgefangen", "escaped": "Abfangen entkommen"}
            hit = len(K("hit"))
            hd = K("hull")
            sd = len([r for r in K("shield") if r["k1"] == "down"])
            fines = sum(r["n1"] for r in K("fine") if r["k1"] != "Resurrect")
            rebuy = sum(r["n1"] for r in K("fine") if r["k1"] == "Resurrect")
            inc_f, reb_f, fin_f, dth_f = {}, {}, {}, {}
            for r in K("cash"):
                if r["n1"] > 0:
                    inc_f[r["file"]] = inc_f.get(r["file"], 0) + r["n1"]
            for r in K("fine"):
                if r["k1"] == "Resurrect":
                    reb_f[r["file"]] = reb_f.get(r["file"], 0) + r["n1"]
                else:
                    fin_f[r["file"]] = fin_f.get(r["file"], 0) + r["n1"]
            for r in K("death"):
                dth_f[r["file"]] = dth_f.get(r["file"], 0) + 1
            ses = []
            for r in Q("SELECT name, first, last FROM jc ORDER BY first DESC"):
                f_ = r["name"]
                if not r["first"] or (cut and (r["last"] or "") < cut) or not (inc_f.get(f_) or reb_f.get(f_) or fin_f.get(f_) or dth_f.get(f_)):
                    continue
                inc_, lo_ = inc_f.get(f_, 0), reb_f.get(f_, 0) + fin_f.get(f_, 0)
                ses.append([r["first"], inc_, reb_f.get(f_, 0), fin_f.get(f_, 0), dth_f.get(f_, 0), inc_ - lo_, lo_ / inc_ if inc_ else 0])
            tot_inc = sum(inc_f.values())
            kpi = [["Tode", len(dth), "n"], ["Verbrechen", len(cr), "n"], ["Strafen bezahlt", fines, "cr"], ["Rebuy-Kosten", rebuy, "cr"],
                   ["Ø Kosten pro Tod", rebuy / len(dth) if dth else 0, "cr"], ["Verlustanteil an Einnahmen", (rebuy + fines) / tot_inc if tot_inc else 0, "f"],
                   ["Treffer erhalten", hit, "n"], ["Rumpfschäden-Ereignisse", len(hd), "n"], ["Schildausfälle", sd, "n"]]
            return {"kpi": kpi, "blocks": [
                helpers._block("Verluste vs. Gewinn je Session", [["Start", "d"], ["Einnahmen", "cr"], ["Rebuy", "cr"], ["Strafen", "cr"], ["Tode", "n"],
                       ["Netto nach Verlusten", "cr"], ["Verlustanteil", "f"]], ses,
                       "Einnahmen = alle positiven Buchungen der Session; Rebuy und Strafen laut Journal."),
                helpers._block("Zerstörungen", [["Zeit", "d"], ["System", "t"], ["Mein Schiff", "t"], ["Zerstört von", "t"], ["Schiff", "t"]], dth),
                helpers._block("Verbrechen", [["Zeit", "d"], ["System", "t"], ["Art", "t"], ["Fraktion", "t"], ["Opfer", "t"], ["Strafe", "cr"]], cr),
                helpers._block("Abfangmanöver", [["Art", "t"], ["Ausgang", "t"], ["Anzahl", "n"]],
                       [[names.get(k[0], k[0]), k[1] or "-", v] for k, v in sorted(ia.items())])]}

        if op == "report":
            now_ = datetime.now(timezone.utc)
            iso_ = lambda d_: d_.strftime("%Y-%m-%dT%H:%M:%SZ")

            def agg(d0, d1):
                a, b = iso_(d0), iso_(d1)
                one = lambda sql, *x: c.execute(sql, x).fetchone()[0] or 0
                o = {}
                o["inc"] = one("SELECT SUM(n1) FROM ce WHERE kind='cash' AND n1>0 AND ts>=? AND ts<?", a, b)
                o["out"] = -one("SELECT SUM(n1) FROM ce WHERE kind='cash' AND n1<0 AND ts>=? AND ts<?", a, b)
                o["net"] = o["inc"] - o["out"]
                o["h"] = one("SELECT COUNT(*) FROM act WHERE b>=? AND b<?", a[:15], b[:15]) / 6.0
                o["cph"] = o["inc"] / o["h"] if o["h"] else 0
                o["trade"] = one("SELECT SUM(n3) FROM ce WHERE kind='trade' AND k3='sell' AND ts>=? AND ts<?", a, b)
                o["kills"] = one("SELECT COUNT(*) FROM ce WHERE kind='kill' AND ts>=? AND ts<?", a, b)
                o["kreward"] = one("SELECT SUM(n1) FROM ce WHERE kind='kill' AND ts>=? AND ts<?", a, b)
                o["deaths"] = one("SELECT COUNT(*) FROM ce WHERE kind='death' AND ts>=? AND ts<?", a, b)
                o["expl"] = one("SELECT SUM(n1) FROM ce WHERE kind='cash' AND k1 IN ('Exploration','Exobiologie') AND n1>0 AND ts>=? AND ts<?", a, b)
                o["mis"] = one("SELECT COUNT(*) FROM ce WHERE kind='mis' AND k3='completed' AND ts>=? AND ts<?", a, b)
                o["jumps"] = one("SELECT COUNT(*) FROM ce WHERE kind='jump' AND ts>=? AND ts<?", a, b)
                o["dist"] = one("SELECT SUM(n1) FROM ce WHERE kind='jump' AND ts>=? AND ts<?", a, b)
                o["sys"] = one("SELECT COUNT(DISTINCT k1) FROM ce WHERE kind='jump' AND ts>=? AND ts<?", a, b)
                return o
            win = {}
            for nm_, dn in (("w7", 7), ("p7", 14), ("w30", 30), ("p30", 60)):
                d1 = now_ - timedelta(days=dn - (7 if nm_ == "p7" else 30 if nm_ == "p30" else dn))
                d0 = now_ - timedelta(days=dn)
                win[nm_] = agg(d0, d1 if nm_ in ("p7", "p30") else now_)
            spec = [("Einnahmen", "inc", "cr"), ("Ausgaben", "out", "cr"), ("Netto", "net", "cr"), ("Aktive Zeit", "h", "h"), ("Einnahmen / h", "cph", "cr"),
                    ("Handelsgewinn (real)", "trade", "cr"), ("Abschüsse", "kills", "n"), ("Kampfbelohnungen", "kreward", "cr"), ("Tode", "deaths", "n"),
                    ("Exploration + Exobiologie", "expl", "cr"), ("Missionen abgeschlossen", "mis", "n"), ("Sprünge", "jumps", "n"),
                    ("Strecke", "dist", "ly"), ("Verschiedene Systeme", "sys", "n")]

            def ftxt(v, k):
                return (f"{timefmt._nf(v)} Cr" if k == "cr" else f"{timefmt._nf(v, 1)} h" if k == "h" else f"{timefmt._nf(v, 1)} Ly" if k == "ly" else timefmt._nf(v))

            def dtxt(cur, prev, k):
                if not cur and not prev:
                    return "-"
                d_ = cur - prev
                t = ("+" if d_ > 0 else "") + ftxt(d_, k)
                return t + (f" ({d_ / prev * 100:+.0f} %)" if prev else "")
            rows_ = [[lbl, ftxt(win["w7"][k], kd), ftxt(win["p7"][k], kd), dtxt(win["w7"][k], win["p7"][k], kd),
                      ftxt(win["w30"][k], kd), ftxt(win["p30"][k], kd), dtxt(win["w30"][k], win["p30"][k], kd)] for lbl, k, kd in spec]
            # Tage der letzten 14 Tage
            since14 = iso_(now_ - timedelta(days=14))
            dd = {}
            for r in Q("SELECT ts, kind, n1, k3 FROM ce WHERE ts>=? AND kind IN ('cash','jump','kill')", since14):
                o = dd.setdefault(ldate(r["ts"]), [0, 0, 0])
                if r["kind"] == "cash" and r["n1"] > 0:
                    o[0] += r["n1"]
                elif r["kind"] == "jump":
                    o[1] += 1
                elif r["kind"] == "kill":
                    o[2] += 1
            act_ = {}
            for r in Q("SELECT b FROM act WHERE b>=?", since14[:15]):
                k_ = helpers._bdt(r["b"]).strftime("%Y-%m-%d")
                act_[k_] = act_.get(k_, 0) + 1 / 6.0
            day_rows = [[k, v[0], act_.get(k, 0), v[1], v[2]] for k, v in sorted(dd.items(), reverse=True)]
            w = win["w7"]
            return {"kpi": [["Netto (7 Tage)", w["net"], "cr"], ["Einnahmen (7 Tage)", w["inc"], "cr"], ["Aktive Zeit (7 Tage)", w["h"], "h"],
                            ["Sprünge (7 Tage)", w["jumps"], "n"], ["Abschüsse (7 Tage)", w["kills"], "n"], ["Tode (7 Tage)", w["deaths"], "n"]],
                    "blocks": [helpers._block("Wochen- und Monatsvergleich", [["Kennzahl", "t"], ["Letzte 7 Tage", "t"], ["Davor (7 Tage)", "t"], ["Änderung", "t"],
                                       ["Letzte 30 Tage", "t"], ["Davor (30 Tage)", "t"], ["Änderung", "t"]], rows_,
                                       "Unabhängig vom Zeitraum-Feld. 'Davor' ist der gleich lange Zeitraum direkt vor dem aktuellen."),
                               helpers._block("Letzte 14 Tage", [["Datum", "t"], ["Einnahmen", "cr"], ["Aktiv", "h"], ["Sprünge", "n"], ["Abschüsse", "n"]], day_rows)]}
        if op == "ko_meine":
            return kolonien.meine_view(c)
        if op == "c_stock":
            return kolonien.stock_view(c)
        if op in kolonien.OPS:
            return kolonien.ko_view(c, op, cut)
        if op in rueckblick.OPS:
            return rueckblick.rb_view(c, op, cut)
        if op in ("pa", "ml_over", "ml_orden"):
            return dienstakte.akte_view(c, op)
        if op == "lm_list":
            return {"error": "use /api/lm"}
        if op in ("replay_list", "replay"):
            return views_misc.replay_view(c, p)
        if op in ("g_mk", "g_pos"):
            return views_misc.gaps_view(c, op)
        if op in ("bi_species", "bi_sites"):
            return views_misc.bio_view(c, op)
        if op in ("b_over", "b_log"):
            return views_misc.bgs_view(c, op)
        if op in ("c_over", "c_jumps", "c_fin"):
            return carrier.carrier_view(c, op)
        if op in ("ms_open", "ms_dest", "ms_hist"):
            return missions.missions_view(c, op)
        if op.startswith("m_"):
            ms = mining.mining_data(c, cut)
            return mining.mining_view(c, op, ms)
        if op == "hot":
            posm, here, hs = helpers._posmap(c)
            ref = (p.get("ref") or "").strip()
            if ref:
                rp = posm.get(ref)
                refname, refpos = ref, rp
            else:
                refname, refpos = hs, here
            lim = helpers._num_range(p.get("range"))
            q = (p.get("q") or "").strip().lower()
            fcls, fres = p.get("cls", ""), p.get("res", "")
            rings = {}
            for r in Q("SELECT ts, sys, k1, k2, k3, x, n1, n2, n3 FROM ce WHERE kind='ring' ORDER BY ts"):
                o = rings.setdefault(r["k1"], {"cls": "", "res": "", "ls": None, "sys": r["sys"], "scan": False})
                if r["k2"]:
                    o["cls"] = r["k2"]
                if r["k3"]:
                    o["res"] = r["k3"]
                if r["x"] != "p":
                    o["scan"] = True
                    if r["n1"]:
                        o["ls"] = r["n1"]
            mapped = {r[0] for r in c.execute("SELECT k1 FROM ce WHERE kind='mapd'")}
            # Pro Ring zaehlt nur der neueste Scan (Detailscan vor FSS): aeltere, abweichende Funde werden verworfen
            evs = {}
            for r in Q("SELECT ts, file, pos, sys, k1, k2, k3, x, n1 FROM ce WHERE kind='hot' ORDER BY ts, file, pos"):
                evs.setdefault((r["k1"], r["file"], r["pos"]), []).append(r)
            newest = {}
            for (rn, _f, _p), lst in evs.items():
                rank = (1 if lst[0]["k3"] == "DSS" else 0, lst[0]["ts"])
                if rn not in newest or rank >= newest[rn][0]:
                    newest[rn] = (rank, lst)
            hot = {}
            for rn, (_rk, lst) in newest.items():
                for r in lst:
                    hot[(rn, r["x"] or r["k2"])] = {"ring": rn, "mineral": r["k2"], "raw": r["x"], "count": int(r["n1"]), "src": r["k3"], "ts": r["ts"], "sys": r["sys"]}
            mins, rows_ = {}, []
            hx = hotx._hotx_load(c)
            nhid = 0
            for (rn, _m), h in list(hot.items()):
                if hotx._hotx_hidden(hx, rn, (h["raw"], h["mineral"]), h["ts"]):
                    nhid += 1
                    del hot[(rn, _m)]
            for (rn, _m), h in hot.items():
                ri = rings.get(rn, {})
                mins[h["mineral"]] = mins.get(h["mineral"], 0) + 1
                if q and q not in (h["mineral"] + " " + h["raw"]).lower():
                    continue
                if fcls and ri.get("cls") != fcls:
                    continue
                if fres and ri.get("res") != fres:
                    continue
                dl = helpers._d3(refpos, posm.get(h["sys"])) if refpos else None
                if h["sys"] == refname:
                    dl = 0.0
                if lim and (dl is None or dl > lim):
                    continue
                parent = bodydata.RING_RE.sub("", rn)
                rows_.append({"mineral": h["mineral"], "raw": h["raw"], "count": h["count"], "ring": rn, "parent": parent, "letter": rn[len(parent):].strip(),
                              "cls": ri.get("cls", ""), "res": ri.get("res", ""), "ls": ri.get("ls"), "system": h["sys"], "dist": dl,
                              "src": h["src"], "ts": h["ts"], "dss": rn in mapped})
            srt = p.get("sort", "dist")
            if srt == "count":
                rows_.sort(key=lambda r: (-r["count"], r["dist"] if r["dist"] is not None else 1e12))
            elif srt == "new":
                rows_.sort(key=lambda r: r["ts"], reverse=True)
            else:
                rows_.sort(key=lambda r: (r["dist"] is None, r["dist"] if r["dist"] is not None else 0, -r["count"]))
            allm = len({h["ring"] for h in hot.values()})
            return {"rows": rows_[:1000], "total": len(rows_), "minerals": sorted(([k, v] for k, v in mins.items()), key=lambda kv: kv[0].lower()),
                    "ref": refname, "ref_known": refpos is not None, "rings_total": allm, "hidden": nhid, "rings_scanned": sum(1 for v in rings.values() if v["scan"]),
                    "systems": sorted(posm.keys(), key=str.lower)[:6000], "classes": sorted({v["cls"] for v in rings.values() if v["cls"]}),
                    "reserves": sorted({v["res"] for v in rings.values() if v["res"]})}
        if op == "disc":
            mapd = {}
            for r in Q("SELECT k1, MIN(n1) pr, MAX(n2) tg FROM ce WHERE kind='mapd' GROUP BY k1"):
                mapd[r["k1"]] = (r["pr"], r["tg"])
            ringed = {}
            for r in Q("SELECT DISTINCT k1 FROM ce WHERE kind='ring'"):
                ringed[r["k1"]] = 1
            bod = {}
            for r in K("scan", "ORDER BY ts"):
                o = bod.setdefault((r["sys"], r["k1"]), {"ts": r["ts"], "cls": r["k2"], "fl": set(), "ls": r["n2"], "m": 0, "g": 0, "atm": ""})
                o["fl"].update(f for f in (r["k3"] or "").split(",") if f)
                o["m"] = max(o["m"], r["n3"] or 0)
                o["g"] = max(o["g"], r["n1"] or 0)
                o["atm"] = o["atm"] or (r["x"] or "")
            sold = {}
            for r in Q("SELECT k1, MAX(ts) t FROM ce WHERE kind='xsold' GROUP BY k1"):
                sold[r["k1"]] = r["t"]
            hasring = lambda nm: any(k.startswith(nm + " ") for k in ringed) if ringed else False
            vals = {}
            for k, o in bod.items():
                fl = o["fl"]
                mp = k[1] in mapd
                eff = mp and mapd[k[1]][0] and mapd[k[1]][1] and mapd[k[1]][0] <= mapd[k[1]][1]
                v = explval.body_value(o["cls"], o["m"], "terra" in fl, "erst" in fl, mp, mp and "unkart" in fl, bool(eff))
                vals[k] = v
                o["v"] = v
                o["sold"] = bool(sold.get(k[0]) and sold[k[0]] >= o["ts"])
                o["sp"] = explval.special(o["cls"], "terra" in fl, "landbar" in fl, o["g"], hasring(k[1]), o["atm"])
            def feat(k, o):
                t = []
                if "erst" in o["fl"]:
                    t.append("Erstentdeckung")
                if k[1] in mapd:
                    t.append("Erstkartierung" if "unkart" in o["fl"] else "Kartiert")
                t += o["sp"]
                return ", ".join(t)
            allr = sorted(((o["ts"], k[0], k[1], o["cls"], feat(k, o), o["ls"], o["v"], "erst" in o["fl"], o["sold"]) for k, o in bod.items()), reverse=True)
            first = [r[:7] for r in allr if r[7]]
            ty = {}
            for r in allr:
                t_ = ty.setdefault(r[3], [0, 0, 0])
                t_[0] += 1
                t_[1] += 1 if r[7] else 0
                t_[2] += r[6] if r[7] else 0
            tyr = [[k, v[0], v[1], v[2]] for k, v in sorted(ty.items(), key=lambda kv: (-kv[1][2], -kv[1][0]))]
            ekart = sum(1 for k, o in bod.items() if "unkart" in o["fl"] and k[1] in mapd)
            fsys = {}
            for k, o in bod.items():
                if "erst" in o["fl"]:
                    x_ = fsys.setdefault(k[0], [0, 0, "", 0])
                    x_[0] += 1
                    x_[1] += o["v"]
                    x_[2] = max(x_[2], o["ts"])
                    x_[3] += 0 if o["sold"] else o["v"]
            sysr = [[k, v[0], v[1], v[3], v[2]] for k, v in sorted(fsys.items(), key=lambda kv: -kv[1][1])]
            best = sorted(((o["v"], k[0], k[1], o["cls"]) for k, o in bod.items() if "erst" in o["fl"]), reverse=True)[:25]
            tot_first = sum(o["v"] for o in bod.values() if "erst" in o["fl"])
            unsold = sum(o["v"] for o in bod.values() if not o["sold"])
            unsold_first = sum(o["v"] for o in bod.values() if not o["sold"] and "erst" in o["fl"])
            # Pruefung gegen echte Verkaeufe: Schaetzung der in den Verkaeufen genannten Systeme gegen die echte Summe
            chk, est_sum, real_sum = [], 0, 0
            for sr in Q("SELECT ts, k1, n1, n2, n3 FROM ce WHERE kind='xsale' ORDER BY ts"):
                sysn = {x["k1"] for x in Q("SELECT k1 FROM ce WHERE kind='xsold' AND ts=?", sr["ts"])}
                prev = {n: (Q("SELECT MAX(ts) t FROM ce WHERE kind='xsold' AND k1=? AND ts<?", n, sr["ts"])[0]["t"] or "") for n in sysn}
                est = sum(o["v"] for k, o in bod.items() if k[0] in sysn and prev.get(k[0], "") < o["ts"] <= sr["ts"])
                if est > 0 and sr["n3"] > 0:
                    chk.append([sr["ts"], int(sr["k1"] or 0), est, sr["n3"], (sr["n3"] / est * 100)])
                    est_sum += est
                    real_sum += sr["n3"]
            kpi = [["Körper gescannt", len(allr), "n"], ["Erstentdeckungen", len(first), "n"], ["Erstkartierungen", ekart, "n"],
                   ["Systeme", len({r[1] for r in allr}), "n"], ["Landbare Körper", sum(1 for o in bod.values() if "landbar" in o["fl"]), "n"],
                   ["Terraformbar", sum(1 for o in bod.values() if "terra" in o["fl"]), "n"],
                   ["Wert Erstentdeckungen (Schätzung)", tot_first, "cr"], ["Noch nicht verkauft (Schätzung)", unsold, "cr"],
                   ["Davon Erstentdeckungen", unsold_first, "cr"]]
            cols = [["Zeit", "d"], ["System", "t"], ["Körper", "t"], ["Typ", "t"], ["Merkmale", "t"], ["Entfernung (ls)", "n"], ["Wert ca. Cr", "cr"]]
            blocks = [
                helpers._block("Erstentdeckungen", cols, first[:500], "Körper, bei denen das Spiel beim Scan 'noch nicht entdeckt' meldete. Wert = grobe Schätzung (siehe Hinweis)."),
                helpers._block("Systeme mit Erstentdeckungen", [["System", "t"], ["Erste Körper", "n"], ["Wert ca. Cr", "cr"], ["Davon unverkauft ca. Cr", "cr"], ["Zuletzt", "d"]], sysr[:300]),
                helpers._block("Wertvollste Erstentdeckungen", [["Wert ca. Cr", "cr"], ["System", "t"], ["Körper", "t"], ["Typ", "t"]], [list(x) for x in best]),
                helpers._block("Alle gescannten Körper", cols, [r[:7] for r in allr[:500]], "Die jüngsten 500."),
                helpers._block("Nach Typ", [["Typ", "t"], ["Gescannt", "n"], ["Davon Erstentdeckung", "n"], ["Wert der Erstentdeckungen ca. Cr", "cr"]], tyr)]
            if chk:
                blocks.append(helpers._block("Prüfung der Schätzung gegen deine echten Verkäufe", [["Verkauf", "d"], ["Systeme", "n"], ["Schätzung Cr", "cr"], ["Echt Cr", "cr"], ["Echt / Schätzung %", "r"]], chk[-30:],
                              f"Summe: Schätzung {timefmt._nf(est_sum)} Cr, echt {timefmt._nf(real_sum)} Cr ({real_sum / est_sum * 100:.0f} % der Schätzung)."))
            return {"kpi": kpi, "blocks": blocks,
                    "note": "Das Journal schreibt keinen Wert je Körper. Die Wertspalte ist eine Näherung nach der bekannten Community-Formel (Klasse, Masse, Erstentdeckung, Kartierung); echte Auszahlungen weichen ab. Unverkauft = die Systeme tauchen nach dem Scan in keinem verkauften Erkundungsdatensatz auf. Echte Verkäufe stehen unter Karriere → Erkundung."}
        if op == "land":
            grav = {r["k1"]: r["n1"] for r in Q("SELECT k1, n1 FROM ce WHERE kind='scan' AND n1>0")}
            tc = K("touch", "ORDER BY ts DESC")
            lrows = []
            for r in tc:
                gv = grav.get(r["k1"])
                lrows.append([r["ts"], r["sys"], r["k1"] or "unbekannt", ("%.3f / %.3f" % (r["n1"], r["n2"])).replace(".", ",") if (r["n1"] or r["n2"]) else "-",
                              r["k2"] or "-", (("%.2f g" % gv).replace(".", ",")) if gv else "-"])
            bs, bo = {}, {}
            for r in K("bsell"):
                o = bs.setdefault((r["k1"], r["k2"]), [0, 0, 0])
                o[0] += r["n3"]; o[1] += r["n1"]; o[2] += r["n2"]
            for r in K("bio"):
                o = bo.setdefault((r["k1"], r["k2"]), [0, set(), ""])
                o[0] += 1
                if r["k3"]:
                    o[1].add(r["k3"])
                o[2] = r["ts"]
            bsr = [[k[0], k[1], v[0], v[1], v[2], v[1] + v[2]] for k, v in sorted(bs.items(), key=lambda kv: -(kv[1][1] + kv[1][2]))]
            bor = [[k[0], k[1], v[0], len(v[1]), v[2]] for k, v in sorted(bo.items(), key=lambda kv: -kv[1][0])]
            bodies = {r["k1"] for r in tc if r["k1"]}
            gm = [grav.get(b) or 0 for b in bodies]
            kpi = [["Landungen", len(tc), "n"], ["Körper mit Landung", len(bodies), "n"], ["Höchste Schwerkraft (g)", max(gm) if gm else 0, "r"],
                   ["Bio-Proben analysiert", sum(v[0] for v in bo.values()), "n"], ["Bio-Arten", len(bo), "n"],
                   ["Bio verkauft", sum(v[1] + v[2] for v in bs.values()), "cr"]]
            return {"kpi": kpi, "blocks": [
                helpers._block("Landungen auf Planeten", [["Zeit", "d"], ["System", "t"], ["Körper", "t"], ["Breite / Länge", "t"], ["Nächstes Ziel", "t"], ["Schwerkraft", "t"]],
                       lrows[:500], "Schwerkraft nur, wenn du den Körper gescannt hast. Körpername aus dem Anflug; fehlt er, steht 'unbekannt'."),
                helpers._block("Biologie analysiert (je Variante)", [["Gattung", "t"], ["Variante", "t"], ["Analysen", "n"], ["Körper", "n"], ["Zuletzt", "d"]], bor),
                helpers._block("Biologie verkauft", [["Gattung", "t"], ["Variante", "t"], ["Anzahl", "n"], ["Wert", "cr"], ["Bonus", "cr"], ["Summe", "cr"]], bsr,
                       "Beträge laut Verkaufsmeldung des Journals.")]}
        if op == "rec":
            pos = {r["system"]: (r["x"], r["y"], r["z"]) for r in Q("SELECT system, x, y, z FROM syspos")}
            jm = Q("SELECT ts, sys, ship, n1 FROM ce WHERE kind='jump' ORDER BY ts")
            f0 = Q("SELECT k1 FROM ce WHERE kind='pos' ORDER BY ts LIMIT 1")
            first_sys = f0[0]["k1"] if f0 else None
            dn = lambda v, d=1: _tf.deN(("{:,.%df}" % d).format(v))
            d3_ = lambda a, b: sum((u - v) ** 2 for u, v in zip(a, b)) ** 0.5
            if not jm:
                return {"kpi": [], "blocks": [], "note": "Noch keine Sprünge gespeichert."}
            lj = max(jm, key=lambda r: r["n1"])
            days = {}
            for r in jm:
                d_ = days.setdefault(ldate(r["ts"]), [0.0, 0])
                d_[0] += r["n1"]; d_[1] += 1
            bd = max(days.items(), key=lambda kv: kv[1][0])
            bn = max(days.items(), key=lambda kv: kv[1][1])
            far0 = farS = None
            if first_sys in pos:
                for r in jm:
                    if r["sys"] in pos:
                        dd = d3_(pos[first_sys], pos[r["sys"]])
                        if far0 is None or dd > far0[0]:
                            far0 = (dd, r["sys"], r["ts"])
            for r in jm:
                if r["sys"] in pos:
                    dd = d3_((0, 0, 0), pos[r["sys"]])
                    if farS is None or dd > farS[0]:
                        farS = (dd, r["sys"], r["ts"])
            tot = sum(r["n1"] for r in jm)
            rows_ = [["Weitester Sprung", dn(lj["n1"]) + " Ly", (lj["sys"] or "?") + " · " + (lj["ship"] or "?"), ldate(lj["ts"])],
                     ["Längste Strecke an einem Tag", dn(bd[1][0]) + " Ly", str(bd[1][1]) + " Sprünge", bd[0]],
                     ["Meiste Sprünge an einem Tag", str(bn[1][1]), dn(bn[1][0]) + " Ly", bn[0]]]
            if far0:
                rows_.append(["Weiteste Entfernung vom ersten bekannten System (" + first_sys + ")", dn(far0[0]) + " Ly", far0[1], ldate(far0[2])])
            if farS:
                rows_.append(["Weiteste Entfernung von Sol", dn(farS[0]) + " Ly", farS[1], ldate(farS[2])])
            ships = {}
            for r in jm:
                o = ships.setdefault(r["ship"] or "?", [0.0, 0, 0.0])
                o[0] = max(o[0], r["n1"]); o[1] += 1; o[2] += r["n1"]
            srows = [[k, v[0], v[1], v[2]] for k, v in sorted(ships.items(), key=lambda kv: -kv[1][2])]
            return {"kpi": [["Sprünge gesamt", len(jm), "n"], ["Strecke gesamt (Ly)", tot, "n"], ["Weitester Sprung (Ly)", lj["n1"], "r"],
                            ["Reisetage", len(days), "n"], ["Ø Sprung (Ly)", tot / len(jm), "r"]],
                    "blocks": [helpers._block("Rekorde", [["Rekord", "t"], ["Wert", "t"], ["Wo / womit", "t"], ["Datum", "t"]], rows_,
                                      "Über alle gespeicherten Journale, unabhängig vom Zeitraum-Feld. Entfernungen nur, wenn die Koordinaten bekannt sind."),
                               helpers._block("Nach Schiff", [["Schiff", "t"], ["Weitester Sprung (Ly)", "r"], ["Sprünge", "n"], ["Strecke (Ly)", "n"]], srows)]}
        if op == "wares":
            tr = K("trade")
            d = {}
            for r in tr:
                o = d.setdefault(r["k1"] or "?", {"bt": 0, "bc": 0, "st": 0, "sr": 0, "sp": 0, "sn": 0, "stn": {}})
                if r["k3"] == "buy":
                    o["bt"] += r["n1"]; o["bc"] += r["n2"]
                elif r["k3"] == "sell":
                    o["st"] += r["n1"]; o["sr"] += r["n2"]; o["sp"] += r["n3"]; o["sn"] += 1
                    z = o["stn"].setdefault(r["k2"] or "?", [0, 0])
                    z[0] += r["n1"]; z[1] += r["n3"]
            rows_ = []
            for k, o in d.items():
                best = worst = None
                for stn, (t_, p_) in o["stn"].items():
                    if t_ > 0:
                        v = p_ / t_
                        if best is None or v > best[1]:
                            best = (stn, v)
                        if worst is None or v < worst[1]:
                            worst = (stn, v)
                rows_.append([k, o["sn"], o["st"], o["bt"], o["sr"], o["sp"], o["sp"] / o["st"] if o["st"] else 0,
                              (best[0] + " (" + _tf.deN("{:,.0f}".format(best[1])) + " Cr/t)") if best else "-",
                              (worst[0] + " (" + _tf.deN("{:,.0f}".format(worst[1])) + " Cr/t)") if worst and worst != best else "-"])
            rows_.sort(key=lambda r: -r[5])
            sells = [r for r in tr if r["k3"] == "sell"]
            return {"kpi": [["Waren gehandelt", len(d), "n"], ["Verkäufe", len(sells), "n"], ["Verkauft (t)", sum(r["n1"] for r in sells), "n"],
                            ["Gewinn gesamt", sum(r["n3"] for r in sells), "cr"]],
                    "blocks": [helpers._block("Handels-Tagebuch je Ware", [["Ware", "t"], ["Verkäufe", "n"], ["Verkauft t", "n"], ["Gekauft t", "n"], ["Erlös", "cr"], ["Gewinn", "cr"],
                                      ["Ø Gewinn / t", "cr"], ["Beste Station", "t"], ["Schwächste Station", "t"]], rows_,
                                      "Gewinn = Erlös minus den im Spiel gemeldeten Durchschnitts-Einkaufspreis. Selbst abgebaute oder per Mission erhaltene Ware hat keinen Einkaufspreis und zählt mit vollem Erlös.")]}
        if op == "expl":
            cs = [r for r in K("cash") if r["k1"] in ("Exploration", "Exobiologie") and r["n1"] > 0]
            h = hours()
            ex = sum(r["n1"] for r in cs if r["k1"] == "Exploration")
            bio = sum(r["n1"] for r in cs if r["k1"] == "Exobiologie")
            days = {}
            for r in cs:
                d_ = days.setdefault(ldate(r["ts"]), [0, 0])
                d_[0 if r["k1"] == "Exploration" else 1] += r["n1"]
            drows = [[k, v[0], v[1], v[0] + v[1]] for k, v in sorted(days.items(), reverse=True)]
            top = [[r["ts"], r["k1"], r["sys"], r["n1"]] for r in sorted(cs, key=lambda r: -r["n1"])[:20]]
            inc = []
            for ent in bodydata._db_cached().values():
                st_ = ent.get("st", {})
                tot = st_.get("total")
                sc = sum(1 for b in (st_.get("bodies") or {}).values() if b.get("cls"))
                if tot and not st_.get("all") and sc < tot:
                    inc.append([ent.get("name", "?"), tot, sc, tot - sc, (ent.get("visits") or [""])[-1]])
            inc.sort(key=lambda r: (-r[3], r[0]))
            kpi = [["Exploration verkauft", ex, "cr"], ["Exobiologie verkauft", bio, "cr"], ["Verkäufe", len(cs), "n"],
                   ["Ø pro Verkauf", (ex + bio) / len(cs) if cs else 0, "cr"], ["Erkundung / aktive h", (ex + bio) / h if h else 0, "cr"],
                   ["Systeme mit offenen Körpern", len(inc), "n"]]
            return {"kpi": kpi, "blocks": [
                helpers._block("Erkundungseinnahmen pro Tag", [["Datum", "t"], ["Exploration", "cr"], ["Exobiologie", "cr"], ["Summe", "cr"]], drows),
                helpers._block("Größte Verkäufe", [["Zeit", "d"], ["Art", "t"], ["System", "t"], ["Betrag", "cr"]], top),
                helpers._block("Systeme mit unvollständigem Scan", [["System", "t"], ["Körper laut FSS-Erstscan", "n"], ["Gescannt", "n"], ["Offen", "n"], ["Zuletzt besucht", "d"]], inc[:300],
                       "Vergleich der Körperzahl aus dem FSS-Erstscan (Honk) mit den Körpern, zu denen du Scandaten gespeichert hast. Abweichungen um 1 können durch Gürtel/Ringe entstehen. Systeme, bei denen das Journal 'alle Körper gefunden' meldet, fehlen hier.")],
                "note": "Beträge zählen erst, wenn du die Daten verkaufst."}

        # ---------------------------------------------------------------- Powerplay / Karriere
        if op == "pp":
            _, pp = helpers._jload(c, "Powerplay")
            ms = K("merit")
            tot = sum(r["n1"] for r in ms)
            h = hours_of(sorted({r["file"] for r in ms}))
            kpi = [["Power", (pp or {}).get("Power", "-"), "t"], ["Rang", (pp or {}).get("Rank", "-"), "t"],
                   ["Merits (aktuell)", (pp or {}).get("Merits", 0), "n"], ["Merits im Zeitraum", tot, "n"],
                   ["Merits / h", tot / h if h else 0, "r"], ["Aktive Zeit (PP-Sessions)", h, "h"]]
            days, sy, ev = {}, {}, {}
            act = day_active()
            for r in ms:
                d = days.setdefault(ldate(r["ts"]), [0, 0])
                d[0] += r["n1"]
                d[1] += 1
                s = sy.setdefault(r["sys"] or "?", [0, 0])
                s[0] += r["n1"]
                s[1] += 1
            for r in K("ppx"):
                o = ev.setdefault((r["k1"], r["k2"]), [0, 0])
                o[0] += 1
                o[1] += r["n1"]
            return {"kpi": kpi, "blocks": [
                helpers._block("Merits pro Tag", [["Datum", "t"], ["Merits", "n"], ["Meldungen", "n"], ["Aktiv", "h"], ["Merits / h", "r"]],
                       [[k, v[0], v[1], act.get(k, 0), v[0] / act[k] if act.get(k) else 0] for k, v in sorted(days.items(), reverse=True)]),
                helpers._block("Merits nach System", [["System", "t"], ["Merits", "n"], ["Meldungen", "n"], ["Ø", "r"]],
                       [[k, v[0], v[1], v[0] / v[1]] for k, v in sorted(sy.items(), key=lambda kv: -kv[1][0])]),
                helpers._block("Powerplay-Aktionen", [["Aktion", "t"], ["Typ", "t"], ["Anzahl", "n"], ["Summe", "n"]],
                       [[k[0], k[1], v[0], v[1]] for k, v in sorted(ev.items(), key=lambda kv: -kv[1][0])])]}
        if op == "rank":
            _, rk = helpers._jload(c, "Rank")
            _, pg = helpers._jload(c, "Progress")
            _, rp = helpers._jload(c, "Reputation")
            rows = []
            for cat in career_ingest.RANKS:
                if not rk or cat not in rk:
                    continue
                pr = Q(f"SELECT n1, n2 FROM ce WHERE kind='prog' AND k1=?{W} ORDER BY ts, id", cat, *A)
                d = (pr[-1]["n1"] * 100 + pr[-1]["n2"]) - (pr[0]["n1"] * 100 + pr[0]["n2"]) if len(pr) > 1 else 0
                # Prognose: Fortschritt der letzten 30 Tage (Punkte je Tag) bis zur naechsten Stufe
                since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                p30 = Q("SELECT ts, n1, n2 FROM ce WHERE kind='prog' AND k1=? AND ts>=? ORDER BY ts, id", cat, since)
                rate = eta = None
                maxr = 14 if cat in ("Empire", "Federation") else 8
                if len(p30) > 1:
                    dd = (timefmt.parse_ts(p30[-1]["ts"]) - timefmt.parse_ts(p30[0]["ts"])).total_seconds() / 86400
                    dp = (p30[-1]["n1"] * 100 + p30[-1]["n2"]) - (p30[0]["n1"] * 100 + p30[0]["n2"])
                    if dd >= 0.5 and dp > 0:
                        rate = dp / dd
                        if rk[cat] < maxr:
                            eta = (100 - (pg or {}).get(cat, 0)) / rate
                rows.append([career_ingest.RANK_DE[cat], career_ingest.rank_name(cat, rk[cat]), rk[cat], (pg or {}).get(cat, 0), d / 100.0 if d else 0, rate, eta])
            bl = [helpers._block("Ränge", [["Laufbahn", "t"], ["Rang", "t"], ["Stufe", "n"], ["Fortschritt", "p"], ["Stufen-Zuwachs", "r"],
                          ["% / Tag (30 Tage)", "r"], ["Tage bis nächste Stufe", "r"]], rows,
                         "Zuwachs = Rangstufen inkl. Fortschritt zwischen erstem und letztem Messpunkt im Zeitraum. Prognose: Tempo der letzten 30 Tage, leer bei Stillstand oder Maximalrang; Tempo kann schwanken.")]
            if rp:
                bl.append(helpers._block("Ruf bei Großmächten", [["Macht", "t"], ["Ruf", "p"]],
                                 [[n, rp.get(k, 0)] for n, k in (("Imperium", "Empire"), ("Föderation", "Federation"),
                                                                  ("Allianz", "Alliance"), ("Unabhängige", "Independent"))]))
            bl.append(helpers._block("Beförderungen", [["Zeit", "d"], ["Laufbahn", "t"], ["Neuer Rang", "t"]],
                             [[r["ts"], career_ingest.RANK_DE.get(r["k1"], r["k1"]), r["k2"]] for r in K("promo", "ORDER BY ts DESC")]))
            return {"blocks": bl}
        if op == "stat":
            ts, st = helpers._jload(c, "Statistics")
            if not st:
                return {"blocks": [], "note": "Noch kein Statistics-Ereignis gefunden."}
            bl = []
            money = re.compile(r"(Profit|Cost|Reward|Wealth|Credits|Bounty|Fines|Spent|Earned|Value|Income|Total_Wealth|Payout|Bonds)", re.I)
            for sec, d in st.items():
                if not isinstance(d, dict):
                    continue
                rows = []
                for k, v in d.items():
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        continue
                    t = "s" if re.search(r"(^|_)(Time|Played|Duration)", k) and v > 1000 else \
                        ("cr" if money.search(k) and v > 100 else "r" if isinstance(v, float) else "n")
                    rows.append([k.replace("_", " "), v, t])
                if rows:
                    bl.append({"title": sec.replace("_", " "), "kv": rows})
            return {"blocks": bl, "note": f"Stand: {ts}"}
        if op == "eng":
            ts, en = helpers._jload(c, "Engineers")
            cr = {}
            for r in K("craft"):
                o = cr.setdefault(r["k1"], [0, 0])
                o[0] += 1
                o[1] = max(o[1], r["n1"])
            rows = []
            for e in (en or {}).get("Engineers", []):
                nm = e.get("Engineer", "?")
                rows.append([nm, e.get("Progress", "-"), e.get("Rank", 0), e.get("RankProgress", 0), cr.get(nm, [0, 0])[0]])
            rows.sort(key=lambda r: (-r[2], r[0]))
            bp = {}
            for r in K("craft"):
                o = bp.setdefault((r["k1"], r["k2"]), [0, 0])
                o[0] += 1
                o[1] = max(o[1], r["n1"])
            return {"blocks": [helpers._block("Ingenieure", [["Ingenieur", "t"], ["Status", "t"], ["Rang", "n"], ["Rang-Fortschritt", "p"],
                    ["Crafts im Zeitraum", "n"]], rows, f"Stand: {ts}" if ts else ""),
                    helpers._block("Gecraftete Blueprints", [["Ingenieur", "t"], ["Blueprint", "t"], ["Anzahl", "n"], ["Max. Stufe", "n"]],
                           [[k[0], career_ingest.pretty_item(k[1]), v[0], v[1]] for k, v in sorted(bp.items(), key=lambda kv: -kv[1][0])])]}
        if op == "mat":
            ts, cur = _mat_stock(c)
            names = {"Raw": "Rohstoffe", "Manufactured": "Hergestellt", "Encoded": "Kodiert"}
            bl = []
            for cat in ("Raw", "Manufactured", "Encoded"):
                rows = [[o[1], o[2]] for k, o in sorted(cur.items(), key=lambda kv: (-kv[1][2], kv[1][1])) if o[0] == cat and o[2] > 0]
                bl.append(helpers._block(f"{names[cat]} ({sum(r[1] for r in rows)})", [["Material", "t"], ["Menge", "n"]], rows))
            return {"blocks": bl, "note": "Stand = letztes Materials-Ereignis (Spielstart) plus danach gesammelt, getauscht und minus Crafting, Synthese und Technologiehändler. Abweichungen sind möglich, z. B. bei Missionsbelohnungen."}
        if op == "need":
            ts, stock = _mat_stock(c)
            evs = {}
            for r in Q("SELECT ts, k1, k2, k3, y, n1, n2, file, pos FROM ce WHERE kind='ing' ORDER BY ts, id"):
                o = evs.setdefault((r["file"], r["pos"]), {"eng": r["k1"], "bp": r["k3"], "lv": int(r["n2"]), "ts": r["ts"], "ing": {}})
                o["ing"][r["k2"]] = (int(r["n1"]), r["y"])
            rec = {}  # je Blueprint, Stufe und Zutatenliste ein Rezept (die Zutaten sind je Craft die gleichen)
            for o in evs.values():
                key = (o["eng"], o["bp"], o["lv"], tuple(sorted((n, v[0]) for n, v in o["ing"].items())))
                r_ = rec.setdefault(key, {"n": 0, "ing": o["ing"], "ts": o["ts"]})
                r_["n"] += 1
                r_["ts"] = max(r_["ts"], o["ts"])
            rows, short = [], {}
            for (eng, bp, lv, _k), o in rec.items():
                miss, parts, can = [], [], None
                for n, (need, loc) in sorted(o["ing"].items()):
                    have = int(stock.get(n, ["", "", 0])[2])
                    nm = (stock.get(n) or ["", "", 0])[1] or loc or n.title()
                    parts.append(f"{nm} {have}/{need}")
                    k = have // need if need else 99
                    can = k if can is None else min(can, k)
                    if have < need:
                        miss.append(f"{nm} −{need - have}")
                        sh = short.setdefault(n, [nm, have, 0, set()])
                        sh[2] = max(sh[2], need - have)
                        sh[3].add(career_ingest.pretty_item(bp) + f" G{lv}")
                rows.append([eng, career_ingest.pretty_item(bp) + f" G{lv}", ", ".join(miss) or "nichts", " · ".join(parts), can or 0, o["n"], len(miss)])
            rows.sort(key=lambda r: (r[6] == 0, r[6], r[1]))
            rows = [r[:6] for r in rows]
            srows = [[v[0], v[1], v[2], len(v[3]), ", ".join(sorted(v[3]))[:140]] for v in sorted(short.values(), key=lambda v: (-len(v[3]), -v[2]))]
            return {"blocks": [
                helpers._block("Baupläne, die du schon gecraftet hast (mit den Zutaten vom letzten Craft)", [["Ingenieur", "t"], ["Blueprint", "t"], ["Fehlt", "t"], ["Zutaten (Bestand/Bedarf)", "t"], ["Jetzt machbar", "n"], ["Bisher gecraftet", "n"]], rows,
                       "Reihenfolge: zuerst Baupläne, denen am wenigsten fehlt."),
                helpers._block("Fehlende Materialien, über alle Baupläne", [["Material", "t"], ["Bestand", "n"], ["Fehlt (mind.)", "n"], ["Baupläne", "n"], ["Betroffen", "t"]], srows)],
                "note": "Baupläne kenne ich nur aus deinen eigenen Crafts im Journal (nichts angenommen). Was du noch nie gecraftet hast, taucht hier nicht auf. Bestand wie unter Materialien. Es zählt die Zutatenliste, die das Journal beim Craft nannte; Bestand und Bedarf sind Stückzahlen."}

        # ---------------------------------------------------------------- Bilanz
        if op == "b_in":
            cs = K("cash")
            h = hours()
            cat = {}
            for r in cs:
                o = cat.setdefault(r["k1"], [0, 0, 0])
                o[0 if r["n1"] > 0 else 1] += r["n1"]
                o[2] += 1
            inc = sum(v[0] for v in cat.values())
            out = sum(v[1] for v in cat.values())
            kpi = [["Einnahmen", inc, "cr"], ["Ausgaben", out, "cr"], ["Netto", inc + out, "cr"], ["Aktive Zeit", h, "h"],
                   ["Einnahmen / h", inc / h if h else 0, "cr"], ["Netto / h", (inc + out) / h if h else 0, "cr"]]
            rows = [[k, v[0], v[1], v[0] + v[1], v[0] / inc if inc else 0, v[0] / h if h else 0, v[2]]
                    for k, v in sorted(cat.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))]
            days, act = {}, day_active()
            for r in cs:
                d = days.setdefault(ldate(r["ts"]), [0, 0])
                d[0 if r["n1"] > 0 else 1] += r["n1"]
            drows = [[k, v[0], v[1], v[0] + v[1], act.get(k, 0), v[0] / act[k] if act.get(k) else 0] for k, v in sorted(days.items(), reverse=True)]
            sh = {}
            for r in cs:
                if r["n1"] > 0:
                    sh[r["ship"] or "?"] = sh.get(r["ship"] or "?", 0) + r["n1"]
            # Zehn-Minuten-Raster der aktiven Zeit der Taetigkeit zuordnen, die darin am meisten eingebracht hat
            inc_b = {}
            for r in cs:
                if r["n1"] > 0:
                    d_ = inc_b.setdefault(r["ts"][:15], {})
                    d_[r["k1"]] = d_.get(r["k1"], 0) + r["n1"]
            tat = {}
            for b in helpers._active(c, cut):
                d_ = inc_b.get(b)
                cat_ = max(d_, key=d_.get) if d_ else "Ohne Einnahmen (Fliegen, Erkunden, Warten)"
                o = tat.setdefault(cat_, [0, 0])
                o[0] += 1 / 6.0
                o[1] += sum(d_.values()) if d_ else 0
            tat_rows = [[k, v[0], v[0] / h if h else 0, v[1], v[1] / v[0] if v[0] else 0]
                        for k, v in sorted(tat.items(), key=lambda kv: -(kv[1][1] / kv[1][0] if kv[1][0] else 0))]
            return {"kpi": kpi, "blocks": [
                helpers._block("Verdienst pro Stunde nach Tätigkeit", [["Tätigkeit", "t"], ["Aktive Zeit", "h"], ["Zeitanteil", "f"], ["Einnahmen", "cr"], ["Cr / h", "cr"]],
                       tat_rows, "Jedes Zehn-Minuten-Raster zählt zu der Einnahmequelle, die darin am meisten gebracht hat. Raster ohne Einnahmen stehen unter 'Ohne Einnahmen'."),
                helpers._block("Einnahmequellen", [["Quelle", "t"], ["Einnahmen", "cr"], ["Ausgaben", "cr"], ["Netto", "cr"], ["Anteil", "f"],
                       ["Cr / aktive h", "cr"], ["Buchungen", "n"]], rows),
                helpers._block("Pro Tag", [["Datum", "t"], ["Einnahmen", "cr"], ["Ausgaben", "cr"], ["Netto", "cr"], ["Aktiv", "h"], ["Einnahmen / h", "cr"]], drows),
                helpers._block("Einnahmen nach Schiff", [["Schiff", "t"], ["Einnahmen", "cr"]], sorted([[k, v] for k, v in sh.items()], key=lambda r: -r[1]))]}
        if op == "b_trade":
            tr = K("trade")
            sells = [r for r in tr if r["k3"] == "sell"]
            buys = [r for r in tr if r["k3"] == "buy"]
            prof = sum(r["n3"] for r in sells)
            rev = sum(r["n2"] for r in sells)
            t = sum(r["n1"] for r in sells)
            kpi = [["Verkauft", t, "n"], ["Erlös", rev, "cr"], ["Realer Gewinn", prof, "cr"], ["Gewinn / t", prof / t if t else 0, "cr"],
                   ["Marge", prof / rev if rev else 0, "f"], ["Eingekauft (t)", sum(r["n1"] for r in buys), "n"],
                   ["Einkaufskosten", sum(r["n2"] for r in buys), "cr"],
                   ["Schwarzmarkt/Hehlerei", sum(r["n3"] for r in sells if r["x"]), "cr"]]

            def grp(keyf):
                d = {}
                for r in sells:
                    o = d.setdefault(keyf(r) or "?", [0, 0, 0, 0])
                    o[0] += r["n1"]
                    o[1] += r["n2"]
                    o[2] += r["n3"]
                    o[3] += 1
                return [[k, v[0], v[1], v[2], v[2] / v[0] if v[0] else 0, v[3]] for k, v in sorted(d.items(), key=lambda kv: -kv[1][2])]
            cols = lambda t: [[t, "t"], ["Menge t", "n"], ["Erlös", "cr"], ["Gewinn", "cr"], ["Gewinn / t", "cr"], ["Verkäufe", "n"]]
            # Vergleich mit dem damals bekannten Markt: bester Verkaufspreis dieser Ware in den 3 Tagen vor dem Verkauf
            cmp_rows, lost = [], 0
            for r in sorted([r for r in sells if r["n1"] > 0], key=lambda r: r["ts"], reverse=True)[:60]:
                lo_ts = (timefmt.parse_ts(r["ts"]) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
                bm = c.execute("""SELECT MAX(i.sell) AS m FROM item i JOIN snap s ON s.id=i.snap_id
                                  WHERE i.name=? COLLATE NOCASE AND i.sell>0 AND i.demand>0 AND s.ts BETWEEN ? AND ?""",
                               (r["k1"], lo_ts, r["ts"])).fetchone()["m"]
                mine = r["n2"] / r["n1"]
                if bm:
                    lost += max(0, bm - mine) * r["n1"]
                cmp_rows.append([r["ts"], r["k1"], r["k2"], r["n1"], mine, bm, (bm - mine) if bm else None,
                                 max(0, bm - mine) * r["n1"] if bm else None])
            kpi.append(["Verschenkt (letzte 60 Verkäufe)", lost, "cr"])
            return {"kpi": kpi, "blocks": [helpers._block("Gewinn nach Ware", cols("Ware"), grp(lambda r: r["k1"])),
                    helpers._block("Gewinn nach Station", cols("Station"), grp(lambda r: r["k2"])),
                    helpers._block("Gewinn nach System", cols("System"), grp(lambda r: r["sys"])),
                    helpers._block("Ist vs. Markt (letzte 60 Verkäufe)", [["Zeit", "d"], ["Ware", "t"], ["Station", "t"], ["Menge", "n"], ["Mein Preis / t", "cr"],
                           ["Bester bekannter Preis (3 Tage davor)", "cr"], ["Differenz / t", "cr"], ["Verschenkt", "cr"]], cmp_rows,
                           "Vergleich mit deinen gespeicherten Marktständen: leer, wenn dafür keine Preise dieser Ware gespeichert waren. Verschenkt = Differenz × Menge, nur wenn ein höherer Preis bekannt war."),
                    helpers._block("Letzte Verkäufe", [["Zeit", "d"], ["Ware", "t"], ["Station", "t"], ["Menge", "n"], ["Erlös", "cr"], ["Gewinn", "cr"]],
                           [[r["ts"], r["k1"], r["k2"], r["n1"], r["n2"], r["n3"]] for r in sorted(sells, key=lambda r: r["ts"], reverse=True)[:60]])],
                    "note": "Realer Gewinn = Erlös − (Ø Einkaufspreis laut Journal × Menge). Missions-/Fundfracht ohne Einkaufspreis zählt voll als Gewinn."}
        if op == "b_mis":
            ms = K("mis")
            ty, fa = {}, {}
            for r in ms:
                o = ty.setdefault(r["x"] or "?", {"accepted": 0, "completed": 0, "failed": 0, "abandoned": 0, "rew": 0})
                o[r["k3"]] += 1
                if r["k3"] == "completed":
                    o["rew"] += r["n1"]
                    f = fa.setdefault(r["k2"] or "?", [0, 0])
                    f[0] += 1
                    f[1] += r["n1"]
            rows = []
            for k, o in sorted(ty.items(), key=lambda kv: -kv[1]["rew"]):
                fin = o["completed"] + o["failed"] + o["abandoned"]
                rows.append([k, o["accepted"], o["completed"], o["failed"], o["abandoned"], o["completed"] / fin if fin else 0,
                             o["rew"], o["rew"] / o["completed"] if o["completed"] else 0])
            kpi = [["Angenommen", sum(o["accepted"] for o in ty.values()), "n"], ["Abgeschlossen", sum(o["completed"] for o in ty.values()), "n"],
                   ["Gescheitert/aufgegeben", sum(o["failed"] + o["abandoned"] for o in ty.values()), "n"],
                   ["Belohnungen", sum(o["rew"] for o in ty.values()), "cr"]]
            last = [[r["ts"], r["x"], r["k1"], r["k2"], r["n1"]] for r in sorted([r for r in ms if r["k3"] == "completed"], key=lambda r: r["ts"], reverse=True)[:50]]
            return {"kpi": kpi, "blocks": [
                helpers._block("Missionsarten", [["Art", "t"], ["Angenommen", "n"], ["Fertig", "n"], ["Gescheitert", "n"], ["Aufgegeben", "n"],
                       ["Erfolgsquote", "f"], ["Belohnung", "cr"], ["Ø", "cr"]], rows),
                helpers._block("Auftraggeber", [["Fraktion", "t"], ["Fertig", "n"], ["Belohnung", "cr"]],
                       [[k, v[0], v[1]] for k, v in sorted(fa.items(), key=lambda kv: -kv[1][1])]),
                helpers._block("Zuletzt abgeschlossen", [["Zeit", "d"], ["Art", "t"], ["Mission", "t"], ["Fraktion", "t"], ["Belohnung", "cr"]], last)]}
        if op == "b_wealth":
            by = {}
            for r in Q("SELECT ts, src, v FROM wealth ORDER BY ts"):
                d = helpers._lts(r["ts"]).strftime("%Y-%m-%d")
                if cut and r["ts"] < cut:
                    continue
                by.setdefault(d, {})[r["src"]] = r["v"]
            rows, prev = [], None
            for d in sorted(by):
                cr = by[d].get("credits")
                w = by[d].get("wealth")
                rows.append([d, cr, w, (cr - prev) if (cr is not None and prev is not None) else 0])
                if cr is not None:
                    prev = cr
            rows.reverse()
            return {"blocks": [helpers._block("Vermögensverlauf (letzter bekannter Stand pro Tag)", [["Datum", "t"], ["Credits", "cr"],
                    ["Gesamtvermögen", "cr"], ["Δ Credits", "cr"]], rows)],
                    "note": "Credits aus LoadGame, Gesamtvermögen aus Statistics – beides nur bei Spielstart/Statistik-Ereignis."}
        if op == "b_time":
            act = helpers._active(c, cut)
            hrs, wds = {}, {}
            for b in act:
                t = helpers._bdt(b)
                hrs.setdefault(t.hour, [0, 0])[0] += 1
                wds.setdefault(t.weekday(), [0, 0])[0] += 1
            for r in K("cash"):
                if r["n1"] > 0:
                    t = helpers._lts(r["ts"])
                    hrs.setdefault(t.hour, [0, 0])[1] += r["n1"]
                    wds.setdefault(t.weekday(), [0, 0])[1] += r["n1"]
            wn = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
            row = lambda lab, v: [lab, v[0] / 6.0, v[1], v[1] / (v[0] / 6.0) if v[0] else 0]
            sess = []
            cash_f = {}
            for r in K("cash"):
                if r["n1"] > 0:
                    cash_f[r["file"]] = cash_f.get(r["file"], 0) + r["n1"]
            for r in Q("SELECT name, first, last FROM jc ORDER BY first DESC"):
                if not r["first"] or (cut and r["last"] < cut):
                    continue
                dur = (timefmt.parse_ts(r["last"]) - timefmt.parse_ts(r["first"])).total_seconds()
                sess.append([r["first"], dur, cash_f.get(r["name"], 0), cash_f.get(r["name"], 0) / (dur / 3600) if dur > 60 else 0])
            ds = [s[1] for s in sess]
            kpi = [["Aktive Zeit", len(act) / 6.0, "h"], ["Sessions", len(sess), "n"],
                   ["Längste Session", max(ds, default=0), "s"], ["Ø Session", sum(ds) / len(ds) if ds else 0, "s"]]
            return {"kpi": kpi, "blocks": [
                helpers._block("Nach Tageszeit (Ortszeit)", [["Stunde", "t"], ["Aktiv", "h"], ["Einnahmen", "cr"], ["Cr / h", "cr"]],
                       [row(f"{h:02d}:00", hrs[h]) for h in sorted(hrs)]),
                helpers._block("Nach Wochentag", [["Tag", "t"], ["Aktiv", "h"], ["Einnahmen", "cr"], ["Cr / h", "cr"]],
                       [row(wn[d], wds[d]) for d in sorted(wds)]),
                helpers._block("Sessions", [["Start", "d"], ["Dauer", "s"], ["Einnahmen", "cr"], ["Cr / h", "cr"]], sess[:80])],
                "note": "Aktive Zeit = Zehn-Minuten-Raster mit Journal-Aktivität."}

        # ---------------------------------------------------------------- Flotte
        if op == "ships":
            ts, ss = helpers._jload(c, "StoredShips")
            rows = []
            for s in (ss or {}).get("ShipsHere", []):
                rows.append([career_ingest.ship_name(s, "ShipType"), s.get("Name", ""), "hier (" + str((ss or {}).get("StationName", "")) + ")",
                             s.get("Value", 0), 0, 1 if s.get("Hot") else 0])
            for s in (ss or {}).get("ShipsRemote", []):
                rows.append([career_ingest.ship_name(s, "ShipType"), s.get("Name", ""), s.get("StarSystem", "?"),
                             s.get("Value", 0), s.get("TransferPrice", 0), 1 if s.get("Hot") else 0])
            perf = {}
            for r in Q(f"SELECT ship, kind, n1 FROM ce WHERE kind IN ('cash','kill'){W}", *A):
                o = perf.setdefault(r["ship"] or "?", [0, 0, 0])
                if r["kind"] == "kill":
                    o[0] += 1
                elif r["n1"] > 0:
                    o[1] += r["n1"]
                else:
                    o[2] += r["n1"]
            ev = [[r["ts"], r["k1"], r["k2"], r["n1"]] for r in K("ship", "ORDER BY ts DESC")]
            return {"blocks": [
                helpers._block("Gelagerte Schiffe", [["Typ", "t"], ["Name", "t"], ["Ort", "t"], ["Wert", "cr"], ["Transfer", "cr"], ["Heiß", "n"]], rows,
                       f"Stand: {ts}" if ts else "Noch kein StoredShips-Ereignis."),
                helpers._block("Leistung je Schiff (Zeitraum)", [["Schiff", "t"], ["Abschüsse", "n"], ["Einnahmen", "cr"], ["Ausgaben", "cr"]],
                       [[k] + v for k, v in sorted(perf.items(), key=lambda kv: -kv[1][1])]),
                helpers._block("Schiffswechsel & Käufe", [["Zeit", "d"], ["Ereignis", "t"], ["Schiff", "t"], ["Preis", "cr"]], ev)]}
        if op == "cmp":
            rows, best = [], {}
            for i, r in enumerate(Q("SELECT k, ts, js FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC")):
                lo = json.loads(r["js"])
                fcap = lo.get("FuelCapacity")
                tank = fcap.get("Main", 0) if isinstance(fcap, dict) else (fcap or 0)
                shield, weap, util = "", 0, 0
                for m in lo.get("Modules", []):
                    it, slot = str(m.get("Item", "")).lower(), str(m.get("Slot", ""))
                    if "shieldgenerator" in it:
                        shield = market_ingest.mod_info(it)[0] + " " + market_ingest.mod_info(it)[2]
                    if slot.endswith(tuple("0123456789")) and "Hardpoint" in slot:
                        if slot.startswith("Tiny"):
                            util += 1
                        else:
                            weap += 1
                code = str(lo.get("Ship", "")).lower()
                need = helpers._ship_need(code)
                val = (lo.get("HullValue", 0) or 0) + (lo.get("ModulesValue", 0) or 0)
                row = [("▶ " if i == 0 else "") + career_ingest.ship_name(lo), (lo.get("ShipName") or "") + " " + (lo.get("ShipIdent") or ""),
                       lo.get("MaxJumpRange", 0) or 0, lo.get("CargoCapacity", 0) or 0, tank, lo.get("UnladenMass", 0) or 0,
                       shield or "-", weap, util, val, lo.get("Rebuy", 0) or 0, helpers.PAD_NAME.get(need, "unbekannt")]
                rows.append(row)
                for key, idx in (("Weiteste Sprungweite", 2), ("Größte Fracht", 3), ("Meiste Waffenplätze", 7), ("Größter Tank", 4)):
                    if not best.get(key) or row[idx] > best[key][1]:
                        best[key] = (row[0].replace("▶ ", ""), row[idx])
            kpi = [[k, f"{v[0]} ({v[1]:.1f})" if isinstance(v[1], float) else f"{v[0]} ({v[1]})", "t"] for k, v in best.items()]
            side = _side_by_side(Q("SELECT k, ts, js FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC"))
            return {"kpi": kpi, "blocks": [side] + [helpers._block("Schiffe im Vergleich (letzter bekannter Loadout je Schiff)",
                    [["Schiff", "t"], ["Name", "t"], ["Sprungweite Ly", "r"], ["Fracht t", "n"], ["Tank t", "n"], ["Leermasse t", "r"], ["Schild", "t"],
                     ["Waffenplätze", "n"], ["Utility", "n"], ["Wert", "cr"], ["Rebuy", "cr"], ["Landeplatz", "t"]], rows,
                    "▶ = zuletzt gewechseltes Schiff. Landeplatz-Größe stammt aus meiner Schiffs-Tabelle (Spielwissen), nicht aus Dateien. Wert = Rumpf + Module laut Loadout.")],
                    "note": "" if rows else "Noch kein Loadout-Ereignis gefunden."}
        if op == "mods":
            bl, kpi = [], []
            for r in Q("SELECT k, js FROM snapkv WHERE k LIKE 'Loadout:%' ORDER BY ts DESC"):
                lo = json.loads(r["js"])
                nm = career_ingest.ship_name(lo)
                rows = []
                for m in lo.get("Modules", []):
                    en = m.get("Engineering") or {}
                    rows.append([m.get("Slot", ""), career_ingest.pretty_item(m.get("Item")), (m.get("Health", 1) or 0) * 100,
                                 "an" if m.get("On") else "aus",
                                 (career_ingest.pretty_item(en.get("BlueprintName")) + f" G{en.get('Level', '')}") if en else ""])
                title = f"{nm} „{lo.get('ShipName', '')}“ {lo.get('ShipIdent', '')}".strip()
                info = (f"Leermasse {lo.get('UnladenMass', 0):.0f} t · Sprungweite {lo.get('MaxJumpRange', 0):.1f} Ly · "
                        f"Fracht {lo.get('CargoCapacity', 0)} t · Tank {lo.get('FuelCapacity', {}).get('Main', 0) if isinstance(lo.get('FuelCapacity'), dict) else lo.get('FuelCapacity', 0)} t · "
                        f"Rebuy {timefmt._nf(lo.get('Rebuy', 0))} Cr")
                bl.append(helpers._block(title, [["Slot", "t"], ["Modul", "t"], ["Zustand", "p"], ["Status", "t"], ["Engineering", "t"]], rows, info))
            return {"blocks": bl, "note": "" if bl else "Noch kein Loadout-Ereignis gefunden."}
        return {"error": "unbekannte Abfrage"}
    finally:
        c.close()
