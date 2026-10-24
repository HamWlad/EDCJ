"""Dienstakte: Journey-Missionen, Dienstgrade, Meilensteine, Personalakte."""

import hashlib
import json
import random
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import career_api, database, helpers, lmcal, timefmt


LM_RANKS = [(0, "Rekrut"), (20, "Fähnrich"), (60, "Leutnant"), (150, "Oberleutnant"), (300, "Kapitänleutnant"), (600, "Fregattenkapitän"),
            (1000, "Commander"), (1600, "Captain"), (2500, "Commodore"), (4000, "Konteradmiral"), (6000, "Vizeadmiral"), (10000, "Admiral")]
LM_DP = {"daily": 10, "weekly": 40, "monthly": 150, "chapter": 60}
LM_SCALE = {"daily": 1.0, "weekly": 4.0, "monthly": 14.0, "chapter": 4.0, "leicht": 0.6, "mittel": 1.5, "schwer": 3.0}
LM_BASE = {"jumps": 12, "ly": 600, "mine_t": 40, "sell_t": 40, "profit_cr": 400000, "bounty_cr": 300000, "kills": 5, "scans": 15, "maps": 3,
           "lands": 2, "bios": 3, "missions": 2, "dock_n": 3, "sell_cr_at": 300000,
           "new_sys": 3, "new_stn": 2, "refresh_markets": 2, "first_disc": 3, "first_map": 2, "new_species": 2, "new_ring": 3, "dist_far": 150,
           "sprint": 6, "profit_single": 200000, "big_haul": 40, "mine_variety": 2, "unharmed": 5,
           "craft_n": 5, "mat_n": 60, "explore_cr": 500000, "active_h": 3, "long_jump": 40, "profit_per_t": 40}
# Meilensteine: (Zaehler, Schwelle, Name, Beschreibung)
LM_MILES = [
    ("m_total", 1, "Erster Befehl", "1 Journey-Mission abgeschlossen"), ("m_total", 5, "Auf Kurs", "5 Missionen abgeschlossen"),
    ("m_total", 10, "Routine", "10 Missionen abgeschlossen"), ("m_total", 25, "Zuverlässiger Offizier", "25 Missionen abgeschlossen"),
    ("m_total", 50, "Veteran des Dienstes", "50 Missionen abgeschlossen"), ("m_total", 100, "Dienstjubiläum", "100 Missionen abgeschlossen"),
    ("m_total", 250, "Lebenswerk", "250 Missionen abgeschlossen"),
    ("m_daily", 1, "Tagesdienst", "1 Tagesmission erfüllt"), ("m_daily", 7, "Wochenwache", "7 Tagesmissionen erfüllt"), ("m_daily", 30, "Monatsdienst", "30 Tagesmissionen erfüllt"),
    ("streak", 3, "Dreifach-Schicht", "3 Tage in Folge die Tagesmission erfüllt"), ("streak", 7, "Sieben-Tage-Wache", "7 Tage in Folge"),
    ("streak", 14, "Zwei Wochen ohne Pause", "14 Tage in Folge"), ("streak", 30, "Unermüdlich", "30 Tage in Folge"),
    ("m_weekly", 1, "Wochenbericht", "1 Wochenmission erfüllt"), ("m_weekly", 4, "Vier-Wochen-Einsatz", "4 Wochenmissionen"), ("m_weekly", 12, "Quartalsbericht", "12 Wochenmissionen"),
    ("m_monthly", 1, "Monatsdirektive", "1 Monatsmission erfüllt"), ("m_monthly", 3, "Quartalsdirektive", "3 Monatsmissionen"), ("m_monthly", 12, "Jahresbericht", "12 Monatsmissionen"),
    ("m_chapter", 1, "Erstes Kapitel", "1 Wochenkapitel abgeschlossen"), ("m_chapter", 4, "Vier Kapitel", "4 Wochenkapitel abgeschlossen"),
    ("m_chapter", 12, "Buch des Quartals", "12 Wochenkapitel abgeschlossen"), ("m_chapter", 26, "Halbjahresband", "26 Wochenkapitel abgeschlossen"),
    ("m_random", 1, "Sonderauftrag", "1 Zufallsmission erfüllt"), ("m_random", 10, "Springer", "10 Zufallsmissionen"), ("m_random", 25, "Allzweckoffizier", "25 Zufallsmissionen"),
    ("m_hard", 1, "Harte Nuss", "1 schwere Zufallsmission erfüllt"), ("m_hard", 5, "Nerven aus Duranium", "5 schwere Zufallsmissionen"),
    ("mine_t", 100, "Erzsucher", "100 t Erz in Journey-Missionen abgebaut"), ("mine_t", 500, "Bergbau-Meister", "500 t Erz abgebaut"), ("mine_t", 2000, "Titan der Ringe", "2.000 t Erz abgebaut"),
    ("jumps", 50, "Sprungbereit", "50 Sprünge in Missionen"), ("jumps", 250, "Navigator", "250 Sprünge"), ("jumps", 1000, "Hyperraum-Veteran", "1.000 Sprünge"),
    ("ly", 2000, "Weitreisender", "2.000 Ly in Missionen geflogen"), ("ly", 10000, "Grenzgänger", "10.000 Ly"), ("ly", 50000, "Entdecker der Randgebiete", "50.000 Ly"),
    ("kills", 25, "Wachposten", "25 Abschüsse in Missionen"), ("kills", 100, "Frontkämpfer", "100 Abschüsse"), ("kills", 500, "Schrecken der Piraten", "500 Abschüsse"),
    ("bounty_cr", 5000000, "Kopfgeldjäger", "5 Mio Cr Kopfgeld in Missionen"), ("bounty_cr", 50000000, "Prämienkönig", "50 Mio Cr Kopfgeld"),
    ("profit_cr", 5000000, "Kaufmann", "5 Mio Cr Handelsgewinn in Missionen"), ("profit_cr", 50000000, "Handelsprinz", "50 Mio Cr Gewinn"), ("profit_cr", 500000000, "Magnat", "500 Mio Cr Gewinn"),
    ("sell_t", 200, "Lieferant", "200 t Ware verkauft"), ("sell_t", 1000, "Großhändler", "1.000 t Ware verkauft"),
    ("scans", 100, "Kartograph", "100 Körper gescannt"), ("scans", 500, "Sternenkundler", "500 Körper gescannt"),
    ("maps", 25, "Vermesser", "25 Körper kartiert"), ("maps", 100, "Chefkartograph", "100 Körper kartiert"),
    ("lands", 10, "Bodenkontakt", "10 Landungen"), ("lands", 50, "Landekommando", "50 Landungen"),
    ("bios", 10, "Xenobiologe", "10 Bio-Proben"), ("bios", 50, "Leiter der Biologie", "50 Bio-Proben"),
    ("docks", 25, "Stammgast", "25 Andockmanöver"), ("docks", 100, "Hafenmeister", "100 Andockmanöver"),
    ("st_distinct", 10, "Hafenkenner", "10 verschiedene Zielstationen"), ("st_distinct", 30, "Stationsinspektor", "30 verschiedene Zielstationen"),
    ("sys_distinct", 10, "Systemkenner", "10 verschiedene Zielsysteme"), ("sys_distinct", 40, "Sektorwächter", "40 verschiedene Zielsysteme"),
    ("gamemis", 10, "Missionsexperte", "10 Spielmissionen in Journey-Missionen"), ("gamemis", 50, "Auftragsprofi", "50 Spielmissionen"),
    ("newsys", 10, "Pionier", "10 nie zuvor besuchte Systeme in Missionen"), ("newsys", 50, "Sternenpionier", "50 neue Systeme"),
    ("newstn", 5, "Neuland", "5 neue Stationen"), ("newstn", 20, "Stationsentdecker", "20 neue Stationen"),
    ("mkt", 5, "Marktforscher", "5 Märkte aufgezeichnet/aufgefrischt"), ("mkt", 25, "Marktchronist", "25 Märkte aufgezeichnet/aufgefrischt"),
    ("firstd", 10, "Erstentdecker", "10 Körper als Erster entdeckt"), ("firstd", 50, "Namensgeber", "50 Erstentdeckungen"),
    ("firstm", 5, "Erstkartierer", "5 unkartierte Körper kartiert"), ("firstm", 25, "Vermessungschef", "25 unkartierte Körper kartiert"),
    ("newspec", 5, "Artenjäger", "5 neue Arten analysiert"), ("newspec", 20, "Chefbiologe", "20 neue Arten analysiert"),
    ("newring", 10, "Ringfinder", "10 neue Ringe gescannt"), ("newring", 40, "Herr der Ringe", "40 neue Ringe gescannt"),
    ("far", 500, "Expeditionsleiter", "Expeditionen über insgesamt 500 Ly Abstand"), ("far", 2000, "Grenzgänger des Quadranten", "Expeditionen über 2.000 Ly Abstand"),
    ("sprints", 1, "Sprungserie", "1 Sprungserie geschafft"), ("sprints", 5, "Hyperraum-Rennfahrer", "5 Sprungserien"),
    ("bigdeal", 1, "Großer Deal", "1 Einzelverkauf mit großem Gewinn"), ("bigdeal", 5, "Dealmeister", "5 große Einzelverkäufe"),
    ("unharmed", 1, "Unversehrt", "1 Kampfauftrag ohne eigenen Tod"), ("unharmed", 5, "Unantastbar", "5 Kampfaufträge ohne eigenen Tod"),
    ("dp", 100, "Hundert Punkte", "100 Dienstpunkte"), ("dp", 500, "Fünfhundert Punkte", "500 Dienstpunkte"), ("dp", 1000, "Tausend Punkte", "1.000 Dienstpunkte"),
    ("dp", 5000, "Fünftausend Punkte", "5.000 Dienstpunkte"),
]
LM_CNT = {"jumps": "jumps", "ly": "ly", "mine_t": "mine_t", "sell_t": "sell_t", "profit_cr": "profit_cr", "bounty_cr": "bounty_cr", "kills": "kills",
          "scans": "scans", "maps": "maps", "lands": "lands", "bios": "bios", "missions": "gamemis", "dock_n": "docks", "dock_at": "docks",
          "new_sys": "newsys", "new_stn": "newstn", "market_scan": "mkt", "refresh_markets": "mkt", "first_disc": "firstd", "first_map": "firstm",
          "new_species": "newspec", "new_ring": "newring", "dist_far": "far", "sprint": "sprints", "profit_single": "bigdeal", "big_haul": "bigdeal",
          "unharmed": "unharmed", "mine_variety": "mine_v", "craft_n": "crafts", "mat_n": "mats", "explore_cr": "explcr", "active_h": "acth",
          "long_jump": "longj", "profit_per_t": "marge"}


def _lm_nice(v):
    v = max(1, int(round(v)))
    if v < 20:
        return v
    mag = 10 ** (len(str(v)) - 2)
    return int(round(v / mag) * mag)


def _lm_fmt(v):
    return timefmt.deN("{:,}".format(int(v)))


def _lm_periods():
    now = datetime.now().astimezone()
    d0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    utc = lambda dt: dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    wk0 = d0 - timedelta(days=d0.weekday())
    nm = (d0.replace(day=1) + timedelta(days=32)).replace(day=1)
    iso = now.isocalendar()
    return {"daily": (d0.strftime("%Y-%m-%d"), utc(d0 + timedelta(days=1)), "Tagesbefehl " + d0.strftime("%d.%m.%Y")),
            "weekly": (f"{iso[0]}-W{iso[1]:02d}", utc(wk0 + timedelta(days=7)), f"Wochenauftrag KW {iso[1]}/{iso[0]}"),
            "chapter": (f"{iso[0]}-W{iso[1]:02d}", utc(wk0 + timedelta(days=7)), f"Wochenkapitel KW {iso[1]}/{iso[0]}"),
            "monthly": (d0.strftime("%Y-%m"), utc(nm), "Monatsdirektive " + ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
                                                                           "Oktober", "November", "Dezember"][d0.month - 1] + d0.strftime(" %Y"))}


def lm_pools(c):
    q = lambda sql, *a: c.execute(sql, a).fetchall()
    dfn = helpers._dist_fn(c)
    st = [r["name"] for r in q("SELECT name, system FROM stdb WHERE via='docked' AND type NOT LIKE '%Carrier%' AND type != 'Siedlung'")
          if True]
    stsys = {r["name"]: r["system"] for r in q("SELECT name, system FROM stdb WHERE via='docked'")}
    near = [n for n in st if (dfn(stsys.get(n)) is not None and dfn(stsys.get(n)) <= 250)]
    systems = [r[0] for r in q("SELECT DISTINCT k1 FROM ce WHERE kind='jump' AND k1 != ''")]
    nsys = [x for x in systems if dfn(x) is not None and 0 < dfn(x) <= 250]
    gap = [dict(r) for r in q("""SELECT d.name, d.system, d.market_id FROM stdb d WHERE d.via='docked' AND d.market_id > 0
                                  AND NOT EXISTS (SELECT 1 FROM snap s WHERE s.market_id=d.market_id)""")]
    cut7 = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = q("SELECT COUNT(*) FROM (SELECT market_id, MAX(ts) t FROM snap GROUP BY market_id) WHERE t < ?", cut7)[0][0]
    xhas = {"first_disc": "SELECT 1 FROM ce WHERE kind='scan' AND k3 LIKE '%erst%' LIMIT 1",
            "first_map": "SELECT 1 FROM ce WHERE kind='scan' AND k3 LIKE '%unkart%' LIMIT 1",
            "ring": "SELECT 1 FROM ce WHERE kind='ring' LIMIT 1", "ores2": "SELECT 1 FROM ce WHERE kind='mine' GROUP BY k1 HAVING 1 LIMIT 1 OFFSET 1"}
    return {"gap": gap, "stale": stale, "x": {k: bool(q(v)) for k, v in xhas.items()}, "stations": near or st, "systems": nsys or systems, "ores": [r[0] for r in q("SELECT DISTINCT k1 FROM ce WHERE kind='mine' AND k1 != ''")],
            "items": [r[0] for r in q("SELECT DISTINCT k1 FROM ce WHERE kind='trade' AND k3='sell' AND k1 != ''")],
            "has": {k: bool(q("SELECT 1 FROM ce WHERE kind=? LIMIT 1", kk)) for k, kk in
                    (("jump", "jump"), ("mine", "mine"), ("kill", "kill"), ("trade", "trade"), ("scan", "scan"), ("bio", "bio"), ("land", "touch"), ("map", "mapd"), ("mis", "mis"))}}


_NEW_OBJ = {"long_jump", "craft_n", "mat_n", "explore_cr", "active_h", "profit_per_t"}


def _new_obj(th, amt, cal, key, rng):
    """Ziele der neuen Typen (Grenzen stammen aus den eigenen Aufzeichnungen)."""
    if th == "long_jump":
        v = amt("long_jump"); return {"type": "long_jump", "target": v, "label": f"Schaffe einen einzelnen Hyperraumsprung von mindestens {_lm_fmt(v)} Ly"}
    if th == "craft_n":
        v = amt("craft_n"); return {"type": "craft_n", "target": v, "label": f"Führe {v} Engineering-Crafts durch"}
    if th == "mat_n":
        v = amt("mat_n"); return {"type": "mat_n", "target": v, "label": f"Sammle {v} Materialien (Planeten, Signalquellen, Wracks)"}
    if th == "explore_cr":
        v = amt("explore_cr"); return {"type": "explore_cr", "target": v, "label": f"Verkaufe Erkundungsdaten für {_lm_fmt(v)} Cr"}
    if th == "active_h":
        v = amt("active_h"); v = max(1, int(round(v))); return {"type": "active_h", "target": v, "label": f"Sei {v} Stunden im Spiel aktiv"}
    if th == "profit_per_t":
        g_ = lmcal.margin_goal(cal, key, rng)
        if not g_:
            return None
        x, n = g_
        return {"type": "profit_per_t", "target": n, "per_t": x, "label": f"Verkaufe {n} t Ware mit mindestens {_lm_fmt(x)} Cr Gewinn je Tonne"}
    return None


_CHAPTERS = {
    "handel": ("Frachtverkehr", ["sell_t", "profit_per_t", "profit_cr", "new_stn"],
               ["Die Lager füllen sich, die Märkte warten. Diese Woche zählt jede Tonne, die du mit Gewinn an den Mann bringst.",
                "Ein ruhiger Laderaum ist ein teurer Laderaum. Das Kapitel dreht sich um saubere Margen."]),
    "kampf": ("Frontdienst", ["kills", "bounty_cr", "unharmed"],
              ["Auf den Funkbändern wird es laut. Das Kapitel verlangt Treffer und Haltung, nicht Heldentod.",
               "Die Kopfgeldlisten sind lang. Arbeite sie ab und komm heil zurück."]),
    "mining": ("Erzgürtel", ["mine_t", "mine_variety", "sell_t"],
               ["Die Ringe geben her, was man ihnen abringt. Dieses Kapitel gehört dem Bohrer.",
                "Ein voller Frachtraum Erz ist ein guter Anfang. Vielfalt macht den Meister."]),
    "erkundung": ("Weite Reise", ["ly", "new_sys", "scans", "long_jump", "bios", "mat_n"],
                  ["Hinter dem nächsten Sprung liegt unbekanntes Gebiet. Das Kapitel führt dich hinaus.",
                   "Sterne zählen, Körper scannen, Spuren hinterlassen: ein Kapitel für Entdecker."]),
}
_CH_NEED = {"handel": "trade", "kampf": "kill", "mining": "mine", "erkundung": "jump"}


def _std_obj(th, amt, P, rng, cal, key):
    """Teilziel der Standardtypen fuer Wochenkapitel (Zielwerte aus den eigenen Richtwerten); None, wenn dir dazu die Datenbasis fehlt."""
    has = P["has"]
    if th in ("sell_t", "profit_cr") and not has["trade"]:
        return None
    if th == "sell_t":
        v = amt("sell_t"); return {"type": "sell_t", "target": v, "label": f"Verkaufe {v} t Ware"}
    if th == "profit_cr":
        v = amt("profit_cr"); return {"type": "profit_cr", "target": v, "label": f"Erziele {_lm_fmt(v)} Cr Handelsgewinn"}
    if th == "new_stn" and P["stations"]:
        v = max(1, min(3, amt("new_stn"))); return {"type": "new_stn", "target": v, "label": f"Docke an {v} " + ("Station, die" if v == 1 else "Stationen, die") + " du noch nie besucht hast"}
    if th == "kills" and has["kill"]:
        v = amt("kills"); return {"type": "kills", "target": v, "label": f"Erledige {v} Gegner (Kopfgeld oder Bond)"}
    if th == "bounty_cr" and has["kill"]:
        v = amt("bounty_cr"); return {"type": "bounty_cr", "target": v, "label": f"Kassiere {_lm_fmt(v)} Cr Kopfgeld/Bonds"}
    if th == "unharmed" and has["kill"]:
        v = amt("unharmed"); return {"type": "unharmed", "target": v, "label": f"Erledige {v} Gegner, ohne selbst zu sterben"}
    if th == "mine_t" and has["mine"] and P["ores"]:
        v = amt("mine_t"); return {"type": "mine_t", "target": v, "ore": "", "label": f"Baue {v} t Erz ab"}
    if th == "mine_variety" and P["x"]["ores2"]:
        v = min(max(2, amt("mine_variety")), 4); return {"type": "mine_variety", "target": v, "label": f"Baue {v} verschiedene Erzsorten ab"}
    if th == "ly" and has["jump"]:
        v = amt("ly"); return {"type": "ly", "target": v, "label": f"Lege {_lm_fmt(v)} Ly im Hyperraum zurück"}
    if th == "new_sys" and has["jump"]:
        v = amt("new_sys"); return {"type": "new_sys", "target": v, "label": f"Springe in {v} " + ("System" if v == 1 else "Systeme") + ", in " + ("dem" if v == 1 else "denen") + " du noch nie warst"}
    if th == "scans" and has["scan"]:
        v = amt("scans"); return {"type": "scans", "target": v, "label": f"Scanne {v} Himmelskörper"}
    if th == "bios" and has["bio"]:
        v = amt("bios"); return {"type": "bios", "target": v, "label": f"Analysiere {v} " + ("biologische Probe" if v == 1 else "biologische Proben")}
    if th == "long_jump" and has["jump"] and cal["jump"]["max"] > 0:
        return _new_obj("long_jump", amt, cal, key, rng)
    if th in ("profit_per_t", "craft_n", "mat_n", "active_h"):
        if th == "craft_n" and not c_has(P, "craft"):
            return None
        return _new_obj(th, amt, cal, key, rng)
    return None


def c_has(P, kind):
    return bool(P.get("extra", {}).get(kind))


def lm_chapter(c, rng, P, cal, key, amt):
    """Wochenkapitel: Thema aus der Spielzeit der letzten vier Wochen, drei Teilziele aus den eigenen Richtwerten."""
    from . import profil
    P.setdefault("extra", {})["craft"] = c.execute("SELECT 1 FROM ce WHERE kind='craft' LIMIT 1").fetchone() is not None
    cut = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%dT%H:%M")[:15]
    mins = {}
    for b, cat in profil._classify(c):
        if b >= cut:
            mins[cat] = mins.get(cat, 0) + 10
    avail = {k: v for k, v in mins.items() if k in _CHAPTERS and P["has"].get(_CH_NEED[k])}
    last = c.execute("SELECT spec FROM lm WHERE scope='chapter' ORDER BY created DESC LIMIT 1").fetchone()
    last_theme = json.loads(last[0]).get("theme") if last else None
    cand = {k: v for k, v in avail.items() if k != last_theme} or avail
    if not cand:
        cand = {k: 1 for k in _CHAPTERS if P["has"].get(_CH_NEED[k])} or {"erkundung": 1}
    keys = sorted(cand)
    theme = rng.choices(keys, weights=[max(1, cand[k]) for k in keys])[0]
    name, prefs, flavors = _CHAPTERS[theme]
    objs, used = [], set()
    for th in prefs:
        o = _std_obj(th, amt, P, rng, cal, key)
        if o and o["type"] not in used:
            objs.append(o)
            used.add(o["type"])
        if len(objs) == 3:
            break
    if cal["m"].get("active_h", {}).get("week") and len(objs) < 3:
        o = _new_obj("active_h", amt, cal, key, rng)
        if o and o["type"] not in used:
            objs.append(o)
    tot = sum(mins.values()) or 1
    share = round(mins.get(theme, 0) / tot * 100)
    brief = rng.choice(flavors) + (f" Gewählt, weil {share} % deiner Spielzeit der letzten vier Wochen darauf entfielen." if mins else "")
    return {"objs": objs, "dp": LM_DP["chapter"], "diff": "", "theme": theme, "chapter": name, "brief": brief}


def lm_generate(c, scope, rng, diff=None):
    """Zufaellige Mission aus eigenen Aufzeichnungen. Rueckgabe: spec-Dict."""
    P = lm_pools(c)
    has = P["has"]
    sc = LM_SCALE[diff or scope]
    key = diff or scope
    cal = lmcal.calib(c)
    themes = []
    if P["stations"]:
        themes.append("station")
    if has["jump"] and P["systems"]:
        themes += ["reise", "system"]
    if has["mine"] and P["ores"]:
        themes.append("mine")
    if has["trade"]:
        themes.append("handel")
    if has["kill"]:
        themes.append("kampf")
    if has["scan"]:
        themes.append("scan")
    if has["bio"]:
        themes.append("bio")
    if has["land"]:
        themes.append("land")
    if has["map"]:
        themes.append("map")
    if has["mis"]:
        themes.append("mission")
    if has["jump"]:
        themes += ["new_sys", "dist_far", "sprint"]
    if P["stations"]:
        themes.append("new_stn")
    if P["gap"]:
        themes.append("market_scan")
    if P["stale"] >= 2:
        themes.append("refresh")
    if P["x"]["first_disc"]:
        themes.append("first_disc")
    if P["x"]["first_map"]:
        themes.append("first_map")
    if has["bio"]:
        themes.append("new_species")
    if P["x"]["ring"]:
        themes.append("new_ring")
    if has["trade"]:
        themes += ["profit_single", "big_haul"]
    if P["x"]["ores2"]:
        themes.append("mine_variety")
    if has["kill"]:
        themes.append("unharmed")
    exp_cash = c.execute("SELECT 1 FROM ce WHERE kind='cash' AND k1='Exploration' LIMIT 1").fetchone() is not None
    if has["jump"] and cal["jump"]["max"] > 0:
        themes.append("long_jump")
    if c.execute("SELECT 1 FROM ce WHERE kind='craft' LIMIT 1").fetchone():
        themes.append("craft_n")
    if c.execute("SELECT 1 FROM ce WHERE kind='mat' AND n1>0 LIMIT 1").fetchone():
        themes.append("mat_n")
    if exp_cash:
        themes.append("explore_cr")
    if key in ("weekly", "monthly", "schwer", "mittel") and (cal["m"].get("active_h") or {}).get("week"):
        themes.append("active_h")
    if has["trade"] and lmcal.margin_goal(cal, key, rng):
        themes.append("profit_per_t")
    if not themes:
        themes = ["reise"]
    n_obj = {"daily": 2, "weekly": 3, "monthly": 4}.get(scope) or (1 if diff == "leicht" else 2 if diff == "mittel" else 3)
    chosen = rng.sample(themes, min(n_obj, len(themes)))
    METRIC = {"jumps": "jumps", "ly": "ly", "mine_t": "mine_t", "sell_t": "sell_t", "profit_cr": "profit_cr", "bounty_cr": "bounty_cr", "kills": "kills",
              "scans": "scans", "maps": "maps", "lands": "lands", "bios": "bios", "missions": "missions", "craft_n": "craft_n", "mat_n": "mat_n",
              "explore_cr": "explore_cr", "active_h": "active_h"}

    def amt(k):
        """Ziel aus den eigenen Richtwerten (was du pro Tag/Woche tatsaechlich schaffst); ohne Daten die Grundwerte."""
        if k in ("profit_single", "big_haul"):
            v = lmcal.single_sale(cal, "profit" if k == "profit_single" else "t", key, rng)
            if v:
                return v
        elif k in METRIC:
            v = lmcal.target(cal, METRIC[k], key, rng)
            if v:
                return v
        elif k in ("new_sys", "sprint"):
            j = lmcal.target(cal, "jumps", key, rng)
            if j:
                return max(1, min(_lm_nice(LM_BASE[k] * sc * rng.uniform(0.7, 1.3)), j))
        elif k in ("first_disc", "new_ring", "first_map"):
            j = lmcal.target(cal, "maps" if k == "first_map" else "scans", key, rng)
            if j:
                return max(1, min(_lm_nice(LM_BASE[k] * sc * rng.uniform(0.7, 1.3)), j))
        elif k == "new_species":
            j = lmcal.target(cal, "bios", key, rng)
            if j:
                return max(1, min(_lm_nice(LM_BASE[k] * sc * rng.uniform(0.7, 1.3)), j))
        elif k == "unharmed":
            j = lmcal.target(cal, "kills", key, rng)
            if j:
                return max(1, min(_lm_nice(LM_BASE[k] * sc * rng.uniform(0.7, 1.3)), j))
        elif k == "sell_cr_at":
            j = lmcal.target(cal, "profit_cr", key, rng)
            if j:
                return max(10000, _lm_nice(j * 1.5))
        elif k == "long_jump":
            lj = cal["jump"]["p90"] or cal["jump"]["max"]
            if lj:
                return max(5, _lm_nice(lj * {"daily": 0.9, "weekly": 0.95, "monthly": 1.0, "leicht": 0.8, "mittel": 0.95, "schwer": 1.02}.get(key, 0.95)))
        return _lm_nice(LM_BASE[k] * sc * rng.uniform(0.7, 1.3))
    if scope == "chapter":
        return lm_chapter(c, rng, P, cal, key, amt)
    objs = []
    for th in chosen:
        if th == "station":
            sn = rng.choice(P["stations"])
            objs.append({"type": "dock_at", "target": 1, "station": sn, "label": f"Fliege zur Station {sn} und docke dort an"})
            if has["trade"] and rng.random() < 0.6:
                v = amt("sell_cr_at")
                objs.append({"type": "sell_cr_at", "target": v, "station": sn, "label": f"Verkaufe bei {sn} Waren für {_lm_fmt(v)} Cr"})
        elif th == "reise":
            if rng.random() < 0.5:
                v = amt("jumps"); objs.append({"type": "jumps", "target": v, "label": f"Führe {v} Hyperraumsprünge durch"})
            else:
                v = amt("ly"); objs.append({"type": "ly", "target": v, "label": f"Lege {_lm_fmt(v)} Ly im Hyperraum zurück"})
        elif th == "system":
            sy = rng.choice(P["systems"])
            objs.append({"type": "visit_sys", "target": 1, "system": sy, "label": f"Springe ins System {sy}"})
        elif th == "mine":
            ore = rng.choice(P["ores"])
            v = amt("mine_t"); objs.append({"type": "mine_t", "target": v, "ore": ore, "label": f"Baue {v} t {ore} ab"})
        elif th == "handel":
            if P["items"] and rng.random() < 0.5:
                it = rng.choice(P["items"]); v = amt("sell_t")
                objs.append({"type": "sell_t", "target": v, "item": it, "label": f"Verkaufe {v} t {it}"})
            else:
                v = amt("profit_cr"); objs.append({"type": "profit_cr", "target": v, "label": f"Erziele {_lm_fmt(v)} Cr Handelsgewinn"})
        elif th == "kampf":
            if rng.random() < 0.5:
                v = amt("kills"); objs.append({"type": "kills", "target": v, "label": f"Erledige {v} Gegner (Kopfgeld oder Bond)"})
            else:
                v = amt("bounty_cr"); objs.append({"type": "bounty_cr", "target": v, "label": f"Kassiere {_lm_fmt(v)} Cr Kopfgeld/Bonds"})
        elif th == "scan":
            v = amt("scans"); objs.append({"type": "scans", "target": v, "label": f"Scanne {v} Himmelskörper"})
        elif th == "bio":
            v = amt("bios"); objs.append({"type": "bios", "target": v, "label": f"Analysiere {v} " + ("biologische Probe" if v == 1 else "biologische Proben")})
        elif th == "land":
            v = amt("lands"); objs.append({"type": "lands", "target": v, "label": f"Lande {v}× auf einem Planeten"})
        elif th == "map":
            v = amt("maps"); objs.append({"type": "maps", "target": v, "label": f"Kartiere {v} Körper mit dem Oberflächenscanner"})
        elif th == "new_sys":
            v = amt("new_sys"); objs.append({"type": "new_sys", "target": v, "label": f"Springe in {v} " + ("System" if v == 1 else "Systeme") + ", in " + ("dem" if v == 1 else "denen") + " du noch nie warst"})
        elif th == "new_stn":
            v = amt("new_stn"); objs.append({"type": "new_stn", "target": v, "label": f"Docke an {v} " + ("Station, die" if v == 1 else "Stationen, die") + " du noch nie besucht hast"})
        elif th == "market_scan":
            g_ = rng.choice(P["gap"])
            objs.append({"type": "market_scan", "target": 1, "station": g_["name"], "market_id": g_["market_id"],
                         "label": f"Zeichne den Markt von {g_['name']} ({g_['system']}) auf – bisher ohne Marktdaten"})
        elif th == "refresh":
            v = max(1, min(amt("refresh_markets"), P["stale"])); objs.append({"type": "refresh_markets", "target": v, "label": f"Frische {v} Märkte auf, die älter als 7 Tage sind (oder fehlen)"})
        elif th == "first_disc":
            v = amt("first_disc"); objs.append({"type": "first_disc", "target": v, "label": f"Scanne {v} " + ("Körper, den" if v == 1 else "Körper, die") + " vor dir noch niemand entdeckt hat"})
        elif th == "first_map":
            v = amt("first_map"); objs.append({"type": "first_map", "target": v, "label": f"Kartiere {v} " + ("Körper, der" if v == 1 else "Körper, die") + " noch nie kartiert wurde" + ("" if v == 1 else "n")})
        elif th == "new_species":
            v = amt("new_species"); objs.append({"type": "new_species", "target": v, "label": f"Analysiere {v} " + ("Art" if v == 1 else "Arten") + ", die du noch nie analysiert hast"})
        elif th == "new_ring":
            v = amt("new_ring"); objs.append({"type": "new_ring", "target": v, "label": f"Scanne {v} Ringe, die nicht in deinen Aufzeichnungen stehen"})
        elif th == "dist_far":
            v = amt("dist_far"); objs.append({"type": "dist_far", "target": v, "label": f"Expedition: Entferne dich {_lm_fmt(v)} Ly von deinem Startpunkt"})
        elif th == "sprint":
            v = amt("sprint"); objs.append({"type": "sprint", "target": v, "label": f"Sprungserie: {v} Sprünge innerhalb von 60 Minuten"})
        elif th == "profit_single":
            v = amt("profit_single"); objs.append({"type": "profit_single", "target": v, "label": f"Erziele mit einem einzigen Verkauf {_lm_fmt(v)} Cr Gewinn"})
        elif th == "big_haul":
            v = amt("big_haul"); objs.append({"type": "big_haul", "target": v, "label": f"Verkaufe {v} t in einem einzigen Verkauf"})
        elif th == "mine_variety":
            v = min(max(2, amt("mine_variety")), 4); objs.append({"type": "mine_variety", "target": v, "label": f"Baue {v} verschiedene Erzsorten ab"})
        elif th == "unharmed":
            v = amt("unharmed"); objs.append({"type": "unharmed", "target": v, "label": f"Erledige {v} Gegner, ohne selbst zu sterben"})
        elif th == "mission":
            v = amt("missions"); objs.append({"type": "missions", "target": v, "label": f"Schließe {v} Missionen im Spiel ab"})
        elif th in _NEW_OBJ:
            o_ = _new_obj(th, amt, cal, key, rng)
            if o_:
                objs.append(o_)
    dp = LM_DP.get(scope) or {"leicht": 5, "mittel": 12, "schwer": 25}[diff]
    return {"objs": objs, "dp": dp, "diff": diff or ""}


def lm_value(c, o, t0, t1):
    t = o["type"]
    base = " AND ts >= ? AND ts <= ?"
    a = (t0, t1)
    one = lambda sql, *x: (c.execute(sql, x).fetchone()[0] or 0)
    if t == "dock_at":
        return one("SELECT COUNT(*) FROM ce WHERE kind='stn' AND k1=?" + base, o["station"], *a)
    if t == "dock_n":
        return one("SELECT COUNT(DISTINCT k1) FROM ce WHERE kind='stn' AND k3 != 'Siedlung'" + base, *a)
    if t == "visit_sys":
        return one("SELECT COUNT(*) FROM ce WHERE kind='jump' AND k1=?" + base, o["system"], *a)
    if t == "jumps":
        return one("SELECT COUNT(*) FROM ce WHERE kind='jump'" + base, *a)
    if t == "ly":
        return one("SELECT SUM(n1) FROM ce WHERE kind='jump'" + base, *a)
    if t == "mine_t":
        return one("SELECT COUNT(*) FROM ce WHERE kind='mine' AND (?='' OR k1=?)" + base, o.get("ore", ""), o.get("ore", ""), *a)
    if t == "sell_t":
        return one("SELECT SUM(n1) FROM ce WHERE kind='trade' AND k3='sell' AND (?='' OR k1=?)" + base, o.get("item", ""), o.get("item", ""), *a)
    if t == "sell_cr_at":
        return one("SELECT SUM(n2) FROM ce WHERE kind='trade' AND k3='sell' AND k2=?" + base, o["station"], *a)
    if t == "profit_cr":
        return one("SELECT SUM(n3) FROM ce WHERE kind='trade' AND k3='sell'" + base, *a)
    if t == "kills":
        return one("SELECT COUNT(*) FROM ce WHERE kind='kill'" + base, *a)
    if t == "bounty_cr":
        return one("SELECT SUM(n1) FROM ce WHERE kind='kill'" + base, *a)
    if t == "scans":
        return one("SELECT COUNT(DISTINCT k1) FROM ce WHERE kind='scan'" + base, *a)
    if t == "maps":
        return one("SELECT COUNT(DISTINCT k1) FROM ce WHERE kind='mapd'" + base, *a)
    if t == "lands":
        return one("SELECT COUNT(*) FROM ce WHERE kind='touch'" + base, *a)
    if t == "bios":
        return one("SELECT COUNT(*) FROM ce WHERE kind='bio'" + base, *a)
    if t == "new_sys":
        return one("""SELECT COUNT(DISTINCT k1) FROM ce e WHERE kind='jump' AND ts >= ? AND ts <= ? AND NOT EXISTS
                      (SELECT 1 FROM ce e2 WHERE e2.kind IN ('jump','pos') AND e2.k1=e.k1 AND e2.ts < ?)""", t0, t1, t0)
    if t == "new_stn":
        return one("""SELECT COUNT(DISTINCT k1) FROM ce e WHERE kind='stn' AND k3 != 'Siedlung' AND ts >= ? AND ts <= ? AND NOT EXISTS
                      (SELECT 1 FROM ce e2 WHERE e2.kind='stn' AND e2.k1=e.k1 AND e2.ts < ?)""", t0, t1, t0)
    if t == "market_scan":
        return one("SELECT COUNT(*) FROM snap WHERE market_id=? AND ts >= ? AND ts <= ?", o["market_id"], t0, t1)
    if t == "refresh_markets":
        cut7 = (timefmt.parse_ts(t0) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return one("""SELECT COUNT(*) FROM (SELECT s.market_id FROM snap s WHERE s.ts >= ? AND s.ts <= ? GROUP BY s.market_id
                      HAVING (SELECT MAX(s2.ts) FROM snap s2 WHERE s2.market_id=s.market_id AND s2.ts < ?) IS NULL
                          OR (SELECT MAX(s2.ts) FROM snap s2 WHERE s2.market_id=s.market_id AND s2.ts < ?) < ?)""", t0, t1, t0, t0, cut7)
    if t == "first_disc":
        return one("SELECT COUNT(DISTINCT k1) FROM ce WHERE kind='scan' AND k3 LIKE '%erst%'" + base, *a)
    if t == "first_map":
        return one("""SELECT COUNT(DISTINCT m.k1) FROM ce m WHERE m.kind='mapd' AND m.ts >= ? AND m.ts <= ?
                      AND EXISTS (SELECT 1 FROM ce sc WHERE sc.kind='scan' AND sc.k1=m.k1 AND sc.k3 LIKE '%unkart%')""", t0, t1)
    if t == "new_species":
        return one("""SELECT COUNT(DISTINCT k2) FROM ce e WHERE kind='bio' AND ts >= ? AND ts <= ? AND NOT EXISTS
                      (SELECT 1 FROM ce e2 WHERE e2.kind='bio' AND e2.k2=e.k2 AND e2.ts < ?)""", t0, t1, t0)
    if t == "new_ring":
        return one("""SELECT COUNT(DISTINCT k1) FROM ce e WHERE kind='ring' AND x != 'p' AND ts >= ? AND ts <= ? AND NOT EXISTS
                      (SELECT 1 FROM ce e2 WHERE e2.kind='ring' AND e2.x != 'p' AND e2.k1=e.k1 AND e2.ts < ?)""", t0, t1, t0)
    if t == "dist_far":
        pr = c.execute("SELECT n1, n2, n3 FROM ce WHERE kind='pos' AND ts < ? ORDER BY ts DESC LIMIT 1", (t0,)).fetchone()
        ps = c.execute("SELECT n1, n2, n3 FROM ce WHERE kind='pos' AND ts >= ? AND ts <= ? ORDER BY ts", (t0, t1)).fetchall()
        if not ps:
            return 0
        st0 = pr or ps[0]
        return max(sum((u - v) ** 2 for u, v in zip((r[0], r[1], r[2]), (st0[0], st0[1], st0[2]))) ** 0.5 for r in ps)
    if t == "sprint":
        ts_ = [timefmt.parse_ts(r[0]).timestamp() for r in c.execute("SELECT ts FROM ce WHERE kind='jump' AND ts >= ? AND ts <= ? ORDER BY ts", (t0, t1))]
        best, j = 0, 0
        for i in range(len(ts_)):
            while ts_[i] - ts_[j] > 3600:
                j += 1
            best = max(best, i - j + 1)
        return best
    if t == "profit_single":
        return one("SELECT MAX(n3) FROM ce WHERE kind='trade' AND k3='sell'" + base, *a)
    if t == "big_haul":
        return one("SELECT MAX(n1) FROM ce WHERE kind='trade' AND k3='sell'" + base, *a)
    if t == "mine_variety":
        return one("SELECT COUNT(DISTINCT k1) FROM ce WHERE kind='mine'" + base, *a)
    if t == "unharmed":
        d = c.execute("SELECT MAX(ts) FROM ce WHERE kind='death' AND ts >= ? AND ts <= ?", (t0, t1)).fetchone()[0]
        return one("SELECT COUNT(*) FROM ce WHERE kind='kill' AND ts >= ? AND ts <= ?", d or t0, t1)
    if t == "missions":
        return one("SELECT COUNT(*) FROM ce WHERE kind='mis' AND k3='completed'" + base, *a)
    if t == "craft_n":
        return one("SELECT COUNT(*) FROM ce WHERE kind='craft'" + base, *a)
    if t == "mat_n":
        return one("SELECT SUM(n1) FROM ce WHERE kind='mat' AND n1>0" + base, *a)
    if t == "explore_cr":
        return one("SELECT SUM(n1) FROM ce WHERE kind='cash' AND k1='Exploration' AND n1>0" + base, *a)
    if t == "active_h":
        return one("SELECT COUNT(*) FROM act WHERE b >= ? AND b <= ?", t0[:15], t1[:15]) / 6.0
    if t == "long_jump":
        return one("SELECT MAX(n1) FROM ce WHERE kind='jump'" + base, *a)
    if t == "profit_per_t":
        return one("SELECT SUM(n1) FROM ce WHERE kind='trade' AND k3='sell' AND n1>0 AND n3 >= ? * n1" + base, o.get("per_t", 0), *a)
    return 0


def lm_eval(c):
    """Periodenmissionen anlegen, Fortschritt messen, erledigte/abgelaufene abschliessen."""
    nowu = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for scope, (key, ends, label) in _lm_periods().items():
        mid = f"{scope}:{key}"
        if not c.execute("SELECT 1 FROM lm WHERE id=?", (mid,)).fetchone():
            rng = random.Random(hashlib.sha256(mid.encode()).hexdigest())
            spec = lm_generate(c, scope, rng)
            spec.update(title=label + (": " + spec["chapter"] if spec.get("chapter") else ""), scope=scope, brief=spec.get("brief") or "Befehl des Kommandos: Erfülle alle Teilziele vor Ablauf der Frist.")
            c.execute("INSERT INTO lm VALUES(?,?,?,?,?,?,?,?,?,?)", (mid, scope, key, nowu, ends, "active", None, spec["dp"], json.dumps(spec, ensure_ascii=False), "[]"))
    for r in c.execute("SELECT id, created, ends, spec FROM lm WHERE status='active'").fetchall():
        spec = json.loads(r["spec"])
        vals = [lm_value(c, o, r["created"], min(nowu, r["ends"])) for o in spec["objs"]]
        done = bool(spec["objs"]) and all(v >= o["target"] for v, o in zip(vals, spec["objs"]))
        if done:
            c.execute("UPDATE lm SET status='done', done_ts=?, prog=? WHERE id=?", (min(nowu, r["ends"]), json.dumps(vals), r["id"]))
        elif nowu > r["ends"]:
            c.execute("UPDATE lm SET status='expired', prog=? WHERE id=?", (json.dumps(vals), r["id"]))
        else:
            c.execute("UPDATE lm SET prog=? WHERE id=?", (json.dumps(vals), r["id"]))
    c.commit()


def lm_stats(c):
    """Zaehler aus ERLEDIGTEN Journey-Missionen (Meilensteine/Raenge entstehen nur daraus). Gibt (Zaehler, Meilensteintermine, Rangtermine) zurueck."""
    cnt = defaultdict(float)
    stn, sysn = set(), set()
    when, rank_when = {}, {}
    rank_i = 0

    def check(ts):
        view = dict(cnt, st_distinct=len(stn), sys_distinct=len(sysn))
        for i, (k, th, _n, _d) in enumerate(LM_MILES):
            if i not in when and view.get(k, 0) >= th:
                when[i] = ts
    for r in c.execute("SELECT scope, done_ts, dp, spec FROM lm WHERE status='done' ORDER BY done_ts").fetchall():
        spec = json.loads(r["spec"])
        cnt["m_total"] += 1
        cnt["m_" + r["scope"] if r["scope"] in ("daily", "weekly", "monthly", "chapter") else "m_random"] += 1
        if spec.get("diff") == "schwer":
            cnt["m_hard"] += 1
        for o in spec["objs"]:
            k = LM_CNT.get(o["type"])
            if k:
                cnt[k] += o["target"]
            if o["type"] == "dock_at":
                stn.add(o["station"])
            if o["type"] == "visit_sys":
                sysn.add(o["system"])
        cnt["dp"] += r["dp"] or 0
        check(r["done_ts"])
        while rank_i + 1 < len(LM_RANKS) and cnt["dp"] >= LM_RANKS[rank_i + 1][0]:
            rank_i += 1
            rank_when[rank_i] = r["done_ts"]
    # Tagesserie: aufeinanderfolgende Kalendertage mit erledigter Tagesmission
    keys = sorted((x["period"], x["done_ts"]) for x in c.execute("SELECT period, done_ts FROM lm WHERE scope='daily' AND status='done'"))
    best = run = 0
    prev = None
    for k, dts in keys:
        d = datetime.strptime(k, "%Y-%m-%d").date()
        run = run + 1 if prev and (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d
        for i, (mk, th, _n, _d) in enumerate(LM_MILES):
            if mk == "streak" and run >= th and i not in when:
                when[i] = dts
    cnt["streak"] = best
    cnt["st_distinct"], cnt["sys_distinct"] = len(stn), len(sysn)
    for i, (k, th, _n, _d) in enumerate(LM_MILES):
        if i not in when and cnt.get(k, 0) >= th:
            when[i] = ""
    return dict(cnt), when, rank_when


def lm_api(body=None):
    c = database._mdb()
    c.row_factory = sqlite3.Row
    try:
        if body:
            op = body.get("op")
            nowu = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if op == "random":
                diff = body.get("diff") if body.get("diff") in ("leicht", "mittel", "schwer") else "mittel"
                if c.execute("SELECT COUNT(*) FROM lm WHERE scope='random' AND status='active'").fetchone()[0] >= 5:
                    return {"error": "Es laufen schon 5 Zufallsmissionen. Schließe oder gib eine auf."}
                rng = random.Random()
                spec = lm_generate(c, "random", rng, diff)
                n = c.execute("SELECT COUNT(*) FROM lm WHERE scope='random'").fetchone()[0] + 1
                names = {"leicht": "Routineflug", "mittel": "Sonderauftrag", "schwer": "Hochrisikoeinsatz"}
                spec.update(title=f"{names[diff]} #{n}", scope="random", brief="Zufällig generierter Auftrag aus deinen eigenen Aufzeichnungen.")
                ends = (datetime.now(timezone.utc) + timedelta(days={"leicht": 3, "mittel": 7, "schwer": 14}[diff])).strftime("%Y-%m-%dT%H:%M:%SZ")
                mid = f"random:{int(time.time() * 1000)}"
                c.execute("INSERT INTO lm VALUES(?,?,?,?,?,?,?,?,?,?)", (mid, "random", str(n), nowu, ends, "active", None, spec["dp"], json.dumps(spec, ensure_ascii=False), "[]"))
            elif op == "abandon":
                c.execute("UPDATE lm SET status='abandoned' WHERE id=? AND scope='random' AND status='active'", (str(body.get("id", "")),))
            c.commit()
        lm_eval(c)
        cnt, when, rank_when = lm_stats(c)
        rows = c.execute("SELECT id, scope, created, ends, status, done_ts, dp, spec, prog FROM lm ORDER BY created DESC").fetchall()
        out = {"active": [], "archive": [], "dp": cnt.get("dp", 0)}
        for r in rows:
            spec = json.loads(r["spec"])
            vals = json.loads(r["prog"] or "[]")
            m = {"id": r["id"], "scope": r["scope"], "title": spec.get("title"), "brief": spec.get("brief"), "diff": spec.get("diff"), "created": r["created"],
                 "ends": r["ends"], "status": r["status"], "done_ts": r["done_ts"], "dp": r["dp"],
                 "objs": [{"label": o["label"], "val": (vals[i] if i < len(vals) else 0), "target": o["target"]} for i, o in enumerate(spec["objs"])]}
            (out["active"] if r["status"] == "active" else out["archive"]).append(m)
        out["archive"] = out["archive"][:30]
        return out
    finally:
        c.close()


def akte_view(c, op):
    c.row_factory = sqlite3.Row
    lm_eval(c)
    cnt, when, rank_when = lm_stats(c)
    dp = int(cnt.get("dp", 0))
    ri = max([i for i, (t, _n) in enumerate(LM_RANKS) if dp >= t] or [0])
    if op == "ml_over":
        done = [(i, m) for i, m in enumerate(LM_MILES) if i in when]
        open_ = [(i, m) for i, m in enumerate(LM_MILES) if i not in when]
        view = dict(cnt)
        rows_d = [[m[2], m[3], when[i] or "-"] for i, m in sorted(done, key=lambda x: when[x[0]] or "9", reverse=True)]
        rows_o = []
        for i, m in open_:
            have = view.get(m[0], 0)
            rows_o.append([m[2], m[3], min(100, have / m[1] * 100), _lm_fmt(have) + " / " + _lm_fmt(m[1])])
        rows_o.sort(key=lambda r: -r[2])
        return {"kpi": [["Erreicht", len(done), "n"], ["Gesamt", len(LM_MILES), "n"], ["Dienstpunkte", dp, "n"], ["Dienstgrad", LM_RANKS[ri][1], "t"]],
                "blocks": [helpers._block("Erreichte Meilensteine", [["Meilenstein", "t"], ["Bedingung", "t"], ["Erreicht am", "d"]], rows_d,
                                  "Meilensteine zählen nur, was du in Journey-Missionen geleistet hast – altes Journal-Wissen bringt hier nichts."),
                           helpers._block("Noch offen", [["Meilenstein", "t"], ["Bedingung", "t"], ["Fortschritt", "p"], ["Stand", "t"]], rows_o)]}
    if op == "pa":
        _, cm = helpers._jload(c, "Commander")
        nxt = LM_RANKS[ri + 1] if ri + 1 < len(LM_RANKS) else None
        kpi = [["Kommandant", (cm or {}).get("Name", "-"), "t"], ["Dienstgrad", LM_RANKS[ri][1], "t"], ["Dienstpunkte", dp, "n"],
               ["Bis " + nxt[1] if nxt else "Höchster Rang", (nxt[0] - dp) if nxt else 0, "n"], ["Missionen erfüllt", int(cnt.get("m_total", 0)), "n"],
               ["Meilensteine", f"{len(when)} / {len(LM_MILES)}", "t"]]
        rk = [[LM_RANKS[i][1], LM_RANKS[i][0], rank_when.get(i, "") if i else "", "erreicht" if dp >= LM_RANKS[i][0] else "offen"] for i in range(len(LM_RANKS))]
        sh = [[r["ship"], r["f"], r["l"], r["n"]] for r in c.execute("SELECT ship, MIN(ts) f, MAX(ts) l, COUNT(*) n FROM ce WHERE ship NOT IN ('', 'Zu Fuß', 'SRV') GROUP BY ship ORDER BY f")]
        blocks = [helpers._block("Dienstgrade", [["Dienstgrad", "t"], ["Ab Dienstpunkten", "n"], ["Erreicht am", "d"], ["Status", "t"]], rk,
                         "Dienstpunkte gibt es für erfüllte Journey-Missionen (Tag 10, Woche 40, Monat 150, Zufall 5–25).")]
        sub = career_api.career_api({"op": "rank"})
        blocks += [b for b in sub.get("blocks", []) if b.get("title") in ("Ränge", "Beförderungen")]
        blocks.append(helpers._block("Schiffe im Dienst", [["Schiff", "t"], ["Erstmals", "d"], ["Zuletzt", "d"], ["Aufzeichnungen", "n"]], sh))
        st = career_api.career_api({"op": "stat"})
        blocks += [dict(b, title="Lebensstatistik · " + b["title"]) for b in st.get("blocks", [])]
        return {"kpi": kpi, "blocks": blocks, "note": st.get("note", "")}
    return {"error": "unbekannte Abfrage"}
