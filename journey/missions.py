"""Missionsübersicht (Spielmissionen)."""

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import config, helpers, status, timefmt


def _fmt_rest(sec):
    if sec is None:
        return "-"
    if sec <= 0:
        return "abgelaufen"
    d, h, m = int(sec // 86400), int(sec % 86400 // 3600), int(sec % 3600 // 60)
    return (f"{d} T {h} Std." if d else f"{h} Std. {m} Min." if h else f"{m} Min.")


def missions_view(c, op):
    c.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc)
    det, red, state = {}, {}, {}
    for r in c.execute("SELECT ts, k1, k2, k3, x, y, n1 FROM ce WHERE kind='mdet' ORDER BY ts"):
        try:
            j = json.loads(r["y"] or "{}")
        except ValueError:
            j = {}
        det[r["k1"]] = dict(j, ts=r["ts"], sys=r["k2"], stn=r["k3"], exp=r["x"], rw=r["n1"])
    for r in c.execute("SELECT ts, k1, k2, k3 FROM ce WHERE kind='mred' ORDER BY ts"):
        red[r["k1"]] = (r["k2"], r["k3"])
    last_act = None
    for r in c.execute("SELECT ts, k1, y FROM ce WHERE kind='mact' ORDER BY ts"):
        last_act = (r["ts"], set(x for x in (r["k1"] or "").split(",") if x), r["y"])
    hist = []
    for r in c.execute("SELECT ts, k1, k2, k3, x, y, n1 FROM ce WHERE kind='mis' ORDER BY ts"):
        mid = str(int(r["y"])) if str(r["y"]).replace(".0", "").isdigit() else str(r["y"])
        if r["k3"] in ("completed", "failed", "abandoned"):
            state[mid] = (r["k3"], r["ts"], r["n1"])
            hist.append([r["ts"], r["k1"], r["x"], r["k2"], {"completed": "abgeschlossen", "failed": "gescheitert", "abandoned": "aufgegeben"}[r["k3"]], r["n1"] if r["k3"] == "completed" else 0])
    act = {}
    for mid, d_ in det.items():
        if mid in state:
            continue
        if last_act and last_act[0] > d_["ts"] and mid not in last_act[1]:
            continue  # beim Laden des Spiels nicht mehr aktiv (abgelaufen/entfernt)
        act[mid] = d_
    unknown = {}
    if last_act:
        try:
            exp_left = json.loads(last_act[2] or "{}")
        except ValueError:
            exp_left = {}
        for mid in last_act[1]:
            if mid not in det and mid not in state:
                unknown[mid] = exp_left.get(mid)
    pos, here, hs = helpers._posmap(c)
    route = set()
    d_ = config._journal_dir()
    if d_:
        nv = status._read_json_file(os.path.join(d_, "NavRoute.json")) or {}
        route = {x.get("StarSystem") for x in nv.get("Route", []) or [] if x.get("StarSystem")}
        for x in nv.get("Route", []) or []:  # Routensysteme bringen ihre Koordinaten mit
            if x.get("StarSystem") and isinstance(x.get("StarPos"), list) and len(x["StarPos"]) == 3:
                pos.setdefault(x["StarSystem"], tuple(x["StarPos"]))
    rows_ = []
    for mid, d in act.items():
        dsys, dstn = red.get(mid, (d["sys"], d["stn"]))
        try:
            rest = (timefmt.parse_ts(d["exp"]) - now).total_seconds() if d.get("exp") else None
        except ValueError:
            rest = None
        dist = helpers._d3(here, pos.get(dsys)) if dsys else None
        if dsys and dsys == hs:
            dist = 0.0
        det_t = []
        if d.get("kc"): det_t.append(f"{d['kc']} Abschüsse" + (f" ({d['tt']})" if d.get("tt") else "") + (f" gegen {d['tf']}" if d.get("tf") else ""))
        if d.get("cm"): det_t.append(f"{d['ct'] or ''} × {d['cm']}")
        if d.get("pc"): det_t.append(f"{d['pc']} Passagiere" + (f" ({d['pt']})" if d.get("pt") else ""))
        if d.get("tg"): det_t.append(f"Ziel: {d['tg']}")
        rows_.append({"id": mid, "exp": d.get("exp") or "", "rest": rest, "ty": d.get("ty", ""), "nm": d.get("nm", ""), "fa": d.get("fa", ""), "sys": dsys or "", "stn": dstn or "",
                      "dist": dist, "route": ("hier" if dsys and dsys == hs else "ja" if dsys in route else "-"), "rw": d.get("rw", 0), "det": "; ".join(det_t) or "-",
                      "redirected": mid in red})
    rows_.sort(key=lambda r: (r["rest"] is None, r["rest"] if r["rest"] is not None else 0))
    stale = [r for r in rows_ if r["rest"] is not None and r["rest"] <= 0]
    live = [r for r in rows_ if r not in stale]
    soon = [r for r in live if r["rest"] is not None and r["rest"] < 86400]
    onr = [r for r in live if r["route"] in ("ja", "hier")]
    done = sum(1 for v in state.values() if v[0] == "completed")
    fail = sum(1 for v in state.values() if v[0] in ("failed", "abandoned"))
    kpi = [["Offene Missionen", len(live), "n"], ["Belohnung offen", sum(r["rw"] for r in live), "cr"], ["Läuft in 24 Std. ab", len(soon), "n"],
           ["Auf Route / hier", len(onr), "n"], ["Abgelaufen, nicht gemeldet", len(stale), "n"], ["Erfolgsquote gesamt", done / (done + fail) if done + fail else 0, "f"]]
    if op == "ms_open":
        trs = lambda r: [r["exp"], _fmt_rest(r["rest"]), r["ty"], r["nm"], r["fa"], (r["sys"] + (" · " + r["stn"] if r["stn"] else "") + (" (umgeleitet)" if r["redirected"] else "")) or "-",
                         r["dist"], r["route"], r["rw"], r["det"]]
        cols = [["Frist", "d"], ["Rest", "t"], ["Art", "t"], ["Auftrag", "t"], ["Auftraggeber", "t"], ["Ziel", "t"], ["Entfernung (Ly)", "r"], ["Route", "t"], ["Belohnung", "cr"], ["Details", "t"]]
        blocks = [helpers._block("Offene Missionen", cols, [trs(r) for r in live], "Sortiert nach Frist. Route = Zielsystem liegt auf der aktuellen Route (NavRoute) oder ist dein System. Entfernung ab deinem aktuellen System.")]
        if stale:
            blocks.append(helpers._block("Frist überschritten, aber nicht als gescheitert gemeldet", cols, [trs(r) for r in stale],
                                 "Das Journal meldet das Scheitern erst, wenn du im Spiel bist. Wahrscheinlich sind diese Missionen verfallen."))
        if unknown:
            blocks.append(helpers._block("Aktiv laut Spiel, Details fehlen", [["Mission-ID", "t"], ["Restzeit", "t"]],
                                 [[k, _fmt_rest(v) if isinstance(v, (int, float)) else "-"] for k, v in unknown.items()],
                                 "Diese Missionen hast du vor dem Beginn der gespeicherten Journale angenommen. Das Spiel nennt nur ID und Restzeit zum Zeitpunkt des Ladens."))
        return {"kpi": kpi, "blocks": blocks}
    if op == "ms_dest":
        g_ = {}
        for r in live:
            o = g_.setdefault(r["sys"] or "unbekannt", {"n": 0, "rw": 0, "soon": None, "dist": r["dist"], "route": r["route"], "stn": set(), "ty": set()})
            o["n"] += 1; o["rw"] += r["rw"]; o["stn"].add(r["stn"] or "-"); o["ty"].add(r["ty"])
            if r["rest"] is not None and (o["soon"] is None or r["rest"] < o["soon"]):
                o["soon"] = r["rest"]
        out = [[k, v["n"], v["rw"], _fmt_rest(v["soon"]), v["dist"], v["route"], ", ".join(sorted(v["stn"])), ", ".join(sorted(v["ty"]))]
               for k, v in sorted(g_.items(), key=lambda kv: (kv[1]["dist"] is None, kv[1]["dist"] or 0))]
        return {"kpi": kpi, "blocks": [helpers._block("Nach Zielsystem", [["System", "t"], ["Missionen", "n"], ["Belohnung", "cr"], ["Nächste Frist in", "t"], ["Entfernung (Ly)", "r"], ["Route", "t"], ["Stationen", "t"], ["Arten", "t"]], out,
                                               "Sortiert nach Entfernung. So siehst du, welche Systeme sich für mehrere Missionen auf einmal lohnen.")]}
    hist.sort(key=lambda r: r[0], reverse=True)
    return {"kpi": kpi + [["Abgeschlossen", done, "n"], ["Gescheitert/aufgegeben", fail, "n"]],
            "blocks": [helpers._block("Verlauf", [["Zeit", "d"], ["Auftrag", "t"], ["Art", "t"], ["Auftraggeber", "t"], ["Ergebnis", "t"], ["Belohnung", "cr"]], hist[:300])]}
