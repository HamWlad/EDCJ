"""Fleet-Carrier-Ansicht."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import helpers
from . import timefmt as _tf


def carrier_view(c, op):
    c.row_factory = sqlite3.Row
    de = lambda v, d=0: _tf.deN(("{:,.%df}" % d).format(v or 0))
    stats = []
    for r in c.execute("SELECT ts, k1, k2, k3, y, n1, n2, n3 FROM ce WHERE kind='cstat' ORDER BY ts"):
        try:
            j = json.loads(r["y"] or "{}")
        except ValueError:
            j = {}
        stats.append(dict(j, ts=r["ts"], call=r["k1"], name=r["k2"], access=r["k3"], fuel=r["n1"]))
    if not stats:
        locs = c.execute("SELECT ts, k1 FROM ce WHERE kind='cloc' ORDER BY ts DESC LIMIT 1").fetchone()
        if not locs:
            return {"kpi": [], "blocks": [], "note": "Noch keine Fleet-Carrier-Daten. Öffne im Spiel einmal die Carrier-Verwaltung, dann schreibt das Journal Tankinhalt, Finanzen und Auslastung."}
    pos = {r["system"]: (r["x"], r["y"], r["z"]) for r in c.execute("SELECT system, x, y, z FROM syspos")}
    own = stats[-1]["call"] if stats else None
    jumps = [dict(ts=r["ts"], sys=r["k1"], body=r["k2"], stn=r["k3"]) for r in c.execute("SELECT ts, k1, k2, k3 FROM ce WHERE kind='cjump' ORDER BY ts")
             if not own or r["k3"] == own]
    reqs = [dict(ts=r["ts"], sys=r["k1"], dep=r["k3"]) for r in c.execute("SELECT ts, k1, k3 FROM ce WHERE kind='cjreq' ORDER BY ts")]
    cans = [r["ts"] for r in c.execute("SELECT ts FROM ce WHERE kind='cjcan' ORDER BY ts")]
    deps = [dict(ts=r["ts"], amt=r["n1"], tot=r["n2"]) for r in c.execute("SELECT ts, n1, n2 FROM ce WHERE kind='cfuel' ORDER BY ts")]
    locs = [(r["ts"], r["k1"]) for r in c.execute("SELECT ts, k1 FROM ce WHERE kind='cloc' ORDER BY ts")]
    # Position: juengstes Ereignis aus Sprung / Standortmeldung
    cand = [(j["ts"], j["sys"]) for j in jumps] + locs
    here = max(cand)[1] if cand else None
    prev = None
    for j in jumps:
        if prev is None:
            before = [l for l in locs if l[0] < j["ts"]]
            prev = before[-1][1] if before else None
        j["from"] = prev if prev != j["sys"] else None
        if j["from"] is None:
            prev = j["sys"]
        a, b = pos.get(j["from"]), pos.get(j["sys"])
        j["dist"] = sum((u - v) ** 2 for u, v in zip(a, b)) ** 0.5 if a and b else None
        prev = j["sys"]
    # Messung des Tritiumverbrauchs je Sprung (nur wenn zwischen zwei Messungen genau ein Sprung lag)
    for j in jumps:
        rq = [q for q in reqs if q["sys"] == j["sys"] and q["ts"] <= j["ts"]]
        t0 = rq[-1]["ts"] if rq else j["ts"]
        sb = [s_ for s_ in stats if s_["ts"] <= t0]
        sa = [s_ for s_ in stats if s_["ts"] >= j["ts"]]
        j["fb"] = j["fa"] = j["use"] = None
        if sb and sa:
            b_, a_ = sb[-1], sa[0]
            others = [x for x in jumps if x is not j and b_["ts"] < x["ts"] <= a_["ts"]]
            dp = sum(d["amt"] for d in deps if b_["ts"] < d["ts"] <= a_["ts"])
            if not others:
                j["fb"], j["fa"], j["use"] = b_["fuel"], a_["fuel"], b_["fuel"] + dp - a_["fuel"]
    last = stats[-1] if stats else {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pend = [q for q in reqs if q["dep"] and q["dep"] > now and not any(cn > q["ts"] for cn in cans)]
    tot_d = sum(j["dist"] for j in jumps if j["dist"])
    mined = c.execute("SELECT COUNT(*) FROM ce WHERE kind='mine' AND lower(k1)='tritium'").fetchone()[0]
    dep_t = sum(d["amt"] for d in deps)
    meas = [j for j in jumps if j["use"] is not None and j["use"] > 0]
    if op == "c_over":
        kpi = [["Rufzeichen", last.get("call", "-"), "t"], ["Name", last.get("name", "-"), "t"], ["Standort (zuletzt bekannt)", here or "-", "t"],
               ["Tritium im Tank (t)", last.get("fuel", 0), "n"], ["Sprungreichweite (Ly)", last.get("jr", 0), "n"],
               ["Kontostand", last.get("bal", 0), "cr"], ["Freier Platz (t)", last.get("free", 0), "n"], ["Sprünge (aufgezeichnet)", len(jumps), "n"],
               ["Strecke gesamt (Ly)", tot_d, "n"], ["Nächster geplanter Sprung", (pend[-1]["sys"] + " um " + pend[-1]["dep"][11:16] + " UTC") if pend else "keiner", "t"]]
        kv = [["Andockrecht", last.get("access", "-")], ["Notorische erlaubt", "ja" if last.get("notor") else "nein"],
              ["Kapazität gesamt", de(last.get("cap")) + " t"], ["Davon Crew", de(last.get("crew")) + " t"], ["Davon Fracht", de(last.get("cargo")) + " t"],
              ["Schiffspakete", de(last.get("sp")) + " t"], ["Modulpakete", de(last.get("mp")) + " t"], ["Frei", de(last.get("free")) + " t"],
              ["Reserve", de(last.get("res")) + " Cr (" + str(last.get("rp", "-")) + " %)"], ["Verfügbar", de(last.get("av")) + " Cr"],
              ["Aktive Dienste", ", ".join(last.get("svc") or []) or "-"],
              ["Steuersätze", ", ".join(f"{k} {v} %" for k, v in (last.get("tax") or {}).items()) or "-"],
              ["Außer Dienst geplant", "ja" if last.get("dec") else "nein"], ["Letzte Messung", last.get("ts", "-")]]
        return {"kpi": kpi, "blocks": [{"title": "Stand laut letzter Carrier-Verwaltung", "kv": kv, "rows": [], "cols": [], "note": "Zahlen stammen aus dem letzten Öffnen der Carrier-Verwaltung im Spiel, nicht live."}],
                "note": f"Tritium-Mining im Journal: {mined} t raffiniert. Eingezahlt laut Journal: {de(dep_t)} t (nur Einzahlungen, die als Ereignis geschrieben wurden)."}
    if op == "c_jumps":
        rows_ = []
        for j in sorted(jumps, key=lambda j: j["ts"], reverse=True):
            rows_.append([j["ts"], j["from"] or "-", j["sys"], j["dist"], j["fb"], j["fa"], j["use"], (j["use"] / j["dist"]) if j["use"] and j["dist"] else None])
        fr = []
        for sx in stats:
            if not fr or fr[-1][1] != sx["fuel"]:
                fr.append([sx["ts"], sx["fuel"]])
        frows = [[a, b] for a, b in reversed(fr)]
        avg = (sum(j["use"] for j in meas) / len(meas)) if meas else 0
        pl = [sum(j["use"] / j["dist"] for j in meas if j["dist"]) / max(1, sum(1 for j in meas if j["dist"]))] if meas else [0]
        return {"kpi": [["Gemessene Sprünge", len(meas), "n"], ["Ø Tritium je Sprung (t)", avg, "r"], ["Ø Tritium je Ly (t)", pl[0], "r"], ["Tank jetzt (t)", last.get("fuel", 0), "n"],
                        ["Einzahlungen (t)", dep_t, "n"], ["Tritium abgebaut (t)", mined, "n"]],
                "blocks": [helpers._block("Sprünge", [["Zeit", "d"], ["Von", "t"], ["Nach", "t"], ["Distanz (Ly)", "r"], ["Tank vorher", "n"], ["Tank nachher", "n"], ["Verbrauch (t)", "n"], ["t pro Ly", "r"]], rows_,
                                  "Verbrauch gemessen aus zwei Tankständen um genau einen Sprung (Einzahlungen dazwischen eingerechnet). Fehlen Messungen, bleibt das Feld leer, es wird nichts geschätzt."),
                           helpers._block("Tankstand-Verlauf", [["Messung", "d"], ["Tritium (t)", "n"]], frows[:200])]}
    if op == "c_fin":
        fr, prev = [], None
        for sx in stats:
            k = (sx.get("bal"), sx.get("res"), sx.get("av"))
            if k != prev:
                fr.append([sx["ts"], sx.get("bal"), sx.get("res"), sx.get("av")])
                prev = k
        bank = [[r["ts"], r["n1"], r["n3"]] for r in c.execute("SELECT ts, n1, n3 FROM ce WHERE kind='cbank' ORDER BY ts DESC LIMIT 200")]
        tr = [[r["ts"], r["k1"], r["k2"], r["n1"], r["n2"], r["k3"]] for r in c.execute("SELECT ts, k1, k2, k3, n1, n2 FROM ce WHERE kind='ctrade' ORDER BY ts DESC LIMIT 200")]
        return {"kpi": [["Kontostand", last.get("bal", 0), "cr"], ["Reserve", last.get("res", 0), "cr"], ["Verfügbar", last.get("av", 0), "cr"],
                        ["Einzahlungen/Abhebungen", len(bank), "n"], ["Handelsaufträge", len(tr), "n"]],
                "blocks": [helpers._block("Finanzverlauf (bei Änderung)", [["Messung", "d"], ["Kontostand", "cr"], ["Reserve", "cr"], ["Verfügbar", "cr"]], list(reversed(fr))[:200]),
                           helpers._block("Überweisungen", [["Zeit", "d"], ["Betrag (+ Einzahlung / − Abhebung)", "cr"], ["Carrier-Konto danach", "cr"]], bank),
                           helpers._block("Handelsaufträge", [["Zeit", "d"], ["Ware", "t"], ["Art", "t"], ["Menge", "n"], ["Preis", "cr"], ["Hinweis", "t"]], tr)]}
    return {"error": "unbekannte Abfrage"}
