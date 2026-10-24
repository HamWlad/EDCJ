"""CSV-Exporte und Suche im Captain's Log."""

import re

from . import config, database


EXPORTS = {
    "markt_aktuell": ("Aktuelle Märkte", "SELECT st.name AS Station, st.system AS System, i.name AS Ware, i.cat AS Kategorie, i.buy AS Einkauf, i.sell AS Verkauf, "
                      "i.mean AS Durchschnitt, i.stock AS Bestand, i.demand AS Nachfrage, s.seen AS Stand " + database.MK_CURRENT + " ORDER BY st.name, i.name"),
    "markt_verlauf": ("Marktverlauf (alle Stände)", "SELECT st.name AS Station, st.system AS System, i.name AS Ware, s.ts AS Zeit, s.seen AS Bestaetigt, "
                      "i.buy AS Einkauf, i.sell AS Verkauf, i.stock AS Bestand, i.demand AS Nachfrage FROM item i JOIN snap s ON s.id=i.snap_id "
                      "JOIN station st ON st.market_id=s.market_id ORDER BY st.name, i.name, s.ts"),
    "ausruestung": ("Ausrüstung und Schiffe", "SELECT t.name AS Station, t.system AS System, CASE g.kind WHEN 'm' THEN 'Modul' ELSE 'Schiff' END AS Art, "
                    "g.label AS Bezeichnung, g.cat AS Kategorie, g.cls AS Klasse, g.price AS Preis_Cr, g.merc AS Preis_MercCoins, g.code AS Code, t.ts AS Stand "
                    "FROM gear g JOIN modst t ON t.market_id=g.market_id AND t.kind=g.kind ORDER BY t.name, g.label"),
    "stationen": ("Stationen und Siedlungen", "SELECT d.system AS System, d.name AS Name, d.type AS Typ, d.faction AS Fraktion, d.gov AS Regierung, d.eco AS Wirtschaft, "
                  "d.dist AS Entfernung_ls, d.via AS Quelle, d.first AS Erstmals, d.last AS Zuletzt, p.s AS Plattform_S, p.m AS Plattform_M, p.l AS Plattform_L "
                  "FROM stdb d LEFT JOIN pads p ON p.market_id=d.market_id ORDER BY d.system, d.name"),
    "systeme": ("Systeme mit Koordinaten", "SELECT y.system AS System, y.x AS X, y.y AS Y, y.z AS Z, "
                "(SELECT COUNT(*) FROM ce WHERE kind='jump' AND k1=y.system) AS Sprünge_hierher FROM syspos y ORDER BY y.system"),
    "spruenge": ("Sprünge", "SELECT ts AS Zeit, k1 AS System, n1 AS Distanz_Ly, n2 AS Treibstoff_t, ship AS Schiff FROM ce WHERE kind='jump' ORDER BY ts"),
    "handel": ("Handel (Käufe und Verkäufe)", "SELECT ts AS Zeit, k3 AS Art, k1 AS Ware, k2 AS Station, sys AS System, n1 AS Menge_t, n2 AS Betrag_Cr, n3 AS Gewinn_Cr FROM ce WHERE kind='trade' ORDER BY ts"),
    "buchungen": ("Alle Credit-Buchungen", "SELECT ts AS Zeit, k1 AS Kategorie, n1 AS Betrag_Cr, sys AS System, ship AS Schiff FROM ce WHERE kind='cash' ORDER BY ts"),
    "kampf": ("Abschüsse", "SELECT ts AS Zeit, k1 AS Ziel, k2 AS Fraktion, x AS Art, n1 AS Belohnung_Cr, sys AS System, ship AS Schiff FROM ce WHERE kind='kill' ORDER BY ts"),
    "notizen": ("Eigene Notizen", "SELECT kind AS Art, name AS Name, txt AS Notiz, ts AS Geaendert FROM notes ORDER BY kind, name"),
    "entdeckungen": ("Gescannte Körper", "SELECT MIN(ts) AS Zeit, sys AS System, k1 AS Koerper, k2 AS Typ, MAX(CASE WHEN k3 LIKE '%erst%' THEN 1 ELSE 0 END) AS Erstentdeckung, "
                     "MAX(n1) AS Schwerkraft_g, MAX(n2) AS Entfernung_ls FROM ce WHERE kind='scan' GROUP BY sys, k1 ORDER BY 1"),
    "carrier": ("Fleet Carrier (Messungen)", "SELECT ts AS Zeit, k1 AS Rufzeichen, k2 AS Name, n1 AS Tritium_t, n2 AS Kontostand_Cr, n3 AS Reserve_Cr FROM ce WHERE kind='cstat' ORDER BY ts"),
    "missionen": ("Missionen", "SELECT d.ts AS Angenommen, d.k1 AS ID, d.k2 AS Zielsystem, d.k3 AS Zielstation, d.x AS Frist, d.n1 AS Belohnung_Cr, d.y AS Details FROM ce d WHERE d.kind='mdet' ORDER BY d.ts"),
    "bergbau": ("Bergbau (raffiniert)", "SELECT ts AS Zeit, sys AS System, k2 AS Ring, k1 AS Erz, n1 AS Tonnen, ship AS Schiff FROM ce WHERE kind='mine' ORDER BY ts"),
    "hotspots": ("Ring-Hotspots", "SELECT h.sys AS System, h.k1 AS Ring, h.k2 AS Mineral, h.n1 AS Anzahl, h.k3 AS Quelle, MAX(h.ts) AS Zeit "
                 "FROM ce h WHERE h.kind='hot' GROUP BY h.k1, COALESCE(NULLIF(h.x,''), h.k2) ORDER BY h.sys, h.k1"),
    "landungen": ("Landungen", "SELECT ts AS Zeit, sys AS System, k1 AS Koerper, k2 AS Ziel, n1 AS Breite, n2 AS Laenge FROM ce WHERE kind='touch' ORDER BY ts"),
    "ereignisse": ("Alle Karriere-Datensätze", "SELECT ts AS Zeit, kind AS Art, sys AS System, ship AS Schiff, k1, k2, k3, x, y, n1, n2, n3 FROM ce ORDER BY ts"),
}


def export_csv(what):
    """CSV mit Semikolon, UTF-8 mit BOM und Dezimalkomma: laesst sich in deutschem Excel direkt oeffnen."""
    if what not in EXPORTS:
        return None, None
    title, sql = EXPORTS[what]
    c = database._mdb()
    try:
        cur = c.execute(sql)
        names = [d[0] for d in cur.description]
        out = [";".join(names)]
        esc_ = lambda v: ("" if v is None else (str(round(v, 3)).replace(".", ",") if isinstance(v, float) else str(v))).replace('"', '""')
        for r in cur:
            out.append(";".join('"' + esc_(v) + '"' if isinstance(v, str) else esc_(v) for v in r))
    finally:
        c.close()
    return "\ufeff" + "\r\n".join(out) + "\r\n", what


def search_log(q, limit=300):
    terms = [t for t in q.lower().split() if t]
    if not terms:
        return {"q": q, "total": 0, "results": [], "terms": []}
    try:
        with open(config.CONFIG["log"], encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    res, sess, sysn = [], "", ""
    for line in lines:
        if line.startswith("## "):
            sess, sysn = line[3:], ""
            continue
        m = re.match(r"- (?:(\d\d:\d\d) )?(.*)$", line)
        if not m or not sess:
            continue
        t, txt = m.group(1) or "", m.group(2)
        mm = re.match(r"(?:Sprung nach (.+?) \(|Flottenträger-Sprung nach (.+)$|Position: (.+)$)", txt)
        if mm:
            sysn = next(g for g in mm.groups() if g)
        sm = re.search(r" \| System: (.+)$", txt)
        if sm:
            sysn = sm.group(1)
        hay = (txt + " " + sysn).lower()
        if all(w in hay for w in terms):
            res.append({"session": sess, "time": t, "system": sysn, "text": txt})
    res.reverse()
    return {"q": q, "total": len(res), "results": res[:limit], "terms": terms}
