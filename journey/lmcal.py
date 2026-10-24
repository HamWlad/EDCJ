"""Persoenliche Richtwerte fuer Journey-Missionen: Ziele orientieren sich an dem, was du selbst tatsaechlich geschafft hast."""

import json
import statistics
from datetime import datetime, timedelta, timezone

# metric -> (SQL-Wert, WHERE)
METRICS = {
    "jumps": ("COUNT(*)", "kind='jump'"),
    "ly": ("SUM(n1)", "kind='jump'"),
    "kills": ("COUNT(*)", "kind='kill'"),
    "bounty_cr": ("SUM(n1)", "kind='kill'"),
    "sell_t": ("SUM(n1)", "kind='trade' AND k3='sell'"),
    "profit_cr": ("SUM(n3)", "kind='trade' AND k3='sell'"),
    "mine_t": ("COUNT(*)", "kind='mine'"),
    "scans": ("COUNT(DISTINCT k1)", "kind='scan'"),
    "bios": ("COUNT(*)", "kind='bio'"),
    "lands": ("COUNT(*)", "kind='touch'"),
    "maps": ("COUNT(DISTINCT k1)", "kind='mapd'"),
    "missions": ("COUNT(*)", "kind='mis' AND k3='completed'"),
    "craft_n": ("COUNT(*)", "kind='craft'"),
    "mat_n": ("SUM(n1)", "kind='mat' AND n1>0"),
    "explore_cr": ("SUM(n1)", "kind='cash' AND k1='Exploration' AND n1>0"),
}


def _nice(v):
    v = max(1, int(round(v)))
    if v < 20:
        return v
    mag = 10 ** (len(str(v)) - 2)
    return int(round(v / mag) * mag)


def calib(c, days=56):
    """Liefert {'m': {metric: {'day': (typisch, bestwert) | None, 'week': (...)}}, 'sale': {...}, 'jump': {...}, 'n_days': aktive Tage}."""
    cut = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {"m": {}, "days": 0}
    for m, (expr, where) in METRICS.items():
        d = [r[0] or 0 for r in c.execute(f"SELECT {expr} FROM ce WHERE {where} AND ts >= ? GROUP BY substr(ts,1,10)", (cut,)) if (r[0] or 0) > 0]
        w = [r[0] or 0 for r in c.execute(f"SELECT {expr} FROM ce WHERE {where} AND ts >= ? GROUP BY strftime('%Y-%W', ts)", (cut,)) if (r[0] or 0) > 0]
        out["m"][m] = {"day": (statistics.median(d), max(d)) if len(d) >= 3 else None,
                       "week": (statistics.median(w), max(w)) if len(w) >= 2 else None}
    # aktive Stunden je Tag/Woche (Zehn-Minuten-Bloecke)
    bd = {}
    for r in c.execute("SELECT b FROM act WHERE b >= ?", (cut[:15],)):
        bd.setdefault(r[0][:10], 0)
        bd[r[0][:10]] += 1
    dd = [v / 6 for v in bd.values()]
    ww = {}
    for k, v in bd.items():
        try:
            wk = datetime.strptime(k, "%Y-%m-%d").strftime("%Y-%W")
        except ValueError:
            continue
        ww[wk] = ww.get(wk, 0) + v / 6
    out["m"]["active_h"] = {"day": (statistics.median(dd), max(dd)) if len(dd) >= 3 else None,
                            "week": (statistics.median(ww.values()), max(ww.values())) if len(ww) >= 2 else None}
    out["days"] = len(bd)
    # Einzelverkaeufe: groesster Gewinn, groesste Menge, Gewinn je Tonne
    sales = c.execute("SELECT n1, n3 FROM ce WHERE kind='trade' AND k3='sell' AND n1>0 AND n3>0").fetchall()
    out["sale"] = None
    if sales:
        per = sorted(r[1] / r[0] for r in sales)
        q = lambda p: per[min(len(per) - 1, int(p * len(per)))]
        out["sale"] = {"max_profit": max(r[1] for r in sales), "max_t": max(r[0] for r in sales), "n": len(sales),
                       "per_t": {"p50": q(0.5), "p75": q(0.75), "p90": q(0.9)}}
        # Tonnen je Woche, die mindestens mit Marge X verkauft wurden
        out["sale"]["rows"] = [(r[0], r[1]) for r in sales]
    mj = c.execute("SELECT MAX(n1) FROM ce WHERE kind='jump'").fetchone()[0] or 0
    j90 = [r[0] for r in c.execute("SELECT n1 FROM ce WHERE kind='jump' AND n1>0 AND ts >= ? ORDER BY n1", (cut,))]
    out["jump"] = {"max": mj, "p90": j90[int(0.9 * len(j90))] if j90 else 0}
    cap = 0
    for r in c.execute("SELECT js FROM snapkv WHERE k LIKE 'Loadout:%'"):
        try:
            cap = max(cap, json.loads(r[0]).get("CargoCapacity", 0) or 0)
        except ValueError:
            pass
    out["cargo_max"] = cap
    return out


# Faktoren je Zeitraum gegen den typischen Wert (Median ueber Tage bzw. Wochen mit Aktivitaet)
SCOPE = {"daily": ("day", 0.7, 1.25), "weekly": ("week", 0.85, 1.25), "chapter": ("week", 0.9, 1.3), "monthly": ("week", 3.0, 4.5),
         "leicht": ("week", 0.45, 1.0), "mittel": ("week", 0.85, 1.25), "schwer": ("week", 1.4, 1.8)}


def target(cal, metric, key, rng):
    """Realistisches Ziel fuer 'metric' im Zeitraum 'key' (daily/weekly/chapter/monthly/leicht/mittel/schwer) oder None ohne Daten."""
    per, f, capf = SCOPE[key]
    mm = (cal["m"].get(metric) or {}).get(per)
    if not mm:
        return None
    typ, best = mm
    v = typ * f * rng.uniform(0.85, 1.15)
    v = min(v, best * capf)
    return max(1, v) if metric == "active_h" else _nice(v)


def single_sale(cal, kind, key, rng):
    """Ziel fuer einen einzelnen Verkauf (Gewinn oder Menge): aus deinen tatsaechlichen Einzelverkaeufen (Perzentile, nicht aus dem Ausreisser),
    nie ueber dem Bestwert und - bei der Menge - nie ueber der groessten Fracht deiner Schiffe."""
    s = cal.get("sale")
    if not s or s["n"] < 3:
        return None
    rows = s["rows"]
    vals = sorted((r[1] if kind == "profit" else r[0]) for r in rows)
    pq = {"daily": 0.5, "leicht": 0.5, "weekly": 0.75, "mittel": 0.75, "chapter": 0.75, "monthly": 0.9, "schwer": 0.9}[key]
    v = vals[min(len(vals) - 1, int(pq * len(vals)))] * rng.uniform(0.95, 1.15)
    v = min(v, vals[-1])
    if kind == "profit":
        if cal["cargo_max"] and s["per_t"]["p90"]:
            v = min(v, cal["cargo_max"] * s["per_t"]["p90"])  # nie mehr, als in einen Laderaum passt
        return _nice(v)
    return max(1, int(min(v, cal["cargo_max"] or v)))


def margin_goal(cal, key, rng):
    """(Gewinn je Tonne, Tonnen) fuer 'Verkaufe N t mit mindestens X Cr/t Gewinn'. Nur Werte, die du in einer Woche schon erreicht hast."""
    s = cal.get("sale")
    if not s or s["n"] < 5:
        return None
    pt = s["per_t"]
    x = pt["p50"] if key in ("daily", "leicht") else pt["p75"] if key in ("weekly", "mittel", "chapter") else pt["p90"]
    x = _nice(max(1, x * rng.uniform(0.9, 1.05)))
    wk = {}
    for (qty, prof) in s["rows"]:
        if prof / qty >= x:
            wk[0] = wk.get(0, 0) + qty
    # Wochenmenge ueber die Marge: aus den Einzelverkaeufen grob nach Anteil am Wochenwert (typische Verkaufsmenge je Woche)
    tw = (cal["m"].get("sell_t") or {}).get("week")
    tot = sum(q for q, _ in s["rows"]) or 1
    share = wk.get(0, 0) / tot
    if not tw or share <= 0:
        return None
    per, f, _ = SCOPE[key]
    base = (cal["m"]["sell_t"].get("day") if per == "day" else tw) or tw
    n = _nice(max(1, base[0] * share * f))
    return x, n
