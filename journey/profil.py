"""Spielstil: Verteilung der Taetigkeiten, Gewohnheiten (Heatmap) und persoenliche Rekorde. Nur eigene Journal-Daten (Tabellen act und ce)."""

import bisect
from datetime import datetime, timedelta

from . import database, timefmt

CATS = [("handel", "Handel"), ("erkundung", "Erkundung"), ("kampf", "Kampf"), ("mining", "Mining"), ("sonst", "Sonstiges")]
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
# Ereignisart (Tabelle ce) -> (Taetigkeit, Gewicht). Pro Zehn-Minuten-Block gewinnt die Taetigkeit mit der hoechsten Punktzahl.
WEIGHT = {
    "trade": ("handel", 5), "dbuy": ("handel", 2), "dsell": ("handel", 2),
    "jump": ("erkundung", 4), "scan": ("erkundung", 1), "mapd": ("erkundung", 5), "bio": ("erkundung", 4), "touch": ("erkundung", 2),
    "ring": ("erkundung", 1),
    "kill": ("kampf", 6), "target": ("kampf", 1), "hit": ("kampf", 1), "hull": ("kampf", 2), "shield": ("kampf", 1), "intd": ("kampf", 3),
    "death": ("kampf", 3), "vouch": ("kampf", 2),
    "mine": ("mining", 3), "prosp": ("mining", 3), "pmat": ("mining", 1), "drone": ("mining", 1), "crack": ("mining", 3),
}
NON_INCOME = ("Verkauf Schiffe/Module", "Kosten & Käufe")
_CACHE = {}


def _fmt(n):
    return timefmt.deN(f"{int(round(n)):,}")


def _dur(minutes):
    m = int(round(minutes))
    return f"{m // 60} Std. {m % 60:02d} Min." if m >= 60 else f"{m} Min."


def _bdt(b):
    return timefmt.parse_ts(b + "0:00Z").astimezone()


def _loc(ts):
    return timefmt.parse_ts(ts).astimezone()


def _classify(c):
    """Alle aktiven Zehn-Minuten-Bloecke -> (lokale Zeit, Taetigkeit). Luecken zwischen zwei gleichen Nachbarbloecken erben deren Taetigkeit."""
    blocks = [r[0] for r in c.execute("SELECT b FROM act ORDER BY b")]
    score = {}
    marks = ",".join("?" * len(WEIGHT))
    for b, kind, n in c.execute(f"SELECT substr(ts,1,15), kind, COUNT(*) FROM ce WHERE kind IN ({marks}) GROUP BY 1, 2", list(WEIGHT)):
        cat, w = WEIGHT[kind]
        d = score.setdefault(b, {})
        d[cat] = d.get(cat, 0) + w * n
    order = [x[0] for x in CATS]
    cat_of = {}
    for b in blocks:
        s = score.get(b)
        cat_of[b] = max(s, key=lambda k: (s[k], -order.index(k))) if s else None
    out = []
    for i, b in enumerate(blocks):
        cat = cat_of[b]
        if cat is None:
            # Schluessel der Nachbarbloecke in UTC bilden (act speichert UTC)
            pb = (timefmt.parse_ts(b + "0:00Z") - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M")[:15]
            nb = (timefmt.parse_ts(b + "0:00Z") + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M")[:15]
            if cat_of.get(pb) and cat_of.get(pb) == cat_of.get(nb):
                cat = cat_of[pb]
        out.append((b, cat or "sonst"))
    return out


def _monday(d):
    return d - timedelta(days=d.weekday())


def _profile(weeks, cls):
    if not cls:
        return {"cats": CATS, "weeks": [], "heat": None, "total_min": 0}
    today = datetime.now().astimezone().date()
    cut = None
    if weeks:
        cut = _monday(today) - timedelta(weeks=weeks - 1)
    sel = [(b, dt, cat) for b, dt, cat in cls if cut is None or dt.date() >= cut]
    wk = {}
    for b, dt, cat in sel:
        key = _monday(dt.date())
        d = wk.setdefault(key, {x[0]: 0 for x in CATS})
        d[cat] += 10
    if wk:  # Wochen ohne Spielzeit als leere Wochen einfuegen, damit die Zeitachse stimmt
        k0, k1 = min(wk), max(wk)
        while k0 <= k1:
            wk.setdefault(k0, {x[0]: 0 for x in CATS})
            k0 += timedelta(weeks=1)
    wk_list = []
    for key in sorted(wk):
        iso = key.isocalendar()
        end = key + timedelta(days=6)
        mins = wk[key]
        wk_list.append({"start": key.isoformat(), "kw": iso[1], "label": f"{key.strftime('%d.%m.')}–{end.strftime('%d.%m.')}",
                        "min": mins, "total": sum(mins.values())})
    # Trend: letzte Woche gegen den Schnitt der bis zu vier Wochen davor (Anteile in Prozentpunkten)
    trend = None
    full = wk_list
    if cut is not None:  # Trend immer ueber alle Wochen, auch bei kurzem Zeitraum
        fw = {}
        for b, dt, cat in cls:
            d = fw.setdefault(_monday(dt.date()), {x[0]: 0 for x in CATS})
            d[cat] += 10
        k0, k1 = min(fw), max(fw)
        while k0 <= k1:
            fw.setdefault(k0, {x[0]: 0 for x in CATS})
            k0 += timedelta(weeks=1)
        full = [{"min": fw[k], "total": sum(fw[k].values())} for k in sorted(fw)]
    if len(full) >= 2:
        last, prev = full[-1], full[-5:-1]
        pt = sum(w["total"] for w in prev) or 1
        trend = []
        for cid, lab in CATS:
            a = last["min"][cid] / last["total"] * 100 if last["total"] else 0
            p = sum(w["min"][cid] for w in prev) / pt * 100
            trend.append({"id": cid, "label": lab, "now": round(a, 1), "before": round(p, 1), "diff": round(a - p, 1)})
    # Heatmap: Wochentag x Stunde
    cells = {}
    for b, dt, cat in sel:
        k = (dt.weekday(), dt.hour)
        o = cells.setdefault(k, {"min": 0, "cats": {}})
        o["min"] += 10
        o["cats"][cat] = o["cats"].get(cat, 0) + 10
    first, last_d = sel[0][1].date(), sel[-1][1].date()
    ndays = [0] * 7
    d = first
    while d <= last_d:
        ndays[d.weekday()] += 1
        d += timedelta(days=1)
    avg = [[0.0] * 24 for _ in range(7)]
    top = [[""] * 24 for _ in range(7)]
    share = [[0] * 24 for _ in range(7)]
    for (wd, h), o in cells.items():
        avg[wd][h] = round(o["min"] / max(1, ndays[wd]), 1)
        tc = max(o["cats"], key=lambda x: o["cats"][x])
        top[wd][h] = tc
        share[wd][h] = round(o["cats"][tc] / o["min"] * 100)
    day_avg = [round(sum(avg[wd]) / 60, 2) for wd in range(7)]  # Stunden pro Wochentag (Durchschnitt)
    hour_avg = [round(sum(avg[wd][h] for wd in range(7)) / 7, 1) for h in range(24)]
    pk = max(((avg[wd][h], wd, h) for wd in range(7) for h in range(24)), default=(0, 0, 0))
    heat = {"avg": avg, "top": top, "share": share, "days": DAYS, "ndays": ndays, "day_avg": day_avg, "hour_avg": hour_avg,
            "peak": {"wd": pk[1], "h": pk[2], "min": pk[0]} if pk[0] else None,
            "first": first.isoformat(), "last": last_d.isoformat()}
    return {"cats": CATS, "weeks": wk_list, "trend": trend, "heat": heat, "total_min": 10 * len(sel),
            "first": first.isoformat(), "last": last_d.isoformat()}


# ---------------------------------------------------------------------------
# Rekorde
# ---------------------------------------------------------------------------
def _records(c, cls):
    today = datetime.now().astimezone().date()
    recs = []

    def add(rid, label, value, detail, day, group):
        recs.append({"id": rid, "label": label, "value": value, "detail": detail, "date": day.isoformat() if day else "",
                     "recent": bool(day and (today - day).days <= 7), "group": group})

    rows = list(c.execute("SELECT id, ts, kind, n1 FROM ce WHERE kind IN ('jump','stn','touch','kill','death','mine','scan','bio') ORDER BY ts, id"))
    # Fluege ohne Landung: Spruenge zwischen zwei Landungen/Dockvorgaengen
    best_n = best_d = None
    run = None
    kills_run, best_kills = 0, None
    kills_start = None
    per_day = {}
    for r in rows:
        k = r["kind"]
        dt = _loc(r["ts"])
        day = dt.date()
        pd = per_day.setdefault(day, {"jump": 0, "ly": 0.0, "kill": 0, "mine": 0, "scan": 0, "bio": 0})
        if k == "jump":
            pd["jump"] += 1
            pd["ly"] += r["n1"] or 0
            if run is None:
                run = {"n": 0, "ly": 0.0, "start": dt}
            run["n"] += 1
            run["ly"] += r["n1"] or 0
            run["end"] = dt
            if best_n is None or run["n"] > best_n["n"]:
                best_n = dict(run)
            if best_d is None or run["ly"] > best_d["ly"]:
                best_d = dict(run)
        elif k in ("stn", "touch"):
            run = None
        elif k == "kill":
            pd["kill"] += 1
            if kills_run == 0:
                kills_start = dt
            kills_run += 1
            if best_kills is None or kills_run > best_kills["n"]:
                best_kills = {"n": kills_run, "start": kills_start, "end": dt}
        elif k == "death":
            kills_run = 0
        elif k == "mine":
            pd["mine"] += r["n1"] or 1
        elif k == "scan":
            pd["scan"] += 1
        elif k == "bio":
            pd["bio"] += 1
    if best_n:
        add("flug_n", "Längster Flug ohne Landung", f"{best_n['n']} Sprünge", f"{best_d_fmt(best_n)} · {_dur((best_n['end'] - best_n['start']).total_seconds() / 60)}", best_n["end"].date(), "Reise")
    if best_d:
        add("flug_ly", "Weitester Flug ohne Landung", f"{_fmt(best_d['ly'])} Ly", f"{best_d['n']} Sprünge · {_dur((best_d['end'] - best_d['start']).total_seconds() / 60)}", best_d["end"].date(), "Reise")

    def day_best(key, rid, label, unit, group, extra=None):
        cand = [(v[key], d) for d, v in per_day.items() if v[key] > 0]
        if cand:
            val, d = max(cand, key=lambda t: (t[0], t[1]))
            add(rid, label, f"{_fmt(val)} {unit}", extra(per_day[d]) if extra else "", d, group)
    day_best("jump", "tag_spruenge", "Meiste Sprünge an einem Tag", "Sprünge", "Reise", lambda v: f"{_fmt(v['ly'])} Ly an diesem Tag")
    day_best("kill", "tag_kills", "Meiste Abschüsse an einem Tag", "Abschüsse", "Kampf")
    day_best("mine", "tag_mine", "Meiste abgebaute Tonnen an einem Tag", "t", "Mining")
    day_best("scan", "tag_scan", "Meiste Scans an einem Tag", "Scans", "Erkundung")
    day_best("bio", "tag_bio", "Meiste Exobiologie-Proben an einem Tag", "Proben", "Erkundung")
    if best_kills and best_kills["n"] > 1:
        add("kills_serie", "Meiste Abschüsse ohne Tod", f"{best_kills['n']} Abschüsse", "Serie zwischen zwei Abstürzen", best_kills["end"].date(), "Kampf")

    # Einnahmen: bester Stundenverdienst (gleitendes 60-Minuten-Fenster) und bester Tag
    inc = []
    for r in c.execute("SELECT ts, n1 FROM ce WHERE kind='cash' AND n1>0 AND k1 NOT IN (?,?) ORDER BY ts, id", NON_INCOME):
        inc.append((timefmt.parse_ts(r["ts"]).timestamp(), r["n1"], r["ts"]))
    if inc:
        ts = [x[0] for x in inc]
        best, lo, acc, bi = 0.0, 0, 0.0, 0
        for hi in range(len(inc)):
            acc += inc[hi][1]
            while ts[hi] - ts[lo] > 3600:
                acc -= inc[lo][1]
                lo += 1
            if acc > best:
                best, bi, blo = acc, hi, lo
        st, en = _loc(inc[blo][2]), _loc(inc[bi][2])
        add("std_gewinn", "Bester Stundenverdienst", f"{_fmt(best)} Cr", f"{st.strftime('%H:%M')}–{en.strftime('%H:%M')} Uhr (alle Einnahmen in 60 Minuten)", en.date(), "Verdienst")
        byday = {}
        for t, v, s in inc:
            d = _loc(s).date()
            byday[d] = byday.get(d, 0) + v
        d = max(byday, key=lambda x: byday[x])
        add("tag_gewinn", "Bester Tag (Einnahmen)", f"{_fmt(byday[d])} Cr", "ohne Verkauf von Schiffen und Modulen", d, "Verdienst")

    # Spielzeit: Sitzungen und Serien aus den aktiven Zehn-Minuten-Bloecken
    if cls:
        sess, cur = [], [cls[0][1]]
        for _b, dt, _c in cls[1:]:
            if (dt - cur[-1]).total_seconds() > 40 * 60:
                sess.append(cur)
                cur = []
            cur.append(dt)
        sess.append(cur)
        ls = max(sess, key=lambda s: len(s))
        add("sitzung", "Längste Spielsitzung", _dur(len(ls) * 10), f"{ls[0].strftime('%H:%M')}–{ls[-1].strftime('%H:%M')} Uhr (Pausen bis 40 Min. zählen mit)", ls[-1].date(), "Spielzeit")
        mins = {}
        for _b, dt, _c in cls:
            mins[dt.date()] = mins.get(dt.date(), 0) + 10
        d = max(mins, key=lambda x: mins[x])
        add("tag_zeit", "Meiste Spielzeit an einem Tag", _dur(mins[d]), "", d, "Spielzeit")
        days = sorted(mins)
        best, cur_s, start = (1, days[0], days[0]), 1, days[0]
        for i in range(1, len(days)):
            if (days[i] - days[i - 1]).days == 1:
                cur_s += 1
            else:
                cur_s, start = 1, days[i]
            if cur_s > best[0]:
                best = (cur_s, start, days[i])
        add("serie", "Längste Serie von Spieltagen", f"{best[0]} Tage", f"{best[1].strftime('%d.%m.%Y')} bis {best[2].strftime('%d.%m.%Y')}", best[2], "Spielzeit")
        live = 0
        d = days[-1]
        if (today - d).days <= 1:
            live = 1
            while (d - timedelta(days=1)) in mins:
                d -= timedelta(days=1)
                live += 1
        add("serie_jetzt", "Aktuelle Serie", f"{live} Tage" if live else "keine", "aufeinanderfolgende Tage mit Spielzeit bis heute oder gestern", days[-1] if live else None, "Spielzeit")
    return recs


def best_d_fmt(run):
    return f"{_fmt(run['ly'])} Ly"


def profile_api(p):
    try:
        weeks = max(0, min(520, int(p.get("weeks", 12))))
    except (TypeError, ValueError):
        weeks = 12
    c = database._mdb()
    try:
        sig = (timefmt.lang(), c.execute("SELECT COUNT(*) FROM act").fetchone()[0], c.execute("SELECT MAX(id) FROM ce").fetchone()[0], weeks, datetime.now().date().isoformat())
        if _CACHE.get("sig") == sig:
            return _CACHE["out"]
        cls = [(b, _bdt(b), cat) for b, cat in _classify(c)]
        out = _profile(weeks, cls)
        out["records"] = _records(c, cls)
        out["weeks_param"] = weeks
        _CACHE.update(sig=sig, out=out)
        return out
    finally:
        c.close()
